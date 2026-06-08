"""Project-level routes — prefixed /projects/{project_id}."""
from __future__ import annotations

import logging
import orjson
from sys import platform
from typing import Any, Optional

import msgspec
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

from panoptic.core.databases.data.models import (
    Commit, DataCommit, DeleteCommit, FileValue, Folder, Instance, Property, PropertyGroup, Sha1Value,
    Tag, InstanceValue, UpsertCommit, File, FileSource,
)
from panoptic.models.models import ProjectSettings
from panoptic.core.project.project import Project
from panoptic.models.action_models import ActionContext
from panoptic.models.stream_models import (
    FileValuesColumn, FullInstance, ImageValuesColumn, InstanceValuesColumn,
    LoadState, StreamChunk, StreamResult, TagCount,
)
from panoptic.core.databases.entity_schema import OP_CREATE, OP_DELETE
from panoptic.core.databases.data.create import (
    FILES_SCHEMA, INSTANCES_SCHEMA, INSTANCE_TAG_VALUES_SCHEMA, SHA1_TAG_VALUES_SCHEMA,
    INSTANCE_VALUES_SCHEMA, SHA1_VALUES_SCHEMA, FILE_VALUES_SCHEMA,
)
from panoptic.routes.deps import get_project

project_router = APIRouter(prefix='/projects/{project_id}')

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json(obj) -> Response:
    return Response(msgspec.json.encode(obj), media_type='application/json')


def _dumps(v) -> str:
    """JSON-encode a single column value to a string. Uses orjson so datetimes (e.g. the
    created_at system column) serialize to ISO strings instead of raising."""
    return orjson.dumps(v, option=orjson.OPT_SERIALIZE_NUMPY).decode()


def _dep(project_id: str) -> Project:
    return get_project(project_id)


_TRACKING_FIELDS = frozenset({'commit_id', 'operation'})

def _db_to_dict(obj: msgspec.Struct) -> dict:
    """Convert a DB model (array_like Struct) to a plain dict, dropping tracking fields."""
    return {
        f.name: getattr(obj, f.name)
        for f in msgspec.structs.fields(obj)
        if f.name not in _TRACKING_FIELDS
    }


# ---------------------------------------------------------------------------
# State — initial full load (ndjson stream)
# ---------------------------------------------------------------------------

_STREAM_BATCH = 10_000


def _structural_chunks(project: Project):
    """Yield NDJSON bytes for properties, tags, and instances (no values).

    Shared by both db_state_stream and db_state_slim.
    Yields (bytes, n_inst) on the final instance batch; all earlier yields are bytes.
    The caller receives n_inst via the StopIteration return value:
        n_inst = yield from _structural_chunks(project)
    """
    import os as _os

    properties = project.get_properties()
    property_groups = project.get_property_groups()
    yield msgspec.json.encode(StreamResult(
        chunk=StreamChunk(
            properties=[_db_to_dict(p) for p in properties],
            property_groups=[_db_to_dict(g) for g in property_groups],
        ),
        state=LoadState(finished_property=True, finished_property_groups=True),
    )) + b'\n'

    tags = project.get_tags()
    yield msgspec.json.encode(StreamResult(
        chunk=StreamChunk(tags=[_db_to_dict(t) for t in tags]),
        state=LoadState(finished_property=True, finished_property_groups=True, finished_tags=True),
    )) + b'\n'

    files     = project.get_files()
    instances = project.get_instances()
    n_inst    = len(instances)
    file_map  = {f.id: f for f in files}
    counter   = 0
    for batch_start in range(0, max(n_inst, 1), _STREAM_BATCH):
        batch = instances[batch_start:batch_start + _STREAM_BATCH]
        stream_instances = []
        for inst in batch:
            f         = file_map.get(inst.file_id)
            full_name = (f.name or '') if f else ''
            basename  = _os.path.basename(full_name)
            extension = _os.path.splitext(basename)[1].lstrip('.')
            stream_instances.append(FullInstance(
                id=inst.id,
                sha1=inst.sha1,
                name=basename,
                ahash='',
                width=f.width or 0 if f else 0,
                height=f.height or 0 if f else 0,
                url=full_name,
                folder_id=f.folder_id if f else None,
                file_id=inst.file_id,
                extension=extension,
                properties={},
            ))
        counter += len(batch)
        yield msgspec.json.encode(StreamResult(
            chunk=StreamChunk(instances=stream_instances),
            state=LoadState(
                max_instance=n_inst,
                finished_property=True,
                finished_property_groups=True,
                finished_tags=True,
                finished_instance=counter >= n_inst,
                counter_instance=counter,
            ),
        )) + b'\n'

    return n_inst


@project_router.get('/db_state_slim')
def stream_db_state_slim(project: Project = Depends(_dep)):
    """Stream structural project state (properties + instances, no values) as NDJSON.

    Used by dataStore2 to build the slot map. Completes in one pass without
    touching value tables, so it finishes much faster on large projects.
    """
    def _generate():
        with project._data_reader() as _sr:
            start_sequence = _sr.get_next_sequence() - 1

        n_inst = yield from _structural_chunks(project)

        yield msgspec.json.encode(StreamResult(
            state=LoadState(
                max_instance=n_inst,
                finished_property=True, finished_property_groups=True,
                finished_tags=True, finished_instance=True,
                finished_instance_values=True, finished_image_values=True,
                finished_file_values=True,
                counter_instance=n_inst,
                max_sequence=start_sequence,
            ),
        )) + b'\n'

    return StreamingResponse(_generate(), media_type='application/x-ndjson')


@project_router.get('/db_state_stream')
def stream_db_state(project: Project = Depends(_dep)):
    """Stream full project state as newline-delimited JSON LoadResult chunks."""
    import json as _json

    def _generate():
        # Capture sequence BEFORE entity reads so any concurrent write during the
        # stream is caught by the first delta call (duplicates are idempotent).
        with project._data_reader() as _sr:
            start_sequence = _sr.get_next_sequence() - 1

        n_inst = yield from _structural_chunks(project)

        # ---- Values: streamed in batches via fetchmany (single scan per table) ----
        # COUNT(*) is O(1) in SQLite and gives us the max for the progress bars.
        # iter_*_values() uses cursor.fetchmany() — one SELECT, no rescanning.
        # Each value is re-encoded as a JSON string because the frontend
        # calls JSON.parse() on every entry (matching the v1 wire format).
        with project._data_reader() as reader:
            n_iv = reader.count_instance_values()
            n_sv = reader.count_sha1_values()
            n_fv = reader.count_file_values()

            iv_counter = 0
            for batch in reader.iter_instance_values(_STREAM_BATCH):
                iv_cols: dict[int, InstanceValuesColumn] = {}
                for iv in batch:
                    col = iv_cols.setdefault(iv.property_id, InstanceValuesColumn(iv.property_id, [], []))
                    col.ids.append(iv.instance_id)
                    col.values.append(_dumps(iv.value))
                iv_counter += len(batch)
                yield msgspec.json.encode(StreamResult(
                    instance_values=list(iv_cols.values()),
                    state=LoadState(
                        max_instance=n_inst, max_instance_value=n_iv,
                        max_image_value=n_sv, max_file_value=n_fv,
                        finished_property=True, finished_property_groups=True,
                        finished_tags=True, finished_instance=True,
                        finished_instance_values=iv_counter >= n_iv,
                        counter_instance=n_inst, counter_instance_value=iv_counter,
                    ),
                )) + b'\n'

            sv_counter = 0
            for batch in reader.iter_sha1_values(_STREAM_BATCH):
                sv_cols: dict[int, ImageValuesColumn] = {}
                for sv in batch:
                    col = sv_cols.setdefault(sv.property_id, ImageValuesColumn(sv.property_id, [], []))
                    col.sha1s.append(sv.sha1)
                    col.values.append(_dumps(sv.value))
                sv_counter += len(batch)
                yield msgspec.json.encode(StreamResult(
                    image_values=list(sv_cols.values()),
                    state=LoadState(
                        max_instance=n_inst, max_instance_value=n_iv,
                        max_image_value=n_sv, max_file_value=n_fv,
                        finished_property=True, finished_property_groups=True,
                        finished_tags=True, finished_instance=True,
                        finished_instance_values=True,
                        finished_image_values=sv_counter >= n_sv,
                        counter_instance=n_inst, counter_instance_value=n_iv,
                        counter_image_value=sv_counter,
                    ),
                )) + b'\n'

            fv_counter = 0
            for batch in reader.iter_file_values(_STREAM_BATCH):
                fv_cols: dict[int, FileValuesColumn] = {}
                for fv in batch:
                    col = fv_cols.setdefault(fv.property_id, FileValuesColumn(fv.property_id, [], []))
                    col.file_ids.append(fv.file_id)
                    col.values.append(_dumps(fv.value))
                fv_counter += len(batch)
                yield msgspec.json.encode(StreamResult(
                    file_values=list(fv_cols.values()),
                    state=LoadState(
                        max_instance=n_inst, max_instance_value=n_iv,
                        max_image_value=n_sv, max_file_value=n_fv,
                        finished_property=True, finished_property_groups=True,
                        finished_tags=True, finished_instance=True,
                        finished_instance_values=True, finished_image_values=True,
                        finished_file_values=fv_counter >= n_fv,
                        counter_instance=n_inst, counter_instance_value=n_iv,
                        counter_image_value=n_sv, counter_file_value=fv_counter,
                        max_sequence=start_sequence,
                    ),
                )) + b'\n'

        # Always emit a final chunk so the frontend unblocks even when all value
        # tables are empty and none of the iter_* loops above executed.
        yield msgspec.json.encode(StreamResult(
            state=LoadState(
                max_instance=n_inst, max_instance_value=n_iv,
                max_image_value=n_sv, max_file_value=n_fv,
                finished_property=True, finished_property_groups=True,
                finished_tags=True, finished_instance=True,
                finished_instance_values=True, finished_image_values=True,
                finished_file_values=True,
                counter_instance=n_inst, counter_instance_value=n_iv,
                counter_image_value=n_sv, counter_file_value=n_fv,
                max_sequence=start_sequence,
            ),
        )) + b'\n'

    return StreamingResponse(_generate(), media_type='application/x-ndjson')


@project_router.get('/delta')
def get_delta(
    since: int,
    full_prop_ids: str | None = None,
    point_prop_ids: str | None = None,
    instance_ids: str | None = None,
    project: Project = Depends(_dep),
):
    """Return all rows changed since `since` as a single StreamResult JSON response.

    Optional filter params (comma-separated integers):
    - full_prop_ids:  return value changes for ALL instances for these property IDs
    - point_prop_ids: return value changes only for the supplied instance_ids
    - instance_ids:   instance IDs used as the filter for point_prop_ids
    """
    import json as _json
    import os as _os

    def _parse(s: str | None) -> list[int] | None:
        return [int(x) for x in s.split(',') if x] if s else None

    with project._data_reader() as reader:
        raw = reader.get_delta(
            since,
            full_prop_ids=_parse(full_prop_ids),
            point_prop_ids=_parse(point_prop_ids),
            instance_ids=_parse(instance_ids),
        )

    sequence  = raw['sequence']
    file_map  = {f.id: f for f in raw['files']}

    # Split entities into upserts vs deletes. Instances are structural (not logged): they
    # carry no `operation` and are never delta-deleted — a structural delete triggers a
    # full frontend reload instead — so every streamed instance is an upsert.
    upsert_instances  = list(raw['instances'])
    delete_instances  = []
    upsert_properties = [x for x in raw['properties']        if x.operation != OP_DELETE]
    delete_properties = [x.id for x in raw['properties']     if x.operation == OP_DELETE]
    upsert_tags       = [x for x in raw['tags']               if x.operation != OP_DELETE]
    delete_tags       = [x.id for x in raw['tags']            if x.operation == OP_DELETE]
    upsert_groups     = [x for x in raw['property_groups']   if x.operation != OP_DELETE]
    delete_groups     = [x.id for x in raw['property_groups'] if x.operation == OP_DELETE]

    upsert_iv = [x for x in raw['instance_values'] if x.operation != OP_DELETE]
    delete_iv = [{'property_id': x.property_id, 'instance_id': x.instance_id}
                 for x in raw['instance_values'] if x.operation == OP_DELETE]

    upsert_sv = [x for x in raw['image_values'] if x.operation != OP_DELETE]
    delete_sv = [{'property_id': x.property_id, 'sha1': x.sha1}
                 for x in raw['image_values'] if x.operation == OP_DELETE]

    upsert_fv = [x for x in raw['file_values'] if x.operation != OP_DELETE]
    delete_fv = [{'property_id': x.property_id, 'file_id': x.file_id}
                 for x in raw['file_values'] if x.operation == OP_DELETE]

    # Build FullInstances for upserted instances
    full_instances = []
    for inst in upsert_instances:
        f         = file_map.get(inst.file_id)
        full_name = (f.name or '') if f else ''
        basename  = _os.path.basename(full_name)
        extension = _os.path.splitext(basename)[1].lstrip('.')
        full_instances.append(FullInstance(
            id=inst.id,
            sha1=inst.sha1,
            name=basename,
            ahash='',
            width=f.width or 0 if f else 0,
            height=f.height or 0 if f else 0,
            url=full_name,
            folder_id=f.folder_id if f else None,
            file_id=inst.file_id,
            extension=extension,
            properties={},
        ))

    # Build columnar value structs for upserted values
    iv_cols: dict[int, InstanceValuesColumn] = {}
    for iv in upsert_iv:
        col = iv_cols.setdefault(iv.property_id, InstanceValuesColumn(iv.property_id, [], []))
        col.ids.append(iv.instance_id)
        col.values.append(_dumps(iv.value))

    sv_cols: dict[int, ImageValuesColumn] = {}
    for sv in upsert_sv:
        col = sv_cols.setdefault(sv.property_id, ImageValuesColumn(sv.property_id, [], []))
        col.sha1s.append(sv.sha1)
        col.values.append(_dumps(sv.value))

    fv_cols: dict[int, FileValuesColumn] = {}
    for fv in upsert_fv:
        col = fv_cols.setdefault(fv.property_id, FileValuesColumn(fv.property_id, [], []))
        col.file_ids.append(fv.file_id)
        col.values.append(_dumps(fv.value))

    all_finished = LoadState(
        finished_property=True, finished_instance=True, finished_tags=True,
        finished_instance_values=True, finished_image_values=True,
        finished_file_values=True, finished_property_groups=True,
        max_sequence=sequence,
    )
    result = StreamResult(
        state=all_finished,
        chunk=StreamChunk(
            instances=full_instances or None,
            properties=[_db_to_dict(p) for p in upsert_properties] or None,
            tags=[_db_to_dict(t) for t in upsert_tags] or None,
            property_groups=[_db_to_dict(g) for g in upsert_groups] or None,
            empty_instances=delete_instances or None,
            empty_properties=delete_properties or None,
            empty_tags=delete_tags or None,
            empty_property_groups=delete_groups or None,
            empty_instance_values=delete_iv or None,
            empty_image_values=delete_sv or None,
            empty_file_values=delete_fv or None,
        ) if (full_instances or upsert_properties or upsert_tags or upsert_groups or
              delete_instances or delete_properties or delete_tags or delete_groups or
              delete_iv or delete_sv or delete_fv) else None,
        instance_values=list(iv_cols.values()) or None,
        image_values=list(sv_cols.values()) or None,
        file_values=list(fv_cols.values()) or None,
    )
    return Response(content=msgspec.json.encode(result), media_type='application/json')


@project_router.get('/init_state')
def get_init_state(project: Project = Depends(_dep)):
    """Lightweight init payload: file sources, folders, tags, properties + current sequence."""
    with project._data_reader() as reader:
        sequence = reader.get_next_sequence() - 1

    return _json({
        'file_sources':    [_db_to_dict(fs) for fs in project.get_file_sources()],
        'folders':         [_db_to_dict(f)  for f  in project.get_folders()],
        'properties':      [_db_to_dict(p)  for p  in project.get_properties()],
        'property_groups': [_db_to_dict(g)  for g  in project.get_property_groups()],
        'tags':            [_db_to_dict(t)  for t  in project.get_tags()],
        'sequence':        sequence,
    })


@project_router.get('/db_state')
def get_db_state(project: Project = Depends(_dep)):
    return _json({
        'properties':      project.get_properties(),
        'tags':            project.get_tags(),
        'folders':         project.get_folders(),
        'files':           project.get_files(),
        'instances':       project.get_instances(),
        'instance_values': project.get_instance_values(),
        'sha1_values':     project.get_sha1_values(),
    })


@project_router.get('/project_state')
def get_project_state(project: Project = Depends(_dep)):
    plugins = [p.get_description().model_dump(by_alias=True) for p in project.plugins]
    tasks = [t.model_dump(mode='json') for t in project.get_task_states()]
    settings = ProjectSettings().model_dump(by_alias=True)
    return {
        'id': project.config.id,
        'name': project.config.name,
        'path': str(project.folder),
        'tasks': tasks,
        'plugins': plugins,
        'settings': settings,
    }


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

@project_router.get('/property')
def get_properties(project: Project = Depends(_dep)):
    return _json(project.get_properties())


@project_router.get('/tags')
def get_tags(project: Project = Depends(_dep)):
    return _json(project.get_tags())


@project_router.get('/tags/counts')
def get_tag_counts(property_id: int | None = None, project: Project = Depends(_dep)):
    return project.get_tag_counts(property_id=property_id)


@project_router.get('/allocate/tags')
def allocate_tags(n: int = 1, project: Project = Depends(_dep)):
    ids = _to_ids(project.allocate_tags(n), n)
    return list(ids)


@project_router.get('/allocate/property_groups')
def allocate_property_groups(n: int = 1, project: Project = Depends(_dep)):
    ids = _to_ids(project.allocate_property_groups(n), n)
    return list(ids)


@project_router.get('/folders')
def get_folders(project: Project = Depends(_dep)):
    return _json([_db_to_dict(f) for f in project.get_folders()])


@project_router.get('/folders/counts')
def get_folder_counts(project: Project = Depends(_dep)):
    return project.count_instances_per_folder()


class _PathRequest(BaseModel):
    path: str


class _IdRequest(BaseModel):
    id: int


@project_router.post('/folders')
def add_folder(req: _PathRequest, project: Project = Depends(_dep)):
    project.import_folder(req.path)
    return _json(project.get_folders())


class _UrlRequest(BaseModel):
    url: str


@project_router.post('/import/iiif')
def import_iiif(req: _UrlRequest, project: Project = Depends(_dep)):
    """Import a IIIF Collection/Manifest URL as a new (or refreshed) file source."""
    project.import_iiif(req.url)
    return _json(project.get_file_sources())


@project_router.post('/reimport_folder')
def reimport_folder(req: _IdRequest, project: Project = Depends(_dep)):
    folders = project.get_folders()
    folder = next((f for f in folders if f.id == req.id), None)
    if not folder:
        raise HTTPException(404, f'Folder {req.id} not found')
    if not folder.path:
        raise HTTPException(400, f'Folder {req.id} has no path')
    project.import_folder(folder.path)
    return _json(folders)


@project_router.delete('/folder')
def delete_folder(folder_id: int, project: Project = Depends(_dep)):
    # Hard delete: the data layer resolves the descendant folders/files/instances, cascades
    # per-instance values + logs, and GCs orphaned sha1/file rows and media. Structural
    # deletes are not undoable, so the frontend should full-reload.
    project.delete_folders([folder_id])
    return {'ok': True, 'reload': True}


@project_router.get('/instances')
def get_instances(project: Project = Depends(_dep)):
    return _json(project.get_instances())


class InstanceValuesRequest(BaseModel):
    ids: list[int]
    prop_ids: list[int]


@project_router.post('/instances/values')
def get_instance_values_batch(
    body: InstanceValuesRequest,
    project: Project = Depends(_dep),
):
    """Batch-fetch values for a subset of instances × properties (lazy ColumnStore load)."""
    instance_ids = body.ids
    pid_list     = body.prop_ids
    if not instance_ids or not pid_list:
        return Response(b'{}', media_type='application/json')

    props = {p.id: p for p in project.get_properties()}
    result: dict[int, dict[int, Any]] = {}

    with project._data_reader() as reader:
        for pid in pid_list:
            prop = props.get(pid)
            if prop is None:
                continue
            values = reader.get_values_for_instances(
                instance_ids, pid, prop.mode or 'id', prop.system_key
            )
            for inst_id, val in values.items():
                result.setdefault(inst_id, {})[pid] = val

    return Response(content=orjson.dumps(result, option=orjson.OPT_NON_STR_KEYS), media_type='application/json')


@project_router.get('/instances/column/{prop_id}')
def get_property_column(
    prop_id: int,
    project: Project = Depends(_dep),
):
    """Stream all values for a single property column as batched NDJSON.

    Each line: {"ids": [...], "values": [...], "state": {counter_instance_value, max_instance_value}}
    """
    import json as _json

    props = {p.id: p for p in project.get_properties()}
    prop  = props.get(prop_id)
    if prop is None:
        raise HTTPException(404, f'Property {prop_id} not found')

    from panoptic.core.databases.data.system_properties import SYSTEM_PROPERTY_MAP

    def _generate():
        with project._data_reader() as reader:
            mode = prop.mode or 'id'

            # System properties — stream from instances table directly
            if prop.system_key and prop.system_key in SYSTEM_PROPERTY_MAP:
                system_def = SYSTEM_PROPERTY_MAP[prop.system_key]
                if system_def.source == 'instance':
                    n = reader.conn.execute(
                        f"SELECT COUNT(*) FROM {INSTANCES_SCHEMA.table}"
                    ).fetchone()[0]

                    cursor = reader.conn.execute(
                        f"SELECT id, {system_def.col} FROM {INSTANCES_SCHEMA.table}"
                    )

                    counter = 0
                    while rows := cursor.fetchmany(_STREAM_BATCH):
                        ids = [r[0] for r in rows]
                        values = [_dumps(r[1]) for r in rows]
                        counter += len(rows)
                        yield msgspec.json.encode(StreamResult(
                            instance_values=[InstanceValuesColumn(prop_id, ids, values)],
                            state=LoadState(
                                counter_instance_value=counter,
                                max_instance_value=n,
                            ),
                        )) + b'\n'

                else:
                    # file-sourced system property (name, format, width, height, etc.)
                    inst_cursor = reader.conn.execute(
                        f"SELECT id, file_id FROM {INSTANCES_SCHEMA.table}"
                    )
                    inst_rows = []
                    while rows := inst_cursor.fetchmany(_STREAM_BATCH):
                        for r in rows:
                            if r[1] is not None:
                                inst_rows.append((r[0], r[1]))

                    file_ids = [r[1] for r in inst_rows]
                    file_to_val: dict[int, Any] = {}
                    if file_ids:
                        file_rows = FILES_SCHEMA.select(
                            reader.conn, ['id', system_def.col], id=file_ids
                        )
                        file_to_val = {r[0]: r[1] for r in file_rows}

                    n = len(inst_rows)
                    counter = 0
                    batch: dict[int, Any] = {}
                    for inst_id, file_id in inst_rows:
                        batch[inst_id] = file_to_val.get(file_id)
                        counter += 1
                        if len(batch) >= _STREAM_BATCH:
                            ids = list(batch.keys())
                            values = [_dumps(batch[i]) for i in ids]
                            yield msgspec.json.encode(StreamResult(
                                instance_values=[InstanceValuesColumn(prop_id, ids, values)],
                                state=LoadState(
                                    counter_instance_value=counter,
                                    max_instance_value=n,
                                ),
                            )) + b'\n'
                            batch = {}

                    if batch:
                        ids = list(batch.keys())
                        values = [_dumps(batch[i]) for i in ids]
                        yield msgspec.json.encode(StreamResult(
                            instance_values=[InstanceValuesColumn(prop_id, ids, values)],
                            state=LoadState(
                                counter_instance_value=n,
                                max_instance_value=n,
                            ),
                        )) + b'\n'

                return

            # Tag properties — use iter_column_values with 'tag' mode
            if reader._is_tag_property(prop_id):
                # Tags are stored per-instance (instance_tag_values) for id-mode
                # properties, or per-sha1 (sha1_tag_values) for sha1-mode ones.
                # This branch used to read instance_tag_values only, so sha1-mode
                # tag/multi_tags columns streamed empty and could not be grouped or
                # sorted. Detect which table actually holds the rows — mirroring the
                # display path's mode routing — and stream from it.
                n = reader.conn.execute(
                    f"SELECT COUNT(*) FROM {INSTANCE_TAG_VALUES_SCHEMA.table} "
                    f"WHERE property_id = ? AND operation = ?",
                    (prop_id, OP_CREATE),
                ).fetchone()[0]

                grouped: dict[int, list[int]] = {}
                if n > 0:
                    cursor = reader.conn.execute(
                        f"SELECT instance_id, tag_id FROM {INSTANCE_TAG_VALUES_SCHEMA.table} "
                        f"WHERE property_id = ? AND operation = ?",
                        (prop_id, OP_CREATE),
                    )
                else:
                    cursor = reader.conn.execute(
                        f"SELECT i.id, stv.tag_id FROM {SHA1_TAG_VALUES_SCHEMA.table} stv "
                        f"JOIN {INSTANCES_SCHEMA.table} i ON i.sha1 = stv.sha1 "
                        f"WHERE stv.property_id = ? AND stv.operation = ?",
                        (prop_id, OP_CREATE),
                    )
                    n = reader.conn.execute(
                        f"SELECT COUNT(DISTINCT i.id) FROM {SHA1_TAG_VALUES_SCHEMA.table} stv "
                        f"JOIN {INSTANCES_SCHEMA.table} i ON i.sha1 = stv.sha1 "
                        f"WHERE stv.property_id = ? AND stv.operation = ?",
                        (prop_id, OP_CREATE),
                    ).fetchone()[0]

                counter = 0
                for row in cursor:
                    grouped.setdefault(row[0], []).append(row[1])
                    if len(grouped) >= _STREAM_BATCH:
                        ids = list(grouped.keys())
                        values = [_dumps(v) for v in grouped.values()]
                        counter += len(ids)
                        yield msgspec.json.encode(StreamResult(
                            instance_values=[InstanceValuesColumn(prop_id, ids, values)],
                            state=LoadState(
                                counter_instance_value=counter,
                                max_instance_value=n,
                            ),
                        )) + b'\n'
                        grouped = {}

                if grouped:
                    ids = list(grouped.keys())
                    values = [_dumps(v) for v in grouped.values()]
                    counter += len(ids)
                    yield msgspec.json.encode(StreamResult(
                        instance_values=[InstanceValuesColumn(prop_id, ids, values)],
                        state=LoadState(
                            counter_instance_value=counter,
                            max_instance_value=n,
                        ),
                    )) + b'\n'

                return

            # Regular properties — detect mode and stream
            n, mode = reader.count_column_values(prop_id)

            if mode == 'id':
                cursor = reader.conn.execute(
                    f"SELECT instance_id, value FROM {INSTANCE_VALUES_SCHEMA.table} WHERE property_id = ?",
                    (prop_id,),
                )
            elif mode == 'sha1':
                cursor = reader.conn.execute(
                    f"SELECT i.id, sv.value FROM {SHA1_VALUES_SCHEMA.table} sv "
                    f"JOIN {INSTANCES_SCHEMA.table} i ON i.sha1 = sv.sha1 "
                    f"WHERE sv.property_id = ?",
                    (prop_id,),
                )
            elif mode == 'file':
                cursor = reader.conn.execute(
                    f"SELECT i.id, fv.value FROM {FILE_VALUES_SCHEMA.table} fv "
                    f"JOIN {INSTANCES_SCHEMA.table} i ON i.file_id = fv.file_id "
                    f"WHERE fv.property_id = ?",
                    (prop_id,),
                )
            else:
                # No data for this property
                yield msgspec.json.encode(StreamResult(
                    instance_values=[InstanceValuesColumn(prop_id, [], [])],
                    state=LoadState(
                        counter_instance_value=0,
                        max_instance_value=0,
                    ),
                )) + b'\n'
                return

            counter = 0
            while rows := cursor.fetchmany(_STREAM_BATCH):
                ids = [r[0] for r in rows]
                values = [_dumps(r[1]) for r in rows]
                counter += len(rows)
                yield msgspec.json.encode(StreamResult(
                    instance_values=[InstanceValuesColumn(prop_id, ids, values)],
                    state=LoadState(
                        counter_instance_value=counter,
                        max_instance_value=n,
                    ),
                )) + b'\n'

    return StreamingResponse(_generate(), media_type='application/x-ndjson')


@project_router.get('/instances/base')
def stream_instances_base(project: Project = Depends(_dep)):
    """Stream instance base columns as batched NDJSON for ColumnStore initialisation.

    Each line: {"ids": [...], "sha1s": [...], "file_ids": [...]}
    All three arrays are the same length; sha1s[i] and file_ids[i] correspond
    to ids[i]. IDs are sent once per batch — not repeated across chunks.
    """
    def _generate():
        with project._data_reader() as reader:
            total = reader.conn.execute(
                f"SELECT COUNT(*) FROM {INSTANCES_SCHEMA.table}"
            ).fetchone()[0]
            first = True
            for ids, sha1s, file_ids in reader.iter_instance_base(_STREAM_BATCH):
                batch: dict = {'ids': ids, 'sha1s': sha1s, 'file_ids': file_ids}
                if first:
                    batch['total'] = total
                    first = False
                yield msgspec.json.encode(batch) + b'\n'

    return StreamingResponse(_generate(), media_type='application/x-ndjson')


# ---------------------------------------------------------------------------
# Commits  (write / undo / redo)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Commit input models (frontend-friendly: arrays, id<0 = new)
# ---------------------------------------------------------------------------

class _PropIn(BaseModel):
    id: int = -1
    name: Optional[str] = None
    type: Optional[str] = None     # frontend field → DB dtype
    dtype: Optional[str] = None    # also accepted
    mode: Optional[str] = None
    property_group_id: Optional[int] = None

class _TagIn(BaseModel):
    id: int = -1
    property_id: Optional[int] = None  # maps to Tag.list_id
    parents: list[int] = []
    value: Optional[str] = None
    color: int = -1

class _IVIn(BaseModel):
    property_id: int
    instance_id: int
    value: Any = None

class _SVIn(BaseModel):
    property_id: int
    sha1: str
    value: Any = None

class _FVIn(BaseModel):
    property_id: int
    file_id: int
    value: Any = None

class _PGIn(BaseModel):
    id: int = -1
    name: Optional[str] = None

class UpsertRequest(BaseModel):
    properties: list[_PropIn] = []
    tags: list[_TagIn] = []
    instance_values: list[_IVIn] = []
    image_values: list[_SVIn] = []
    file_values: list[_FVIn] = []
    property_groups: list[_PGIn] = []
    instances: list[Any] = []  # passthrough — not yet supported

class DeleteRequest(BaseModel):
    empty_instances: list[int] = []
    empty_properties: list[int] = []
    empty_tags: list[int] = []
    empty_property_groups: list[int] = []
    empty_instance_values: list[_IVIn] = []
    empty_image_values: list[_SVIn] = []
    empty_file_values: list[_FVIn] = []


def _to_ids(val: Any, n: int) -> range:
    """Normalise allocate_* return to always be iterable."""
    if isinstance(val, int):
        return range(val, val + n)
    return val


@project_router.post('/commit/upsert')
def upsert_commit_route(req: UpsertRequest, project: Project = Depends(_dep)):
    from panoptic.core.databases.entity_schema import OP_CREATE, OP_UPDATE

    upsert = UpsertCommit()
    prop_id_map: dict[int, int] = {}

    # Properties — allocate IDs for id < 0
    new_props = [p for p in req.properties if p.id < 0]
    upd_props  = [p for p in req.properties if p.id >= 0]

    if new_props:
        ids = _to_ids(project.allocate_properties(len(new_props)), len(new_props))
        for p, pid in zip(new_props, ids):
            prop_id_map[p.id] = pid
            upsert.properties[pid] = Property(
                id=pid, dtype=p.type or p.dtype or 'text',
                mode=p.mode or 'sha1', name=p.name or '',
                access='write', tag_list_id=pid,
                property_group_id=p.property_group_id,
                commit_id=0, operation=OP_CREATE,
            )
    for p in upd_props:
        upsert.properties[p.id] = Property(
            id=p.id, dtype=p.type or p.dtype or 'text',
            mode=p.mode or 'sha1', name=p.name or '',
            access='write', tag_list_id=p.id,
            property_group_id=p.property_group_id,
            commit_id=0, operation=OP_UPDATE,
        )

    # Tags — allocate IDs for id < 0
    new_tags = [t for t in req.tags if t.id < 0]
    upd_tags  = [t for t in req.tags if t.id >= 0]

    if new_tags:
        ids = _to_ids(project.allocate_tags(len(new_tags)), len(new_tags))
        for t, tid in zip(new_tags, ids):
            list_id = prop_id_map.get(t.property_id, t.property_id)
            upsert.tags[tid] = Tag(
                id=tid, list_id=list_id, parents=t.parents,
                value=t.value or '', color=t.color,
                commit_id=0, operation=OP_CREATE,
            )
    for t in upd_tags:
        list_id = prop_id_map.get(t.property_id, t.property_id)
        upsert.tags[t.id] = Tag(
            id=t.id, list_id=list_id, parents=t.parents,
            value=t.value or '', color=t.color,
            commit_id=0, operation=OP_UPDATE,
        )

    # Instance values (grouped by property_id for UpsertCommit)
    for iv in req.instance_values:
        pid = prop_id_map.get(iv.property_id, iv.property_id)
        upsert.instance_values.setdefault(pid, []).append(
            InstanceValue(property_id=pid, instance_id=iv.instance_id,
                          value=iv.value, commit_id=0, operation=OP_UPDATE)
        )

    # Sha1 values (grouped by property_id for UpsertCommit)
    for sv in req.image_values:
        pid = prop_id_map.get(sv.property_id, sv.property_id)
        upsert.sha1_values.setdefault(pid, []).append(
            Sha1Value(property_id=pid, sha1=sv.sha1,
                      value=sv.value, commit_id=0, operation=OP_UPDATE)
        )

    # File values (grouped by property_id for UpsertCommit)
    for fv in req.file_values:
        pid = prop_id_map.get(fv.property_id, fv.property_id)
        upsert.file_values.setdefault(pid, []).append(
            FileValue(property_id=pid, file_id=fv.file_id,
                      value=fv.value, commit_id=0, operation=OP_UPDATE)
        )

    # Property groups (IDs are already real — allocated by the frontend)
    for g in req.property_groups:
        upsert.property_groups[g.id] = PropertyGroup(
            id=g.id, name=g.name or '',
            commit_id=0, operation=OP_CREATE,
        )

    if (upsert.properties or upsert.tags or upsert.instance_values
            or upsert.sha1_values or upsert.file_values or upsert.property_groups):
        project.apply_upsert_commit('ui', upsert)

    return {
        'properties': [
            {'id': p.id, 'dtype': p.dtype, 'mode': p.mode, 'name': p.name}
            for p in upsert.properties.values()
        ],
        'tags': [
            {'id': t.id, 'list_id': t.list_id, 'value': t.value,
             'parents': t.parents, 'color': t.color}
            for t in upsert.tags.values()
        ],
        'property_groups': [
            {'id': g.id, 'name': g.name}
            for g in upsert.property_groups.values()
        ],
    }


@project_router.post('/commit/delete')
def delete_commit_route(req: DeleteRequest, project: Project = Depends(_dep)):
    from panoptic.core.databases.entity_schema import OP_DELETE

    reload = False
    # Structural (instances): hard delete + GC, not undoable → frontend full-reload.
    if req.empty_instances:
        project.delete_instances(list(req.empty_instances))
        reload = True

    # Logged (properties / tags / property_groups): unified revertable commit.
    commit = DataCommit(
        properties=[Property(id=i, operation=OP_DELETE) for i in req.empty_properties],
        tags=[Tag(id=i, operation=OP_DELETE) for i in req.empty_tags],
        property_groups=[PropertyGroup(id=i, operation=OP_DELETE) for i in req.empty_property_groups],
    )
    if commit.properties or commit.tags or commit.property_groups:
        project.apply_commit('ui', commit)

    return {'ok': True, 'reload': reload}


@project_router.post('/undo')
def undo_route(project: Project = Depends(_dep)):
    commits = project.get_commits()
    active = [c for c in commits if c.active]
    if not active:
        raise HTTPException(400, 'Nothing to undo')
    last = max(active, key=lambda c: c.id)
    project.set_commit_active(last.id, False)
    return _json(last)


@project_router.post('/redo')
def redo_route(project: Project = Depends(_dep)):
    commits = project.get_commits()
    inactive = [c for c in commits if not c.active]
    if not inactive:
        raise HTTPException(400, 'Nothing to redo')
    last = max(inactive, key=lambda c: c.id)
    project.set_commit_active(last.id, True)
    return _json(last)


@project_router.get('/history')
def get_history(project: Project = Depends(_dep)):
    commits = project.get_commits()
    undo = [c for c in commits if c.active]
    redo = [c for c in commits if not c.active]
    return {'undo': len(undo), 'redo': len(redo)}


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

@project_router.get('/image/by_size/{sha1:path}')
async def get_image_by_size(sha1: str, size: int | None = None, project: Project = Depends(_dep)):
    """Serve a stored thumbnail. size=N picks the best fit; omit for the largest available."""
    data = project.get_best_image_bytes(sha1, size)
    if data:
        return Response(data, media_type='image/jpeg')
    return await get_image_raw(sha1, project)


@project_router.get('/image/small/{sha1:path}')
def get_image_small(sha1: str, project: Project = Depends(_dep)):
    data = project.get_best_image_bytes(sha1, 256)
    if data:
        return Response(data, media_type='image/jpeg')
    raise HTTPException(404, f'Image {sha1} not found')


@project_router.get('/image/large/{sha1:path}')
def get_image_large(sha1: str, project: Project = Depends(_dep)):
    data = project.get_best_image_bytes(sha1, None)
    if data:
        return Response(data, media_type='image/jpeg')
    raise HTTPException(404, f'Image {sha1} not found')


@project_router.get('/image/raw/{sha1:path}')
async def get_image_raw(sha1: str, project: Project = Depends(_dep)):
    from pathlib import Path
    from starlette.responses import FileResponse as FR
    import httpx

    ref = project.resolve_image_ref(sha1)
    if ref and ref['kind'] == 'local':
        if Path(ref['path']).exists():
            return FR(ref['path'])
    elif ref and ref['kind'] == 'iiif':
        try:
            # A browser-like UA avoids 403s from hosts like Gallica/BnF.
            headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                r = await client.get(ref['url'], headers=headers)
            if r.status_code == 200:
                media_type = r.headers.get('content-type', 'image/jpeg')
                return Response(r.content, media_type=media_type)
        except Exception:
            logger.exception('IIIF proxy failed for %s', ref['url'])

    # Fall back to the largest cached thumbnail (also covers IIIF when the remote is down).
    data = project.get_best_image_bytes(sha1, None)
    if data:
        return Response(data, media_type='image/jpeg')
    raise HTTPException(404, f'Image {sha1} not found')


@project_router.get('/image/medium/{sha1:path}')
def get_image_medium(sha1: str, project: Project = Depends(_dep)):
    return get_image_large(sha1, project)


# ---------------------------------------------------------------------------
# Actions & plugins
# ---------------------------------------------------------------------------

class ActionContextRequest(BaseModel):
    instance_ids: list[int] | None = None
    group_name: str | None = None
    ui_inputs: dict = {}


class ExecuteActionRequest(BaseModel):
    function: str
    context: ActionContextRequest = ActionContextRequest()


@project_router.post('/action_execute')
def execute_action(req: ExecuteActionRequest, project: Project = Depends(_dep)):
    ctx = ActionContext(
        instance_ids=req.context.instance_ids,
        group_name=req.context.group_name,
        ui_inputs=req.context.ui_inputs,
    )
    if req.function not in project.action.actions:
        raise HTTPException(404, f'Action {req.function!r} not found')
    result = project.action.call(req.function, ctx)
    return result  # ActionResult is a dataclass — FastAPI serialises it


@project_router.get('/actions')
def get_actions(project: Project = Depends(_dep)):
    return project.action.get_all()


@project_router.get('/plugins_info')
def get_plugins_info(project: Project = Depends(_dep)):
    return [p.get_description() for p in project.plugins]


class PluginParamsRequest(BaseModel):
    plugin: str
    params: dict


@project_router.post('/plugin_params')
def update_plugin_params(req: PluginParamsRequest, project: Project = Depends(_dep)):
    try:
        project.update_plugin_params(req.plugin, req.params)
    except KeyError as e:
        raise HTTPException(404, str(e))
    return [p.get_description() for p in project.plugins]


# ---------------------------------------------------------------------------
# UI data  (tab state / user defaults)
# ---------------------------------------------------------------------------

class UiDataRequest(BaseModel):
    key: str
    data: object


@project_router.get('/ui_data')
def get_all_ui_data(project: Project = Depends(_dep), user_id: str = 'default'):
    rows = project.get_all_user_defaults(user_id=user_id)
    return {row.key: row.data for row in rows}


@project_router.get('/ui_data/{key:path}')
def get_ui_data(key: str, project: Project = Depends(_dep), user_id: str = 'default'):
    result = project.get_user_defaults(user_id=user_id, key=key)
    return result.data if result else None


@project_router.post('/ui_data')
def set_ui_data(req: UiDataRequest, project: Project = Depends(_dep), user_id: str = 'default'):
    from panoptic.core.databases.project.models import UserDefaults
    project.set_user_defaults(UserDefaults(user_id=user_id, key=req.key, data=req.data))
    return {'ok': True}


@project_router.post('/ui_data_bulk')
def set_ui_data_bulk(data: dict, project: Project = Depends(_dep), user_id: str = 'default'):
    from panoptic.core.databases.project.models import UserDefaults
    items = [UserDefaults(user_id=user_id, key=k, data=v) for k, v in data.items()]
    project.set_user_defaults_bulk(items)
    return {'ok': True}


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

class _CreateTabRequest(BaseModel):
    id: str
    state: Any
    selection: Optional[list] = None


class _UpdateTabStateRequest(BaseModel):
    state: Any


@project_router.get('/tabs')
def get_tabs(project: Project = Depends(_dep), user_id: str = 'default'):
    tabs = project.get_user_tabs(user_id=user_id)
    return _json([_db_to_dict(t) for t in tabs])


@project_router.post('/tabs')
def create_tab(req: _CreateTabRequest, project: Project = Depends(_dep), user_id: str = 'default'):
    from panoptic.core.databases.project.models import TabData
    project.set_tab_data(TabData(id=req.id, user_id=user_id, state=req.state, selection=req.selection))
    return {'ok': True}


@project_router.put('/tabs/{tab_id}')
def update_tab(tab_id: str, req: _UpdateTabStateRequest, project: Project = Depends(_dep), user_id: str = 'default'):
    existing = project.get_tab_data(tab_id)
    selection = existing.selection if existing else None
    from panoptic.core.databases.project.models import TabData
    project.set_tab_data(TabData(id=tab_id, user_id=user_id, state=req.state, selection=selection))
    return {'ok': True}


@project_router.delete('/tabs/{tab_id}')
def delete_tab(tab_id: str, project: Project = Depends(_dep)):
    project.delete_tab_data(tab_id)
    return {'ok': True}


# ---------------------------------------------------------------------------
# Media — maps and atlases
# ---------------------------------------------------------------------------

@project_router.get('/list_maps')
def list_maps(project: Project = Depends(_dep)):
    return [_db_to_dict(m) for m in project.get_maps()]


@project_router.get('/map/{map_id}')
def get_map(map_id: int, project: Project = Depends(_dep)):
    maps = project.get_maps(id=map_id)
    if not maps:
        raise HTTPException(404, f'Map {map_id} not found')
    return _db_to_dict(maps[0])


@project_router.delete('/map')
def delete_map(map_id: int, project: Project = Depends(_dep)):
    project.delete_map(map_id)
    return {'ok': True}


@project_router.get('/atlas/{atlas_id}')
def get_atlas(atlas_id: int, project: Project = Depends(_dep)):
    atlases = project.get_image_atlases(id=atlas_id)
    if not atlases:
        return Response(b'null', media_type='application/json')
    a = atlases[0]
    # ImageAtlas is array_like=True for DB efficiency; serialize as dict for the frontend
    return Response(msgspec.json.encode({
        'id': a.id,
        'atlas_nb': a.atlas_nb,
        'width': a.width,
        'height': a.height,
        'cell_width': a.cell_width,
        'cell_height': a.cell_height,
        'sha1_mapping': a.sha1_mapping,
    }), media_type='application/json')


@project_router.get('/atlas_sheet/{atlas_id}/{sheet_nb}')
def get_atlas_sheet(atlas_id: int, sheet_nb: int, project: Project = Depends(_dep)):
    path = project.folder / 'atlas' / f'{atlas_id}_{sheet_nb}.png'
    if not path.exists():
        raise HTTPException(404, f'Atlas sheet {atlas_id}/{sheet_nb} not found')
    return FileResponse(str(path), media_type='image/png')


@project_router.get('/vector_types')
def get_vector_types(project: Project = Depends(_dep)):
    return _json(project.get_vector_types())


@project_router.get('/vector_stats')
def get_vector_stats(project: Project = Depends(_dep)):
    return _json(project.get_vector_stats())


# ---------------------------------------------------------------------------
# Settings  (V2 stores no custom settings yet — defaults always returned)
# ---------------------------------------------------------------------------

@project_router.get('/settings')   # TODO: needs testing
def get_settings(project: Project = Depends(_dep)):
    return ProjectSettings()


@project_router.post('/settings')  # TODO: needs testing
def post_settings(settings: ProjectSettings, project: Project = Depends(_dep)):
    # V2 does not yet persist per-project settings; echo back what was received.
    return settings


# ---------------------------------------------------------------------------
# Image types
# ---------------------------------------------------------------------------

class _ImageTypeRequest(BaseModel):
    id: int = -1
    name: str
    format: str
    width: Optional[int] = None
    height: Optional[int] = None
    auto_gen: bool = True


@project_router.get('/image_types')
def get_image_types(project: Project = Depends(_dep)):
    types = project.get_image_types()
    return _json([_db_to_dict(t) for t in types])


@project_router.post('/image_types')
def upsert_image_type(req: _ImageTypeRequest, project: Project = Depends(_dep)):
    from panoptic.core.databases.media.models import ImageType
    if req.id < 0:
        type_id = project.allocate_image_types(1)
    else:
        type_id = req.id
    image_type = ImageType(
        id=type_id, name=req.name, format=req.format,
        width=req.width, height=req.height, auto_gen=req.auto_gen,
    )
    project.upsert_image_type(image_type)
    return _json(_db_to_dict(image_type))


@project_router.delete('/image_types/{type_id}')
def delete_image_type(type_id: int, project: Project = Depends(_dep)):
    project.delete_image_type(type_id)
    return {'ok': True}


@project_router.get('/image_stats')
def get_image_stats(project: Project = Depends(_dep)):
    return project.get_image_stats()


# ---------------------------------------------------------------------------
# Tags — merge
# ---------------------------------------------------------------------------

class _TagMergeRequest(BaseModel):
    tag_ids: list[int]


@project_router.post('/tags/merge')  # TODO: needs testing
def merge_tags_route(req: _TagMergeRequest, project: Project = Depends(_dep)):
    from panoptic.core.databases.entity_schema import OP_UPDATE, OP_CREATE

    tag_ids = req.tag_ids
    if len(tag_ids) < 2:
        raise HTTPException(400, 'Select at least 2 tags to merge')

    all_tags = project.get_tags()
    tag_map  = {t.id: t for t in all_tags}

    main_id     = tag_ids[0]
    removed_ids = set(tag_ids[1:])
    merge_set   = set(tag_ids)

    main_tag = tag_map.get(main_id)
    if not main_tag:
        raise HTTPException(404, f'Tag {main_id} not found')
    list_id = main_tag.list_id
    if not all(tag_map.get(tid) and tag_map[tid].list_id == list_id for tid in tag_ids):
        raise HTTPException(400, 'All tags must belong to the same property')

    # Update main tag: union of all merged parents, excluding the removed set
    all_parent_ids = {
        p for tid in tag_ids
        for p in (tag_map[tid].parents or [])
        if p not in removed_ids and p != main_id
    }
    upsert = UpsertCommit()
    upsert.tags[main_id] = Tag(
        id=main_id, list_id=list_id, parents=list(all_parent_ids),
        value=main_tag.value, color=main_tag.color, commit_id=0, operation=OP_UPDATE,
    )

    # Fix tags whose parents reference any removed id
    for t in all_tags:
        if t.id in merge_set:
            continue
        if not any(p in removed_ids for p in (t.parents or [])):
            continue
        new_parents: list[int] = []
        has_main = False
        for p in (t.parents or []):
            if p not in removed_ids and p != main_id:
                new_parents.append(p)
            elif not has_main:
                new_parents.append(main_id)
                has_main = True
        upsert.tags[t.id] = Tag(
            id=t.id, list_id=t.list_id, parents=new_parents,
            value=t.value, color=t.color, commit_id=0, operation=OP_UPDATE,
        )

    # Fix property values that contain any removed tag id.
    # Tag properties store values in the tag-specific tables (one row per tag
    # assignment) rather than the generic value tables, so we must query
    # get_sha1_tag_values / get_instance_tag_values.
    props = project.get_properties()
    prop  = next((p for p in props if p.tag_list_id == list_id), None)
    if prop:
        if prop.mode == 'sha1':
            sha1_tags: dict[str, set] = {}
            for row in project.get_sha1_tag_values(property_id=prop.id, operation=OP_CREATE):
                sha1_tags.setdefault(row.sha1, set()).add(row.tag_id)
            for sha1, tag_set in sha1_tags.items():
                if not any(tid in removed_ids for tid in tag_set):
                    continue
                new_tag_set = (tag_set - removed_ids) | {main_id}
                upsert.sha1_values.setdefault(prop.id, []).append(
                    Sha1Value(property_id=prop.id, sha1=sha1,
                              value=sorted(new_tag_set), commit_id=0, operation=OP_UPDATE)
                )
        else:
            inst_tags: dict[int, set] = {}
            for row in project.get_instance_tag_values(property_id=prop.id, operation=OP_CREATE):
                inst_tags.setdefault(row.instance_id, set()).add(row.tag_id)
            for inst_id, tag_set in inst_tags.items():
                if not any(tid in removed_ids for tid in tag_set):
                    continue
                new_tag_set = (tag_set - removed_ids) | {main_id}
                upsert.instance_values.setdefault(prop.id, []).append(
                    InstanceValue(property_id=prop.id, instance_id=inst_id,
                                  value=sorted(new_tag_set), commit_id=0, operation=OP_UPDATE)
                )

    if upsert.tags or upsert.instance_values or upsert.sha1_values:
        project.apply_upsert_commit('ui', upsert)

    project.apply_delete_commit('ui', DeleteCommit(tags=removed_ids))

    return {
        'empty_tags': list(removed_ids),
        'tags': [
            {'id': t.id, 'list_id': t.list_id, 'value': t.value,
             'parents': t.parents, 'color': t.color}
            for t in upsert.tags.values()
        ],
        'instance_values': [
            {'property_id': v.property_id, 'instance_id': v.instance_id, 'value': v.value}
            for vals in upsert.instance_values.values() for v in vals
        ],
        'image_values': [
            {'property_id': v.property_id, 'sha1': v.sha1, 'value': v.value}
            for vals in upsert.sha1_values.values() for v in vals
        ],
    }


# ---------------------------------------------------------------------------
# Vectors — info / delete / default
# ---------------------------------------------------------------------------

@project_router.get('/vectors_info')   # TODO: needs testing
def get_vectors_info(project: Project = Depends(_dep)):
    vector_types = project.get_vector_types()
    # Retrieve the stored default vector id (None if never set)
    row = project.get_user_defaults(user_id='system', key='default_vector_id')
    default_id = row.data if row else None
    return _json({'vector_types': vector_types, 'default_vector_id': default_id})


@project_router.post('/delete_vector_type')  # TODO: needs testing
def delete_vector_type_route(req: _IdRequest, project: Project = Depends(_dep)):
    project.delete_vector_type(req.id)
    return _json(project.get_vector_types())


@project_router.post('/default_vectors')  # TODO: needs testing
def set_default_vectors(req: _IdRequest, project: Project = Depends(_dep)):
    from panoptic.core.databases.project.models import UserDefaults
    project.set_user_defaults(UserDefaults(user_id='system', key='default_vector_id', data=req.id))
    vector_types = project.get_vector_types()
    return _json({'vector_types': vector_types, 'default_vector_id': req.id})


# ---------------------------------------------------------------------------
# Delete empty instance clones
# ---------------------------------------------------------------------------

@project_router.post('/delete_empty_clones')  # TODO: needs testing
def delete_empty_clones_route(project: Project = Depends(_dep)):
    from collections import defaultdict

    all_instances = project.get_instances()

    # An instance is "empty" if no InstanceValue references it
    non_empty_ids = {v.instance_id for v in project.get_instance_values()}
    # Also treat instances whose sha1 has stored values as non-empty
    sha1s_with_values = {v.sha1 for v in project.get_sha1_values()}
    non_empty_ids |= {i.id for i in all_instances if i.sha1 and i.sha1 in sha1s_with_values}

    empty_insts = [i for i in all_instances if i.id not in non_empty_ids]

    # Group by sha1 and delete all but the lowest id per group
    sha1_groups: dict[str, list[int]] = defaultdict(list)
    for inst in empty_insts:
        if inst.sha1:
            sha1_groups[inst.sha1].append(inst.id)

    to_delete: set[int] = set()
    for ids in sha1_groups.values():
        if len(ids) > 1:
            to_delete.update(sorted(ids)[1:])

    if to_delete:
        project.delete_instances(list(to_delete))

    return {'deleted': len(to_delete), 'reload': bool(to_delete)}


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------

class _ImportParseRequest(BaseModel):
    fusion: str = 'first'
    relative: bool = False
    properties: dict[str, Any] = {}
    exclude: list[int] = []


class _ImportConfirmRequest(BaseModel):
    exclude: list[int] = []
    properties: dict[str, Any] = {}   # col_index_str → {id, name, dtype, mode}
    fusion: str = 'first'
    relative: bool = False


@project_router.post('/import/upload')   # TODO: needs testing
async def import_upload(file: UploadFile, project: Project = Depends(_dep)):
    """Save the uploaded CSV to the project folder and parse its headers."""
    content   = await file.read()
    save_path = project.folder / (file.filename or 'import.csv')
    save_path.write_bytes(content)
    return project.importer.parse_headers(str(save_path))


@project_router.post('/import/parse')   # TODO: needs testing
def import_parse(req: _ImportParseRequest, project: Project = Depends(_dep)):
    """Map CSV rows to existing instance IDs."""
    return project.importer.verify_mapping(relative=req.relative, fusion=req.fusion)


@project_router.post('/import/confirm')   # TODO: needs testing
def import_confirm(req: _ImportConfirmRequest, project: Project = Depends(_dep)):
    """Write imported CSV data to the database."""
    project.importer.import_data_and_commit(
        exclude=req.exclude,
        properties=req.properties,
    )
    return {'ok': True}


@project_router.post('/import/tags')   # TODO: needs testing
async def import_tags(
    file: UploadFile,
    property_id: int = Form(...),
    project: Project = Depends(_dep),
):
    """Import a tag hierarchy CSV (name; color; parents) into a tag property."""
    content = await file.read()
    project.importer.import_tags(content, property_id)
    return _json(project.get_tags())


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class _ExportRequest(BaseModel):
    name: str | None = None
    images: list[int] | None = None        # instance ids to export; None = all
    properties: list[int] = []
    export_images: bool = False
    key: str = 'id'


@project_router.post('/export')   # TODO: needs testing
def export_route(req: _ExportRequest, project: Project = Depends(_dep)):
    import subprocess, sys
    export_path = project.exporter.export_data(
        path=str(project.folder),
        name=req.name,
        instance_ids=req.images,
        properties=req.properties,
        copy_images=req.export_images,
        key=req.key,
    )
    # Try to reveal the folder in the file manager (best-effort, non-blocking)
    try:
        if sys.platform == 'darwin':
            subprocess.Popen(['open', export_path])
        elif sys.platform.startswith('linux'):
            subprocess.Popen(['xdg-open', export_path])
    except Exception:
        pass
    return {'path': export_path}
