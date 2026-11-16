"""PluginProjectInterface — self-contained project API for plugin authors.

Holds DB paths directly and opens its own connections per call.
No reference to Project is kept — plugins cannot reach internal project
state through this interface. Only the public methods are plugin API: the DB
connections are private (name-mangled). `_media_db` / `_project_db` remain as
deprecated aliases until the plugins that still call them are ported.

Plugins import everything they need from `panoptic.plugin`.
"""
from __future__ import annotations

import threading
from pathlib import Path
from random import randint
from typing import TYPE_CHECKING, Any, Callable, Iterable, List, Mapping

from panoptic.core.databases.data.data_reader import DataReader
from panoptic.core.databases.data.data_writer import DataWriter
from panoptic.core.databases.media.create import datastore_desc
from panoptic.core.databases.media.media_db import MediaDB
from panoptic.core.databases.media.models import ImageType, Map, Vector, VectorType
from panoptic.core.databases.project.models import UserDefaults
from panoptic.core.databases.project.project_db import ProjectDB
from panoptic.core.databases.data.models import (
    Commit, DataCommit, DeleteCommit, File, FileSource, Folder, Instance, InstanceValue,
    Property, PropertyGroup, Sha1Value, Tag, UpsertCommit, FileValue,
)
from panoptic.core.databases.entity_schema import OP_CREATE
from panoptic.core.plugin.action_registry import ActionRegistry, build_function_description
from panoptic.core.task.task import Task
from panoptic.models.action_models import ActionContext, FunctionDescription
from panoptic.models.models import PropertyMode, PropertyType

if TYPE_CHECKING:
    from panoptic.core.task.task_manager import TaskManager

_TAG_DTYPES = {PropertyType.tag.value, PropertyType.multi_tags.value}
# user_defaults keys under user_id 'plugin.<name>'
_OWNED_PROPERTIES = 'properties'      # {plugin key: property id}
_OWNED_GROUPS     = 'property_groups' # {group name: property group id}

# One lock per (project, plugin), shared by every interface built for it: a reloaded
# plugin gets a new interface while the old one's task threads may still be writing.
_locks: dict[tuple[str, str], threading.RLock] = {}
_locks_guard = threading.Lock()


def _plugin_lock(project_db_path: Path, name: str) -> threading.RLock:
    with _locks_guard:
        return _locks.setdefault((str(project_db_path), name), threading.RLock())


def _first_id(allocated) -> int:
    # ProjectDB.allocate_* returns an int for one id, else a range
    return allocated if isinstance(allocated, int) else list(allocated)[0]


class PluginProjectInterface:
    def __init__(
        self,
        plugin_name: str,
        base_path: Path,
        data_db_path: Path,
        media_db_path: Path,
        project_db_path: Path,
        task_manager: TaskManager,
        action_registry: ActionRegistry,
        register_import_complete: Callable,
        register_folder_delete: Callable,
        on_commit: Callable[[], None] | None = None,
        register_vector_type_delete: Callable | None = None,
    ):
        self._name         = plugin_name
        self.base_path     = Path(base_path)
        self._data_path    = Path(data_db_path)
        self._media_path   = Path(media_db_path)
        self._project_path = Path(project_db_path)
        self._tasks        = task_manager
        self._actions      = action_registry
        self._reg_import_complete = register_import_complete
        self._reg_delete   = register_folder_delete
        self._on_commit    = on_commit
        self._reg_vector_type_delete = register_vector_type_delete
        # Serializes this plugin's ensure_* and tag-creating writes across its threads
        self.__lock = _plugin_lock(self._project_path, plugin_name)

    # ------------------------------------------------------------------
    # Private DB helpers — same open/close-per-call pattern as Project
    # ------------------------------------------------------------------

    def __data_reader(self) -> DataReader:
        return DataReader(str(self._data_path))

    def __data_writer(self) -> DataWriter:
        return DataWriter(str(self._data_path))

    def __media_db(self) -> MediaDB:
        return MediaDB(str(self._media_path), datastore_desc)

    def __project_db(self) -> ProjectDB:
        return ProjectDB(self._project_path)

    # Deprecated, not plugin API. Kept only because deepfaune-panoptic-plugin still opens
    # the databases directly; remove once it uses the public methods.
    def _media_db(self) -> MediaDB:
        return self.__media_db()

    def _project_db(self) -> ProjectDB:
        return self.__project_db()

    # ------------------------------------------------------------------
    # Read — data.db
    # ------------------------------------------------------------------

    def get_folders(self, **filters) -> List[Folder]:
        with self.__data_reader() as r:
            return r.get_folders(**filters)

    def get_files(self, **filters) -> List[File]:
        with self.__data_reader() as r:
            return r.get_files(**filters)

    def get_file_sources(self, **filters) -> List[FileSource]:
        with self.__data_reader() as r:
            return r.get_file_sources(**filters)

    def get_instances(self, **filters) -> List[Instance]:
        with self.__data_reader() as r:
            return r.get_instances(**filters)

    def get_properties(self, **filters) -> List[Property]:
        with self.__data_reader() as r:
            return r.get_properties(**filters)

    def get_property_groups(self, **filters) -> List[PropertyGroup]:
        with self.__data_reader() as r:
            return r.get_property_groups(**filters)

    def get_tags(self, **filters) -> List[Tag]:
        with self.__data_reader() as r:
            return r.get_tags(**filters)

    def get_instance_values(self, **filters) -> List[InstanceValue]:
        with self.__data_reader() as r:
            return r.get_instance_values(**filters)

    def get_sha1_values(self, **filters) -> List[Sha1Value]:
        with self.__data_reader() as r:
            return r.get_sha1_values(**filters)

    def get_file_values(self, **filters) -> List[FileValue]:
        with self.__data_reader() as r:
            return r.get_file_values(**filters)

    def instances_of(self, ctx: ActionContext) -> List[Instance]:
        """Instances an action was called on, in selection order. No selection means all."""
        if not ctx.instance_ids:
            return self.get_instances()
        order = {iid: i for i, iid in enumerate(dict.fromkeys(ctx.instance_ids))}
        return sorted(self.get_instances(id=list(order)), key=lambda inst: order[inst.id])

    def sha1s_of(self, ctx: ActionContext) -> List[str]:
        """Unique non-empty sha1s of instances_of(ctx), in first-seen order."""
        return list(dict.fromkeys(i.sha1 for i in self.instances_of(ctx) if i.sha1))

    def get_instances_under_folder(self, folder_id: int | None) -> List[Instance]:
        """Instances of the files in a folder and all its sub-folders. None means all."""
        if folder_id is None:
            return self.get_instances()
        with self.__data_reader() as r:
            children: dict[int, list[int]] = {}
            for f in r.get_folders():
                children.setdefault(f.parent, []).append(f.id)
            folder_ids, frontier = {folder_id}, [folder_id]
            while frontier:
                frontier = [c for f in frontier for c in children.get(f, ()) if c not in folder_ids]
                folder_ids.update(frontier)
            file_ids = [f.id for f in r.get_files(folder_id=list(folder_ids))]
            return r.get_instances(file_id=file_ids) if file_ids else []

    # ------------------------------------------------------------------
    # Write — data.db  (source is always the plugin name)
    # ------------------------------------------------------------------

    def add_property(self, name: str, dtype: str, mode: str = 'sha1',
                     readonly: bool = False, property_group_id: int = None) -> Property:
        """Create a property owned by this plugin and return it with its allocated id.

        readonly=True marks the property non-editable (access='read'): the UI renders it
        read-only and the HTTP routes refuse any write to it. The plugin itself keeps
        writing its values normally — this interface commits straight through DataWriter,
        which is deliberately not guarded.
        """
        with self.__project_db() as pdb:
            new_id = _first_id(pdb.allocate_properties(1))
        prop = Property(
            id=new_id, dtype=dtype, mode=mode, name=name,
            access='read' if readonly else 'write',
            tag_list_id=new_id, property_group_id=property_group_id,
            commit_id=0, operation=OP_CREATE,
        )
        commit = UpsertCommit()
        commit.properties[new_id] = prop
        self.apply_upsert_commit(commit)
        return prop

    def add_property_group(self, name: str) -> PropertyGroup:
        """Create a property group and return it with its allocated id."""
        with self.__project_db() as pdb:
            new_id = _first_id(pdb.allocate_property_groups(1))
        group = PropertyGroup(id=new_id, name=name, commit_id=0, operation=OP_CREATE)
        commit = UpsertCommit()
        commit.property_groups[new_id] = group
        self.apply_upsert_commit(commit)
        return group

    def ensure_property(self, key: str, name: str, dtype: str, *, mode: str = 'sha1',
                        group: str | None = None, readonly: bool = False) -> Property:
        """Return the plugin's property known as `key`, creating it on first use.

        `key` is the plugin's own stable id for the property; the key → id map is kept in
        project.db, so the property is found again after a restart even if the user renamed
        it. A new property is created (in property group `group`, itself created once) when
        the old one was deleted or no longer has this dtype/mode; such an old property is
        left as it is. name, group and readonly only apply on creation. Thread-safe.
        """
        with self.__lock:
            owned = self.__load_owned(_OWNED_PROPERTIES)
            pid = owned.get(key)
            found = self.get_properties(id=pid) if pid is not None else []
            if found and found[0].dtype == dtype and found[0].mode == mode:
                return found[0]
            group_id = self.__ensure_group(group) if group else None
            prop = self.add_property(name, dtype, mode, readonly=readonly,
                                     property_group_id=group_id)
            owned[key] = prop.id
            self.__save_owned(_OWNED_PROPERTIES, owned)
            return prop

    def adopt_property(self, key: str, property_id: int, *, group: str | None = None,
                       group_id: int | None = None) -> Property | None:
        """Record an existing property as the plugin's property `key`, for ensure_property.

        Used to carry over ids a plugin kept on its own. Returns the property, or None (and
        records nothing) if property_id is not alive. A key already mapped to a live property
        keeps its mapping and that property is returned, so calling it again is harmless.
        With group and group_id, the group is recorded too when it is alive and the name is
        not already mapped to a live group. Thread-safe.
        """
        with self.__lock:
            owned = self.__load_owned(_OWNED_PROPERTIES)
            current = self.get_properties(id=owned[key]) if key in owned else []
            if current:
                prop = current[0]
            else:
                found = self.get_properties(id=property_id)
                if not found:
                    return None
                prop = found[0]
                owned[key] = prop.id
                self.__save_owned(_OWNED_PROPERTIES, owned)
            if group is not None and group_id is not None:
                groups = self.__load_owned(_OWNED_GROUPS)
                mapped = groups.get(group)
                if not (mapped is not None and self.get_property_groups(id=mapped)) \
                        and self.get_property_groups(id=group_id):
                    groups[group] = group_id
                    self.__save_owned(_OWNED_GROUPS, groups)
            return prop

    def __ensure_group(self, name: str) -> int:
        owned = self.__load_owned(_OWNED_GROUPS)
        gid = owned.get(name)
        if gid is not None and self.get_property_groups(id=gid):
            return gid
        owned[name] = self.add_property_group(name).id
        self.__save_owned(_OWNED_GROUPS, owned)
        return owned[name]

    def __load_owned(self, key: str) -> dict:
        with self.__project_db() as db:
            row = db.get_user_defaults(user_id=f'plugin.{self._name}', key=key)
        return dict(row.data) if row and row.data else {}

    def __save_owned(self, key: str, data: dict) -> None:
        with self.__project_db() as db:
            db.set_user_defaults(UserDefaults(user_id=f'plugin.{self._name}', key=key, data=data))

    def ensure_tags(self, property_id: int, labels: Iterable[str], *,
                    color: int | Callable[[str], int] | None = None) -> dict[str, int]:
        """Map tag labels to tag ids for a tag / multi_tags property, creating the missing
        ones in one commit. Returns {label: id} for the given labels.

        color: an int, or a function label -> int, in the UI's 0..11 range. Default: random.
        Thread-safe.
        """
        with self.__lock:
            ids, new = self.__tag_ids(self.__tag_property(property_id), labels, color)
            if new:
                self.apply_commit(DataCommit(tags=new))
            return ids

    def __tag_property(self, property_id: int) -> Property:
        found = self.get_properties(id=property_id)
        if not found:
            raise KeyError(f'Property {property_id} does not exist')
        if found[0].dtype not in _TAG_DTYPES:
            raise ValueError(f'Property {property_id} is not a tag property')
        return found[0]

    def __tag_ids(self, prop: Property, labels: Iterable[str],
                  color: int | Callable[[str], int] | None) -> tuple[dict[str, int], list[Tag]]:
        """{label: id} for labels, plus the Tag rows still to commit for the missing ones."""
        wanted = list(dict.fromkeys(labels))
        existing = {t.value: t.id for t in self.get_tags(list_id=prop.tag_list_id)}
        missing = [label for label in wanted if label not in existing]
        new: list[Tag] = []
        if missing:
            with self.__project_db() as pdb:
                first = _first_id(pdb.allocate_tags(len(missing)))
            for tag_id, label in enumerate(missing, start=first):
                c = color(label) if callable(color) else color
                new.append(Tag(id=tag_id, list_id=prop.tag_list_id, parents=[], value=label,
                               color=randint(0, 11) if c is None else c))
                existing[label] = tag_id
        return {label: existing[label] for label in wanted}, new

    def set_sha1_values(self, property_id: int, values: Mapping[str, Any], *,
                        tag_color: int | Callable[[str], int] | None = None) -> Commit | None:
        """Write {sha1: value} for a sha1-mode property in one commit. See set_sha1_values_many."""
        return self.set_sha1_values_many({property_id: values}, tag_color=tag_color)

    def set_instance_values(self, property_id: int, values: Mapping[int, Any], *,
                            tag_color: int | Callable[[str], int] | None = None) -> Commit | None:
        """Write {instance_id: value} for an id-mode property in one commit."""
        return self.set_instance_values_many({property_id: values}, tag_color=tag_color)

    def set_sha1_values_many(self, values: Mapping[int, Mapping[str, Any]], *,
                             tag_color: int | Callable[[str], int] | None = None) -> Commit | None:
        """Write {property_id: {sha1: value}} for sha1-mode properties, all in one commit.

        Values: None clears a cell (as the UI does). A tag / multi_tags property takes a tag
        id, a label, or a list mixing both; unknown labels become new tags (colored by
        tag_color, see ensure_tags) in the same commit; None or [] removes every tag.
        Cells already holding the value are skipped. Returns None when nothing changed.
        """
        return self.__set_values(PropertyMode.sha1.value, values, tag_color)

    def set_instance_values_many(self, values: Mapping[int, Mapping[int, Any]], *,
                                 tag_color: int | Callable[[str], int] | None = None) -> Commit | None:
        """Write {property_id: {instance_id: value}} for id-mode properties, all in one commit.
        Same value rules as set_sha1_values_many."""
        return self.__set_values(PropertyMode.id.value, values, tag_color)

    def __set_values(self, mode: str, values: Mapping[int, Mapping[Any, Any]],
                     color: int | Callable[[str], int] | None) -> Commit | None:
        values = {pid: cells for pid, cells in values.items() if cells}
        if not values:
            return None
        # Held through the commit, so two threads never create the same new label twice
        with self.__lock:
            props = {p.id: p for p in self.get_properties(id=list(values))}
            commit = DataCommit()
            for pid, cells in values.items():
                prop = props.get(pid)
                if prop is None:
                    raise KeyError(f'Property {pid} does not exist')
                if prop.mode != mode:
                    raise ValueError(f'Property {pid} has mode {prop.mode!r}, not {mode!r}')
                if prop.dtype in _TAG_DTYPES:
                    cells = {k: _tag_list(v) for k, v in cells.items()}
                    labels = [t for v in cells.values() for t in v if isinstance(t, str)]
                    if labels:
                        ids, new = self.__tag_ids(prop, labels, color)
                        commit.tags.extend(new)
                        cells = {k: [ids[t] if isinstance(t, str) else t for t in v]
                                 for k, v in cells.items()}
                if mode == PropertyMode.sha1.value:
                    commit.sha1_values.extend(Sha1Value(property_id=pid, sha1=k, value=v)
                                              for k, v in cells.items())
                else:
                    commit.instance_values.extend(InstanceValue(property_id=pid, instance_id=k, value=v)
                                                  for k, v in cells.items())
            return self.apply_commit(commit)

    def apply_commit(self, commit: DataCommit, group_id: int = None) -> Commit | None:
        """Unified create/update/delete for the logged (revertable) entities.

        Returns None when the payload asserts the state the DB already holds: nothing changed,
        so nothing is committed.
        """
        with self.__data_writer() as w:
            result = w.apply_commit(self._name, commit, group_id=group_id)
        self._fire_on_commit()
        return result

    def apply_upsert_commit(self, commit: UpsertCommit, group_id: int = None) -> Commit | None:
        with self.__data_writer() as w:
            result = w.apply_upsert_commit(self._name, commit, group_id=group_id)
        self._fire_on_commit()
        return result

    def apply_delete_commit(self, commit: DeleteCommit, group_id: int = None) -> Commit | None:
        with self.__data_writer() as w:
            result = w.apply_delete_commit(self._name, commit, group_id=group_id)
        self._fire_on_commit()
        return result

    def _fire_on_commit(self) -> None:
        # Writes bypass Project, so clients are told here to fetch the new delta.
        if self._on_commit:
            self._on_commit()

    # ------------------------------------------------------------------
    # Vectors — media.db
    # ------------------------------------------------------------------

    def get_vector_types(self, source: str = None) -> List[VectorType]:
        with self.__media_db() as mdb:
            return mdb.get_vector_types(source=source) if source else mdb.get_vector_types()

    def upsert_vector_type(self, vt: VectorType) -> VectorType:
        """Insert or update a vector type. If vt.id < 0 a new ID is allocated."""
        if vt.id < 0:
            with self.__project_db() as pdb:
                new_id = pdb.allocate_vector_types(1)
            vt = VectorType(id=new_id, source=vt.source, params=vt.params)
        with self.__media_db() as mdb:
            mdb.upsert_vector_type(vt)
        return vt

    def delete_vector_type(self, type_id: int) -> None:
        with self.__media_db() as mdb:
            mdb.delete_vector_type(type_id)

    def get_vectors(self, type_id: int, sha1s: List[str] = None) -> List[Vector]:
        filters = {'type_id': type_id}
        if sha1s is not None:
            filters['sha1'] = sha1s
        with self.__media_db() as mdb:
            return mdb.get_vectors(**filters)

    def upsert_vectors(self, vectors: List[Vector]) -> None:
        with self.__media_db() as mdb:
            mdb.upsert_vectors(vectors)

    def vector_exist(self, type_id: int, sha1: str) -> bool:
        with self.__media_db() as mdb:
            return len(mdb.get_vectors(type_id=type_id, sha1=sha1)) > 0

    def get_vector_sha1s(self, type_id: int) -> set[str]:
        """sha1s that already have a vector of this type."""
        with self.__media_db() as mdb:
            return mdb.get_vector_sha1s(type_id)

    # ------------------------------------------------------------------
    # Stored images — media.db
    # ------------------------------------------------------------------

    def get_image_types(self) -> List[ImageType]:
        with self.__media_db() as mdb:
            return mdb.get_image_types()

    def pick_image_type(self, min_size: int | None = None) -> ImageType | None:
        """The stored rendition to read: the smallest whose longest side is at least
        min_size, else (or with no min_size) the largest. None if there is no image type."""
        types = self.get_image_types()
        sized = [t for t in types if t.width or t.height]
        if not sized:
            return types[0] if types else None
        def side(t: ImageType) -> tuple[int, int]:
            return max(t.width or 0, t.height or 0), t.id
        if min_size is not None:
            big_enough = [t for t in sized if side(t)[0] >= min_size]
            if big_enough:
                return min(big_enough, key=side)
        return max(sized, key=side)

    def get_image_bytes(self, type_id: int, sha1s: List[str]) -> dict[str, bytes]:
        """Stored image bytes of one rendition, {sha1: bytes}. sha1s without one are absent."""
        if not sha1s:
            return {}
        with self.__media_db() as mdb:
            return {img.sha1: img.data for img in mdb.get_images(type_id=type_id, sha1=list(sha1s))}

    # ------------------------------------------------------------------
    # Maps — media.db
    # ------------------------------------------------------------------

    def get_maps(self, **filters) -> List[Map]:
        with self.__media_db() as mdb:
            return mdb.get_maps(**filters)

    def upsert_map(self, map_: Map) -> Map:
        """Insert or update a map. If map_.id < 0 a new ID is allocated."""
        if map_.id < 0:
            with self.__project_db() as pdb:
                new_id = pdb.allocate_maps(1)
            map_ = Map(
                id=new_id, source=map_.source, name=map_.name,
                key=map_.key, count=map_.count, data=map_.data,
            )
        with self.__media_db() as mdb:
            mdb.upsert_map(map_)
        return map_

    def delete_map(self, map_id: int) -> None:
        with self.__media_db() as mdb:
            mdb.delete_map(map_id)

    # ------------------------------------------------------------------
    # Plugin params — project.db  (namespaced to plugin name automatically)
    # ------------------------------------------------------------------

    def load_params(self) -> dict | None:
        with self.__project_db() as db:
            row = db.get_user_defaults(user_id=f'plugin.{self._name}', key='params')
            return row.data if row else None

    def save_params(self, params: dict) -> None:
        with self.__project_db() as db:
            db.set_user_defaults(UserDefaults(
                user_id=f'plugin.{self._name}',
                key='params',
                data=params,
            ))

    # ------------------------------------------------------------------
    # Action registration  (used by APlugin — not called directly)
    # ------------------------------------------------------------------

    def register_action(self, fn: Callable, hooks: list[str] = None) -> FunctionDescription:
        """Build a FunctionDescription and register fn in the project's ActionRegistry."""
        desc = build_function_description(self._name, fn, hooks)
        self._actions.add(fn, desc, owner=self._name)
        return desc

    def register_action_with_desc(self, fn: Callable, description: FunctionDescription) -> None:
        """Register fn with an explicit FunctionDescription."""
        self._actions.add(fn, description, owner=self._name)

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def add_task(self, task: Task, high_priority: bool = False) -> Task:
        """Queue a task. It is stopped when the plugin is stopped."""
        task.owner = self._name
        return self._tasks.add_task(task, high_priority=high_priority)

    # ------------------------------------------------------------------
    # CPU executor
    # ------------------------------------------------------------------

    def run_in_executor(self, fn: Callable, *args) -> Any:
        """Kept for compatibility with plugins written for the asyncio backend: just fn(*args).

        Routes and tasks already run in threads, so there is nothing to offload to.
        """
        return fn(*args)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def on_import_complete(self, callback: Callable[[int | None], None]) -> None:
        self._reg_import_complete(callback)

    def on_folder_delete(self, callback: Callable[[List[Folder]], None]) -> None:
        self._reg_delete(callback)

    def on_vector_type_delete(self, callback: Callable[[int], None]) -> None:
        """callback(type_id) after a vector type is deleted through the project (the UI).
        Not called for the plugin's own delete_vector_type()."""
        if self._reg_vector_type_delete:
            self._reg_vector_type_delete(callback)


def _tag_list(value: Any) -> list:
    """A tag cell value as a list: None → [], one id or label → [it]."""
    if value is None:
        return []
    if isinstance(value, (int, str)):
        return [value]
    return list(value)
