"""Panoptic configuration: TOML file (--config / PANOPTIC_CONFIG), then env vars, then CLI options."""
from __future__ import annotations

import os
from typing import Literal

import msgspec
import msgspec.toml

DEFAULT_DB = os.path.join('~', '.panoptic', 'panoptic.db')
DEFAULT_PORT = 8000


class ConfigError(Exception):
    pass


class PluginSpec(msgspec.Struct, forbid_unknown_fields=True):
    name: str
    source: str
    type: Literal['pip', 'git', 'path']


class DataPath(msgspec.Struct, forbid_unknown_fields=True):
    path: str
    alias: str | None = None


class PanopticConfig(msgspec.Struct, forbid_unknown_fields=True, kw_only=True):
    db: str = DEFAULT_DB
    port: int = DEFAULT_PORT
    host: str | None = None
    gzip: bool | None = None
    watch_plugins: bool = False
    plugins: list[PluginSpec] = []
    data_paths: list[DataPath] = []


def resolve_db(path: str, base: str | None = None) -> str:
    """A folder means <folder>/panoptic.db."""
    path = os.path.expanduser(path)
    path = os.path.abspath(os.path.join(base, path) if base else path)
    if os.path.isdir(path):
        path = os.path.join(path, 'panoptic.db')
    return path


def _read_file(path: str) -> PanopticConfig:
    try:
        with open(path, 'rb') as f:
            config = msgspec.toml.decode(f.read(), type=PanopticConfig)
    except OSError as e:
        raise ConfigError(f"cannot read config file {path}: {e}") from e
    except (msgspec.ValidationError, msgspec.DecodeError) as e:
        raise ConfigError(f"invalid config file {path}: {e}") from e
    base = os.path.dirname(path)
    config.db = resolve_db(config.db, base)
    for data_path in config.data_paths:
        data_path.path = os.path.realpath(os.path.join(base, os.path.expanduser(data_path.path)))
        data_path.alias = data_path.alias or os.path.basename(data_path.path) or data_path.path
    return config


def _apply_env(config: PanopticConfig, env) -> None:
    if env.get('PANOPTIC_DB'):
        config.db = resolve_db(env['PANOPTIC_DB'])
    if env.get('PANOPTIC_PORT'):
        try:
            config.port = int(env['PANOPTIC_PORT'])
        except ValueError:
            raise ConfigError(f"PANOPTIC_PORT must be an integer, got {env['PANOPTIC_PORT']!r}")
    if env.get('PANOPTIC_HOST'):
        config.host = env['PANOPTIC_HOST']
    if env.get('PANOPTIC_WATCH_PLUGINS'):
        config.watch_plugins = env['PANOPTIC_WATCH_PLUGINS'] == '1'
    if config.gzip is None:
        config.gzip = bool(env.get('PANOPTIC_REMOTE'))


def load_config(path: str | None = None, db: str | None = None, env=None) -> PanopticConfig:
    env = os.environ if env is None else env
    path = path or env.get('PANOPTIC_CONFIG')
    config = _read_file(os.path.abspath(os.path.expanduser(path))) if path else PanopticConfig()
    if not path:
        config.db = resolve_db(config.db)
    _apply_env(config, env)
    if db:
        config.db = resolve_db(db)
    return config


def is_allowed_path(path: str, config: PanopticConfig | None = None) -> bool:
    """Without data_paths everything is allowed; symlinks and '..' are resolved first."""
    config = config or get_config()
    if not config.data_paths:
        return True
    real = os.path.normcase(os.path.realpath(path))
    for data_path in config.data_paths:
        root = os.path.normcase(data_path.path)
        if real == root or real.startswith(root.rstrip(os.sep) + os.sep):
            return True
    return False


_config: PanopticConfig | None = None


def get_config() -> PanopticConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: PanopticConfig | None) -> None:
    global _config
    _config = config
