import tkinter as tk
from multiprocessing import Process
from threading import Thread
from time import sleep
from tkinter.filedialog import askdirectory

import uvicorn
from fastapi import FastAPI
import requests
from uvicorn import logging

port = 8000


def api(path):
    return 'http://localhost:' + str(port) + '/' + path


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

        self._database_name = tk.StringVar(value='panoptic.db')
        self.server_status = tk.StringVar(value='starting...')

        # Create a label
        self.label = tk.Label(master, textvariable=self._database_name)
        self.label.pack()

        self.label2 = tk.Label(master, textvariable=self.server_status)
        self.label2.pack()

        # Create a listbox to display imported folders
        self.listbox = tk.Listbox(master)
        # self.listbox.insert(tk.END, "path/lala/lolo")
        self.listbox.pack(fill=tk.BOTH, expand=True)

        # Create a button to add new folders
        self.button = tk.Button(master, text="Add Folder", command=self.add_folder)
        self.button.pack()

    def init_folders(self):
        failed = True
        while failed:
            try:
                res = requests.get(api('folders')).json()
                for folder in res:
                    self.listbox.insert(tk.END, folder['path'])
                failed = False
                ui.server_status.set('running !')
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
            self.listbox.insert(tk.END, folder['path'])


def on_fastapi_start():
    ui.server_status.set('fastapi init...')
    t1 = Thread(target=ui.init_folders)
    t1.start()


def launch_uvicorn():
    from panoptic_api.main import app
    app.add_event_handler('startup', on_fastapi_start)
    app.add_event_handler('shutdown', lambda: ui.server_status.set('stopped'))
    uvicorn.run(app)
    # while True:
    #     print("running")
    #     sleep(2)


if __name__ == '__main__':
    root = tk.Tk()
    thread = Thread(target=launch_uvicorn)
    thread.daemon = True
    thread.start()

    ui = MiniUI(root)

    root.mainloop()
