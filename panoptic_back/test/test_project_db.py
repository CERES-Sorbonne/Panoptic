from pathlib import Path

from panoptic.core.databases.media.models import ImageType
from panoptic.core.databases.project.models import TabData, UserDefaults
from panoptic.core.databases.project.project_db import ProjectDB
from panoptic.models import Tag
from panoptic.models.data import File

project_db_path = Path("~/tmp/project.db").expanduser()


def _setup():
    db_path = project_db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        db_path.unlink()

    db = ProjectDB(str(db_path))
    db.start()
    return db


def test_file_allocation_with_tracking():
    """Ensures File objects are allocated correctly with their tracking fields."""
    db = _setup()

    # File(id, name, folder_id, sha1, commit_id, operation)
    files = [
        File(id=-1, name="photo.jpg", folder_id=10, sha1="abc", commit_id=1, operation=1),
        File(id=-1, name="data.txt", folder_id=10, sha1="def", commit_id=1, operation=1)
    ]

    db.allocate_files(files)

    # IdRegistry starts at 1
    assert files[0].id == 1
    assert files[1].id == 2
    assert files[0].name == "photo.jpg"
    assert files[1].sha1 == "def"


def test_image_type_allocation():
    db = _setup()

    i_types = [
        ImageType(id=-1, name='thumbnail', format='jpeg', width=128,  height=128),
        ImageType(id=-1, name='preview',   format='webp', width=1024, height=None),
    ]

    db.allocate_image_types(i_types)

    assert i_types[0].id == 1
    assert i_types[1].id == 2
    assert i_types[0].name == 'thumbnail'
    assert i_types[1].height is None


def test_cycle_tab_data_complex():
    """Verifies TabData can handle complex Any types in state/selection."""
    db = _setup()
    tab_id = "main_view"

    state_data = {
        "layers": ["base", "overlay"],
        "viewport": {"x": 100, "y": 200, "scale": 1.5}
    }
    selection_data = [101, 102, 105]

    tab = TabData(id=tab_id, user_id="user_1", state=state_data, selection=selection_data)
    db.set_tab_data(tab)

    retrieved = db.get_tab_data(tab_id)
    assert retrieved.state["viewport"]["scale"] == 1.5
    assert 105 in retrieved.selection


def test_registry_increment_persistence():
    """Ensures the registry increments correctly across multiple allocation calls."""
    db = _setup()

    # First batch
    db.allocate_tags([Tag(id=-1, property_id=1, value="A", parents=[], color=1), Tag(id=-1, property_id=1, value="B", parents=[], color=1)])

    # Second batch
    tags_batch_2 = [Tag(id=-1, property_id=1, value="C", parents=[], color=1)]
    db.allocate_tags(tags_batch_2)

    # Starts at 1, so C should be 3
    assert tags_batch_2[0].id == 3


def test_new_db_has_uuid():
    """Verifies that a newly created ProjectDB has a non-empty UUID in its config."""
    db = _setup()

    assert db.config.id is not None
    assert len(db.config.id) > 0

def test_uuid_persists_across_restart():
    """Verifies that reopening an existing DB yields the same UUID."""
    db = _setup()
    original_id = db.config.id
    db.close()

    db2 = ProjectDB(str(project_db_path))
    db2.start()

    assert db2.config.id == original_id


def test_user_defaults_and_plugin_data_isolation():
    """Checks compound primary key logic for UserDefaults and PluginData."""
    db = _setup()
    uid = "user_1"

    # Two different keys for the same user
    db.set_user_defaults(UserDefaults(user_id=uid, key="theme", data="dark"))
    db.set_user_defaults(UserDefaults(user_id=uid, key="font", data="inter"))

    assert db.get_user_defaults(uid, "theme").data == "dark"

    # Update one key
    db.set_user_defaults(UserDefaults(user_id=uid, key="theme", data="light"))
    assert db.get_user_defaults(uid, "theme").data == "light"