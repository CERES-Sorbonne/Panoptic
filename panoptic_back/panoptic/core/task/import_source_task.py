import logging
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

from panoptic.core.file_source.base import FileSourceReader, import_folder_tree, write_batch
from panoptic.core.task.task import Task

logger = logging.getLogger('ImportSourceTask')

WRITE_BATCH = 60


class ImportSourceTask(Task):
    """Imports a FileSourceReader's tree: scan -> fetch+process (parallel) -> write.

    Source-specific behavior (filesystem walk vs IIIF manifest traversal, local read
    vs HTTP download) lives entirely in the reader; this task just drives it.
    """

    def __init__(self, project, reader: FileSourceReader, commit_source: str):
        super().__init__()
        self.name = f'Import {reader.dtype}'
        self._project = project
        self._reader = reader
        self._commit_source = commit_source
        # Only meaningful to readers whose scan() can take a while (e.g. IIIF
        # traversing a large collection) — local's os.walk doesn't check it.
        reader.is_cancelled = self._cancel_event.is_set

    def start(self):
        t0 = time.monotonic()
        reader = self._reader

        self.set_step('Scanning folder structure')
        fs_id = reader.ensure_source()

        # Resync support: if this root was already imported, capture its previous
        # folder/file tree before rescanning, so we can reconcile deletions below.
        # Scoped to reader.root's subtree (not the whole file source) because local
        # imports share one singleton FileSource across independently-imported roots.
        pre_existing_folders = self._project.get_folders(source_id=fs_id)
        root_folder = next((f for f in pre_existing_folders if f.path == reader.root), None)
        old_folder_ids: set[int] = set()
        if root_folder is not None:
            children_by_parent: dict[int, list[int]] = {}
            for f in pre_existing_folders:
                if f.parent is not None:
                    children_by_parent.setdefault(f.parent, []).append(f.id)
            frontier = [root_folder.id]
            old_folder_ids.add(root_folder.id)
            while frontier:
                frontier = [c for p in frontier for c in children_by_parent.get(p, []) if c not in old_folder_ids]
                old_folder_ids.update(frontier)

        old_files_by_key = {
            (f.folder_id, f.name): f.id
            for f in self._project.get_files(folder_id=list(old_folder_ids))
            if f.name and f.folder_id is not None
        } if old_folder_ids else {}

        folder_nodes, items = reader.scan()

        path_to_folder_id = import_folder_tree(self._project, fs_id, folder_nodes, self._commit_source)

        pending = []
        for item in items:
            folder_id = path_to_folder_id.get(item.folder_path)
            if folder_id is None or (folder_id, item.name) in old_files_by_key:
                continue
            pending.append((folder_id, item))

        removed_files = 0
        if old_folder_ids:
            self.set_step('Reconciling removed files')
            current_folder_ids = {path_to_folder_id[n.path] for n in folder_nodes if n.path in path_to_folder_id}
            missing_folder_ids = old_folder_ids - current_folder_ids
            if missing_folder_ids:
                removed_files += len([
                    k for k in old_files_by_key if k[0] in missing_folder_ids
                ])
                self._project.delete_folders(list(missing_folder_ids))

            seen_now = {(path_to_folder_id[item.folder_path], item.name) for item in items}
            missing_file_ids = [
                fid for key, fid in old_files_by_key.items()
                if key not in seen_now and key[0] not in missing_folder_ids
            ]
            if missing_file_ids:
                removed_files += len(missing_file_ids)
                self._project.delete_files(missing_file_ids)

        self.state.total = len(pending)
        self.set_step('Importing files')
        self.set_workers(reader.max_workers)

        executor_cls = ProcessPoolExecutor if reader.executor == 'process' else ThreadPoolExecutor
        batch: list[dict] = []

        with executor_cls(max_workers=reader.max_workers) as pool:
            futures = {
                pool.submit(reader.worker_fn, *reader.worker_args(item)): (folder_id, item)
                for folder_id, item in pending
            }
            for future in as_completed(futures):
                if self._cancel_event.is_set():
                    break

                folder_id, item = futures[future]
                result = None
                try:
                    result = future.result()
                except Exception as e:
                    logger.error('Worker failed: %s', e)

                if result:
                    result['folder_id'] = folder_id
                    result['name'] = item.name
                    batch.append(result)
                    if len(batch) >= WRITE_BATCH:
                        write_batch(self._project, batch, self._commit_source)
                        batch.clear()
                else:
                    self.state.failed += 1

                self.state.done += 1
                self._notify()

        if batch:
            write_batch(self._project, batch, self._commit_source)

        elapsed = time.monotonic() - t0
        rate = self.state.done / elapsed if elapsed > 0 else 0
        logger.info('Import done: %s items in %.1fs (%.1f/s, %s failed, %s removed)',
                     self.state.done, elapsed, rate, self.state.failed, removed_files)

        reader.on_import_complete(fs_id, self.state.done, self.state.failed, self.state.total, removed_files)

    def on_last(self) -> None:
        from panoptic.core.task.generate_atlas_task import GenerateAtlasTask
        self._project.add_task(GenerateAtlasTask(self._project))
