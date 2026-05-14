import uuid
from pathlib import Path
from panoptic.core.databases.panoptic.panoptic_db import PanopticDB
from panoptic.core.databases.panoptic.models import User, ProjectKey, PluginKey


def _setup():
    db_path = Path("~/tmp/panoptic.db").expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        db_path.unlink()

    db = PanopticDB(str(db_path))
    return db


def test_cycle_projects():
    db = _setup()
    path = "/home/user/project_alpha"
    uid = "abcdefgh"

    # CREATE
    project = db.add_project(uid=uid, path=path, excluded_plugins=["plugin_v1"])
    projects = db.get_projects()
    assert len(projects) == 1
    assert projects[0].path == path
    assert "plugin_v1" in projects[0].excluded_plugins

    # UPDATE (via upsert in add_project)
    project = projects[0]
    project.excluded_plugins = ["plugin_v2"]
    db.update_project(project)
    projects = db.get_projects()
    assert len(projects) == 1
    assert "plugin_v2" in projects[0].excluded_plugins
    assert "plugin_v1" not in projects[0].excluded_plugins

    # DELETE
    db.delete_project(path)
    projects = db.get_projects()
    assert len(projects) == 0


def test_cycle_users():
    db = _setup()
    uid = str(uuid.uuid4())

    # CREATE
    user = db.add_user(
        uid=uid,
        name="Alice",
        description="Admin User",
        password_hash="hash123"
    )
    users = db.get_users()
    assert len(users) == 1
    assert users[0].name == "Alice"
    assert users[0].uuid == uid

    # UPDATE
    user.name = "Alice Updated"
    user.description = "Superuser"
    db.update_user(user)

    users = db.get_users()
    assert users[0].name == "Alice Updated"
    assert users[0].description == "Superuser"

    # DELETE
    db.delete_user(uid)
    users = db.get_users()
    assert len(users) == 0


def test_cycle_plugins():
    db = _setup()
    plugin_id = "org.panoptic.vision"

    # CREATE
    plugin = db.add_plugin(
        id_=plugin_id,
        install_path="/opt/plugins/vision",
        source_type="git",
        source_path="https://github.com/org/vision.git"
    )
    plugins = db.get_plugins()
    assert len(plugins) == 1
    assert plugins[0].id == plugin_id
    assert plugins[0].source_type == "git"

    # UPDATE
    plugin.source_type = "local"
    plugin.source_path = "/usr/local/src/vision"
    db.update_plugin(plugin)

    plugins = db.get_plugins()
    assert plugins[0].source_type == "local"
    assert plugins[0].source_path == "/usr/local/src/vision"

    # DELETE
    db.delete_plugin(plugin_id)
    plugins = db.get_plugins()
    assert len(plugins) == 0


def test_multiple_entities():
    """Ensure that adding different types of entities doesn't interfere with each other."""
    db = _setup()
    puid = 'abcdefgh'
    db.add_user(str(uuid.uuid4()), "Bob", "User")
    db.add_project(puid, "/tmp/p1")
    db.add_plugin("p.id", "/path", "type", "src")

    assert len(db.get_users()) == 1
    assert len(db.get_projects()) == 1
    assert len(db.get_plugins()) == 1