"""CSV importer for Panoptic V2.

Stateful: call parse_headers → verify_mapping → import_data_and_commit in order.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from random import randint
from typing import Any, TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from panoptic2.core.project.project import Project2

from panoptic2.core.databases.data.models import (
    Instance, Property, Tag, InstanceValue, Sha1Value, UpsertCommit,
)
from panoptic2.core.databases.entity_schema import OP_CREATE, OP_UPDATE


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
# Tiny path trie for fuzzy / relative path matching
# ---------------------------------------------------------------------------

class _TrieNode:
    __slots__ = ('children', 'ids')
    def __init__(self):
        self.children: dict[str, _TrieNode] = {}
        self.ids: list[int] = []


class _PathTrie:
    def __init__(self):
        self._root = _TrieNode()

    def insert(self, path: str, id_: int):
        node = self._root
        for ch in path:
            node = node.children.setdefault(ch, _TrieNode())
        node.ids.append(id_)

    def exact(self, path: str) -> list[int]:
        node = self._root
        for ch in path:
            if ch not in node.children:
                return []
            node = node.children[ch]
        return node.ids

    def prefix(self, path: str) -> list[int]:
        """Return all ids whose stored key starts with *path* (suffix search)."""
        node = self._root
        for ch in path:
            if ch not in node.children:
                return []
            node = node.children[ch]
        result: list[int] = []
        stack = [node]
        while stack:
            n = stack.pop()
            result.extend(n.ids)
            stack.extend(n.children.values())
        return result

    @staticmethod
    def _norm(path: str) -> str:
        p = path.replace('\\', '/')
        if not p.startswith('/'):
            p = '/' + p
        return p[::-1]   # store reversed for suffix-as-prefix search

    def insert_path(self, path: str, id_: int):
        self.insert(self._norm(path), id_)

    def search_absolute(self, path: str) -> list[int]:
        return self.exact(self._norm(path))

    def search_relative(self, path: str) -> list[int]:
        return self.prefix(self._norm(path))


# ---------------------------------------------------------------------------
# Importer2
# ---------------------------------------------------------------------------

class Importer2:
    """Stateful CSV importer for Project2.

    Usage::

        importer = project.importer
        confirm  = importer.parse_headers('/path/to/file.csv')
        verify   = importer.verify_mapping(relative=False, fusion='new')
        importer.import_data_and_commit()
    """

    def __init__(self, project: 'Project2'):
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
                str(i): {'id': p.id, 'name': p.name, 'dtype': p.dtype, 'mode': p.mode}
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

        df = _read_csv(self.file_path, columns=[self.file_key])
        if df is None:
            raise IOError("Cannot read key column from CSV")

        key_data  = df[self.file_key].to_list()
        instances = self.project.get_instances()
        files     = {f.id: f for f in self.project.get_files()}
        inst_map  = {i.id: i for i in instances}

        # Determine which instance ids have at least one value (for fusion='new')
        non_empty_ids: set[int] = set()
        used_ids:      set[int] = set()
        if fusion == 'new':
            non_empty_ids = {v.instance_id for v in self.project.get_instance_values()}

        # Build initial row→ids mapping
        initial: list[list[int]] = []

        if self.file_key == 'id':
            all_ids = {i.id for i in instances}
            for val in key_data:
                try:
                    n = int(val)
                    initial.append([n] if n in all_ids else [])
                except (ValueError, TypeError):
                    initial.append([])

        else:  # 'path'
            trie = _PathTrie()
            for inst in instances:
                f = files.get(inst.file_id)
                if f and f.name:
                    trie.insert_path(f.name, inst.id)

            search = trie.search_relative if relative else trie.search_absolute
            for val in key_data:
                initial.append(search(val) if val else [])

        # Apply fusion mode
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
                        orig   = inst_map[matches[0]]
                        new_id = self.project.allocate_instances(1)
                        if isinstance(new_id, range):
                            new_id = new_id.start
                        row_to_ids.append([new_id])
                        new_inst_info.append((orig.file_id or 0, new_id, orig.sha1 or ''))
                    else:
                        row_to_ids.append([])
                else:
                    row_to_ids.append([])
            else:
                row_to_ids.append([matches[0]] if matches else [])

        self._row_to_ids  = row_to_ids
        self._new_inst_info = new_inst_info

        missing = [i for i, ids in enumerate(row_to_ids) if not ids]
        return {'missing_rows': missing, 'new_instances_count': len(new_inst_info)}

    # ------------------------------------------------------------------
    # Step 3: read CSV data and commit to DB
    # ------------------------------------------------------------------

    def import_data_and_commit(self, exclude: list[int] | None = None,
                                properties: dict[str, dict] | None = None):
        if not self.columns or not self.col_to_prop:
            raise ValueError("Call parse_headers and verify_mapping first")

        BATCH = 25_000
        exclude_set = set(exclude or [])

        # Build working column→prop map with optional user overrides
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
            return

        # Commit new instances (IDs already pre-allocated in verify_mapping)
        if self._new_inst_info:
            inst_commit = UpsertCommit()
            for file_id, inst_id, sha1 in self._new_inst_info:
                inst_commit.instances[inst_id] = Instance(
                    id=inst_id, file_id=file_id, sha1=sha1,
                    commit_id=0, operation=OP_CREATE,
                )
            self.project.apply_upsert_commit('import', inst_commit)

        # Commit new properties (allocate real IDs)
        prop_id_map: dict[int, int] = {}
        new_props = [p for p in working.values() if p.id < 0]
        if new_props:
            ids = self.project.allocate_properties(len(new_props))
            if isinstance(ids, int):
                ids = range(ids, ids + 1)
            prop_commit = UpsertCommit()
            for p, real_id in zip(new_props, ids):
                prop_id_map[p.id] = real_id
                p.id = real_id
                prop_commit.properties[real_id] = Property(
                    id=real_id, dtype=p.dtype, mode=p.mode,
                    name=p.name, access='write', tag_list_id=real_id,
                    commit_id=0, operation=OP_CREATE,
                )
            self.project.apply_upsert_commit('import', prop_commit)

        # Pre-load tag cache for existing tag properties
        tag_cache: dict[int, dict[str, int]] = {}   # list_id → {value: tag_id}
        for p in working.values():
            if p.dtype in _TAG_TYPES and p.id > 0:
                tag_cache[p.id] = {
                    t.value: t.id
                    for t in self.project.get_tags()
                    if t.list_id == p.id
                }

        # Build sha1 map once if any sha1-mode columns
        sha1_map: dict[int, str] = {}
        if any(p.mode == 'sha1' for p in working.values()):
            sha1_map = {i.id: i.sha1 for i in self.project.get_instances() if i.sha1}

        pending = UpsertCommit()
        pending_n = 0

        def flush():
            nonlocal pending, pending_n
            if pending_n == 0:
                return
            self.project.apply_upsert_commit('import', pending)
            pending = UpsertCommit()
            pending_n = 0

        for col_i, prop in working.items():
            col_name = self.columns[col_i]
            is_tag   = prop.dtype in _TAG_TYPES
            parse_fn = _PARSERS.get(prop.dtype, _PARSERS['text'])

            df_col = _read_csv(self.file_path, columns=[col_name])
            if df_col is None:
                continue

            csv_values = df_col[col_name].to_list()

            for row_i, raw in enumerate(csv_values):
                ids = self._row_to_ids[row_i] if row_i < len(self._row_to_ids) else []
                if not ids:
                    continue

                parsed = parse_fn(raw)
                if parsed is None:
                    continue

                if is_tag:
                    names = parsed if isinstance(parsed, list) else [parsed]
                    list_id = prop.id
                    if list_id not in tag_cache:
                        tag_cache[list_id] = {}
                    tag_ids = []
                    for name in names:
                        if name in tag_cache[list_id]:
                            tag_ids.append(tag_cache[list_id][name])
                        else:
                            new_tid = self.project.allocate_tags(1)
                            if isinstance(new_tid, range):
                                new_tid = new_tid.start
                            pending.tags[new_tid] = Tag(
                                id=new_tid, list_id=list_id, parents=[],
                                value=name, color=randint(0, 11),
                                commit_id=0, operation=OP_CREATE,
                            )
                            tag_cache[list_id][name] = new_tid
                            tag_ids.append(new_tid)
                    final_val = tag_ids
                else:
                    final_val = parsed

                for inst_id in ids:
                    if prop.mode == 'sha1':
                        sha1 = sha1_map.get(inst_id)
                        if sha1:
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

            del df_col

        flush()
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
