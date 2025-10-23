#!/bin/bash

# Désactiver l'arrêt automatique en cas d'erreur pour gérer nous-mêmes les erreurs
set +e

if ! xcode-select -p &> /dev/null; then
    echo "Installation des outils de développement Xcode requis..."
    xcode-select --install
    read -p "Appuyez sur Entrée une fois l'installation des outils Xcode terminée..."
fi

# Tentative d'installation de libomp
LIBOMP_ERROR=false

# Vérifier si libomp est déjà installé
if [ -f "/opt/homebrew/opt/libomp/lib/libomp.dylib" ]; then
    echo "libomp est déjà installé"
    export DYLD_LIBRARY_PATH="/opt/homebrew/opt/libomp/lib:$DYLD_LIBRARY_PATH"
else
    echo "Tentative d'installation de libomp via Homebrew..."

    # Vérifier si brew est installé
    if ! command -v brew &> /dev/null; then
        echo "Homebrew n'est pas installé. Impossible d'installer libomp."
        LIBOMP_ERROR=true
    else
        # Tenter d'installer libomp
        if brew install libomp 2>/dev/null; then
            echo "libomp installé avec succès"
            export DYLD_LIBRARY_PATH="/opt/homebrew/opt/libomp/lib:$DYLD_LIBRARY_PATH"

            # Ajouter l'export au .zshrc si pas déjà présent
            if ! grep -q "DYLD_LIBRARY_PATH.*libomp" ~/.zshrc 2>/dev/null; then
                echo 'export DYLD_LIBRARY_PATH="/opt/homebrew/opt/libomp/lib:$DYLD_LIBRARY_PATH"' >> ~/.zshrc
                echo "DYLD_LIBRARY_PATH ajouté au .zshrc"
            fi

            # Vérifier que la bibliothèque est bien présente
            if [ ! -f "/opt/homebrew/opt/libomp/lib/libomp.dylib" ]; then
                echo "Erreur : libomp installé mais bibliothèque introuvable"
                LIBOMP_ERROR=true
            fi
        else
            echo "Erreur lors de l'installation de libomp (permissions insuffisantes ou autre problème)"
            LIBOMP_ERROR=true
        fi
    fi
fi

# Vérifier si uv est installé
if ! command -v uv &> /dev/null; then
    echo "uv n'est pas installé. Installation en cours..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
    export PATH="$HOME/.local/bin:$PATH"
fi

# Vérifier si le dossier ~/panoptic existe
# Demander à l'utilisateur le nom du dossier d'installation (par défaut : panoptic)
read -p "Nom du dossier d'installation (par défaut: panoptic) : " INSTALL_NAME
if [ -z "$INSTALL_NAME" ]; then
    INSTALL_NAME="panoptic"
fi

# Chemin complet du dossier d'installation
INSTALL_DIR="$HOME/$INSTALL_NAME"

# Vérifier si le dossier d'installation existe
if [ ! -d "$INSTALL_DIR" ]; then
    echo "Création du dossier $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
fi

# Se déplacer dans le dossier d'installation
cd "$INSTALL_DIR" || exit

# Choisir la version de Python en fonction des erreurs libomp
if [ "$LIBOMP_ERROR" = true ]; then
    echo "=== Erreur détectée avec libomp ==="
    echo "Utilisation de Python 3.11 avec torch 2.1.0"
    PYTHON_VERSION="3.11"
else
    echo "=== Aucune erreur détectée ==="
    echo "Utilisation de Python 3.13"
    PYTHON_VERSION="3.13"
fi

# Vérifier si l'environnement virtuel existe
if [ ! -d ".venv" ]; then
    echo "Création de l'environnement virtuel Python $PYTHON_VERSION"
    uv venv --python $PYTHON_VERSION

    # Installer torch 2.1.0 si Python 3.11
    if [ "$PYTHON_VERSION" = "3.11" ]; then
        echo "Installation de torch 2.1.0..."
        uv pip install torch==2.1.0
    fi
else
    # Vérifier la version Python de l'env existant
    CURRENT_PYTHON=$(.venv/bin/python --version 2>&1 | grep -oE "[0-9]+\.[0-9]+")
    if [ "$CURRENT_PYTHON" != "$PYTHON_VERSION" ]; then
        echo "Version Python incorrecte ($CURRENT_PYTHON au lieu de $PYTHON_VERSION). Recréation de l'environnement..."
        rm -rf .venv
        uv venv --python $PYTHON_VERSION

        # Installer torch 2.1.0 si Python 3.11
        if [ "$PYTHON_VERSION" = "3.11" ]; then
            echo "Installation de torch 2.1.0..."
            uv pip install torch==2.1.0
        fi
    fi
fi
source .venv/bin/activate
# Installer la dernière version de pip
uv pip install pip

# Vérifier si panoptic est installé
if ! uv pip show panoptic &> /dev/null; then
    echo "Panoptic n'est pas installé. Installation en cours..."
    uv pip install panoptic
else
    echo "Panoptic est installé. Vérification des mises à jour..."
    LATEST_VERSION=$(uvx pip index versions panoptic 2>/dev/null | grep -oE "[0-9]+\.[0-9]+\.[0-9]+" | sort -V | tail -n 1)
    CURRENT_VERSION=$(uv pip show panoptic | grep -i "Version:" | sed -E 's/(.*)Version: (.*)/\2/')
    if [ -n "$LATEST_VERSION" ] && [ "$LATEST_VERSION" != "$CURRENT_VERSION" ]; then
        read -p "Une nouvelle version de Panoptic ($LATEST_VERSION) est disponible. Voulez-vous l'installer ? (y/n) " choice
        if [ "$choice" = "y" ]; then
            uv pip install --upgrade panoptic
        fi
    fi
fi
uv run panoptic plugins add vision

# Lancer Panoptic
uv run panoptic