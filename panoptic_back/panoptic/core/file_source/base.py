from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional

from panoptic.core.databases.data.models import File, FileSource, Folder, Instance, UpsertCommit
from panoptic.core.databases.media.models import Image


@dataclass
class FolderNode:
    path: str
    name: str
    parent_path: Optional[str]


@dataclass
class ItemRef:
    """One importable leaf under a source: identity (folder + name) plus an opaque
    payload telling the reader's worker function how to fetch its bytes."""
    folder_path: str
    name: str   # stored verbatim as File.name
    fetch: Any  # passed to the reader's worker_fn via worker_args()


class FileSourceReader(ABC):
    """Reads one FileSource's tree + bytes.

    Local filesystem, IIIF, etc. each implement this so import tasks and the
    /image/raw serve proxy stay source-agnostic — adding a new source type means
    writing one reader, not touching tasks/routes/data_reader.
    """

    dtype: str
    executor: str = 'thread'  # 'thread' (network-bound) or 'process' (CPU-bound)
    max_workers: int = 4
    worker_fn: Callable  # module-level, executor-submittable: worker_fn(*args) -> dict | None

    def __init__(self, project, root: str):
        self.project = project
        self.root = root  # folder path for local, manifest/collection URL for IIIF
        self.file_source_id: int | None = None  # set once ensure_source() resolves it

    @abstractmethod
    def ensure_source(self) -> int:
        """Return this source's FileSource id, creating the row if needed."""

    @abstractmethod
    def scan(self) -> tuple[list[FolderNode], list[ItemRef]]:
        """Discover the folder tree and importable items under self.root."""

    @abstractmethod
    def worker_args(self, item: ItemRef) -> tuple:
        """Positional args to submit to the executor as worker_fn(*args)."""

    def fetch_bytes(self, ref: str) -> bytes:
        """Read raw bytes for a serve-time reference (see resolve_serve_ref).

        Used by the /image/raw proxy. Default raises — local files are served
        straight off disk by the route and never need this.
        """
        raise NotImplementedError(f'{type(self).__name__} does not support fetch_bytes')

    def on_import_complete(self, fs_id: int, done: int, failed: int, total: int) -> None:
        """Post-import hook: snapshots generic sync status onto the FileSource row.

        Subclasses that track dtype-specific history (e.g. IIIF) should call
        ``super().on_import_complete(...)`` first, then layer their own metadata.
        """
        update_sync_status(self.project, fs_id, done, failed, total)


# ---------------------------------------------------------------------------
# Shared DB-write helpers — identical for every source type today, so a single
# copy lives here instead of one per task.
# ---------------------------------------------------------------------------

def update_file_source(project, fs_id: int, commit_source: str, **overrides) -> None:
    """Patch a FileSource row, preserving any field not passed in ``overrides``."""
    source = next((s for s in project.get_file_sources() if s.id == fs_id), None)
    if not source:
        return

    fields = {f: getattr(source, f) for f in ('dtype', 'name', 'root_url', 'metadata', 'sync_status')}
    fields.update(overrides)

    commit = UpsertCommit()
    commit.file_sources[fs_id] = FileSource(id=source.id, **fields)
    project.apply_upsert_commit(commit_source, commit)


def update_sync_status(project, fs_id: int, done: int, failed: int, total: int) -> None:
    """Compute and persist a generic last-sync snapshot for a FileSource."""
    folders = project.get_folders(source_id=fs_id)
    folder_ids = [f.id for f in folders]
    file_count = len(project.get_files(folder_id=folder_ids)) if folder_ids else 0

    sync_status = {
        'last_synced_at': datetime.utcnow().isoformat() + 'Z',
        'status': 'partial' if failed > 0 else 'success',
        'folder_count': len(folders),
        'file_count': file_count,
        'imported_count': done - failed,
        'failed_count': failed,
    }
    update_file_source(project, fs_id, 'sync_status', sync_status=sync_status)


def import_folder_tree(
    project, fs_id: int, folder_nodes: list[FolderNode], commit_source: str,
) -> dict[str, int]:
    existing = {
        f.path: f.id
        for f in project.get_folders(source_id=fs_id)
        if f.path
    }
    path_to_id: dict[str, int] = dict(existing)

    seen = set()
    new_nodes = []
    for n in folder_nodes:
        if n.path in path_to_id or n.path in seen:
            continue
        seen.add(n.path)
        new_nodes.append(n)

    if not new_nodes:
        return path_to_id

    id_range = project.allocate_folders(len(new_nodes))
    if isinstance(id_range, int):
        id_range = range(id_range, id_range + 1)

    commit = UpsertCommit()
    for node, fid in zip(new_nodes, id_range):
        parent_id = path_to_id.get(node.parent_path) if node.parent_path else None
        commit.folders[fid] = Folder(
            id=fid, source_id=fs_id,
            path=node.path, name=node.name, parent=parent_id,
        )
        path_to_id[node.path] = fid

    project.apply_upsert_commit(commit_source, commit)
    return path_to_id


def write_batch(project, results: list[dict], commit_source: str) -> None:
    """results: dicts produced by a reader's worker_fn, each augmented with
    'folder_id' and 'name' (-> File.name) before being passed here."""
    if not results:
        return

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
            name=info['name'],
            folder_id=info['folder_id'],
            sha1=info['sha1'],
            width=info.get('width'),
            height=info.get('height'),
            format=info.get('format'),
            created_at=info.get('created_at'),
        )
        commit.instances[iid] = Instance(id=iid, file_id=fid, sha1=info['sha1'])
        for type_id, data in info.get('images', []):
            media.append(Image(type_id=type_id, sha1=info['sha1'], data=data))

    project.apply_upsert_commit(commit_source, commit)
    if media:
        project.upsert_images(media)
