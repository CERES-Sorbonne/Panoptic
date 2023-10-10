import tkinter as tk
from tkinter import ttk

import tkinter as tk
from tkinter import ttk

class MiniUI:
    def __init__(self, master):
        self.master = master
        self.selected_project = None
        self.projects = None

        master.title("Panoptic Server")

        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        x = (screen_width // 2) - (500 // 2)
        y = (screen_height // 2) - (350 // 2)

        master.geometry(f"500x350+{x}+{y}")

        # Frame pour la partie A
        frame_a = ttk.Frame(master)
        frame_a.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Frame pour la partie A.1
        frame_a1 = ttk.Frame(frame_a)
        frame_a1.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))

        # Label, combobox et bouton dans la partie A.1
        self.label = tk.Label(frame_a1, text="Choisir Projet existant", command=self.create_project)
        self.label.pack(pady=10)

        self.combobox = ttk.Combobox(frame_a1)
        self.combobox.pack(pady=10, padx=5)

        self.new_project_button = tk.Button(frame_a1, text="Nouveau projet")
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
        self.label2 = tk.Entry(frame_b, textvariable=self.server_status, state='readonly')
        self.label2.pack(pady=10)

        # Button centré dans la partie B
        self.open_button = tk.Button(frame_b, text="Ouvrir Panoptic", width=20)
        self.open_button['state'] = "disabled"
        self.open_button.pack(pady=10)


if __name__ == "__main__":
    root = tk.Tk()
    app = MiniUI(root)
    root.mainloop()