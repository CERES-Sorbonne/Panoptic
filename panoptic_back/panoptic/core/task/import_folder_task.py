import asyncio
import os
import logging
from panoptic.core.task.task import Task
from panoptic.core.task.import_instance_task import ImportInstanceTask

logger = logging.getLogger('ImportFolderTask')

# Use a tuple for super-fast endswith checking
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.webp')


class ImportFolderTask(Task):
    """
    Scans folders using a background thread (zero IPC overhead) 
    and yields control during large DB/Memory operations to keep the UI smooth.
    """

    def __init__(self, project, folders: list[str]):
        super().__init__()
        self.name = 'Import Folder'
        self._project = project
        self._folders = [os.path.normpath(f) for f in folders]
        self.state.total = len(self._folders)

    async def start(self):
        self.state.running = True
        self._notify()

        all_images_to_process = []

        for folder in self._folders:
            if self._cancel_event.is_set():
                break

            # 1. Run filesystem walk in a Thread. 
            # Threads share memory, so returning a 100k item dict is instant.
            scan_result = await asyncio.to_thread(self._scan_folder_thread, folder)

            # 2. Sync folders to DB (Chunks to prevent loop starvation)
            path_to_id = await self._sync_folders_to_db(scan_result['folder_nodes'])

            # 3. Prepare images for the ImportInstanceTask
            images = scan_result['images']
            image_to_folder = scan_result['image_to_folder_path']

            # Process the 100k list in chunks so the Event Loop can breathe
            chunk_size = 5000
            for i in range(0, len(images), chunk_size):
                if self._cancel_event.is_set():
                    break

                chunk = images[i:i + chunk_size]
                for img_path in chunk:
                    folder_path = image_to_folder[img_path]
                    all_images_to_process.append((img_path, path_to_id[folder_path]))

                # Magic trick: Yields control back to asyncio to process UI/Network events
                await asyncio.sleep(0)

            self.state.done += 1
            self._project.on.sync.emitFolders(await self._project.db.get_folders())
            self._notify()

        # 4. Chain the ImportInstanceTask
        if all_images_to_process and not self._cancel_event.is_set():
            logger.info(f"Passing {len(all_images_to_process)} images to ImportInstanceTask")
            next_task = ImportInstanceTask(self._project, all_images_to_process)
            self._project.task_manager.add_task(next_task)

        self.state.running = False
        self.state.finished = True
        self._finished_event.set()
        self._notify()

    def _scan_folder_thread(self, folder: str) -> dict:
        """Runs in a background thread. Fast, blocking I/O."""
        images = []
        folder_path_set = set()
        image_to_folder_path = {}

        for dirpath, _, filenames in os.walk(folder):
            # Track directories
            if dirpath not in folder_path_set:
                current = dirpath
                while len(current) >= len(folder):
                    folder_path_set.add(current)
                    parent = os.path.dirname(current)
                    if parent == current:
                        break
                    current = parent

            for name in filenames:
                # String manipulation is much faster than Path() for 100k inner-loops
                if name.lower().endswith(IMAGE_EXTENSIONS):
                    full_path = os.path.join(dirpath, name)
                    images.append(full_path)
                    image_to_folder_path[full_path] = dirpath

        # Sort so parent paths appear before child paths
        folder_nodes = []
        for path in sorted(folder_path_set):
            parent_path = os.path.dirname(path)
            folder_nodes.append({
                'path': path,
                'name': os.path.basename(path),
                'parent_path': parent_path if parent_path != path and parent_path in folder_path_set else None
            })

        return {
            'images': images,
            'folder_nodes': folder_nodes,
            'image_to_folder_path': image_to_folder_path
        }

    async def _sync_folders_to_db(self, folder_nodes: list[dict]) -> dict[str, int]:
        """Inserts folders into the database while keeping the UI responsive."""
        db = self._project.db
        path_to_id = {}

        chunk_size = 500
        for i in range(0, len(folder_nodes), chunk_size):
            chunk = folder_nodes[i:i + chunk_size]
            for node in chunk:
                parent_id = path_to_id.get(node['parent_path']) if node['parent_path'] else None
                folder = await db.add_folder(node['path'], node['name'], parent_id)
                path_to_id[node['path']] = folder.id

            # Yield control to event loop after every chunk of DB writes
            await asyncio.sleep(0)

        return path_to_id