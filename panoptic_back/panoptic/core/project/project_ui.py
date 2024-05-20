from panoptic.core.db.db import Db
from panoptic.models import UpdateCounter, DbCommit, PluginDescription, ActionDescription


#
class ProjectUi:
    def __init__(self, db: Db):
        self._db = db
        self.update_counter = UpdateCounter()

        self.commits: list[DbCommit] = []
        self.plugins: list[PluginDescription] = []
        self.actions: list[ActionDescription] = []

    def clear(self):
        self.commits.clear()
        self.plugins.clear()
        self.actions.clear()
