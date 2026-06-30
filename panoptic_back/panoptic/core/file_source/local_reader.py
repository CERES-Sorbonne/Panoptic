import logging
import os
from datetime import datetime

from panoptic.core.file_source.base import FileSourceReader, FolderNode, ItemRef
from panoptic.core.file_source.processing import ImageTypeSpec, process_bytes

logger = logging.getLogger('LocalFileSourceReader')

IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.webp')


def _process_local_item(path: str, image_types: list[ImageTypeSpec]) -> dict | None:
    """Runs in a worker process (must be picklable, hence module-level)."""
    try:
        with open(path, 'rb') as f:
            raw = f.read()
    except Exception:
        return None

    created_at = datetime.fromtimestamp(os.stat(path).st_mtime)
    result = process_bytes(
        raw, image_types,
        on_pil_error=lambda e: logger.error('PIL failed on %s: %s', path, e),
    )
    result['created_at'] = created_at
    return result


class LocalFileSourceReader(FileSourceReader):
    dtype = 'local'
    executor = 'process'
    worker_fn = staticmethod(_process_local_item)

    def __init__(self, project, root: str, image_types: list[ImageTypeSpec] | None = None):
        super().__init__(project, os.path.normpath(root))
        self.max_workers = min(os.cpu_count() or 4, 10)
        self.image_types = image_types if image_types is not None else [
            (t.id, t.format, t.width, t.height)
            for t in project.get_image_types()
            if t.auto_gen
        ]

    def ensure_source(self) -> int:
        return self.project.ensure_local_file_source()

    def scan(self) -> tuple[list[FolderNode], list[ItemRef]]:
        root = self.root
        folder_path_set: set[str] = set()
        items: list[ItemRef] = []

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
                    items.append(ItemRef(
                        folder_path=dirpath,
                        name=name,
                        fetch=os.path.join(dirpath, name),
                    ))

        folder_nodes = []
        for path in sorted(folder_path_set):
            parent_path = os.path.dirname(path)
            folder_nodes.append(FolderNode(
                path=path,
                name=os.path.basename(path),
                parent_path=parent_path if parent_path != path and parent_path in folder_path_set else None,
            ))

        return folder_nodes, items

    def worker_args(self, item: ItemRef) -> tuple:
        return (item.fetch, self.image_types)

    def fetch_bytes(self, ref: str) -> bytes:
        with open(ref, 'rb') as f:
            return f.read()
