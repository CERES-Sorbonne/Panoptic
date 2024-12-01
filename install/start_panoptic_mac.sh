#!/bin/bash

ENV_DIR="panoptic_env"
MIN_PYTHON_VERSION="3.10"

# Vérifie et installe les outils de développement Xcode si non installés
if ! xcode-select -p &> /dev/null; then
    echo "Installation des outils de développement Xcode requis..."
    xcode-select --install
    read -p "Appuyez sur Entrée une fois l'installation des outils Xcode terminée..."
fi

# Vérifie si Python >= 3.10 et pip3 sont installés, sinon installe Python via Homebrew
check_and_install_python() {
    if ! command -v python3 &> /dev/null || ! command -v pip3 &> /dev/null || [[ "$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" < "$MIN_PYTHON_VERSION" ]]; then
        echo "Installation de Python >= 3.10 et de pip3 requis..."
        if ! command -v brew &> /dev/null; then
            echo "Homebrew n'est pas installé. Installation de Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.bash_profile
            source ~/.bash_profile
        fi
        brew install python@3.11
        PYTHON_EXEC="python3.11"
        PIP_EXEC="pip3"
    else
        PYTHON_EXEC="python3"
        PIP_EXEC="pip3"
    fi
}

# Vérifie et installe Python si nécessaire
check_and_install_python

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
LATEST_PANOPTIC_VERSION=$($PIP_EXEC install panoptic==999999 2>&1 | grep -oP '(?<=from versions: )[^)]+' | tr ', ' '\n' | grep -v 'rc' | tail -1)
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
