import os
import webbrowser
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from panoptic.core.panoptic import Panoptic
from panoptic.routes.project_routes import project_router
from panoptic.routes.panoptic_routes import selection_router, set_panoptic
from panoptic.utils import get_base_path


def start():

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await panoptic.close()


    panoptic = Panoptic()
    panoptic.load_data()

    HOST = os.getenv("PANOPTIC_HOST", None)
    # default port for Panoptic backend
    PORT = os.getenv("PANOPTIC_PORT", 8000)

    # FastAPI setup
    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    BASE_PATH = get_base_path()
    # base path for the static folder

    app.include_router(selection_router)
    app.include_router(project_router)

    set_panoptic(panoptic)

    # static directory route
    app.mount("/", StaticFiles(directory=os.path.join(BASE_PATH, "html"), html=True), name="static")

    dev_url = 'http://localhost:5173/'
    prod_url = 'http://localhost:' + str(PORT) + '/'
    front_url = dev_url if os.getenv("PANOPTIC_ENV", "PROD") == "DEV" else prod_url

    if not os.environ.get('REMOTE'):
        webbrowser.open(front_url)

    # @app.on_event("shutdown")
    # async def shutdown_event():
    #     await panoptic.close()


    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == '__main__':
    start()
