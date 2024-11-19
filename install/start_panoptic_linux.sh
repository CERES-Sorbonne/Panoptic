#!/usr/bin/env bash

assume_yes=false
reinstall=false
start_only=false

VENV_DIR="$HOME/panoptic/panoptic_env"
PYTHON_VERSION="3.12"
SCRIPT_NAME=$(basename "$0")
COMMAND_NAME="start-panoptic"

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
      start_only=true
      shift
      ;;
    -h|--help)
      echo "Usage: $SCRIPT_NAME [-y|--yes|--assume-yes] [-r|--reinstall] [-s|--start-only] [-h|--help]"
      echo "Options:"
      echo "  -y, --yes, --assume-yes  Assume yes for all prompts."
      echo "  -r, --reinstall          Recreate the virtual environment and reinstall panoptic."
      echo "  -s, --start-only         Start panoptic without checking the environment."
      echo "  -h, --help               Display this help message."
      exit 0
      ;;
    *)
      ;;
  esac
done

if [ "$start_only" = true ]; then
    source "$VENV_DIR"/bin/activate || { echo "L'environnement virtuel n'existe pas. Veuillez exécuter le script sans l'option -s pour utilisez les procédures d'installation."; exit 1; }
    echo "Lancement de panoptic..."
    panoptic || { echo "Erreur lors du lancement de panoptic."; exit 1; }
    exit 0
fi

PACKAGES="python$PYTHON_VERSION python$PYTHON_VERSION-venv python$PYTHON_VERSION-dev"
PYTHON_EXEC="python$PYTHON_VERSION"

PIP_EXEC="$PYTHON_EXEC -m pip"
VENV_EXEC="$PYTHON_EXEC -m venv $VENV_DIR"

is_script_in_path () {
    if [ -x "$(command -v $COMMAND_NAME)" ]; then
        echo "Le script est déjà dans le PATH."
        return 0
    fi
    return 1
}

add_to_bin () {
    if is_script_in_path; then
        return 0
    fi

    if [ -d "/usr/bin" ]; then
        if [ "$SCRIPT_NAME" == "$COMMAND_NAME" ]; then
            echo "Le script est déjà dans le PATH. (Nom du script = Nom de la commande)"
            return 0
        fi
        cp "$SCRIPT_NAME" "/usr/bin/$COMMAND_NAME"
        chmod +x "/usr/bin/$COMMAND_NAME"
        echo "Le script a été copié dans /usr/bin."
    else
        echo "Le répertoire /usr/bin n'existe pas. Le script n'a pas été copié."
    fi
}


install_packages () {
    packagesNeeded=$1
    if [ -x "$(command -v apk)" ];
    then
        sudo apk add --no-cache "${packagesNeeded[@]}" ${assume_yes:+"--noconfirm"}
    elif [ -x "$(command -v apt-get)" ];
    then
        sudo apt-get install "${packagesNeeded[@]}" ${assume_yes:+"--yes"}
    elif [ -x "$(command -v dnf)" ];
    then
        sudo dnf install "${packagesNeeded[@]}" ${assume_yes:+"-y"}
    elif [ -x "$(command -v zypper)" ];
    then
        sudo zypper install "${packagesNeeded[@]}" ${assume_yes:+"-y"}
    else
        echo "FAILED TO INSTALL PACKAGE: Package manager not found. You must manually install: ${packagesNeeded[*]}">&2;
    fi
    }

check_python_install () {
  commands=("$PYTHON_EXEC" "$PIP_EXEC" "$VENV_EXEC")
  for cmd in "${commands[@]}"; do
    if ! command -v $cmd &> /dev/null; then
        echo "Installation de $cmd requis..."
        return 1
    fi
  done
  return 0
  }

check_python_version_in_venv () {
    if [[ "$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" != "$PYTHON_VERSION" ]]; then
        echo "Installation de Python == $PYTHON_VERSION requis..."
        return 1
    fi
    return 0
}

check_panoptic () {
    source "$VENV_DIR"/bin/activate
    if ! command -v panoptic &> /dev/null; then
        echo "Installation de panoptic dans l'environnement virtuel..."
        $PIP_EXEC install panoptic
    else
        echo "panoptic est déjà installé dans l'environnement virtuel."
    fi
}

create_venv () {
    $VENV_EXEC
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

check_venv () {
    if [ "$reinstall" = true ]; then
        recreate
    else
      if [ ! -d "$VENV_DIR" ]; then
          echo "L'environnement virtuel '$VENV_DIR' n'existe pas. Création..."
          create_venv
      else
          echo "L'environnement virtuel '$VENV_DIR' existe déjà. Activation..."
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
      fi
    fi
}

# Ajoute le script dans le PATH
add_to_bin

# Vérifie si Python == `$PYTHON_VERSION`, pip et venv sont installés, sinon installe ceux qui manquent
#if ! command -v $PYTHON_EXEC &> /dev/null || ! command -v $PIP_EXEC &> /dev/null || command -v $VENV_EXEC &> /dev/null; then
if ! check_python_install; then
    echo "Installation de python$PYTHON_VERSION, pip et/ou venv requis..."
    install_packages "$PACKAGES" || { echo "Erreur lors de l'installation de python$PYTHON_VERSION, pip et/ou venv."; exit 1; }
else
    echo "python$PYTHON_VERSION, pip et venv sont déjà installés."
fi

check_venv

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
