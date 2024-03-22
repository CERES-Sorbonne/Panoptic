from typing import Callable, Awaitable

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
