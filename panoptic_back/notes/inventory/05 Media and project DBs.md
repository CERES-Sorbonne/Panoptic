---
tags: [inventory, backend]
zone: media-project-db
---
# 05 · Media DB & project DB

Back to [[00 Backend inventory]] · Unused files: [[99 Unused files]]

**Scope:** `media.db` (thumbnails, image types, vectors, atlas, maps; no journal, no undo) and `project.db` (id registry, project config, tab data, per-user defaults, plugin data).

## Zone-level checks
- [ ] `media/models.py` is imported by the PanopticML plugin in 5 places (`VectorType`, `Vector`, `Map`…). Renaming a field breaks plugins ([[07 Plugin system]]).
- [ ] ⚠ `test/test_media_db.py` and `test/test_project_db.py` no longer import ([[09 Tests and fixtures]]), so this zone currently has **no working unit tests**.
- [ ] `project_db_config_reader.py` is never imported ([[99 Unused files]]).
- [ ] TabData is stored by the backend but versioned by the frontend (`TAB_MODEL_VERSION` in `panoptic_front/src/data/tabStore.ts`). Check who migrates old tab JSON.

## Files
- [ ] `panoptic/core/databases/media/create.py` · 32 L. `media.db` schema.
- [ ] `panoptic/core/databases/media/media_db.py` · 128 L. `MediaDB`: image types (default seeding), thumbnails, vectors, atlas sheets, maps.
- [ ] `panoptic/core/databases/media/models.py` · 57 L. `VectorType`, `Vector`, `ImageType`, `Image`, `ImageAtlas`, `Map`.
- [ ] `panoptic/core/databases/project/create.py` · 34 L. `project.db` schema, including `PROJECT_CONFIG_SHEMA`.
- [ ] `panoptic/core/databases/project/models.py` · 62 L. `IdRegistry`, `ProjectConfig`, `ProjectFlags`, `PluginData`, `TabData`, `UserDefaults`.
- [ ] `panoptic/core/databases/project/project_db.py` · 179 L. `ProjectDB`: id allocation (registry), config and uuid, tabs, user defaults, plugin data.
