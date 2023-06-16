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
from tkinter import filedialog, ttk
from tkinter.filedialog import askdirectory

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

class MiniUI:
    def __init__(self, master):
        self.master = master
        self.selected_project = None
        self.projects = None

        master.title("Panoptic Server")

        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        x = (screen_width // 2) - (700 // 2)
        y = (screen_height // 2) - (350 // 2)

        master.geometry(f"700x350+{x}+{y}")

        # Frame pour la partie A
        frame_a = ttk.Frame(master)
        frame_a.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Frame pour la partie A.1
        frame_a1 = ttk.Frame(frame_a)
        frame_a1.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))

        # Label, combobox et bouton dans la partie A.1
        self.label = tk.Label(frame_a1, text="Choisir Projet existant")
        self.label.pack(pady=10)

        self.combo_box = ttk.Combobox(frame_a1)
        self.combo_box.pack(pady=10, padx=5)

        self.new_project_button = tk.Button(frame_a1, text="Nouveau projet",  command=self.create_project)
        self.new_project_button.pack(pady=10)

        # Espacement entre A.1 et A.2
        spacer = tk.Label(frame_a, width=2)
        spacer.pack(side=tk.LEFT)

        # Barre de séparation entre A.1 et A.2
        separator = ttk.Frame(frame_a, width=2, relief=tk.SUNKEN)
        separator.pack(side=tk.LEFT, fill=tk.Y)

        # Frame pour la partie A.2
        frame_a2 = ttk.Frame(frame_a)
        frame_a2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Label et listbox dans la partie A.2
        self.label2 = tk.Label(frame_a2, text="Dossiers")
        self.label2.pack(pady=10)

        self.listbox = tk.Listbox(frame_a2)
        self.listbox.pack(fill=tk.BOTH, expand=True)

        # Button en bas de la partie A.2
        self.button = tk.Button(frame_a2, text="Ajouter Dossier", command=self.add_folder)
        self.button.pack(side=tk.BOTTOM, pady=10)

        # Barre de séparation entre A et B
        separator2 = ttk.Frame(master, height=2, relief=tk.SUNKEN)
        separator2.pack(side=tk.TOP, fill=tk.X)

        # Frame pour la partie B
        frame_b = ttk.Frame(master)
        frame_b.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Label2 centré dans la partie B
        self.server_status = tk.StringVar(value='starting...')
        self.label2 = tk.Entry(frame_b, textvariable=self.server_status, state='readonly', width=30)
        self.label2.pack(pady=10)

        # Button centré dans la partie B
        self.open_button = tk.Button(frame_b, text="Ouvrir Panoptic", width=20, command=self.open_panoptic)
        self.open_button['state'] = "disabled"
        self.open_button.pack(pady=10)

        self.init_projects()

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

        self.combo_box.bind("<<ComboboxSelected>>", self.load_project)

        # Récupérer les noms des projets dans une liste
        project_names = [project['name'] for project in self.projects['projects']]

        if project_names:
            # Mettre à jour la liste déroulante
            self.combo_box['values'] = project_names
            # Sélectionner le premier projet par défaut s'il existe
            self.combo_box.current(0)
            self.selected_project = self.projects['projects'][0]

        if self.projects['last_opened'] is not None:
            index = project_names.index(self.projects['last_opened']['name'])
            self.combo_box.current(index)
            self.selected_project = self.projects['projects'][index]

        if self.selected_project:
            self.load_project()

    def init_folders(self):
        self.listbox.delete(0, tk.END)
        failed = True
        while failed:
            try:
                res = requests.get(api('folders')).json()
                for folder in res:
                    if folder['parent'] is None:
                        self.listbox.insert(tk.END, folder['path'])
                failed = False
                message = 'running'
                if HOST:
                    try:
                        ip = socket.gethostbyname(socket.gethostname())
                        message += f' on {ip}:{PORT}'
                    except:
                        pass
                ui.server_status.set(message)
                ui.open_button['state'] = "normal"
            except Exception:
                pass
            sleep(0.5)

    def add_folder(self):
        folder_path = askdirectory(parent=self.master, title='Select a directory')
        # self.listbox.insert(tk.END, folder_path)
        print(folder_path)
        res = requests.post(api('folders'), headers={"Content-type": "application/json"},
                            json={"path": folder_path}).json()
        self.listbox.delete(0, tk.END)
        for folder in res:
            if folder['parent'] is None:
                self.listbox.insert(tk.END, folder['path'])

    def open_panoptic(self):
        webbrowser.open(FRONT_URL)
        self.projects['last_opened'] = self.selected_project
        with open(PROJECT_PATH, 'w') as json_file:
            json.dump(self.projects, json_file)

    def create_project(self):
        # Demander à l'utilisateur de choisir un emplacement pour le projet
        folder_path = filedialog.askdirectory()

        # Récupérer le nom du projet depuis le dernier dossier du chemin
        project_name = os.path.basename(folder_path)

        # Créer un nouvel objet projet
        new_project = {'name': project_name, 'path': folder_path}

        # Ajouter le nouveau projet aux données existantes
        self.projects['projects'].append(new_project)

        # Enregistrer les données dans le fichier JSON
        with open(PROJECT_PATH, 'w') as json_file:
            json.dump(self.projects, json_file)

        # Mettre à jour la liste déroulante
        project_names = [project['name'] for project in self.projects['projects']]
        self.combo_box['values'] = project_names

        # Sélectionner le nouveau projet dans la liste déroulante
        self.combo_box.current(len(project_names) - 1)
        self.load_project()

    def load_project(self, event=None):
        if len(self.projects['projects']) == 0:
            return
        self.selected_project = self.projects['projects'][self.combo_box.current()]
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
    ui.server_status.set('fastapi init...')
    t1 = Thread(target=ui.init_folders)
    t1.start()


def launch_uvicorn():
    from panoptic.api import app
    app.add_event_handler('startup', on_fastapi_start)
    app.add_event_handler('shutdown', lambda: ui.server_status.set('stopped'))
    if HOST:
        uvicorn.run(app, host="0.0.0.0")
    else:
        uvicorn.run(app)


def start_thread():
    global THREAD
    THREAD = Thread(target=launch_uvicorn)
    THREAD.daemon = True
    THREAD.start()


def start():
    parser = argparse.ArgumentParser(description="Start Panoptic, use --host to share your panoptic across local network")
    parser.add_argument('--host', action="store_true")
    args = parser.parse_args()
    global HOST
    HOST = args.host
    root = tk.Tk()
    try:
        root.iconbitmap(os.path.join(os.path.dirname(__file__), "html/favicon.ico"))
    except:
        pass

    global ui
    ui = MiniUI(root)

    root.mainloop()

if __name__ == '__main__':
    start()