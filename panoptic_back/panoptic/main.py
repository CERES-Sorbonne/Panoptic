import os
import sys

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from panoptic.scripts.project_routes import project_router
from panoptic.scripts.project_selection_routes import selection_router

if __name__ == '__main__':

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

    # base path for the static folder
    if getattr(sys, 'frozen', False):
        # Le programme est exécuté en mode fichier unique
        BASE_PATH = sys._MEIPASS
    else:
        # Le programme est exécuté en mode script
        BASE_PATH = os.path.dirname(__file__)

    app.include_router(selection_router)
    app.include_router(project_router)

    # static directory route
    app.mount("/", StaticFiles(directory=os.path.join(BASE_PATH, "html"), html=True), name="static")

    uvicorn.run(app, port=PORT)
