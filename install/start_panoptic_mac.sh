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

# --- PRE-REQUIS : XCODE & LIBOMP ---
if ! xcode-select -p &> /dev/null; then
    echo "Installation des outils de developpement Xcode requis..."
    xcode-select --install
    read -p "Appuyez sur Entree une fois l'installation des outils Xcode terminee..."
fi

LIBOMP_ERROR=false
if [ -f "/opt/homebrew/opt/libomp/lib/libomp.dylib" ]; then
    echo "libomp est deja installe"
    export DYLD_LIBRARY_PATH="/opt/homebrew/opt/libomp/lib:$DYLD_LIBRARY_PATH"
else
    if ! command -v brew &> /dev/null; then
        echo "Homebrew n'est pas installe. Impossible d'installer libomp."
        LIBOMP_ERROR=true
    else
        echo "Tentative d'installation de libomp via Homebrew..."
        if brew install libomp 2>/dev/null; then
            export DYLD_LIBRARY_PATH="/opt/homebrew/opt/libomp/lib:$DYLD_LIBRARY_PATH"
            [[ ! $(grep "DYLD_LIBRARY_PATH.*libomp" ~/.zshrc) ]] && echo 'export DYLD_LIBRARY_PATH="/opt/homebrew/opt/libomp/lib:$DYLD_LIBRARY_PATH"' >> ~/.zshrc
        else
            LIBOMP_ERROR=true
        fi
    fi
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
PYTHON_VERSION=$([ "$LIBOMP_ERROR" = true ] && echo "3.11" || echo "3.13")

if [ ! -d ".venv" ] || [ "$(.venv/bin/python --version 2>&1 | grep -oE "[0-9]+\.[0-9]+")" != "$PYTHON_VERSION" ]; then
    echo "Configuration de l'environnement Python $PYTHON_VERSION..."
    rm -rf .venv
    uv python install $PYTHON_VERSION
    uv venv --python $PYTHON_VERSION
    [ "$PYTHON_VERSION" = "3.11" ] && uv pip install torch==2.1.0 numpy==1.25.2
fi

uv pip install -U pip

# --- INSTALLATION / MISE A JOUR PANOPTIC ---
if ! uv pip show panoptic &> /dev/null; then
    echo "Installation de Panoptic..."
    uv pip install panoptic
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
uv run .venv/bin/panoptic
