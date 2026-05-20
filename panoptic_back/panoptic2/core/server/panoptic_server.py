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

        # DbWatcher per loaded project (id → watcher)
        self._watchers: dict[str, DbWatcher] = {}

        # asyncio loop — set in on_startup()
        self._loop: asyncio.AbstractEventLoop | None = None

        self._register_events()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_startup(self) -> None:
        """Call from FastAPI/uvicorn startup hook to capture the running event loop."""
        self._loop = asyncio.get_running_loop()

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

        await self._emit_connection_state(connection_id)
        await self._emit_update_projects()

    async def _close_project(self, id_: str, connection_id: str) -> None:
        # Only close the watcher when no connection is still on this project
        remaining = sum(
            1 for s in self._connection_states.values()
            if s.connected_project == id_ and s.connection_id != connection_id
        )
        if remaining == 0:
            self._detach_watcher(id_)
            await anyio.to_thread.run_sync(
                lambda: self._panoptic.close_project(id_)
            )

        state = self._connection_states.get(connection_id)
        if state:
            state.connected_project = None

        await self._emit_connection_state(connection_id)
        await self._emit_update_projects()

    # ------------------------------------------------------------------
    # Watcher management
    # ------------------------------------------------------------------

    def _attach_watcher(self, id_: str, data_db_path) -> None:
        watcher = DbWatcher(
            data_db_path=data_db_path,
            project_id=id_,
            broadcast_fn=self._broadcast_commits,
        )
        self._watchers[id_] = watcher
        # _attach_watcher is always called from an async context, so ensure_future is safe.
        asyncio.ensure_future(watcher.run())

    def _detach_watcher(self, id_: str) -> None:
        watcher = self._watchers.pop(id_, None)
        if watcher:
            watcher.stop()

    # ------------------------------------------------------------------
    # Async broadcast helpers
    # ------------------------------------------------------------------

    async def _broadcast_commits(self, id_: str, commit_ids: list[int]) -> None:
        sids = self._get_project_sids(id_)
        if not sids:
            return
        await self._sio.emit('commits', {'project_id': id_, 'commit_ids': commit_ids}, to=sids)

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
        """Return a sync callable that bridges task updates into the event loop."""
        loop  = self._loop
        sio   = self._sio
        server = self

        def on_update(states: list[TaskState]) -> None:
            payload = {
                'project_id': id_,
                'tasks': [s.model_dump(mode='json') for s in states],
            }

            async def _emit() -> None:
                sids = server._get_project_sids(id_)
                if sids:
                    await sio.emit('tasks', payload, to=sids)

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


