from panoptic.core.db.db import Db
from panoptic.models import UpdateCounter


#
class ProjectUi:
    def __init__(self, db: Db):
        self._db = db
        self.update_counter = UpdateCounter()
