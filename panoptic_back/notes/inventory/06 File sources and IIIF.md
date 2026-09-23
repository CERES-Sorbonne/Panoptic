---
tags: [inventory, backend]
zone: file-sources
---
# 06 · File sources (local & IIIF)

Back to [[00 Backend inventory]] · Unused files: [[99 Unused files]]

**Scope:** where images come from: the reader abstraction, the local folder reader, the IIIF manifest/collection reader, and image processing into thumbnails. The design is in `notes/iiif_source_plan.md`.

## Zone-level checks
- [ ] ⚠ `iiif_reader.py` (and `project_routes.py`) import `httpx`, which is **not declared** in `pyproject.toml`. It only works because something else pulls it in.
- [ ] IIIF rate limiting and retry (`_RateLimiter`, `_get_with_retry`): check behaviour on 429/5xx and on auth-protected manifests (`IIIFAuth`).
- [ ] The frontend `FileSourceOptionDropdown.vue` has `TODO: replace with a real API call once the backend exposes a connection-test endpoint`. No such endpoint exists here yet.
- [ ] Re-syncing a source: `update_sync_status` / `import_folder_tree` against deleted or moved files.

## Files
- [ ] `panoptic/core/file_source/__init__.py` · package marker
- [ ] `panoptic/core/file_source/base.py` · 183 L. `FolderNode`, `ItemRef`, the abstract `FileSourceReader`, and the shared helpers `update_file_source`, `update_sync_status`, `import_folder_tree`, `write_batch`.
- [ ] `panoptic/core/file_source/local_reader.py` · 86 L. `LocalFileSourceReader`: walks a local folder.
- [ ] `panoptic/core/file_source/iiif_config.py` · 141 L. Typed IIIF source metadata: `IIIFAuth`, `IIIFImportHistory`, `IIIFSourceConfig`.
- [ ] `panoptic/core/file_source/iiif_reader.py` · 426 L. `IIIFFileSourceReader`: fetches manifests and collections, rate-limits, retries, downloads images.
- [ ] `panoptic/core/file_source/processing.py` · 53 L. `render` / `process_bytes`: PIL decoding into the configured image sizes. Also used by `generate_thumbnails_task.py`.
- [ ] `panoptic/core/file_source/registry.py` · 29 L. `get_reader_for_source`: picks a reader by source type.
