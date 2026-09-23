---
tags: [inventory, backend]
zone: migration
---
# 08 · Legacy migration (vendored migrator)

Back to [[00 Backend inventory]] · Unused files: [[99 Unused files]]

**Scope:** `panoptic/migration/` converts any of the 11 legacy project shapes (P0, P1, v1–v7c) into the new multi-database format. It's **vendored** from the standalone `~/migration-panpoic` tool by `scripts/sync_migrator.sh`. At runtime it's reached through `core/panoptic/legacy_migration.py`, and on its own through `python -m panoptic.migration`. The integration notes are in `notes/legacy_migration_integration.md`.

## Zone-level checks
- [ ] **Don't hand-edit** unless the change is also made upstream. `sync_migrator.sh` does `rm -rf panoptic/migration` and re-copies. The only allowed local changes are the ones listed in the script: tests import `panoptic.migration.*`, and fixture paths point to `tests/fixtures`.
- [ ] `schema/*.sql` are copies of this repo's own `create.py` schemas. After changing `entity_schema.py` or any `create.py`, check `schema/check.py`'s fingerprint against `schema/upstream.json`.
- [ ] `schema/*.sql` are shipped as wheel artifacts (`pyproject.toml` → `artifacts`), and `migration/tests` is excluded from the wheel and sdist.
- [ ] `migration/__init__.py` holds its own `__version__` and the `MIGRATOR_UPSTREAM` provenance, which is separate from the empty `panoptic/__init__.py`.

## Files: package
- [ ] `panoptic/migration/__init__.py` · 20 L. Package docstring, migrator `__version__`, `MIGRATOR_UPSTREAM` marker.
- [ ] `panoptic/migration/__main__.py` · 7 L. `python -m panoptic.migration`, which calls `cli.main`.
- [ ] `panoptic/migration/cli.py` · 555 L. Argparse CLI (`<old_project> <new_project>`, discover mode) and run reports.
- [ ] `panoptic/migration/README.md`. Upstream usage doc.
- [ ] `panoptic/migration/detect.py` · 241 L. Source shape detection (`SchemaFacts`, `sniff`, `detect_db`).
- [ ] `panoptic/migration/errors.py` · 22 L. `MigratorError`, `SourceNotFound`, `UnknownShape`, `TargetExists`, `AlreadyMigrated`.
- [ ] `panoptic/migration/home.py` · 435 L. Reads the legacy home/instance registry (where old installs kept their project list).
- [ ] `panoptic/migration/ir.py` · 302 L. The intermediate representation every reader produces.
- [ ] `panoptic/migration/pipeline.py` · 201 L. `run_pipeline` and `register_project`.
- [ ] `panoptic/migration/report.py` · 180 L. `Report`: structured record of one run.
- [ ] `panoptic/migration/source.py` · 64 L. Resolves and guards source and target folders.

## Files: readers & legacy chain
- [ ] `panoptic/migration/readers/__init__.py` · 106 L. `reader_for`, `read_source`.
- [ ] `panoptic/migration/readers/base.py` · 430 L. Shared reader machinery (dtype, colour and parent normalisation, served-URL stripping).
- [ ] `panoptic/migration/readers/modern.py` · 110 L. `ModernReader`, `V7Reader` (v1–v7c).
- [ ] `panoptic/migration/readers/prehistoric.py` · 165 L. `P0Reader`, `P1Reader`.
- [ ] `panoptic/migration/legacy/__init__.py` · 48 L. Verbatim copies of old `project_db/migrations/v*.py`.
- [ ] `panoptic/migration/legacy/v3.py` · 28 L
- [ ] `panoptic/migration/legacy/v4.py` · 2 L
- [ ] `panoptic/migration/legacy/v5.py` · 2 L
- [ ] `panoptic/migration/legacy/v6.py` · 6 L
- [ ] `panoptic/migration/legacy/v7.py` · 15 L

## Files: writers
- [ ] `panoptic/migration/writers/__init__.py` · 49 L. Writer entry points.
- [ ] `panoptic/migration/writers/data_db.py` · 262 L. Writes `data.db` (journal plus entities).
- [ ] `panoptic/migration/writers/genesis.py` · 147 L. The genesis journal: the one code path that writes a logged entity.
- [ ] `panoptic/migration/writers/ids.py` · 94 L. System property ids and `id_registry` seeds.
- [ ] `panoptic/migration/writers/media_db.py` · 181 L. Writes `media.db` (thumbnails, atlas, maps).
- [ ] `panoptic/migration/writers/panoptic_db.py` · 258 L. Registers the project in the home `panoptic.db`.
- [ ] `panoptic/migration/writers/postcheck.py` · 294 L. Post-conditions checked on the output DBs.
- [ ] `panoptic/migration/writers/project_db.py` · 168 L. Writes `project.db`.

## Files: target schema copy
- [ ] `panoptic/migration/schema/__init__.py` · 108 L. `schema_path`, `schema_sql`, `create_db`, `table_names`.
- [ ] `panoptic/migration/schema/check.py` · 108 L. Advisory drift check against `~/panoptic`.
- [ ] `panoptic/migration/schema/data.sql`
- [ ] `panoptic/migration/schema/media.sql`
- [ ] `panoptic/migration/schema/panoptic.sql`
- [ ] `panoptic/migration/schema/project.sql`
- [ ] `panoptic/migration/schema/upstream.json`. Fingerprints read by `check.py`.
- (`schema/regenerate.py` is a manual upstream-only tool, so it's in [[99 Unused files]].)

## Files: tooling
- [ ] `scripts/sync_migrator.sh`. Re-vendors this folder from upstream and refreshes the provenance marker.
