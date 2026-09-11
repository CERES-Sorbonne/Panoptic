---
tags: [inventory, backend]
zone: tests
---
# 09 · Tests & fixtures

Back to [[00 Backend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the pytest suite in `test/`, the vendored migrator suite in `panoptic/migration/tests/`, their data, and two manual helper scripts.

Run: `.venv/bin/python -m pytest test panoptic/migration/tests`. The migrator suite also runs on its own with `python -m unittest discover -s panoptic/migration/tests -t .`.
On 2026-09-11 `--collect-only` gave **249 tests collected, 3 modules failing at import**.

## Zone-level checks
- [ ] ⚠ 3 test modules are **broken at import** and are listed in [[99 Unused files]]:
  - `test/test_media_db.py` imports `_DEFAULT_IMAGE_TYPES`, which no longer exists in `media_db.py`.
  - `test/test_project.py` imports `PropertyType`, `Property`, `PropertyMode`, `InstanceProperty`, `DbCommit` and `Instance` from `panoptic.models`, which is now an empty package.
  - `test/test_project_db.py` imports `Tag` from `panoptic.models`.

  Because of these, `media.db`, `project.db` and the `Project` import flows have no running tests.
- [ ] `test_panoptic2.py` is named after the old `panoptic2` package. It tests `Panoptic` lifecycle, projects, users and plugins, and it still collects.
- [ ] `test/data/*.db` are binary fixtures. Check that they are regenerated whenever `create.py` schemas change.
- [ ] Nothing runs the suite in CI: no workflow in `.github/workflows/` calls pytest.

## Files: pytest suite
- [ ] `test/pytest.ini` · asyncio auto mode
- [ ] `test/conftest.py` · 92 L. Fixtures: `image_dir`, `import_csv`, `import_with_empty_csv`, `import_with_missing_csv`, `empty_project`, `instance_project`, `data_project`.
- [ ] `test/test_data_db.py` · 406 L. Structural vs logged split, cascades, undo cycles. Extended 2026-09-11.
- [ ] `test/test_legacy_migration.py` · 321 L. Legacy discovery, `panoptic.db` v1→v2, migration service.
- [ ] `test/test_panoptic2.py` · 312 L. `Panoptic` integration: lifecycle, projects, users, plugins.
- [ ] `test/test_panoptic_db.py` · 117 L. Projects, users and plugins CRUD cycles.
- [ ] `test/test_readonly_properties.py` · 204 L. Read-only and system property enforcement at the route layer.
- [ ] `test/test_task_manager.py` · 154 L. FIFO, priority, serial execution, dismiss, stop.

## Files: pytest data (all referenced by `conftest.py`)
- [ ] `test/data/data.db`
- [ ] `test/data/empty.db`
- [ ] `test/data/instance.db`
- [ ] `test/data/import.csv`
- [ ] `test/data/import_with_empty.csv`
- [ ] `test/data/import_with_missing.csv`
- [ ] `test/data/images/number_1.png`
- [ ] `test/data/images/2-3/number_2.png`
- [ ] `test/data/images/2-3/number_3.png`
- [ ] `test/data/images/4-6/number_4.png`
- [ ] `test/data/images/4-6/number_5.png`
- [ ] `test/data/images/4-6/number_6.png`
- [ ] `test/data/images/7-10/number_7.png`
- [ ] `test/data/images/7-10/number_8.png`
- [ ] `test/data/images/7-10/number_9.png`
- [ ] `test/data/images/7-10/number_10.png`

## Files: manual helpers (run by hand, not by tests)
- [ ] `test/export_to_import.py` · 96 L. Converts an export CSV (`local_path;sha1[sha1]`) into an import-ready CSV with fake columns.
- [ ] `test/gen_import_csv.py` · 120 L. Generates a large fake import CSV (every property type) for load-testing `Importer`.

## Files: vendored migrator suite
- [ ] `panoptic/migration/tests/__init__.py`
- [ ] `panoptic/migration/tests/test_detect.py` · 105 L. Detector on the 11 fixtures.
- [ ] `panoptic/migration/tests/test_readers.py` · 395 L. Every fixture into the IR, checked against `_fixture_report.json`.
- [ ] `panoptic/migration/tests/test_registry.py` · 580 L. Legacy home reader and home writer.
- [ ] `panoptic/migration/tests/test_roundtrip.py` · 947 L. Before/after invariants per fixture.
- [ ] `panoptic/migration/tests/test_writers.py` · 633 L. End-to-end writers plus post-conditions.

## Files: migrator fixtures (`panoptic/migration/tests/fixtures/`)
Each shape folder has a `panoptic.db` and a `_fixture_report.json`:
- [ ] `P0/`
- [ ] `P1/`
- [ ] `v1/`
- [ ] `v2/`
- [ ] `v3/`
- [ ] `v4/`
- [ ] `v5/`
- [ ] `v6/`
- [ ] `v7a/`
- [ ] `v7b/`
- [ ] `v7c/`, plus `v7c/image_data/atlas/0/atlas_0.png`
- [ ] `sample_images/` (10 images plus `sub/sub_star.png` and `sub/sub_wave.png`). This is the source folder the fixture projects were built from, and it's referenced in the fixture reports.
