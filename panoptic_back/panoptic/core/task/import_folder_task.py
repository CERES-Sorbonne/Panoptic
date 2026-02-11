import os
from pathlib import Path
from typing import List

from panoptic.core.task.import_instance_task import ImportInstanceTask
from panoptic.core.task.task import Task


class ImportFolderTask(Task):
    def __init__(self, seq: int, folder: str):
        super().__init__(priority=True)
        self.folder = os.path.normpath(folder)
        self.seq = seq
        self.name = 'Import Folder'
        self.key += '-' + str(seq)

    async def run(self):
        # Gather all image files from folder
        all_images = await self.run_async(self._get_all_images, self.folder)

        # Compute folder structure
        folder_node, file_to_folder_id = await self._compute_folder_structure(self.folder, all_images)

        # Create and queue individual import tasks
        tasks = [ImportInstanceTask(seq=self.seq, file=file, folder_id=file_to_folder_id[file])
                 for file in all_images]

        for task in tasks:
            self._project.task_queue.add_task(task)

        # Emit folders update
        self._project.on.sync.emitFolders(await self._project.db.get_folders())

    async def _compute_folder_structure(self, root_path, all_files: List[str]):
        offset = len(root_path)
        root, root_name = os.path.split(root_path)
        root_folder = await self._project.db.add_folder(root_path, root_name)
        file_to_folder_id = {}
        for file in all_files:
            path, name = os.path.split(file)
            if offset == len(path):
                file_to_folder_id[file] = root_folder.id
                continue
            path = path[offset + 1:]
            parts = Path(path).parts
            current_folder = root_folder
            for part in parts:
                if part not in current_folder.children:
                    child = await self._project.db.add_folder(current_folder.path + '/' + part, part, current_folder.id)
                    current_folder.children[part] = child
                else:
                    child = current_folder.children[part]
                file_to_folder_id[file] = child.id
                current_folder = child
        return root_folder, file_to_folder_id

    @staticmethod
    def _get_all_images(folder: str) -> List[str]:
        """Get all files from folder tree (run in executor to avoid blocking)"""
        all_files = [os.path.join(path, name)
                for path, subdirs, files in os.walk(folder)
                for name in files]

        all_images = [i for i in all_files if
                      i.lower().endswith('.png') or i.lower().endswith('.jpg') or
                      i.lower().endswith('.jpeg') or i.lower().endswith('.gif') or
                      i.lower().endswith('.webp')]

        return all_images

    async def run_if_last(self):
        """Called when this is the last ImportFolderTask in the queue"""
        pass