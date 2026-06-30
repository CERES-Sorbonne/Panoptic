import logging
import random
import threading
import time
from typing import Callable

import httpx

from panoptic.core.databases.data.models import FileSource, UpsertCommit
from panoptic.core.file_source.base import FileSourceReader, FolderNode, ItemRef
from panoptic.core.file_source.iiif_config import IIIFSourceConfig
from panoptic.core.file_source.processing import ImageTypeSpec, process_bytes

logger = logging.getLogger('IIIFFileSourceReader')

# Network-bound work → threads. Kept low to stay polite: strict hosts like
# Gallica/BnF return HTTP 429 (Too Many Requests) under heavier concurrency.
MAX_WORKERS = 3
HTTP_TIMEOUT = 30.0
MAX_RETRIES = 6          # on 429 / 503 / transient network errors
INIT_BACKOFF = 2.0       # first retry wait (seconds); doubles each attempt
MAX_BACKOFF = 30.0       # cap for a single backoff sleep (seconds)
# Global throttle: strict hosts (Gallica/BnF) 429 on bursts of requests.
# Every HTTP request across all reader instances is paced to at most one per interval.
REQUEST_INTERVAL = 0.5

# Import downloads a bounded-width rendition (not full-res) for sha1 + thumbnails:
# strict hosts heavily throttle full-res requests, and the capped image is plenty for
# hashing and the largest thumbnail type. Full-res stays available on demand via
# fetch_bytes() (used by the /image/raw proxy). Trade-off: the sha1 is the capped
# image's, so it won't match a locally-imported full-res copy of the same image.
IMPORT_WIDTH = 1024

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.tif', '.tiff')

# IIIF Presentation context markers used to sniff the major version.
_V3_CTX = 'presentation/3/context.json'
_V2_CTX = 'presentation/2/context.json'

# Some IIIF hosts (e.g. Gallica/BnF) reject requests without complete browser-like headers.
HTTP_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
    ),
    'Accept': 'application/json, application/ld+json, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}


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


def _get_with_retry(url: str, headers: dict, timeout: float = HTTP_TIMEOUT) -> httpx.Response:
    """GET with exponential backoff on 429/503 (honoring Retry-After) and transient errors.

    Shared by import-time downloads and the serve-time /image/raw proxy, so both paths
    get the same politeness/retry/auth treatment instead of diverging.
    """
    backoff = INIT_BACKOFF
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            _rate_limiter.wait()
            resp = httpx.get(url, timeout=timeout, follow_redirects=True, headers=headers)
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


def _process_iiif_item(fetch_url: str, headers: dict, image_types: list[ImageTypeSpec]) -> dict | None:
    """Runs in a worker thread: download a capped-width rendition, sha1, thumbnails."""
    print(f'[IIIF]   ↓ downloading {fetch_url}')
    try:
        raw = _get_with_retry(fetch_url, headers).content
    except Exception as e:
        print(f'[IIIF]   ✗ download FAILED — {type(e).__name__}: {e}')
        logger.error('IIIF download failed for %s: %s', fetch_url, e)
        return None

    result = process_bytes(
        raw, image_types,
        on_pil_error=lambda e: (
            print(f'[IIIF]   ✗ PIL FAILED on {fetch_url} — {type(e).__name__}: {e}'),
            logger.error('PIL failed on IIIF image %s: %s', fetch_url, e),
        ),
    )
    print(f"[IIIF]   ✓ {len(raw)//1024} KB, {result['width']}x{result['height']} {result['format']}, "
          f"{len(result['images'])} thumbs, sha1={result['sha1'][:8]}")
    return result


class IIIFFileSourceReader(FileSourceReader):
    dtype = 'iiif'
    executor = 'thread'
    worker_fn = staticmethod(_process_iiif_item)

    def __init__(self, project, root: str, config: IIIFSourceConfig | None = None,
                 image_types: list[ImageTypeSpec] | None = None):
        super().__init__(project, root.strip())
        self.config = config or IIIFSourceConfig()
        self.max_workers = MAX_WORKERS
        self.image_types = image_types if image_types is not None else [
            (t.id, t.format, t.width, t.height)
            for t in project.get_image_types()
            if t.auto_gen
        ]
        self.is_cancelled: Callable[[], bool] = lambda: False

    def worker_args(self, item: ItemRef) -> tuple:
        return (self._capped_url(item.fetch), self._headers(), self.image_types)

    def fetch_bytes(self, ref: str) -> bytes:
        """Full-resolution fetch — used by the /image/raw proxy, with the same
        retry/auth/rate-limit treatment as import downloads."""
        return _get_with_retry(ref, self._headers()).content

    def _headers(self) -> dict:
        return self.config.apply_all_headers(dict(HTTP_HEADERS))

    # ------------------------------------------------------------------
    # Probing (used by the /iiif/test route — same parsing as a real import,
    # so the "test connection" preview can't drift from what import actually sees)
    # ------------------------------------------------------------------

    def probe(self) -> dict:
        entry = self._fetch_json(self.root)
        if entry is None:
            return {'success': False, 'error': f'Could not fetch {self.root}'}
        version = self._detect_version(entry)
        node_type = self._node_type(entry)
        item_count = (
            len(self._collection_children(entry, version))
            if node_type == 'Collection'
            else len(self._manifest_canvases(entry, version))
        )
        return {
            'success': True,
            'title': self._node_id(entry),
            'label': self._label(entry, version),
            'version': version,
            'type': node_type,
            'itemCount': item_count,
        }

    # ------------------------------------------------------------------
    # Source bootstrap
    # ------------------------------------------------------------------

    def ensure_source(self) -> int:
        if self.file_source_id is not None:
            return self.file_source_id

        existing = next(
            (s for s in self.project.get_file_sources()
             if s.dtype == 'iiif' and s.root_url == self.root),
            None,
        )
        if existing:
            print(f'[IIIF] reusing existing FileSource id={existing.id} (name={existing.name!r})')
            self.config = IIIFSourceConfig.from_dict(existing.metadata)
            self.file_source_id = existing.id
            return self.file_source_id

        entry = self._fetch_json(self.root)
        version = self._detect_version(entry) if entry else 3
        name = (self._label(entry, version) if entry else None) or self.root

        fs_id = self.project.allocate_file_sources(1)
        if isinstance(fs_id, range):
            fs_id = fs_id.start
        commit = UpsertCommit()
        commit.file_sources[fs_id] = FileSource(
            id=fs_id, dtype='iiif', name=name, root_url=self.root,
            metadata=self.config.to_dict(),
        )
        self.project.apply_upsert_commit('iiif_import', commit)
        print(f'[IIIF] created FileSource id={fs_id} (name={name!r})')
        self.file_source_id = fs_id
        return fs_id

    def save_config(self) -> None:
        """Persist the current config (e.g. updated import history) to the FileSource row."""
        if self.file_source_id is None:
            return
        source = next((s for s in self.project.get_file_sources() if s.id == self.file_source_id), None)
        if not source:
            return
        commit = UpsertCommit()
        commit.file_sources[source.id] = FileSource(
            id=source.id, dtype=source.dtype, name=source.name, root_url=source.root_url,
            metadata=self.config.to_dict(),
        )
        self.project.apply_upsert_commit('iiif_import', commit)

    def on_import_complete(self, fs_id: int, done: int, failed: int, total: int) -> None:
        status = 'partial' if failed > 0 else 'success'
        self.config.update_import_history(status=status, count=done - failed, total=total)
        self.save_config()

    # ------------------------------------------------------------------
    # Traversal — builds folder tree (preorder, parents first) + canvas items
    # ------------------------------------------------------------------

    def scan(self) -> tuple[list[FolderNode], list[ItemRef]]:
        print(f'[IIIF] entry url: {self.root}')
        entry = self._fetch_json(self.root)
        if entry is None:
            print('[IIIF] ABORT: could not fetch entry url')
            logger.error('IIIF import aborted: could not fetch %s', self.root)
            return [], []
        version = self._detect_version(entry)
        print(f'[IIIF] fetched entry — version=v{version}, type={self._node_type(entry)}, '
              f'label={self._label(entry, version)!r}')

        self.ensure_source()  # so a fresh source reuses the entry we already fetched

        folder_nodes: list[FolderNode] = []
        items: list[ItemRef] = []
        self._collect(entry, version, parent_path=None, folder_nodes=folder_nodes, items=items)
        print(f'[IIIF] traversal done: {len(folder_nodes)} folder node(s), {len(items)} canvas(es) found')
        return folder_nodes, items

    def _collect(self, node: dict, version: int, parent_path: str | None,
                 folder_nodes: list[FolderNode], items: list[ItemRef]):
        if self.is_cancelled():
            return

        node_type = self._node_type(node)
        node_id = self._node_id(node)
        if not node_id:
            print(f'[IIIF] skip node with no id (type={node_type})')
            return

        label = self._label(node, version) or node_id
        folder_nodes.append(FolderNode(path=node_id, name=label, parent_path=parent_path))

        if node_type == 'Collection':
            children = self._collection_children(node, version)
            print(f'[IIIF] Collection {label!r}: {len(children)} child(ren)')
            for child in children:
                child_id = self._node_id(child)
                if not child_id:
                    continue
                # Children are usually references — fetch the full document.
                full = self._fetch_json(child_id) or child
                self._collect(full, self._detect_version(full), node_id, folder_nodes, items)
        elif node_type == 'Manifest':
            manifest_canvases = self._manifest_canvases(node, version)
            before = len(items)
            for canvas in manifest_canvases:
                self._collect_canvas(canvas, version, node_id, items)
            print(f'[IIIF] Manifest {label!r}: {len(manifest_canvases)} canvas(es), '
                  f'{len(items) - before} with usable image')
        else:
            print(f'[IIIF] unhandled node type {node_type!r} ({label!r})')

    def _collect_canvas(self, canvas: dict, version: int, manifest_path: str, items: list[ItemRef]):
        body = self._canvas_image_body(canvas, version)
        if not body:
            print(f'[IIIF]   canvas {self._node_id(canvas)} — no image body, skipping')
            return
        url = self._image_url(body, version)
        if not url:
            print(f'[IIIF]   canvas {self._node_id(canvas)} — no image url, skipping')
            return
        # name (stored in file.name) is the full-res URL, returned verbatim by the serve
        # resolver for /image/raw. The capped rendition is only used at import time for
        # sha1 + thumbnail generation (avoids full-res throttling).
        items.append(ItemRef(folder_path=manifest_path, name=url, fetch=url))

    # ------------------------------------------------------------------
    # HTTP / parsing helpers
    # ------------------------------------------------------------------

    def _fetch_json(self, url: str) -> dict | None:
        print(f'[IIIF] GET json: {url}')
        try:
            resp = _get_with_retry(url, self._headers())
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

    @staticmethod
    def _collection_children(node: dict, version: int) -> list[dict]:
        if version >= 3:
            return [c for c in node.get('items', [])
                    if IIIFFileSourceReader._node_type(c) in ('Collection', 'Manifest')]
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
