import hashlib
import io
import logging
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

from panoptic.core.databases.entity_schema import OP_CREATE
from panoptic.core.databases.media.models import Image
from panoptic.models.data import File, FileSource, FileValue, Folder, Instance, Property, UpsertCommit
from panoptic2.core.task.task import Task

logger = logging.getLogger('ImportFolderTask')

IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
MAX_WORKERS = min(os.cpu_count() or 4, 10)
WRITE_BATCH = 60

# Default properties created (once) for every project, keyed by mode='file'.
# Names match keys returned by _process_one so the write loop needs no extra mapping.
FILE_METADATA_PROPS = [
    ('width',     'width'),
    ('height',    'height'),
    ('path',      'path'),
    ('sha1',      'sha1'),
    ('extension', 'text'),
    ('file_size', 'number'),
]

# (type_id, format, max_width, max_height)
ImageTypeSpec = tuple[int, str, int | None, int | None]


# ---------------------------------------------------------------------------
# Worker helpers (module-level — must be picklable for ProcessPoolExecutor)
# ---------------------------------------------------------------------------

def _process_one(
    path: str,
    folder_id: int | None,
    image_types: list[ImageTypeSpec],
) -> dict | None:
    """Runs in a worker process: read + sha1 + PIL resize for every auto_gen type."""
    from PIL import Image as PilImage

    try:
        with open(path, 'rb') as f:
            raw = f.read()
    except Exception:
        return None

    sha1      = hashlib.sha1(raw).hexdigest()
    file_size = len(raw)
    width = height = None
    images = []

    try:
        with PilImage.open(io.BytesIO(raw)) as img:
            width, height = img.size
            if image_types:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                img.load()
                for type_id, fmt, max_w, max_h in image_types:
                    data = _render(img, fmt, max_w, max_h)
                    images.append((type_id, data))
    except Exception as e:
        logger.error('PIL failed on %s: %s', path, e)

    return {
        'path': path, 'folder_id': folder_id, 'sha1': sha1,
        'images': images, 'width': width, 'height': height, 'file_size': file_size,
        'extension': os.path.splitext(path)[1].lstrip('.').lower(),
    }


def _render(img, fmt: str, max_w: int | None, max_h: int | None) -> bytes:
    """Resize to fit within (max_w, max_h) — both optional — then encode."""
    copy = img.copy()
    if max_w or max_h:
        copy.thumbnail((max_w or 10 ** 6, max_h or 10 ** 6))
    buf = io.BytesIO()
    # PIL uses 'jpeg' not 'jpg'
    copy.save(buf, format='jpeg' if fmt.lower() in ('jpg', 'jpeg') else fmt)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class ImportFolderTask(Task):
    def __init__(self, project, folder_path: str):
        super().__init__()
        self.name = 'Import Folder'
        self._project     = project
        self._folder_path = os.path.normpath(folder_path)

        # Snapshot auto_gen types at creation time so workers get a consistent view
        self._image_types: list[ImageTypeSpec] = [
            (t.id, t.format, t.width, t.height)
            for t in project.get_image_types()
            if t.auto_gen
        ]

    def _ensure_metadata_properties(self) -> dict[str, int]:
        """Create default file-metadata properties if they don't exist yet.

        Returns a mapping {property_name: property_id} for all FILE_METADATA_PROPS.
        """
        existing = {p.name: p.id for p in self._project.get_properties(mode='file')}
        needed = [(name, dtype) for name, dtype in FILE_METADATA_PROPS if name not in existing]

        if needed:
            ids = self._project.allocate_properties(len(needed))
            if isinstance(ids, int):
                ids = range(ids, ids + 1)
            commit = UpsertCommit()
            for (name, dtype), prop_id in zip(needed, ids):
                commit.properties[prop_id] = Property(
                    id=prop_id, dtype=dtype, mode='file', name=name,
                    access=None, tag_list_id=None, commit_id=0, operation=OP_CREATE,
                )
            self._project.apply_upsert_commit('import', commit)
            for (name, _), prop_id in zip(needed, ids):
                existing[name] = prop_id

        return {name: existing[name] for name, _ in FILE_METADATA_PROPS if name in existing}

    def start(self):
        import time
        t0 = time.monotonic()
        self._meta_props = self._ensure_metadata_properties()

        # Scan first — we need the path lists before hitting the DB
        folder_nodes, image_paths = self._scan(self._folder_path)

        # Query only for the paths we actually found — never loads the full table
        folder_paths  = [n['path'] for n in folder_nodes]
        existing_folders = {
            f.path: f.id
            for f in self._project.get_folders(path=folder_paths)
            if f.path
        }
        existing_files = {
            f.name
            for f in self._project.get_files(name=image_paths)
            if f.name
        }

        image_paths = [p for p in image_paths if p not in existing_files]

        self.state.total = len(image_paths)
        self._notify()

        path_to_folder_id = self._import_folder_tree(folder_nodes, existing_folders)

        items = [
            (path, path_to_folder_id.get(os.path.dirname(path)))
            for path in image_paths
        ]

        image_types = self._image_types  # local ref avoids repeated self lookup in loop
        batch: list[dict] = []

        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {
                pool.submit(_process_one, path, folder_id, image_types): None
                for path, folder_id in items
            }

            for future in as_completed(futures):
                if self._cancel_event.is_set():
                    break

                result = None
                try:
                    result = future.result()
                except Exception as e:
                    logger.error('Worker failed: %s', e)

                if result:
                    batch.append(result)
                    if len(batch) >= WRITE_BATCH:
                        self._write_batch(batch)
                        batch.clear()

                self.state.done += 1
                self._notify()

        if batch:
            self._write_batch(batch)

        elapsed = time.monotonic() - t0
        rate = self.state.done / elapsed if elapsed > 0 else 0
        print(f'Import done:{self.state.done} instances in {elapsed}s ({rate} img/s)')

    # ------------------------------------------------------------------
    # Filesystem scan
    # ------------------------------------------------------------------

    def _scan(self, root: str) -> tuple[list[dict], list[str]]:
        folder_path_set: set[str] = set()
        image_paths: list[str] = []

        for dirpath, _, filenames in os.walk(root):
            current = dirpath
            while len(current) >= len(root):
                folder_path_set.add(current)
                parent = os.path.dirname(current)
                if parent == current:
                    break
                current = parent

            for name in filenames:
                if name.lower().endswith(IMAGE_EXTENSIONS):
                    image_paths.append(os.path.join(dirpath, name))

        folder_nodes = []
        for path in sorted(folder_path_set):
            parent_path = os.path.dirname(path)
            folder_nodes.append({
                'path':        path,
                'name':        os.path.basename(path),
                'parent_path': parent_path if parent_path != path and parent_path in folder_path_set else None,
            })

        return folder_nodes, image_paths

    # ------------------------------------------------------------------
    # DB writes (main thread only)
    # ------------------------------------------------------------------

    def _import_folder_tree(
        self,
        folder_nodes: list[dict],
        existing_folders: dict[str, int],
    ) -> dict[str, int]:
        # Seed the mapping with already-known folders
        path_to_id: dict[str, int] = dict(existing_folders)

        new_nodes = [n for n in folder_nodes if n['path'] not in path_to_id]
        if not new_nodes:
            return path_to_id

        project  = self._project
        fs_id    = project.allocate_file_sources(1)
        id_range = project.allocate_folders(len(new_nodes))
        if isinstance(id_range, int):
            id_range = range(id_range, id_range + 1)

        commit = UpsertCommit()
        commit.file_sources[fs_id] = FileSource(
            id=fs_id, dtype='local',
            name=os.path.basename(self._folder_path),
            root_url=self._folder_path,
            commit_id=0, operation=OP_CREATE,
        )

        for node, fid in zip(new_nodes, id_range):
            parent_id = path_to_id.get(node['parent_path']) if node['parent_path'] else None
            commit.folders[fid] = Folder(
                id=fid, source_id=fs_id,
                path=node['path'], name=node['name'], parent=parent_id,
                commit_id=0, operation=OP_CREATE,
            )
            path_to_id[node['path']] = fid

        project.apply_upsert_commit('import', commit)
        return path_to_id

    def _write_batch(self, results: list[dict]):
        if not results:
            return

        project  = self._project
        n        = len(results)
        file_ids = project.allocate_files(n)
        inst_ids = project.allocate_instances(n)
        if isinstance(file_ids, int):
            file_ids = range(file_ids, file_ids + 1)
        if isinstance(inst_ids, int):
            inst_ids = range(inst_ids, inst_ids + 1)

        commit = UpsertCommit()
        media:  list[Image] = []

        for info, fid, iid in zip(results, file_ids, inst_ids):
            commit.files[fid] = File(
                id=fid, name=info['path'], folder_id=info['folder_id'],
                sha1=info['sha1'], commit_id=0, operation=OP_CREATE,
            )
            commit.instances[iid] = Instance(
                id=iid, file_id=fid, sha1=info['sha1'],
                commit_id=0, operation=OP_CREATE,
            )
            for name, prop_id in self._meta_props.items():
                value = info.get(name)
                if value is not None:
                    commit.file_values.setdefault(prop_id, []).append(
                        FileValue(property_id=prop_id, file_id=fid, value=value,
                                  commit_id=0, operation=OP_CREATE)
                    )
            for type_id, data in info.get('images', []):
                media.append(Image(type_id=type_id, sha1=info['sha1'], data=data))

        project.apply_upsert_commit('import', commit)
        if media:
            project.upsert_images(media)
