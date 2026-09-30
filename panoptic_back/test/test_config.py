import os

import pytest
from fastapi import HTTPException

from panoptic import config as config_module
from panoptic.config import ConfigError, DataPath, PanopticConfig, is_allowed_path, load_config, set_config
from panoptic.routes import panoptic_routes


def write(path, text):
    path.write_text(text)
    return str(path)


def test_defaults_without_file():
    config = load_config(env={})
    assert config.db == os.path.expanduser('~/.panoptic/panoptic.db')
    assert config.port == 8000
    assert config.gzip is False
    assert not config.watch_plugins
    assert config.data_paths == []


def test_file_paths_are_relative_to_the_file(tmp_path):
    (tmp_path / 'images').mkdir()
    path = write(tmp_path / 'c.toml', '''
db = "base"
data_paths = [{ path = "images", alias = "pics" }, { path = "images" }]
''')
    config = load_config(path, env={})
    assert config.db == str(tmp_path / 'base')
    assert [(d.path, d.alias) for d in config.data_paths] == [
        (str(tmp_path / 'images'), 'pics'), (str(tmp_path / 'images'), 'images')]


def test_db_folder_means_panoptic_db_inside(tmp_path):
    path = write(tmp_path / 'c.toml', f'db = "{tmp_path}"')
    assert load_config(path, env={}).db == str(tmp_path / 'panoptic.db')


def test_precedence_cli_over_env_over_file(tmp_path):
    path = write(tmp_path / 'c.toml', 'db = "file.db"\nport = 1\nwatch_plugins = true\n')
    env = {'PANOPTIC_PORT': '2', 'PANOPTIC_DB': str(tmp_path / 'env.db'), 'PANOPTIC_WATCH_PLUGINS': '0'}
    config = load_config(path, env=env)
    assert config.port == 2
    assert config.db == str(tmp_path / 'env.db')
    assert not config.watch_plugins
    assert load_config(path, db=str(tmp_path / 'cli.db'), env=env).db == str(tmp_path / 'cli.db')


def test_config_path_from_env(tmp_path):
    path = write(tmp_path / 'c.toml', 'port = 4242')
    assert load_config(env={'PANOPTIC_CONFIG': path}).port == 4242


def test_default_config_file_used_only_as_last_resort(tmp_path, monkeypatch):
    default = write(tmp_path / 'panoptic_config.toml', 'port = 1111\ndb = "main"')
    monkeypatch.setattr(config_module, 'DEFAULT_CONFIG', default)
    config = load_config(env={})
    assert config.port == 1111
    assert config.db == str(tmp_path / 'main')
    other = write(tmp_path / 'other.toml', 'port = 2222')
    assert load_config(env={'PANOPTIC_CONFIG': other}).port == 2222
    assert load_config(other, env={}).port == 2222


def test_gzip_defaults_to_remote_mode_unless_set(tmp_path):
    assert load_config(env={'PANOPTIC_REMOTE': '1'}).gzip is True
    path = write(tmp_path / 'c.toml', 'gzip = false')
    assert load_config(path, env={'PANOPTIC_REMOTE': '1'}).gzip is False


@pytest.mark.parametrize('content, message', [
    ('prot = 1', 'unknown field `prot`'),
    ('port = "x"', 'Expected `int`'),
    ('plugins = [{ name = "a", source = "b", type = "pip" }]', 'unknown field `plugins`'),
    ('port =', 'invalid config file'),
])
def test_invalid_file(tmp_path, content, message):
    path = write(tmp_path / 'c.toml', content)
    with pytest.raises(ConfigError, match=message):
        load_config(path, env={})


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match='cannot read'):
        load_config(str(tmp_path / 'nope.toml'), env={})


@pytest.fixture
def data_root(tmp_path):
    root = tmp_path / 'data'
    (root / 'sub').mkdir(parents=True)
    (root / 'sub' / 'a.png').write_bytes(b'png')
    (tmp_path / 'secret').mkdir()
    (tmp_path / 'secret' / 'b.png').write_bytes(b'png')
    (root / 'escape').symlink_to(tmp_path / 'secret')
    set_config(PanopticConfig(data_paths=[DataPath(str(root), 'images')]))
    return root


def test_allowed_paths(data_root):
    assert is_allowed_path(str(data_root))
    assert is_allowed_path(str(data_root / 'sub' / 'a.png'))
    assert not is_allowed_path(str(data_root.parent / 'secret'))
    assert not is_allowed_path(str(data_root / '..' / 'secret'))
    assert not is_allowed_path(str(data_root / 'escape' / 'b.png'))
    assert not is_allowed_path(str(data_root) + '-other')


def test_everything_allowed_without_data_paths(tmp_path):
    set_config(PanopticConfig())
    assert is_allowed_path('/')


def test_filesystem_routes_restricted(data_root):
    info = panoptic_routes.filesystem_info()
    assert info == {'partitions': [], 'restricted': True,
                    'fast': [{'path': str(data_root), 'name': 'images', 'images': 0}]}
    assert [d['name'] for d in panoptic_routes.filesystem_ls(str(data_root))['directories']] == ['escape', 'sub']
    assert panoptic_routes.filesystem_count(str(data_root / 'sub'))['count'] == 1

    outside = str(data_root.parent / 'secret')
    for call in (panoptic_routes.filesystem_ls, panoptic_routes.filesystem_count, panoptic_routes.get_image_file):
        with pytest.raises(HTTPException) as e:
            call(outside)
        assert e.value.status_code == 403
    with pytest.raises(HTTPException):
        panoptic_routes.get_image_file(str(data_root / 'escape' / 'b.png'))
