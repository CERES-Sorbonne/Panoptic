"""Plugin base class.

A plugin subclasses :class:`Plugin`, declares actions (``@action`` or ``self.add_action``) and,
optionally, a pydantic ``Params`` model. The runtime (``panoptic_plugin.run``) instantiates it,
connects to the backend, and calls the hooks:

    __init__()                 register actions; no project access yet
    on_start()                 project opened, params loaded: load models, warm caches
    on_project_open(info)      after on_start, with the project info sent by the backend
    on_import_complete(root_folder_id)
    on_folder_delete(folders)
    on_params_changed(old, new)
    on_stop()                  release resources; tasks were already asked to stop

Sync actions and hooks run in a thread pool (the RPC loop never blocks); ``async def`` actions run
on the event loop.
"""
from __future__ import annotations

import inspect
import logging
import os
from pathlib import Path
from typing import Any, Callable

from . import protocol as P
from .introspect import build_function_description, build_params_description
from .models import Folder, Notif, NotifType, VectorType
from .tasks import TaskRunner

_ACTION_ATTR = '_panoptic_action'


def action(fn: Callable | None = None, *, hooks: list[str] | None = None, name: str | None = None,
           label: str | None = None):
    """Declare a method as an action. Usable bare (``@action``) or with options
    (``@action(hooks=['similar'])``). The first parameter after ``self`` receives the
    :class:`ActionContext`; the others are UI inputs typed with the supported annotations."""
    def mark(f):
        setattr(f, _ACTION_ATTR, {'hooks': list(hooks or []), 'name': name, 'label': label})
        return f
    return mark(fn) if fn is not None else mark


class Plugin:
    #: pydantic model of the plugin settings (shown in the plugin settings panel, persisted
    #: per project by the backend). Can also be set as ``self.params = MyParams()`` in __init__.
    Params: Any = None
    #: version reported in hello (defaults to the distribution version when found)
    version: str | None = None
    #: write data.db directly (commit-log protocol) instead of sending commits to the backend
    direct_data_writes: bool = False

    def __init__(self, name: str | None = None):
        self.name: str = name or os.environ.get(P.ENV_NAME) or type(self).__name__
        self.params: Any = self.Params() if self.Params is not None else None
        self.project = None                       # ProjectData, set before on_start
        self.tasks: TaskRunner = TaskRunner(None, owner=self.name)   # replaced by the runtime
        self.data_path: Path | None = None
        self.vector_types: list[VectorType] = []
        self.log = logging.getLogger(f'panoptic_plugin.{self.name}')
        self._actions: dict[str, tuple[Callable, dict]] = {}
        self._runtime = None
        self._started = False
        for attr in dir(type(self)):
            member = getattr(type(self), attr, None)
            meta = getattr(member, _ACTION_ATTR, None)
            if meta is not None:
                self.add_action(getattr(self, attr), hooks=meta['hooks'], name=meta['name'], label=meta['label'])

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------

    def add_action(self, fn: Callable, hooks: list[str] | None = None, name: str | None = None,
                   label: str | None = None, description: dict | None = None) -> dict:
        """Register ``fn`` as an action; returns its FunctionDescription (dict).

        The id is ``<plugin name>.<function name>``. Parameter descriptions come from the
        docstring (``@param: text``). ``description`` overrides the introspected description.
        """
        desc = description or build_function_description(self.name, fn, hooks, name=name, label=label)
        self._actions[desc['name']] = (fn, desc)
        if self._runtime is not None:
            self._runtime.actions_changed()
        return desc

    # name used by the in-process API
    add_action_easy = add_action

    def remove_action(self, name: str) -> None:
        self._actions.pop(name, None)
        if self._runtime is not None:
            self._runtime.actions_changed()

    def action_descriptions(self) -> list[dict]:
        return [desc for _, desc in self._actions.values()]

    def find_action(self, action_id: str) -> tuple[Callable, dict] | None:
        name = action_id.split('.', 1)[1] if action_id.startswith(self.name + '.') else action_id
        return self._actions.get(name)

    # ------------------------------------------------------------------
    # params
    # ------------------------------------------------------------------

    def params_description(self) -> dict:
        model = type(self.params) if self.params is not None else self.Params
        return build_params_description(model, self.params)

    def params_dict(self) -> dict:
        return self.params.model_dump(mode='json') if self.params is not None else {}

    def _load_params(self, stored: dict | None) -> None:
        """Merge stored values into the defaults; invalid stored values are dropped (reference
        `APlugin._load_params` ignores a stored dict that does not validate)."""
        if self.params is None or not stored:
            return
        cls = type(self.params)
        try:
            self.params = cls.model_validate({**self.params.model_dump(), **stored})
        except Exception:
            merged = self.params.model_dump()
            for k, v in stored.items():
                trial = {**merged, k: v}
                try:
                    cls.model_validate(trial)
                    merged = trial
                except Exception:
                    self.log.warning(f'stored param {k!r}={v!r} is invalid, using the default')
            self.params = cls.model_validate(merged)

    def _update_params(self, update: dict) -> None:
        if self.params is None:
            return
        old = self.params
        self.params = type(old).model_validate({**old.model_dump(), **(update or {})})
        self.on_params_changed(old, self.params)

    def save_params(self) -> None:
        """Persist the current params (after the plugin changed them itself)."""
        if self._runtime is not None:
            self._runtime.bridge.call('params.set', {'params': self.params_dict()})

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def notify(self, message: str, type: NotifType = NotifType.INFO, name: str | None = None,
               data: Any = None) -> None:
        """Show a notification in the UI (outside of an action result)."""
        self.notify_many([Notif(type=type, name=name or self.name, message=message, data=data)])

    def notify_many(self, notifs: list[Notif]) -> None:
        if self._runtime is not None:
            self._runtime.bridge.notify('notify', {'notifs': notifs})
        else:
            for n in notifs:
                self.log.info(f'[{n.type.value}] {n.name}: {n.message}')

    def refresh_vector_types(self) -> list[VectorType]:
        """Re-read this plugin's vector types (they can be deleted from the UI at any time)."""
        if self.project is not None:
            self.vector_types = self.project.get_vector_types(source=self.name)
        return self.vector_types

    def run_in_executor(self, fn: Callable, *args):
        """Kept for porting: actions already run in worker threads, so this calls fn directly."""
        return fn(*args)

    # ------------------------------------------------------------------
    # hooks (override)
    # ------------------------------------------------------------------

    def on_start(self) -> None:
        """Project opened and params loaded (the old ``_start``)."""

    def on_project_open(self, info: dict) -> None:
        """Called after on_start with the project info of ``project.open``."""

    def on_import_complete(self, root_folder_id: int | None) -> None:
        """An import finished. ``None`` means everything may be new."""

    def on_folder_delete(self, folders: list[Folder]) -> None:
        """Folders (and their files / instances) were deleted."""

    def on_params_changed(self, old: Any, new: Any) -> None:
        """Params were changed from the UI."""

    def on_stop(self) -> None:
        """The plugin is stopping (the old ``_stop``)."""

    # ------------------------------------------------------------------
    # description (hello)
    # ------------------------------------------------------------------

    def describe(self) -> dict:
        return {
            'name': self.name,
            'version': self.version or _dist_version(type(self)),
            'description': inspect.cleandoc(type(self).__doc__) if type(self).__doc__ else None,
            'path': os.environ.get(P.ENV_SOURCE_PATH) or _source_path(type(self)),
        }


def _dist_version(cls) -> str | None:
    try:
        from importlib import metadata
        top = cls.__module__.split('.')[0]
        for dist_name in metadata.packages_distributions().get(top, []):
            return metadata.version(dist_name)
    except Exception:
        pass
    return None


def _source_path(cls) -> str | None:
    try:
        return str(Path(inspect.getfile(cls)).parent)
    except (TypeError, OSError):
        return None
