import os
import subprocess
import sys
from pathlib import Path

def run_command(command, check=False, capture_output=False, shell=True):
    result = subprocess.run(command, shell=shell, text=True, capture_output=capture_output)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {command}")
    return result

# Ajouter .local/bin au PATH
local_bin = Path.home() / ".local" / "bin"
os.environ["PATH"] = f"{local_bin}{os.pathsep}{os.environ.get('PATH', '')}"

# Vérifier si uv est disponible, sinon l'installer
try:
    run_command("where uv", check=True)
except RuntimeError:
    run_command('powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"')
    os.environ["PATH"] = f"{local_bin}{os.pathsep}{os.environ.get('PATH', '')}"

# Naviguer dans le dossier utilisateur
home_dir = Path.home()
os.chdir(home_dir)

# Créer le dossier panoptic s'il n'existe pas
panoptic_dir = home_dir / "panoptic"
panoptic_dir.mkdir(exist_ok=True)
os.chdir(panoptic_dir)

# Créer l'environnement virtuel avec Python 3.12 s'il n'existe pas
if not (panoptic_dir / ".venv").exists():
    run_command("uv venv --python 3.12")

# Installer la dernière version de pip
run_command("uv pip install pip")

# Vérifier si panoptic est installé, sinon l'installer
if run_command("uv pip show panoptic", capture_output=True).returncode != 0:
    run_command("uv pip install panoptic")

# Vérifier si panoptic est obsolète
outdated = run_command("uv pip list --outdated", capture_output=True).stdout
if "panoptic" in outdated:
    user_input = input("Mise à jour trouvée, voulez-vous l'installer ? (O/N) ").strip().lower()
    if user_input == "o":
        run_command("uv pip install -U panoptic")
else:
    print("La dernière version de panoptic est déjà installée.")

# Activer l'environnement virtuel et lancer panoptic
venv_activate = panoptic_dir / ".venv" / "Scripts" / "activate"
panoptic_exe = panoptic_dir / ".venv" / "Scripts" / "panoptic"
subprocess.run(f"call {venv_activate} & call {panoptic_exe}", shell=True)
