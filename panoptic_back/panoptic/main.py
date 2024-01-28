import os
import sys
import webbrowser

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from panoptic.core.panoptic import panoptic
from panoptic.routes.project_routes2 import project_router
from panoptic.routes.project_selection_routes import selection_router
from panoptic.utils import get_base_path

if __name__ == '__main__':

    panoptic.load_data()

    # default port for Panoptic backend
    PORT = 8000

    # FastAPI setup
    app = FastAPI()
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

    # static directory route
    app.mount("/", StaticFiles(directory=os.path.join(BASE_PATH, "html"), html=True), name="static")


    def api(path):
        return 'http://localhost:' + str(PORT) + '/' + path

    dev_url = 'http://localhost:5173/'
    prod_url = 'http://localhost:' + str(PORT) + '/'
    FRONT_URL = dev_url if os.getenv("PANOPTIC_ENV", "PROD") == "DEV" else prod_url

    if not os.environ.get('REMOTE'):
        webbrowser.open(FRONT_URL)

    uvicorn.run(app, port=PORT)
