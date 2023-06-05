import os
import tkinter as tk
import webbrowser
import socket
import argparse
from threading import Thread
from time import sleep
from tkinter.filedialog import askdirectory
from panoptic.api import app

import uvicorn
import requests

PORT = 8000
HOST = False

def api(path):
    return 'http://localhost:' + str(PORT) + '/' + path


FRONT_URL = 'http://localhost:5173/' if os.getenv("PANOPTIC_ENV", "PROD") == "DEV" else api("")

class MiniUI:
    def __init__(self, master):
        self.master = master
        master.title("Panoptic Server")

        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        x = (screen_width // 2) - (500 // 2)  # Change 500 to the desired window width
        y = (screen_height // 2) - (300 // 2)  # Change 400 to the desired window height

        # Set the window position and size
        master.geometry(f"500x300+{x}+{y}")

        self._database_name = tk.StringVar(value='compute.db')
        self.server_status = tk.StringVar(value='starting...')

        # Create a label
        self.label = tk.Label(master, textvariable=self._database_name)
        self.label.pack()

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


def on_fastapi_start():
    ui.server_status.set('fastapi init...')
    t1 = Thread(target=ui.init_folders)
    t1.start()


def launch_uvicorn():
    app.add_event_handler('startup', on_fastapi_start)
    app.add_event_handler('shutdown', lambda: ui.server_status.set('stopped'))
    if HOST:
        uvicorn.run(app, host="0.0.0.0")
    else:
        uvicorn.run(app)
    # while True:
    #     print("running")
    #     sleep(2)


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
    thread = Thread(target=launch_uvicorn)
    thread.daemon = True
    thread.start()
    global ui
    ui = MiniUI(root)

    root.mainloop()

if __name__ == '__main__':
    start()