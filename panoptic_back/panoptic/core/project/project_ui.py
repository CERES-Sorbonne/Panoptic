from panoptic.core.project.project_db import ProjectDb
from panoptic.models import UpdateCounter, DbCommit, PluginDescription, ActionDescription, DbUpdate


class ProjectUi:
    def __init__(self, db: ProjectDb):
        self._db = db
        self.update_counter = UpdateCounter()

        self.commits: list[DbCommit] = []
        self.plugins: list[PluginDescription] = []
        self.actions: list[ActionDescription] = []
        self.broadcast_db_update_callback = None

    def set_broadcast_callback(self, callback):
        self.broadcast_db_update_callback = callback

    def clear(self):
        self.commits.clear()
        self.plugins.clear()
        self.actions.clear()

    async def on_db_update(self, update: DbUpdate, sid=None):
        # Process the update, e.g., update internal state
        print(f"Received db_update from {sid}: {update}")
        # Broadcast the update to other clients
        if self.broadcast_db_update_callback:
            await self.broadcast_db_update_callback(update, sid)
