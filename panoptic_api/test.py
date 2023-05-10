import asyncio
import sys
import threading
import tkinter as tk
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from time import sleep
from tkinter.filedialog import askdirectory

import uvicorn
from uvicorn import Config

from panoptic_api.main import app


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
        self.listbox.insert(tk.END, "path/lala/lolo")
        self.listbox.pack(fill=tk.BOTH, expand=True)

        # Create a button to add new folders
        self.button = tk.Button(master, text="Add Folder", command=self.add_folder)
        self.button.pack()

    def add_folder(self):
        self.listbox.insert(tk.END, askdirectory(parent=self.master, title='Select a directory'))


def launch_uvicorn():
    uvicorn.run(app)


root = tk.Tk()

if __name__ == '__main__':
    thread = threading.Thread(target=launch_uvicorn)
    thread.daemon = True
    thread.start()

    ui = MiniUI(root)

    app.add_event_handler('startup', lambda: ui.server_status.set('running'))
    app.add_event_handler('shutdown', lambda: ui.server_status.set('stopped'))

    root.mainloop()
