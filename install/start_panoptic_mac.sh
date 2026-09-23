#!/bin/bash

# --- CONFIGURATION ---
CONFIG_DIR="$HOME/.config"
CONFIG_FILE="$CONFIG_DIR/.panoptic_config"
set +e

# --- FONCTIONS ---
save_path() {
    mkdir -p "$CONFIG_DIR"
    echo "$1" > "$CONFIG_FILE"
}

# --- NETTOYAGE DES ANCIENNES INSTALLATIONS ---
# Les versions precedentes de ce script ajoutaient le libomp de Homebrew a
# DYLD_LIBRARY_PATH dans ~/.zshrc. Ce n'est plus necessaire (panopticml charge torch
# avant faiss) et ca remplacerait le libomp embarque par torch : on retire la ligne.
if [ -f ~/.zshrc ] && grep -q 'DYLD_LIBRARY_PATH="/opt/homebrew/opt/libomp/lib' ~/.zshrc; then
    sed -i '' '/DYLD_LIBRARY_PATH="\/opt\/homebrew\/opt\/libomp\/lib/d' ~/.zshrc
fi

# --- INSTALLATION DE UV ---
if ! command -v uv &> /dev/null; then
    echo "Installation de uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# --- GESTION DU CHEMIN D'INSTALLATION ---
if [ -f "$CONFIG_FILE" ]; then
    INSTALL_DIR=$(cat "$CONFIG_FILE")
    if [ ! -d "$INSTALL_DIR" ]; then
        echo "Dossier d'installation introuvable : $INSTALL_DIR"
        echo "Reinitialisation de la configuration..."
        rm -f "$CONFIG_FILE"
        INSTALL_DIR=""
    else
        echo "Installation existante detectee dans : $INSTALL_DIR"
    fi
fi

if [ -z "$INSTALL_DIR" ]; then
    echo "--- Premiere installation ---"
    read -p "Nom ou chemin du dossier d'installation (par defaut: $HOME/panoptic) : " USER_INPUT

    if [ -z "$USER_INPUT" ]; then
        INSTALL_DIR="$HOME/panoptic"
    elif [[ "$USER_INPUT" = /* ]]; then
        INSTALL_DIR="$USER_INPUT"
    else
        INSTALL_DIR="$HOME/$USER_INPUT"
    fi

    mkdir -p "$INSTALL_DIR"
    save_path "$INSTALL_DIR"
    echo "Chemin sauvegarde dans $CONFIG_FILE"
fi

# --- GESTION DE L'ENVIRONNEMENT PYTHON ---
PYTHON_VERSION="3.13"

# Recree aussi les anciens venv Python 3.11 (torch 2.1, trop vieux pour panopticml)
if [ ! -d ".venv" ] || [ "$(.venv/bin/python --version 2>&1 | grep -oE "[0-9]+\.[0-9]+")" != "$PYTHON_VERSION" ]; then
    echo "Configuration de l'environnement Python $PYTHON_VERSION..."
    rm -rf .venv
    uv python install $PYTHON_VERSION
    uv venv --python $PYTHON_VERSION
fi

uv pip install -U pip

# --- INSTALLATION / MISE A JOUR PANOPTIC ---
if ! uv pip show panoptic &> /dev/null; then
    echo "Installation de Panoptic..."
    # PANOPTIC_PACKAGE permet de surcharger la source (ex. checkout local en CI).
    uv pip install "${PANOPTIC_PACKAGE:-panoptic}"
    # PANOPTICML_PACKAGE permet d'installer une autre source de panopticml (ex. une branche git en CI).
    [ -n "$PANOPTICML_PACKAGE" ] && uv pip install "$PANOPTICML_PACKAGE"
    uv run .venv/bin/panoptic plugins add vision

    # --- OPTION TELECHARGEMENT MODELE ---
    echo "-------------------------------------------------------"
    read -p "Voulez-vous telecharger le modele CLIP (openai/clip-vit-base-patch32) maintenant ? (y/n) : " DOWNLOAD_CLIP
    if [[ "$DOWNLOAD_CLIP" =~ ^[Yy]$ ]]; then
        echo "Telechargement du modele..."
        uvx --from huggingface_hub hf download openai/clip-vit-base-patch32
    fi
    echo "-------------------------------------------------------"
else
    echo "Panoptic est deja installe. Verification des mises a jour..."
    uv pip install --upgrade panoptic
fi

# --- LANCEMENT ---
echo "Lancement de Panoptic..."
# En CI/test (PANOPTIC_INSTALL_TEST=1), on vérifie l'installation sans démarrer le serveur.
if [ "$PANOPTIC_INSTALL_TEST" = "1" ]; then
    uv run .venv/bin/panoptic --dry
else
    uv run .venv/bin/panoptic
fi
