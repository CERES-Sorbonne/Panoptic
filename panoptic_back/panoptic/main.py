import os
import tempfile
import traceback
import webbrowser
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles
import socketio

from panoptic.core.panoptic import Panoptic
from panoptic.core.panoptic_server import PanopticServer
from panoptic.routes.panoptic_routes import selection_router, set_server
from panoptic.routes.project_routes import project_router
from panoptic.models import PluginType
from panoptic.routes.panoptic_routes import selection_router
from panoptic.routes.project_routes import project_router
from panoptic.utils import get_base_path


def start_api(install=False):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await panoptic._close()

    panoptic = Panoptic()
    panoptic.start()

    if install:
        panoptic.add_plugin(
            name='PanopticVision',
            source='panopticml',
            ptype=PluginType.pip
        )

    HOST = os.getenv("PANOPTIC_HOST", None)
    # default port for Panoptic backend is 8000
    PORT = int(os.getenv("PANOPTIC_PORT", 8000))

    # FastAPI setup
    app = FastAPI(lifespan=lifespan)

    server = PanopticServer(panoptic)
    sio_app = socketio.ASGIApp(server.sio)
    app.mount("/socket.io", sio_app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    BASE_PATH = get_base_path()
    # base path for the static folder

    app.include_router(selection_router)
    app.include_router(project_router)

    @app.exception_handler(Exception)
    async def unicorn_exception_handler(request: Request, exc: BaseException):
        headers = {
            "Access-Control-Allow-Origin": "*",  # match your CORS settings
            "Access-Control-Allow-Credentials": "false",
        }

        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        name = str(type(exc).__name__)
        message = str(exc)

        return JSONResponse(
            status_code=500,
            headers=headers,
            content={"traceback": tb, "name": name, "message": message}
        )

    set_server(server)

    app.mount("/", StaticFiles(directory=os.path.join(BASE_PATH, "html"), html=True), name="static")

    dev_url = 'http://localhost:5173/'
    prod_url = 'http://localhost:' + str(PORT) + '/'
    front_url = dev_url if os.getenv("PANOPTIC_ENV", "PROD") == "DEV" else prod_url

    if not os.environ.get('REMOTE'):
        webbrowser.open(front_url)
    if os.environ.get('SERVER_MODE'):
        server.ask_users = True


    uvicorn.run(app, host=HOST, port=PORT)

def start(test=False, install=False):
    if test:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ['PANOPTIC_DATA_DIR'] = tmpdir
            start_api(install)
    else:
        start_api()

if __name__ == '__main__':
    # start(sys.argv[1]=="test")
    start()

