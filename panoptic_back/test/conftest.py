import os
import shutil
from pathlib import Path

import pytest

from panoptic.core.project.project import Project

EMPTY_DB_PATH = "data/empty.db"
INSTANCE_DB_PATH = "data/instance.db"
DATA_DB_PATH = "data/data.db"


@pytest.fixture
def image_dir(request):
    return str(Path(request.fspath).parent / "data" / "images")


@pytest.fixture
def import_csv(request):
    return str(Path(request.fspath).parent / "data" / "import.csv")


@pytest.fixture
async def empty_project(request, tmp_path):
    base_path = Path(request.fspath).parent / EMPTY_DB_PATH

    project_path = tmp_path / "tmp_project"
    os.makedirs(project_path)
    shutil.copy(base_path, project_path / 'panoptic.db')

    project = Project(str(project_path), [])
    await project.start()
    # Yield the connection object to the test
    yield project

    # Close the connection after the test
    await project.close()

    # Cleanup is handled automatically by pytest when tmp_path is removed


@pytest.fixture
async def instance_project(request, tmp_path):
    base_path = Path(request.fspath).parent / INSTANCE_DB_PATH

    project_path = tmp_path / "tmp_project"
    os.makedirs(project_path)
    shutil.copy(base_path, project_path / 'panoptic.db')

    project = Project(str(project_path), [])
    await project.start()
    # Yield the connection object to the test
    yield project

    # Close the connection after the test
    await project.close()

    # Cleanup is handled automatically by pytest when tmp_path is removed


@pytest.fixture
async def data_project(request, tmp_path):
    base_path = Path(request.fspath).parent / DATA_DB_PATH

    project_path = tmp_path / "tmp_project"
    os.makedirs(project_path)
    shutil.copy(base_path, project_path / 'panoptic.db')

    project = Project(str(project_path), [])
    await project.start()
    # Yield the connection object to the test
    yield project

    # Close the connection after the test
    await project.close()

    # Cleanup is handled automatically by pytest when tmp_path is removed
