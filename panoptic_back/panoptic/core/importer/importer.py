"""CSV importer for Panoptic V2.

Stateful: call parse_headers → verify_mapping → import_data_and_commit in order.
"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from random import randint
from typing import Any, TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from panoptic.core.project.project import Project

from panoptic.core.databases.data.models import (
    Instance, Property, Tag, InstanceValue, Sha1Value, UpsertCommit,
)
from panoptic.core.databases.entity_schema import OP_CREATE, OP_UPDATE


# ---------------------------------------------------------------------------
# Internal property descriptor used during an import session
# ---------------------------------------------------------------------------

@dataclass
class ImportProp:
    id: int       # negative = new; positive = existing DB id
    name: str
    dtype: str    # 'text', 'number', 'tag', 'multi_tags', etc.
    mode: str     # 'sha1' | 'id'


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_TYPES = {'text', 'number', 'tag', 'multi_tags', 'url', 'date', 'path', 'color', 'checkbox'}
_VALID_KEYS  = {'id', 'path'}
_TAG_TYPES   = {'tag', 'multi_tags'}

# Number of CSV columns to read per disk pass. Higher = fewer reads but more RAM.
_COL_BATCH = 50

_PARSERS: dict[str, Any] = {
    'text':       lambda v: str(v) if v else None,
    'number':     lambda v: (float(v) if '.' in v else int(v)) if v else None,
    'tag':        lambda v: [v.strip()] if v and v.strip() else None,
    'multi_tags': lambda v: [x.strip() for x in v.split(',') if x.strip()] if v else None,
    'date':       lambda v: str(v) if v else None,
    'color':      lambda v: int(v) if v else None,
    'url':        lambda v: str(v) if v else None,
    'checkbox':   lambda v: True if v else None,
    'path':       lambda v: str(v) if v else None,
}


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def _read_csv(file_path: str, columns: list[str] | None = None,
              n_rows: int | None = None) -> pl.DataFrame | None:
    try:
        return pl.read_csv(
            file_path,
            separator=';',
            encoding='utf-8',
            null_values=[],
            infer_schema=False,
            n_rows=n_rows,
            columns=columns,
        )
    except Exception:
        return None


def _parse_header(index: int, name: str, errors: dict[int, str]):
    if '[' not in name:
        if name in _VALID_KEYS:
            errors[index] = 'Key column found in wrong position; it must be first'
        else:
            errors[index] = 'Missing type bracket — columns must be "Name[type]"'
        dtype = 'text'
    else:
        name, remain = name.split('[', 1)
        raw_type = remain.split(']')[0]
        if raw_type not in _VALID_TYPES:
            errors[index] = f'Invalid type "{raw_type}"'
            dtype = 'text'
        else:
            dtype = raw_type
    return index, name.strip(), dtype


# ---------------------------------------------------------------------------
# Path index: flat dict instead of a character trie
#
# The character trie stored one Python dict node per character across all
# paths — ~30 M nodes for 512 K paths, costing 10–20 GB of RAM.
# This flat dict stores one entry per path-component suffix, which is
# O(depth × n_paths) — typically 1.5 M entries for the same dataset (~400 MB).
# Component-level suffix matching is also more correct: a query "sub/file.jpg"
# matches "root/sub/file.jpg" but NOT "nosub/file.jpg" (no false char-level hits).
# ---------------------------------------------------------------------------

def _norm_path(p: str) -> str:
    return p.replace('\\', '/').strip('/')


class _PathIndex:
    def __init__(self, relative: bool):
        self._relative = relative
        # full normalised path → [inst_ids]
        self._exact: dict[str, list[int]] = {}
        # each component suffix → [inst_ids]  (only built when relative=True)
        self._suffix: dict[str, list[int]] | None = {} if relative else None

    def insert(self, path: str, inst_id: int):
        key = _norm_path(path)
        self._exact.setdefault(key, []).append(inst_id)
        if self._relative:
            parts = key.split('/')
            # start from 1 so the full path is only stored in _exact
            for i in range(1, len(parts)):
                self._suffix.setdefault('/'.join(parts[i:]), []).append(inst_id)

    def search(self, path: str) -> list[int]:
        key = _norm_path(path)
        if self._relative:
            return self._suffix.get(key) or self._exact.get(key) or []
        return self._exact.get(key) or []


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------

class Importer:
    """Stateful CSV importer for Project.

    Usage::

        importer = project.importer
        confirm  = importer.parse_headers('/path/to/file.csv')
        verify   = importer.verify_mapping(relative=False, fusion='new')
        importer.import_data_and_commit()
    """

    def __init__(self, project: 'Project'):
        self.project = project
        self.file_path: str = ''
        self.columns:   list[str] = []
        self.file_key:  str | None = None
        self.col_to_prop: dict[int, ImportProp] = {}
        self._row_to_ids:      list[list[int]] = []
        self._new_inst_info:   list[tuple[int, int, str]] = []   # (file_id, inst_id, sha1)

    # ------------------------------------------------------------------
    # Step 1: parse CSV headers
    # ------------------------------------------------------------------

    def parse_headers(self, file_path: str) -> dict:
        self._clear()
        self.file_path = file_path
        errors: dict[int, str] = {}

        df = _read_csv(file_path, n_rows=0)
        if df is None:
            errors[0] = 'Invalid CSV — use ";" as separator'
            return {'key': '', 'col_to_property': {}, 'errors': errors}

        self.columns  = df.columns
        first         = self.columns[0] if self.columns else ''
        self.file_key = first if first in _VALID_KEYS else None

        if self.file_key is None:
            errors[0] = 'No valid key column (must be "id" or "path" in first column)'

        file_props: list[tuple[int, str, str]] = [
            _parse_header(i, col, errors)
            for i, col in enumerate(self.columns[1:], start=1)
            if col
        ]

        db_props    = self.project.get_properties()
        prop_lookup = {(p.name, p.dtype): p for p in db_props}

        col_to_prop: dict[int, ImportProp] = {}
        for i, name, dtype in file_props:
            existing = prop_lookup.get((name, dtype))
            if existing:
                col_to_prop[i] = ImportProp(id=existing.id, name=name, dtype=dtype,
                                             mode=existing.mode or 'sha1')
            else:
                col_to_prop[i] = ImportProp(id=-i, name=name, dtype=dtype, mode='sha1')

        self.col_to_prop = col_to_prop
        return {
            'key': self.file_key or '',
            'col_to_property': {
                str(i): {'id': p.id, 'name': p.name, 'type': p.dtype, 'mode': p.mode}
                for i, p in col_to_prop.items()
            },
            'errors': errors,
        }

    # ------------------------------------------------------------------
    # Step 2: map CSV rows → instance IDs
    # ------------------------------------------------------------------

    def verify_mapping(self, relative: bool = False, fusion: str = 'new') -> dict:
        if not self.file_key or not self.columns:
            raise ValueError("Call parse_headers first")

        print(f"[import] verify_mapping  file={self.file_path}  key={self.file_key}  fusion={fusion}  relative={relative}")

        df = _read_csv(self.file_path, columns=[self.file_key])
        if df is None:
            raise IOError("Cannot read key column from CSV")

        key_data = df[self.file_key].to_list()
        print(f"[import] CSV rows: {len(key_data):,}")

        from panoptic.core.databases.data.create import (
            INSTANCES_SCHEMA, FILES_SCHEMA, FOLDERS_SCHEMA, INSTANCE_VALUES_SCHEMA,
        )

        print("[import] loading instances / files / folders from DB …")
        with self.project._data_reader() as reader:
            inst_rows   = INSTANCES_SCHEMA.select(reader.conn, ['id', 'sha1', 'file_id'])
            file_rows   = FILES_SCHEMA.select(reader.conn, ['id', 'name', 'folder_id'])
            folder_rows = FOLDERS_SCHEMA.select(reader.conn, ['id', 'path', 'name'])
            print(f"[import]   instances={len(inst_rows):,}  files={len(file_rows):,}  folders={len(folder_rows):,}")

            non_empty_ids: set[int] = set()
            if fusion == 'new':
                rows = reader.conn.execute(
                    f"SELECT DISTINCT instance_id FROM {INSTANCE_VALUES_SCHEMA.table}"
                ).fetchall()
                non_empty_ids = {r[0] for r in rows}
                print(f"[import]   instances with existing values: {len(non_empty_ids):,}")

        instances  = {r[0]: (r[1], r[2]) for r in inst_rows}
        files      = {r[0]: (r[1], r[2]) for r in file_rows}
        folders    = {r[0]: (r[1], r[2]) for r in folder_rows}

        used_ids: set[int] = set()

        initial: list[list[int]] = []

        if self.file_key == 'id':
            print("[import] building id lookup …")
            all_ids = set(instances)
            for val in key_data:
                try:
                    n = int(val)
                    initial.append([n] if n in all_ids else [])
                except (ValueError, TypeError):
                    initial.append([])

        else:  # 'path'
            print("[import] building path index …")
            idx = _PathIndex(relative)
            for inst_id, (sha1, file_id) in instances.items():
                if file_id is None:
                    continue
                fname, folder_id = files.get(file_id, (None, None))
                if not fname:
                    continue
                if folder_id is not None:
                    fpath, _ = folders.get(folder_id, (None, None))
                    full_path = os.path.join(fpath, fname) if fpath else fname
                else:
                    full_path = fname
                idx.insert(full_path, inst_id)
            print(f"[import] path index built  exact={len(idx._exact):,}  suffix={len(idx._suffix) if idx._suffix is not None else 'n/a':,}")

            print("[import] matching CSV rows to instances …")
            for val in key_data:
                initial.append(idx.search(val) if val else [])

        matched = sum(1 for m in initial if m)
        print(f"[import] row matching done  matched={matched:,}  unmatched={len(initial)-matched:,}")

        print(f"[import] applying fusion mode '{fusion}' …")
        row_to_ids:    list[list[int]] = []
        new_inst_info: list[tuple[int, int, str]] = []

        for matches in initial:
            if fusion == 'first':
                row_to_ids.append([matches[0]] if matches else [])

            elif fusion == 'last':
                row_to_ids.append([matches[-1]] if matches else [])

            elif fusion == 'new':
                if matches:
                    reusable = [m for m in matches if m not in non_empty_ids and m not in used_ids]
                    if reusable:
                        free_id = reusable[0]
                        used_ids.add(free_id)
                        row_to_ids.append([free_id])
                    elif self.file_key == 'path':
                        orig_sha1, orig_file_id = instances[matches[0]]
                        new_id = self.project.allocate_instances(1)
                        if isinstance(new_id, range):
                            new_id = new_id.start
                        row_to_ids.append([new_id])
                        new_inst_info.append((orig_file_id or 0, new_id, orig_sha1 or ''))
                    else:
                        row_to_ids.append([])
                else:
                    row_to_ids.append([])
            else:
                row_to_ids.append([matches[0]] if matches else [])

        self._row_to_ids    = row_to_ids
        self._new_inst_info = new_inst_info

        missing = [[i, key_data[i]] for i, ids in enumerate(row_to_ids) if not ids]
        print(f"[import] verify_mapping done  mapped={len(row_to_ids)-len(missing):,}  missing={len(missing):,}  new_instances={len(new_inst_info):,}")
        return {'missing_rows': missing, 'new_instances_count': len(new_inst_info)}

    # ------------------------------------------------------------------
    # Step 3: read CSV data and commit to DB
    # ------------------------------------------------------------------

    def import_data_and_commit(self, exclude: list[int] | None = None,
                                properties: dict[str, dict] | None = None):
        if not self.columns or not self.col_to_prop:
            raise ValueError("Call parse_headers and verify_mapping first")

        print("[import] import_data_and_commit start")

        BATCH = 25_000
        exclude_set = set(exclude or [])

        working: dict[int, ImportProp] = {}
        for i, prop in self.col_to_prop.items():
            if i in exclude_set:
                continue
            override = (properties or {}).get(str(i))
            if override:
                working[i] = ImportProp(
                    id=int(override.get('id', prop.id)),
                    name=override.get('name', prop.name),
                    dtype=override.get('dtype', prop.dtype),
                    mode=override.get('mode', prop.mode),
                )
            else:
                working[i] = ImportProp(id=prop.id, name=prop.name,
                                         dtype=prop.dtype, mode=prop.mode)

        if not working:
            print("[import] no columns to import — aborting")
            return

        print(f"[import] columns to import: {[f'{p.name}[{p.dtype}]/{p.mode}' for p in working.values()]}")

        if self._new_inst_info:
            print(f"[import] committing {len(self._new_inst_info):,} new instances …")
            inst_commit = UpsertCommit()
            for file_id, inst_id, sha1 in self._new_inst_info:
                inst_commit.instances[inst_id] = Instance(
                    id=inst_id, file_id=file_id, sha1=sha1,
                    commit_id=0, operation=OP_CREATE,
                )
            self.project.apply_upsert_commit('import', inst_commit)
            print("[import] new instances committed")

        new_props = [p for p in working.values() if p.id < 0]
        if new_props:
            print(f"[import] creating {len(new_props)} new propert{'y' if len(new_props)==1 else 'ies'} …")
            ids = self.project.allocate_properties(len(new_props))
            if isinstance(ids, int):
                ids = range(ids, ids + 1)
            prop_commit = UpsertCommit()
            for p, real_id in zip(new_props, ids):
                p.id = real_id
                prop_commit.properties[real_id] = Property(
                    id=real_id, dtype=p.dtype, mode=p.mode,
                    name=p.name, access='write', tag_list_id=real_id,
                    commit_id=0, operation=OP_CREATE,
                )
            self.project.apply_upsert_commit('import', prop_commit)
            print(f"[import] properties committed: {[p.name for p in new_props]}")

        from panoptic.core.databases.data.create import INSTANCES_SCHEMA

        print("[import] loading tag cache and sha1 map …")
        with self.project._data_reader() as reader:
            tag_cache: dict[int, dict[str, int]] = {}
            for t in reader.get_tags():
                if t.list_id is not None:
                    tag_cache.setdefault(t.list_id, {})[t.value] = t.id

            sha1_map: dict[int, str] = {}
            if any(p.mode == 'sha1' for p in working.values()):
                for inst_id, sha1 in INSTANCES_SCHEMA.select(reader.conn, ['id', 'sha1']):
                    if sha1:
                        sha1_map[inst_id] = sha1
        print(f"[import] sha1_map={len(sha1_map):,}  tag_cache lists={len(tag_cache):,}")

        pending         = UpsertCommit()
        pending_n       = 0
        total_committed = 0
        seen_sha1_pairs: set[tuple[int, str]] = set()

        def flush():
            nonlocal pending, pending_n, seen_sha1_pairs, total_committed
            if pending_n == 0:
                return
            self.project.apply_upsert_commit('import', pending)
            total_committed += pending_n
            print(f"[import]   flushed {pending_n:,} values  (total so far: {total_committed:,})")
            pending         = UpsertCommit()
            pending_n       = 0
            seen_sha1_pairs = set()

        prop_items = list(working.items())
        n_col_chunks = (len(prop_items) + _COL_BATCH - 1) // _COL_BATCH

        for chunk_idx, chunk_start in enumerate(range(0, len(prop_items), _COL_BATCH)):
            chunk     = prop_items[chunk_start: chunk_start + _COL_BATCH]
            col_names = [self.columns[col_i] for col_i, _ in chunk]
            print(f"[import] reading CSV chunk {chunk_idx+1}/{n_col_chunks}: {col_names} …")

            df_chunk = _read_csv(self.file_path, columns=col_names)
            if df_chunk is None:
                print(f"[import]   could not read chunk — skipping")
                continue

            for col_i, prop in chunk:
                col_name = self.columns[col_i]
                is_tag   = prop.dtype in _TAG_TYPES
                parse_fn = _PARSERS.get(prop.dtype, _PARSERS['text'])

                csv_values = df_chunk[col_name].to_list()
                print(f"[import]   processing '{prop.name}[{prop.dtype}]' ({len(csv_values):,} rows) …")

                for row_i, raw in enumerate(csv_values):
                    ids = self._row_to_ids[row_i] if row_i < len(self._row_to_ids) else []
                    if not ids:
                        continue

                    parsed = parse_fn(raw)
                    if parsed is None:
                        continue

                    if is_tag:
                        names   = parsed if isinstance(parsed, list) else [parsed]
                        list_id = prop.id
                        cache   = tag_cache.setdefault(list_id, {})
                        tag_ids = []
                        for name in names:
                            if name in cache:
                                tag_ids.append(cache[name])
                            else:
                                new_tid = self.project.allocate_tags(1)
                                if isinstance(new_tid, range):
                                    new_tid = new_tid.start
                                pending.tags[new_tid] = Tag(
                                    id=new_tid, list_id=list_id, parents=[],
                                    value=name, color=randint(0, 11),
                                    commit_id=0, operation=OP_CREATE,
                                )
                                cache[name] = new_tid
                                tag_ids.append(new_tid)
                        final_val = tag_ids
                    else:
                        final_val = parsed

                    for inst_id in ids:
                        if prop.mode == 'sha1':
                            sha1 = sha1_map.get(inst_id)
                            if sha1:
                                pair = (prop.id, sha1)
                                if pair in seen_sha1_pairs:
                                    continue
                                seen_sha1_pairs.add(pair)
                                pending.sha1_values.setdefault(prop.id, []).append(
                                    Sha1Value(property_id=prop.id, sha1=sha1,
                                              value=final_val, commit_id=0, operation=OP_UPDATE)
                                )
                                pending_n += 1
                        else:
                            pending.instance_values.setdefault(prop.id, []).append(
                                InstanceValue(property_id=prop.id, instance_id=inst_id,
                                              value=final_val, commit_id=0, operation=OP_UPDATE)
                            )
                            pending_n += 1

                    if pending_n >= BATCH:
                        flush()

            del df_chunk

        flush()
        print(f"[import] done — total values committed: {total_committed:,}")
        self._clear()

    # ------------------------------------------------------------------
    # Tag CSV import  (separate from the main CSV flow)
    # ------------------------------------------------------------------

    def import_tags(self, file_bytes: bytes, property_id: int):
        """Import tag hierarchy from a CSV with columns: name, color, parents."""
        try:
            df = pl.read_csv(
                io.BytesIO(file_bytes),
                separator=';',
                encoding='utf-8',
                has_header=False,
                new_columns=['name', 'color', 'parents'],
                infer_schema=False,
            )
        except Exception as e:
            raise ValueError(f"Failed to parse tags CSV: {e}")

        existing   = {t.value: t for t in self.project.get_tags() if t.list_id == property_id}
        name_to_id: dict[str, int] = {v: t.id for v, t in existing.items()}
        new_tags:   list[Tag] = []

        # Pass 1: allocate IDs for new tags
        rows = list(df.iter_rows(named=True))
        for row in rows:
            name = (row['name'] or '').strip()
            if not name or name in name_to_id:
                continue
            raw_color = (row['color'] or '').strip()
            try:
                color = max(0, min(11, int(raw_color)))
            except (ValueError, TypeError):
                color = randint(1, 12)
            new_id = self.project.allocate_tags(1)
            if isinstance(new_id, range):
                new_id = new_id.start
            new_tags.append(Tag(id=new_id, list_id=property_id, parents=[],
                                value=name, color=color, commit_id=0, operation=OP_CREATE))
            name_to_id[name] = new_id

        # Pass 2: resolve parent references
        tags_with_parents: list[Tag] = []
        for i, row in enumerate(rows):
            name = (row['name'] or '').strip()
            if not name:
                continue
            tag_id = name_to_id.get(name)
            if tag_id is None:
                continue
            raw_parents = (row['parents'] or '').strip()
            parent_ids  = [name_to_id[p.strip()] for p in raw_parents.split(',')
                           if p.strip() and p.strip() in name_to_id] if raw_parents else []

            if name in existing:
                orig = existing[name]
                tags_with_parents.append(
                    Tag(id=orig.id, list_id=orig.list_id, parents=parent_ids,
                        value=orig.value, color=orig.color, commit_id=0, operation=OP_UPDATE)
                )
            else:
                for j, t in enumerate(new_tags):
                    if t.id == tag_id:
                        new_tags[j] = Tag(id=t.id, list_id=t.list_id, parents=parent_ids,
                                          value=t.value, color=t.color,
                                          commit_id=0, operation=t.operation)
                        break

        all_tags = new_tags + tags_with_parents
        if all_tags:
            commit = UpsertCommit()
            for t in all_tags:
                commit.tags[t.id] = t
            self.project.apply_upsert_commit('import', commit)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _clear(self):
        self.file_path    = ''
        self.columns      = []
        self.file_key     = None
        self.col_to_prop  = {}
        self._row_to_ids  = []
        self._new_inst_info = []
