import asyncio
import os
import pathlib
import sys
from typing import List, Any, Callable, Awaitable, Dict

from pydantic import BaseModel

from panoptic.models import ParamDescription, Instance


def get_datadir() -> pathlib.Path:
    """
    Returns a parent directory path
    where persistent application data can be stored.

    # linux: ~/.local/share
    # macOS: ~/Library/Application Support
    # windows: C:/Users/<USER>/AppData/Roaming
    # gently taken from https://stackoverflow.com/questions/19078969/python-getting-appdata-folder-in-a-cross-platform-way
    """

    home = pathlib.Path.home()

    if sys.platform == "win32":
        return home / "AppData/Roaming"
    elif sys.platform == "linux":
        return home / ".local/share"
    elif sys.platform == "darwin":
        return home / "Library/Application Support"


def get_base_path():
    if getattr(sys, 'frozen', False):
        # Le programme est exécuté en mode fichier unique
        return sys._MEIPASS
    else:
        # Le programme est exécuté en mode script
        return os.path.dirname(__file__)


AsyncCallable = Callable[[Any, Any, Any], Awaitable[None]]


class EventListener:
    def __init__(self):
        self.callbacks: List[AsyncCallable] = []
        self._tasks = []

    def register(self, callback: AsyncCallable):
        # print('register')
        self.callbacks.append(callback)
        # print(self.callbacks)

    def redirect(self, listener):
        async def redirect(x):
            listener.emit(x)

        self.register(redirect)

    def unregister(self, callback: AsyncCallable):
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def emit(self, event: Any):
        # print(f'callbacks: {self.callbacks}')
        async def async_emit():
            # print(f'async callbacks: {self.callbacks}')
            # print(f'execute {len(self.callbacks)} callbacks')
            for callback in self.callbacks:
                await callback(event)

        task = asyncio.create_task(async_emit())
        self._tasks.append(task)
        task.add_done_callback(self._tasks.remove)


def to_str_type(type_):
    if type_ is int:
        return 'int'
    if type_ is float:
        return 'float'
    if type_ is str:
        return 'str'
    if type_ is List[str]:
        return '[str]'
    if type_ is bool:
        return 'bool'
    if type_ is pathlib.Path:
        return 'path'
    return None


def get_param_comment_from_model(model: BaseModel, param_name: str):
    doc: str = model.__doc__
    token = f'@{param_name}: '
    if not doc or token not in doc:
        return None

    token_start = doc.index(token)
    start = token_start + len(token)
    if '@' in doc[start:]:
        end = doc.index('@', start)
        return doc[start:end]
    return doc[start:]


def get_model_params_description(model: BaseModel):
    res: List[ParamDescription] = []
    fields = model.__fields__
    for field_name, field_info in fields.items():
        field_type = field_info.type_
        default_value = field_info.default
        description = get_param_comment_from_model(model, field_name)
        res.append(ParamDescription(name=field_name, description=description, type=to_str_type(field_type),
                                    default_value=default_value))
    return res


def group_by_sha1(instances: List[Instance]):
    res: Dict[str, List[Instance]] = {}
    for i in instances:
        if i.sha1 not in res:
            res[i.sha1] = []
        res[i.sha1].append(i)
    return res
