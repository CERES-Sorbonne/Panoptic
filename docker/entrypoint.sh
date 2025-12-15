#!/bin/bash

# Vérifie si UPGRADE_PANOPTIC est défini sur true
if [ "$UPGRADE_PANOPTIC" = "true" ]; then
    echo "Upgrading panoptic"
    pip3 install -U panoptic panopticml
fi

# Lance la commande panoptic
exec panoptic