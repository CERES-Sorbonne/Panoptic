---
tags: [inventory, backend]
zone: data-db
---
# 04 · Data DB, ORM layer & versioning

Back to [[00 Backend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the generic SQLite/msgspec layer that all four databases use, plus `data.db`: entities, the `entity_log` journal, and multi-user non-sequential undo. The design is in `notes/versioning_architecture.md`.

## Zone-level checks
- [ ] `entity_schema.py` (970 L) is the ORM for every DB (18 importers). Any change to it touches all of them, including the migration writers, which hard-copy the schema into `migration/schema/*.sql`. Re-check the drift with `migration/schema/check.py`.
- [ ] `data_writer.py` + `resolver.py`: undo/redo with other users' commits interleaved — covered by `test/test_data_db.py` **and `test/test_undo_redo.py`** (added 2026-09-21); 75 tests, all green.
- [ ] System properties (`system_properties.py`) are refused as write targets at the route layer (`test/test_readonly_properties.py`).
- [ ] The file name `key_value_shema.py` is misspelled (should be "schema"). Renaming it would touch 2 importers.

## Files
- [ ] `panoptic/core/databases/__init__.py` · package marker
- [ ] `panoptic/core/databases/db_description.py` · 17 L. `DbDescription`: the name, version and tables of one DB.
- [ ] `panoptic/core/databases/entity_schema.py` · 970 L. Introspects msgspec structs into SQL: `PrimaryKey`, `Index`, `Col`, type mapping, filter parsing, and generic get/insert/update/delete.
- [ ] `panoptic/core/databases/key_value_shema.py` · 164 L. `KeyValueSchema`: a typed key/value config table, used by the `project.db` and `panoptic.db` configs.
- [ ] `panoptic/core/databases/sqlite_db.py` · 187 L. `SQLiteWriter`: connection, pragmas, transactions. Base class of the DataWriter, MediaDB, PanopticDB and ProjectDB writers.
- [ ] `panoptic/core/databases/sqlite_reader.py` · 96 L. `SQLiteReader`: read connection plus JSON field decoding. Used by `DataReader`.
- [ ] `panoptic/core/databases/data/__init__.py` · package marker
- [ ] `panoptic/core/databases/data/create.py` · 127 L. `data.db` schema: entity tables plus `entity_log`.
- [ ] `panoptic/core/databases/data/models.py` · 196 L. Entity structs: `Commit` (with `author`, `active` and `redoable`), `ChangeOp`, `FileSource`, `Folder`, `File`, `Instance`, `Property`, `PropertyGroup`, tags and values. Plugins import it.
- [ ] `panoptic/core/databases/data/data_reader.py` · 807 L. `DataReader`: every query and stream over `data.db`. Used by the routes, the server, the exporter and the plugin interface.
- [ ] `panoptic/core/databases/data/data_writer.py` · 763 L. `DataWriter`: logged and structural writes, commit creation, `undo(author)` / `redo(author)` / `set_commit_active`, `_discard_redo`, compaction. Last changed 2026-09-21 (`5a6893b9`).
- [ ] `panoptic/core/databases/data/resolver.py` · 152 L. `EntitySpec`, key encode/decode, `diff_changes`, `resolve`. This is the non-sequential undo resolver, and only `data_writer.py` imports it.
- [ ] `panoptic/core/databases/data/system_properties.py` · 46 L. `SystemProperty` ids plus `is_system` / `is_readonly`.
