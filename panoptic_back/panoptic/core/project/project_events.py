import asyncio
from typing import Callable, TypeVar, List, Any, Awaitable

from panoptic.models import Instance
from panoptic.utils import EventListener


class ImportInstanceEvent(EventListener):
    def register(self, callback: Callable[[Instance], Awaitable[None]]):
        super().register(callback)

    def emit(self, event: Instance):
        super().emit(event)


class ProjectEvents:
    def __init__(self):
        self.import_instance = ImportInstanceEvent()


async def launch():
    pass


asyncio.run(launch())
