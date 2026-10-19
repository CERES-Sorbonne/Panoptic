"""Ordered API contract scenario. Tests build on each other: run the whole file.

Each test drives the frontend-facing routes in the order the UI uses them and compares the
normalized responses (and socket events) with golden/*.json. See conftest.py for how to run.
"""
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path

import pytest

from contract_harness import SocketRecorder, sorted_list

pytestmark = pytest.mark.contract

TASK_FIELDS = {'id', 'name', 'key', 'total', 'done', 'failed', 'running', 'finished', 'cancelled',
               'owner', 'vector_type_id', 'step', 'detail', 'workers', 'started_at', 'remain',
               'elapsed', 'rate', 'eta_seconds'}
#: task fields compared with the golden (others depend on the machine / timing)
TASK_STABLE = ('id', 'name', 'key', 'total', 'done', 'failed', 'running', 'finished', 'cancelled',
               'owner', 'vector_type_id', 'remain')
#: socket events whose count / payload depends on timing: checked by dedicated asserts only
NOISY_EVENTS = {'tasks', 'db_update'}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def ctype(r) -> str:
    return r.headers.get('content-type', '').split(';')[0].strip()


def body(r):
    if ctype(r) == 'application/json':
        return r.json()
    return r.text


def snap(c, r, transform=None) -> dict:
    """Normalized {status, content_type, body} of a response."""
    data = body(r)
    if transform is not None and r.status_code < 400:
        data = transform(data)
    return {'status': r.status_code, 'content_type': ctype(r), 'body': c.norm(data)}


def check(c, name: str, r, transform=None, *, status: int = 200) -> dict:
    s = snap(c, r, transform)
    assert r.status_code == status, f'{name}: HTTP {r.status_code} {r.text[:2000]}'
    c.golden.check(name, s)
    return s


def check_error(c, name: str, r, status: int, *, golden_message: bool = True):
    """Error responses: {name, message} (HTTPException) or {name, message, traceback} (500)."""
    assert r.status_code == status, f'{name}: expected {status}, got {r.status_code} {r.text[:500]}'
    data = r.json()
    if golden_message:
        c.golden.check(name, {'status': r.status_code, 'content_type': ctype(r), 'body': c.norm(data)})
    else:
        assert set(data) >= {'name', 'message'}, data


def shape(v):
    """Type skeleton of a value: for implementation-specific payloads (versions, disks)."""
    if isinstance(v, dict):
        return {k: shape(x) for k, x in v.items()}
    if isinstance(v, list):
        return [shape(v[0])] if v else []
    return type(v).__name__


def events(c, mark: int, include_noisy: bool = False) -> list:
    out = []
    for _, name, payload in c.sock.since(mark):
        if name in NOISY_EVENTS and not include_noisy:
            continue
        out.append([name, c.norm(payload)])
    return out


def tasks_done(expected_keys: set[str]):
    def pred(payload):
        tasks = payload.get('tasks') or []
        keys = {t['key'] for t in tasks if t['finished']}
        return bool(tasks) and not any(t['running'] for t in tasks) and expected_keys <= keys
    return pred


def wait_tasks(c, mark: int, expected_keys: set[str], timeout: float = 180) -> list[dict]:
    payload = c.sock.wait_for('tasks', tasks_done(expected_keys), since=mark, timeout=timeout)
    assert payload['project_id'] == c.api.project_id
    for t in payload['tasks']:
        assert set(t) == TASK_FIELDS, sorted(set(t) ^ TASK_FIELDS)
    return payload['tasks']


def stable_tasks(c, tasks: list[dict]) -> list[dict]:
    return sorted_list(({k: t[k] for k in TASK_STABLE} for t in tasks), key=lambda t: t['id'])


def dismiss_finished(c):
    r = c.api.ppost('/tasks/dismiss_finished')
    assert r.status_code == 200 and r.json() is True


def inst_row(c, inst: dict) -> dict:
    """FullInstance with non-deterministic ids mapped."""
    out = dict(inst)
    out['id'] = c.norm.inst(inst['id'])
    out['file_id'] = c.norm.file(inst['file_id'])
    return out


def norm_chunk(c, chunk: dict | None) -> dict | None:
    if not chunk:
        return chunk
    chunk = dict(chunk)
    if chunk.get('instances'):
        chunk['instances'] = sorted_list((inst_row(c, i) for i in chunk['instances']),
                                         key=lambda i: i['id'])
    for key in ('empty_instance_values',):
        if chunk.get(key):
            chunk[key] = sorted_list({**v, 'instance_id': c.norm.inst(v['instance_id'])} for v in chunk[key])
    if chunk.get('empty_file_values'):
        chunk['empty_file_values'] = sorted_list({**v, 'file_id': c.norm.file(v['file_id'])}
                                                 for v in chunk['empty_file_values'])
    for key in ('properties', 'tags', 'property_groups', 'empty_image_values'):
        if chunk.get(key):
            chunk[key] = sorted_list(chunk[key])
    for key in ('empty_properties', 'empty_tags', 'empty_property_groups', 'empty_instances'):
        if chunk.get(key):
            chunk[key] = sorted(chunk[key])
    return chunk


def norm_columns(c, cols: list | None, id_key: str, mapper, value_mapper=None) -> list | None:
    """Columnar value batches -> {property_id, rows: sorted [[mapped id, raw value]]}."""
    if cols is None:
        return None
    merged: dict[int, list] = {}
    for col in cols:
        rows = merged.setdefault(col['property_id'], [])
        for k, v in zip(col[id_key], col['values']):
            # kept verbatim: values are JSON-encoded strings, except /instances/column on a
            # regular property where numbers stored as SQLite REAL/INTEGER come through raw
            assert isinstance(v, (str, int, float)), v
            rows.append([mapper(k), value_mapper(v) if value_mapper else tag_set(v)])
    return [{'property_id': pid, 'key': id_key, 'rows': sorted_list(c.norm(rows))}
            for pid, rows in sorted(merged.items())]


def tag_set(v):
    """Tag lists are sets (row order of the tag tables): sort them, keep the compact encoding."""
    if isinstance(v, str) and v.startswith('[') and v.endswith(']'):
        decoded = json.loads(v)
        if all(isinstance(x, int) for x in decoded):
            return json.dumps(sorted(decoded), separators=(',', ':'))
    return v


def json_id_mapper(mapper):
    """Values of the `id` / `file_id` system columns are JSON-encoded ids: map them too."""
    def f(v):
        return json.dumps(mapper(json.loads(v))) if isinstance(v, str) and v != 'null' else v
    return f


def norm_stream_result(c, line: dict, value_mapper=None) -> dict:
    out = dict(line)
    if 'chunk' in out:
        out['chunk'] = norm_chunk(c, out['chunk'])
    if 'instance_values' in out:
        out['instance_values'] = norm_columns(c, out['instance_values'], 'ids', c.norm.inst, value_mapper)
    if 'image_values' in out:
        out['image_values'] = norm_columns(c, out['image_values'], 'sha1s', lambda s: s)
    if 'file_values' in out:
        out['file_values'] = norm_columns(c, out['file_values'], 'file_ids', c.norm.file)
    return out


def check_stream(c, name: str, path: str, transform=None) -> list:
    r, lines, raw = c.api.stream_ndjson(path)
    assert r.status_code == 200, raw[:500]
    assert ctype(r) == 'application/x-ndjson'
    assert raw == b'' or raw.endswith(b'\n'), 'every NDJSON line is terminated by \\n'
    norm_lines = [c.norm((transform or (lambda x: x))(line)) for line in lines]
    c.golden.check(name, {'status': r.status_code, 'content_type': ctype(r), 'lines': norm_lines})
    return lines


def seq_rel(c, seq: int) -> str:
    """Sequences are compared relative to the sequence right after the import."""
    base = c.data.get('seq_base')
    if base is None or not isinstance(seq, int) or seq == 0:   # 0 = 'not set' in LoadState
        return seq
    return f'<seq:+{seq - base}>'


def path_of(c, rel: str) -> str:
    return str(c.images / rel)


def inst_of(c, rel: str) -> int:
    return c.data['inst_by_path'][rel]


def file_of(c, rel: str) -> int:
    return c.data['file_by_path'][rel]


def sha1_of(c, rel: str) -> str:
    return c.fixture['files'][rel]


def prop_by_key(c, key: str) -> int:
    return c.data['system_props'][key]


def wait_db_update(c, mark: int, timeout: float = 15) -> dict:
    payload = c.sock.wait_for('db_update', since=mark, timeout=timeout)
    assert payload['project_id'] == c.api.project_id
    assert isinstance(payload['sequence'], int)
    return payload


def delta(c, name: str, since: int, **params):
    p = {'since': since}
    p.update(params)
    r = c.api.pget('/delta', params=p)

    def tr(d):
        d = norm_stream_result(c, d)
        d['state'] = dict(d['state'], max_sequence=seq_rel(c, d['state']['max_sequence']))
        return d
    return check(c, name, r, tr)


# ---------------------------------------------------------------------------
# 00 — server-level routes, before any project
# ---------------------------------------------------------------------------

def test_00_server_routes(ctx):
    c = ctx
    r = c.api.get('/version')
    assert r.status_code == 200
    c.golden.check('00_version_shape', shape(r.json()))
    r = c.api.get('/packages')
    assert r.status_code == 200
    c.golden.check('00_packages_shape', sorted(r.json()))
    check(c, '00_users', c.api.get('/users'))
    check(c, '00_projects_empty', c.api.get('/projects'))
    check(c, '00_plugins_empty', c.api.get('/plugins'))
    check(c, '00_legacy_projects', c.api.get('/legacy/projects'))
    r = c.api.get('/filesystem/info')
    assert r.status_code == 200
    c.golden.check('00_filesystem_info_shape', sorted(r.json()))

    def ls(d):
        d['images'] = sorted(d['images'])
        d['directories'] = sorted_list(d['directories'], key=lambda x: x['path'])
        d['files'] = sorted_list(d['files'], key=lambda x: x['path'])
        return d
    check(c, '00_filesystem_ls_images', c.api.get('/filesystem/ls' + str(c.images)), ls)
    check(c, '00_filesystem_ls_a', c.api.get('/filesystem/ls' + str(c.images / 'a')), ls)
    check(c, '00_filesystem_count', c.api.get('/filesystem/count' + str(c.images)))

    # raw file serving outside any project
    rel = 'a/img_a00.png'
    r = c.api.get('/images' + path_of(c, rel))
    assert r.status_code == 200 and ctype(r) == 'image/png'
    assert r.content == (c.images / rel).read_bytes()
    r = c.api.get('/images' + path_of(c, 'a/img_a01.jpg'))
    assert r.status_code == 200 and ctype(r) == 'image/jpeg'

    # error shapes
    check_error(c, '00_err_project_not_loaded', c.api.get('/projects/nope/init_state'), 404)
    check_error(c, '00_err_load_unknown', c.api.post('/load', json={'id': 'nope'}), 400)
    check_error(c, '00_err_validation', c.api.post('/load', json={}), 422, golden_message=False)
    assert c.api.post('/load', json={}).json()['name'] == 'ValidationError'
    r = c.api.get('/this/route/does/not/exist')
    assert r.status_code == 404
    c.golden.check('00_err_unknown_route', {'status': r.status_code, 'content_type': ctype(r),
                                            'body': body(r)})

    # CORS: every origin allowed, no credentials
    r = c.api.http.options('/projects', headers={'Origin': 'http://example.org',
                                                 'Access-Control-Request-Method': 'POST'})
    assert r.status_code == 200
    assert r.headers.get('access-control-allow-origin') == '*'
    r = c.api.get('/projects', headers={'Origin': 'http://example.org'})
    assert r.headers.get('access-control-allow-origin') == '*'


# ---------------------------------------------------------------------------
# 01 — socket connection handshake
# ---------------------------------------------------------------------------

def test_01_socket_connect(ctx):
    c = ctx
    c.sock.connect()
    c.sock.wait_for('connection_state')
    c.sock.quiet()
    c.golden.check('01_socket_connect_events', events(c, 0))

    # without auth.connection_id the server assigns one (40 hex chars) and sends it back
    other = SocketRecorder(c.url, None)
    other.connect()
    try:
        state = other.wait_for('connection_state')
        assert isinstance(state['connection_id'], str) and len(state['connection_id']) >= 8
        assert state['connection_id'] != 'contract-connection-1'
        assert state['user'] == {'id': 'default', 'name': 'default'}
        assert state['connected_project'] is None
    finally:
        other.disconnect()


# ---------------------------------------------------------------------------
# 02 — users and per-user data
# ---------------------------------------------------------------------------

def test_02_users(ctx):
    c = ctx
    m = c.sock.mark()
    r = c.api.post('/users', json={'name': 'alice'})
    assert r.status_code == 200
    alice = r.json()
    c.norm.register(alice['id'], '<USER:alice>')
    c.data['alice'] = alice['id']
    check(c, '02_create_user', r)
    check_error(c, '02_err_user_exists', c.api.post('/users', json={'name': 'alice'}), 400)
    check(c, '02_users', c.api.get('/users'), lambda d: sorted_list(d, key=lambda u: u['name']))

    r = c.api.post('/connect_user', json={'user_id': alice['id']})
    check(c, '02_connect_user', r)
    c.sock.wait_for('connection_state', lambda s: s['user']['id'] == alice['id'], since=m)
    check_error(c, '02_err_connect_unknown', c.api.post('/connect_user', json={'user_id': 'ghost'}), 404)

    # per-user key/value store follows the connection's user
    check(c, '02_set_user_data', c.api.post('/user_data', json={'key': 'explorer/history', 'data': ['/a', {'x': 1}]}))
    check(c, '02_get_user_data', c.api.get('/user_data/explorer/history'))
    r = c.api.post('/disconnect_user')
    check(c, '02_disconnect_user', r)
    c.sock.wait_for('connection_state', lambda s: s['user']['id'] == 'default', since=m)
    check(c, '02_get_user_data_default_user', c.api.get('/user_data/explorer/history'))
    check(c, '02_get_user_data_missing', c.api.get('/user_data/nothing_here'))

    r = c.api.post('/users', json={'name': 'bob'})
    bob = r.json()['id']
    c.norm.register(bob, '<USER:bob>')
    check(c, '02_delete_user', c.api.delete(f'/users/{bob}'))
    check_error(c, '02_err_delete_default_user', c.api.delete('/users/default'), 400)
    c.sock.quiet()
    c.golden.check('02_events', events(c, m))


# ---------------------------------------------------------------------------
# 03 — project creation
# ---------------------------------------------------------------------------

def test_03_create_project(ctx):
    c = ctx
    m = c.sock.mark()
    c.project_path = c.tmp / 'projects' / 'contract'
    c.project_path.parent.mkdir(parents=True, exist_ok=True)
    r = c.api.post('/create_project', json={'name': 'contract', 'path': str(c.project_path)})
    assert r.status_code == 200, r.text
    projects = r.json()
    assert len(projects) == 1
    c.api.project_id = projects[0]['id']
    c.norm.register(c.api.project_id, '<PROJECT_ID>')
    check(c, '03_create_project', r)
    state = c.sock.wait_for('connection_state', lambda s: s['connected_project'] is not None, since=m)
    assert state['connected_project'] == c.api.project_id
    c.sock.quiet()
    c.golden.check('03_events', events(c, m))
    check_error(c, '03_err_create_twice', c.api.post('/create_project', json={'name': 'x', 'path': str(c.project_path)}), 400)
    check(c, '03_projects', c.api.get('/projects'))
    for name in ('project.db', 'data.db', 'media.db'):
        assert (c.project_path / name).exists(), name


def test_04_empty_project_reads(ctx):
    c = ctx
    check(c, '04_project_state', c.api.pget('/project_state'))
    check(c, '04_init_state_empty', c.api.pget('/init_state'))
    r = c.api.pget('/property')
    check(c, '04_property_arrays', r)
    c.data['system_props'] = {p[6]: p[0] for p in r.json() if p[6]}
    check(c, '04_tags_empty', c.api.pget('/tags'))
    check(c, '04_folders_empty', c.api.pget('/folders'))
    check(c, '04_file_sources', c.api.pget('/file_sources'))
    check(c, '04_image_types', c.api.pget('/image_types'))
    check(c, '04_vector_types', c.api.pget('/vector_types'))
    check(c, '04_vector_stats', c.api.pget('/vector_stats'))
    check(c, '04_vectors_info', c.api.pget('/vectors_info'))
    check(c, '04_image_stats', c.api.pget('/image_stats'))
    check(c, '04_actions', c.api.pget('/actions'))
    check(c, '04_plugins_info', c.api.pget('/plugins_info'))
    check(c, '04_settings', c.api.pget('/settings'))
    check(c, '04_tabs_empty', c.api.pget('/tabs'))
    check(c, '04_ui_data_empty', c.api.pget('/ui_data'))
    check(c, '04_list_maps', c.api.pget('/list_maps'))
    check(c, '04_history_empty', c.api.pget('/history'))
    check(c, '04_commits_empty', c.api.pget('/commits'))
    check(c, '04_folder_counts_empty', c.api.pget('/folders/counts'))
    check(c, '04_tag_counts_empty', c.api.pget('/tags/counts'))
    check(c, '04_atlas_missing', c.api.pget('/atlas/1'))
    check_stream(c, '04_instances_base_empty', '/instances/base')


# ---------------------------------------------------------------------------
# 05 — folder import (task + socket progress)
# ---------------------------------------------------------------------------

def test_05_import_folder(ctx):
    c = ctx
    m = c.sock.mark()
    r = c.api.ppost('/folders', json={'path': str(c.images)})
    assert r.status_code == 200 and ctype(r) == 'application/json'
    assert isinstance(r.json(), list)   # folders as positional arrays; racy with the import task
    tasks = wait_tasks(c, m, {'ImportSourceTask', 'GenerateAtlasTask'})
    c.golden.check('05_import_tasks', c.norm(stable_tasks(c, tasks)))
    c.sock.wait_for('atlas', since=m, timeout=30)
    upd = wait_db_update(c, m)
    c.sock.quiet()
    c.golden.check('05_import_events', sorted({e[0] for e in events(c, m, include_noisy=True)}))
    assert all(e[2]['project_id'] == c.api.project_id for e in c.sock.since(m, 'tasks'))
    dismiss_finished(c)

    # build the id maps: instance / file ids depend on worker completion order
    folders = c.api.pget('/folders').json()
    folder_path = {f['id']: f['path'] for f in folders}
    _, lines, _ = c.api.stream_ndjson('/db_state_slim')
    inst_by_path, file_by_path = {}, {}
    for line in lines:
        for inst in (line.get('chunk') or {}).get('instances') or []:
            rel = os.path.relpath(os.path.join(folder_path[inst['folder_id']], inst['url']), c.images)
            rel = Path(rel).as_posix()
            inst_by_path[rel] = inst['id']
            file_by_path[rel] = inst['file_id']
            c.norm.inst_map[inst['id']] = f'<inst:{rel}>'
            c.norm.file_map[inst['file_id']] = f'<file:{rel}>'
    assert sorted(inst_by_path) == sorted(c.fixture['files'])
    c.data['inst_by_path'] = inst_by_path
    c.data['file_by_path'] = file_by_path
    c.data['folder_by_path'] = {Path(os.path.relpath(p, c.images)).as_posix(): i for i, p in folder_path.items()}
    seq = c.api.pget('/init_state').json()['sequence']
    assert upd['sequence'] <= seq + 1
    c.data['seq_base'] = seq


def test_06_reads_after_import(ctx):
    c = ctx

    def init_tr(d):
        d['sequence'] = seq_rel(c, d['sequence'])
        return d
    check(c, '06_init_state', c.api.pget('/init_state'), init_tr)
    check(c, '06_folders', c.api.pget('/folders'))
    check(c, '06_file_sources', c.api.pget('/file_sources'))
    check(c, '06_folder_counts', c.api.pget('/folders/counts'))
    check(c, '06_instances_arrays', c.api.pget('/instances'),
          lambda d: sorted_list(([c.norm.inst(i), c.norm.file(f), s] for i, f, s in d), key=lambda x: x[0]))

    def base_tr(line):
        assert len(line['ids']) == len(line['sha1s']) == len(line['file_ids'])
        rows = sorted_list(([c.norm.inst(i), s, c.norm.file(f)] for i, s, f in
                            zip(line['ids'], line['sha1s'], line['file_ids'])), key=lambda x: x[0])
        return {**{k: v for k, v in line.items() if k not in ('ids', 'sha1s', 'file_ids')},
                'rows[id,sha1,file_id]': rows}
    lines = check_stream(c, '06_instances_base', '/instances/base', base_tr)
    assert lines[0]['total'] == 30
    assert sorted(lines[0]['ids']) == lines[0]['ids'], 'instances/base is ordered by id'

    def slim_tr(line):
        line = norm_stream_result(c, line)
        line['state'] = dict(line['state'], max_sequence=seq_rel(c, line['state']['max_sequence']))
        return line
    check_stream(c, '06_db_state_slim', '/db_state_slim', slim_tr)
    check_stream(c, '06_db_state_stream', '/db_state_stream', slim_tr)

    value_mappers = {'id': json_id_mapper(c.norm.inst), 'file_id': json_id_mapper(c.norm.file)}
    for key, pid in sorted(c.data['system_props'].items()):
        check_stream(c, f'06_column_system_{key}', f'/instances/column/{pid}',
                     lambda l, vm=value_mappers.get(key): norm_stream_result(c, l, vm))
    check_error(c, '06_err_column_unknown', c.api.pget('/instances/column/99999'), 404)

    ids = [inst_of(c, 'a/img_a00.png'), inst_of(c, 'b/copy_of_a00.png'), inst_of(c, 'b/deep/img_d01.png')]
    props = [prop_by_key(c, k) for k in ('name', 'width', 'sha1', 'folder', 'path')]
    r = c.api.ppost('/instances/values', json={'ids': ids, 'prop_ids': props})
    check(c, '06_instances_values', r,
          lambda d: {c.norm.inst(int(k)): v for k, v in d.items()})
    check(c, '06_instances_values_empty', c.api.ppost('/instances/values', json={'ids': [], 'prop_ids': props}))

    def db_state_tr(d):
        d['files'] = sorted_list(([c.norm.file(f[0])] + f[1:] for f in d['files']), key=lambda x: x[0])
        d['instances'] = sorted_list(([c.norm.inst(i[0]), c.norm.file(i[1]), i[2]] for i in d['instances']),
                                     key=lambda x: x[0])
        return d
    check(c, '06_db_state_arrays', c.api.pget('/db_state'), db_state_tr)


# ---------------------------------------------------------------------------
# 07 — images
# ---------------------------------------------------------------------------

def test_07_images(ctx):
    c = ctx
    png, jpg = 'a/img_a02.png', 'a/img_a03.jpg'
    for rel in (png, jpg):
        sha1 = sha1_of(c, rel)
        for path, params in [(f'/image/by_size/{sha1}', {'size': 128}), (f'/image/by_size/{sha1}', {}),
                             (f'/image/small/{sha1}', {}), (f'/image/medium/{sha1}', {}),
                             (f'/image/large/{sha1}', {})]:
            r = c.api.pget(path, params=params)
            assert r.status_code == 200, (path, r.text[:300])
            assert ctype(r).startswith('image/'), (path, ctype(r))
            assert len(r.content) > 100
        r = c.api.pget(f'/image/raw/{sha1}')
        assert r.status_code == 200
        assert ctype(r) == ('image/png' if rel.endswith('.png') else 'image/jpeg')
        assert r.content == (c.images / rel).read_bytes()
    # a thumbnail that covers the requested size is served as a jpeg thumbnail
    r = c.api.pget(f'/image/by_size/{sha1_of(c, png)}', params={'size': 32})
    assert ctype(r) == 'image/jpeg'
    # bigger than every stored thumbnail: the local original is served
    r = c.api.pget(f'/image/by_size/{sha1_of(c, png)}', params={'size': 4096})
    assert ctype(r) == 'image/png' and r.content == (c.images / png).read_bytes()
    missing = '0' * 40
    check_error(c, '07_err_image_small_missing', c.api.pget(f'/image/small/{missing}'), 404)
    check_error(c, '07_err_image_raw_missing', c.api.pget(f'/image/raw/{missing}'), 404)
    check_error(c, '07_err_image_by_size_missing', c.api.pget(f'/image/by_size/{missing}'), 404)

    r = c.api.pget('/atlas/0')

    def atlas_tr(d):
        mapping = d.pop('sha1_mapping')
        assert sorted(mapping) == sorted(c.fixture['sha1_to_paths'])
        cells = sorted(tuple(v) for v in mapping.values())
        assert len(set(cells)) == len(cells), 'one atlas cell per sha1'
        d['sha1_mapping_cells'] = sorted([list(v) for v in mapping.values()])
        return d
    check(c, '07_atlas', r, atlas_tr)
    r = c.api.pget('/atlas_sheet/0/0')
    assert r.status_code == 200 and ctype(r) == 'image/png' and r.content[:8] == b'\x89PNG\r\n\x1a\n'
    check_error(c, '07_err_atlas_sheet_missing', c.api.pget('/atlas_sheet/0/99'), 404)
    check(c, '07_image_stats', c.api.pget('/image_stats'))


# ---------------------------------------------------------------------------
# 08 — commits: properties, tags, values, delta, undo / redo / history
# ---------------------------------------------------------------------------

def test_08_commits(ctx):
    c = ctx
    seq0 = c.api.pget('/init_state').json()['sequence']
    m = c.sock.mark()
    r = c.api.ppost('/commit/upsert', json={
        'properties': [
            {'id': -1, 'name': 'Note', 'type': 'text', 'mode': 'id'},
            {'id': -2, 'name': 'Score', 'type': 'number', 'mode': 'sha1'},
            {'id': -3, 'name': 'Keywords', 'type': 'multi_tags', 'mode': 'sha1'},
            {'id': -4, 'name': 'Status', 'type': 'tag', 'mode': 'id'},
        ],
        'tags': [
            {'id': -1, 'property_id': -3, 'value': 'animal', 'color': 1, 'parents': []},
            {'id': -2, 'property_id': -3, 'value': 'cat', 'color': 2, 'parents': [-1]},
            {'id': -3, 'property_id': -3, 'value': 'dog', 'color': 3, 'parents': [-1]},
            {'id': -4, 'property_id': -4, 'value': 'todo', 'color': 4},
            {'id': -5, 'property_id': -4, 'value': 'done', 'color': 5},
        ],
    })
    res = check(c, '08_upsert_properties_tags', r)['body']
    props = {p['name']: p['id'] for p in r.json()['properties']}
    tags = {t['value']: t['id'] for t in r.json()['tags']}
    c.data['props'], c.data['tags'] = props, tags
    upd = wait_db_update(c, m)
    assert upd['sequence'] > seq0

    m = c.sock.mark()
    a00, a01, d00 = 'a/img_a00.png', 'a/img_a01.jpg', 'b/deep/img_d00.png'
    r = c.api.ppost('/commit/upsert', json={
        'instance_values': [
            {'property_id': props['Note'], 'instance_id': inst_of(c, a00), 'value': 'first note'},
            {'property_id': props['Note'], 'instance_id': inst_of(c, a01), 'value': 'second "quoted" note'},
            {'property_id': props['Status'], 'instance_id': inst_of(c, a00), 'value': [tags['todo']]},
            {'property_id': props['Status'], 'instance_id': inst_of(c, d00), 'value': [tags['done']]},
        ],
        'image_values': [
            {'property_id': props['Score'], 'sha1': sha1_of(c, a00), 'value': 4.5},
            {'property_id': props['Score'], 'sha1': sha1_of(c, a01), 'value': 2},
            {'property_id': props['Keywords'], 'sha1': sha1_of(c, a00), 'value': [tags['cat'], tags['animal']]},
            {'property_id': props['Keywords'], 'sha1': sha1_of(c, d00), 'value': [tags['dog']]},
        ],
    })
    check(c, '08_upsert_values', r)
    wait_db_update(c, m)

    delta(c, '08_delta_since_before_commits', seq0)
    delta(c, '08_delta_full_props', seq0,
          full_prop_ids=f"{props['Note']},{props['Score']}")
    delta(c, '08_delta_point_props', seq0, point_prop_ids=str(props['Note']),
          instance_ids=str(inst_of(c, a00)))
    seq1 = c.api.pget('/init_state').json()['sequence']
    delta(c, '08_delta_nothing_new', seq1)

    check(c, '08_tag_counts', c.api.pget('/tags/counts'), lambda d: sorted_list(d, key=lambda x: x['tag_id']))
    check(c, '08_tag_counts_keywords', c.api.pget('/tags/counts', params={'property_id': props['Keywords']}),
          lambda d: sorted_list(d, key=lambda x: x['tag_id']))
    for name in ('Note', 'Score', 'Keywords', 'Status'):
        check_stream(c, f'08_column_{name.lower()}', f'/instances/column/{props[name]}',
                     lambda l: norm_stream_result(c, l))
    check(c, '08_tags_arrays', c.api.pget('/tags'))
    check(c, '08_property_arrays', c.api.pget('/property'))

    # history / undo / redo  (per author: user_id query param = 'default')
    check(c, '08_history', c.api.pget('/history'))
    check(c, '08_history_all', c.api.pget('/history', params={'scope': 'all'}))
    check(c, '08_commits', c.api.pget('/commits', params={'limit': 5}))
    m = c.sock.mark()
    check(c, '08_undo', c.api.ppost('/undo'))
    wait_db_update(c, m)
    delta(c, '08_delta_after_undo', seq1)
    check(c, '08_history_after_undo', c.api.pget('/history'))
    seq2 = c.api.pget('/init_state').json()['sequence']
    m = c.sock.mark()
    check(c, '08_redo', c.api.ppost('/redo'))
    wait_db_update(c, m)
    delta(c, '08_delta_after_redo', seq2)
    check(c, '08_history_after_redo', c.api.pget('/history'))
    check_error(c, '08_err_redo_empty', c.api.ppost('/redo'), 400)
    # another author has nothing to undo
    check_error(c, '08_err_undo_other_user', c.api.http.post(
        f'/projects/{c.api.project_id}/undo', params={'user_id': c.data['alice']}), 400)

    # per-commit toggle (Data settings)
    last = c.api.pget('/commits', params={'limit': 1}).json()[0]['id']
    check(c, '08_set_commit_inactive', c.api.ppost('/set_commit_active', json={'id': last, 'active': False}))
    check(c, '08_commits_after_toggle', c.api.pget('/commits', params={'limit': 2}))
    check(c, '08_set_commit_active', c.api.ppost('/set_commit_active', json={'id': last, 'active': True}))

    # guards
    check_error(c, '08_err_readonly_value', c.api.ppost('/commit/upsert', json={'instance_values': [
        {'property_id': prop_by_key(c, 'name'), 'instance_id': inst_of(c, a00), 'value': 'x'}]}), 403)
    check_error(c, '08_err_delete_system_property', c.api.ppost('/commit/delete', json={
        'empty_properties': [prop_by_key(c, 'width')]}), 403)
    check(c, '08_upsert_empty', c.api.ppost('/commit/upsert', json={}))

    # allocation + property groups
    r = c.api.pget('/allocate/tags', params={'n': 3})
    check(c, '08_allocate_tags', r)
    r = c.api.pget('/allocate/property_groups', params={'n': 1})
    check(c, '08_allocate_property_groups', r)
    gid = r.json()[0]
    check(c, '08_upsert_property_group', c.api.ppost('/commit/upsert', json={
        'property_groups': [{'id': gid, 'name': 'My group'}],
        'properties': [{'id': props['Note'], 'property_group_id': gid}]}))
    check(c, '08_upsert_rename_property', c.api.ppost('/commit/upsert', json={
        'properties': [{'id': props['Score'], 'name': 'Rating'}]}))
    check(c, '08_init_state_after_commits', c.api.pget('/init_state'),
          lambda d: {**d, 'sequence': seq_rel(c, d['sequence'])})

    # value deletion = upsert with value null; tag deletion through commit/delete
    m = c.sock.mark()
    check(c, '08_upsert_clear_value', c.api.ppost('/commit/upsert', json={'instance_values': [
        {'property_id': props['Note'], 'instance_id': inst_of(c, a01), 'value': None}]}))
    seq3 = c.api.pget('/init_state').json()['sequence']
    check(c, '08_delete_tag', c.api.ppost('/commit/delete', json={'empty_tags': [tags['dog']]}))
    wait_db_update(c, m)
    delta(c, '08_delta_after_deletes', seq1)

    # merge tags (TagModal)
    r = c.api.ppost('/tags/merge', json={'tag_ids': [tags['todo'], tags['done']]})
    check(c, '08_merge_tags', r, lambda d: {**d, 'instance_values': sorted_list(
        {**v, 'instance_id': c.norm.inst(v['instance_id'])} for v in d['instance_values'])})
    check_error(c, '08_err_merge_one_tag', c.api.ppost('/tags/merge', json={'tag_ids': [tags['todo']]}), 400)
    check(c, '08_tag_counts_after_merge', c.api.pget('/tags/counts'),
          lambda d: sorted_list(d, key=lambda x: x['tag_id']))
    check(c, '08_history_final', c.api.pget('/history'))

    def stream_tr(line):
        line = norm_stream_result(c, line)
        line['state'] = dict(line['state'], max_sequence=seq_rel(c, line['state']['max_sequence']))
        return line
    check_stream(c, '08_db_state_stream_with_values', '/db_state_stream', stream_tr)


# ---------------------------------------------------------------------------
# 09 — tabs and ui_data
# ---------------------------------------------------------------------------

def test_09_tabs_ui_data(ctx):
    c = ctx
    state = {'name': 'Tab 1', 'display': 'grid', 'filter': {'groupId': 0, 'filters': []}, 'nested': [1, 2.5, None]}
    check(c, '09_create_tab', c.api.ppost('/tabs', json={'id': 'tab-1', 'state': state, 'selection': [3, 1]}))
    check(c, '09_create_tab_2', c.api.ppost('/tabs', json={'id': 'tab-2', 'state': {'name': 'Tab 2'}, 'selection': None}))
    check(c, '09_tabs', c.api.pget('/tabs'), lambda d: sorted_list(d, key=lambda t: t['id']))
    check(c, '09_update_tab', c.api.pput('/tabs/tab-1', json={'state': {**state, 'name': 'Renamed'}}))
    check(c, '09_tabs_after_update', c.api.pget('/tabs'), lambda d: sorted_list(d, key=lambda t: t['id']))
    check(c, '09_delete_tab', c.api.pdelete('/tabs/tab-2'))
    check(c, '09_tabs_after_delete', c.api.pget('/tabs'))
    # tabs are per user
    r = c.api.http.get(f'/projects/{c.api.project_id}/tabs', params={'user_id': c.data['alice']})
    check(c, '09_tabs_other_user', r)

    check(c, '09_set_ui_data', c.api.ppost('/ui_data', json={'key': 'state', 'data': {'sidebar': True, 'w': 320}}))
    check(c, '09_set_ui_data_scalar', c.api.ppost('/ui_data', json={'key': 'zoom', 'data': 3}))
    check(c, '09_set_ui_data_bulk', c.api.ppost('/ui_data_bulk', json={'a/b': [1, 2], 'c': {'deep': [True, False]}, 'zoom': 4}))
    check(c, '09_get_ui_data', c.api.pget('/ui_data/state'))
    check(c, '09_get_ui_data_path_key', c.api.pget('/ui_data/a/b'))
    check(c, '09_get_ui_data_missing', c.api.pget('/ui_data/missing'))
    check(c, '09_get_all_ui_data', c.api.pget('/ui_data'))


# ---------------------------------------------------------------------------
# 10 — atlas regeneration, image types
# ---------------------------------------------------------------------------

def test_10_atlas_image_types(ctx):
    c = ctx
    m = c.sock.mark()
    check(c, '10_atlas_generate', c.api.ppost('/atlas/generate'))
    tasks = wait_tasks(c, m, {'GenerateAtlasTask'})
    c.golden.check('10_atlas_tasks', c.norm(stable_tasks(c, tasks)))
    c.sock.wait_for('atlas', since=m)
    dismiss_finished(c)

    r = c.api.ppost('/image_types', json={'id': -1, 'name': 'preview', 'format': 'webp',
                                          'width': 64, 'height': 64, 'auto_gen': False})
    check(c, '10_upsert_image_type', r)
    tid = r.json()['id']
    check(c, '10_image_types', c.api.pget('/image_types'))
    m = c.sock.mark()
    check(c, '10_generate_images', c.api.ppost('/image_types/generate', json={'type_ids': [tid]}))
    tasks = wait_tasks(c, m, {'GenerateThumbnailsTask'})
    c.golden.check('10_generate_tasks', c.norm(stable_tasks(c, tasks)))
    dismiss_finished(c)
    check(c, '10_image_stats', c.api.pget('/image_stats'))
    check(c, '10_delete_image_type', c.api.pdelete(f'/image_types/{tid}'))
    check(c, '10_image_types_after_delete', c.api.pget('/image_types'))


# ---------------------------------------------------------------------------
# 11 — CSV export / import
# ---------------------------------------------------------------------------

def test_11_csv_export_import(ctx):
    c = ctx
    props = c.data['props']
    r = c.api.ppost('/export', json={'name': 'contract_export', 'key': 'path',
                                     'properties': [props['Note'], props['Score'], props['Keywords']]})
    check(c, '11_export', r)
    export_dir = Path(r.json()['path'])
    text = (export_dir / 'data.csv').read_text(encoding='utf-8')
    rows = list(csv.reader(io.StringIO(text), delimiter=';'))
    tag_col = rows[0].index('Keywords[multi_tags]')
    for row in rows[1:]:
        row[tag_col] = ','.join(sorted(row[tag_col].split(','))) if row[tag_col] else ''
    c.golden.check('11_export_csv', c.norm({'header': rows[0], 'rows': sorted(rows[1:])}))

    r = c.api.ppost('/export', json={'name': 'contract_export_ids', 'key': 'id',
                                     'images': [inst_of(c, 'a/img_a00.png')], 'properties': [props['Note']]})
    assert r.status_code == 200
    rows = list(csv.reader(io.StringIO((Path(r.json()['path']) / 'data.csv').read_text(encoding='utf-8')),
                           delimiter=';'))
    c.golden.check('11_export_csv_ids', {'header': rows[0], 'rows': [[c.norm.inst(int(x[0]))] + x[1:] for x in rows[1:]]})

    content = 'path;Imported[text];Points[number];Notes again[text]\n'
    content += f'{path_of(c, "a/img_a04.png")};hello;12;n1\n'
    content += f'{path_of(c, "b/img_b01.png")};world;3.5;\n'
    content += '/does/not/exist.png;lost;1;\n'
    r = c.api.ppost('/import/upload', files={'file': ('contract.csv', content.encode(), 'text/csv')})
    check(c, '11_import_upload', r)
    r = c.api.ppost('/import/parse', json={'fusion': 'first', 'relative': True})
    check(c, '11_import_parse', r)
    m = c.sock.mark()
    r = c.api.ppost('/import/confirm', json={'exclude': [3], 'properties': {}, 'fusion': 'first', 'relative': True})
    check(c, '11_import_confirm', r)
    tasks = wait_tasks(c, m, {'ImportCsvTask'})
    c.golden.check('11_import_tasks', c.norm(stable_tasks(c, tasks)))
    dismiss_finished(c)
    prop_rows = c.api.pget('/property').json()
    imported = next(p for p in prop_rows if p[3] == 'Imported')
    check_stream(c, '11_column_imported', f'/instances/column/{imported[0]}', lambda l: norm_stream_result(c, l))

    tag_csv = 'bird;6;animal\nsparrow;7;bird\nfish;3;\n'   # no header row: name;color;parents
    r = c.api.ppost('/import/tags', files={'file': ('tags.csv', tag_csv.encode(), 'text/csv')},
                    data={'property_id': str(props['Keywords'])})
    check(c, '11_import_tags', r)


# ---------------------------------------------------------------------------
# 12 — tasks, folders, file sources, maps, misc
# ---------------------------------------------------------------------------

def test_12_tasks_folders(ctx):
    c = ctx
    check_error(c, '12_err_stop_unknown_task', c.api.ppost('/task/stop', json={'id': 'Nope#1'}), 404)
    check_error(c, '12_err_dismiss_unknown_task', c.api.ppost('/task/dismiss', json={'id': 'Nope#1'}), 404)
    check(c, '12_dismiss_finished', c.api.ppost('/tasks/dismiss_finished'))

    root = c.data['folder_by_path']['.']
    m = c.sock.mark()
    check(c, '12_reimport_folder', c.api.ppost('/reimport_folder', json={'id': root}))
    tasks = wait_tasks(c, m, {'ImportSourceTask', 'GenerateAtlasTask'})
    c.golden.check('12_reimport_tasks', c.norm(stable_tasks(c, tasks)))
    dismiss_finished(c)
    check_error(c, '12_err_reimport_unknown', c.api.ppost('/reimport_folder', json={'id': 9999}), 404)

    source = c.api.pget('/file_sources').json()[0]['id']
    m = c.sock.mark()
    check(c, '12_resync_file_source', c.api.ppost('/file_source/resync', json={'id': source}))
    wait_tasks(c, m, {'ImportSourceTask', 'GenerateAtlasTask'})
    dismiss_finished(c)
    check(c, '12_folders_after_resync', c.api.pget('/folders'))
    check(c, '12_folder_counts_after_resync', c.api.pget('/folders/counts'))

    check_error(c, '12_err_map_missing', c.api.pget('/map/999'), 404)
    check(c, '12_delete_map_missing', c.api.pdelete('/map', params={'map_id': 999}))
    check(c, '12_plugins_info', c.api.pget('/plugins_info'))
    check_error(c, '12_err_action_unknown', c.api.ppost('/action_execute', json={'function': 'nope.fn'}), 404)
    check_error(c, '12_err_plugin_stop_unknown', c.api.ppost('/plugin/stop', json={'name': 'nope'}), 404)

    # deleting a folder is structural: hard delete + reload request
    deep = c.data['folder_by_path']['b/deep']
    check(c, '12_delete_folder', c.api.pdelete('/folder', params={'folder_id': deep}))
    check(c, '12_folders_after_delete', c.api.pget('/folders'))
    check(c, '12_folder_counts_after_delete', c.api.pget('/folders/counts'))
    _, lines, _ = c.api.stream_ndjson('/instances/base')
    assert lines[0]['total'] == 25   # b/deep held 5 files

    check(c, '12_delete_empty_clones', c.api.ppost('/delete_empty_clones'))
    check(c, '12_project_state', c.api.pget('/project_state'),
          lambda d: {**d, 'tasks': stable_tasks(c, d['tasks'])})


# ---------------------------------------------------------------------------
# 13 — project lifecycle: rename, close, unregister, import, load, delete
# ---------------------------------------------------------------------------

def test_13_project_lifecycle(ctx):
    c = ctx
    pid = c.api.project_id
    m = c.sock.mark()
    check(c, '13_update_project', c.api.post('/update_project', json={'id': pid, 'name': 'renamed'}))
    c.sock.wait_for('update_projects', since=m)
    check_error(c, '13_err_update_unknown', c.api.post('/update_project', json={'id': 'nope', 'name': 'x'}), 400)

    m = c.sock.mark()
    check(c, '13_close', c.api.post('/close', json={'id': pid}))
    c.sock.wait_for('connection_state', lambda s: s['connected_project'] is None, since=m)
    c.sock.quiet()
    c.golden.check('13_close_events', events(c, m))
    check_error(c, '13_err_closed_project', c.api.pget('/init_state'), 404)

    m = c.sock.mark()
    check(c, '13_load', c.api.post('/load', json={'id': pid}))
    c.sock.wait_for('connection_state', lambda s: s['connected_project'] == pid, since=m)
    c.sock.quiet()
    c.golden.check('13_load_events', events(c, m))
    check(c, '13_init_state_reloaded', c.api.pget('/init_state'), lambda d: {**d, 'sequence': seq_rel(c, d['sequence'])})

    # reconnecting with the same connection_id while the project is open keeps the session
    m = c.sock.mark()
    c.sock.disconnect()
    c.sock = SocketRecorder(c.url, 'contract-connection-1')
    c.sock.connect()
    c.sock.wait_for('connection_state')
    c.sock.quiet()
    c.golden.check('13_reconnect_events', events(c, 0))

    m = c.sock.mark()
    check(c, '13_close_again', c.api.post('/close', json={'id': pid}))
    check(c, '13_unregister', c.api.post('/delete_project', json={'id': pid, 'delete_files': False}))
    c.sock.wait_for('update_projects', since=m)
    assert (c.project_path / 'project.db').exists()

    m = c.sock.mark()
    r = c.api.post('/import_project', json={'path': str(c.project_path)})
    check(c, '13_import_project', r)
    c.sock.wait_for('connection_state', lambda s: s['connected_project'] == pid, since=m)
    check_error(c, '13_err_import_twice', c.api.post('/import_project', json={'path': str(c.project_path)}), 400)
    check_error(c, '13_err_import_not_project', c.api.post('/import_project', json={'path': str(c.images)}), 400)
    check(c, '13_tabs_survive', c.api.pget('/tabs'))

    m = c.sock.mark()
    check(c, '13_delete_project', c.api.post('/delete_project', json={'id': pid, 'delete_files': True}))
    c.sock.wait_for('update_projects', since=m)
    assert not c.project_path.exists()
    check(c, '13_projects_final', c.api.get('/projects'))
