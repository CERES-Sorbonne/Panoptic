import asyncio
import os
import pathlib
import sys
from typing import List, Any, Callable, Awaitable


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


AsyncCallable = Callable[[Any], Awaitable[None]]


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
