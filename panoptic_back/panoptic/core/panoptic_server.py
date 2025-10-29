import asyncio
import hashlib
import time
from dataclasses import asdict
from datetime import datetime

import socketio

from panoptic.core.panoptic import Panoptic
from panoptic.models import DbUpdate, IgnoredPluginPayload, DbCommit
from panoptic.models.models import PanopticClientState, SyncData, TaskState, User, UserState, ProjectUpdatePayload
from panoptic.utils import serialize_payload, AsyncAdaptiveBuffer

users = [
    UserState(id=1, name="Annie Flaubert"),
    UserState(id=2, name="Marcel Dumas"),
    UserState(id=3, name="Alexandre Ernaux"),
    UserState(id=4, name="Victor Baudelaire"),
    UserState(id=5, name="Gustave Sartre"),
    UserState(id=6, name="Jean-Paul Hugo"),
    UserState(id=7, name="Honoré Molière"),
    UserState(id=8, name="François-Marie Proust"),
    UserState(id=9, name="Jean-Baptiste Voltaire"),
    UserState(id=10, name="Charles Balzac"),
]


class PanopticServer:
    def __init__(self, panoptic: Panoptic):
        self.sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
        self.panoptic = panoptic

        # Mappings
        self.sid_to_connection_id: dict[str, str] = {}
        self.connection_id_to_sids: dict[str, list[str]] = {}
        self._connect_id_counter = 0
        self.client_states: dict[str, PanopticClientState] = {}

        self._connections_to_close: list[str] = []
        self._close_connections_task: asyncio.Task | None = None

        # one buffer per _project
        self._commit_buffers: dict[int, AsyncAdaptiveBuffer] = {}
        self._tasks_buffers: dict[int, AsyncAdaptiveBuffer] = {}

        # users
        self.users: dict[int, UserState] = {u.id: u for u in users}
        self._connection_to_user: dict[str, UserState] = {}
        self.ask_users: bool = False

        @self.sio.event
        async def connect(sid, environ, auth):
            client_connection_id = auth.get('connection_id') if auth else None

            assigned_connection_id = client_connection_id
            if assigned_connection_id is None:
                assigned_connection_id = self._get_next_connect_id()

            if assigned_connection_id not in self.client_states:
                self.client_states[assigned_connection_id] = PanopticClientState(
                    connection_id=assigned_connection_id,
                    connected_project=None,
                    connected_at=datetime.now()
                )

            # Store the mappings
            self.sid_to_connection_id[sid] = assigned_connection_id
            if assigned_connection_id not in self.connection_id_to_sids:
                self.connection_id_to_sids[assigned_connection_id] = []
            self.connection_id_to_sids[assigned_connection_id].append(sid)

            print(f"Client connected: sid={sid}, assigned connection_id={assigned_connection_id}")
            print(f"Current SIDs for {assigned_connection_id}: {self.connection_id_to_sids[assigned_connection_id]}")

            await self._emit_server_state()
            await self._emit_client_state(assigned_connection_id)

        @self.sio.event
        async def disconnect(sid):
            if sid in self.sid_to_connection_id:
                connection_id = self.sid_to_connection_id[sid]
                print(f"Client disconnected: sid={sid}, connection_id={connection_id}")

                # Clean up mappings
                del self.sid_to_connection_id[sid]

                if connection_id in self.connection_id_to_sids:
                    try:
                        self.connection_id_to_sids[connection_id].remove(sid)
                        if not self.connection_id_to_sids[connection_id]:
                            del self.connection_id_to_sids[connection_id]
                            if connection_id in self.client_states:
                                self.close_connection(connection_id)
                            print(f"Connection ID {connection_id} has no more clients and is removed.")
                    except ValueError:
                        # This case should ideally not happen with proper connect/disconnect flow
                        print(f"Warning: sid {sid} not found in list for connection_id {connection_id}.")
            else:
                print(f"Warning: Disconnected sid {sid} had no connection_id mapping.")

        @self.sio.event
        async def connect_user(sid, data: int):
            print(f'ask user {data}')
            connection_id = self.sid_to_connection_id[sid]
            ok = await self.connect_user(connection_id, data)
            if ok:
                self.client_states[connection_id].user = self.users[data]
            await self._emit_client_state(connection_id)
            await self._emit_server_state()

        @self.sio.event
        async def disconnect_user(sid):
            connection_id = self.sid_to_connection_id[sid]
            self.disconnect_user(connection_id)
            await self._emit_client_state(connection_id)
            await self._emit_server_state()



    async def connect_user(self, connection_id: str, user_id: int):
        if user_id not in self.users:
            return False
        user = self.users[user_id]
        if user.connected_to:
            if user.connected_to == connection_id:
                return user
            return False
        self._connection_to_user[connection_id] = user
        user.connected_to = connection_id
        return user

    def disconnect_user(self, connection_id: str):
        if connection_id not in self._connection_to_user:
            return
        user = self._connection_to_user[connection_id]
        if user.connected_to != connection_id:
            return
        user.connected_to = None
        del self._connection_to_user[connection_id]
        self.client_states[connection_id].user = None

    async def broadcast_db_update(self, update: DbUpdate, sid=None):
        await self.sio.emit("db_update", asdict(update), skip_sid=sid)

    def _create_commit_buffer(self, project_id: int):
        async def flush_callback(commits: list[DbCommit]):
            return await self._flush_commits(project_id, commits)

        if project_id in self._commit_buffers:
            return
        self._commit_buffers[project_id] = AsyncAdaptiveBuffer(on_flush=flush_callback)

    def _create_tasks_buffer(self, project_id: int):
        async def flush_callback(tasks: list[TaskState]):
            return await self._flush_tasks(project_id, tasks)

        if project_id in self._tasks_buffers:
            return
        self._tasks_buffers[project_id] = AsyncAdaptiveBuffer(on_flush=flush_callback, flush_interval=0.5)

    async def _flush_commits(self, project_id: int, commits: list[DbCommit]):
        sids = self.get_project_sids(project_id)
        await self.sio.emit('commit', serialize_payload(commits), to=sids)

    async def _flush_tasks(self, project_id: int, tasks: list[list[TaskState]]):
        sids = self.get_project_sids(project_id)
        tasks = tasks[-1]  # only send the last update
        await self.sio.emit('tasks', serialize_payload(tasks), to=sids)

    def _get_next_connect_id(self) -> str:
        """
        Generates a new unique connection ID based on the current time and a counter.
        """
        self._connect_id_counter += 1
        raw_id = f"{time.time()}-{self._connect_id_counter}"
        hashed_id = hashlib.sha1(raw_id.encode()).hexdigest()
        return hashed_id

    def get_client_state(self, connection_id: str):
        return self.client_states[connection_id]

    async def _emit_client_state(self, connection_id: str):
        state = self.client_states[connection_id]
        if not state:
            return
        sids = self.connection_id_to_sids[connection_id]
        print(f'send to {sids}')
        await self.sio.emit('client_state', state.model_dump(mode='json'), to=sids)

    async def _emit_server_state(self, sids: list[str] = None):
        state = await self.panoptic.get_state()
        state.ask_user = self.ask_users
        state.users = list(self.users.values())
        await self.sio.emit('server_state', state.model_dump(mode='json'), to=sids)

    async def load_project(self, project_id: int, connection_id: str = None):
        project = await self.panoptic.load_project(project_id)
        if project:
            project.on.sync.register(self.broadcast_sync_event)
            self._create_commit_buffer(project.id)
            self._create_tasks_buffer(project.id)
        if connection_id:
            state = self.client_states[connection_id]
            state.connected_project = project.id
            await self._emit_client_state(connection_id)

    async def create_project(self, name: str, path: str, connection_id: str = None):
        project = await self.panoptic.create_project(name, path)
        await self.load_project(project.id, connection_id)
        await self._emit_server_state()

    async def import_project(self, path: str, connection_id: str = None):
        project = await self.panoptic.import_project(path)
        if project:
            await self.load_project(project.id, connection_id)
            await self._emit_server_state()

    async def update_project(self, req: ProjectUpdatePayload):
        await self.panoptic.update_project(req.id, req.name, req.ignored_plugins)
        await self._emit_server_state()

    async def remove_project(self, project_id: int):
        await self.panoptic.remove_project(project_id)
        await self._emit_server_state()

    async def close_project(self, project_id: int, connection_id: str = None):
        count = len([s for s in self.client_states.values() if s.connected_project == project_id])
        if count == 1:
            try:
                await self.panoptic.close_project(project_id)
            except Exception as e:
                print(e)
                pass
        self.client_states[connection_id].connected_project = None

        await self._emit_client_state(connection_id)

    async def _close_unused_connections_task(self):
        await asyncio.sleep(2.0)
        for connection_id in self._connections_to_close:
            if connection_id not in self.connection_id_to_sids:
                self.disconnect_user(connection_id)
                del self.client_states[connection_id]
        self._close_connections_task = None

    def close_connection(self, connection_id: str):
        if connection_id not in self._connections_to_close:
            self._connections_to_close.append(connection_id)
        if self._close_connections_task:
            self._close_connections_task.cancel()
        self._close_connections_task = asyncio.create_task(self._close_unused_connections_task())

    async def set_ignored_plugin(self, data: IgnoredPluginPayload):
        await self.panoptic.set_ignored_plugin(data.project, data.plugin, data.value)
        await self._emit_server_state()

    async def broadcast_sync_event(self, data: SyncData):
        project = self.panoptic.open_projects.get(data.project_id, None)
        # print(f'try emit {data.project_id}')
        if project is None:
            return

        if data.key == 'commit':
            await self._commit_buffers[project.id].push(data.data)
            return
        if data.key == 'tasks':
            await self._tasks_buffers[project.id].push(data.data)
            return
        sids = self.get_project_sids(data.project_id)
        payload = serialize_payload(data.data)
        print(f'emit: {data.key} to {sids}')
        await self.sio.emit(data.key, payload, to=sids)

    def get_project_sids(self, project_id: int):
        res = []
        for conn_id in self.client_states.keys():
            state = self.client_states[conn_id]
            if state.connected_project == project_id:
                res.extend(self.connection_id_to_sids[conn_id])
        return res
