from panoptic.core.databases.panoptic.create import (
    panoptic_db_desc,
    USERS_SCHEMA,
    PROJECTS_SCHEMA,
    PLUGINS_SCHEMA,
)
from panoptic.core.databases.panoptic.models import User, ProjectKey, PluginKey
from panoptic.core.databases.sqlite_db import SQLiteWriter


class PanopticDB(SQLiteWriter):

    def __init__(self, path: str):
        super().__init__(path, panoptic_db_desc)
        self.start()

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def get_projects(self) -> list[ProjectKey]:
        return PROJECTS_SCHEMA.get(self.conn)

    def add_project(self, path: str, excluded_plugins: list[str] = None) -> ProjectKey:
        project = ProjectKey(
            path=path,
            excluded_plugins=excluded_plugins or [],
        )
        with self.transaction() as tx:
            PROJECTS_SCHEMA.upsert(tx, project)
        return project

    def update_project(self, project: ProjectKey) -> ProjectKey:
        with self.transaction() as tx:
            PROJECTS_SCHEMA.upsert(tx, project)
        return project

    def delete_project(self, path: str) -> None:
        with self.transaction() as tx:
            PROJECTS_SCHEMA.delete(tx, path=path)

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def get_users(self) -> list[User]:
        return USERS_SCHEMA.get(self.conn)

    def add_user(self, uid: str, name: str, description: str, password_hash: str = None) -> User:
        user = User(
            uuid=uid,
            name=name,
            description=description,
            password_hash=password_hash,
        )
        with self.transaction() as tx:
            USERS_SCHEMA.upsert(tx, user)
        return user

    def update_user(self, user: User) -> None:
        with self.transaction() as tx:
            USERS_SCHEMA.upsert(tx, user)

    def delete_user(self, user_uuid: str) -> None:
        with self.transaction() as tx:
            USERS_SCHEMA.delete(tx, uuid=user_uuid)

    # ------------------------------------------------------------------
    # Plugins
    # ------------------------------------------------------------------

    def get_plugins(self) -> list[PluginKey]:
        return PLUGINS_SCHEMA.get(self.conn)

    def add_plugin(self, id_: str, install_path: str, source_type: str, source_path: str) -> PluginKey:
        plugin = PluginKey(
            id=id_,
            install_path=install_path,
            source_type=source_type,
            source_path=source_path,
        )
        with self.transaction() as tx:
            PLUGINS_SCHEMA.upsert(tx, plugin)
        return plugin

    def update_plugin(self, plugin: PluginKey) -> None:
        with self.transaction() as tx:
            PLUGINS_SCHEMA.upsert(tx, plugin)

    def delete_plugin(self, plugin_id: str) -> None:
        with self.transaction() as tx:
            PLUGINS_SCHEMA.delete(tx, id=plugin_id)
