---
tags: [inventory, backend]
zone: panoptic-home
---
# 02 · Panoptic home, users & legacy discovery

Back to [[00 Backend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the per-machine "home" database (`~/.panoptic/panoptic.db`): the project registry, users, the plugin registry and the detection of projects from old 0.x installs.

## Zone-level checks
- [ ] `panoptic.db` schema version upgrade path (`create.py` → `_migrate_1_to_2`) is covered by `test/test_legacy_migration.py::test_panoptic_db_v1_upgrades_to_v2`.
- [ ] Password hashing in `panoptic.py` (`_hash_password` / `_verify_password`): check the algorithm and salt handling.
- [ ] Legacy discovery is skippable by env var (there's a test for it). Make sure it can't slow down startup on machines with many old projects.
- [ ] The files in `core/databases/panoptic/` have no `__init__.py`, so it's a namespace package, same as `media/` and `project/`. That works, but it's inconsistent with `core/databases/data/`.

## Files
- [ ] `panoptic/core/panoptic/__init__.py` · package marker
- [ ] `panoptic/core/panoptic/panoptic.py` · 277 L. `Panoptic`: the instance object. It opens `panoptic.db` and handles creating, importing, listing, loading and closing projects, users, and plugin install/registry (through `PluginInstaller`). Used by `main.py`, `routes/deps.py`, `panoptic_server.py` and the tests.
- [ ] `panoptic/core/panoptic/models.py` · 10 L. `ProjectState`.
- [ ] `panoptic/core/panoptic/legacy_migration.py` · 506 L. Detects projects registered by an old (0.x) Panoptic (`LegacyRegistry`, `LegacyScan`) and migrates *copies* of them through `panoptic.migration` (`MigrationRun`). The frontend `LegacyImportModal.vue` on the home page drives it.
- [ ] `panoptic/core/databases/panoptic/create.py` · 40 L. `panoptic.db` schema plus `_migrate_1_to_2`.
- [ ] `panoptic/core/databases/panoptic/models.py` · 47 L. `PanopticConfig`, `User`, `ProjectKey`, `PluginKey`, `LegacyMigration`.
- [ ] `panoptic/core/databases/panoptic/panoptic_db.py` · 153 L. `PanopticDB` (CRUD for projects, users and plugins) and `DEFAULT_USER_ID`.
