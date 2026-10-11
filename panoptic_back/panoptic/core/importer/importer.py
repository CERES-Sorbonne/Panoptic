"""CSV importer for Panoptic V2.

Stateful: call parse_headers → verify_mapping → start_import (or import_data_and_commit)
in order.
"""
from __future__ import annotations

import csv
import io
import os
import uuid
from array import array
from contextlib import closing
from itertools import islice
from dataclasses import dataclass
from pathlib import Path
from random import randint
from typing import Any, Iterator, TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from panoptic.core.project.project import Project
    from panoptic.core.task.task import Task

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

# Values written per commit. Rows are read from the CSV one commit at a time, so this
# also bounds the memory the import uses.
_COMMIT_VALUES = 25_000

# Row with no instance to write to, in Importer._row_ids
_NO_INSTANCE = -1

# Long text cells must not abort the import (the csv module refuses cells over 128 KB)
csv.field_size_limit(2**31 - 1)

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


def _iter_rows(file_path: str) -> Iterator[list[str]]:
    """Stream the CSV's data rows (header skipped), one list of cells per row.

    Both verify_mapping and the import read rows with this, so row numbers always agree.
    """
    with open(file_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=';')
        next(reader, None)
        yield from reader


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

def _allocate(allocate, n: int) -> range:
    """Allocate n ids with one of Project's allocate_* methods, as a range."""
    ids = allocate(n)
    return ids if isinstance(ids, range) else range(ids, ids + 1)


class Importer:
    """Stateful CSV importer for Project.

    Usage::

        importer = project.importer
        confirm  = importer.parse_headers('/path/to/file.csv')
        verify   = importer.verify_mapping(relative=False, fusion='new')
        task     = importer.start_import()   # or importer.import_data_and_commit()
    """

    def __init__(self, project: 'Project'):
        self.project = project
        self.file_path: str = ''
        self.columns:   list[str] = []
        self.file_key:  str | None = None
        self.col_to_prop: dict[int, ImportProp] = {}
        # Instance written by each CSV row, _NO_INSTANCE when none
        self._row_ids:         array = array('q')
        self._new_inst_info:   list[tuple[int, int, str]] = []   # (file_id, inst_id, sha1)
        # CSV saved by upload() that no import has taken over yet
        self._upload_path: str | None = None

    # ------------------------------------------------------------------
    # Step 0 (optional): save an uploaded CSV
    # ------------------------------------------------------------------

    def upload(self, file_name: str, content: bytes) -> dict:
        """Save an uploaded CSV in the project folder, then parse its headers.

        Each upload gets its own folder and is deleted once imported, so an import still
        reading its CSV is not affected by a later upload of a file with the same name.
        """
        self._discard_upload()
        path = self.project.folder / 'imports' / uuid.uuid4().hex / (Path(file_name).name or 'import.csv')
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
        self._upload_path = str(path)
        return self.parse_headers(self._upload_path)

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

        key_data = [row[0] if row else '' for row in _iter_rows(self.file_path)]
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
        row_ids = array('q', [_NO_INSTANCE]) * len(initial)
        to_copy: list[tuple[int, int]] = []   # (row, instance the row's new instance copies)

        for row, matches in enumerate(initial):
            if not matches:
                continue
            if fusion == 'last':
                row_ids[row] = matches[-1]
            elif fusion == 'new':
                free_id = next((m for m in matches if m not in non_empty_ids and m not in used_ids), None)
                if free_id is not None:
                    used_ids.add(free_id)
                    row_ids[row] = free_id
                elif self.file_key == 'path':
                    to_copy.append((row, matches[0]))
            else:
                row_ids[row] = matches[0]

        new_inst_info: list[tuple[int, int, str]] = []
        if to_copy:
            for (row, orig), new_id in zip(to_copy, _allocate(self.project.allocate_instances, len(to_copy))):
                orig_sha1, orig_file_id = instances[orig]
                row_ids[row] = new_id
                new_inst_info.append((orig_file_id or 0, new_id, orig_sha1 or ''))

        self._row_ids       = row_ids
        self._new_inst_info = new_inst_info

        missing = [[i, key_data[i]] for i, inst_id in enumerate(row_ids) if inst_id == _NO_INSTANCE]
        print(f"[import] verify_mapping done  mapped={len(row_ids)-len(missing):,}  missing={len(missing):,}  new_instances={len(new_inst_info):,}")
        return {'missing_rows': missing, 'new_instances_count': len(new_inst_info)}

    # ------------------------------------------------------------------
    # Step 3: read CSV data and commit to DB
    # ------------------------------------------------------------------

    def start_import(self, exclude: list[int] | None = None,
                     properties: dict[str, dict] | None = None) -> 'Task':
        """Queue the import of the verified CSV as a background task and return the task."""
        from panoptic.core.task.import_csv_task import ImportCsvTask
        return self.project.add_task(ImportCsvTask(self._take_import(exclude, properties)))

    def import_data_and_commit(self, exclude: list[int] | None = None,
                                properties: dict[str, dict] | None = None):
        """Import the verified CSV in the calling thread."""
        for _ in self._take_import(exclude, properties).run():
            pass

    def _take_import(self, exclude: list[int] | None,
                     properties: dict[str, dict] | None) -> 'CsvImport':
        """Hand the session over to a CsvImport, and clear it so another import can start."""
        if not self.columns or not self.col_to_prop:
            raise ValueError("Call parse_headers and verify_mapping first")

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

        owns_file = self.file_path == self._upload_path
        job = CsvImport(self.project, self.file_path, working, self._row_ids,
                        self._new_inst_info, delete_file=owns_file)
        if owns_file:
            self._upload_path = None
        self._clear()
        return job

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
        self._row_ids     = array('q')
        self._new_inst_info = []

    def _discard_upload(self):
        """Delete the uploaded CSV no import has taken over."""
        if self._upload_path:
            _delete_upload(self._upload_path)
            self._upload_path = None


def _delete_upload(path: str):
    """Delete a CSV saved by Importer.upload, with the folder made for it."""
    p = Path(path)
    p.unlink(missing_ok=True)
    try:
        p.parent.rmdir()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Import job
# ---------------------------------------------------------------------------

class CsvImport:
    """Writes one verified CSV into the project. Built by Importer, run by ImportCsvTask.

    Rows are streamed from the CSV and committed every _COMMIT_VALUES values, so memory
    does not grow with the file. Each commit is applied as soon as it is built: an import
    that stops early keeps the rows it already wrote.
    """

    def __init__(self, project: 'Project', file_path: str, props: dict[int, ImportProp],
                 row_ids: array, new_instances: list[tuple[int, int, str]],
                 delete_file: bool = False):
        self.project       = project
        self.file_path     = file_path
        self.name          = Path(file_path).name
        self.props         = props           # CSV column index -> property
        self.row_ids       = row_ids
        self.new_instances = new_instances
        self.delete_file   = delete_file     # the CSV is an upload, delete it once done

    @property
    def n_rows(self) -> int:
        return len(self.row_ids)

    def run(self) -> Iterator[tuple[int, int]]:
        """Import the CSV, yielding (rows done, cells that failed to parse) after each commit.

        Stop iterating to stop the import.
        """
        try:
            yield from self._run()
        finally:
            if self.delete_file:
                _delete_upload(self.file_path)

    def _run(self) -> Iterator[tuple[int, int]]:
        project = self.project
        props   = self.props
        if not props:
            print("[import] no columns to import — aborting")
            return

        print(f"[import] importing {self.n_rows:,} rows, columns: "
              f"{[f'{p.name}[{p.dtype}]/{p.mode}' for p in props.values()]}")

        if self.new_instances:
            print(f"[import] committing {len(self.new_instances):,} new instances …")
            inst_commit = UpsertCommit()
            for file_id, inst_id, sha1 in self.new_instances:
                inst_commit.instances[inst_id] = Instance(id=inst_id, file_id=file_id, sha1=sha1)
            project.apply_upsert_commit('import', inst_commit)

        new_props = [p for p in props.values() if p.id < 0]
        if new_props:
            prop_commit = UpsertCommit()
            for p, real_id in zip(new_props, _allocate(project.allocate_properties, len(new_props))):
                p.id = real_id
                prop_commit.properties[real_id] = Property(
                    id=real_id, dtype=p.dtype, mode=p.mode,
                    name=p.name, access='write', tag_list_id=real_id,
                    commit_id=0, operation=OP_CREATE,
                )
            project.apply_upsert_commit('import', prop_commit)
            print(f"[import] properties created: {[p.name for p in new_props]}")

        from panoptic.core.databases.data.create import INSTANCES_SCHEMA

        with project._data_reader() as reader:
            # list id -> tag value -> tag id
            tag_cache: dict[int, dict[str, int]] = {}
            for t in reader.get_tags():
                if t.list_id is not None:
                    tag_cache.setdefault(t.list_id, {})[t.value] = t.id

            # sha1 of each row's instance, as an index in sha1s (-1 when none)
            row_sha1 = array('q', [-1]) * self.n_rows
            sha1s: list[str] = []
            if any(p.mode == 'sha1' for p in props.values()):
                inst_sha1 = dict(INSTANCES_SCHEMA.select(reader.conn, ['id', 'sha1']))
                sha1_index: dict[str, int] = {}
                for row, inst_id in enumerate(self.row_ids):
                    sha1 = inst_sha1.get(inst_id) if inst_id != _NO_INSTANCE else None
                    if sha1:
                        i = sha1_index.setdefault(sha1, len(sha1s))
                        if i == len(sha1s):
                            sha1s.append(sha1)
                        row_sha1[row] = i
                del inst_sha1, sha1_index

        # Per sha1-mode property, the images that already got a value: the first row
        # with a value wins when several rows share an image.
        seen = {p.id: bytearray(len(sha1s)) for p in props.values() if p.mode == 'sha1'}
        columns = [(col, prop, _PARSERS.get(prop.dtype, _PARSERS['text']))
                   for col, prop in props.items()]
        rows_per_commit = max(1, _COMMIT_VALUES // len(columns))

        done = failed = written = 0
        # Closed even when the import stops early, so the upload can then be deleted
        with closing(_iter_rows(self.file_path)) as rows:
            while batch := list(islice(rows, rows_per_commit)):
                commit, n_values, n_failed = self._build_commit(
                    done, batch, columns, tag_cache, row_sha1, sha1s, seen)
                if n_values:
                    project.apply_upsert_commit('import', commit)
                done    += len(batch)
                failed  += n_failed
                written += n_values
                yield done, failed

        print(f"[import] done — {written:,} values written, {failed:,} cells failed to parse")

    def _build_commit(self, start: int, batch: list[list[str]], columns: list[tuple],
                      tag_cache: dict[int, dict[str, int]], row_sha1: array, sha1s: list[str],
                      seen: dict[int, bytearray]) -> tuple[UpsertCommit, int, int]:
        """Commit of the values in ``batch``, the rows starting at row ``start``.

        Returns (commit, number of values, number of cells that failed to parse).
        """
        # Parse every cell first, so the new tags of the batch get their ids in one allocation
        cells: list[tuple[ImportProp, int, int, Any]] = []   # (prop, instance, sha1 index, value)
        new_tags: dict[tuple[int, str], None] = {}           # (list id, tag value)
        failed = 0
        for row, cells_row in enumerate(batch, start):
            inst_id = self.row_ids[row] if row < self.n_rows else _NO_INSTANCE
            if inst_id == _NO_INSTANCE:
                continue
            for col, prop, parse in columns:
                try:
                    value = parse(cells_row[col] if col < len(cells_row) else '')
                except ValueError:
                    failed += 1
                    continue
                if value is None:
                    continue
                sha1 = row_sha1[row]
                if prop.mode == 'sha1':
                    if sha1 < 0 or seen[prop.id][sha1]:
                        continue
                    seen[prop.id][sha1] = 1
                if prop.dtype in _TAG_TYPES:
                    known = tag_cache.get(prop.id, {})
                    for name in value:
                        if name not in known:
                            new_tags[(prop.id, name)] = None
                cells.append((prop, inst_id, sha1, value))

        commit = UpsertCommit()
        if new_tags:
            for (list_id, name), tag_id in zip(new_tags, _allocate(self.project.allocate_tags, len(new_tags))):
                commit.tags[tag_id] = Tag(
                    id=tag_id, list_id=list_id, parents=[],
                    value=name, color=randint(0, 11),
                    commit_id=0, operation=OP_CREATE,
                )
                tag_cache.setdefault(list_id, {})[name] = tag_id

        for prop, inst_id, sha1, value in cells:
            if prop.dtype in _TAG_TYPES:
                value = [tag_cache[prop.id][name] for name in value]
            if prop.mode == 'sha1':
                commit.sha1_values.setdefault(prop.id, []).append(
                    Sha1Value(property_id=prop.id, sha1=sha1s[sha1],
                              value=value, commit_id=0, operation=OP_UPDATE))
            else:
                commit.instance_values.setdefault(prop.id, []).append(
                    InstanceValue(property_id=prop.id, instance_id=inst_id,
                                  value=value, commit_id=0, operation=OP_UPDATE))
        return commit, len(cells), failed
