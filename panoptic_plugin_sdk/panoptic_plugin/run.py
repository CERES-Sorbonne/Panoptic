"""Entry point of a plugin process: ``python -m panoptic_plugin.run`` (or ``panoptic-plugin``).

The backend starts it with the environment described in PLUGIN_PROTOCOL.md (§ Process
lifecycle). The plugin class is found, in order, from:

1. ``--entry`` / ``PANOPTIC_PLUGIN_ENTRY``: ``package.module:Class``, a plugin folder (legacy
   layout: ``__init__.py`` exporting ``plugin_class``) or a ``.py`` file;
2. the ``panoptic.plugins`` entry point named like ``PANOPTIC_PLUGIN_NAME``, or the only entry
   point of that group installed in the venv.

Exit codes: 0 shutdown, 2 handshake refused / bad configuration, 3 backend unreachable or lost,
4 the plugin failed to load.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import importlib.util
import inspect
import logging
import os
import sys
from pathlib import Path

from . import protocol as P
from .plugin import Plugin
from .runtime import PluginRuntime, RpcLogHandler, RuntimeConfig, watch_parent

log = logging.getLogger('panoptic_plugin')


def load_plugin_class(entry: str | None = None, name: str | None = None):
    entry = entry or os.environ.get(P.ENV_ENTRY)
    if entry:
        obj = _load_entry(entry)
    else:
        obj = _from_entry_points(name or os.environ.get(P.ENV_NAME))
    if inspect.ismodule(obj):
        obj = getattr(obj, 'plugin_class', None) or _single_plugin_class(obj)
    if not (inspect.isclass(obj) and issubclass(obj, Plugin)):
        raise TypeError(f"{obj!r} is not a panoptic_plugin.Plugin subclass")
    return obj


def _load_entry(entry: str):
    path = Path(entry)
    if ':' in entry and not path.exists():
        module_name, _, attr = entry.partition(':')
        return getattr(importlib.import_module(module_name), attr)
    if path.is_dir():
        if not (path / '__init__.py').exists():
            raise FileNotFoundError(f"no __init__.py in plugin folder {path}")
        sys.path.insert(0, str(path.resolve().parent))
        return importlib.import_module(path.resolve().name)
    if path.suffix == '.py' and path.exists():
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        spec.loader.exec_module(module)
        return module
    return importlib.import_module(entry)


def _from_entry_points(name: str | None):
    from importlib.metadata import entry_points
    eps = list(entry_points(group=P.ENTRY_POINT_GROUP))
    if not eps:
        raise LookupError(f"no {P.ENTRY_POINT_GROUP!r} entry point installed and no {P.ENV_ENTRY}")
    if name:
        for ep in eps:
            if ep.name == name:
                return ep.load()
    if len(eps) == 1:
        return eps[0].load()
    raise LookupError(f"several {P.ENTRY_POINT_GROUP!r} entry points ({[e.name for e in eps]}); "
                      f"set {P.ENV_ENTRY}")


def _single_plugin_class(module):
    found = [v for v in vars(module).values()
             if inspect.isclass(v) and issubclass(v, Plugin) and v is not Plugin
             and v.__module__.startswith(module.__name__)]
    if len(found) != 1:
        raise LookupError(f"module {module.__name__} must export `plugin_class` (found {len(found)} plugins)")
    return found[0]


def instantiate(cls, name: str | None):
    params = inspect.signature(cls.__init__).parameters
    if 'name' in params:
        return cls(name=name) if name else cls()
    plugin = cls()
    if name:
        plugin.name = name
    return plugin


def setup_logging() -> None:
    level = os.environ.get(P.ENV_LOG_LEVEL, 'INFO').upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO), stream=sys.stderr,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='panoptic-plugin', description='Run a Panoptic plugin process')
    parser.add_argument('--entry', help='module:Class, plugin folder or .py file')
    parser.add_argument('--name', help='plugin name (default: PANOPTIC_PLUGIN_NAME)')
    args = parser.parse_args(argv)
    setup_logging()

    name = args.name or os.environ.get(P.ENV_NAME)
    if name:
        os.environ[P.ENV_NAME] = name
    try:
        config = RuntimeConfig.from_env()
    except SystemExit as e:
        log.error(str(e))
        return 2
    try:
        cls = load_plugin_class(args.entry, name)
        plugin = instantiate(cls, name)
    except Exception:
        log.exception('failed to load the plugin')
        return 4

    runtime = PluginRuntime(plugin, config)
    forward = RpcLogHandler(runtime.bridge, level=logging.WARNING)
    logging.getLogger().addHandler(forward)
    parent = int(os.environ.get(P.ENV_PARENT_PID, '0') or 0)
    watch_parent(parent, lambda: os._exit(3))
    try:
        return asyncio.run(runtime.run())
    except KeyboardInterrupt:
        return 0
    finally:
        logging.getLogger().removeHandler(forward)


if __name__ == '__main__':
    sys.exit(main())
