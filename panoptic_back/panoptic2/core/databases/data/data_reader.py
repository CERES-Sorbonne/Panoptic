import json
from typing import Any, List

from panoptic2.core.databases.data.system_properties import SYSTEM_PROPERTY_MAP
from panoptic2.core.databases.data.create import (
    COMMITS_SCHEMA, FILE_SOURCES_SCHEMA, FOLDERS_SCHEMA, FILES_SCHEMA,
    INSTANCES_SCHEMA, PROPERTIES_SCHEMA, TAGS_SCHEMA,
    INSTANCE_VALUES_SCHEMA, SHA1_VALUES_SCHEMA, FILE_VALUES_SCHEMA,
    INSTANCE_TAG_VALUES_SCHEMA, SHA1_TAG_VALUES_SCHEMA,
)
from panoptic2.core.databases.sqlite_reader import SQLiteReader
from panoptic2.core.databases.data.models import (
    Commit, FileSource, Folder, File, Instance,
    Property, Tag, InstanceValue, Sha1Value, FileValue,
    InstanceTagValue, Sha1TagValue,
)
from panoptic2.models.models import PropertyType
from panoptic2.core.databases.entity_schema import OP_CREATE, OP_DELETE, OP_DELETE

_TAG_DTYPES = {PropertyType.tag.value, PropertyType.multi_tags.value}


class DataReader(SQLiteReader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_max_commit_id(self) -> int:
        result = self.conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM {COMMITS_SCHEMA.table}").fetchone()
        return result[0] if result else 0

    def get_next_sequence(self) -> int:
        result = self.conn.execute("SELECT COALESCE(MAX(id), 0) FROM sequence").fetchone()
        return result[0] if result else 0

    def get_commits_since(self, last_commit_id: int) -> List[Commit]:
        sql = f"SELECT * FROM {COMMITS_SCHEMA.table} WHERE id > ? ORDER BY id ASC"
        rows = self.conn.execute(sql, (last_commit_id,)).fetchall()
        return [COMMITS_SCHEMA._decode_row(r) for r in rows]

    def get_commits(self, offset: int = None, limit: int = None, group_id: int = None) -> List[Commit]:
        sql = f"SELECT * FROM {COMMITS_SCHEMA.table}"
        params = []

        if group_id is not None:
            sql += " WHERE group_id = ?"
            params.append(group_id)

        sql += " ORDER BY id DESC"
        if limit is not None:
            sql += f" LIMIT {limit}"
        if offset is not None:
            sql += f" OFFSET {offset}"

        rows = self.conn.execute(sql, params).fetchall()
        return [COMMITS_SCHEMA._decode_row(r) for r in rows]

    def get_commit_by_id(self, commit_id: int) -> Commit:
        return COMMITS_SCHEMA.get(self.conn, id=commit_id)[0]

    def get_file_sources(self, **filters) -> List[FileSource]:
        return FILE_SOURCES_SCHEMA.get(self.conn, **filters)

    def get_folders(self, **filters) -> List[Folder]:
        return FOLDERS_SCHEMA.get(self.conn, **filters)

    def get_files(self, **filters) -> List[File]:
        return FILES_SCHEMA.get(self.conn, **filters)

    def get_instances(self, **filters) -> List[Instance]:
        return INSTANCES_SCHEMA.get(self.conn, **filters)

    def get_properties(self, **filters) -> List[Property]:
        return PROPERTIES_SCHEMA.get(self.conn, **filters)

    def get_tags(self, **filters) -> List[Tag]:
        return TAGS_SCHEMA.get(self.conn, **filters)

    def get_instance_values(self, **filters) -> List[InstanceValue]:
        return INSTANCE_VALUES_SCHEMA.get(self.conn, **filters)

    def get_sha1_values(self, **filters) -> List[Sha1Value]:
        return SHA1_VALUES_SCHEMA.get(self.conn, **filters)

    def get_file_values(self, **filters) -> List[FileValue]:
        return FILE_VALUES_SCHEMA.get(self.conn, **filters)

    def get_instance_tag_values(self, **filters) -> List[InstanceTagValue]:
        return INSTANCE_TAG_VALUES_SCHEMA.get(self.conn, **filters)

    def get_sha1_tag_values(self, **filters) -> List[Sha1TagValue]:
        return SHA1_TAG_VALUES_SCHEMA.get(self.conn, **filters)

    def count_instance_values(self) -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {INSTANCE_VALUES_SCHEMA.table}").fetchone()[0]

    def count_sha1_values(self) -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {SHA1_VALUES_SCHEMA.table}").fetchone()[0]

    def count_file_values(self) -> int:
        return self.conn.execute(f"SELECT COUNT(*) FROM {FILE_VALUES_SCHEMA.table}").fetchone()[0]

    def iter_instance_values(self, batch_size: int):
        cursor = self.conn.execute(f"SELECT * FROM {INSTANCE_VALUES_SCHEMA.table}")
        while rows := cursor.fetchmany(batch_size):
            yield [INSTANCE_VALUES_SCHEMA._decode_row(r) for r in rows]

    def iter_sha1_values(self, batch_size: int):
        cursor = self.conn.execute(f"SELECT * FROM {SHA1_VALUES_SCHEMA.table}")
        while rows := cursor.fetchmany(batch_size):
            yield [SHA1_VALUES_SCHEMA._decode_row(r) for r in rows]

    def iter_file_values(self, batch_size: int):
        cursor = self.conn.execute(f"SELECT * FROM {FILE_VALUES_SCHEMA.table}")
        while rows := cursor.fetchmany(batch_size):
            yield [FILE_VALUES_SCHEMA._decode_row(r) for r in rows]

    def iter_instance_base(self, batch_size: int):
        """Yield batches of (ids, sha1s, file_ids) for all non-deleted instances.

        All three lists in each batch share the same positional order so
        sha1s[i] and file_ids[i] correspond to ids[i].
        """
        cursor = self.conn.execute(
            f"SELECT id, sha1, file_id FROM {INSTANCES_SCHEMA.table}"
            f" WHERE operation != ?",
            (OP_DELETE,),
        )
        while rows := cursor.fetchmany(batch_size):
            yield (
                [r[0] for r in rows],
                [r[1] for r in rows],
                [r[2] for r in rows],
            )

    # ------------------------------------------------------------------
    # Lazy column fetch (used by the ColumnStore endpoints)
    # ------------------------------------------------------------------

    def _is_tag_property(self, prop_id: int) -> bool:
        props = PROPERTIES_SCHEMA.get(self.conn, id=prop_id)
        return bool(props and props[0].dtype in _TAG_DTYPES)

    def get_values_for_instances(
        self,
        instance_ids: list[int],
        prop_id: int,
        mode: str,
        system_key: str | None,
    ) -> dict[int, Any]:
        """Return {instance_id: value} for the given property and instance subset."""
        if not instance_ids:
            return {}

        if system_key:
            return self._system_values_for_instances(instance_ids, system_key)

        if mode == 'id':
            if self._is_tag_property(prop_id):
                return self._tag_values_for_instances(instance_ids, prop_id)
            rows = INSTANCE_VALUES_SCHEMA.get(self.conn, property_id=prop_id, instance_id=instance_ids)
            return {v.instance_id: v.value for v in rows}

        if mode == 'sha1':
            inst_rows = INSTANCES_SCHEMA.select(self.conn, ['id', 'sha1'], id=instance_ids)
            sha1_to_ids: dict[str, list[int]] = {}
            for inst_id, sha1 in inst_rows:
                if sha1:
                    sha1_to_ids.setdefault(sha1, []).append(inst_id)
            if not sha1_to_ids:
                return {}
            if self._is_tag_property(prop_id):
                return self._sha1_tag_values_for_instances(sha1_to_ids, prop_id)
            val_rows = SHA1_VALUES_SCHEMA.get(self.conn, property_id=prop_id, sha1=list(sha1_to_ids))
            result: dict[int, Any] = {}
            for v in val_rows:
                for inst_id in sha1_to_ids[v.sha1]:
                    result[inst_id] = v.value
            return result

        if mode == 'file':
            inst_rows = INSTANCES_SCHEMA.select(self.conn, ['id', 'file_id'], id=instance_ids)
            file_to_ids: dict[int, list[int]] = {}
            for inst_id, file_id in inst_rows:
                if file_id is not None:
                    file_to_ids.setdefault(file_id, []).append(inst_id)
            if not file_to_ids:
                return {}
            val_rows = FILE_VALUES_SCHEMA.get(self.conn, property_id=prop_id, file_id=list(file_to_ids))
            result: dict[int, Any] = {}
            for v in val_rows:
                for inst_id in file_to_ids[v.file_id]:
                    result[inst_id] = v.value
            return result

        return {}

    def _tag_values_for_instances(self, instance_ids: list[int], prop_id: int) -> dict[int, Any]:
        tag_rows = INSTANCE_TAG_VALUES_SCHEMA.get(self.conn, property_id=prop_id, instance_id=instance_ids, operation=OP_CREATE)
        result: dict[int, list[int]] = {}
        for r in tag_rows:
            result.setdefault(r.instance_id, []).append(r.tag_id)
        return result

    def _sha1_tag_values_for_instances(self, sha1_to_ids: dict[str, list[int]], prop_id: int) -> dict[int, Any]:
        tag_rows = SHA1_TAG_VALUES_SCHEMA.get(self.conn, property_id=prop_id, sha1=list(sha1_to_ids), operation=OP_CREATE)
        sha1_to_tags: dict[str, list[int]] = {}
        for r in tag_rows:
            sha1_to_tags.setdefault(r.sha1, []).append(r.tag_id)
        result: dict[int, Any] = {}
        for sha1, inst_ids in sha1_to_ids.items():
            tags = sha1_to_tags.get(sha1)
            if tags:
                for inst_id in inst_ids:
                    result[inst_id] = tags
        return result

    def get_full_column(
        self,
        prop_id: int,
        mode: str,
        system_key: str | None,
    ) -> tuple[list[int], list[Any]]:
        """Return (instance_ids, values) for all instances for the given property."""
        if system_key:
            return self._system_full_column(system_key)

        if mode == 'id':
            if self._is_tag_property(prop_id):
                return self._full_tag_column_by_instance(prop_id)
            rows = INSTANCE_VALUES_SCHEMA.get(self.conn, property_id=prop_id)
            return [v.instance_id for v in rows], [v.value for v in rows]

        if mode == 'sha1':
            if self._is_tag_property(prop_id):
                return self._full_tag_column_by_sha1(prop_id)
            val_rows = SHA1_VALUES_SCHEMA.get(self.conn, property_id=prop_id)
            sha1_to_val = {v.sha1: v.value for v in val_rows}
            if not sha1_to_val:
                return [], []
            inst_rows = INSTANCES_SCHEMA.select(self.conn, ['id', 'sha1'])
            ids, values = [], []
            for inst_id, sha1 in inst_rows:
                if sha1 in sha1_to_val:
                    ids.append(inst_id)
                    values.append(sha1_to_val[sha1])
            return ids, values

        if mode == 'file':
            val_rows = FILE_VALUES_SCHEMA.get(self.conn, property_id=prop_id)
            file_to_val = {v.file_id: v.value for v in val_rows}
            if not file_to_val:
                return [], []
            inst_rows = INSTANCES_SCHEMA.select(self.conn, ['id', 'file_id'])
            ids, values = [], []
            for inst_id, file_id in inst_rows:
                if file_id in file_to_val:
                    ids.append(inst_id)
                    values.append(file_to_val[file_id])
            return ids, values

        return [], []

    def _full_tag_column_by_instance(self, prop_id: int) -> tuple[list[int], list[Any]]:
        tag_rows = INSTANCE_TAG_VALUES_SCHEMA.get(self.conn, property_id=prop_id, operation=OP_CREATE)
        grouped: dict[int, list[int]] = {}
        for r in tag_rows:
            grouped.setdefault(r.instance_id, []).append(r.tag_id)
        return list(grouped.keys()), list(grouped.values())

    def _full_tag_column_by_sha1(self, prop_id: int) -> tuple[list[int], list[Any]]:
        tag_rows = SHA1_TAG_VALUES_SCHEMA.get(self.conn, property_id=prop_id, operation=OP_CREATE)
        sha1_to_tags: dict[str, list[int]] = {}
        for r in tag_rows:
            sha1_to_tags.setdefault(r.sha1, []).append(r.tag_id)
        if not sha1_to_tags:
            return [], []
        inst_rows = INSTANCES_SCHEMA.select(self.conn, ['id', 'sha1'])
        ids, values = [], []
        for inst_id, sha1 in inst_rows:
            if sha1 in sha1_to_tags:
                ids.append(inst_id)
                values.append(sha1_to_tags[sha1])
        return ids, values

    def _system_values_for_instances(self, instance_ids: list[int], system_key: str) -> dict[int, Any]:
        defn = SYSTEM_PROPERTY_MAP[system_key]
        if defn.source == 'instance':
            rows = INSTANCES_SCHEMA.select(self.conn, ['id', defn.col], id=instance_ids)
            return {r[0]: r[1] for r in rows}
        # file-sourced: resolve file_id first, then look up the column on files
        inst_rows = INSTANCES_SCHEMA.select(self.conn, ['id', 'file_id'], id=instance_ids)
        file_ids = [r[1] for r in inst_rows if r[1] is not None]
        if not file_ids:
            return {}
        file_rows = FILES_SCHEMA.select(self.conn, ['id', defn.col], id=file_ids)
        file_to_val = {r[0]: r[1] for r in file_rows}
        return {r[0]: file_to_val[r[1]] for r in inst_rows if r[1] in file_to_val}

    def _system_full_column(self, system_key: str) -> tuple[list[int], list[Any]]:
        defn = SYSTEM_PROPERTY_MAP[system_key]
        if defn.source == 'instance':
            rows = INSTANCES_SCHEMA.select(self.conn, ['id', defn.col])
            return [r[0] for r in rows], [r[1] for r in rows]
        # file-sourced
        inst_rows = INSTANCES_SCHEMA.select(self.conn, ['id', 'file_id'])
        file_ids = [r[1] for r in inst_rows if r[1] is not None]
        if not file_ids:
            return [r[0] for r in inst_rows], [None] * len(inst_rows)
        file_rows = FILES_SCHEMA.select(self.conn, ['id', defn.col], id=file_ids)
        file_to_val = {r[0]: r[1] for r in file_rows}
        ids = [r[0] for r in inst_rows]
        values = [file_to_val.get(r[1]) for r in inst_rows]
        return ids, values

    def get_file_path_for_sha1(self, sha1: str) -> str | None:
        """Return the full filesystem path for the first file matching sha1, or None."""
        row = self.conn.execute(
            "SELECT fo.path, f.name"
            " FROM files f JOIN folders fo ON fo.id = f.folder_id"
            " WHERE f.sha1 = ? AND f.name IS NOT NULL AND fo.path IS NOT NULL"
            " LIMIT 1",
            (sha1,),
        ).fetchone()
        if not row:
            return None
        return f"{row[0]}/{row[1]}"

    def get_delta(
        self,
        since: int,
        full_prop_ids: list[int] | None = None,
        point_prop_ids: list[int] | None = None,
        instance_ids: list[int] | None = None,
    ) -> dict:
        """Return all rows changed since `since`.

        When filter params are provided, value tables are scoped:
        - full_prop_ids:  return changed values for ALL instances (column reload)
        - point_prop_ids + instance_ids: return changed values only for those instances
        - sha1/file value tables: filtered by property_id only (no instance_id column)

        The max sequence is always computed over unfiltered tables so that
        lastSequence advances past rows the caller chose not to fetch.
        """
        data = {
            'instances':  INSTANCES_SCHEMA.get_since(self.conn, since),
            'files':      FILES_SCHEMA.get_since(self.conn, since),
            'folders':    FOLDERS_SCHEMA.get_since(self.conn, since),
            'properties': PROPERTIES_SCHEMA.get_since(self.conn, since),
            'tags':       TAGS_SCHEMA.get_since(self.conn, since),
        }

        filtering = full_prop_ids is not None or point_prop_ids is not None
        if not filtering:
            data['instance_values'] = INSTANCE_VALUES_SCHEMA.get_since(self.conn, since)
            data['image_values']    = SHA1_VALUES_SCHEMA.get_since(self.conn, since)
            data['file_values']     = FILE_VALUES_SCHEMA.get_since(self.conn, since)
        else:
            all_prop_ids = list({*(full_prop_ids or []), *(point_prop_ids or [])})
            data['instance_values'] = self._iv_since_filtered(
                since, full_prop_ids or [], point_prop_ids or [], instance_ids or []
            )
            data['image_values'] = self._values_since_prop_filter(
                SHA1_VALUES_SCHEMA, since, all_prop_ids
            )
            data['file_values'] = self._values_since_prop_filter(
                FILE_VALUES_SCHEMA, since, all_prop_ids
            )

        # Merge instance_tag_values back into instance_values shape: {instance_id: [tag_ids]}
        itv_since = INSTANCE_TAG_VALUES_SCHEMA.get_since(self.conn, since)
        if itv_since:
            grouped_itv: dict[tuple, list[int]] = {}
            for r in itv_since:
                grouped_itv.setdefault((r.instance_id, r.property_id), []).append(r.tag_id)
            # Reconstruct full tag list from current junction state for affected (instance, property) pairs
            merged_iv = data.get('instance_values', [])
            affected_pairs = list(grouped_itv.keys())
            for inst_id, prop_id in affected_pairs:
                full_tags = [r.tag_id for r in INSTANCE_TAG_VALUES_SCHEMA.get(
                    self.conn, instance_id=inst_id, property_id=prop_id)]
                merged_iv.append(InstanceValue(
                    property_id=prop_id, instance_id=inst_id,
                    value=full_tags if full_tags else None,
                ))
            data['instance_values'] = merged_iv

        stv_since = SHA1_TAG_VALUES_SCHEMA.get_since(self.conn, since)
        if stv_since:
            grouped_stv: dict[tuple, list[int]] = {}
            for r in stv_since:
                grouped_stv.setdefault((r.sha1, r.property_id), [])
            merged_sv = data.get('image_values', [])
            for sha1, prop_id in grouped_stv.keys():
                full_tags = [r.tag_id for r in SHA1_TAG_VALUES_SCHEMA.get(
                    self.conn, sha1=sha1, property_id=prop_id)]
                merged_sv.append(Sha1Value(
                    property_id=prop_id, sha1=sha1,
                    value=full_tags if full_tags else None,
                ))
            data['image_values'] = merged_sv

        max_seq = since
        for table in ('instances', 'files', 'folders', 'properties', 'tags',
                      'instance_values', 'sha1_values', 'file_values',
                      'instance_tag_values', 'sha1_tag_values'):
            row = self.conn.execute(
                f"SELECT MAX(sequence) FROM {table} WHERE sequence > ?", (since,)
            ).fetchone()
            if row and row[0] is not None:
                max_seq = max(max_seq, row[0])
        data['sequence'] = max_seq
        return data

    def get_tag_counts(self, property_id: int | None = None) -> list[dict]:
        """Return [{tag_id, instance_count, sha1_count}] from both junction tables."""
        where = "WHERE property_id = ?" if property_id is not None else ""
        params = (property_id,) if property_id is not None else ()
        where_op = f"WHERE operation = {OP_CREATE}" if not where else f"{where} AND operation = {OP_CREATE}"
        sql = f"""
            SELECT tag_id,
                   SUM(instance_count) AS instance_count,
                   SUM(sha1_count)     AS sha1_count
            FROM (
                SELECT tag_id,
                       COUNT(DISTINCT instance_id) AS instance_count,
                       0                           AS sha1_count
                FROM {INSTANCE_TAG_VALUES_SCHEMA.table}
                {where_op}
                GROUP BY tag_id
                UNION ALL
                SELECT tag_id,
                       0                       AS instance_count,
                       COUNT(DISTINCT sha1)    AS sha1_count
                FROM {SHA1_TAG_VALUES_SCHEMA.table}
                {where_op}
                GROUP BY tag_id
            )
            GROUP BY tag_id
        """
        rows = self.conn.execute(sql, params + params).fetchall()
        return [{'tag_id': r[0], 'instance_count': r[1], 'sha1_count': r[2]} for r in rows]

    def count_instances_per_tag(self, property_id: int | None = None) -> dict[int, int]:
        """Return {tag_id: count of distinct instance_ids} from instance_tag_values."""
        if property_id is not None:
            rows = self.conn.execute(
                "SELECT tag_id, COUNT(DISTINCT instance_id) FROM instance_tag_values"
                " WHERE property_id = ? GROUP BY tag_id",
                (property_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT tag_id, COUNT(DISTINCT instance_id) FROM instance_tag_values"
                " GROUP BY tag_id"
            ).fetchall()
        return {tag_id: count for tag_id, count in rows}

    def count_sha1s_per_tag(self, property_id: int | None = None) -> dict[int, int]:
        """Return {tag_id: count of distinct sha1s} from sha1_tag_values."""
        if property_id is not None:
            rows = self.conn.execute(
                "SELECT tag_id, COUNT(DISTINCT sha1) FROM sha1_tag_values"
                " WHERE property_id = ? GROUP BY tag_id",
                (property_id,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT tag_id, COUNT(DISTINCT sha1) FROM sha1_tag_values"
                " GROUP BY tag_id"
            ).fetchall()
        return {tag_id: count for tag_id, count in rows}

    def _iv_since_filtered(
        self,
        since: int,
        full_prop_ids: list[int],
        point_prop_ids: list[int],
        instance_ids: list[int],
    ) -> list:
        rows = []
        if full_prop_ids:
            rows += self._query_iv_since(since, full_prop_ids, None)
        if point_prop_ids and instance_ids:
            rows += self._query_iv_since(since, point_prop_ids, instance_ids)
        return rows

    def _query_iv_since(
        self,
        since: int,
        prop_ids: list[int],
        instance_ids: list[int] | None,
    ) -> list:
        if not prop_ids:
            return []
        prop_ph = ','.join('?' * len(prop_ids))
        if instance_ids is None:
            sql = (f"SELECT * FROM {INSTANCE_VALUES_SCHEMA.table} "
                   f"WHERE sequence > ? AND property_id IN ({prop_ph})")
            rows = self.conn.execute(sql, [since, *prop_ids]).fetchall()
            return [INSTANCE_VALUES_SCHEMA._decode_row(r) for r in rows]

        # Chunk instance_ids to stay within SQLite's 999-variable limit
        fixed = 1 + len(prop_ids)  # since + prop_ids placeholders
        chunk_size = max(1, 900 - fixed)
        result = []
        for i in range(0, len(instance_ids), chunk_size):
            chunk = instance_ids[i:i + chunk_size]
            inst_ph = ','.join('?' * len(chunk))
            sql = (f"SELECT * FROM {INSTANCE_VALUES_SCHEMA.table} "
                   f"WHERE sequence > ? AND property_id IN ({prop_ph}) "
                   f"AND instance_id IN ({inst_ph})")
            rows = self.conn.execute(sql, [since, *prop_ids, *chunk]).fetchall()
            result += [INSTANCE_VALUES_SCHEMA._decode_row(r) for r in rows]
        return result

    def _values_since_prop_filter(self, schema, since: int, prop_ids: list[int]) -> list:
        if not prop_ids:
            return []
        prop_ph = ','.join('?' * len(prop_ids))
        sql = (f"SELECT * FROM {schema.table} "
               f"WHERE sequence > ? AND property_id IN ({prop_ph})")
        rows = self.conn.execute(sql, [since, *prop_ids]).fetchall()
        return [schema._decode_row(r) for r in rows]