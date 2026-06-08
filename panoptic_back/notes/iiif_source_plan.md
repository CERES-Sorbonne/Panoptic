# IIIF File Source — Implementation Plan

## What is IIIF?

IIIF (International Image Interoperability Framework) defines two relevant APIs:

- **Presentation API** — describes *what* a collection contains (manifests, collections, canvases, images). This gives us the hierarchy and metadata.
- **Image API** — defines *how* to request image pixels at any resolution/region (`{base}/{identifier}/{region}/{size}/{rotation}/{quality}.{format}`).

A Manifest is a JSON-LD document describing one object (e.g. a book, a painting). A Collection groups multiple Manifests (and sub-Collections) — this is the hierarchy we can map to Folders.

IIIF v2 and v3 are both in widespread use. v3 is current. The structures differ slightly but the mapping to our models is the same.

---

## How IIIF Maps to Panoptic Concepts

| IIIF Concept | Panoptic Concept | Notes |
|---|---|---|
| Collection | Folder | Recursive; a collection can contain sub-collections |
| Manifest | Folder | Leaf-level folder; contains the canvases |
| Canvas | File + Instance | One canvas = one image |
| Image Resource (`@id` / `body.id`) | File.name / url for fetching | The actual pixel URL |
| IIIF Image Service | used for thumbnail requests | Avoid downloading full-res for thumbnails |
| Label (multilingual) | Folder.name / File.name | Take `en` or first available language |

A typical hierarchy: `Collection → Sub-Collection → Manifest → Canvas`
We mirror this directly as nested Folders, with Files at the Canvas level.

---

## Key Files to Read Before Implementing

### Core Models
- `panoptic/core/databases/data/models.py`
  - `FileSource(id, dtype, name, root_url)` — needs a new dtype `'iiif'`
  - `Folder(id, source_id, path, name, parent)` — `path` stores manifest/collection URL; `parent` gives hierarchy
  - `File(id, name, folder_id, sha1, width, height, format, created_at)` — canvas image
  - `Instance(id, file_id, sha1)` — one per canvas
  - `UpsertCommit` — the batch-write container for all of the above

### Write Path
- `panoptic/core/databases/data/data_writer.py` — `apply_upsert_commit(source, commit)`
- `panoptic/core/project/project.py` — `allocate_file_sources()`, `allocate_folders()`, `allocate_files()`, `allocate_instances()`

### Read / Serve Path
- `panoptic/core/databases/data/data_reader.py` — `get_file_path_for_sha1()` builds the URL/path used by image routes; needs an IIIF branch
- `panoptic/routes/project_routes.py` — `/image/raw/{sha1}`, `/image/large/{sha1}`, `/image/small/{sha1}`

### Reference Implementation (copy the pattern)
- `panoptic/core/task/import_folder_task.py` — scan → allocate → worker pool → UpsertCommit → apply

### Plugin Hooks (for metadata extraction phase)
- `panoptic/core/plugin/plugin.py` — `on_instance_import` callback
- `panoptic/core/plugin/plugin_interface.py` — safe API surface for plugins

### Architecture Docs (read these first)
- `notes/project2_architecture.md` — thread model, connection lifetime, fastapi bridge
- `notes/file_property_mode.md` — file-level vs sha1-level properties (relevant for IIIF metadata)
- `notes/routes_reference.md` — all existing REST endpoints

---

## Implementation Plan

### Phase 1 — IIIF Import Task (core ingestion)

**Goal:** parse a manifest URL, create the folder/file/instance tree, cache thumbnails.

#### 1.1 — Add `dtype = 'iiif'` constant
In `models.py` (or a new `file_source_types.py`):
```python
class FileSourceType:
    LOCAL = 'local'
    IIIF  = 'iiif'
```
No schema change needed — `dtype` is already a free-form string.

#### 1.2 — Create `IIIFImportTask`
New file: `panoptic/core/task/iiif_import_task.py`

Inherits from `Task`. Constructor takes `(project, manifest_url)`.

**Step A — Allocate the FileSource + resolve the entry point**
First allocate a `FileSource(dtype='iiif', name=<label>, root_url=<entry url>)` via `project.allocate_file_sources(1)` and write it in the commit — every Folder created below must reference its `id` as `source_id`. (The local source is auto-created in `project.py`; IIIF sources are not, so the task must create one.)
Then fetch the manifest/collection URL. Detect `@context` to determine IIIF version (v2 vs v3).

**Step B — Traverse the hierarchy**
Recursive function `_traverse(node, parent_folder_id)`:
- If `type == 'Collection'` (v3) or `@type == 'sc:Collection'` (v2):
  - Allocate a Folder, set `path = node['id']`, `parent = parent_folder_id`
  - Recurse into `items` (v3) or `manifests` + `collections` (v2)
- If `type == 'Manifest'`:
  - Allocate a Folder for the manifest itself. **`Folder.path` stores the IIIF Image API base URL** (the per-manifest image-service host). The path resolver (Phase 2) combines `FileSource.dtype` + `Folder.path` + `File.name` to build the request URL — exactly mirroring how local files use `folder.path + '/' + file.name`. This is why the URL lives on the Folder, not the File: identity = source + folder + file for both backends.
  - Iterate Canvases → allocate File + Instance per canvas
  - Store the canvas's stable identifier (the part appended after the image base) in `File.name`

  > Assumption: all canvases within one manifest share one image-service host. If a manifest mixes hosts, split into sub-folders per host (rare; handle later).

**Step C — Download full image, compute SHA1, generate thumbnails**
For each canvas:
- Resolve the image URL. Prefer the IIIF Image Service (`{service}/full/full/0/default.jpg`); **fall back to the canvas's plain image `body.id`** when the canvas is level-0 / has no service or `info.json`.
- Download the **full-res bytes → compute SHA1 from real pixels** (so cross-source dedup with local imports works — Decision #1). Then run PIL exactly like `import_folder_task._process_one` to derive `width/height/format` and render the auto_gen thumbnail types into `media.db`. No `info.json` round-trip needed since we have the bytes.
- This is the expensive path (one full download per canvas) — see concurrency note below.

**Step D — Batch write**
Build an `UpsertCommit` containing all FileSource, Folder, File, Instance records.
Call `project.apply_upsert_commit('iiif_import', commit)`. Write in batches (~`WRITE_BATCH`) like the folder task, and honor `self._cancel_event` between canvases.

**Step E — `on_last` → atlas**
Override `on_last` to enqueue `GenerateAtlasTask(self._project)`, exactly like `ImportFolderTask` — the grid/UMAP frontend needs the atlas, and the plan previously omitted this.

#### Cross-cutting task details (mirror `import_folder_task.py`)

- **Idempotency / re-import (Decision #4 = skip existing):** before fetching, load existing folders by `path` and existing files by `(folder_id, name)`, and skip canvases already present — same pre-filter the folder task uses. A re-import only adds new canvases.
- **Concurrency:** downloads are network-bound, not CPU-bound. Use a thread pool / async `httpx` for the per-canvas downloads (a `ProcessPoolExecutor` like the folder task buys nothing here), with a bounded worker count, a per-request timeout, and a small retry on transient HTTP errors. Report progress via `state.total/done` + `_notify`.
- **Auth (Decision #3 = public only):** no credential handling in v1. Drop the URL-embedded-credentials idea; a 401/403 just fails that canvas/manifest with a logged error.

#### 1.3 — Add API endpoint
In `panoptic/routes/project_routes.py`:
```
POST /projects/{project_id}/import/iiif
Body: { "manifest_url": "https://..." }
Returns: { "task_id": "..." }
```
Spawns the `IIIFImportTask` and returns immediately (same pattern as folder import).

---

### Phase 2 — Image Serving

**Problem:** `get_file_path_for_sha1()` (data_reader.py:431) returns a **string** path (`folder.path + '/' + file.name`) and is consumed directly by `/image/raw` (project_routes.py:1050). The original plan invented a new dict-returning method but never changed the route to use it — so an IIIF sha1 would build a bogus path, `Path(...).exists()` fails, and the route silently falls back to the cached thumbnail. We need a real resolver and a real route change.

**Solution — a backend-aware path resolver.** Identity is always `source + folder + file`; the resolver picks how to combine them by `FileSource.dtype`:

```python
def resolve_image_ref(self, sha1: str) -> dict | None:
    row = conn.execute("""
        SELECT fo.path, f.name, fs.dtype
        FROM files f
        JOIN folders fo ON fo.id = f.folder_id
        JOIN file_sources fs ON fs.id = fo.source_id
        WHERE f.sha1 = ? AND f.name IS NOT NULL AND fo.path IS NOT NULL
        LIMIT 1
    """, (sha1,)).fetchone()
    if not row:
        return None
    path, name, dtype = row
    if dtype == 'iiif':
        # folder.path = image-service base, file.name = canvas identifier
        return {'kind': 'iiif', 'url': f"{path}/{name}/full/full/0/default.jpg"}
    return {'kind': 'local', 'path': f"{path}/{name}"}
```

Keep `get_file_path_for_sha1()` as a thin wrapper returning the local path (or `None` for iiif) so existing callers don't break.

`/image/raw/{sha1}` becomes `async` and branches on `kind`: local → `FileResponse` as today; iiif → stream-proxy the URL with `httpx.AsyncClient`.

**Thumbnails** (small/large/by_size) read from `media.db` via `get_best_image_bytes` and are populated at import — so those routes need no change. This also means `/image/raw` is the *only* route that ever hits the network.

---

### Phase 3 — IIIF Metadata as Properties (optional, plugin-based)

Hook into `on_instance_import` to extract and store IIIF metadata as file properties:

| IIIF Field | Property Name | Property Type |
|---|---|---|
| `label` | `iiif:label` | string |
| `description` / `summary` | `iiif:description` | string |
| `rights` / `license` | `iiif:rights` | string |
| `requiredStatement` / `attribution` | `iiif:attribution` | string |
| `metadata` array | per-key properties | string |
| `navDate` | `iiif:date` | date |

Store these as `file`-mode properties (see `file_property_mode.md`) so they are per-instance rather than per-sha1 — two IIIF sources could have different metadata for the same image.

---

### Phase 4 — Frontend (future)

- `FileSource` is already synced to the frontend via the delta-sync mechanism
- The folder tree already uses `source_id` grouping — IIIF collections will appear naturally
- Image display: the frontend requests `/image/small/{sha1}` — no change needed since thumbnails are cached locally
- Consider a "Connect IIIF source" dialog in the settings/import panel that takes a manifest URL

---

## Decisions

1. **SHA1 identity = full image** — download the full-res canvas image and hash the real pixel bytes (same as local import). This makes a IIIF canvas and a local file that are the same image share a sha1 → shared cached thumbnail and true cross-source dedup. Cost: one full download per canvas at import time (mitigated by concurrency). `File` is not sha1-unique, so records from different sources coexist.

2. **v2 vs v3 parsing** — backend auto-detects from the `@context` field. **Note:** the difference is more than cosmetic — v2 uses `sequences→canvases→images` and string `label`s; v3 uses `items→AnnotationPage→Annotation` and language-map `label`s. `iiif-prezi3` is **v3-only**, so it cannot parse v2; either write one branching JSON parser for both, or use `iiif-prezi3` for v3 + manual for v2. Label rule: take `en`/first available language. Detection logic lives in `IIIFImportTask`.

3. **Authentication** — **out of scope for v1: public manifests only.** No credential handling; protected resources (401/403) fail the affected canvas with a logged error. The IIIF Authorization Flow API (probe/token/cookie services) is deferred. (Earlier idea of embedding creds in `root_url` is dropped — it does not match how real IIIF auth works.)

4. **Re-sync** — manual only. A re-import **skips existing** folders/files (matched by `folder.path` and `(folder_id, name)`) and only adds new canvases, mirroring `ImportFolderTask`. No duplicates.

5. **Where the image URL lives** — on the **Folder**, not the File. `Folder.path` = the image-service base URL; `File.name` = the canvas identifier appended to it. A `dtype`-aware resolver (Phase 2) reconstructs the request URL the same way it does for local files (`path + '/' + name`). No schema change to `File`. Assumes one image host per manifest.

---

## Minimal Dependency

The only external library needed for Phase 1–2 is `httpx` (async HTTP) — already likely present. Optionally `iiif-prezi3` for manifest parsing, or just use `json` directly (IIIF manifests are plain JSON-LD).
