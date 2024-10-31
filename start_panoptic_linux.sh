#!/bin/bash

ENV_DIR="panoptic_env"
MIN_PYTHON_VERSION="3.10"

# Fonction pour vérifier si Python >= 3.10 est installé
check_python_version() {
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if [[ "$(echo -e "$PYTHON_VERSION\n$MIN_PYTHON_VERSION" | sort -V | head -n1)" == "$MIN_PYTHON_VERSION" ]]; then
            echo "Python $PYTHON_VERSION est déjà installé."
            return 0
        fi
    fi
    return 1
}

# Vérifie si Python >= 3.10 est installé
if check_python_version; then
    PYTHON_EXEC="python3"
    PIP_EXEC="pip3"
else
    if ! sudo apt install -y python3.12 python3.12-venv; then
        echo "Python >= 3.10 n'est pas installé. Veuillez installer Python 3.10 ou plus récent."
        echo "Exécutez la commande suivante pour installer Python 3.12 sur Ubuntu/Debian :"
        echo "sudo apt update && sudo apt install -y python3.12 python3.12-venv"
        exit 1
    fi
fi

# Vérifie si pip est installé
if ! $PIP_EXEC --version &> /dev/null; then
    echo "pip n'est pas installé. Tentative d'installation de pip..."
    if ! apt install python3.12-venv; then
        echo "L'installation de pip a échoué. Essayez d'installer pip manuellement :"
        echo "sudo apt install -y python3-pip"
        exit 1
    fi
fi

# Vérifie si l'environnement virtuel existe
if [ -d "$ENV_DIR" ]; then
    echo "L'environnement '$ENV_DIR' existe déjà. Activation..."
else
    echo "Création de l'environnement virtuel '$ENV_DIR'..."
    if ! $PYTHON_EXEC -m venv $ENV_DIR; then
        sudo apt install python3.12-venv
        PYTHON_EXEC -m venv $ENV_DIR
    fi
    echo "Installation de panoptic dans l'environnement virtuel..."
    source $ENV_DIR/bin/activate
    $PIP_EXEC install --upgrade pip
    $PIP_EXEC install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    $PIP_EXEC install panoptic==0.3.5rc16
fi

# Active l'environnement
source $ENV_DIR/bin/activate

# Lance la commande panoptic
echo "Lancement de panoptic..."
panoptic
