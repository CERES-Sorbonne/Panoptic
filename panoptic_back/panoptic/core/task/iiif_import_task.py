import hashlib
import io
import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from panoptic.core.databases.data.models import File, FileSource, Folder, Instance, UpsertCommit
from panoptic.core.databases.media.models import Image
from panoptic.core.task.import_folder_task import ImageTypeSpec, _render
from panoptic.core.task.task import Task

logger = logging.getLogger('IIIFImportTask')

# Network-bound work → threads (not processes). Kept low to stay polite: strict hosts
# like Gallica/BnF return HTTP 429 (Too Many Requests) under heavier concurrency.
MAX_WORKERS = 3
WRITE_BATCH = 60
HTTP_TIMEOUT = 30.0
MAX_RETRIES = 6          # on 429 / 503 / transient network errors
INIT_BACKOFF = 2.0       # first retry wait (seconds); doubles each attempt
MAX_BACKOFF = 30.0       # cap for a single backoff sleep (seconds)
# Global throttle: strict hosts (Gallica/BnF) 429 on bursts of requests.
# Every HTTP request across all worker threads is paced to at most one per interval.
REQUEST_INTERVAL = 0.5

# Import downloads a bounded-width rendition (not full-res) for sha1 + thumbnails:
# strict hosts heavily throttle full-res requests, and the capped image is plenty for
# hashing and the largest thumbnail type. Full-res stays available on demand via the
# /image/raw proxy. Trade-off: the sha1 is the capped image's, so it won't match a
# locally-imported full-res copy of the same image.
IMPORT_WIDTH = 1024


class _RateLimiter:
    """Thread-safe minimum-interval gate shared by all download workers.

    Holds the lock across the sleep so request *starts* are serialized to one per
    interval — a single global request flow regardless of worker count.
    """

    def __init__(self, min_interval: float):
        self._min = min_interval
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self):
        with self._lock:
            now = time.monotonic()
            delay = self._next - now
            if delay > 0:
                time.sleep(delay)
                now = time.monotonic()
            self._next = now + self._min


_rate_limiter = _RateLimiter(REQUEST_INTERVAL)

# Some IIIF hosts (e.g. Gallica/BnF) reject requests without a browser-like
# User-Agent with HTTP 403.
HTTP_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
    ),
}

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.tif', '.tiff')

# IIIF Presentation context markers used to sniff the major version.
_V3_CTX = 'presentation/3/context.json'
_V2_CTX = 'presentation/2/context.json'


# ---------------------------------------------------------------------------
# Worker (runs in a thread): download full image, sha1, render thumbnails.
# Mirrors import_folder_task._process_one but reads bytes from the network.
# ---------------------------------------------------------------------------

def _get_with_retry(url: str, headers: dict) -> httpx.Response:
    """GET with exponential backoff on 429/503 (honoring Retry-After) and transient errors."""
    backoff = INIT_BACKOFF
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            _rate_limiter.wait()
            resp = httpx.get(url, timeout=HTTP_TIMEOUT, follow_redirects=True, headers=headers)
            if resp.status_code in (429, 503) and attempt < MAX_RETRIES - 1:
                retry_after = resp.headers.get('Retry-After')
                try:
                    wait = float(retry_after) if retry_after else backoff
                except ValueError:
                    wait = backoff
                wait = min(wait, MAX_BACKOFF) + random.uniform(0, 1)
                print(f'[IIIF] HTTP {resp.status_code} (attempt {attempt + 1}/{MAX_RETRIES}) '
                      f'— backing off {wait:.1f}s — {url}')
                # Jitter so concurrent workers desync instead of retrying in lockstep.
                time.sleep(wait)
                backoff *= 2
                continue
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError:
            raise
        except Exception as e:  # connection/timeout — retry
            last_exc = e
            if attempt < MAX_RETRIES - 1:
                wait = min(backoff, MAX_BACKOFF) + random.uniform(0, 1)
                print(f'[IIIF] network error (attempt {attempt + 1}/{MAX_RETRIES}) '
                      f'— retrying in {wait:.1f}s — {type(e).__name__}: {e}')
                time.sleep(wait)
                backoff *= 2
            else:
                raise
    if last_exc:
        raise last_exc
    raise RuntimeError(f'failed to fetch {url}')


def _process_canvas(fetch_url: str, image_types: list[ImageTypeSpec]) -> dict | None:
    from PIL import Image as PilImage

    print(f'[IIIF]   ↓ downloading {fetch_url}')
    try:
        raw = _get_with_retry(fetch_url, HTTP_HEADERS).content
    except Exception as e:
        print(f'[IIIF]   ✗ download FAILED — {type(e).__name__}: {e}')
        logger.error('IIIF download failed for %s: %s', fetch_url, e)
        return None

    sha1 = hashlib.sha1(raw).hexdigest()
    width = height = None
    fmt = None
    images = []

    try:
        with PilImage.open(io.BytesIO(raw)) as img:
            width, height = img.size
            fmt = (img.format or '').lower() or None
            if image_types:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.load()
                for type_id, image_fmt, max_w, max_h in image_types:
                    images.append((type_id, _render(img, image_fmt, max_w, max_h)))
    except Exception as e:
        print(f'[IIIF]   ✗ PIL FAILED on {fetch_url} — {type(e).__name__}: {e}')
        logger.error('PIL failed on IIIF image %s: %s', fetch_url, e)

    print(f'[IIIF]   ✓ {len(raw)//1024} KB, {width}x{height} {fmt}, '
          f'{len(images)} thumbs, sha1={sha1[:8]}')
    return {
        'sha1': sha1, 'images': images,
        'width': width, 'height': height, 'format': fmt,
    }


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class IIIFImportTask(Task):
    def __init__(self, project, manifest_url: str):
        super().__init__()
        self.name = 'Import IIIF'
        self._project = project
        self._url = manifest_url.strip()

        self._image_types: list[ImageTypeSpec] = [
            (t.id, t.format, t.width, t.height)
            for t in project.get_image_types()
            if t.auto_gen
        ]

    # ------------------------------------------------------------------

    def start(self):
        import time
        t0 = time.monotonic()
        print(f'[IIIF] ===== import START =====')
        print(f'[IIIF] entry url: {self._url}')
        print(f'[IIIF] auto_gen thumbnail types: {self._image_types}')

        entry = self._fetch_json(self._url)
        if entry is None:
            print(f'[IIIF] ABORT: could not fetch entry url')
            logger.error('IIIF import aborted: could not fetch %s', self._url)
            return
        version = self._detect_version(entry)
        print(f'[IIIF] fetched entry — version=v{version}, type={self._node_type(entry)}, '
              f'label={self._label(entry, version)!r}')

        fs_id = self._ensure_source(entry, version)

        # Traverse the hierarchy: build the folder tree (preorder, parents first)
        # and the flat list of canvases to download.
        print(f'[IIIF] traversing hierarchy...')
        folder_nodes: list[dict] = []
        canvases: list[dict] = []
        self._collect(entry, version, parent_path=None,
                      folder_nodes=folder_nodes, canvases=canvases)
        print(f'[IIIF] traversal done: {len(folder_nodes)} folder node(s), '
              f'{len(canvases)} canvas(es) found')

        path_to_id = self._import_folder_tree(fs_id, folder_nodes)

        # Skip canvases already imported under this source (idempotent re-import).
        all_folder_ids = list(set(path_to_id.values()))
        existing_files = {
            (f.folder_id, f.name)
            for f in self._project.get_files(folder_id=all_folder_ids)
            if f.name and f.folder_id is not None
        } if all_folder_ids else set()

        items = []
        skipped = 0
        for c in canvases:
            folder_id = path_to_id.get(c['folder_path'])
            if folder_id is None:
                continue
            if (folder_id, c['ref']) in existing_files:
                skipped += 1
                continue
            items.append((folder_id, c))
        print(f'[IIIF] {len(items)} canvas(es) to download, {skipped} skipped '
              f'(already imported)')

        self.state.total = len(items)
        self._notify()

        image_types = self._image_types
        batch: list[dict] = []

        print(f'[IIIF] downloading with {MAX_WORKERS} worker(s), '
              f'≥{REQUEST_INTERVAL}s between requests, capped width {IMPORT_WIDTH}px')
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {
                pool.submit(_process_canvas, c['fetch_url'], image_types): (folder_id, c)
                for folder_id, c in items
            }
            for future in as_completed(futures):
                if self._cancel_event.is_set():
                    print(f'[IIIF] CANCELLED — stopping at {self.state.done}/{self.state.total}')
                    break
                folder_id, c = futures[future]
                result = None
                try:
                    result = future.result()
                except Exception as e:
                    print(f'[IIIF] worker raised — {type(e).__name__}: {e}')
                    logger.error('IIIF worker failed: %s', e)

                if result:
                    result['folder_id'] = folder_id
                    result['ref'] = c['ref']
                    batch.append(result)
                    if len(batch) >= WRITE_BATCH:
                        self._write_batch(batch)
                        batch.clear()
                else:
                    self.state.failed += 1

                self.state.done += 1
                print(f'[IIIF] progress {self.state.done}/{self.state.total} '
                      f'({self.state.failed} failed)')
                self._notify()

        if batch:
            self._write_batch(batch)

        elapsed = time.monotonic() - t0
        print(f'[IIIF] ===== import DONE: {self.state.done} canvases in {elapsed:.1f}s '
              f'({self.state.failed} failed) =====')

    def on_last(self) -> None:
        print(f'[IIIF] on_last → enqueueing GenerateAtlasTask')
        from panoptic.core.task.generate_atlas_task import GenerateAtlasTask
        self._project.add_task(GenerateAtlasTask(self._project))

    # ------------------------------------------------------------------
    # HTTP / parsing helpers
    # ------------------------------------------------------------------

    def _fetch_json(self, url: str) -> dict | None:
        print(f'[IIIF] GET json: {url}')
        try:
            resp = _get_with_retry(url, {**HTTP_HEADERS,
                                         'Accept': 'application/json, application/ld+json'})
            return resp.json()
        except Exception as e:
            print(f'[IIIF] ✗ json fetch FAILED — {type(e).__name__}: {e}')
            logger.error('Failed to fetch IIIF resource %s: %s', url, e)
            return None

    @staticmethod
    def _detect_version(node: dict) -> int:
        ctx = node.get('@context', '')
        flat = ' '.join(ctx) if isinstance(ctx, list) else str(ctx)
        if _V2_CTX in flat:
            return 2
        return 3  # default to current

    @staticmethod
    def _node_id(node: dict) -> str | None:
        return node.get('id') or node.get('@id')

    @staticmethod
    def _node_type(node: dict) -> str:
        # v3: 'Collection'/'Manifest'/'Canvas'; v2: 'sc:Collection'/'sc:Manifest'/'sc:Canvas'
        t = node.get('type') or node.get('@type') or ''
        if isinstance(t, list):
            t = next((x for x in t if 'Collection' in x or 'Manifest' in x or 'Canvas' in x), t[0] if t else '')
        return t.split(':')[-1]

    @staticmethod
    def _label(node: dict, version: int) -> str | None:
        label = node.get('label')
        if label is None:
            return None
        if version >= 3 and isinstance(label, dict):
            # language map: {"en": ["..."], "none": ["..."]}
            for key in ('en', 'none'):
                if key in label and label[key]:
                    return str(label[key][0])
            for vals in label.values():
                if vals:
                    return str(vals[0])
            return None
        if isinstance(label, list):
            first = label[0]
            return first.get('@value') if isinstance(first, dict) else str(first)
        return str(label)

    # ------------------------------------------------------------------
    # Traversal — fills folder_nodes (path/name/parent_path) and canvases
    # ------------------------------------------------------------------

    def _collect(self, node: dict, version: int, parent_path: str | None,
                 folder_nodes: list[dict], canvases: list[dict]):
        if self._cancel_event.is_set():
            return

        node_type = self._node_type(node)
        node_id = self._node_id(node)
        if not node_id:
            print(f'[IIIF] skip node with no id (type={node_type})')
            return

        label = self._label(node, version) or node_id
        folder_nodes.append({
            'path': node_id,
            'name': label,
            'parent_path': parent_path,
        })

        if node_type == 'Collection':
            children = self._collection_children(node, version)
            print(f'[IIIF] Collection {label!r}: {len(children)} child(ren)')
            for child in children:
                child_id = self._node_id(child)
                if not child_id:
                    continue
                # Children are usually references — fetch the full document.
                full = self._fetch_json(child_id) or child
                self._collect(full, self._detect_version(full), node_id,
                              folder_nodes, canvases)
        elif node_type == 'Manifest':
            manifest_canvases = self._manifest_canvases(node, version)
            before = len(canvases)
            for canvas in manifest_canvases:
                self._collect_canvas(canvas, version, node_id, canvases)
            print(f'[IIIF] Manifest {label!r}: {len(manifest_canvases)} canvas(es), '
                  f'{len(canvases) - before} with usable image')
        else:
            print(f'[IIIF] unhandled node type {node_type!r} ({label!r})')

    @staticmethod
    def _collection_children(node: dict, version: int) -> list[dict]:
        if version >= 3:
            return [c for c in node.get('items', [])
                    if IIIFImportTask._node_type(c) in ('Collection', 'Manifest')]
        return list(node.get('collections', [])) + list(node.get('manifests', []))

    @staticmethod
    def _manifest_canvases(node: dict, version: int) -> list[dict]:
        if version >= 3:
            return list(node.get('items', []))
        sequences = node.get('sequences') or []
        canvases = []
        for seq in sequences:
            canvases.extend(seq.get('canvases', []))
        return canvases

    def _collect_canvas(self, canvas: dict, version: int, manifest_path: str,
                        canvases: list[dict]):
        body = self._canvas_image_body(canvas, version)
        if not body:
            print(f'[IIIF]   canvas {self._node_id(canvas)} — no image body, skipping')
            return
        url = self._image_url(body, version)
        if not url:
            print(f'[IIIF]   canvas {self._node_id(canvas)} — no image url, skipping')
            return
        # ref (stored in file.name) is the full-res URL, returned verbatim by the serve
        # resolver for /image/raw. fetch_url is a capped-width rendition used only at
        # import time for sha1 + thumbnail generation (avoids full-res throttling).
        canvases.append({
            'folder_path': manifest_path,
            'ref': url,
            'fetch_url': self._capped_url(url),
        })

    @staticmethod
    def _capped_url(url: str) -> str:
        """Rewrite a IIIF Image API request's size segment to a bounded width.

        Matches the size keyword we (and most servers) use in image URLs — v2 ``full``
        and v3 ``max`` — and replaces it with ``{IMPORT_WIDTH},``. Leaves non-IIIF /
        static image URLs unchanged (they can't be resized via URL).
        """
        for seg in ('/full/max/', '/full/full/'):
            if seg in url:
                return url.replace(seg, f'/full/{IMPORT_WIDTH},/', 1)
        return url

    @classmethod
    def _image_url(cls, body: dict, version: int) -> str | None:
        """Best full-resolution image URL for a canvas image body.

        Prefer the body id when it is already a complete image request (the IIIF
        cookbook/most servers point it at the default rendition). Otherwise build a
        full-size request from the Image Service, using the version-correct size
        keyword (v3 = ``max``, v2 = ``full``). Falls back to the raw body id.
        """
        body_id = cls._node_id(body)
        if body_id and ('/full/' in body_id or body_id.lower().endswith(IMAGE_EXTENSIONS)):
            return body_id
        service_id = cls._image_service_id(body)
        if service_id:
            size = 'max' if version >= 3 else 'full'
            return f"{service_id.rstrip('/')}/full/{size}/0/default.jpg"
        return body_id

    @staticmethod
    def _canvas_image_body(canvas: dict, version: int) -> dict | None:
        if version >= 3:
            for page in canvas.get('items', []):
                for anno in page.get('items', []):
                    body = anno.get('body')
                    if isinstance(body, list):
                        body = body[0] if body else None
                    if body:
                        return body
            return None
        for image in canvas.get('images', []):
            res = image.get('resource')
            if res:
                return res
        return None

    @staticmethod
    def _image_service_id(body: dict) -> str | None:
        service = body.get('service')
        if not service:
            return None
        if isinstance(service, list):
            service = service[0] if service else None
        if not isinstance(service, dict):
            return None
        return service.get('id') or service.get('@id')

    # ------------------------------------------------------------------
    # DB writes (main thread only)
    # ------------------------------------------------------------------

    def _ensure_source(self, entry: dict, version: int) -> int:
        """Reuse an existing IIIF source with the same root_url, else create one."""
        existing = next(
            (s for s in self._project.get_file_sources()
             if s.dtype == 'iiif' and s.root_url == self._url),
            None,
        )
        if existing:
            print(f'[IIIF] reusing existing FileSource id={existing.id} '
                  f'(name={existing.name!r})')
            return existing.id

        fs_id = self._project.allocate_file_sources(1)
        if isinstance(fs_id, range):
            fs_id = fs_id.start
        name = self._label(entry, version) or self._url
        commit = UpsertCommit()
        commit.file_sources[fs_id] = FileSource(
            id=fs_id, dtype='iiif', name=name, root_url=self._url,
        )
        self._project.apply_upsert_commit('iiif_import', commit)
        print(f'[IIIF] created FileSource id={fs_id} (name={name!r})')
        return fs_id

    def _import_folder_tree(self, fs_id: int, folder_nodes: list[dict]) -> dict[str, int]:
        existing = {
            f.path: f.id
            for f in self._project.get_folders(source_id=fs_id)
            if f.path
        }
        path_to_id: dict[str, int] = dict(existing)

        # De-dup nodes by path (a path can appear once); keep first occurrence order.
        seen = set()
        new_nodes = []
        for n in folder_nodes:
            if n['path'] in path_to_id or n['path'] in seen:
                continue
            seen.add(n['path'])
            new_nodes.append(n)

        if not new_nodes:
            print(f'[IIIF] folder tree: {len(path_to_id)} existing, 0 new')
            return path_to_id

        print(f'[IIIF] folder tree: {len(existing)} existing, '
              f'creating {len(new_nodes)} new folder(s)')
        id_range = self._project.allocate_folders(len(new_nodes))
        if isinstance(id_range, int):
            id_range = range(id_range, id_range + 1)

        commit = UpsertCommit()
        for node, fid in zip(new_nodes, id_range):
            parent_id = path_to_id.get(node['parent_path']) if node['parent_path'] else None
            commit.folders[fid] = Folder(
                id=fid, source_id=fs_id,
                path=node['path'], name=node['name'], parent=parent_id,
            )
            path_to_id[node['path']] = fid

        self._project.apply_upsert_commit('iiif_import', commit)
        return path_to_id

    def _write_batch(self, results: list[dict]):
        if not results:
            return

        project = self._project
        n = len(results)
        file_ids = project.allocate_files(n)
        inst_ids = project.allocate_instances(n)
        if isinstance(file_ids, int):
            file_ids = range(file_ids, file_ids + 1)
        if isinstance(inst_ids, int):
            inst_ids = range(inst_ids, inst_ids + 1)

        commit = UpsertCommit()
        media: list[Image] = []

        for info, fid, iid in zip(results, file_ids, inst_ids):
            commit.files[fid] = File(
                id=fid,
                name=info['ref'],          # canvas image reference (resolved at serve time)
                folder_id=info['folder_id'],
                sha1=info['sha1'],
                width=info.get('width'),
                height=info.get('height'),
                format=info.get('format'),
            )
            commit.instances[iid] = Instance(id=iid, file_id=fid, sha1=info['sha1'])
            for type_id, data in info.get('images', []):
                media.append(Image(type_id=type_id, sha1=info['sha1'], data=data))

        project.apply_upsert_commit('iiif_import', commit)
        if media:
            project.upsert_images(media)
        print(f'[IIIF] wrote batch: {n} file(s)/instance(s), {len(media)} thumbnail blob(s)')
