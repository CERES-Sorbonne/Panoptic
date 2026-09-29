import os

import pytest
from click.testing import CliRunner

from panoptic.cli import cli


@pytest.fixture(autouse=True)
def restore_db_env(monkeypatch):
    # --db writes PANOPTIC_DB: keep it from leaking into the other tests
    monkeypatch.delenv('PANOPTIC_DB', raising=False)


def test_db_option_opens_given_file(tmp_path):
    db = tmp_path / 'sub' / 'mine.db'
    result = CliRunner().invoke(cli, ['--db', str(db), '--dry'])
    assert result.exit_code == 0, result.output
    assert db.exists()
    assert os.environ['PANOPTIC_DB'] == str(db)


def test_db_option_folder_means_panoptic_db_inside(tmp_path):
    result = CliRunner().invoke(cli, ['--db', str(tmp_path), '--dry'])
    assert result.exit_code == 0, result.output
    assert (tmp_path / 'panoptic.db').exists()


def test_db_option_applies_to_subcommands(tmp_path):
    db = tmp_path / 'plugins.db'
    result = CliRunner().invoke(cli, ['--db', str(db), 'plugins', 'list'])
    assert result.exit_code == 0, result.output
    assert db.exists()
