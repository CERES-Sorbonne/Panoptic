import json

from panoptic.core.db.utils import auto_dict
from panoptic.core.panoptic_db.create import DB_VERSION
from panoptic.core.panoptic_db.db_connection import DbConnection, panoptic_db_lock
from panoptic.models import PanopticData, ProjectRef, PluginKey, PluginType, ProjectRef2


class PanopticDb:
    def __init__(self, conn: DbConnection):
        if not conn.is_loaded:
            raise Exception('DbConnection is not started. Execute await conn.start() before')
        self.conn = conn

    async def close(self):
        await self.conn.close()

    async def get_data(self) -> PanopticData:
        version = await self.conn.get_param(DB_VERSION)
        projects = await self.get_projects()
        plugins = await self.get_plugins()
        return PanopticData(projects=projects, plugins=plugins, version=int(version))

    async def get_projects(self):
        query = "SELECT * FROM projects"
        cursor = await self.conn.execute_query(query)
        return [ProjectRef2(**auto_dict(p, cursor)) for p in await cursor.fetchall()]

    async def import_project(self, project: ProjectRef2):
        if project.id < 0:
            project.id = await self._get_new_project_id()
        query = "INSERT OR REPLACE INTO projects (id, name, path, ignored_plugins) VALUES (?, ?, ?, ?)"
        await self.conn.execute_query(query, (project.id, project.name, project.path, json.dumps(project.ignored_plugins)))
        return project

    async def delete_project(self, project_id: int):
        query = "DELETE FROM projects WHERE id = ?"
        await self.conn.execute_query(query, (project_id,))
        return project_id

    async def get_plugins(self):
        query = "SELECT * FROM plugins"
        cursor = await self.conn.execute_query(query)
        rows = await cursor.fetchall()
        return [PluginKey(name=r[0], path=r[1], type=PluginType(r[2]), source=r[3]) for r in rows]

    async def import_plugin(self, plugin: PluginKey):
        query = "INSERT OR REPLACE INTO plugins (name, path, type, source) VALUES (?, ?, ?, ?)"
        await self.conn.execute_query(query, (plugin.name, plugin.path, plugin.type.value, plugin.source))
        return plugin

    async def delete_plugin(self, name: str):
        query = "DELETE FROM plugins WHERE name = ?"
        await self.conn.execute_query(query, (name,))
        return name


    @panoptic_db_lock
    async def _get_new_project_id(self):
        query = "SELECT MAX(id) FROM projects"
        cursor = await self.conn.execute_query(query)
        res = await cursor.fetchone()
        if res[0] is None:
            return 1
        else:
            return res[0] + 1


