# Panoptic

[![PyPI - Version](https://img.shields.io/pypi/v/panoptic.svg)](https://pypi.org/project/panoptic)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/panoptic.svg)](https://pypi.org/project/panoptic)


![Aperçu](https://github.com/CERES-Sorbonne/Panoptic/assets/10096711/8e6389c7-ee80-4e0f-95d8-790602bd028e)

Panoptic est un outil d'exploration et d'annotation de large corpus d'images, utilisant des outils d'analyse d'image et de machine learning pour faciliter ces tâches. 

Ayant besoin de librairies de deep learning, il est recommandé de l'utiliser avec un ordinateur ayant des capacités minimales en terme de calcul.

> Attention: Panoptic est encore en phase active de développement et n'est pour l'instant qu'un prototype, il est fort probable que vous rencontriez des bugs, aussi nous recommandons de n'utiliser cet outil que pour des tests et ne pas se reposer dessus pour un travail académique conséquent. 

## Scripts d'installation automatique et de lancement (recommandé)
<p style="color: red;">
Il se peut que le script vous demande votre mot de passe pour installer les dépendances, cela est nécessaire dans le cas où il vous manquerait des dépendances système pour installer Panoptic (python, pip et/ou venv).
</p>

### Windows

[//]: # (Voici les trois commandes à exécuter pour installer Panoptic sur Windows:)

[//]: # (```cmd)

[//]: # (curl -O https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_windows.ps1)

[//]: # (powershell -ExecutionPolicy Bypass -File start_panoptic_windows.ps1)

[//]: # (```)

[//]: # ()
[//]: # (Pour détailler un peu plus les étapes:)

[//]: # (1. Téléchargez le script d'installation automatique et de lancement de Panoptic en cliquant sur le lien suivant: [start_panoptic_windows.ps1]&#40;https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_windows.ps1&#41; ou directement depuis le terminal avec la commande suivante:)

[//]: # (```cmd)

[//]: # (curl -O https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_windows.ps1)

[//]: # (```)

[//]: # ()
[//]: # (2. Exécutez le script en double-cliquant sur le fichier ou en utilisant la commande suivante:)

[//]: # (```cmd)

[//]: # (powershell -ExecutionPolicy Bypass -File start_panoptic_windows.ps1)

[//]: # (```)

[//]: # ()
[//]: # (#### Post-installation)

[//]: # (Après l'installation, vous pouvez lancer Panoptic en vous rendant de nouveau dans le dossier où vous avez exécuté le script d'installation et en exécutant la commande suivante:)

[//]: # (```cmd)

[//]: # (powershell -ExecutionPolicy Bypass -File start-panoptic.ps1)

[//]: # (```)


### Linux
Voici les trois commandes à exécuter pour installer Panoptic sur Linux:
```bash
wget https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_linux.sh -O start_panoptic_linux.sh
chmod +x start_panoptic_linux.sh
./start_panoptic_linux.sh
```

Pour détailler un peu plus les étapes:
1. Téléchargez le script d'installation automatique et de lancement de Panoptic en cliquant sur le lien suivant: [start_panoptic_linux.sh](https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_linux.sh)
ou directement depuis le terminal avec la commande suivante:
```bash
wget https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_linux.sh -O start_panoptic_linux.sh
```
2. Rendez le script exécutable en utilisant les propriétés du fichier ou en utilisant la commande suivante:
```bash
chmod +x start_panoptic_linux.sh
```
3. Exécutez le script (double-cliquez sur le fichier ou utilisez la commande suivante):
```bash
./start_panoptic_linux.sh
```

Vous pouvez également préciser les paramètres de lancement de Panoptic en utilisant la commande suivante:
```bash
./start_panoptic_linux.sh [-y|--yes|--assume-yes] [-r|--reinstall] [-s|--start-only] [-u|--uninstall] [--no-bin-copy] [-h|--help]
```
Les options disponibles sont les suivantes:
- `-y`, `--yes` ou `--assume-yes`: Utilisez cette option pour accepter automatiquement toutes les demandes de confirmation.
- `-r` ou `--reinstall`: Utilisez cette option pour réinstaller Panoptic.
- `-s` ou `--start-only`: Utilisez cette option pour lancer Panoptic sans réinstaller.
- `-u` ou `--uninstall`: Utilisez cette option pour désinstaller Panoptic (ne supprime pas les données ni les dépendances système).'
- `--no-bin-copy`: Utilisez cette option pour ne pas copier le script de lancement de Panoptic dans le répertoire `/usr/local/bin`.
- `-h` ou `--help`: Utilisez cette option pour afficher l'aide.

#### Post-installation
Après l'installation, vous pouvez lancer Panoptic en utilisant la commande suivante:
```bash
start-panoptic
```
 
Vous pouvez également préciser les paramètres de lancement de Panoptic en utilisant la commande suivante:
```bash
start-panoptic [-y|--yes|--assume-yes] [-r|--reinstall] [-s|--start-only] [-u|--uninstall] [--no-bin-copy] [-h|--help]
```
Les options disponibles sont les suivantes:
- `-y`, `--yes` ou `--assume-yes`: Utilisez cette option pour accepter automatiquement toutes les demandes de confirmation.
- `-r` ou `--reinstall`: Utilisez cette option pour réinstaller Panoptic.
- `-s` ou `--start-only`: Utilisez cette option pour lancer Panoptic sans réinstaller.
- `-u` ou `--uninstall`: Utilisez cette option pour désinstaller Panoptic (ne supprime pas les données ni les dépendances système).'
- `--no-bin-copy`: Utilisez cette option pour ne pas copier le script de lancement de Panoptic dans le répertoire `/usr/local/bin`.
- `-h` ou `--help`: Utilisez cette option pour afficher l'aide.


### MacOS
Voici les trois commandes à exécuter pour installer Panoptic sur MacOS:
```bash
curl -O https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_mac.sh
chmod +x start_panoptic_mac.sh
./start_panoptic_mac.sh
```

Pour détailler un peu plus les étapes:
1. Téléchargez le script d'installation automatique et de lancement de Panoptic en cliquant sur le lien suivant: [start_panoptic_mac.sh](https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/start_panoptic_mac.sh)
2. Rendez le script exécutable en utilisant les propriétés du fichier ou en utilisant la commande suivante:
```bash
chmod +x start_panoptic_mac.sh
```
3. Exécutez le script (double-cliquez sur le fichier ou utilisez la commande suivante):
```bash
./start_panoptic_mac.sh
```

#### Post-installation
Après l'installation, vous pouvez lancer Panoptic en vous rendant de nouveau dans le dossier où vous avez exécuté le script d'installation et en exécutant la commande suivante:
```bash
./start-panoptic.sh
```

## Installations manuelle (avec pip)
<p style="color: red;">
Quel que soit votre OS vous aurez besoin de Python 3.10 ou supérieur, nous vous recommandons d'utiliser la version 3.12.
</p>

### Windows et Linux

Normalement il suffit d'ouvrir un terminal et de lancer les commandes suivantes pour installer, puis lancer panoptic:

- `pip3 install panoptic`
- `panoptic`

### MacOS

Sur mac il existe un prérequis supplémentaire, celui d'installer les outils en ligne de commande x-tools. 
Pour cela il faut ouvrir un terminal et lancer la commande suivante:
`xcode-select –-install` cela devrait lancer l'installation.

Une fois installé il suffit de lancer:

- `pip3 install panoptic`
- `panoptic`


## Installation Docker

Si vous avez rencontré des problèmes avec l'installation classique, ou que vous préférez utiliser Docker, une image est à disposition. Il faut tout d'abord:

### Installer Docker
- [Sur MacOS](https://docs.docker.com/desktop/install/mac-install/)
- [Sur Windows](https://docs.docker.com/desktop/install/windows-install/)
- [Sur Linux](https://docs.docker.com/desktop/install/linux-install/)

### Différences avec la version python

Sur la version docker, il n'existe pas la petite interface pour ajouter des dossiers ou gérer ses projets, il faut indiquer directement à docker les dossiers avec lesquels on va travailler:

### Option 1: Un seul dossier pour les images et pour les données panoptic:

Cela implique d'avoir créé un dossier spécial appelé "images", dans le dossier que vous indiquerez en entrée de panoptic. Dans l'exemple suivant, il faudrait ainsi que dans le dossier: `/chemin/vers/le/dossier`, il existe un dossier `images`dont le chemin complet serait par conséquent `/chemin/vers/le/dossier/images`.

Il faut ensuite lancer la commande suivante (avec Docker de lancé au préalable)

```console
docker run -it -p 8000:8000 -v /path/to/your/folder:/data --name panoptic ceressorbonne/panoptic
```

### Option 2: Un dossier pour les images, et un dossier pour les données panoptic:

```console
docker run -it -p 8000:8000 \
-v /path/to/your/data:/data \
-v /path/to/your/images:/data/images \
--name panoptic \
ceressorbonne/panoptic
```

## Installation (développement)

Les étapes suivantes impliquent d'avoir cloné le répertoire et sont recommandées pour les utilisateurs souhaitant avoir accès aux versions de développement, ou souhaitant modifier eux même le code afin de constribuer.

### Développement back uniquement

Pour tester et modifier le fonctionnement backend, nous fournissons un front-end déjà buildé dans le dossier html du back.
* aller dans le dossier `panoptic-back`
* pour installer les dépendances
    - `python3 setup.py install` simplement pour utiliser panoptic
    - `pip3 install -e .` pour développer
    - `pip3 install -r requirements.txt` et il faut ajouter `panoptic-back` au PYTHON_PATH également pour développer
* lancer `python panoptic/main.py`


### Développement front et back

1. Réaliser tout d'abord les étapes d'installation du backend
2. aller dans le dossier `panoptic-front`
3. lancer `npm install`
4. lancer `npm run dev`
5. avant de lancer le backend la variable d'environnement `PANOPTIC_ENV` devra être set à `DEV` afin d'utiliser le frontend de développement.
