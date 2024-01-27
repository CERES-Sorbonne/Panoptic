from panoptic.core.db.db import Db


class ProjectUi:
    def __init__(self, db: Db):
        self._db = db

    async def get_tabs(self):
        return await self._db.get_tabs()

    async def add_tab(self, data):
        return await self._db.add_tab(data)

    async def update_tab(self, data):
        return await self._db.update_tab(data)

    async def delete_tab(self, tab_id: int):
        return await self._db.delete_tab(tab_id)
