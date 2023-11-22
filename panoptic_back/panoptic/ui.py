import json
import os
import sys
from threading import Thread

import requests
import socket
import webbrowser
from time import sleep

import qtawesome as qta
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import QSize, pyqtSignal
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, \
    QPushButton, QLineEdit, QFileDialog, QListWidget, QDesktopWidget

import panoptic
from panoptic.utils import get_datadir


class IconLabel(QWidget):

    def __init__(self, qta_id, text, screen_width, color="blue", final_stretch=True):
        super(QWidget, self).__init__()

        self.IconSize = QSize(16, 16) if screen_width <= 700 else QSize(32, 32)
        self.HorizontalSpacing = 2

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.icon = QLabel()
        self.icon.setPixmap(qta.icon(qta_id, color=color).pixmap(self.IconSize))

        layout.addWidget(self.icon)
        layout.addSpacing(self.HorizontalSpacing)
        layout.addWidget(QLabel(text))

        if final_stretch:
            layout.addStretch()

    def setAlignment(self, pos):
        self.icon.setAlignment(pos)


class MiniUI(QMainWindow):

    def __init__(self, client):
        super().__init__()
        self.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__), "html/favicon.ico")))
        self.width = self._init_size()
        self.thread = None
        self.selected_project = None
        self.projects = None
        self.client = client
        self.project_path = (get_datadir() / "panoptic" / "projects.json").as_posix()
        self.version = panoptic.__version__

        # define all windows
        self.setObjectName("Main")
        self.setStyleSheet("""
        #Main{
            background: white;
        }
        QLabel{
            font-size: 12pt;
        }
        QWidget{
            font-size: 11pt;
        }
        QPushButton{
            padding: 5px;
            border: 3px solid lightgrey;
            border-radius: 3px;
        }
        QComboBox{
            padding: 5px;
            border: 1px solid lightgrey
        }
        QComboBox::drop-down{
            border: 0px
        }
        QComboBox::down-arrow {
            image: url(panoptic/assets/arrow.png);
            width: 11px;
            height: 11px;
            margin-right: 5px;
        }
        """)


        self.setWindowTitle("Panoptic Server - " + self.version)
        self.setGeometry(100, 100, self.width, self.width // 2)
        self._center()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Partie A
        frame_a = QWidget()
        frame_a.setObjectName("A")
        frame_a.setStyleSheet("""#A{
            border-bottom: 1px solid lightgrey;
        }""")
        layout.addWidget(frame_a)
        frame_a_layout = QHBoxLayout(frame_a)

        # Partie A.1
        frame_a1 = QWidget()
        frame_a_layout.addWidget(frame_a1)
        frame_a1_layout = QVBoxLayout(frame_a1)
        frame_a1_layout.setAlignment(QtCore.Qt.AlignTop)
        label = IconLabel("fa5.folder", "Choisir Projet existant", self.width)
        label.setAlignment(QtCore.Qt.AlignCenter)
        frame_a1_layout.addWidget(label)
        self.combo_box = QComboBox()
        frame_a1_layout.addWidget(self.combo_box)

        self.new_project_button = QPushButton("Nouveau projet")
        self.new_project_button.clicked.connect(self.create_project)
        self.new_project_button.setCursor(QCursor(QtCore.Qt.PointingHandCursor))
        frame_a1_layout.addWidget(self.new_project_button)
        frame_a1.setFixedWidth(self.width // 3)


        # Partie A.2
        frame_a2 = QWidget()
        frame_a_layout.addWidget(frame_a2)
        frame_a2_layout = QVBoxLayout(frame_a2)

        label2 = IconLabel("fa5.image", "Dossiers d'images du projet courant", self.width)
        label2.setAlignment(QtCore.Qt.AlignCenter)
        frame_a2_layout.addWidget(label2)

        self.listbox = QListWidget()
        frame_a2_layout.addWidget(self.listbox)

        self.button = QPushButton("Ajouter un dossier d'images")
        self.button.clicked.connect(self.add_folder)
        self.button.setCursor(QCursor(QtCore.Qt.PointingHandCursor))
        frame_a2_layout.addWidget(self.button)

        # Partie B
        frame_b = QWidget()
        layout.addWidget(frame_b)
        frame_b_layout = QVBoxLayout(frame_b)
        frame_b_layout.setAlignment(QtCore.Qt.AlignCenter)

        self.server_status = QLineEdit("Initialisation")
        self.server_status.setReadOnly(True)
        self.server_status.setAlignment(QtCore.Qt.AlignCenter)
        self.server_status.setFixedWidth(200)
        frame_b_layout.addWidget(self.server_status)

        self.open_button = QPushButton("Ouvrir Panoptic")
        self.open_button.setFixedWidth(200)
        self.open_button.clicked.connect(self.open_panoptic)
        self.open_button.setCursor(QCursor(QtCore.Qt.PointingHandCursor))

        frame_b_layout.addWidget(self.open_button)

    def _init_size(self):
        width = QDesktopWidget().availableGeometry().width()
        return max(700, width // 3)

    def on_success_handler(self, folders):
        for folder in folders:
            if folder['parent'] is None:
                self.listbox.addItem(folder['path'])
        failed = False
        self.set_processing(False, self._get_running_message())


    def set_processing(self, value: bool, message: str = None):
        if value:
            self.server_status.setStyleSheet("""
                QWidget {
                    background-color: "orange";
                    padding: 5px;
                    border-radius: 10px;
                }
            """)
            # since this is making panoptic crash on linux maybe make our own custom setEnabled false crossplatform
            if not sys.platform.startswith("linux"):
                self.setEnabled(False)
        else:
            self.server_status.setStyleSheet("""
                QWidget {
                    background-color: "green";
                    padding: 5px;
                    border-radius: 10px;
                    color: white;
                }
            """)
            if not sys.platform.startswith("linux"):
                self.setEnabled(True)
        if message:
            self.server_status.setText(message)
        QApplication.processEvents()

    def _center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def init_projects(self):
        # TODO: si tout marche bien sortir tout le code suivant dans une fonction à part
        # Vérifier et créer les répertoires parents si nécessaire
        os.makedirs(os.path.dirname(self.project_path), exist_ok=True)

        # Vérifier si le fichier JSON existe
        if os.path.exists(self.project_path):
            # Lire le fichier JSON
            with open(self.project_path) as json_file:
                self.projects = json.load(json_file)
        else:
            self.projects = {'projects': [], 'last_opened': None}
            # Créer un fichier JSON avec une liste vide
            with open(self.project_path, 'w') as json_file:
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

        self.load_project()

    def load_project(self):
        self.set_processing(True, "Chargement des données")

        # if when trying to load project there are already no projects then just start uvicorn
        if len(self.projects['projects']) == 0 and not self.thread:
            self.start_uvicorn()
        # else load the selected project
        else:
            self.selected_project = self.projects['projects'][self.combo_box.currentIndex()]
            os.environ['PANOPTIC_DATA'] = self.selected_project['path']
            path = os.path.join(os.environ['PANOPTIC_DATA'], 'mini')
            if not os.path.exists(path):
                os.makedirs(path)

            # if we have already a project but uvicorn is not running start it
            if not self.thread:
                self.start_uvicorn()
            else:
                requests.post(self.client.api("project"), json={"project": os.environ["PANOPTIC_DATA"]})
                self.init_folders()

    def _get_running_message(self):
        message = 'Running !'
        if self.client.host:
            try:
                ip = socket.gethostbyname(socket.gethostname())
                message += f' on {ip}:{self.client.port}'
            except:
                pass
        return message

    def init_folders(self):
        self.listbox.clear()
        failed = True
        while failed:
            try:
                res = requests.get(self.client.api('folders')).json()
                self.on_success_handler(res)
                failed = False
            except Exception:
                pass
            sleep(0.5)

    def add_folder(self):
        folder_path = self._get_file_dialog("Choisir un dossier d'images")
        res = requests.post(self.client.api('folders'), headers={"Content-type": "application/json"},
                            json={"path": folder_path}).json()
        self.listbox.clear()
        for folder in res:
            if folder['parent'] is None:
                self.listbox.addItem(folder['path'])

    def _get_file_dialog(self, message):
        # this function is a fix when running with pycharm on linux
        if os.getenv("PANOPTIC_ENV", "PROD") == "DEV":
            res = QFileDialog.getExistingDirectory(self, message, options=QFileDialog.DontUseNativeDialog)
        else:
            res = QFileDialog.getExistingDirectory(self, message)
        return res

    def open_panoptic(self):
        webbrowser.open(self.client.front_url)
        self.projects['last_opened'] = self.selected_project
        with open(self.project_path, 'w') as json_file:
            json.dump(self.projects, json_file)

    def create_project(self):
        folder_path = self._get_file_dialog('Dossier où stocker les données panoptic')
        project_name = os.path.basename(folder_path)
        if folder_path == "":
            return
        new_project = {'name': project_name, 'path': folder_path}
        self.projects['projects'].append(new_project)
        with open(self.project_path, 'w') as json_file:
            json.dump(self.projects, json_file)
        self.combo_box.addItem(project_name)
        self.combo_box.setCurrentIndex(self.combo_box.count() - 1)
        self.load_project()

    def start_uvicorn(self):
        self.thread = Thread(target=self.client.launch_uvicorn(self))
        self.thread.daemon = True
        self.thread.start()