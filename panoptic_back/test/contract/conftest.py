"""Fixtures of the API contract suite (see technical_docs/rust_port/API_CONTRACT.md §Harness).

    pytest contract                 compare against golden/  (starts the python backend)
    pytest contract --record        rewrite golden/
    PANOPTIC_CONTRACT_URL=http://127.0.0.1:8123 pytest contract     use an already running server
    PANOPTIC_CONTRACT_CMD='/path/panoptic-server --port {port} --db {db}' pytest contract
"""
from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from contract_harness import (
    Api, Golden, Normalizer, ServerProcess, SocketRecorder, make_fixture_images,
)

GOLDEN_DIR = Path(__file__).parent / 'golden'
CONNECTION_ID = 'contract-connection-1'


def pytest_configure(config):
    config.addinivalue_line('markers', 'contract: API contract suite (starts a backend server)')


def pytest_addoption(parser):
    parser.addoption('--record', action='store_true', default=False,
                     help='contract suite: write golden files instead of comparing')
    parser.addoption('--keep-tmp', action='store_true', default=False,
                     help='contract suite: keep the temp dir (server log, db, images)')


@pytest.fixture(autouse=True)
def isolated_config():
    """Override test/conftest.py's fixture: this suite never imports panoptic in-process."""
    yield


@dataclass
class Ctx:
    """Shared state of the ordered scenario (tests run in file order and build on each other)."""
    tmp: Path
    images: Path
    fixture: dict
    url: str
    api: Api
    sock: SocketRecorder
    norm: Normalizer
    golden: Golden
    server: ServerProcess | None = None
    project_path: Path | None = None
    data: dict = field(default_factory=dict)


@pytest.fixture(scope='session')
def ctx(request):
    record = request.config.getoption('--record', default=False) or os.environ.get('PANOPTIC_CONTRACT_RECORD') == '1'
    keep = request.config.getoption('--keep-tmp', default=False)
    tmp = Path(tempfile.mkdtemp(prefix='panoptic_contract_'))
    images = tmp / 'images'
    fixture = make_fixture_images(images)

    server = None
    url = os.environ.get('PANOPTIC_CONTRACT_URL')
    if not url:
        server = ServerProcess(tmp)
        server.start()
        url = server.url

    norm = Normalizer()
    norm.add_path(tmp, '<TMP>')
    norm.add_path(images, '<IMAGES>')
    norm.add_path(tmp / 'projects' / 'contract', '<PROJECT>')
    if server:
        norm.add_path(server.db.parent, '<PANOPTIC_HOME>')
        norm.add_path(server.home, '<HOME>')
    norm.set_sha1s(fixture['sha1_to_paths'])
    norm.register(CONNECTION_ID, '<CONNECTION_ID>')

    api = Api(url, CONNECTION_ID)
    sock = SocketRecorder(url, CONNECTION_ID)
    c = Ctx(tmp=tmp, images=images, fixture=fixture, url=url, api=api, sock=sock, norm=norm,
            golden=Golden(GOLDEN_DIR, record), server=server)
    try:
        yield c
    finally:
        sock.disconnect()
        api.close()
        if server:
            server.stop()
            if request.session.testsfailed:
                print(f'\n--- contract server log tail ({server.log_path}) ---\n{server.log_tail(40)}')
        if keep:
            print(f'\ncontract temp dir kept: {tmp}')
        else:
            shutil.rmtree(tmp, ignore_errors=True)
