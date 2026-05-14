"""PanopticServer2 — owns the Socket.IO server and all async wiring.

Responsibilities:
- Socket.IO event registration (connect, disconnect, load_project, close_project)
- Connection-state tracking: sid → connection_id → project_uid
- DbWatcher lifecycle per loaded project
- sync→async callback bridge for task updates
- Broadcasts: server_state, client_state, commits, tasks
"""

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import socketio

from panoptic.models.models import TaskState
from panoptic2.core.panoptic.models import PanopticState
from panoptic2.core.panoptic.panoptic import Panoptic2
from panoptic2.core.watcher.db_watcher import DbWatcher


# ---------------------------------------------------------------------------
# Client state
# ---------------------------------------------------------------------------

@dataclass
class ClientState:
    connection_id: str
    connected_project: Optional[str] = None   # project uid or None
    connected_at: Optional[datetime] = None

    def __post_init__(self):
        if self.connected_at is None:
            self.connected_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            'connection_id': self.connection_id,
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
        self._sid_to_connection_id:   dict[str, str]        = {}
        self._connection_id_to_sids:  dict[str, list[str]]  = {}
        self._client_states:          dict[str, ClientState] = {}
        self._connect_id_counter = 0

        # DbWatcher per loaded project (uid → watcher)
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

            if connection_id not in self._client_states:
                self._client_states[connection_id] = ClientState(connection_id=connection_id)

            self._sid_to_connection_id[sid] = connection_id
            self._connection_id_to_sids.setdefault(connection_id, []).append(sid)

            logging.info(f"connect sid={sid} connection_id={connection_id}")
            await self._emit_server_state(sids=[sid])
            await self._emit_client_state(connection_id)

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
                self._client_states.pop(connection_id, None)
                logging.info(f"connection {connection_id} fully disconnected")
            else:
                logging.info(f"disconnect sid={sid}, {len(sids)} sids remain for {connection_id}")

        @sio.event
        async def load_project(sid, data: dict):
            uid = data.get('uid')
            connection_id = self._sid_to_connection_id.get(sid)
            if not uid or not connection_id:
                return
            try:
                await self._load_project(uid, connection_id)
            except Exception as e:
                logging.exception(f"load_project failed for uid={uid!r}: {e}")

        @sio.event
        async def close_project(sid, data: dict):
            uid = data.get('uid')
            connection_id = self._sid_to_connection_id.get(sid)
            if not uid or not connection_id:
                return
            await self._close_project(uid, connection_id)

    # ------------------------------------------------------------------
    # Project wiring
    # ------------------------------------------------------------------

    async def _load_project(self, uid: str, connection_id: str) -> None:
        project = self._panoptic.load_project(uid)

        # Start DbWatcher if not already running for this project
        if uid not in self._watchers:
            self._attach_watcher(uid, project.data_db_path)

        # Wire task callback if not yet wired
        if self._panoptic.get_project(uid).task_manager._on_update is None:
            project.task_manager._on_update = self._make_task_callback(uid)

        state = self._client_states.get(connection_id)
        if state:
            state.connected_project = uid

        await self._emit_client_state(connection_id)
        await self._emit_server_state()

    async def _close_project(self, uid: str, connection_id: str) -> None:
        # Only close the watcher when no connection is still on this project
        remaining = sum(
            1 for s in self._client_states.values()
            if s.connected_project == uid and s.connection_id != connection_id
        )
        if remaining == 0:
            self._detach_watcher(uid)
            self._panoptic.close_project(uid)

        state = self._client_states.get(connection_id)
        if state:
            state.connected_project = None

        await self._emit_client_state(connection_id)
        await self._emit_server_state()

    # ------------------------------------------------------------------
    # Watcher management
    # ------------------------------------------------------------------

    def _attach_watcher(self, uid: str, data_db_path) -> None:
        watcher = DbWatcher(
            data_db_path=data_db_path,
            project_uid=uid,
            broadcast_fn=self._broadcast_commits,
        )
        self._watchers[uid] = watcher
        # _attach_watcher is always called from an async context, so ensure_future is safe.
        asyncio.ensure_future(watcher.run())

    def _detach_watcher(self, uid: str) -> None:
        watcher = self._watchers.pop(uid, None)
        if watcher:
            watcher.stop()

    # ------------------------------------------------------------------
    # Async broadcast helpers
    # ------------------------------------------------------------------

    async def _broadcast_commits(self, uid: str, commit_ids: list[int]) -> None:
        sids = self._get_project_sids(uid)
        if not sids:
            return
        await self._sio.emit('commits', {'project_uid': uid, 'commit_ids': commit_ids}, to=sids)

    async def _emit_server_state(self, sids: list[str] = None) -> None:
        state: PanopticState = self._panoptic.get_state()
        payload = {
            'projects':            [_struct_to_dict(p) for p in state.projects],
            'loaded_project_uids': state.loaded_project_uids,
            'plugins':             [_struct_to_dict(p) for p in state.plugins],
            'users':               [_struct_to_dict(u) for u in state.users],
        }
        await self._sio.emit('server_state', payload, to=sids)

    async def _emit_client_state(self, connection_id: str) -> None:
        state = self._client_states.get(connection_id)
        if state is None:
            return
        sids = self._connection_id_to_sids.get(connection_id)
        if not sids:
            return
        await self._sio.emit('client_state', state.to_dict(), to=sids)

    # ------------------------------------------------------------------
    # Task callback bridge  (sync thread → async event loop)
    # ------------------------------------------------------------------

    def _make_task_callback(self, uid: str):
        """Return a sync callable that bridges task updates into the event loop."""
        loop  = self._loop
        sio   = self._sio
        server = self

        def on_update(states: list[TaskState]) -> None:
            payload = {
                'project_uid': uid,
                'tasks': [s.model_dump(mode='json') for s in states],
            }

            async def _emit() -> None:
                sids = server._get_project_sids(uid)
                if sids:
                    await sio.emit('tasks', payload, to=sids)

            loop.call_soon_threadsafe(lambda: asyncio.ensure_future(_emit()))

        return on_update

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_project_sids(self, uid: str) -> list[str]:
        result = []
        for conn_id, state in self._client_states.items():
            if state.connected_project == uid:
                result.extend(self._connection_id_to_sids.get(conn_id, []))
        return result

    def _next_connection_id(self) -> str:
        self._connect_id_counter += 1
        raw = f"{time.time()}-{self._connect_id_counter}"
        return hashlib.sha1(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _struct_to_dict(obj) -> dict:
    """Convert a msgspec.Struct to a plain dict for JSON emission."""
    import msgspec
    return msgspec.json.decode(msgspec.json.encode(obj), type=dict)
