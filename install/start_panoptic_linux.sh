#!/usr/bin/env bash

assume_yes=false
reinstall=false
update_script_in_path=true
no_bin_copy=false

VENV_DIR="$HOME/panoptic/panoptic_env"
PYTHON_VERSION="3.12"
SCRIPT_NAME=$(basename "$0")
COMMAND_NAME="start-panoptic"
BIN_DIR="/usr/local/bin"
DESKTOP_FILE_URL="https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/panoptic.desktop"
DESKTOP_FILE="panoptic.desktop"
WHERE_TO_PUT_DESKTOP_FILE=("${XDG_DATA_HOME:-$HOME/.local/share}/applications" "$XDG_DESKTOP_DIR" "$HOME/Desktop" "$HOME/Bureau")
ICON_DESKTOP_FILE_URL="https://raw.githubusercontent.com/CERES-Sorbonne/Panoptic/refs/heads/main/install/panoptic.ico"
ICON_DESKTOP_FILE="panoptic.ico"
ICON_DESKTOP_DIR="$HOME/panoptic"


PACKAGES="python$PYTHON_VERSION python$PYTHON_VERSION-venv python$PYTHON_VERSION-dev"
PYTHON_EXEC="python$PYTHON_VERSION"

PIP_EXEC="$PYTHON_EXEC -m pip"
VENV_EXEC="$PYTHON_EXEC -m venv $VENV_DIR"

is_script_in_path () {
    if [ -x "$(command -v $COMMAND_NAME)" ]; then
        echo "Le script est déjà dans le PATH."
        if [ "$update_script_in_path" = true ]; then
            echo "Le script sera mis à jour."
            return 1
        fi
        return 0
    fi
    return 1
}

uninstall () {
    if [ $assume_yes = true ]; then
        REPLY="n"
    else
        read -p "Voulez-vous vraiment désinstaller panoptic ? (o/n) " -n 1 -r
        echo
    fi
    if [[ ! $REPLY =~ ^[Oo]$ ]]; then
        echo "Désinstallation annulée."
        exit 0
    fi
    echo "Suppression de l'environnement virtuel '$VENV_DIR'..."
    rm -rf "$VENV_DIR"
    if is_script_in_path; then
        echo "Suppression du script de démarrage '$COMMAND_NAME'..."
        sudo rm "$BIN_DIR/$COMMAND_NAME"
    fi
    echo "Désinstallation terminée, les fichiers de données et les paquets système ne sont pas affectés."
}

start_only () {
    source "$VENV_DIR"/bin/activate || { echo "L'environnement virtuel n'existe pas. Veuillez exécuter le script sans l'option -s pour utilisez les procédures d'installation."; exit 1; }
    echo "Lancement de panoptic..."
    panoptic || { echo "Erreur lors du lancement de panoptic."; exit 1; }
}

add_to_bin () {
    if [ "$no_bin_copy" = true ] || is_script_in_path ;  then
        return 0
    fi

    if [ -d "$BIN_DIR" ]; then
        if [ "$SCRIPT_NAME" == "$COMMAND_NAME" ] && [ $update_script_in_path != true ]; then
            echo "Le script est déjà dans le PATH. (Nom du script = Nom de la commande)"
            return 0
        else
          sudo cp "$SCRIPT_NAME" "$BIN_DIR/$COMMAND_NAME" || { echo "Erreur lors de la copie du script dans $BIN_DIR."; exit 1; }
          sudo chmod +x "$BIN_DIR/$COMMAND_NAME" || { echo "Erreur lors du changement des permissions du script."; exit 1; }
          echo "Le script a été copié dans $BIN_DIR."
        fi
    else
        echo "Le répertoire $BIN_DIR n'existe pas. Le script n'a pas été copié."
    fi
}

# Fonction pour ajouter l'icône desktop
add_icon_file () {
  wget -O "$ICON_DESKTOP_FILE" "$ICON_DESKTOP_FILE_URL" || { echo "Erreur lors du téléchargement de l'icône desktop."; exit 1; }
  cp "$ICON_DESKTOP_FILE" "$ICON_DESKTOP_DIR/$ICON_DESKTOP_FILE" || { echo "Erreur lors de la copie de l'icône desktop dans $ICON_DESKTOP_DIR."; exit 1; }
}

# Fonction pour ajouter le fichier desktop dans les répertoires standards
add_desktop_file () {
    downloaded=false
    for i in "${WHERE_TO_PUT_DESKTOP_FILE[@]}"; do
        if [ ! -d "$i" ]; then
            continue
        fi

        if [ -f "$i/$DESKTOP_FILE" ]; then
          if [ "$reinstall" = true ] ; then
            rm "$i/$DESKTOP_FILE" || { echo "Erreur lors de la suppression du fichier desktop dans $i."; exit 1; }
          else
            echo "Le fichier desktop existe déjà dans $i."
            continue
          fi
        fi

        if [ -d "$i" ]; then
            if [ "$downloaded" = false ]; then
                echo "Téléchargement du fichier desktop..."
                wget -O "$DESKTOP_FILE" "$DESKTOP_FILE_URL" || { echo "Erreur lors du téléchargement du fichier desktop."; exit 1; }
                sed -i 's|PANOPTIC_ICON_PATH|'"${ICON_DESKTOP_DIR}/${ICON_DESKTOP_FILE}"'|g' "$DESKTOP_FILE"
                add_icon_file
                downloaded=true
            fi
            cp "$DESKTOP_FILE" "$i" || { echo "Erreur lors de la copie du fichier desktop dans $i."; exit 1; }
            gio set "$i/$DESKTOP_FILE" "metadata::trusted" true || { echo "Erreur lors du changement des permissions du fichier desktop."; exit 1; }
            chmod a+x "$i/$DESKTOP_FILE" || { echo "Erreur lors du changement des permissions du fichier desktop."; exit 1; }
            echo "Le fichier desktop a été copié dans $i."
        fi
    done
    case $PWD/ in
      */Panoptic/install/*)
        echo "$DESKTOP_FILE ne sera pas supprimé, car le script est exécuté depuis le dépôt git."
        return 0
        ;;
      *)
        rm "$DESKTOP_FILE"
        ;;
    esac
}

install_packages () {
    packagesNeeded=$1
    # shellcheck disable=SC2086
    if [ -x "$(command -v apk)" ];
    then
        sudo apk add --no-cache $packagesNeeded ${assume_yes:+"--noconfirm"}
    elif [ -x "$(command -v apt-get)" ];
    then
        sudo apt-get install $packagesNeeded ${assume_yes:+"--yes"}
    elif [ -x "$(command -v dnf)" ];
    then
        sudo dnf install $packagesNeeded ${assume_yes:+"-y"}
    elif [ -x "$(command -v zypper)" ];
    then
        sudo zypper install $packagesNeeded ${assume_yes:+"-y"}
    else
        echo "FAILED TO INSTALL PACKAGE: Package manager not found. You must manually install: ${packagesNeeded[*]}">&2;
    fi
    }

check_python_version_in_venv () {
    if [[ "$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" != "$PYTHON_VERSION" ]]; then
        echo "Installation de Python == $PYTHON_VERSION requis..."
        return 1
    fi
    return 0
}

check_panoptic () {
    if ! command -v panoptic &> /dev/null; then
        echo "Installation de panoptic dans l'environnement virtuel..."
        $PIP_EXEC install panoptic
    else
        echo "panoptic est déjà installé dans l'environnement virtuel."
    fi
}

create_venv () {
    $VENV_EXEC || (install_packages "$PACKAGES" && $VENV_EXEC ) || { echo "Erreur lors de la création de l'environnement virtuel"; exit 1; }
    echo "Installation de panoptic dans l'environnement virtuel..."
    source "$VENV_DIR"/bin/activate
    $PIP_EXEC install --upgrade pip
    $PIP_EXEC install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    $PIP_EXEC install panoptic
    echo "L'environnement virtuel '$VENV_DIR' a été créé et panoptic a été installé."
}

recreate () {
    echo "Suppression de l'environnement virtuel '$VENV_DIR'..."
    rm -rf "$VENV_DIR"
    create_venv
}

resolve_venv () {
  if [ ! -d "$VENV_DIR" ]; then
      echo "L'environnement virtuel n'existe pas."
      create_venv
      return 0
  fi

  echo "L'environnement virtuel '$VENV_DIR' existe déjà."
  if [ "$reinstall" = true ]; then
    recreate
    return 0
  fi

  echo "Activation de l'environnement virtuel..."
  source "$VENV_DIR"/bin/activate

  check_python_version_in_venv
  if [ $? -eq 1 ]; then
    if [ "$assume_yes" = true ]; then
      REPLY="o"
    else
      read -p "L'environnement virtuel existant a été créé avec une version de Python différente.\nSouhaitez-vous le recréer ? (o/n) avec la version $PYTHON_VERSION puis réinstaller panoptic ? " -n 1 -r
      echo
    fi

    if [[ $REPLY =~ ^[Oo]$ ]]; then
      recreate
    else
      check_panoptic
    fi
    fi
}

for i in "$@"; do
  case $i in
    -y|--yes|--assume-yes)
      assume_yes=true
      shift
      ;;
    -r|--reinstall)
      reinstall=true
      shift
      ;;
    -s|--start-only)
      start_only
      exit 0
      ;;
    -u|--uninstall)
      uninstall
      exit 0
      ;;
    --no-bin-copy)
      no_bin_copy=true
      shift
      ;;
    --no-update-script)
      update_script_in_path=false
      shift
      ;;
    -h|--help)
      echo "Usage: $SCRIPT_NAME [-y|--yes|--assume-yes] [-r|--reinstall] [-s|--start-only] [-u|--uninstall] [--no-bin-copy] [-h|--help]"
      echo "Options:"
      echo "  -y, --yes, --assume-yes  Assume yes for all prompts."
      echo "  -r, --reinstall          Recreate the virtual environment and reinstall panoptic."
      echo "  -s, --start-only         Start panoptic without checking the environment."
      echo "  -u, --uninstall          Uninstall panoptic and remove the virtual environment, won't remove any data nor system packages."
      echo "  --no-bin-copy            Don't copy the script to $BIN_DIR."
      echo "  --no-update-script       Don't update the script in $BIN_DIR."
      echo "  -h, --help               Display this help message."
      exit 0
      ;;
    *)
      ;;
  esac
done

## MAIN ##

# Ajoute le script dans le PATH
add_to_bin
add_desktop_file

resolve_venv

# Active l'environnement virtuel
source "$VENV_DIR"/bin/activate

# Vérifie si une mise à jour de panoptic est disponible et propose de l'installer
LATEST_PANOPTIC_VERSION=$($PIP_EXEC install panoptic==pedro 2>&1 | grep -oP '(?<=from versions: )[^)]+' | tr ', ' '\n' | grep -v 'rc' | tail -1)
CURRENT_PANOPTIC_VERSION=$($PIP_EXEC show panoptic | grep -oP '(?<=Version: )[^ ]+')

if [[ "$LATEST_PANOPTIC_VERSION" > "$CURRENT_PANOPTIC_VERSION" ]]; then
    echo "Une nouvelle version de panoptic est disponible : $LATEST_PANOPTIC_VERSION (actuellement installée : $CURRENT_PANOPTIC_VERSION)."
    if [ "$assume_yes" = true ]; then
        REPLY="o"
    else
        read -p "Souhaitez-vous installer la dernière version stable ? (o/n) " -n 1 -r
        echo
    fi
    if [[ $REPLY =~ ^[Oo]$ ]]; then
        $PIP_EXEC install -U panoptic
        echo "Panoptic mis à jour vers la version $LATEST_PANOPTIC_VERSION."
    fi
else
    echo "Vous possédez déjà la dernière version stable de panoptic."
fi

# Lance la commande panoptic
echo "Lancement de panoptic..."
panoptic || { echo "Erreur lors du lancement de panoptic."; exit 1; }
