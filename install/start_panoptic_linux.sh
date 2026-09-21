#!/bin/bash

set -e  # Arrêter le script en cas d'erreur
PYTHON_VERSION=3.13
# Ajouter .local/bin au PATH
LOCAL_BIN="$HOME/.local/bin"
export PATH="$LOCAL_BIN:$PATH"
# Vérifier si uv est disponible, sinon l'installer
if ! command -v uv &> /dev/null; then
    echo "Installation de uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$LOCAL_BIN:$PATH"
fi
# Naviguer dans le dossier utilisateur
cd "$HOME"
# Créer le dossier panoptic s'il n'existe pas
PANOPTIC_DIR="$HOME/panoptic"
mkdir -p "$PANOPTIC_DIR"
cd "$PANOPTIC_DIR"
# Créer l'environnement virtuel avec Python 3.12 s'il n'existe pas
if [ ! -d ".venv" ]; then
    echo "Création de l'environnement virtuel..."
	uv python install $PYTHON_VERSION
    uv venv --python $PYTHON_VERSION
fi
# Installer la dernière version de pip
echo "Installation de pip..."
uv pip install pip
# Vérifier si panoptic est installé, sinon l'installer
if ! uv pip show panoptic &> /dev/null; then
    echo "Installation de panoptic..."
    # PANOPTIC_PACKAGE permet de surcharger la source (ex. checkout local en CI).
    uv pip install "${PANOPTIC_PACKAGE:-panoptic}"
    
    read -p "Si vous possédez une carte graphique NVIDIA vous pouvez également installer une version optimisée mais plus lourde du programme: (O/N) " with_cuda
    with_cuda=$(echo "$with_cuda" | tr '[:upper:]' '[:lower:]')
    
    if [ "$with_cuda" = "o" ]; then
        echo "Installation de torch avec support CUDA..."
        uv pip install torch torchvision --torch-backend=auto
    else
        echo "Installation de torch en mode CPU..."
        uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
    fi
    
    # echo "Installation du plugin de similarité panopticml"
    uv run .venv/bin/panoptic plugins add vision

    read -p "Voulez-vous pré-télécharger le modèle CLIP (recommandé avant de venir à un atelier) ? (O/N) " download_clip
    download_clip=$(echo "$download_clip" | tr '[:upper:]' '[:lower:]')

    if [ "$download_clip" = "o" ]; then
        echo "Téléchargement du modèle CLIP..."
        uvx hf download openai/clip-vit-base-patch32
    fi
fi
# Vérifier si panoptic est obsolète
echo "Vérification des mises à jour..."

OUTDATED=$(uv pip list --outdated)

if echo "$OUTDATED" | grep -q "panoptic"; then
    read -p "Mise à jour trouvée, voulez-vous l'installer ? (O/N) " user_input
    user_input=$(echo "$user_input" | tr '[:upper:]' '[:lower]')
    
    if [ "$user_input" = "o" ]; then
        echo "Mise à jour de panoptic..."
        uv pip install -U panoptic
    fi
else
    echo "La dernière version de panoptic est déjà installée."
fi
echo "Lancement de panoptic..."
# En CI/test (PANOPTIC_INSTALL_TEST=1), on vérifie l'installation sans démarrer le serveur.
if [ "$PANOPTIC_INSTALL_TEST" = "1" ]; then
    uv run .venv/bin/panoptic --dry
else
    uv run .venv/bin/panoptic
fi
