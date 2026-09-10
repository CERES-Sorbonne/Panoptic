"""The panoptic *home* (instance) registry -- legacy side (task 3.4).

Two things live outside a project folder: the list of projects panoptic knows
about, and the list of installed plugins. Where that list lives changed twice.

    <= 0.6.x   <datadir>/panoptic/projects.json   (a JSON file, no DB at all)
    0.7.x      <datadir>/panoptic/panoptic.db     (`panoptic`, `projects`,
                                                   `plugins`; db_version always 1)
    new        $PANOPTIC_DB or ~/.panoptic/panoptic.db  (`panoptic_config`,
                                                   `users`, `projects`, `plugins`)

`<datadir>` is `panoptic.utils.get_datadir()`: `~/Library/Application Support`
on macOS, `~/.local/share` on linux, `%APPDATA%` on windows -- **not** `~/.panoptic`.
The new layout moved the home to `~/.panoptic`, so the legacy home and the new
home are different files on disk and the migration never overwrites its source.

This module only *reads* the legacy side and normalises both shapes into
`LegacyHome`. `migrator/writers/panoptic_db.py` writes the new one.
"""

from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import sys
from collections import namedtuple

from .errors import AlreadyMigrated, SourceNotFound, UnknownShape

#: the legacy global registry has been `panoptic_db_version = 1` since it was
#: introduced in 0.7.0 and never changed (analysis/DBVERSION_MAP.md): one shape.
LEGACY_DB_VERSION = 1

LEGACY_TABLES = ("panoptic", "projects", "plugins")
TARGET_TABLES = ("panoptic_config", "users", "projects", "plugins")

#: legacy `plugins.type` (PluginType: local|git|pip) -> target `source_type`
#: (plugin_installer.SOURCE_*: path|git|pip). `local` was renamed `path`;
#: a copy would leave an unknown source_type that `reinstall` raises on.
PLUGIN_TYPE_MAP = {"local": "path", "path": "path", "git": "git", "pip": "pip"}
DEFAULT_PLUGIN_TYPE = "path"

LegacyProject = namedtuple("LegacyProject",
                           "id name path description ignored_plugins")
LegacyPlugin = namedtuple("LegacyPlugin", "name path type source")


# -- where the two homes live ------------------------------------------------

def default_home_db():
    """The *new* panoptic home DB (`main.py`: `$PANOPTIC_DB` or ~/.panoptic)."""
    return os.path.abspath(os.path.expanduser(
        os.environ.get("PANOPTIC_DB") or os.path.join("~", ".panoptic",
                                                      "panoptic.db")))


def legacy_datadir():
    """`panoptic.utils.get_datadir()`, reimplemented without importing panoptic."""
    home = pathlib.Path(os.path.expanduser("~"))
    if os.environ.get("PANOPTIC_DATA_DIR", ""):
        return pathlib.Path(os.environ["PANOPTIC_DATA_DIR"]) / "panoptic_data"
    if os.environ.get("IS_DOCKER", False):
        return pathlib.Path("/data")
    if sys.platform == "win32":
        return home / "AppData/Roaming"
    if sys.platform == "linux":
        return home / ".local/share"
    if sys.platform == "darwin":
        return home / "Library/Application Support"
    return home / ".local/share"


def legacy_home_dir():
    """`<datadir>/panoptic` -- where every legacy registry on this machine lives."""
    return legacy_datadir() / "panoptic"


def legacy_home_candidates(base=None):
    """*Every* legacy registry present on this machine, `panoptic.db` first.

    There is not necessarily one. 0.7 reads `$PANOPTIC_DB_NAME` (default
    `panoptic.db`) out of `<datadir>/panoptic`, so anyone who ever ran a second
    instance -- notably `panoptic-dev`, which ships as its own console script
    and writes `panoptic-dev.db` -- has **two registries side by side holding
    different project sets** (this is the case on the machine this migrator was
    developed on: `panoptic.db` and `panoptic-dev.db`, no overlap). Probing only
    the default name silently loses half the user's projects, so every `*.db`
    in the folder is returned, plus the <= 0.6.8 `projects.json`.

    Ordering is stable and deliberate: `panoptic.db`, then `$PANOPTIC_DB_NAME`
    if it is something else, then the remaining `.db` files alphabetically, then
    `projects.json`. Nothing is filtered on shape here -- `discover_homes()`
    classifies, so that an unreadable or already-migrated file is *reported*
    rather than quietly dropped from the list.
    """
    base = pathlib.Path(base) if base is not None else legacy_home_dir()
    try:
        names = sorted(p.name for p in base.iterdir()
                       if p.is_file() and p.suffix == ".db")
    except OSError:
        return []
    preferred = [n for n in ("panoptic.db", os.environ.get("PANOPTIC_DB_NAME"))
                 if n and n in names]
    ordered = preferred + [n for n in names if n not in preferred]
    found = [str(base / n) for n in ordered]
    js = base / "projects.json"
    if js.is_file():
        found.append(str(js))
    return found


#: one discovered registry: its path, its shape (or None), how many projects and
#: plugins it holds, and why it is unusable if it is.
DiscoveredHome = namedtuple("DiscoveredHome",
                            "path shape projects plugins problem")


def discover_homes(base=None):
    """Classify every registry `legacy_home_candidates()` finds.

    Never raises: a file that cannot be read becomes a row with `problem` set,
    because "there is a registry here and I could not read it" is information
    the user needs, and dropping it is exactly the silent-pick failure mode this
    function exists to prevent.
    """
    out = []
    for path in legacy_home_candidates(base):
        try:
            shape = detect_home(path)
        except (UnknownShape, SourceNotFound, OSError) as exc:
            out.append(DiscoveredHome(path, None, None, None, str(exc)))
            continue
        if shape == "target-db":
            out.append(DiscoveredHome(
                path, shape, None, None,
                "already in the new format -- this is a panoptic home written "
                "by the new Panoptic, not a legacy one; nothing to migrate"))
            continue
        try:
            legacy = read_legacy_home(path)
        except Exception as exc:                       # noqa: BLE001 - report it
            out.append(DiscoveredHome(path, shape, None, None, str(exc)))
            continue
        out.append(DiscoveredHome(path, shape, len(legacy.projects),
                                  len(legacy.plugins), None))
    return out


def usable_homes(discovered):
    """The subset of `discover_homes()` that `migrate_home` can actually read."""
    return [d for d in discovered if d.problem is None]


# -- shape detection ---------------------------------------------------------

def _tables(path):
    conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    try:
        return {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def detect_home(path):
    """Return `'legacy-db'`, `'legacy-json'` or `'target-db'` for `path`.

    Sniffed from `sqlite_master`, exactly like the project-side detector: the
    recorded `db_version` is a cross-check only, never the decision.
    """
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(path):
        raise SourceNotFound("no such file: %s" % path)
    if path.endswith(".json"):
        return "legacy-json"
    try:
        tables = _tables(path)
    except sqlite3.DatabaseError as exc:
        raise UnknownShape("%s is not a readable sqlite database (%s)"
                           % (path, exc))
    if set(TARGET_TABLES) <= tables:
        return "target-db"
    if set(LEGACY_TABLES) <= tables:
        return "legacy-db"
    raise UnknownShape(
        "%s is neither a legacy panoptic home (%s) nor a new one (%s); it has: %s"
        % (path, ", ".join(LEGACY_TABLES), ", ".join(TARGET_TABLES),
           ", ".join(sorted(tables)) or "(no tables)"))


# -- the normalised legacy home ---------------------------------------------

class LegacyHome:
    """`projects` + `plugins` read out of either legacy shape."""

    def __init__(self, path, shape, projects, plugins, version=None,
                 warnings=None):
        self.path = path
        self.shape = shape
        self.projects = projects
        self.plugins = plugins
        self.version = version
        self.warnings = list(warnings or ())

    def summary(self):
        return "%s: %d project(s), %d plugin(s)" % (
            self.shape, len(self.projects), len(self.plugins))

    def to_json(self):
        return {
            "path": self.path,
            "shape": self.shape,
            "recorded_db_version": self.version,
            "projects": [p._asdict() for p in self.projects],
            "plugins": [p._asdict() for p in self.plugins],
        }


def _json_list(raw, default=()):
    if raw in (None, ""):
        return list(default)
    if isinstance(raw, (list, tuple)):
        return list(raw)
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return list(default)
    return list(value) if isinstance(value, list) else list(default)


def read_legacy_home(path):
    """Read a legacy home into `LegacyHome`. Never opens it for writing."""
    shape = detect_home(path)
    if shape == "target-db":
        raise AlreadyMigrated(
            "%s is already in the new format (it has %s) -- there is nothing to "
            "migrate. Use `register` to add a migrated project to it."
            % (path, ", ".join(TARGET_TABLES)))
    if shape == "legacy-json":
        return _read_json_home(path)
    return _read_db_home(path)


def _read_db_home(path):
    path = os.path.abspath(os.path.expanduser(path))
    warnings = []
    conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
    try:
        version = None
        row = conn.execute(
            "SELECT value FROM panoptic WHERE key='db_version'").fetchone()
        if row is not None:
            try:
                version = int(row[0])
            except (TypeError, ValueError):
                version = row[0]
        if version != LEGACY_DB_VERSION:
            warnings.append(
                "legacy home records panoptic db_version=%r, expected %d; "
                "reading it as the only known shape anyway"
                % (version, LEGACY_DB_VERSION))
        cols = {r[1] for r in conn.execute("PRAGMA table_info(projects)")}
        projects = []
        for row in conn.execute(
                "SELECT id, name, path, %s, %s FROM projects ORDER BY id"
                % ("description" if "description" in cols else "NULL",
                   "ignored_plugins" if "ignored_plugins" in cols else "NULL")):
            projects.append(LegacyProject(
                id=row[0], name=row[1], path=row[2], description=row[3],
                ignored_plugins=_json_list(row[4])))
        plugins = [LegacyPlugin(name=r[0], path=r[1], type=r[2], source=r[3])
                   for r in conn.execute(
                       "SELECT name, path, type, source FROM plugins "
                       "ORDER BY name")]
    finally:
        conn.close()
    return LegacyHome(path, "legacy-db", projects, plugins, version, warnings)


def _read_json_home(path):
    """`<datadir>/panoptic/projects.json`, the <= 0.6.x shape.

    Two sub-shapes: with a `version` key (0.6-era, plugins are dicts of
    name/type/path/source) and without (older, plugins carry `source_url` and
    no type -- `convert_old_panoptic_json` derives git/local from it). Projects
    never had ids there; 0.7 assigned them `i + 1` on import, and so do we, so
    the same folder gets the same legacy id either way.
    """
    path = os.path.abspath(os.path.expanduser(path))
    warnings = []
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    version = data.get("version")
    projects = []
    for i, entry in enumerate(data.get("projects") or []):
        projects.append(LegacyProject(
            id=entry.get("id") if entry.get("id") is not None else i + 1,
            name=entry.get("name"), path=entry.get("path"),
            description=entry.get("description"),
            ignored_plugins=_json_list(entry.get("ignored_plugins"))))
    plugins = []
    for entry in data.get("plugins") or []:
        if isinstance(entry, str):
            # the oldest shape: a bare module path, no name and no source
            plugins.append(LegacyPlugin(
                name=os.path.basename(entry.rstrip("/\\")) or entry,
                path=entry, type="local", source=None))
            continue
        type_ = entry.get("type")
        if not type_:
            # convert_old_panoptic_json's rule, applied to the pre-version shape
            type_ = "git" if entry.get("source_url") else "local"
        plugins.append(LegacyPlugin(
            name=entry.get("name"), path=entry.get("path"), type=type_,
            source=entry.get("source") or entry.get("source_url")))
    if version is None:
        warnings.append(
            "%s has no `version` key: read as the pre-0.6 plugin shape "
            "(source_url -> git/local), the same rule "
            "`convert_old_panoptic_json` applies" % os.path.basename(path))
    return LegacyHome(path, "legacy-json", projects, plugins, version, warnings)


def map_plugin_type(legacy_type):
    """Legacy `plugins.type` -> target `plugins.source_type`, plus a warning.

    Returns `(source_type, warning_or_None)`. `local` is *renamed* `path` in the
    new installer, so a straight copy would leave a value
    `PluginInstaller.reinstall` raises `Unknown source_type` on.
    """
    key = (legacy_type or "").strip().lower()
    if key in PLUGIN_TYPE_MAP:
        mapped = PLUGIN_TYPE_MAP[key]
        if mapped != key:
            return mapped, ("plugin source type %r was renamed %r in the new "
                            "installer" % (legacy_type, mapped))
        return mapped, None
    return DEFAULT_PLUGIN_TYPE, (
        "unknown legacy plugin type %r: registered as %r (the new installer "
        "accepts only pip/git/path)" % (legacy_type, DEFAULT_PLUGIN_TYPE))


# -- legacy home -> new home -------------------------------------------------

class HomeMigrationResult:
    def __init__(self, source, target, legacy):
        self.source = source
        self.target = target
        self.legacy = legacy
        self.registered = []      # (legacy_id, new_uuid, path)
        self.skipped = []         # (legacy_id, path, reason)
        self.plugins = []
        self.notes = []

    def to_json(self):
        return {
            "source": self.source, "target": self.target,
            "shape": self.legacy.shape,
            "projects_registered": [
                {"legacy_id": a, "id": b, "path": c} for a, b, c in self.registered],
            "projects_skipped": [
                {"legacy_id": a, "path": b, "reason": c} for a, b, c in self.skipped],
            "plugins": list(self.plugins),
            "notes": self.notes,
        }

    def summary(self):
        return ("%d project(s) registered, %d skipped, %d plugin(s)"
                % (len(self.registered), len(self.skipped), len(self.plugins)))


def migrate_home(source, target, mapping=None, report=None):
    """Convert a legacy home registry into a new-format `panoptic.db`.

    `mapping` maps a legacy project path to the folder its migration produced.
    A project is registered **only** when a migrated folder can be found and its
    `project_config.id` read: `projects.id` must equal it, so inventing a UUID
    for an unmigrated folder would guarantee the `ID mismatch` that
    `load_project` raises. Unresolved projects are skipped and listed.

    Lookup order per legacy project: an explicit `--map` entry, then the legacy
    path itself (a folder migrated in place next to its old DB), then skip.
    """
    from .writers.panoptic_db import HomeDbError, read_project_config

    source = os.path.abspath(os.path.expanduser(source))
    legacy = read_legacy_home(source)
    mapping = {os.path.abspath(os.path.expanduser(k)):
               os.path.abspath(os.path.expanduser(v))
               for k, v in (mapping or {}).items()}

    result = HomeMigrationResult(source, os.path.abspath(
        os.path.expanduser(target)), legacy)
    for warning in legacy.warnings:
        result.notes.append(warning)
        if report is not None:
            report.warn(warning)

    from .writers.panoptic_db import PanopticHomeWriter
    with PanopticHomeWriter(target, report=report) as writer:
        for project in legacy.projects:
            legacy_path = os.path.abspath(os.path.expanduser(project.path or ""))
            folder = mapping.get(legacy_path, legacy_path)
            try:
                project_id, _, _ = read_project_config(folder)
            except HomeDbError as exc:
                result.skipped.append((project.id, project.path, str(exc)))
                continue
            writer.register_project(project_id, folder,
                                    name=project.name,
                                    excluded_plugins=project.ignored_plugins)
            result.registered.append((project.id, project_id, folder))
            if project.description:
                # `projects` has no description column; project_config carries it
                result.notes.append(
                    "project %r had a description in the legacy registry; the "
                    "new `projects` table has no such column (it belongs in "
                    "project_config.description): %r"
                    % (project.name, project.description))

        for plugin in legacy.plugins:
            writer.register_plugin(plugin.name, plugin.path, plugin.type,
                                   plugin.source)
            result.plugins.append(plugin.name)

        result.notes.extend(writer.notes)
        result.created = writer.created
        result.instance_id = writer.instance_id
    for note in result.notes:
        if report is not None and note not in report.warnings:
            report.warn(note)
    return result
