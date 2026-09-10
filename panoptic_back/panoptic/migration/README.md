# `panoptic.migration` — legacy (0.x) project migrator

Vendored from the standalone `migration-panpoic` tool. **stdlib only**, and it
must never import `panoptic` — that is what lets it stay syncable from upstream
and runnable on a machine with no panoptic install.

Re-vendor with `panoptic_back/scripts/sync_migrator.sh` (upstream path
overridable via `$MIGRATOR_UPSTREAM_DIR`). Provenance lives in
`MIGRATOR_UPSTREAM` in `__init__.py`.

## Running the tests

There is currently **no CI job that runs unit tests** in this repository
(`.github/workflows/` only builds, publishes and smoke-installs), so this suite
has to be run by hand:

```sh
cd panoptic_back
python -m unittest discover -s panoptic/migration/tests -t .
```

158 tests. The fixtures (one real legacy project per schema shape, ~2 MB) live
in `tests/fixtures/`; both `tests/` and its fixtures are excluded from the
built wheel and sdist (see `[tool.hatch.build.targets.*] exclude` in
`pyproject.toml`).

## Public API used by the app

Do **not** use `cli.py` from the app: `cli.default_report_dir()` resolves to
`<package>/reports`, which is inside site-packages once installed. Call the
library directly and pass explicit paths.

```python
from panoptic.migration.home import discover_homes, read_legacy_home  # DiscoveredHome, LegacyHome
from panoptic.migration.detect import detect_db                       # -> Detection
from panoptic.migration.pipeline import run_pipeline
from panoptic.migration.report import Report

detection = detect_db("<legacy project>/panoptic.db")
report = Report(source_dir, source_db, target_dir, dry_run=False)
report.on_step = lambda name, detail: ...        # progress callback
run_pipeline(detection, source_db, target_dir, report, home_db=None)
report.write_markdown(path); report.write(path)  # caller chooses the path
```

`home_db=None` means the migrator registers nothing itself; registration goes
through `Panoptic.import_project()`.
