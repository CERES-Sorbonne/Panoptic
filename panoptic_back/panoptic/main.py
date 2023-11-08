import json
import os
import pathlib
import sys
import tkinter as tk
import webbrowser
import socket
import argparse
from threading import Thread
from time import sleep

import uvicorn
import requests

from panoptic.utils import get_datadir

PORT = 8000
HOST = False
THREAD = None


def api(path):
    return 'http://localhost:' + str(PORT) + '/' + path


FRONT_URL = 'http://localhost:5173/' if os.getenv("PANOPTIC_ENV", "PROD") == "DEV" else api("")
PROJECT_PATH = get_datadir() / "panoptic" / "projects.json"
PROJECT_PATH = PROJECT_PATH.as_posix()

from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, \
    QPushButton, QListView, QLineEdit, QFileDialog, QListWidget
from PyQt5 import QtCore


class MiniUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_project = None
        self.projects = None

        self.setWindowTitle("Panoptic Server")
        self.setGeometry(100, 100, 700, 350)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)

        # Partie A
        frame_a = QWidget()
        layout.addWidget(frame_a)
        frame_a_layout = QVBoxLayout(frame_a)

        # Partie A.1
        frame_a1 = QWidget()
        frame_a_layout.addWidget(frame_a1)
        frame_a1_layout = QVBoxLayout(frame_a1)

        label = QLabel("Choisir Projet existant")
        frame_a1_layout.addWidget(label)

        self.combo_box = QComboBox()
        frame_a1_layout.addWidget(self.combo_box)

        self.new_project_button = QPushButton("Nouveau projet")
        self.new_project_button.clicked.connect(self.create_project)
        frame_a1_layout.addWidget(self.new_project_button)

        # Espacement entre A.1 et A.2
        spacer = QLabel()
        spacer.setFixedSize(2, 20)
        frame_a_layout.addWidget(spacer)

        # Partie A.2
        frame_a2 = QWidget()
        frame_a_layout.addWidget(frame_a2)
        frame_a2_layout = QVBoxLayout(frame_a2)

        label2 = QLabel("Dossiers d'images du projet courant")
        frame_a2_layout.addWidget(label2)

        self.listbox = QListWidget()
        frame_a2_layout.addWidget(self.listbox)

        self.button = QPushButton("Ajouter un dossier d'images")
        self.button.clicked.connect(self.add_folder)
        frame_a2_layout.addWidget(self.button)

        # Barre de séparation entre A et B
        separator2 = QLabel()
        separator2.setFixedSize(2, 20)
        layout.addWidget(separator2)

        # Partie B
        frame_b = QWidget()
        layout.addWidget(frame_b)
        frame_b_layout = QVBoxLayout(frame_b)

        self.server_status = QLineEdit("Démarrage...")
        self.server_status.setStyleSheet("""
            QWidget {
                background-color: "orange";
                padding: 5px;
                border-radius: 10px;
            }
        """)
        self.server_status.setReadOnly(True)
        self.server_status.setAlignment(QtCore.Qt.AlignCenter)
        frame_b_layout.addWidget(self.server_status)

        self.open_button = QPushButton("Ouvrir Panoptic")
        self.open_button.setFixedWidth(200)
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_panoptic)
        frame_b_layout.addWidget(self.open_button)

        self.setEnabled(False)

    def init_projects(self):
        # TODO: si tout marche bien sortir tout le code suivant dans une fonction à part
        # Vérifier et créer les répertoires parents si nécessaire
        os.makedirs(os.path.dirname(PROJECT_PATH), exist_ok=True)

        # Vérifier si le fichier JSON existe
        if os.path.exists(PROJECT_PATH):
            # Lire le fichier JSON
            with open(PROJECT_PATH) as json_file:
                self.projects = json.load(json_file)
        else:
            self.projects = {'projects': [], 'last_opened': None}
            # Créer un fichier JSON avec une liste vide
            with open(PROJECT_PATH, 'w') as json_file:
                json.dump(self.projects, json_file)


        # Récupérer les noms des projets dans une liste
        project_names = [project['name'] for project in self.projects['projects']]

        if project_names:
            # Mettre à jour la liste déroulante
            self.combo_box.addItems(project_names)
            # Sélectionner le premier projet par défaut s'il existe
            self.combo_box.setCurrentIndex(0)
            self.selected_project = self.projects['projects'][0]

        if self.projects['last_opened'] is not None:
            index = project_names.index(self.projects['last_opened']['name'])
            self.combo_box.setCurrentIndex(index)
            self.selected_project = self.projects['projects'][index]

        self.combo_box.currentIndexChanged.connect(self.load_project)

        if self.selected_project:
            self.load_project()

    def init_folders(self):
        self.listbox.clear()
        failed = True
        while failed:
            try:
                res = requests.get(api('folders')).json()
                for folder in res:
                    if folder['parent'] is None:
                        self.listbox.addItem(folder['path'])
                failed = False
                message = 'Running !'
                if HOST:
                    try:
                        ip = socket.gethostbyname(socket.gethostname())
                        message += f' on {ip}:{PORT}'
                    except:
                        pass
                self.server_status.setText(message)
                self.server_status.setStyleSheet("""
                    QWidget {
                        background-color: "green";
                        padding: 5px;
                        border-radius: 10px;
                        color: white;
                    }
                """)
                self.setEnabled(True)

            except Exception:
                pass
            sleep(0.5)

    def add_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Choisir un dossier d'images")
        print(folder_path)
        res = requests.post(api('folders'), headers={"Content-type": "application/json"},
                            json={"path": folder_path}).json()
        self.listbox.clear()
        for folder in res:
            if folder['parent'] is None:
                self.listbox.addItem(folder['path'])

    def open_panoptic(self):
        webbrowser.open(FRONT_URL)
        self.projects['last_opened'] = self.selected_project
        with open(PROJECT_PATH, 'w') as json_file:
            json.dump(self.projects, json_file)

    def create_project(self):
        folder_path = QFileDialog.getExistingDirectory(self, 'Dossier où stocker les données panoptic')
        project_name = os.path.basename(folder_path)
        new_project = {'name': project_name, 'path': folder_path}
        self.projects['projects'].append(new_project)
        with open(PROJECT_PATH, 'w') as json_file:
            json.dump(self.projects, json_file)
        self.combo_box.addItem(project_name)
        self.combo_box.setCurrentIndex(self.combo_box.count() - 1)
        self.load_project()

    def load_project(self, event=None):
        if len(self.projects['projects']) == 0:
            return
        self.selected_project = self.projects['projects'][self.combo_box.currentIndex()]
        os.environ['PANOPTIC_DATA'] = self.selected_project['path']
        path = os.path.join(os.environ['PANOPTIC_DATA'], 'mini')
        if not os.path.exists(path):
            os.makedirs(path)
        if not THREAD:
            start_thread()
        else:
            requests.post(api("project"), json={"project": os.environ["PANOPTIC_DATA"]})
            self.init_folders()


def on_fastapi_start():
    ui.server_status.setText('Initialisation...')
    t1 = Thread(target=ui.init_folders)
    t1.start()


def init_folders_server():
    os.environ['PANOPTIC_DATA'] = os.getenv('PANOPTIC_DATA', (pathlib.Path.home() / 'panoptic').as_posix())
    path = os.path.join(os.environ['PANOPTIC_DATA'], 'mini')
    if not os.path.exists(path):
        os.makedirs(path)
    # requests.post(api("project"), json={"project": projects['projects'][0]['path']})
    requests.post(api('folders'), headers={"Content-type": "application/json"}, json={"path": FOLDER}).json()


def on_fastapi_start_server():
    t1 = Thread(target=init_folders_server)
    t1.start()


def launch_uvicorn():
    from panoptic.api import app
    app.add_event_handler('startup', on_fastapi_start if not SERVER else on_fastapi_start_server)
    if not SERVER:
        app.add_event_handler('shutdown', lambda: ui.server_status.set('stopped'))
    if HOST:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        uvicorn.run(app, port=PORT)


def start_thread():
    global THREAD
    THREAD = Thread(target=launch_uvicorn)
    THREAD.daemon = True
    THREAD.start()


def start():
    parser = argparse.ArgumentParser(
        description="Start Panoptic, use --host to share your panoptic across local network")
    parser.add_argument('--host', action="store_true")
    parser.add_argument('--server', action="store_true")
    parser.add_argument('--folder', type=str)

    args = parser.parse_args()
    global HOST
    global SERVER
    global FOLDER
    HOST = args.host
    SERVER = args.server
    FOLDER = args.folder

    if not SERVER:
        app = QApplication(sys.argv)

        global ui
        ui = MiniUI()
        ui.show()
        ui.init_projects()
        sys.exit(app.exec_())
    else:
        if not FOLDER:
            print("folder parameter need to be fullfilled in server mode")
            sys.exit(0)
        launch_uvicorn()


if __name__ == '__main__':
    start()
