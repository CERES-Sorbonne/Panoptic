import logging
import uuid

from panoptic.core.databases.panoptic.create import (
    panoptic_db_desc,
    PANOPTIC_CONFIG_SCHEMA,
    USERS_SCHEMA,
    PROJECTS_SCHEMA,
    PLUGINS_SCHEMA,
)
from panoptic.core.databases.panoptic.models import PanopticConfig, User, ProjectKey, PluginKey
from panoptic.core.databases.sqlite_db import SQLiteWriter


class PanopticDB(SQLiteWriter):

    def __init__(self, path: str):
        super().__init__(path, panoptic_db_desc)
        self.config: PanopticConfig = PanopticConfig()
        self.start()
        self._init_config()

    def _init_config(self):
        with self.transaction() as tx:
            PANOPTIC_CONFIG_SCHEMA.ensure_keys(tx)
        self.config = PANOPTIC_CONFIG_SCHEMA.get(self.conn)
        if not self.config.uuid:
            self.config = PanopticConfig(uuid=str(uuid.uuid4()), name=self.config.name, description=self.config.description)
            with self.transaction() as tx:
                PANOPTIC_CONFIG_SCHEMA.set(tx, self.config)
            logging.info(f"Created new Panoptic instance with id: {self.config.uuid}")

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def get_projects(self) -> list[ProjectKey]:
        return PROJECTS_SCHEMA.get(self.conn)

    def add_project(self, uid: str, path: str, name: str = None, excluded_plugins: list[str] = None) -> ProjectKey:
        from pathlib import Path as _Path
        project = ProjectKey(
            uid=uid,
            path=path,
            name=name or _Path(path).name,
            excluded_plugins=excluded_plugins or [],
        )
        with self.transaction() as tx:
            PROJECTS_SCHEMA.upsert(tx, project)
        return project

    def update_project(self, project: ProjectKey) -> ProjectKey:
        with self.transaction() as tx:
            PROJECTS_SCHEMA.upsert(tx, project)
        return project

    def delete_project(self, uid: str) -> None:
        with self.transaction() as tx:
            PROJECTS_SCHEMA.delete(tx, uid=uid)

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
