import asyncio
import json
import subprocess
from pathlib import Path

import pytest

from panoptic_plugin.testing import add_images, create_project

ROOT = Path(__file__).resolve().parents[2]
REF_PYTHON = ROOT / 'panoptic_back' / '.venv' / 'bin' / 'python'
REF_HELPER = Path(__file__).with_name('ref_helper.py')

IMAGES = [
    ('/data/a', 'a1.jpg', 'sha_a1'),
    ('/data/a', 'a2.jpg', 'sha_a2'),
    ('/data/a', 'dup.jpg', 'sha_dup'),
    ('/data/b', 'b1.jpg', 'sha_b1'),
    ('/data/b', 'dup.jpg', 'sha_dup'),
]


def arun(coro, timeout: float = 60):
    return asyncio.run(asyncio.wait_for(coro, timeout))


@pytest.fixture
def project(tmp_path):
    path = create_project(tmp_path / 'proj')
    add_images(path, IMAGES)
    return path


def ref_available() -> bool:
    return REF_PYTHON.exists()


def run_ref(*args) -> str:
    res = subprocess.run([str(REF_PYTHON), str(REF_HELPER), *map(str, args)],
                         cwd=str(ROOT / 'panoptic_back'), capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        raise RuntimeError(f'reference helper failed:\n{res.stdout}\n{res.stderr}')
    return res.stdout.strip().splitlines()[-1]


@pytest.fixture
def ref_project(tmp_path):
    """A project created by the python reference backend (system properties included)."""
    if not ref_available():
        pytest.skip('python reference env (panoptic_back/.venv) not available')
    path = tmp_path / 'ref'
    images = tmp_path / 'images.json'
    images.write_text(json.dumps(IMAGES))
    run_ref('create', path, images)
    return path
