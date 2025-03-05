import asyncio
import os
import pathlib
import sys
from enum import Enum
from queue import Queue
from typing import List, Any, Callable, Awaitable, Dict, TypeVar, Tuple

from pydantic import BaseModel

from panoptic.dateformat import parse_date
from panoptic.models import ParamDescription, Instance, ImageProperty, InstanceProperty, Property, \
    PropertyType, PropertyId, Tag, Folder, ActionContext
from panoptic.models.computed_properties import ComputedId


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
    if os.getenv('PANOPTIC_DATA_DIR', ""):
        path = pathlib.Path(os.getenv('PANOPTIC_DATA_DIR')) / "panoptic_data"
        path.mkdir(parents=True, exist_ok=True)
        return path
    elif os.getenv('IS_DOCKER', False):
        return pathlib.Path('/data')
    elif sys.platform == "win32":
        return home / "AppData/Roaming"
    elif sys.platform == "linux":
        return home / ".local/share"
    elif sys.platform == "darwin":
        return home / "Library/Application Support"


def get_base_path():
    if getattr(sys, 'frozen', False):
        # if using pyinstaller file
        return sys._MEIPASS
    else:
        # if using script
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
    if type_ is bool:
        return 'bool'
    if type_ is pathlib.Path:
        return 'path'
    if type_ is PropertyId:
        return 'property'
    if type_ is ActionContext:
        return 'context'
    if issubclass(type_, Enum):
        return 'enum'
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
        field_type = field_info.annotation
        default_value = field_info.default
        description = get_param_comment_from_model(model, field_name)

        param_desc = ParamDescription(
            name=field_name,
            description=description,
            type=to_str_type(field_type),
            default_value=default_value)

        if param_desc.type == 'enum':
            param_desc.possible_values = [e for e in field_type]

        res.append(param_desc)
    return res


def group_by_sha1(instances: List[Instance]):
    res: Dict[str, List[Instance]] = {}
    for i in instances:
        if i.sha1 not in res:
            res[i.sha1] = []
        res[i.sha1].append(i)
    return res


def convert_to_instance_values(values: list[ImageProperty], instances: list[Instance]) \
        -> list[InstanceProperty]:
    sha1_to_instances = {i.sha1: [] for i in instances}
    [sha1_to_instances[i.sha1].append(i) for i in instances]

    def converter2(value: ImageProperty):
        targets = sha1_to_instances[value.sha1]
        return [InstanceProperty(instance_id=i.id, property_id=value.property_id, value=value.value) for i in
                targets]

    pre_res = [converter2(v) for v in values]
    return [v for vv in pre_res for v in vv]


def clean_value(prop: Property, v: Any):
    if prop.type == PropertyType.date and v:
        return parse_date(v)

    if v is False:
        return None
    # avoid setting to None
    if v == 0 or v == '0':
        return 0

    if not v:
        return None

    return v


def get_computed_values(instance: Instance):
    res = [InstanceProperty(instance_id=instance.id, property_id=-1, value=instance.id),
           InstanceProperty(instance_id=instance.id, property_id=-2, value=instance.sha1),
           InstanceProperty(instance_id=instance.id, property_id=-3, value=instance.ahash),
           InstanceProperty(instance_id=instance.id, property_id=-4, value=instance.folder_id),
           InstanceProperty(instance_id=instance.id, property_id=-5, value=instance.width),
           InstanceProperty(instance_id=instance.id, property_id=-6, value=instance.height),
           InstanceProperty(instance_id=instance.id, property_id=-7, value=instance.url)]
    return res


def all_equal(l: list):
    if len(l) == 1:
        return True
    for i in range(len(l) - 1):
        if l[i] != l[i + 1]:
            return False
    return True


def is_circular(tree: dict[int, set[int]], link: tuple[int, int]):
    tree[0] = {0}
    child, parent = link
    visited = set()
    queue = Queue()
    queue.put(parent)
    while not queue.empty():
        tag = queue.get()
        visited.add(tag)
        if tag == child:
            return True
        to_visit = [t for t in tree[tag] if t not in visited]
        [queue.put(t) for t in to_visit]
    return False


class Node:
    def __init__(self):
        self.children = {}  # A dictionary to store children nodes indexed by characters
        self.is_end_of_word = False  # Marks the end of a word (suffix)
        self.ids = []


class Trie:
    def __init__(self):
        self.root = Node()

    def insert(self, word, id_):
        node = self.root
        for char in word:
            if char not in node.children:
                node.children[char] = Node()
            node = node.children[char]
        node.is_end_of_word = True  # Marking the end of a suffix (string)
        node.ids.append(id_)

    def search_by_prefix(self, prefix):
        node = self.root
        for char in prefix:
            if char not in node.children:
                return []  # No words with the given prefix exist
            node = node.children[char]

        suffixes = []
        self._find_suffixes(node, suffixes)
        return suffixes

    def search_by_word(self, word):
        node = self.root
        for char in word:
            if char not in node.children:
                return []  # No words with the given prefix exist
            node = node.children[char]
        res = node.ids
        return res

    def _find_suffixes(self, node, suffixes):
        if node.is_end_of_word:
            suffixes.extend(node.ids)  # Assuming prefix is constructed from the path traversed so far

        for char, child in node.children.items():
            self._find_suffixes(child, suffixes)


class RelativePathTrie(Trie):
    def insert_paths(self, instances: list[Instance]):
        for inst in instances:
            path = inst.url
            if not path.startswith('/'):
                path = '/' + path
            path = path.replace('\\', '/')
            inverse = path[::-1]
            self.insert(inverse, inst.id)

    def search_relative_path(self, path):
        if not path.startswith('/'):
            path = '/' + path
        path = path.replace('\\', '/')
        inverse = path[::-1]
        res = self.search_by_prefix(inverse)
        return res

    def search_absolute_path(self, path):
        if not path.startswith('/'):
            path = '/' + path
        path = path.replace('\\', '/')
        inverse = path[::-1]
        res = self.search_by_word(inverse)
        return res


def chunk_list(input_list, n):
    """Split a list into chunks of a given size."""
    # Use a list comprehension to create chunks
    return [input_list[i:i + n] for i in range(0, len(input_list), n)]


def get_all_parent(tag: Tag, index: dict[int, Tag]) -> set[int]:
    res = set(tag.parents)
    for p in tag.parents:
        if p == 0:
            continue
        [res.add(pId) for pId in get_all_parent(index[p], index)]
    return res


def clean_and_separate_values(values, index: dict[int, Property]):
    valid = []
    empty = []
    for v in values:
        v.value = clean_value(index[v.property_id], v.value)
        if v.value is None:
            empty.append(v)
        else:
            valid.append(v)
    return valid, empty


def get_local_paths(index: dict[int, Folder], folders: list[Folder]):
    paths = {}
    for folder in folders:
        path = folder.name
        parent_id = folder.parent
        while parent_id is not None:
            parent = index[parent_id]
            path = parent.name + '/' + path
            parent_id = parent.parent
        paths[folder.id] = path
    return paths


T = TypeVar('T')


def separate_ids(objs: List[T]) -> Tuple[List[T], List[T]]:
    valid = [o for o in objs if o.id >= 0]
    new = [o for o in objs if o.id < 0]
    return new, valid
