"""ProjectData: what a plugin sees of the project it runs for (``plugin.project``).

* reads go straight to the SQLite files (read-only connections),
* data.db writes go to the backend (``commit`` RPC) unless direct writes are enabled,
* media.db vectors and maps are written directly, followed by a coalesced ``db.changed``,
* vector types go through ``vector_type.upsert`` (the backend allocates, writes, refreshes UIs),
* new ids come from ``ids.allocate``.

Without a backend connection (``bridge=None``: unit tests, scripts) every write is direct.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from . import models as m
from .db import schema as s
from .db.connection import ConnectionPool
from .db.reader import ProjectReader
from .db.writer import DataWriter, MediaWriter, allocate_ids, assign_placeholder_ids

log = logging.getLogger('panoptic_plugin.project')

CHANGE_FLUSH_INTERVAL = 1.0


class ProjectData(ProjectReader):
    def __init__(self, plugin_name: str, project_path: str | Path, data_dir: str | Path | None = None,
                 bridge=None, direct_data_writes: bool = False, project_id: str | None = None):
        self.base_path = Path(project_path)
        self.project_id = project_id
        self.plugin_name = plugin_name
        self.data_dir = Path(data_dir) if data_dir else self.base_path / 'plugin_data' / plugin_slug(plugin_name)
        self.pool = ConnectionPool({
            'data': self.base_path / 'data.db',
            'media': self.base_path / 'media.db',
            'project': self.base_path / 'project.db',
        })
        super().__init__(self.pool)
        self._bridge = bridge
        self.direct_data_writes = direct_data_writes
        self._data_writer = DataWriter(lambda: self.pool.write('data'))
        self._media_writer = MediaWriter(lambda: self.pool.write('media'))
        self._pending_media: dict[str, set] = {}
        self._pending_lock = threading.Lock()
        self._flush_timer: threading.Timer | None = None
        self._last_flush = 0.0

    @property
    def connected(self) -> bool:
        return self._bridge is not None

    # ------------------------------------------------------------------
    # ids
    # ------------------------------------------------------------------

    def allocate_ids(self, kind: str, count: int = 1) -> int:
        """Reserve ``count`` consecutive ids of ``kind`` (properties, tags, property_groups,
        vector_types, maps); returns the first one."""
        if kind not in s.PLUGIN_ID_KINDS:
            raise ValueError(f"plugins cannot allocate {kind!r} ids")
        if count < 1:
            raise ValueError("count must be >= 1")
        if self._bridge is not None:
            return int(self._bridge.call('ids.allocate', {'kind': kind, 'count': count})['start'])
        with self.pool.write('project') as cur:
            return allocate_ids(cur, kind, count)

    # ------------------------------------------------------------------
    # data.db writes
    # ------------------------------------------------------------------

    def commit(self, commit: m.DataCommit, group_id: int | None = None, author: str | None = None,
               direct: bool | None = None) -> m.CommitResult:
        """Apply a DataCommit as one undoable commit (source = this plugin).

        Routed through the backend by default, which records it in the history, updates its
        in-memory state and notifies clients. ``direct=True`` (or ``direct_data_writes``) writes
        data.db here, following the commit-log protocol, then sends ``db.changed``.
        """
        _validate_commit(commit)
        if commit.is_empty():
            return m.CommitResult(commit=None)
        use_direct = direct if direct is not None else (self.direct_data_writes or self._bridge is None)
        if not use_direct:
            res = self._bridge.call('commit', {'commit': commit, 'group_id': group_id, 'author': author})
            return _commit_result(res)
        resolved, ids = assign_placeholder_ids(commit, self.allocate_ids)
        row, seq = self._data_writer.apply_commit(self.plugin_name, resolved, group_id=group_id, author=author)
        if row is not None and self._bridge is not None:
            self._bridge.notify('db.changed', {'db': 'data', 'sequence': seq, 'commit_ids': [row.id]})
        return m.CommitResult(commit=row, ids=ids, sequence=seq)

    # names of the old PluginProjectInterface
    apply_commit = commit

    def add_property(self, name: str, dtype: str, mode: str = 'sha1', readonly: bool = False,
                     property_group_id: int | None = None) -> m.Property:
        """Create a property owned by this plugin; returns it with its real id.
        ``readonly=True`` stores access='read': the UI cannot edit it, the plugin still can."""
        prop = m.Property(id=-1, dtype=dtype, mode=mode, name=name, access='read' if readonly else 'write',
                          tag_list_id=None, property_group_id=property_group_id)
        res = self.commit(m.DataCommit(properties=[prop]))
        new_id = res.real_id('properties', -1)
        return self.property(new_id) or m.Property(
            id=new_id, dtype=dtype, mode=mode, name=name, access=prop.access, tag_list_id=new_id,
            property_group_id=property_group_id, operation=s.OP_CREATE)

    def add_property_group(self, name: str) -> m.PropertyGroup:
        res = self.commit(m.DataCommit(property_groups=[m.PropertyGroup(id=-1, name=name)]))
        new_id = res.real_id('property_groups', -1)
        rows = self.get_property_groups(id=new_id)
        return rows[0] if rows else m.PropertyGroup(id=new_id, name=name, operation=s.OP_CREATE)

    def get_or_create_property(self, name: str, dtype: str, mode: str = 'sha1', readonly: bool = False,
                               property_group_id: int | None = None) -> m.Property:
        existing = self.find_property(name, dtype=dtype, mode=mode)
        return existing or self.add_property(name, dtype, mode, readonly, property_group_id)

    def add_tag(self, property_id: int, value: str, parents: list[int] | None = None,
                color: int | None = None) -> m.Tag:
        prop = self.property(property_id)
        if prop is None:
            raise KeyError(f"Property {property_id} not found")
        tag = m.Tag(id=-1, list_id=prop.tag_list_id, parents=parents or [], value=value, color=color)
        res = self.commit(m.DataCommit(tags=[tag]))
        new_id = res.real_id('tags', -1)
        rows = self.get_tags(id=new_id)
        return rows[0] if rows else tag

    def set_values(self, property_id: int, values: dict, group_id: int | None = None) -> m.CommitResult:
        """Set the values of one property: ``{instance_id | sha1 | file_id: value}`` depending
        on the property mode. For tag properties a value is the full list of tag ids."""
        prop = self.property(property_id)
        if prop is None:
            raise KeyError(f"Property {property_id} not found")
        c = m.DataCommit()
        if prop.mode == 'id':
            c.instance_values = [m.InstanceValue(property_id=prop.id, instance_id=k, value=v) for k, v in values.items()]
        elif prop.mode == 'sha1':
            c.sha1_values = [m.Sha1Value(property_id=prop.id, sha1=k, value=v) for k, v in values.items()]
        elif prop.mode == 'file':
            c.file_values = [m.FileValue(property_id=prop.id, file_id=k, value=v) for k, v in values.items()]
        else:
            raise ValueError(f"Property {property_id} has mode {prop.mode!r}")
        return self.commit(c, group_id=group_id)

    # ------------------------------------------------------------------
    # media.db writes
    # ------------------------------------------------------------------

    def upsert_vectors(self, vectors: list[m.Vector]) -> None:
        """Write vectors directly (INSERT OR REPLACE, short transactions)."""
        if not vectors:
            return
        self._media_writer.upsert_vectors(vectors)
        self._media_changed('vectors', {v.type_id for v in vectors})

    def delete_vectors(self, type_id: int, sha1s: list[str] | None = None) -> None:
        self._own_vector_type(type_id)
        self._media_writer.delete_vectors(type_id, sha1s)
        self._media_changed('vectors', {type_id})

    def upsert_vector_type(self, vt: m.VectorType) -> m.VectorType:
        """Create (``id < 0``) or update one of this plugin's vector types."""
        vt = m.VectorType(id=vt.id, source=self.plugin_name, params=dict(vt.params or {}))
        if self._bridge is not None:
            res = self._bridge.call('vector_type.upsert', {'vector_type': vt})
            return m.from_dict(m.VectorType, res['vector_type'])
        if vt.id < 0:
            vt = m.VectorType(id=self.allocate_ids('vector_types'), source=vt.source, params=vt.params)
        else:
            self._own_vector_type(vt.id)
        self._media_writer.upsert_vector_type(vt)
        return vt

    def delete_vector_type(self, type_id: int) -> None:
        if self._bridge is not None:
            self._bridge.call('vector_type.delete', {'id': type_id})
            return
        self._own_vector_type(type_id)
        self._media_writer.delete_vector_type(type_id)

    def upsert_map(self, map_: m.Map) -> m.Map:
        """Create (``id < 0``) or update one of this plugin's maps. Written directly (map data
        can be far larger than an RPC message), then announced with ``db.changed``."""
        if map_.id < 0:
            map_ = m.Map(id=self.allocate_ids('maps'), source=self.plugin_name, name=map_.name,
                         key=map_.key, count=map_.count, data=map_.data)
        else:
            existing = self.get_maps(id=map_.id)
            if existing and existing[0].source != self.plugin_name:
                raise PermissionError(f"map {map_.id} belongs to {existing[0].source!r}")
            map_ = m.Map(id=map_.id, source=self.plugin_name, name=map_.name, key=map_.key,
                         count=map_.count, data=map_.data)
        self._media_writer.upsert_map(map_)
        self._media_changed('maps', {map_.id}, flush=True)
        return map_

    def delete_map(self, map_id: int) -> None:
        if self._bridge is not None:
            self._bridge.call('map.delete', {'id': map_id})
            return
        self._media_writer.delete_map(map_id)

    def _own_vector_type(self, type_id: int) -> None:
        vt = self.vector_type(type_id)
        if vt is not None and vt.source != self.plugin_name:
            raise PermissionError(f"vector type {type_id} belongs to {vt.source!r}")

    # -- db.changed coalescing (media) ----------------------------------------------------
    def _media_changed(self, table: str, ids: set, flush: bool = False) -> None:
        if self._bridge is None:
            return
        with self._pending_lock:
            self._pending_media.setdefault(table, set()).update(ids)
            due = flush or time.monotonic() - self._last_flush >= CHANGE_FLUSH_INTERVAL
            if not due and self._flush_timer is None:
                self._flush_timer = threading.Timer(CHANGE_FLUSH_INTERVAL, self.flush_changes)
                self._flush_timer.daemon = True
                self._flush_timer.start()
        if due:
            self.flush_changes()

    def flush_changes(self) -> None:
        """Send the pending ``db.changed`` for media writes now."""
        with self._pending_lock:
            pending, self._pending_media = self._pending_media, {}
            if self._flush_timer is not None:
                self._flush_timer.cancel()
                self._flush_timer = None
            self._last_flush = time.monotonic()
        if not pending or self._bridge is None:
            return
        params: dict[str, Any] = {'db': 'media', 'tables': sorted(pending)}
        if 'vectors' in pending:
            params['vector_type_ids'] = sorted(pending['vectors'])
        if 'maps' in pending:
            params['map_ids'] = sorted(pending['maps'])
        self._bridge.notify('db.changed', params)

    def close(self) -> None:
        try:
            self.flush_changes()
        finally:
            self.pool.close()


def plugin_slug(name: str) -> str:
    """Folder name of a plugin's data dir (APlugin: '_'.join(name.split()).lower())."""
    return '_'.join(name.split()).lower()


def _validate_commit(commit: m.DataCommit) -> None:
    for p in commit.properties:
        if p.system_key:
            raise ValueError("plugins cannot create or change system properties")
        if p.id is None:
            raise ValueError("property id is required (use a negative placeholder for a new one)")
    for t in commit.tags:
        if t.id is None:
            raise ValueError("tag id is required (use a negative placeholder for a new one)")


def _commit_result(res: dict) -> m.CommitResult:
    row = res.get('commit')
    commit = None
    if row:
        commit = m.from_dict(m.Commit, row)
        if isinstance(commit.timestamp, str):
            try:
                commit.timestamp = s.parse_timestamp(commit.timestamp)
            except Exception:
                pass
    ids = {kind: {int(k): int(v) for k, v in mapping.items()} for kind, mapping in (res.get('ids') or {}).items()}
    return m.CommitResult(commit=commit, ids=ids, sequence=res.get('sequence'))
