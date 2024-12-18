import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from tqdm import tqdm

# Variables de configuration
home_dir = Path.home()
env_dir = home_dir / "panoptic" / "panoptic_env"
min_python_version = (3, 10)
target_python_version = "3.12.7"
python_folder_name = "Python" + "".join(target_python_version.split('.')[0:2])
python_paths = [
    str(Path(os.getenv('ProgramFiles')) / python_folder_name),
    str(Path(os.getenv('ProgramFiles')) / python_folder_name / 'Scripts'),
    str(Path(os.getenv('ProgramFiles(x86)')) / python_folder_name),
    str(Path(os.getenv('ProgramFiles(x86)')) / python_folder_name / 'Scripts')
]
python_installer = "python-installer.exe"
python_download_url = f"https://www.python.org/ftp/python/{target_python_version}/python-{target_python_version}-amd64.exe"

# Fonction pour télécharger un fichier avec une barre de progression
def download_with_progress(url, output_path):
    response = urllib.request.urlopen(url)
    total_size = int(response.info()["Content-Length"])
    with open(output_path, "wb") as f, tqdm(
        total=total_size, unit="B", unit_scale=True, desc="Téléchargement"
    ) as pbar:
        while True:
            chunk = response.read(1024)
            if not chunk:
                break
            f.write(chunk)
            pbar.update(len(chunk))

# Fonction d'installation de Python
def install_python():
    print(f"Installation de Python version {target_python_version}...")
    download_with_progress(python_download_url, python_installer)
    subprocess.run([
        python_installer, "/passive", "InstallAllUsers=1", "PrependPath=1"
    ], check=True)
    os.remove(python_installer)

    # Recharge le PATH pour inclure le nouveau Python
    os.environ['PATH'] = os.pathsep.join(python_paths + [os.environ['PATH']])
    return "python", "pip"

# Vérifie si Python >= 3.10 est installé
def get_python_and_pip():
    python_exec = "python"
    pip_exec = "pip"

    try:
        result = subprocess.run(
            [python_exec, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
            capture_output=True, text=True, check=True
        )
        python_version = tuple(map(int, result.stdout.strip().split('.')))
        if python_version >= min_python_version:
            return python_exec, pip_exec
        else:
            print(f"Version de Python obsolète détectée. Mise à jour vers Python {target_python_version}...")
            return install_python()
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Python n'est pas installé. Téléchargement et installation...")
        return install_python()

# Crée l'environnement virtuel si nécessaire
def setup_virtual_env(python_exec):
    if env_dir.exists():
        print(f"L'environnement '{env_dir}' existe déjà. Activation...")
    else:
        print(f"Création de l'environnement virtuel '{env_dir}'...")
        subprocess.run([python_exec, "-m", "venv", str(env_dir)], check=True)
        print("Installation de panoptic dans l'environnement virtuel...")
        subprocess.run([str(env_dir / "Scripts" / "python"), "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run([str(env_dir / "Scripts" / "pip"), "install", "panoptic"], check=True)
    return env_dir / "Scripts" / "activate"

# Vérifie et met à jour Panoptic si nécessaire
def check_and_update_panoptic():
    pip_exec = str(env_dir / "Scripts" / "pip")
    try:
        result = subprocess.run(
            [pip_exec, "install", "panoptic==9999999"],
            capture_output=True, text=True, check=False
        )
        all_versions = result.stderr.split("from versions: ")[-1].split(')')[0].split(',')
        latest_version = [v for v in st2 if 'rc' not in v][-1].strip()

        result = subprocess.run(
            [pip_exec, "show", "panoptic"],
            capture_output=True, text=True, check=True
        )
        current_version = [line.split(": ")[1] for line in result.stdout.splitlines() if line.startswith("Version")][0].strip()

        if latest_version > current_version:
            print(f"Une nouvelle version de panoptic est disponible : {latest_version} (actuellement installée : {current_version}).")
            reply = input("Souhaitez-vous installer la dernière version stable ? (o/n): ")
            if reply.lower() == "o":
                subprocess.run([pip_exec, "install", "-U", "panoptic"], check=True)
                print(f"Panoptic mis à jour vers la version {latest_version}.")
        else:
            print("Vous utilisez déjà la dernière version stable de panoptic.")
    except Exception as e:
        print(f"Erreur lors de la vérification de mise à jour de Panoptic : {e}")

# Désinstalle l'environnement virtuel et Python
def uninstall():
    if env_dir.exists():
        confirm_env = input(f"Voulez-vous supprimer l'environnement virtuel '{env_dir}' ? (o/n): ")
        if confirm_env.lower() == "o":
            print(f"Suppression de l'environnement virtuel '{env_dir}'...")
            for item in env_dir.rglob("*"):
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    item.rmdir()
            env_dir.rmdir()
            print("Environnement virtuel supprimé.")
    else:
        print("Aucun environnement virtuel trouvé.")

    confirm_python = input("Voulez-vous désinstaller Python ? (o/n): ")
    if confirm_python.lower() == "o":
        print("Désinstallation de Python...")
        subprocess.run(["wmic", "product", "where", "name like '%Python%'", "call", "uninstall"], check=False)
        print("Python désinstallé.")

# Lancement principal
def main():
    if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
        uninstall()
    else:
        python_exec, _ = get_python_and_pip()
        setup_virtual_env(python_exec)
        check_and_update_panoptic()

        print("Lancement de Panoptic...")
        subprocess.run([str(env_dir / "Scripts" / "panoptic")], check=False)

if __name__ == "__main__":
    main()