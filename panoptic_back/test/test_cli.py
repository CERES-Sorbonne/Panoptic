import os

import pytest
from click.testing import CliRunner

from panoptic.cli import cli
from panoptic.config import get_config


@pytest.fixture(autouse=True)
def restore_db_env(monkeypatch):
    # the CLI writes PANOPTIC_DB: keep it from leaking into the other tests
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


def test_config_option_sets_db_and_db_option_wins(tmp_path):
    config = tmp_path / 'panoptic.toml'
    config.write_text('db = "from_file.db"\nport = 9123\n')
    result = CliRunner().invoke(cli, ['--config', str(config), '--dry'])
    assert result.exit_code == 0, result.output
    assert (tmp_path / 'from_file.db').exists()
    assert get_config().port == 9123

    other = tmp_path / 'cli.db'
    result = CliRunner().invoke(cli, ['--config', str(config), '--db', str(other), '--dry'])
    assert result.exit_code == 0, result.output
    assert other.exists()


def test_invalid_config_is_a_clean_error(tmp_path):
    config = tmp_path / 'panoptic.toml'
    config.write_text('prot = 8000\n')
    result = CliRunner().invoke(cli, ['--config', str(config), '--dry'])
    assert result.exit_code != 0
    assert 'unknown field `prot`' in result.output
