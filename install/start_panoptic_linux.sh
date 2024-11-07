#!/bin/bash

ENV_DIR="~/panoptic/panoptic_env"
MIN_PYTHON_VERSION="3.10"
TARGET_PYTHON_VERSION="3.12"

# Vérifie si Python >= 3.10 et pip3 sont installés, sinon installe python3.12 et pip3
if ! command -v python3 &> /dev/null || ! command -v pip3 &> /dev/null || [[ "$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" < "$MIN_PYTHON_VERSION" ]]; then
    echo "Installation de Python >= 3.10 et de pip3 requis..."
    sudo apt update && sudo apt install -y python$TARGET_PYTHON_VERSION python$TARGET_PYTHON_VERSION-venv
    PYTHON_EXEC="python"$TARGET_PYTHON_VERSION
    PIP_EXEC="pip3"
else
    PYTHON_EXEC="python3"
    PIP_EXEC="pip3"
fi

# Vérifie si l'environnement virtuel existe
if [ -d "$ENV_DIR" ]; then
    echo "L'environnement '$ENV_DIR' existe déjà. Activation..."
else
    echo "Création de l'environnement virtuel '$ENV_DIR'..."
    $PYTHON_EXEC -m venv $ENV_DIR
    echo "Installation de panoptic dans l'environnement virtuel..."
    source $ENV_DIR/bin/activate
    $PIP_EXEC install --upgrade pip
    $PIP_EXEC install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    $PIP_EXEC install panoptic
fi

# Active l'environnement virtuel
source $ENV_DIR/bin/activate

# Vérifie si une mise à jour de panoptic est disponible et propose de l'installer
LATEST_PANOPTIC_VERSION=$($PIP_EXEC install panoptic==nonexistent 2>&1 | grep -oP '(?<=from versions: )[^)]+' | tr ', ' '\n' | grep -v 'rc' | tail -1)
CURRENT_PANOPTIC_VERSION=$($PIP_EXEC show panoptic | grep -oP '(?<=Version: )[^ ]+')

if [[ "$LATEST_PANOPTIC_VERSION" > "$CURRENT_PANOPTIC_VERSION" ]]; then
    echo "Une nouvelle version de panoptic est disponible : $LATEST_PANOPTIC_VERSION (actuellement installée : $CURRENT_PANOPTIC_VERSION)."
    read -p "Souhaitez-vous installer la dernière version stable ? (o/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Oo]$ ]]; then
        $PIP_EXEC install -U panoptic
        echo "Panoptic mis à jour vers la version $LATEST_PANOPTIC_VERSION."
    fi
else
    echo "Vous utilisez déjà la dernière version stable de panoptic."
fi

# Lance la commande panoptic
echo "Lancement de panoptic..."
panoptic
