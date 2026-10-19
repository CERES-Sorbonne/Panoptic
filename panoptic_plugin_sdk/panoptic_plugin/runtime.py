"""Plugin process runtime: connection, handshake, dispatch, reconnection.

One runtime per plugin process. The asyncio loop owns the WebSocket; plugin code runs in a
thread pool and talks to the backend through :class:`Bridge` (thread-safe, blocking calls).
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import functools
import inspect
import logging
import os
import platform
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import protocol as P
from .introspect import InputError, coerce_inputs
from .models import ActionContext, Folder, from_dict, result_from_any
from .project import ProjectData, plugin_slug
from .rpc import ConnectionLost, RpcError, RpcPeer
from .tasks import TaskRunner

log = logging.getLogger('panoptic_plugin.runtime')

DEFAULT_CALL_TIMEOUT = 300.0


class Bridge:
    """Thread-safe access to the current RPC peer for synchronous plugin code."""

    def __init__(self, runtime: 'PluginRuntime'):
        self._rt = runtime

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        return self._rt.loop

    def call(self, method: str, params: Any = None, timeout: float | None = DEFAULT_CALL_TIMEOUT) -> Any:
        loop = self.loop
        if _on_loop_thread(loop):
            raise RuntimeError(f"blocking call to {method!r} from the event loop thread: "
                               f"use `await plugin.bridge.acall(...)` in async actions")
        fut = asyncio.run_coroutine_threadsafe(self.acall(method, params, timeout), loop)
        return fut.result()

    async def acall(self, method: str, params: Any = None, timeout: float | None = DEFAULT_CALL_TIMEOUT) -> Any:
        peer = self._rt.peer
        if peer is None or peer.closed:
            raise ConnectionLost('not connected to the backend')
        return await peer.request(method, params, timeout=timeout)

    def notify(self, method: str, params: Any = None) -> None:
        loop = self.loop
        if loop is None or loop.is_closed():
            return
        if _on_loop_thread(loop):
            asyncio.ensure_future(self.anotify(method, params))
        else:
            loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self.anotify(method, params)))

    async def anotify(self, method: str, params: Any = None) -> None:
        peer = self._rt.peer
        if peer is None or peer.closed:
            log.debug(f'dropped {method} (not connected)')
            return
        await peer.notify(method, params)


def _on_loop_thread(loop) -> bool:
    try:
        return asyncio.get_running_loop() is loop
    except RuntimeError:
        return False


@dataclass
class RuntimeConfig:
    url: str
    token: str | None = None
    project_path: Path | None = None
    project_id: str | None = None
    data_dir: Path | None = None
    reconnect_timeout: float = 15.0
    connect_timeout: float = 10.0
    max_workers: int = 8
    open_timeout: float = 10.0
    extra_headers: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls, env=None) -> 'RuntimeConfig':
        env = os.environ if env is None else env
        url = env.get(P.ENV_URL)
        if not url:
            raise SystemExit(f"{P.ENV_URL} is not set: plugins are started by the Panoptic backend")
        return cls(
            url=url,
            token=env.get(P.ENV_TOKEN),
            project_path=Path(env[P.ENV_PROJECT_PATH]) if env.get(P.ENV_PROJECT_PATH) else None,
            project_id=env.get(P.ENV_PROJECT_ID),
            data_dir=Path(env[P.ENV_DATA_DIR]) if env.get(P.ENV_DATA_DIR) else None,
            reconnect_timeout=float(env.get(P.ENV_RECONNECT_TIMEOUT, 15)),
        )


class HandshakeRefused(Exception):
    pass


class PluginRuntime:
    def __init__(self, plugin, config: RuntimeConfig):
        self.plugin = plugin
        self.config = config
        self.loop: asyncio.AbstractEventLoop | None = None
        self.peer: RpcPeer | None = None
        self.bridge = Bridge(self)
        self.session_id: str | None = None
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=config.max_workers, thread_name_prefix=f'plugin-{plugin.name}')
        self._project_open = False
        self._shutdown: asyncio.Event | None = None   # created in run()
        self._hello_sent = False
        plugin._runtime = self
        plugin.tasks = TaskRunner(self.bridge, owner=plugin.name)

    # ------------------------------------------------------------------
    # main loop
    # ------------------------------------------------------------------

    async def run(self) -> int:
        """Connect, handshake, serve. Returns the process exit code."""
        self.loop = asyncio.get_running_loop()
        self._shutdown = asyncio.Event()
        first = True
        try:
            while not self._shutdown.is_set():
                budget = self.config.connect_timeout if first else self.config.reconnect_timeout
                ws = await self._connect(budget)
                if ws is None:
                    log.error('backend unreachable, exiting')
                    return 3
                self.peer = RpcPeer(ws, self._handle_request, self._handle_notification)
                serve = asyncio.create_task(self.peer.serve())
                try:
                    await self._hello(resume=not first)
                except HandshakeRefused as e:
                    log.error(f'handshake refused: {e}')
                    await self.peer.close()
                    return 2
                except ConnectionLost:
                    pass
                first = False
                await serve
                if self._shutdown.is_set():
                    break
                log.warning('connection to the backend lost, reconnecting')
            return 0
        finally:
            await self._cleanup()

    async def _connect(self, budget: float):
        from websockets.asyncio.client import connect
        headers = dict(self.config.extra_headers)
        if self.config.token:
            headers['Authorization'] = f'Bearer {self.config.token}'
        deadline = time.monotonic() + budget
        delay = 0.2
        while True:
            try:
                return await connect(self.config.url, additional_headers=headers,
                                     max_size=P.MAX_MESSAGE_SIZE, open_timeout=self.config.open_timeout,
                                     ping_interval=None)
            except Exception as e:
                if time.monotonic() + delay > deadline:
                    log.debug(f'connect failed: {e!r}')
                    return None
                await asyncio.sleep(delay)
                delay = min(delay * 2, 2.0)

    async def _hello(self, resume: bool) -> None:
        plugin = self.plugin
        params = {
            'protocol': P.PROTOCOL_VERSION,
            'sdk': {'name': P.SDK_NAME, 'version': P.SDK_VERSION, 'language': 'python',
                    'runtime': f'{platform.python_implementation()} {platform.python_version()}'},
            'plugin': plugin.describe(),
            'pid': os.getpid(),
            'actions': plugin.action_descriptions(),
            'params': plugin.params_description(),
            'capabilities': {'direct_data_writes': bool(plugin.direct_data_writes), 'batch': True,
                             'cancel': True, 'actions_update': True},
            'resume': self.session_id if resume else None,
        }
        try:
            res = await self.peer.request('hello', params, timeout=30)
        except RpcError as e:
            if e.code in (P.UNAUTHORIZED, P.PROTOCOL_UNSUPPORTED, P.INVALID_PARAMS):
                raise HandshakeRefused(e.message)
            raise
        resumed = bool(res.get('resumed')) and resume
        self.session_id = res.get('session_id')
        self._hello_sent = True
        if resume and not resumed:
            # The backend lost our state: its task list no longer has our tasks.
            await self.loop.run_in_executor(self.executor, self.plugin.tasks.stop_all)
        elif resumed:
            for task in self.plugin.tasks.active():
                await self.peer.notify('task.progress', task.state.progress_params())

    async def _cleanup(self) -> None:
        plugin = self.plugin
        try:
            await self.loop.run_in_executor(self.executor, self._close_project)
        except Exception:
            log.exception('cleanup failed')
        if self.peer is not None and not self.peer.closed:
            await self.peer.close()
        self.executor.shutdown(wait=False, cancel_futures=True)
        plugin._runtime = None

    def _close_project(self) -> None:
        if not self._project_open:
            return
        self._project_open = False
        self.plugin.tasks.close()
        try:
            self.plugin.on_stop()
        except Exception:
            log.exception('on_stop failed')
        if self.plugin.project is not None:
            self.plugin.project.close()

    def actions_changed(self) -> None:
        if self._hello_sent:
            self.bridge.notify('actions.update', {'actions': self.plugin.action_descriptions()})

    # ------------------------------------------------------------------
    # dispatch
    # ------------------------------------------------------------------

    async def _handle_request(self, method: str, params: Any, req_id: Any) -> Any:
        params = params or {}
        handler = {
            'project.open': self._project_open_handler,
            'project.close': self._project_close_handler,
            'action.execute': self._action_execute,
            'params.update': self._params_update,
            'task.stop': self._task_stop,
            'task.start': self._task_start_req,
            'ping': self._ping,
            'shutdown': self._shutdown_handler,
        }.get(method)
        if handler is None:
            raise RpcError(P.METHOD_NOT_FOUND, f'unknown method {method!r}')
        return await handler(params)

    async def _handle_notification(self, method: str, params: Any) -> None:
        params = params or {}
        if method == 'event.import_complete':
            await self._run_hook('on_import_complete', params.get('root_folder_id'))
        elif method == 'event.folder_delete':
            folders = [from_dict(Folder, f) for f in params.get('folders') or []]
            await self._run_hook('on_folder_delete', folders)
        elif method == 'task.start':
            self.plugin.tasks.on_start(params.get('task_id'))
        elif method == 'task.stop':
            self.plugin.tasks.on_stop(params.get('task_id'))
        else:
            log.debug(f'ignored notification {method}')

    async def _run_hook(self, name: str, *args) -> None:
        if not self._project_open:
            log.warning(f'{name} received before project.open, ignored')
            return
        try:
            await self.loop.run_in_executor(self.executor, functools.partial(getattr(self.plugin, name), *args))
        except Exception:
            log.exception(f'{name} failed')

    # -- handlers ----------------------------------------------------------------------------
    async def _project_open_handler(self, params: dict) -> dict:
        plugin = self.plugin
        if not self._project_open:
            project = params.get('project') or {}
            path = Path(project.get('path') or self.config.project_path or '')
            if not (path / 'data.db').exists():
                raise RpcError(P.INVALID_PARAMS, f'no project databases in {str(path)!r}')
            data_dir = Path(params.get('data_dir') or self.config.data_dir
                            or path / 'plugin_data' / plugin_slug(plugin.name))
            data_dir.mkdir(parents=True, exist_ok=True)
            plugin.data_path = data_dir
            plugin.project = ProjectData(plugin.name, path, data_dir=data_dir, bridge=self.bridge,
                                         direct_data_writes=plugin.direct_data_writes,
                                         project_id=project.get('id') or self.config.project_id)
            plugin._load_params(params.get('params'))

            def start():
                plugin.refresh_vector_types()
                plugin.on_start()
                plugin.on_project_open(project)

            try:
                await self.loop.run_in_executor(self.executor, start)
            except Exception as e:
                raise RpcError(P.INTERNAL_ERROR, f'on_start failed: {type(e).__name__}: {e}',
                               _error_data(e))
            self._project_open = True
            plugin._started = True
        return {'params': plugin.params_dict(), 'params_description': plugin.params_description()}

    async def _project_close_handler(self, params: dict) -> dict:
        await self.loop.run_in_executor(self.executor, self._close_project)
        return {}

    async def _action_execute(self, params: dict) -> dict:
        if not self._project_open:
            raise RpcError(P.NOT_READY, 'project is not open')
        action_id = params.get('action') or params.get('function')
        found = self.plugin.find_action(action_id or '')
        if found is None:
            raise RpcError(P.ACTION_NOT_FOUND, f'Action {action_id!r} not found')
        fn, desc = found
        raw = params.get('context') or {}
        ctx = ActionContext(instance_ids=raw.get('instance_ids'), group_name=raw.get('group_name'),
                            ui_inputs=raw.get('ui_inputs') or {}, user_id=raw.get('user_id'),
                            cancelled=threading.Event())
        try:
            kwargs = coerce_inputs(fn, desc['params'], ctx.ui_inputs)
        except InputError as e:
            raise RpcError(P.INVALID_INPUT, str(e))
        try:
            if inspect.iscoroutinefunction(fn):
                result = await fn(ctx, **kwargs)
            else:
                result = await self.loop.run_in_executor(self.executor, functools.partial(fn, ctx, **kwargs))
            return result_from_any(result)
        except asyncio.CancelledError:
            ctx.cancelled.set()
            raise
        except RpcError:
            raise
        except Exception as e:
            log.exception(f'action {action_id} failed')
            raise RpcError(P.ACTION_FAILED, f'{type(e).__name__}: {e}', _error_data(e))

    async def _params_update(self, params: dict) -> dict:
        update = params.get('params') or {}

        def apply():
            self.plugin._update_params(update)

        try:
            await self.loop.run_in_executor(self.executor, apply)
        except Exception as e:
            raise RpcError(P.PARAMS_INVALID, f'{type(e).__name__}: {e}', _error_data(e))
        return {'params': self.plugin.params_dict(), 'params_description': self.plugin.params_description()}

    async def _task_stop(self, params: dict) -> dict:
        return {'stopping': self.plugin.tasks.on_stop(params.get('task_id'))}

    async def _task_start_req(self, params: dict) -> dict:
        self.plugin.tasks.on_start(params.get('task_id'))
        return {}

    async def _ping(self, params: dict) -> dict:
        return {'time': time.time()}

    async def _shutdown_handler(self, params: dict) -> dict:
        self._shutdown.set()
        # stop tasks and run on_stop while task.done / log notifications can still be sent
        await self.loop.run_in_executor(self.executor, self._close_project)
        # respond first, then close: the reader loop ends when the backend closes the socket
        self.loop.call_later(0.05, lambda: asyncio.ensure_future(self.peer.close()))
        return {}


def _error_data(e: BaseException) -> dict:
    return {'type': type(e).__name__, 'message': str(e),
            'traceback': ''.join(traceback.format_exception(type(e), e, e.__traceback__))}


class RpcLogHandler(logging.Handler):
    """Forward log records to the backend as ``log`` notifications."""

    _guard = threading.local()

    def __init__(self, bridge: Bridge, level=logging.WARNING):
        super().__init__(level)
        self.bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith('panoptic_plugin.rpc') or getattr(self._guard, 'busy', False):
            return
        if self.bridge._rt.peer is None:
            return
        self._guard.busy = True
        try:
            params = {'level': record.levelname, 'message': record.getMessage(), 'logger': record.name,
                      'time': record.created}
            if record.exc_info:
                params['exc'] = ''.join(traceback.format_exception(*record.exc_info))
            self.bridge.notify('log', params)
        except Exception:
            pass
        finally:
            self._guard.busy = False


def watch_parent(pid: int, on_gone) -> None:
    """Exit when the backend process disappears (POSIX), so plugins never outlive it."""
    if os.name != 'posix' or pid <= 0:
        return

    def loop():
        while True:
            time.sleep(2)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                on_gone()
                return
            except PermissionError:
                pass

    threading.Thread(target=loop, daemon=True, name='parent-watch').start()


def _stderr(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)
