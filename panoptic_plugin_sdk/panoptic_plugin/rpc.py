"""Bidirectional JSON-RPC 2.0 over one WebSocket (text frames, one JSON value per frame).

Both peers send requests and notifications. A frame may hold a batch (JSON array). Incoming
requests are dispatched concurrently (one asyncio task each) so a long handler never blocks the
reader; responses go out through a single writer task, which keeps send order.
"""
from __future__ import annotations

import asyncio
import itertools
import json
import logging
from typing import Any, Awaitable, Callable

from . import protocol as P
from .models import to_jsonable

log = logging.getLogger('panoptic_plugin.rpc')

Handler = Callable[[str, Any, Any], Awaitable[Any]]   # (method, params, request_id) -> result


class RpcError(Exception):
    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.data = data

    def to_json(self) -> dict:
        err = {'code': self.code, 'message': self.message}
        if self.data is not None:
            err['data'] = to_jsonable(self.data)
        return err


class ConnectionLost(RpcError):
    def __init__(self, message: str = 'connection lost'):
        super().__init__(P.CONNECTION_LOST, message)


def dumps(msg: Any) -> str:
    return json.dumps(to_jsonable(msg), allow_nan=False, separators=(',', ':'))


class RpcPeer:
    def __init__(self, ws, handler: Handler, notification_handler: Callable[[str, Any], Awaitable[None]]):
        self.ws = ws
        self._handler = handler
        self._on_notification = notification_handler
        self._ids = itertools.count(1)
        self._pending: dict[Any, asyncio.Future] = {}
        self._incoming: dict[Any, asyncio.Task] = {}
        self._out: asyncio.Queue = asyncio.Queue()
        self._closed = asyncio.Event()
        self._writer_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # outgoing
    # ------------------------------------------------------------------

    async def request(self, method: str, params: Any = None, timeout: float | None = None) -> Any:
        if self._closed.is_set():
            raise ConnectionLost()
        req_id = next(self._ids)
        fut = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut
        msg = {'jsonrpc': '2.0', 'id': req_id, 'method': method}
        if params is not None:
            msg['params'] = params
        await self._send(msg)
        try:
            return await asyncio.wait_for(fut, timeout) if timeout else await fut
        except asyncio.TimeoutError:
            raise RpcError(P.TIMEOUT, f'{method} timed out after {timeout}s')
        finally:
            self._pending.pop(req_id, None)

    async def notify(self, method: str, params: Any = None) -> None:
        if self._closed.is_set():
            return
        msg = {'jsonrpc': '2.0', 'method': method}
        if params is not None:
            msg['params'] = params
        await self._send(msg)

    async def _send(self, msg: Any) -> None:
        # Serialize here so encoding errors surface at the caller, not in the writer task.
        await self._out.put(dumps(msg))

    async def _writer(self) -> None:
        while True:
            text = await self._out.get()
            if text is None:
                return
            try:
                await self.ws.send(text)
            except Exception as e:
                log.debug(f'send failed: {e!r}')
                self._closed.set()
                return

    # ------------------------------------------------------------------
    # incoming
    # ------------------------------------------------------------------

    async def serve(self) -> None:
        """Read until the socket closes. Fails pending requests with ConnectionLost."""
        self._writer_task = asyncio.create_task(self._writer())
        try:
            async for raw in self.ws:
                if isinstance(raw, bytes):
                    await self._send(self._error_response(None, P.INVALID_REQUEST, 'binary frames are not supported'))
                    continue
                try:
                    msg = json.loads(raw)
                except ValueError:
                    await self._send(self._error_response(None, P.PARSE_ERROR, 'parse error'))
                    continue
                if isinstance(msg, list):
                    if not msg:
                        await self._send(self._error_response(None, P.INVALID_REQUEST, 'empty batch'))
                        continue
                    asyncio.create_task(self._handle_batch(msg))
                else:
                    await self._dispatch(msg)
        except Exception as e:  # ConnectionClosed and friends
            log.debug(f'reader stopped: {e!r}')
        finally:
            self._closed.set()
            for fut in list(self._pending.values()):
                if not fut.done():
                    fut.set_exception(ConnectionLost())
            for task in list(self._incoming.values()):
                task.cancel()
            await self._out.put(None)

    async def _dispatch(self, msg: Any, batch: list | None = None) -> None:
        if not isinstance(msg, dict) or msg.get('jsonrpc') != '2.0':
            resp = self._error_response(msg.get('id') if isinstance(msg, dict) else None,
                                        P.INVALID_REQUEST, 'invalid request')
            await self._reply(resp, batch)
            return
        if 'method' in msg:
            method, params, req_id = msg['method'], msg.get('params'), msg.get('id')
            if 'id' not in msg:
                if method == '$/cancel':
                    self._cancel_incoming((params or {}).get('id'))
                    return
                asyncio.create_task(self._run_notification(method, params))
                return
            task = asyncio.create_task(self._run_request(method, params, req_id, batch))
            self._incoming[req_id] = task
            task.add_done_callback(lambda _t, rid=req_id: self._incoming.pop(rid, None))
            return
        # a response to one of our requests
        fut = self._pending.get(msg.get('id'))
        if fut is None or fut.done():
            log.debug(f'unexpected response id {msg.get("id")!r}')
            return
        if 'error' in msg and msg['error'] is not None:
            e = msg['error']
            fut.set_exception(RpcError(e.get('code', P.INTERNAL_ERROR), e.get('message', ''), e.get('data')))
        else:
            fut.set_result(msg.get('result'))

    async def _handle_batch(self, msgs: list) -> None:
        responses: list = []
        tasks = []
        for msg in msgs:
            await self._dispatch(msg, batch=responses)
            if isinstance(msg, dict) and 'method' in msg and 'id' in msg:
                t = self._incoming.get(msg['id'])
                if t is not None:
                    tasks.append(t)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if responses:
            await self._send(responses)

    async def _reply(self, resp: dict, batch: list | None) -> None:
        if batch is not None:
            batch.append(resp)
        else:
            await self._send(resp)

    async def _run_request(self, method: str, params: Any, req_id: Any, batch: list | None) -> None:
        try:
            result = await self._handler(method, params, req_id)
            resp = {'jsonrpc': '2.0', 'id': req_id, 'result': to_jsonable(result)}
        except asyncio.CancelledError:
            resp = self._error_response(req_id, P.CANCELLED, 'request cancelled')
        except RpcError as e:
            resp = {'jsonrpc': '2.0', 'id': req_id, 'error': e.to_json()}
        except Exception as e:
            log.exception(f'handler for {method} failed')
            resp = self._error_response(req_id, P.INTERNAL_ERROR, f'{type(e).__name__}: {e}')
        try:
            dumps(resp)
        except (TypeError, ValueError) as e:
            resp = self._error_response(req_id, P.INTERNAL_ERROR, f'result is not JSON serializable: {e}')
        if not self._closed.is_set():
            await self._reply(resp, batch)

    async def _run_notification(self, method: str, params: Any) -> None:
        try:
            await self._on_notification(method, params)
        except Exception:
            log.exception(f'notification handler for {method} failed')

    def _cancel_incoming(self, req_id: Any) -> None:
        task = self._incoming.get(req_id)
        if task is not None:
            task.cancel()

    @staticmethod
    def _error_response(req_id: Any, code: int, message: str, data: Any = None) -> dict:
        err: dict = {'code': code, 'message': message}
        if data is not None:
            err['data'] = data
        return {'jsonrpc': '2.0', 'id': req_id, 'error': err}

    @property
    def closed(self) -> bool:
        return self._closed.is_set()

    async def close(self) -> None:
        """Flush what is queued, then close the socket."""
        await self._out.put(None)
        if self._writer_task is not None and not self._writer_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(self._writer_task), 5)
            except Exception:
                pass
        self._closed.set()
        try:
            await self.ws.close()
        except Exception:
            pass
