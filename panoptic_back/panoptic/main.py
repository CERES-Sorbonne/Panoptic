import json
import os
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

PORT = 8000
HOST = False
THREAD = None

def api(path):
    return 'http://localhost:' + str(PORT) + '/' + path


FRONT_URL = 'http://localhost:5173/' if os.getenv("PANOPTIC_ENV", "PROD") == "DEV" else api("")
PROJECT_PATH = os.path.join(os.getenv("APPDATA"), "panoptic", "projects.json")


class MiniUI:
    def __init__(self, master):
        self.master = master
        self.selected_project = None
        self.projects = None

        master.title("Panoptic Server")

        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        x = (screen_width // 2) - (500 // 2)
        y = (screen_height // 2) - (300 // 2)

        master.geometry(f"500x300+{x}+{y}")

        # Label "Choisir un projet existant"
        self.label = tk.Label(master, text="Choisir un projet existant")
        self.label.pack()

        # Créer une liste déroulante
        self.combobox = ttk.Combobox(master)
        self.combobox.pack()

        # Bouton "Créer un nouveau projet"
        self.new_project_button = tk.Button(master, text="Créer un nouveau projet", command=self.create_project)
        self.new_project_button.pack()

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

        self.combobox.bind("<<ComboboxSelected>>", self.load_project)

        # Récupérer les noms des projets dans une liste
        project_names = [project['name'] for project in self.projects['projects']]

        if project_names:
            # Mettre à jour la liste déroulante
            self.combobox['values'] = project_names
            # Sélectionner le premier projet par défaut s'il existe
            self.combobox.current(0)
            self.selected_project = self.projects['projects'][0]

        if self.projects['last_opened'] is not None:
            index = project_names.index(self.projects['last_opened']['name'])
            self.combobox.current(index)
            self.selected_project = self.projects['projects'][index]

        if self.selected_project:
            self.load_project()

        self.server_status = tk.StringVar(value='starting...')

        self.label2 = tk.Entry(master, textvariable=self.server_status, state='readonly')
        self.label2.pack()

        # Create a button to add new folders
        self.button = tk.Button(master, text="Add Folder", command=self.add_folder)
        self.button.pack()

        # Create a listbox to display imported folders
        self.listbox = tk.Listbox(master)
        # self.listbox.insert(tk.END, "path/lala/lolo")
        self.listbox.pack(fill=tk.BOTH, expand=True)

        # Create a button to
        self.open_button = tk.Button(master, text="Open Panoptic", command=self.open_panoptic)
        self.open_button['state'] = "disabled"
        self.open_button.pack()

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
        self.combobox['values'] = project_names

        # Sélectionner le nouveau projet dans la liste déroulante
        self.combobox.current(len(project_names) - 1)
        self.load_project()

    def load_project(self, event=None):
        if len(self.projects['projects']) == 0:
            return
        self.selected_project = self.projects['projects'][self.combobox.current()]
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