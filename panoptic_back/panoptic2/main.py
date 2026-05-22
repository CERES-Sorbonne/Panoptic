"""panoptic2 entry point — FastAPI + Socket.IO backed by Panoptic2."""
from __future__ import annotations

import os
import traceback
from contextlib import asynccontextmanager

import socketio
import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from panoptic2.core.panoptic.panoptic import Panoptic2
from panoptic2.core.server.panoptic_server import PanopticServer2
from panoptic2.routes.deps import set_dependencies
from panoptic2.routes.panoptic_routes import panoptic_router
from panoptic2.routes.project_routes import project_router


def start():
    db_path = os.getenv('PANOPTIC_DB', os.path.expanduser('~/.panoptic2/panoptic.db'))
    PORT    = int(os.getenv('PANOPTIC_PORT', 8000))
    HOST    = os.getenv('PANOPTIC_HOST', None)

    panoptic = Panoptic2(db_path)
    panoptic.start()

    sio    = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
    server = PanopticServer2(panoptic, sio)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        server.on_startup()
        yield
        await server.shutdown()
        panoptic.close()

    app = FastAPI(lifespan=lifespan, title='Panoptic2')

    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=False,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    if os.environ.get('PANOPTIC_REMOTE'):
        from starlette.middleware.gzip import GZipMiddleware
        app.add_middleware(GZipMiddleware, minimum_size=1_000_000, compresslevel=4)

    app.mount('/socket.io', socketio.ASGIApp(sio))

    set_dependencies(panoptic, server)
    app.include_router(panoptic_router)
    app.include_router(project_router)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            headers={'Access-Control-Allow-Origin': '*'},
            content={'name': 'HTTPException', 'message': str(exc.detail)},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            headers={'Access-Control-Allow-Origin': '*'},
            content={'name': 'ValidationError', 'message': str(exc)},
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: BaseException):
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        return JSONResponse(
            status_code=500,
            headers={'Access-Control-Allow-Origin': '*'},
            content={'traceback': tb, 'name': type(exc).__name__, 'message': str(exc)},
        )

    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == '__main__':
    start()
