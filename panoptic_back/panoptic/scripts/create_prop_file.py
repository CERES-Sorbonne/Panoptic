import os
import random

import pandas as pd

# Chemin vers le dossier contenant les images
dossier_images = r"D:\Alie\Documents\CollectesTwitter\AhashExps\small"

# Liste des noms de fichiers d'images
noms_images = os.listdir(dossier_images)

# Initialisation des listes pour les colonnes du dataframe
keys = []
descriptions = []
likes = []

# Parcourir chaque nom de fichier
for nom_image in noms_images:
    # Générer un nombre aléatoire entre 1 et 10 pour le nombre de fois où le nom sera ajouté dans la colonne "key"
    nb_ajouts = random.randint(1, 10)
    
    for _ in range(nb_ajouts):
        # Ajouter le nom du fichier dans la liste "keys"
        keys.append(nom_image)
        
        # Générer un texte français aléatoire avec un entier variable
        texte_aleatoire = "Texte français aléatoire {}".format(random.randint(1, 100))
        
        # Ajouter le texte aléatoire dans la liste "descriptions"
        descriptions.append(texte_aleatoire)
        
        # Générer un nombre aléatoire entre 1 et 1500 pour la colonne "likes"
        nb_likes = random.randint(1, 1500)
        
        # Ajouter le nombre aléatoire dans la liste "likes"
        likes.append(nb_likes)

# Créer le dataframe
df = pd.DataFrame({"key": keys, "description[string]": descriptions, "likes[number]": likes})

# Sauvegarder le dataframe dans un fichier CSV
df.to_csv("prop_file.csv", sep=";", index=False)
