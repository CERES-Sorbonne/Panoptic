"""Testing helpers for plugin authors (and the SDK's own tests).

* :func:`create_project` builds an empty project (data.db, media.db, project.db) with the exact
  schema of the backend, :func:`add_images` adds structural rows (source / folder / file /
  instance) the way an import would.
* :class:`MockBackend` is a minimal backend side of the plugin protocol: a WebSocket server that
  accepts one plugin, answers its requests (commits are applied with the SDK writer) and lets a
  test drive it (execute actions, update params, stop tasks, send events, shut down).
"""
from __future__ import annotations

import asyncio
import json
import secrets
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

from . import models as m
from . import protocol as P
from .db import schema as s
from .db.ddl import DB_VERSIONS, DDL, VERSION_TABLE_SQL
from .project import ProjectData
from .rpc import RpcError, RpcPeer


# ---------------------------------------------------------------------------
# offline project
# ---------------------------------------------------------------------------

def create_project(path: str | Path, name: str | None = None) -> Path:
    """Create the three databases of an empty project (no system properties, unlike a project
    created by the backend)."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    for db, tables in DDL.items():
        conn = sqlite3.connect(str(path / f'{db}.db'), isolation_level=None)
        try:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.executescript(VERSION_TABLE_SQL)
            conn.execute("INSERT OR IGNORE INTO _version (key, value) VALUES ('db_version', ?)", (DB_VERSIONS[db],))
            for sql in tables.values():
                conn.executescript(sql)
            if db == 'project':
                for key in s.ID_REGISTRY_KEYS:
                    conn.execute("INSERT OR IGNORE INTO id_registry (key, value) VALUES (?, ?)", (key, json.dumps(1)))
                for key, value in (('id', str(uuid.uuid4())), ('name', name or path.name), ('description', None)):
                    conn.execute("INSERT OR IGNORE INTO project_config (key, value) VALUES (?, ?)",
                                 (key, json.dumps(value) if value is not None else None))
                conn.execute("INSERT OR IGNORE INTO project_flags (key, value) VALUES ('thumbnails_dirty', 'false')")
        finally:
            conn.close()
    return path


def add_images(path: str | Path, images: list[tuple[str, str, str]], source_dtype: str = 'local') -> list[m.Instance]:
    """Add ``(folder_path, file_name, sha1)`` images as an import would (structural rows, one
    sequence for the batch, ids from the registry). Returns the new instances."""
    path = Path(path)
    conn = sqlite3.connect(str(path / 'data.db'), isolation_level=None)
    pconn = sqlite3.connect(str(path / 'project.db'), isolation_level=None)
    try:
        def alloc(kind, n):
            pconn.execute('BEGIN IMMEDIATE')
            cur = s.json_load(pconn.execute("SELECT value FROM id_registry WHERE key = ?", (kind,)).fetchone()[0])
            pconn.execute("UPDATE id_registry SET value = ? WHERE key = ?", (json.dumps(cur + n), kind))
            pconn.execute('COMMIT')
            return cur

        conn.execute('BEGIN IMMEDIATE')
        seq = conn.execute("UPDATE sequence SET id = id + 1 RETURNING id").fetchone()[0] - 1
        row = conn.execute("SELECT id FROM file_sources WHERE dtype = ?", (source_dtype,)).fetchone()
        if row:
            source_id = row[0]
        else:
            source_id = alloc('file_sources', 1)
            conn.execute(s.FILE_SOURCES.upsert_sql(1), s.FILE_SOURCES.encode(
                m.FileSource(id=source_id, dtype=source_dtype, name=f'{source_dtype}_filesystem', root_url=None), seq))
        folders = {r[1]: r[0] for r in conn.execute("SELECT id, path FROM folders").fetchall()}
        out = []
        for folder_path, name, sha1 in images:
            if folder_path not in folders:
                fid = alloc('folders', 1)
                conn.execute(s.FOLDERS.upsert_sql(1), s.FOLDERS.encode(
                    m.Folder(id=fid, source_id=source_id, path=folder_path, name=Path(folder_path).name, parent=None), seq))
                folders[folder_path] = fid
            file_id = alloc('files', 1)
            conn.execute(s.FILES.upsert_sql(1), s.FILES.encode(
                m.File(id=file_id, name=name, folder_id=folders[folder_path], sha1=sha1, width=10, height=10,
                       format='jpeg'), seq))
            inst = m.Instance(id=alloc('instances', 1), file_id=file_id, sha1=sha1)
            conn.execute(s.INSTANCES.upsert_sql(1), s.INSTANCES.encode(inst, seq))
            out.append(inst)
        conn.execute('COMMIT')
        return out
    finally:
        conn.close()
        pconn.close()


# ---------------------------------------------------------------------------
# mock backend
# ---------------------------------------------------------------------------

class MockBackend:
    """Backend side of the protocol for tests. Use inside a running event loop::

        backend = MockBackend(project_path)
        await backend.start()
        ... start the plugin with backend.env() ...
        await backend.wait_ready()
        result = await backend.execute('MyPlugin.my_action', {'instance_ids': [1]})
    """

    def __init__(self, project_path: str | Path, plugin_name: str = 'TestPlugin',
                 auto_start_tasks: bool = True, stored_params: dict | None = None):
        self.project_path = Path(project_path)
        self.plugin_name = plugin_name
        self.token = secrets.token_hex(16)
        self.auto_start_tasks = auto_start_tasks
        self.stored_params = stored_params
        self.port: int | None = None
        self.peer: RpcPeer | None = None
        self.hello: dict | None = None
        self.open_result: dict | None = None
        self.actions: dict[str, dict] = {}
        self.tasks: dict[str, dict] = {}
        self.notifs: list[dict] = []
        self.logs: list[dict] = []
        self.db_changes: list[dict] = []
        self.commits: list[dict] = []
        self.calls: list[tuple[str, Any]] = []
        self.session_id = str(uuid.uuid4())
        self.connections = 0
        self.reject_token = False
        self._ready = asyncio.Event()
        self._closed = asyncio.Event()
        self._server = None
        self._task_counter = 0
        self._data = ProjectData(plugin_name, self.project_path)   # offline: direct writes

    def env(self, **extra) -> dict:
        return {
            P.ENV_URL: f'ws://127.0.0.1:{self.port}/plugin',
            P.ENV_TOKEN: self.token,
            P.ENV_NAME: self.plugin_name,
            P.ENV_PROJECT_PATH: str(self.project_path),
            P.ENV_PROJECT_ID: 'test-project',
            P.ENV_DATA_DIR: str(self.project_path / 'plugin_data' / self.plugin_name.lower()),
            P.ENV_PROTOCOL: P.PROTOCOL_VERSION,
            P.ENV_RECONNECT_TIMEOUT: '3',
            **extra,
        }

    async def start(self) -> None:
        from websockets.asyncio.server import serve
        self._server = await serve(self._on_connection, '127.0.0.1', 0, max_size=P.MAX_MESSAGE_SIZE,
                                   process_request=self._check_request)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        self._data.close()

    def _check_request(self, connection, request):
        if request.path.split('?')[0] != '/plugin':
            return connection.respond(404, 'not found\n')
        auth = request.headers.get('Authorization', '')
        if self.reject_token or auth != f'Bearer {self.token}':
            return connection.respond(401, 'bad token\n')
        return None

    async def _on_connection(self, ws) -> None:
        self.connections += 1
        self._ready.clear()
        self.peer = RpcPeer(ws, self._handle_request, self._handle_notification)
        await self.peer.serve()
        self._closed.set()

    # -- plugin -> backend ------------------------------------------------------------------
    async def _handle_request(self, method: str, params: Any, req_id: Any) -> Any:
        params = params or {}
        self.calls.append((method, params))
        if method == 'hello':
            if str(params.get('protocol', '')).split('.')[0] != P.PROTOCOL_VERSION.split('.')[0]:
                raise RpcError(P.PROTOCOL_UNSUPPORTED, 'unsupported protocol')
            if params['plugin']['name'] != self.plugin_name:
                raise RpcError(P.INVALID_PARAMS, 'plugin name does not match')
            resumed = params.get('resume') == self.session_id
            self.hello = params
            self.actions = {a['id']: a for a in params['actions']}
            asyncio.get_running_loop().call_soon(lambda: asyncio.ensure_future(self._open_project(resumed)))
            return {'protocol': P.PROTOCOL_VERSION, 'session_id': self.session_id, 'resumed': resumed,
                    'heartbeat_interval': 15}
        if method == 'task.create':
            self._task_counter += 1
            task_id = f"{params['key']}#{self._task_counter}"
            self.tasks[task_id] = {**params, 'id': task_id, 'state': 'queued', 'done': 0, 'failed': 0}
            if self.auto_start_tasks or not params.get('queued', True):
                asyncio.get_running_loop().call_later(0.01, lambda: asyncio.ensure_future(self.start_task(task_id)))
            return {'task_id': task_id}
        if method == 'commit':
            commit = m.DataCommit.from_dict(params['commit'])
            res = await asyncio.to_thread(self._data.commit, commit, params.get('group_id'), params.get('author'))
            self.commits.append(params)
            return {'commit': res.commit, 'ids': res.ids, 'sequence': res.sequence}
        if method == 'ids.allocate':
            if params.get('kind') not in s.PLUGIN_ID_KINDS:
                raise RpcError(P.FORBIDDEN, f"cannot allocate {params.get('kind')!r}")
            start = await asyncio.to_thread(self._data.allocate_ids, params['kind'], int(params.get('count', 1)))
            return {'start': start, 'count': int(params.get('count', 1))}
        if method == 'vector_type.upsert':
            vt = m.from_dict(m.VectorType, params['vector_type'])
            if vt.source != self.plugin_name:
                raise RpcError(P.FORBIDDEN, 'vector type source must be the plugin name')
            vt = await asyncio.to_thread(self._data.upsert_vector_type, vt)
            return {'vector_type': vt}
        if method == 'vector_type.delete':
            await asyncio.to_thread(self._data.delete_vector_type, params['id'])
            return {}
        if method == 'map.delete':
            await asyncio.to_thread(self._data.delete_map, params['id'])
            return {}
        if method == 'params.set':
            await asyncio.to_thread(self._store_params, params['params'])
            return {'params': params['params']}
        raise RpcError(P.METHOD_NOT_FOUND, f'unknown method {method!r}')

    async def _handle_notification(self, method: str, params: Any) -> None:
        params = params or {}
        self.calls.append((method, params))
        if method == 'task.progress':
            t = self.tasks.get(params['task_id'])
            if t is not None:
                t.update({k: v for k, v in params.items() if k != 'task_id'})
        elif method == 'task.done':
            t = self.tasks.get(params['task_id'])
            if t is not None:
                t['state'] = 'cancelled' if params.get('cancelled') else 'done'
        elif method == 'task.failed':
            t = self.tasks.get(params['task_id'])
            if t is not None:
                t['state'] = 'failed'
                t['error'] = params.get('error')
        elif method == 'notify':
            self.notifs.extend(params.get('notifs') or [])
        elif method == 'log':
            self.logs.append(params)
        elif method == 'db.changed':
            self.db_changes.append(params)
        elif method == 'actions.update':
            self.actions = {a['id']: a for a in params['actions']}

    async def _open_project(self, resumed: bool) -> None:
        if resumed and self.open_result is not None:
            self._ready.set()
            return
        stored = self.stored_params
        if stored is None:
            stored = self._data.stored_params(self.plugin_name)
        self.open_result = await self.peer.request('project.open', {
            'project': {'id': 'test-project', 'name': self.project_path.name, 'path': str(self.project_path)},
            'data_dir': str(self.project_path / 'plugin_data' / self.plugin_name.lower()),
            'params': stored,
        }, timeout=60)
        await asyncio.to_thread(self._store_params, self.open_result['params'])
        self._ready.set()

    def _store_params(self, params: dict) -> None:
        conn = sqlite3.connect(str(self.project_path / 'project.db'), isolation_level=None)
        try:
            conn.execute("INSERT OR REPLACE INTO user_defaults (user_id, key, data) VALUES (?, 'params', ?)",
                         (s.plugin_params_user_id(self.plugin_name), json.dumps(params)))
        finally:
            conn.close()

    # -- test driver ------------------------------------------------------------------------
    async def wait_ready(self, timeout: float = 30) -> None:
        await asyncio.wait_for(self._ready.wait(), timeout)

    async def wait_closed(self, timeout: float = 30) -> None:
        await asyncio.wait_for(self._closed.wait(), timeout)

    async def wait_for(self, predicate: Callable[[], bool], timeout: float = 10, interval: float = 0.02) -> None:
        deadline = asyncio.get_running_loop().time() + timeout
        while not predicate():
            if asyncio.get_running_loop().time() > deadline:
                raise TimeoutError('condition not met')
            await asyncio.sleep(interval)

    async def execute(self, action: str, context: dict | None = None, timeout: float = 60) -> dict:
        return await self.peer.request('action.execute', {'action': action, 'context': context or {}},
                                       timeout=timeout)

    async def update_params(self, params: dict) -> dict:
        res = await self.peer.request('params.update', {'params': params}, timeout=30)
        await asyncio.to_thread(self._store_params, res['params'])
        return res

    async def start_task(self, task_id: str) -> None:
        t = self.tasks[task_id]
        if t['state'] == 'queued':
            t['state'] = 'running'
            await self.peer.notify('task.start', {'task_id': task_id})

    async def stop_task(self, task_id: str) -> dict:
        return await self.peer.request('task.stop', {'task_id': task_id}, timeout=10)

    async def send_event(self, method: str, params: dict) -> None:
        await self.peer.notify(method, params)

    async def ping(self) -> dict:
        return await self.peer.request('ping', {}, timeout=10)

    async def cancel(self, request_id) -> None:
        await self.peer.notify('$/cancel', {'id': request_id})

    async def shutdown(self) -> None:
        try:
            await self.peer.request('project.close', {}, timeout=30)
            await self.peer.request('shutdown', {}, timeout=30)
        finally:
            await self.peer.close()


def run_plugin_in_thread(plugin, env: dict) -> tuple[threading.Thread, dict]:
    """Run ``plugin`` with a PluginRuntime on its own thread/loop (in-process test helper).
    Returns the thread and a dict that receives ``exit_code``."""
    from .runtime import PluginRuntime, RuntimeConfig
    result: dict = {}

    def target():
        config = RuntimeConfig.from_env(env)
        runtime = PluginRuntime(plugin, config)
        result['runtime'] = runtime
        result['exit_code'] = asyncio.run(runtime.run())

    thread = threading.Thread(target=target, daemon=True, name='plugin-runtime')
    thread.start()
    return thread, result
