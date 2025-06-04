#!/bin/bash

if ! xcode-select -p &> /dev/null; then
    echo "Installation des outils de développement Xcode requis..."
    xcode-select --install
    read -p "Appuyez sur Entrée une fois l'installation des outils Xcode terminée..."
fi

# Vérifier si uv est installé
if ! command -v uv &> /dev/null; then
    echo "uv n'est pas installé. Installation en cours..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
    source ~/.zshrc
fi

# Vérifier si le dossier ~/panoptic existe
if [ ! -d "$HOME/panoptic" ]; then
    echo "Création du dossier ~/panoptic"
    mkdir -p "$HOME/panoptic"
fi

# Se déplacer dans le dossier
cd "$HOME/panoptic" || exit

# Vérifier si l'environnement virtuel existe
if [ ! -d ".venv" ]; then
    echo "Création de l'environnement virtuel Python 3.11"
    uv venv --python 3.11
fi

# Installer la dernière version de pip
uv pip install pip

# Vérifier si panoptic est installé
if ! uv pip show panoptic &> /dev/null; then
    echo "Panoptic n'est pas installé. Installation en cours..."
    uv pip install panoptic
else
    echo "Panoptic est installé. Vérification des mises à jour..."
    LATEST_VERSION=$(uvx pip index versions panoptic | grep -oE "[0-9]+\.[0-9]+\.[0-9]+" | sort -V | tail -n 1)
    CURRENT_VERSION=$(uv pip show panoptic | grep -i "Version:" | sed -E 's/(.*)Version: (.*)/\2/')
    if [ "$LATEST_VERSION" != "$CURRENT_VERSION" ]; then
        read -p "Une nouvelle version de Panoptic ($LATEST_VERSION) est disponible. Voulez-vous l'installer ? (y/n) " choice
        if [ "$choice" = "y" ]; then
            uv pip install --upgrade panoptic
        fi
    fi
fi

# Lancer Panoptic
uv run panoptic
