"""Detect projects registered by an old (0.x) Panoptic and migrate copies of them.

Nothing here ever writes to a legacy project folder or a legacy registry: the
vendored migrator (`panoptic.migration`) opens every source strictly read-only
and always writes a brand-new destination folder. A migration therefore has a
trivial recovery story — delete the destination and try again.

Bookkeeping lives in the new `panoptic.db`'s `legacy_migrations` table, keyed by
the *legacy* folder path, so a project that was migrated or explicitly dismissed
is never offered again.
"""
from __future__ import annotations

import dataclasses
import logging
import os
import shutil
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from panoptic.core.databases.panoptic.models import LegacyMigration

logger = logging.getLogger(__name__)

#: rough RSS the migrator needs, per image, while it holds the IR in memory
BYTES_PER_INSTANCE = 1200

STATUS_DONE = 'done'
STATUS_FAILED = 'failed'
STATUS_DISMISSED = 'dismissed'


# ---------------------------------------------------------------------------
# Result shapes  (plain dataclasses; the routes camelCase them on the way out)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class LegacyRegistry:
    path: str
    shape: Optional[str] = None
    projects: Optional[int] = None
    plugins: Optional[int] = None
    problem: Optional[str] = None


@dataclasses.dataclass
class LegacyProjectInfo:
    legacy_path: str
    name: Optional[str] = None
    registry: Optional[str] = None
    shape: Optional[str] = None
    recorded_version: object = None
    instance_count: Optional[int] = None
    exists: bool = False
    status: Optional[str] = None          # done | failed | dismissed | None
    problem: Optional[str] = None
    migrated_to: Optional[str] = None
    suggested_path: Optional[str] = None
    plugins: list[str] = dataclasses.field(default_factory=list)
    db_size: Optional[int] = None


@dataclasses.dataclass
class LegacyScan:
    registries: list[LegacyRegistry] = dataclasses.field(default_factory=list)
    projects: list[LegacyProjectInfo] = dataclasses.field(default_factory=list)
    skipped: bool = False
    reason: Optional[str] = None


@dataclasses.dataclass
class MigrationRun:
    id: str
    legacy_path: str
    dest_path: str
    name: str
    status: str = 'pending'   # pending | running | done | failed
    stage: Optional[str] = None
    stage_index: int = 0
    stage_count: int = 0
    detail: Optional[str] = None
    error: Optional[str] = None
    warnings: list[str] = dataclasses.field(default_factory=list)
    plugins: list[str] = dataclasses.field(default_factory=list)
    report_path: Optional[str] = None
    project_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Read-only probing helpers
# ---------------------------------------------------------------------------

def _describe_os_error(path: str, exc: BaseException) -> str:
    """Turn an OSError on a legacy path into something a user can act on.

    The three causes seen in the wild are genuinely different and must not all
    read as "files are missing".
    """
    if isinstance(exc, PermissionError) or getattr(exc, 'errno', None) == 1:
        return (f"access denied reading {path} — macOS is blocking Panoptic from "
                f"this folder. Grant Full Disk Access to Panoptic (or your "
                f"terminal) in System Settings › Privacy & Security, then retry.")
    if getattr(exc, 'errno', None) in (2, 19, 6):
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            return (f"{path} is not reachable — the folder is gone or lives on a "
                    f"volume that is not mounted. Plug the drive back in and retry.")
    return f"{path} could not be read: {exc}"


def _sidecar_warning(db_path: str) -> Optional[str]:
    stray = [s for s in ('-wal', '-shm') if os.path.exists(db_path + s)]
    if not stray:
        return None
    return (f"{os.path.basename(db_path)} has leftover {', '.join(stray)} "
            f"sidecar file(s): the old Panoptic did not shut down cleanly. The "
            f"migration reads the database read-only and will not replay them, "
            f"so the very last unsaved changes may be missing.")


def _count_instances(db_path: str) -> tuple[Optional[int], Optional[str]]:
    """Cheap read-only image count. Never raises."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return None, f"cannot open {db_path} read-only: {exc}"
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for table in ('instances', 'images'):
            if table in tables:
                return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0], None
        return None, None
    except sqlite3.Error as exc:
        return None, f"could not count images in {db_path}: {exc}"
    finally:
        conn.close()


def suggest_destination(legacy_path: str, name: str) -> str:
    """`<legacy parent>/<name>-v2`, with a numeric suffix on collision."""
    parent = os.path.dirname(os.path.abspath(legacy_path))
    base = (name or os.path.basename(os.path.abspath(legacy_path)) or 'project')
    base = base.strip().replace(os.sep, '_') or 'project'
    candidate = os.path.join(parent, f"{base}-v2")
    i = 2
    while os.path.exists(candidate) and os.listdir(candidate):
        candidate = os.path.join(parent, f"{base}-v2-{i}")
        i += 1
    return candidate


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class LegacyMigrationService:
    """Owned by `Panoptic`; constructed in `Panoptic.start()`."""

    def __init__(self, panoptic, home_dir: str | Path | None = None):
        self._panoptic = panoptic
        self.home_dir = Path(home_dir) if home_dir else Path(panoptic.db_path).parent
        self.reports_dir = self.home_dir / 'migration-reports'

        self._scan: LegacyScan | None = None
        self._lock = threading.Lock()
        self._runs: dict[str, MigrationRun] = {}
        self._active: str | None = None
        self._thread: threading.Thread | None = None

        #: set by the server: fn(MigrationRun) -> None, called on every state change
        self.on_migration_state: Callable[[MigrationRun], None] | None = None
        #: set by the server: fn(LegacyScan) -> None, called when discovery finishes
        self.on_scan: Callable[[LegacyScan], None] | None = None

    # -- discovery ------------------------------------------------------

    @property
    def scan(self) -> LegacyScan | None:
        return self._scan

    def is_disabled(self) -> tuple[bool, Optional[str]]:
        if os.environ.get('PANOPTIC_NO_LEGACY_SCAN') == '1':
            return True, 'PANOPTIC_NO_LEGACY_SCAN=1'
        try:
            if getattr(self._panoptic.db.config, 'legacy_scan_dismissed', False):
                return True, 'legacy_scan_dismissed'
        except Exception:
            pass
        return False, None

    def discover(self, base: str | Path | None = None, force: bool = False) -> LegacyScan:
        """Classify every legacy registry on this machine and its projects.

        Never raises. `base` overrides the legacy home directory (tests only).
        """
        disabled, reason = self.is_disabled()
        if disabled and not force:
            self._scan = LegacyScan(skipped=True, reason=reason)
            return self._scan
        try:
            self._scan = self._discover(base)
        except Exception as exc:                      # noqa: BLE001 — never crash startup
            logger.exception("legacy discovery failed")
            self._scan = LegacyScan(skipped=True, reason=str(exc))
        return self._scan

    def _discover(self, base) -> LegacyScan:
        from panoptic.migration.home import discover_homes, read_legacy_home

        handled = {m.legacy_path: m for m in self._panoptic.db.get_legacy_migrations()}
        scan = LegacyScan()
        seen: set[str] = set()

        for home in discover_homes(base):
            scan.registries.append(LegacyRegistry(
                path=home.path, shape=home.shape, projects=home.projects,
                plugins=home.plugins, problem=home.problem))
            if home.problem is not None:
                continue
            try:
                legacy = read_legacy_home(home.path)
            except Exception as exc:                  # noqa: BLE001
                scan.registries[-1].problem = str(exc)
                continue

            plugin_names = [p.name for p in legacy.plugins if p.name]
            for project in legacy.projects:
                if not project.path:
                    continue
                path = os.path.abspath(os.path.expanduser(project.path))
                if path in seen:
                    continue
                seen.add(path)

                recorded = handled.get(path)
                if recorded and recorded.status in (STATUS_DONE, STATUS_DISMISSED):
                    continue

                info = self._inspect_project(path, project, home.path, plugin_names)
                if recorded:
                    info.status = recorded.status
                    info.migrated_to = recorded.new_path
                scan.projects.append(info)

        return scan

    def _inspect_project(self, path, project, registry_path, plugin_names) -> LegacyProjectInfo:
        from panoptic.migration.detect import detect_db

        name = project.name or os.path.basename(path)
        info = LegacyProjectInfo(
            legacy_path=path, name=name, registry=registry_path,
            plugins=list(plugin_names),
            suggested_path=suggest_destination(path, name),
        )
        db_path = os.path.join(path, 'panoptic.db')
        try:
            info.exists = os.path.isdir(path)
        except OSError as exc:
            info.problem = _describe_os_error(path, exc)
            return info
        if not info.exists:
            info.problem = _describe_os_error(path, FileNotFoundError(2, 'no such folder'))
            return info
        try:
            if not os.path.isfile(db_path):
                info.problem = (f"{path} has no panoptic.db — it is registered by the "
                                f"old Panoptic but is not (or no longer) a project folder.")
                return info
            info.db_size = os.path.getsize(db_path)
        except OSError as exc:
            info.problem = _describe_os_error(db_path, exc)
            return info

        # Probe readability first: sqlite reports a TCC denial as a generic
        # "unable to open database file", which must not be shown as "missing".
        try:
            with open(db_path, 'rb') as fh:
                fh.read(16)
        except OSError as exc:
            info.problem = _describe_os_error(db_path, exc)
            return info

        try:
            detection = detect_db(db_path)
            info.shape = detection.shape
            info.recorded_version = detection.facts.recorded_db_version
        except Exception as exc:                      # noqa: BLE001
            if isinstance(exc, OSError):
                info.problem = _describe_os_error(db_path, exc)
            else:
                info.problem = str(exc)
            return info

        count, problem = _count_instances(db_path)
        info.instance_count = count
        sidecar = _sidecar_warning(db_path)
        info.problem = problem or sidecar
        return info

    # -- guards ---------------------------------------------------------

    def check_destination(self, legacy_path: str, dest_path: str) -> list[str]:
        """Raise ValueError on a refusal; return a list of non-fatal warnings."""
        src = os.path.abspath(os.path.expanduser(legacy_path))
        dest = os.path.abspath(os.path.expanduser(dest_path))

        if not os.path.isdir(src):
            raise ValueError(f"{src} does not exist — nothing to migrate.")
        db_path = os.path.join(src, 'panoptic.db')
        if not os.path.isfile(db_path):
            raise ValueError(f"{src} has no panoptic.db — not an old Panoptic project.")
        if dest == src:
            raise ValueError("The destination must be a different folder from the source.")
        try:
            inside = os.path.commonpath([src, dest]) == src
        except ValueError:      # different drives on Windows
            inside = False
        if inside:
            raise ValueError(
                f"The destination {dest} is inside the source project {src}. "
                f"Choose a folder outside the old project.")
        if os.path.isdir(dest) and os.listdir(dest):
            raise ValueError(f"{dest} already exists and is not empty. "
                             f"Choose another folder, or delete that one first.")
        if os.path.exists(dest) and not os.path.isdir(dest):
            raise ValueError(f"{dest} exists and is not a folder.")

        warnings: list[str] = []
        try:
            size = os.path.getsize(db_path)
            free = shutil.disk_usage(os.path.dirname(dest) or '/').free
            if free < size * 1.5:
                warnings.append(
                    f"Only {free // (1024 ** 2)} MB free where the copy would go, "
                    f"and the old database alone is {size // (1024 ** 2)} MB "
                    f"(thumbnail atlas sheets are copied too). Free up space first.")
        except OSError:
            pass

        count, _ = _count_instances(db_path)
        if count:
            need = count * BYTES_PER_INSTANCE
            if need > 1024 ** 3:
                warnings.append(
                    f"{count} images: the migration holds about "
                    f"{need / 1024 ** 3:.1f} GB in memory while it runs.")
        return warnings

    # -- migration ------------------------------------------------------

    def get_run(self, run_id: str) -> MigrationRun | None:
        return self._runs.get(run_id)

    def migrate(self, legacy_path: str, dest_path: str, name: str | None = None,
                load: bool = False) -> MigrationRun:
        """Start a migration on a background thread. One at a time."""
        src = os.path.abspath(os.path.expanduser(legacy_path))
        dest = os.path.abspath(os.path.expanduser(dest_path))
        name = name or os.path.basename(dest)

        warnings = self.check_destination(src, dest)

        with self._lock:
            if self._active is not None:
                active = self._runs[self._active]
                raise ValueError(
                    f"A migration is already running ({active.name}, stage "
                    f"{active.stage or 'starting'}). Wait for it to finish.")
            run = MigrationRun(id=str(uuid.uuid4()), legacy_path=src,
                               dest_path=dest, name=name, status='pending',
                               warnings=list(warnings))
            self._runs[run.id] = run
            self._active = run.id

        self._thread = threading.Thread(
            target=self._run, args=(run, load), name='legacy-migration', daemon=True)
        self._thread.start()
        return run

    def _emit(self, run: MigrationRun) -> None:
        if self.on_migration_state:
            try:
                self.on_migration_state(run)
            except Exception:                          # noqa: BLE001
                logger.exception("legacy migration state callback failed")

    def _run(self, run: MigrationRun, load: bool) -> None:
        from panoptic.migration.detect import detect_db
        from panoptic.migration.pipeline import PIPELINE, run_pipeline
        from panoptic.migration.report import Report

        source_db = os.path.join(run.legacy_path, 'panoptic.db')
        run.status = 'running'
        run.stage_count = len(PIPELINE)
        self._emit(run)

        self.reports_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        slug = ''.join(c if c.isalnum() or c in '-_' else '_' for c in run.name)[:60]
        md_path = self.reports_dir / f"{stamp}-{slug}.md"
        json_path = self.reports_dir / f"{stamp}-{slug}.json"
        run.report_path = str(md_path)

        report = Report(run.legacy_path, source_db, run.dest_path, False)

        def on_step(step_name, detail=''):
            run.stage = step_name
            run.detail = detail
            run.stage_index = next(
                (i + 1 for i, s in enumerate(PIPELINE) if s.name == step_name),
                run.stage_index + 1)
            self._emit(run)

        report.on_step = on_step

        try:
            detection = detect_db(source_db)
            report.set_detection(detection)
            run_pipeline(detection, source_db, run.dest_path, report, home_db=None)
            report.status = 'ok'

            key = self._panoptic.import_project(run.dest_path)
            run.project_id = key.id
            self._record(run, detection.shape, STATUS_DONE)

            run.warnings.extend(report.warnings)
            run.plugins = self._plugins_for(run.legacy_path)
            run.status = 'done'
            run.stage = 'done'
            run.stage_index = run.stage_count
        except Exception as exc:                       # noqa: BLE001
            logger.exception("legacy migration failed for %s", run.legacy_path)
            report.status = 'failed'
            report.error(str(exc))
            run.status = 'failed'
            run.error = str(exc)
            run.warnings.extend(report.warnings)
            shape = report.detection.shape if report.detection else None
            try:
                self._record(run, shape, STATUS_FAILED)
            except Exception:                          # noqa: BLE001
                logger.exception("could not record failed legacy migration")
        finally:
            try:
                report.write_markdown(str(md_path))
                report.write(str(json_path))
            except Exception:                          # noqa: BLE001
                logger.exception("could not write migration report")
            with self._lock:
                self._active = None
            # rescan BEFORE the final emit: the server broadcasts the refreshed
            # legacy_projects list off the back of that event, and a stale scan
            # would still list the project we just migrated.
            if run.status == 'done':
                try:
                    self.discover()
                except Exception:                      # noqa: BLE001
                    logger.exception("rescan after migration failed")
            self._emit(run)
            if run.status == 'done' and load and run.project_id:
                try:
                    self._panoptic.load_project(run.project_id)
                except Exception:                      # noqa: BLE001
                    logger.exception("loading the migrated project failed")

    def _plugins_for(self, legacy_path: str) -> list[str]:
        scan = self._scan
        if not scan:
            return []
        for p in scan.projects:
            if p.legacy_path == legacy_path:
                return list(p.plugins)
        return []

    def _record(self, run: MigrationRun, shape, status: str) -> None:
        self._panoptic.db.set_legacy_migration(LegacyMigration(
            legacy_path=run.legacy_path,
            new_path=run.dest_path,
            project_id=run.project_id,
            shape=shape,
            migrated_at=datetime.now().astimezone().isoformat(timespec='seconds'),
            report_path=run.report_path,
            status=status,
        ))

    # -- dismissal ------------------------------------------------------

    def dismiss(self, path: str | None = None) -> LegacyScan:
        """Dismiss one legacy project, or (path=None) stop asking entirely."""
        if path:
            target = os.path.abspath(os.path.expanduser(path))
            self._panoptic.db.set_legacy_migration(LegacyMigration(
                legacy_path=target,
                migrated_at=datetime.now().astimezone().isoformat(timespec='seconds'),
                status=STATUS_DISMISSED,
            ))
        else:
            self._panoptic.db.set_config_key('legacy_scan_dismissed', True)
        return self.discover()
