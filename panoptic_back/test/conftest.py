import pytest

from panoptic import config


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Tests never read the user's ~/.panoptic/panoptic_config.toml nor share a loaded config."""
    monkeypatch.setattr(config, 'DEFAULT_CONFIG', str(tmp_path / 'no_default' / 'panoptic_config.toml'))
    monkeypatch.delenv('PANOPTIC_CONFIG', raising=False)
    config.set_config(None)
    yield
    config.set_config(None)
