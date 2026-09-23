---
tags: [inventory, backend]
zone: project-runtime
---
# 03 · Project runtime, tasks, import & export

Back to [[00 Backend inventory]] · Unused files: [[99 Unused files]]

**Scope:** the `Project` object that ties one project's databases together, the background task queue, and CSV import/export.

## Zone-level checks
- [ ] `Project` (651 L) is imported by 11 modules. Check that it stays a coordinator and doesn't grow DB logic that belongs in the readers and writers ([[04 Data DB and versioning]]).
- [ ] Task lifecycle: stop/cancel of pending chunks and dismiss are tested (`test/test_task_manager.py`). Check that thumbnail and atlas tasks survive a project close mid-run.
- [ ] Export → import round trip: exporter output (`local_path;sha1[sha1]`) can be converted back with `test/export_to_import.py`. Check that it still matches the importer header format `Name[type]`.
- [ ] Importer column types match what the frontend `import/DataImport.vue` offers.

## Files
- [ ] `panoptic/core/project/__init__.py` · package marker
- [ ] `panoptic/core/project/project.py` · 651 L. `Project`:
  - opens `data.db`, `media.db` and `project.db`
  - handles file sources (local and IIIF), tasks and plugin loading
  - is the entry point for import, export and settings
- [ ] `panoptic/core/task/__init__.py` · package marker
- [ ] `panoptic/core/task/task.py` · 57 L. `Task` base class (chunks, progress, state). Plugins import it too.
- [ ] `panoptic/core/task/task_manager.py` · 128 L. `TaskManager`: a FIFO queue with a high-priority lane; tasks run serially and report state through callbacks.
- [ ] `panoptic/core/task/import_source_task.py` · 146 L. `ImportSourceTask`: walks a file source and writes files, instances and thumbnails, then queues the atlas.
- [ ] `panoptic/core/task/generate_thumbnails_task.py` · 127 L. `GenerateThumbnailsTask`: fills in missing thumbnails from the original files. Also triggered from `project_routes.py`.
- [ ] `panoptic/core/task/generate_atlas_task.py` · 121 L. `GenerateAtlasTask`: stitches small-image blobs from `MediaDB` into PNG sheets for the map view. It always rewrites atlas id 0 in place; the frontend `mediaStore.ts` depends on that.
- [ ] `panoptic/core/importer/__init__.py` · package marker
- [ ] `panoptic/core/importer/importer.py` · 589 L. CSV importer: header parsing (`name[type]`), path normalisation and index (`_PathIndex`), and the instance and image import modes.
- [ ] `panoptic/core/exporter.py` · 257 L. CSV and image exporter, using polars. It writes `data.csv`.
