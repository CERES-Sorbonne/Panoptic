"""Read helpers over data.db / media.db / project.db — ports of the python reference readers
(`DataReader`, `MediaDB`, `ProjectDB`) restricted to what plugins need.
"""
from __future__ import annotations

from typing import Any

from .. import models as m
from . import schema as s
from .connection import ConnectionPool

# system_key -> (source table, column), data/system_properties.py
SYSTEM_PROPERTIES = {
    'id':         ('instance', 'id'),
    'sha1':       ('instance', 'sha1'),
    'file_id':    ('instance', 'file_id'),
    'folder':     ('file', 'folder_id'),
    'name':       ('file', 'name'),
    'path':       ('file', 'path'),
    'format':     ('file', 'format'),
    'width':      ('file', 'width'),
    'height':     ('file', 'height'),
    'created_at': ('file', 'created_at'),
}


def _parse_filters(filters: dict) -> tuple[str | None, list | None, dict, dict]:
    lists, scalars = {}, {}
    for col, val in filters.items():
        if isinstance(val, (list, tuple, set, frozenset)):
            lists[col] = list(val)
        else:
            scalars[col] = val
    if not lists:
        return None, None, {}, scalars
    big = max(lists, key=lambda k: len(lists[k]))
    return big, lists.pop(big), lists, scalars


def _col_ref(col: str, vals: list) -> str:
    # Keep `operation = 1` lookups off the operation index (entity_schema._col_ref)
    if col == 'operation' and s.OP_DELETE not in vals:
        return '+operation'
    return col


def select_rows(conn, table: s.Table | str, columns, **filters) -> list[tuple]:
    """Chunked `SELECT columns FROM table WHERE ...` — scalar filters are `=`, lists are `IN`
    (port of EntitySchema._execute_chunked)."""
    name = table.name if isinstance(table, s.Table) else table
    col_clause = ', '.join(columns)
    big_col, big_vals, small, scalars = _parse_filters(filters)
    parts, params = [], []
    for col, vals in small.items():
        if not vals:
            return []
        parts.append(f"{_col_ref(col, vals)} IN ({', '.join(['?'] * len(vals))})")
        params.extend(vals)
    for col, val in scalars.items():
        if val is None:
            parts.append(f"{col} IS NULL")
        else:
            parts.append(f"{_col_ref(col, [val])} = ?")
            params.append(val)
    fixed = ' AND '.join(parts)
    if big_col is None:
        sql = f"SELECT {col_clause} FROM {name}" + (f" WHERE {fixed}" if fixed else '')
        return conn.execute(sql, params).fetchall()
    room = s.MAX_VARS - len(params)
    if room < 1:
        raise ValueError(f"Too many filter values besides {big_col!r}")
    out: list[tuple] = []
    for i in range(0, len(big_vals), room):
        chunk = big_vals[i:i + room]
        where = [f"{_col_ref(big_col, chunk)} IN ({', '.join(['?'] * len(chunk))})"]
        if fixed:
            where.append(fixed)
        sql = f"SELECT {col_clause} FROM {name} WHERE {' AND '.join(where)}"
        out.extend(conn.execute(sql, chunk + params).fetchall())
    return out


def get_entities(conn, table: s.Table, state: int = 1, **filters) -> list:
    """Port of EntitySchema.get: on logged tables state=1 keeps live rows (create/update),
    state=-1 tombstones, state=0 everything."""
    if table.logged and 'operation' not in filters:
        if state == 1:
            filters['operation'] = [s.OP_CREATE, s.OP_UPDATE]
        elif state == -1:
            filters['operation'] = s.OP_DELETE
    return [table.decode(r) for r in select_rows(conn, table, table.model_columns, **filters)]


def get_by_pk(conn, table: s.Table, pks: list) -> list:
    """Rows (tombstones included) for a list of pks (scalars or tuples)."""
    if not pks:
        return []
    n = len(table.pk)
    per = max(1, s.MAX_VARS // n)
    out = []
    cols = ', '.join(table.model_columns)
    pk_cols = ', '.join(table.pk)
    for i in range(0, len(pks), per):
        chunk = pks[i:i + per]
        if n == 1:
            sql = f"SELECT {cols} FROM {table.name} WHERE {table.pk[0]} IN ({', '.join(['?'] * len(chunk))})"
            params = list(chunk)
        else:
            ph = ', '.join(['(' + ','.join(['?'] * n) + ')'] * len(chunk))
            sql = f"SELECT {cols} FROM {table.name} WHERE ({pk_cols}) IN (VALUES {ph})"
            params = [v for pk in chunk for v in pk]
        out.extend(conn.execute(sql, params).fetchall())
    return [table.decode(r) for r in out]


class ProjectReader:
    """Read-only access to a project's databases."""

    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def _data(self):
        return self._pool.read('data')

    def _media(self):
        return self._pool.read('media')

    def _project(self):
        return self._pool.read('project')

    # ------------------------------------------------------------------
    # data.db — entities  (old PluginProjectInterface names kept)
    # ------------------------------------------------------------------

    def get_file_sources(self, **filters) -> list[m.FileSource]:
        return get_entities(self._data(), s.FILE_SOURCES, **filters)

    def get_folders(self, **filters) -> list[m.Folder]:
        return get_entities(self._data(), s.FOLDERS, **filters)

    def get_files(self, **filters) -> list[m.File]:
        return get_entities(self._data(), s.FILES, **filters)

    def get_instances(self, **filters) -> list[m.Instance]:
        return get_entities(self._data(), s.INSTANCES, **filters)

    def get_properties(self, **filters) -> list[m.Property]:
        return get_entities(self._data(), s.PROPERTIES, **filters)

    def get_property_groups(self, **filters) -> list[m.PropertyGroup]:
        return get_entities(self._data(), s.PROPERTY_GROUPS, **filters)

    def get_tags(self, **filters) -> list[m.Tag]:
        return get_entities(self._data(), s.TAGS, **filters)

    def get_instance_values(self, **filters) -> list[m.InstanceValue]:
        return get_entities(self._data(), s.INSTANCE_VALUES, **filters)

    def get_sha1_values(self, **filters) -> list[m.Sha1Value]:
        return get_entities(self._data(), s.SHA1_VALUES, **filters)

    def get_file_values(self, **filters) -> list[m.FileValue]:
        return get_entities(self._data(), s.FILE_VALUES, **filters)

    def get_instance_tag_values(self, **filters) -> list[m.InstanceTagValue]:
        return get_entities(self._data(), s.INSTANCE_TAG_VALUES, **filters)

    def get_sha1_tag_values(self, **filters) -> list[m.Sha1TagValue]:
        return get_entities(self._data(), s.SHA1_TAG_VALUES, **filters)

    # Short names
    def instances(self, ids: list[int] | None = None, sha1s: list[str] | None = None,
                  file_ids: list[int] | None = None) -> list[m.Instance]:
        f = {}
        if ids is not None:
            f['id'] = list(ids)
        if sha1s is not None:
            f['sha1'] = list(sha1s)
        if file_ids is not None:
            f['file_id'] = list(file_ids)
        return self.get_instances(**f)

    def property(self, property_id: int) -> m.Property | None:
        rows = self.get_properties(id=property_id)
        return rows[0] if rows else None

    def find_property(self, name: str, dtype: str | None = None, mode: str | None = None) -> m.Property | None:
        for p in self.get_properties(name=name):
            if (dtype is None or p.dtype == dtype) and (mode is None or p.mode == mode):
                return p
        return None

    def folder_subtree(self, root_folder_id: int) -> list[int]:
        """Ids of a folder and all its descendants."""
        children: dict[int, list[int]] = {}
        for fid, parent in self._data().execute("SELECT id, parent FROM folders").fetchall():
            if parent is not None:
                children.setdefault(parent, []).append(fid)
        out, frontier = [root_folder_id], [root_folder_id]
        while frontier:
            frontier = [c for p in frontier for c in children.get(p, [])]
            out.extend(frontier)
        return out

    def instances_under_folder(self, root_folder_id: int | None) -> list[m.Instance]:
        """Instances of a folder subtree (folders -> files -> instances); all when None."""
        if root_folder_id is None:
            return self.get_instances()
        files = self.get_files(folder_id=self.folder_subtree(root_folder_id))
        if not files:
            return []
        return self.get_instances(file_id=[f.id for f in files])

    # ------------------------------------------------------------------
    # data.db — property values  (DataReader.get_values_for_instances / get_full_column)
    # ------------------------------------------------------------------

    def _alive_tag_ids(self) -> set[int]:
        return {r[0] for r in select_rows(self._data(), s.TAGS, ['id'], operation=[s.OP_CREATE, s.OP_UPDATE])}

    def values(self, property_id: int, instance_ids: list[int] | None = None) -> dict[int, Any]:
        """{instance_id: value} of a property, for the given instances or all of them.

        Follows the property mode (id / sha1 / file), tag properties (value = list of alive tag
        ids) and system properties (computed from the instance / file tables).
        """
        prop = self.property(property_id)
        if prop is None:
            raise KeyError(f"Property {property_id} not found")
        if instance_ids is not None:
            return self._values_for_instances(list(instance_ids), prop)
        ids, vals = self._full_column(prop)
        return dict(zip(ids, vals))

    def _values_for_instances(self, instance_ids: list[int], prop: m.Property) -> dict[int, Any]:
        conn = self._data()
        if not instance_ids:
            return {}
        if prop.system_key:
            return self._system_values(prop.system_key, instance_ids)
        is_tag = prop.dtype in s.TAG_DTYPES
        if prop.mode == 'id':
            if is_tag:
                alive = self._alive_tag_ids()
                out: dict[int, list] = {}
                for r in get_entities(conn, s.INSTANCE_TAG_VALUES, property_id=prop.id,
                                      instance_id=instance_ids, operation=s.OP_CREATE):
                    if r.tag_id in alive:
                        out.setdefault(r.instance_id, []).append(r.tag_id)
                return out
            return {v.instance_id: v.value for v in get_entities(
                conn, s.INSTANCE_VALUES, property_id=prop.id, instance_id=instance_ids)}
        if prop.mode == 'sha1':
            sha1_to_ids: dict[str, list[int]] = {}
            for iid, sha1 in select_rows(conn, s.INSTANCES, ['id', 'sha1'], id=instance_ids):
                if sha1:
                    sha1_to_ids.setdefault(sha1, []).append(iid)
            if not sha1_to_ids:
                return {}
            per_sha1: dict[str, Any] = {}
            if is_tag:
                alive = self._alive_tag_ids()
                for r in get_entities(conn, s.SHA1_TAG_VALUES, property_id=prop.id,
                                      sha1=list(sha1_to_ids), operation=s.OP_CREATE):
                    if r.tag_id in alive:
                        per_sha1.setdefault(r.sha1, []).append(r.tag_id)
            else:
                for v in get_entities(conn, s.SHA1_VALUES, property_id=prop.id, sha1=list(sha1_to_ids)):
                    per_sha1[v.sha1] = v.value
            return {iid: val for sha1, val in per_sha1.items() for iid in sha1_to_ids[sha1]}
        if prop.mode == 'file':
            file_to_ids: dict[int, list[int]] = {}
            for iid, fid in select_rows(conn, s.INSTANCES, ['id', 'file_id'], id=instance_ids):
                if fid is not None:
                    file_to_ids.setdefault(fid, []).append(iid)
            if not file_to_ids:
                return {}
            out = {}
            for v in get_entities(conn, s.FILE_VALUES, property_id=prop.id, file_id=list(file_to_ids)):
                for iid in file_to_ids[v.file_id]:
                    out[iid] = v.value
            return out
        return {}

    def _full_column(self, prop: m.Property) -> tuple[list[int], list[Any]]:
        conn = self._data()
        if prop.system_key:
            ids = [r[0] for r in conn.execute("SELECT id FROM instances").fetchall()]
            vals = self._system_values(prop.system_key, ids)
            return ids, [vals.get(i) for i in ids]
        is_tag = prop.dtype in s.TAG_DTYPES
        if prop.mode == 'id':
            if is_tag:
                alive = self._alive_tag_ids()
                grouped: dict[int, list[int]] = {}
                for r in get_entities(conn, s.INSTANCE_TAG_VALUES, property_id=prop.id, operation=s.OP_CREATE):
                    if r.tag_id in alive:
                        grouped.setdefault(r.instance_id, []).append(r.tag_id)
                return list(grouped), list(grouped.values())
            rows = get_entities(conn, s.INSTANCE_VALUES, property_id=prop.id)
            return [v.instance_id for v in rows], [v.value for v in rows]
        if prop.mode == 'sha1':
            per_sha1: dict[str, Any] = {}
            if is_tag:
                alive = self._alive_tag_ids()
                for r in get_entities(conn, s.SHA1_TAG_VALUES, property_id=prop.id, operation=s.OP_CREATE):
                    if r.tag_id in alive:
                        per_sha1.setdefault(r.sha1, []).append(r.tag_id)
            else:
                per_sha1 = {v.sha1: v.value for v in get_entities(conn, s.SHA1_VALUES, property_id=prop.id)}
            if not per_sha1:
                return [], []
            ids, vals = [], []
            for iid, sha1 in conn.execute("SELECT id, sha1 FROM instances").fetchall():
                if sha1 in per_sha1:
                    ids.append(iid)
                    vals.append(per_sha1[sha1])
            return ids, vals
        if prop.mode == 'file':
            per_file = {v.file_id: v.value for v in get_entities(conn, s.FILE_VALUES, property_id=prop.id)}
            if not per_file:
                return [], []
            ids, vals = [], []
            for iid, fid in conn.execute("SELECT id, file_id FROM instances").fetchall():
                if fid in per_file:
                    ids.append(iid)
                    vals.append(per_file[fid])
            return ids, vals
        return [], []

    def _system_values(self, system_key: str, instance_ids: list[int]) -> dict[int, Any]:
        source, col = SYSTEM_PROPERTIES[system_key]
        conn = self._data()
        if source == 'instance':
            return {r[0]: r[1] for r in select_rows(conn, s.INSTANCES, ['id', col], id=instance_ids)}
        inst = select_rows(conn, s.INSTANCES, ['id', 'file_id'], id=instance_ids)
        file_ids = [r[1] for r in inst if r[1] is not None]
        if not file_ids:
            return {}
        if system_key == 'path':
            per_file = self._file_paths(file_ids)
        else:
            per_file = {r[0]: r[1] for r in select_rows(conn, s.FILES, ['id', col], id=file_ids)}
            if col == 'created_at':
                per_file = {k: (s.parse_timestamp(v) if isinstance(v, (str, bytes)) else v)
                            for k, v in per_file.items()}
        return {iid: per_file[fid] for iid, fid in inst if fid in per_file}

    def _file_paths(self, file_ids: list[int]) -> dict[int, str | None]:
        conn = self._data()
        iiif = {r[0] for r in conn.execute("SELECT id, dtype FROM file_sources").fetchall() if r[1] == 'iiif'}
        prefixes: dict[int, str] = {}
        for folder_id, path, source_id in conn.execute("SELECT id, path, source_id FROM folders").fetchall():
            if source_id in iiif:
                prefixes[folder_id] = ''
            elif path is not None:
                prefixes[folder_id] = f"{path}/"
        out = {}
        for fid, folder_id, name in select_rows(conn, s.FILES, ['id', 'folder_id', 'name'], id=file_ids):
            out[fid] = prefixes[folder_id] + name if name is not None and folder_id in prefixes else None
        return out

    # ------------------------------------------------------------------
    # data.db — files on disk
    # ------------------------------------------------------------------

    def resolve_image_ref(self, sha1: str) -> dict | None:
        """{'kind': 'local', 'path'} or {'kind': 'iiif', 'url', 'source_id'} (DataReader.resolve_image_ref)."""
        row = self._data().execute(
            "SELECT fo.path, f.name, fs.dtype, fs.id FROM files f"
            " JOIN folders fo ON fo.id = f.folder_id"
            " JOIN file_sources fs ON fs.id = fo.source_id"
            " WHERE f.sha1 = ? AND f.name IS NOT NULL LIMIT 1", (sha1,)).fetchone()
        if not row:
            return None
        path, name, dtype, source_id = row
        if dtype == 'iiif':
            return {'kind': 'iiif', 'url': name, 'source_id': source_id}
        if path is None:
            return None
        return {'kind': 'local', 'path': f"{path}/{name}"}

    def file_path(self, sha1: str) -> str | None:
        """Local filesystem path of the first local file with this sha1 (None for IIIF)."""
        ref = self.resolve_image_ref(sha1)
        return ref['path'] if ref and ref['kind'] == 'local' else None

    def local_paths(self) -> dict[str, str]:
        """{sha1: local path} for every sha1 backed by a local file (first file wins)."""
        rows = self._data().execute(
            "SELECT f.sha1, fo.path, f.name FROM files f"
            " JOIN folders fo ON fo.id = f.folder_id"
            " JOIN file_sources fs ON fs.id = fo.source_id"
            " WHERE f.sha1 IS NOT NULL AND f.name IS NOT NULL"
            "   AND fo.path IS NOT NULL AND fs.dtype != 'iiif'").fetchall()
        out: dict[str, str] = {}
        for sha1, path, name in rows:
            out.setdefault(sha1, f"{path}/{name}")
        return out

    # ------------------------------------------------------------------
    # data.db — sync state
    # ------------------------------------------------------------------

    def sequence(self) -> int:
        """Current value of the data.db sequence counter (next sequence to be used)."""
        row = self._data().execute("SELECT COALESCE(MAX(id), 0) FROM sequence").fetchone()
        return row[0] if row else 0

    def max_commit_id(self) -> int:
        row = self._data().execute("SELECT COALESCE(MAX(id), 0) FROM commits").fetchone()
        return row[0] if row else 0

    def get_commits(self, source: str | None = None) -> list[m.Commit]:
        f = {} if source is None else {'source': source}
        rows = select_rows(self._data(), s.COMMITS, s.COMMITS.model_columns, **f)
        return sorted((s.COMMITS.decode(r) for r in rows), key=lambda c: c.id)

    # ------------------------------------------------------------------
    # media.db
    # ------------------------------------------------------------------

    def get_vector_types(self, source: str | None = None, **filters) -> list[m.VectorType]:
        if source is not None:
            filters['source'] = source
        return get_entities(self._media(), s.VECTOR_TYPES, **filters)

    def vector_type(self, type_id: int) -> m.VectorType | None:
        rows = self.get_vector_types(id=type_id)
        return rows[0] if rows else None

    def get_vectors(self, type_id: int, sha1s: list[str] | None = None) -> list[m.Vector]:
        f: dict = {'type_id': type_id}
        if sha1s is not None:
            f['sha1'] = list(sha1s)
        return get_entities(self._media(), s.VECTORS, **f)

    def vector_sha1s(self, type_id: int) -> set[str]:
        return {r[0] for r in self._media().execute(
            "SELECT sha1 FROM vectors WHERE type_id = ?", (type_id,)).fetchall()}

    def vector_exist(self, type_id: int, sha1: str) -> bool:
        return self._media().execute("SELECT 1 FROM vectors WHERE type_id = ? AND sha1 = ? LIMIT 1",
                                     (type_id, sha1)).fetchone() is not None

    def get_maps(self, **filters) -> list[m.Map]:
        return get_entities(self._media(), s.MAPS, **filters)

    def get_image_types(self, **filters) -> list[m.ImageType]:
        return get_entities(self._media(), s.IMAGE_TYPES, **filters)

    def get_images(self, type_id: int, sha1s: list[str]) -> dict[str, bytes]:
        """{sha1: encoded image bytes} of a stored rendition (thumbnails in media.db)."""
        rows = select_rows(self._media(), 'images', ['sha1', 'data'], type_id=type_id, sha1=list(sha1s))
        return {r[0]: r[1] for r in rows}

    def get_image(self, sha1: str, type_id: int) -> bytes | None:
        return self.get_images(type_id, [sha1]).get(sha1)

    # ------------------------------------------------------------------
    # project.db
    # ------------------------------------------------------------------

    def stored_params(self, plugin_name: str) -> dict | None:
        row = self._project().execute(
            "SELECT data FROM user_defaults WHERE user_id = ? AND key = 'params'",
            (s.plugin_params_user_id(plugin_name),)).fetchone()
        return s.json_load(row[0]) if row and row[0] is not None else None

    def project_config(self) -> dict:
        rows = self._project().execute("SELECT key, value FROM project_config").fetchall()
        return {k: s.json_load(v) for k, v in rows}
