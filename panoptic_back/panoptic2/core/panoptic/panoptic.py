import hashlib
import shutil
import threading
import uuid
from pathlib import Path
from typing import Optional

from panoptic.core.databases.panoptic.models import PluginKey, ProjectKey, User
from panoptic.core.databases.panoptic.panoptic_db import PanopticDB
from panoptic.core.databases.project.project_db import ProjectDB
from panoptic2.core.panoptic.models import ProjectState
from panoptic2.core.plugin.plugin_installer import (
    SOURCE_GIT, SOURCE_PATH, SOURCE_PIP, PluginInstaller,
)
from panoptic2.core.project.project import Project2


class Panoptic2:
    def __init__(self, db_path: str | Path):
        self.db_path     = Path(db_path)
        self.plugins_dir = self.db_path.parent / 'plugins'

        self.db:         PanopticDB | None       = None
        self._installer: PluginInstaller | None  = None

        self._loaded_projects: dict[str, Project2] = {}
        self._sessions:        dict[str, str]       = {}  # token → user_id
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db         = PanopticDB(str(self.db_path))
        self._installer = PluginInstaller(self.plugins_dir)

    def close(self):
        with self._lock:
            for project in list(self._loaded_projects.values()):
                try:
                    project.close()
                except Exception:
                    pass
            self._loaded_projects.clear()
        if self.db:
            self.db.close()
            self.db = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_):
        self.close()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def get_projects_state(self) -> list[ProjectState]:
        with self._lock:
            loaded = set(self._loaded_projects.keys())
        return [
            ProjectState(
                id=k.id,
                path=k.path,
                name=k.name,
                excluded_plugins=k.excluded_plugins,
                loaded=k.id in loaded,
            )
            for k in self.db.get_projects()
        ]

    # ------------------------------------------------------------------
    # Project management
    # ------------------------------------------------------------------

    def get_projects(self) -> list[ProjectKey]:
        return self.db.get_projects()

    def create_project(self, name: str, path: str | Path) -> ProjectKey:
        """Create a new empty project folder and register it."""
        p = Path(path)
        if any(k.path == str(p) for k in self.db.get_projects()):
            raise ValueError(f"Path {str(p)!r} is already registered")
        # Project2.start() creates the folder and seeds the DBs
        project = Project2(p)
        project.start()
        id_ = project.config.id
        project.close()
        return self.db.add_project(id_=id_, path=str(p), name=name)

    def import_project(self, path: str | Path) -> ProjectKey:
        """Register an existing project folder that already has a project.db."""
        p = Path(path)
        if not (p / 'project.db').exists():
            raise ValueError(f"{str(p)!r} has no project.db — not a Panoptic project folder")
        if any(k.path == str(p) for k in self.db.get_projects()):
            raise ValueError(f"Path {str(p)!r} is already registered")
        with ProjectDB(p / 'project.db') as db:
            id_ = db.config.id
        return self.db.add_project(id_=id_, path=str(p), name=p.name)

    def load_project(self, id_: str) -> Project2:
        """Start a Project2 instance for the given id and keep it in memory."""
        with self._lock:
            if id_ in self._loaded_projects:
                return self._loaded_projects[id_]

        key = next((k for k in self.db.get_projects() if k.id == id_), None)
        if not key:
            raise ValueError(f"Project {id_!r} is not registered")

        # Integrity check — detect copied/moved project folders
        with ProjectDB(Path(key.path) / 'project.db') as db:
            actual_id = db.config.id
        if actual_id != id_:
            raise ValueError(
                f"ID mismatch: registered as {id_!r} but project.db contains "
                f"{actual_id!r}. Re-import the project to fix the registration."
            )

        all_plugins = self.db.get_plugins()
        project_plugins = [p for p in all_plugins if p.id not in key.excluded_plugins]
        project = Project2(Path(key.path), plugin_keys=project_plugins)
        project.start()

        with self._lock:
            self._loaded_projects[id_] = project
        return project

    def close_project(self, id_: str):
        with self._lock:
            project = self._loaded_projects.pop(id_, None)
        if project:
            project.close()

    def get_project(self, id_: str) -> Optional[Project2]:
        with self._lock:
            return self._loaded_projects.get(id_)

    def delete_project(self, id_: str, delete_files: bool = False):
        self.close_project(id_)
        key = next((k for k in self.db.get_projects() if k.id == id_), None)
        self.db.delete_project(id_)
        if delete_files and key:
            p = Path(key.path)
            if p.exists():
                shutil.rmtree(p)

    def update_project(self, id_: str, name: str = None, excluded_plugins: list[str] = None) -> ProjectKey:
        key = next((k for k in self.db.get_projects() if k.id == id_), None)
        if not key:
            raise ValueError(f"Project {id_!r} is not registered")
        updated = ProjectKey(
            id=key.id,
            path=key.path,
            name=name if name is not None else key.name,
            excluded_plugins=excluded_plugins if excluded_plugins is not None else key.excluded_plugins,
        )
        return self.db.update_project(updated)

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def get_users(self) -> list[User]:
        return self.db.get_users()

    def create_user(self, name: str, description: str = '', password: str = None) -> User:
        if self.get_user_by_name(name):
            raise ValueError(f"User {name!r} already exists")
        return self.db.add_user(
            id_=str(uuid.uuid4()),
            name=name,
            description=description,
            password_hash=_hash_password(password) if password else None,
        )

    def update_user(self, user: User) -> None:
        self.db.update_user(user)

    def delete_user(self, user_id: str) -> None:
        self.db.delete_user(user_id)

    def get_user_by_name(self, name: str) -> Optional[User]:
        return next((u for u in self.db.get_users() if u.name == name), None)

    # ------------------------------------------------------------------
    # Session management  (in-memory, cleared on restart)
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> str:
        user = self.get_user_by_name(username)
        if not user or not _verify_password(password, user.password_hash or ''):
            raise ValueError("Invalid credentials")
        token = str(uuid.uuid4())
        with self._lock:
            self._sessions[token] = user.id
        return token

    def logout(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(token, None)

    def get_user_from_token(self, token: str) -> Optional[User]:
        with self._lock:
            user_id = self._sessions.get(token)
        if not user_id:
            return None
        return next((u for u in self.db.get_users() if u.id == user_id), None)

    # ------------------------------------------------------------------
    # Plugin management
    # ------------------------------------------------------------------

    def get_plugins(self) -> list[PluginKey]:
        return self.db.get_plugins()

    def add_plugin(self, name: str, source_path: str, source_type: str) -> PluginKey:
        if any(p.id == name for p in self.db.get_plugins()):
            raise ValueError(f"Plugin {name!r} is already registered")

        if source_type == SOURCE_PIP:
            install_path = self._installer.install_from_pip(source_path)
        elif source_type == SOURCE_GIT:
            install_path = self._installer.install_from_git(source_path, name=name)
        elif source_type == SOURCE_PATH:
            install_path = self._installer.install_from_path(source_path)
        else:
            raise ValueError(f"Unknown source_type {source_type!r}")

        return self.db.add_plugin(
            id_=name,
            install_path=install_path,
            source_type=source_type,
            source_path=source_path,
        )

    def reinstall_plugin(self, plugin_id: str) -> None:
        plugin = next((p for p in self.db.get_plugins() if p.id == plugin_id), None)
        if not plugin:
            raise ValueError(f"Plugin {plugin_id!r} is not registered")
        install_path = self._installer.reinstall(plugin)
        self.db.update_plugin(PluginKey(
            id=plugin.id,
            install_path=install_path,
            source_type=plugin.source_type,
            source_path=plugin.source_path,
        ))

    def delete_plugin(self, plugin_id: str) -> None:
        plugin = next((p for p in self.db.get_plugins() if p.id == plugin_id), None)
        if not plugin:
            return
        # Remove DB record first — a crash during filesystem cleanup leaves an
        # orphaned directory, not a broken DB reference.
        self.db.delete_plugin(plugin_id)
        self._installer.uninstall_files(plugin)


# ---------------------------------------------------------------------------
# Password helpers  (sha256 — sufficient for a local-first app)
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _verify_password(password: str, stored_hash: str) -> bool:
    return _hash_password(password) == stored_hash
