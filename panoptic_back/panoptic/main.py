import argparse
import os
import pathlib
import sys
from threading import Thread

import requests
import uvicorn

from PyQt5.QtWidgets import QApplication

from panoptic.ui import MiniUI


class ApiClient:
    def __init__(self, port, server, host, folder):
        self.port = port
        self.server = server
        self.host = host
        self.folder = folder
        self.front_url = 'http://localhost:5173/' if os.getenv("PANOPTIC_ENV", "PROD") == "DEV" else self.api("")

    def api(self, path):
        return 'http://localhost:' + str(self.port) + '/' + path

    def launch_uvicorn(self, ui=None):
        from panoptic.api import app
        app.add_event_handler('startup',
                              lambda: on_fastapi_start(ui) if not self.server else lambda: on_fastapi_start_server(
                                  self))
        if not self.server:
            app.add_event_handler('shutdown', lambda: ui.server_status.setText('stopped'))
        if self.host:
            uvicorn.run(app, host="0.0.0.0", port=self.port)
        else:
            uvicorn.run(app, port=self.port)


def on_fastapi_start(ui):
    t1 = Thread(target=ui.init_folders)
    t1.start()


def on_fastapi_start_server(client):
    t1 = Thread(target=lambda: init_folders_server(client))
    t1.start()


def init_folders_server(client):
    os.environ['PANOPTIC_DATA'] = os.getenv('PANOPTIC_DATA', (pathlib.Path.home() / 'panoptic').as_posix())
    path = os.path.join(os.environ['PANOPTIC_DATA'], 'mini')
    if not os.path.exists(path):
        os.makedirs(path)
    requests.post(client.api('folders'), headers={"Content-type": "application/json"}, json={"path": client.folder}).json()


def start():
    parser = argparse.ArgumentParser(
        description="Start Panoptic, use --host to share your panoptic across local network")
    parser.add_argument('--host', action="store_true")
    parser.add_argument('--server', action="store_true")
    parser.add_argument('--folder', type=str)
    parser.add_argument('--port', type=int, default=8000)

    args = parser.parse_args()

    host = args.host
    server = args.server
    folder = args.folder
    port = args.port

    client = ApiClient(port, server, host, folder)

    if not server:
        app = QApplication(sys.argv)
        ui = MiniUI(client)
        ui.show()
        ui.init_projects()
        QApplication.processEvents()
        sys.exit(app.exec_())
    else:
        if not folder:
            print("folder parameter need to be fullfilled in server mode")
            sys.exit(0)
        client.launch_uvicorn()


if __name__ == '__main__':
    start()
