"""PanopticServer2 — owns the Socket.IO server and all async wiring.

Responsibilities:
- Socket.IO event registration (connect, disconnect, load_project, close_project)
- Connection-state tracking: sid → connection_id → project_id
- DbWatcher lifecycle per loaded project
- sync→async callback bridge for task updates
- Broadcasts: update_projects, update_plugins, update_users, connection_state, commits, tasks
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import anyio

import socketio

from panoptic.core.databases.panoptic.models import User
from panoptic.core.databases.panoptic.panoptic_db import DEFAULT_USER_ID
from panoptic.models.models import TaskState
from panoptic2.core.panoptic.panoptic import Panoptic2
from panoptic2.core.watcher.db_watcher import DbWatcher


# ---------------------------------------------------------------------------
# Connection state
# ---------------------------------------------------------------------------

@dataclass
class ConnectionState:
    connection_id: str
    user: User
    connected_project: Optional[str] = None
    connected_at: Optional[datetime] = None

    def __post_init__(self):
        if self.connected_at is None:
            self.connected_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            'connection_id': self.connection_id,
            'user': {'id': self.user.id, 'name': self.user.name},
            'connected_project': self.connected_project,
        }


# ---------------------------------------------------------------------------
# PanopticServer2
# ---------------------------------------------------------------------------

class PanopticServer2:
    def __init__(self, panoptic: Panoptic2, sio: socketio.AsyncServer):
        self._panoptic = panoptic
        self._sio      = sio

        # Connection state
        self._sid_to_connection_id:   dict[str, str]             = {}
        self._connection_id_to_sids:  dict[str, list[str]]       = {}
        self._connection_states:      dict[str, ConnectionState] = {}
        self._connect_id_counter = 0

        # DbWatcher per loaded project (id → watcher) + its asyncio task
        self._watchers:      dict[str, DbWatcher]          = {}
        self._watcher_tasks: dict[str, asyncio.Task]       = {}

        # Last known project per user (user_id → project_id), in-memory only
        self._user_last_project: dict[str, str | None] = {}

        # asyncio loop — set in on_startup()
        self._loop: asyncio.AbstractEventLoop | None = None

        self._register_events()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_startup(self) -> None:
        """Call from FastAPI/uvicorn startup hook to capture the running event loop."""
        self._loop = asyncio.get_running_loop()

    async def shutdown(self) -> None:
        """Tear down all watchers so every DataReader connection closes before the
        process exits. Without this, SQLite leaves behind -wal/-shm files."""
        watcher_ids = list(self._watchers.keys())
        for id_ in watcher_ids:
            await self._detach_watcher(id_)
        # Final TRUNCATE checkpoint on every still-loaded project's data DB.
        # The readers are now gone, so the checkpoint will succeed.
        await anyio.to_thread.run_sync(self._checkpoint_all_projects)

    def _checkpoint_all_projects(self) -> None:
        from panoptic.core.databases.data.data_writer import DataWriter
        for project in self._panoptic._loaded_projects.values():
            try:
                with DataWriter(str(project.data_db_path)) as w:
                    w.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception:
                logging.exception("WAL checkpoint failed for %s", project.data_db_path)

    # ------------------------------------------------------------------
    # Socket.IO event registration
    # ------------------------------------------------------------------

    def _register_events(self) -> None:
        sio = self._sio

        @sio.event
        async def connect(sid, environ, auth):
            client_connection_id = (auth or {}).get('connection_id')
            connection_id = client_connection_id or self._next_connection_id()

            if connection_id not in self._connection_states:
                default_user = self._get_default_user()
                self._connection_states[connection_id] = ConnectionState(
                    connection_id=connection_id,
                    user=default_user,
                )

            self._sid_to_connection_id[sid] = connection_id
            self._connection_id_to_sids.setdefault(connection_id, []).append(sid)

            logging.info(f"connect sid={sid} connection_id={connection_id}")
            await self._emit_update_projects(sids=[sid])
            await self._emit_update_plugins(sids=[sid])
            await self._emit_update_users(sids=[sid])

            # Restore last project for this user if one is remembered
            state = self._connection_states[connection_id]
            last_project = self._user_last_project.get(state.user.id)
            known_ids = {p.id for p in self._panoptic.db.get_projects()}
            if last_project and last_project in known_ids and state.connected_project is None:
                try:
                    await self._load_project(last_project, connection_id)
                except Exception:
                    logging.exception(f"auto-restore project {last_project!r} failed")
                    await self._emit_connection_state(connection_id)
            else:
                await self._emit_connection_state(connection_id)

        @sio.event
        async def disconnect(sid):
            connection_id = self._sid_to_connection_id.pop(sid, None)
            if connection_id is None:
                return

            sids = self._connection_id_to_sids.get(connection_id, [])
            try:
                sids.remove(sid)
            except ValueError:
                pass

            if not sids:
                self._connection_id_to_sids.pop(connection_id, None)
                self._connection_states.pop(connection_id, None)
                logging.info(f"connection {connection_id} fully disconnected")
            else:
                logging.info(f"disconnect sid={sid}, {len(sids)} sids remain for {connection_id}")

        @sio.event
        async def load_project(sid, data: dict):
            id_ = data.get('id')
            connection_id = self._sid_to_connection_id.get(sid)
            if not id_ or not connection_id:
                return
            try:
                await self._load_project(id_, connection_id)
            except Exception as e:
                logging.exception(f"load_project failed for id={id_!r}: {e}")

        @sio.event
        async def close_project(sid, data: dict):
            id_ = data.get('id')
            connection_id = self._sid_to_connection_id.get(sid)
            if not id_ or not connection_id:
                return
            await self._close_project(id_, connection_id)

    # ------------------------------------------------------------------
    # Project wiring
    # ------------------------------------------------------------------

    async def _load_project(self, id_: str, connection_id: str) -> None:
        project = await anyio.to_thread.run_sync(
            lambda: self._panoptic.load_project(id_)
        )

        # Start DbWatcher if not already running for this project
        if id_ not in self._watchers:
            self._attach_watcher(id_, project.data_db_path)

        # Wire task callback if not yet wired
        if self._panoptic.get_project(id_).task_manager._on_update is None:
            project.task_manager._on_update = self._make_task_callback(id_)

        state = self._connection_states.get(connection_id)
        if state:
            state.connected_project = id_
            self._user_last_project[state.user.id] = id_

        await self._emit_connection_state(connection_id)
        await self._emit_update_projects()

    async def _close_project(self, id_: str, connection_id: str) -> None:
        # Only close the watcher when no connection is still on this project
        remaining = sum(
            1 for s in self._connection_states.values()
            if s.connected_project == id_ and s.connection_id != connection_id
        )
        if remaining == 0:
            await self._detach_watcher(id_)
            await anyio.to_thread.run_sync(
                lambda: self._panoptic.close_project(id_)
            )

        state = self._connection_states.get(connection_id)
        if state:
            state.connected_project = None
            self._user_last_project[state.user.id] = None

        await self._emit_connection_state(connection_id)
        await self._emit_update_projects()

    # ------------------------------------------------------------------
    # Watcher management
    # ------------------------------------------------------------------

    def _attach_watcher(self, id_: str, data_db_path) -> None:
        watcher = DbWatcher(
            data_db_path=data_db_path,
            project_id=id_,
            broadcast_fn=self._broadcast_update,
        )
        self._watchers[id_] = watcher
        task = asyncio.ensure_future(watcher.run())
        self._watcher_tasks[id_] = task

    async def _detach_watcher(self, id_: str) -> None:
        self._watchers.pop(id_, None)
        task = self._watcher_tasks.pop(id_, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    # ------------------------------------------------------------------
    # Async broadcast helpers
    # ------------------------------------------------------------------

    async def _broadcast_update(self, id_: str, sequence: int) -> None:
        sids = self._get_project_sids(id_)
        if not sids:
            return
        await self._sio.emit('db_update', {'project_id': id_, 'sequence': sequence}, to=sids)

    async def _emit_update_projects(self, sids: list[str] = None) -> None:
        await self._sio.emit('update_projects', to=sids)

    async def _emit_update_plugins(self, sids: list[str] = None) -> None:
        await self._sio.emit('update_plugins', to=sids)

    async def _emit_update_users(self, sids: list[str] = None) -> None:
        await self._sio.emit('update_users', to=sids)

    async def _emit_connection_state(self, connection_id: str) -> None:
        state = self._connection_states.get(connection_id)
        if state is None:
            return
        sids = self._connection_id_to_sids.get(connection_id)
        if not sids:
            return
        await self._sio.emit('connection_state', state.to_dict(), to=sids)

    def _get_default_user(self) -> User:
        users = self._panoptic.get_users()
        return next((u for u in users if u.id == DEFAULT_USER_ID), users[0])

    # ------------------------------------------------------------------
    # Task callback bridge  (sync thread → async event loop)
    # ------------------------------------------------------------------

    def _make_task_callback(self, id_: str):
        """Return a sync callable that bridges task updates into the event loop.

        Throttled to at most 4 socket emissions per second; finished/stopped
        states always bypass the throttle so the UI sees the final state.
        """
        import time as _time

        loop   = self._loop
        sio    = self._sio
        server = self

        _INTERVAL  = 0.25          # seconds between emissions
        _last: list[float] = [0.0] # mutable cell; mutated only from the task thread
        _plugins_info_sent: set[str] = set()  # task IDs that already triggered plugins_info
        _atlas_sent: set[str] = set()         # task IDs that already triggered atlas event

        def on_update(states: list[TaskState]) -> None:
            now = _time.monotonic()
            # Only bypass throttle when no task is actively running (terminal state).
            # Checking `any(finished)` would always be True once LoadPluginTask finishes
            # because TaskManager keeps finished tasks in its registry indefinitely.
            terminal = not any(s.running for s in states)
            if not terminal and now - _last[0] < _INTERVAL:
                return
            _last[0] = now

            # Only fire plugins_info once per LoadPluginTask instance (stale finished
            # tasks stay in get_states() forever, so we must deduplicate by task ID).
            new_plugin_done = [
                s for s in states
                if s.key == 'LoadPluginTask' and s.finished and s.id not in _plugins_info_sent
            ]
            plugin_task_finished = bool(new_plugin_done)
            _plugins_info_sent.update(s.id for s in new_plugin_done)

            new_atlas_done = [
                s for s in states
                if s.key == 'GenerateAtlasTask' and s.finished and s.id not in _atlas_sent
            ]
            atlas_task_finished = bool(new_atlas_done)
            _atlas_sent.update(s.id for s in new_atlas_done)

            payload = {
                'project_id': id_,
                'tasks': [s.model_dump(mode='json') for s in states],
            }

            async def _emit() -> None:
                sids = server._get_project_sids(id_)
                if sids:
                    await sio.emit('tasks', payload, to=sids)
                    if plugin_task_finished:
                        await sio.emit('plugins_info', {'project_id': id_}, to=sids)
                    if atlas_task_finished:
                        await sio.emit('atlas', {'project_id': id_}, to=sids)

            loop.call_soon_threadsafe(lambda: asyncio.ensure_future(_emit()))

        return on_update

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_project_sids(self, id_: str) -> list[str]:
        result = []
        for conn_id, state in self._connection_states.items():
            if state.connected_project == id_:
                result.extend(self._connection_id_to_sids.get(conn_id, []))
        return result

    def _next_connection_id(self) -> str:
        self._connect_id_counter += 1
        raw = f"{time.time()}-{self._connect_id_counter}"
        return hashlib.sha1(raw.encode()).hexdigest()


