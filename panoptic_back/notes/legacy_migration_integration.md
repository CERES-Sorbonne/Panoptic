# Plan — integrate `migration-panpoic` into Panoptic

Goal: on launch, Panoptic detects projects registered by any old (0.x) Panoptic and offers,
per project, to **build a migrated copy in a new folder** and register it. The old project,
its folder and the old registry are never written to.

Source tool: `~/migration-panpoic` — `migrate.py` + `migrator/` package.
Properties that make this easy: stdlib-only, never imports `panoptic`, opens all sources
read-only, always writes a brand-new folder, 158 unit tests, 11 schema-shape fixtures.

---

## 0. Decisions to take first

| Question | Recommendation |
|---|---|
| Vendor the migrator or depend on it? | **Vendor** `migrator/` → `panoptic_back/panoptic/migration/`. It has zero deps and never imports panoptic, so vendoring costs nothing and avoids a second PyPI release train. Keep `~/migration-panpoic` as upstream + a `scripts/sync_migrator.sh` and a `MIGRATOR_UPSTREAM` commit sha in `panoptic/migration/__init__.py` so drift is visible. |
| Ship the migrator's tests? | Exclude `migration/tests/` from the wheel, keep them in the repo and in CI. |
| Track what was already migrated? | New table in the **new** `panoptic.db` (see §2). Requires bumping that DB's `DbDescription.version` 1→2 with a migration entry — the app's own migration map, which is exactly what it is for. |
| Where do migrated copies go? | Default `<legacy project parent>/<name>-v2`, user-editable in the modal via the existing `FolderSelectionModal`. Destination must not exist or be empty (the migrator refuses otherwise). |
| Progress reporting | Panoptic-level background thread + socket events. The per-project `TaskManager` is not usable here — there is no project yet. |

---

## 1. Vendoring (phase A)

1. `cp -R ~/migration-panpoic/migrator panoptic_back/panoptic/migration` (drop `__pycache__`,
   keep `schema/*.sql` — the target DDL lives there, it is **not** generated at runtime).
2. Verify `.sql` files ship: `[tool.hatch.build.targets.sdist]` includes `/panoptic` wholesale,
   and the hatchling wheel includes package data by default — confirm with
   `hatch build && unzip -l dist/*.whl | grep migration/schema`.
3. Adjust two module-level behaviours that assume a hand-run CLI:
   - `cli.default_report_dir()` resolves to `<package>/reports` → inside site-packages.
     Do **not** use `migrator.cli` from the app; call the library API and set the report path
     explicitly to `<panoptic home>/migration-reports/`.
   - `home.legacy_datadir()` reimplements `panoptic.utils.get_datadir()`. Leave it as is
     (it is deliberately independent), but confirm it still matches the current
     `panoptic.utils` implementation, and add a `base=` override used by tests.
4. Wire the migrator's unittest suite into CI:
   `python -m unittest discover -s panoptic_back/panoptic/migration/tests -t panoptic_back`.

Public API the app will use (no CLI, no subprocess):
- `migration.home.discover_homes()` → `[DiscoveredHome(path, shape, projects, plugins, problem)]`
- `migration.home.read_legacy_home(path)` → `LegacyHome(projects=[...], plugins=[...])`
- `migration.detect.detect_db(path)` → `Detection(shape, recorded, warnings)`
- `migration.pipeline.run_pipeline(detection, source_db, target_dir, report, home_db=None)`
- `migration.report.Report`

Pass `home_db=None` so the migrator registers nothing itself; registration goes through the
existing `Panoptic.import_project()`, which already enforces `projects.id == project_config.id`.

---

## 2. Backend — state and schema (phase B)

New table in `panoptic.db` (`core/databases/panoptic/create.py`), version 1 → 2:

```
legacy_migrations(
  legacy_path TEXT PRIMARY KEY,   -- the old project folder (identity key)
  new_path    TEXT,               -- the migrated copy
  project_id  TEXT,               -- id registered in projects
  shape       TEXT,               -- v7c, P1, ...
  migrated_at TEXT,
  report_path TEXT,
  status      TEXT                -- done | failed | dismissed
)
```

Plus a `panoptic_config` flag `legacy_scan_dismissed` (bool) for "stop asking me".

This table is what makes the startup check idempotent: a legacy project is offered only if its
path has no `done`/`dismissed` row. Without it the banner reappears forever.

Also add `PANOPTIC_NO_LEGACY_SCAN=1` to skip discovery entirely (CI, docker, dev sandboxes).

---

## 3. Backend — service (phase B)

New `panoptic/core/panoptic/legacy_migration.py`, a `LegacyMigrationService` held by `Panoptic`:

- `discover() -> LegacyScan`
  - `discover_homes()` for every registry under the legacy datadir (there are usually **two**:
    `panoptic.db` and `panoptic-dev.db`, listing different projects — the UI must show both);
  - for each listed project: does the folder exist, is `panoptic.db` readable, `detect_db()`
    shape + recorded version, instance count (cheap `SELECT count(*)`), and status from
    `legacy_migrations`;
  - never raises: an unreadable registry/project becomes a row with a `problem` string
    (macOS TCC "access denied", unplugged volume, stray `-wal` sidecar — all expected).
  - Cheap enough to run at startup, but run it **off the startup path** anyway (thread), and
    cache the result on the service.
- `migrate(legacy_path, dest_path, name) -> MigrationRun` (background thread, one at a time)
  1. `detect_db(legacy/panoptic.db)`
  2. `run_pipeline(..., home_db=None)` with a `Report` subclass whose `step()`/`warn()` forward
     to a progress callback → socket events. The pipeline has 6 named stages; that is the
     whole progress bar, no changes needed inside the vendored code.
  3. write the md+json report into `<panoptic home>/migration-reports/`
  4. `Panoptic.import_project(dest_path)` to register + `_load_project` if the user asked
  5. insert the `legacy_migrations` row
  - On failure: leave the (partial) destination folder in place, record `status=failed` with the
    report path, and tell the user to delete that folder and retry — that is the tool's own
    recovery story, and the source is untouched either way.
- `dismiss(path | all)`.

Guards: refuse if destination exists and is non-empty; refuse if destination is inside the
source folder; warn if free disk space < size of the legacy `panoptic.db` × 1.5 (atlas sheets
are copied); note the memory profile (~1.2 KB/image, so a 4 M-image project wants ~4.5 GB).

Plugins: the legacy registry also lists plugins. Do **not** auto-install them. Show them as an
informational line ("this project used: panopticml") in the result.

---

## 4. Backend — routes + socket (phase B)

In `routes/panoptic_routes.py`:

- `GET  /legacy/projects` → `{registries: [...], projects: [{legacyPath, name, shape, recordedVersion, instanceCount, exists, status, problem, migratedTo}]}`
- `POST /legacy/migrate` `{legacyPath, destPath, name, load?}` → 202 + run id
- `POST /legacy/dismiss` `{path?}` (omit `path` = dismiss all)
- `GET  /legacy/report/{runId}` → the markdown report, for display and download

In `PanopticServer`:
- `on_startup()` kicks the discovery thread; result broadcast as `legacy_projects`
- `legacy_migration_state` emitted on each pipeline stage and at completion
- after a successful migration, reuse `_emit_update_projects()`

---

## 5. Frontend (phase C)

- `data/apiPanopticRoutes.ts`: `apiGetLegacyProjects`, `apiMigrateLegacyProject`,
  `apiDismissLegacy`, `apiGetLegacyReport`.
- `data/panopticStore.ts`: `legacyProjects`, `legacyScanDone`, `legacyMigration` (run state);
  subscribe to the two new socket events.
- `views/HomeView.vue`: a banner above the project list when `legacyProjects.length > 0`,
  next to the existing `FirstModal` logic (note: `FirstModal` currently shows when there are
  **no** projects — the common upgrade case is exactly "no new projects, several old ones", so
  the legacy banner must take precedence over `FirstModal`).
- New `components/modals/LegacyImportModal.vue`:
  - one row per legacy project: name, path, shape/version, image count, status;
  - destination folder (prefilled, editable via `FolderSelectionModal`);
  - explicit copy: *"Le projet d'origine n'est jamais modifié — une copie convertie est créée
    dans un nouveau dossier."*;
  - per-stage progress, then a result panel listing the migrator's warnings in plain language:
    missing files on disk, no/partial thumbnails ("resynchroniser le dossier"), **tabs and UI
    layout are not carried over**, vectors must be recomputed;
  - links "ouvrir le rapport" and "ignorer".
- i18n keys in `locales/fr.json` + `en.json` (the repo is bilingual; recent commits are translations).

---

## 6. Tests (phase D)

- Keep the migrator's 158 tests green in CI.
- New backend tests:
  - discovery against a fake datadir (`base=` override) containing a legacy `panoptic.db`,
    a `projects.json` home and an unreadable file → three rows, one with `problem`;
  - end-to-end: migrate `fixtures/v7c` → `Panoptic.import_project` → `load_project` succeeds
    and reads folders/instances/properties/tags (the migrator already has a UI-acceptance
    script, `scripts/ui_acceptance.py`, worth porting as a pytest);
  - idempotence: a second scan does not re-offer a migrated project;
  - refusal paths: non-empty destination, missing source, id mismatch.
- Manual pass on this machine: both real registries under
  `~/Library/Application Support/panoptic/` (they list different projects), plus a large
  project for timing/RSS.

---

## 7. Suggested order

- **A** vendor + CI green (half a day)
- **B** schema bump, service, routes, socket (1–2 days)
- **C** store + banner + modal + i18n (1–2 days)
- **D** tests + manual pass on real registries (half a day)

Ship A+B behind `GET /legacy/projects` first: it is testable with curl before any UI exists.

---

## 8. Known risks

1. **Two registries.** Reading only `panoptic.db` silently hides half the user's projects.
2. **Detection lies.** `db_version` is known to be wrong; always trust `detect_db()`'s sniffed
   shape. The UI should show the shape, not the recorded version.
3. **macOS TCC.** Projects under `~/Desktop`/`~/Documents`/`~/Downloads` give *access denied*,
   not *not found*. The message must say "grant Full Disk Access", never "files are missing".
4. **Thumbnails.** Migrated projects are routinely thumbnail-poor and the new Panoptic does not
   backfill. The result panel must offer/explain a resync.
5. **Semantics validated on synthetic fixtures only** — the three real projects tested had zero
   properties, tags or values. First real user migration with tags is the actual acceptance test.
6. **Writing to a migrated project was never exercised** by the migration project ("load
   acceptance" only). Phase D should add one write + undo on a migrated fixture.
