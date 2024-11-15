import json
from deepdiff import DeepDiff
import os

# Définir les chemins des fichiers JSON
path_en = "./panoptic_front/src/locales/en.json"
path_fr = "./panoptic_front/src/locales/fr.json"


def load_json(filepath):
    """Charge le contenu JSON d'un fichier."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(filepath, data):
    """Enregistre le contenu JSON dans un fichier."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def get_missing_keys(fr_data, en_data):
    """Trouve les clés présentes dans fr.json mais absentes de en.json."""
    diff = DeepDiff(en_data, fr_data, ignore_order=True)
    missing_keys = diff.get('dictionary_item_added', [])
    return [key.replace('root[', '').replace('[', '.').replace(']', '').replace("'", "") for key in missing_keys]


def get_nested_value(data, key_path):
    """Récupère la valeur d'une clé imbriquée à partir de son chemin."""
    keys = key_path.split('.')
    for key in keys:
        data = data[key]
    return data


def set_nested_value(data, key_path, value):
    """Modifie ou ajoute la valeur d'une clé imbriquée dans le dictionnaire."""
    keys = key_path.split('.')
    for key in keys[:-1]:
        data = data.setdefault(key, {})
    data[keys[-1]] = value


# Charger les fichiers JSON
en_data = load_json(path_en)
fr_data = load_json(path_fr)

# Obtenir les clés manquantes dans en.json
missing_keys = get_missing_keys(fr_data, en_data)

if not missing_keys:
    print("Toutes les clés de fr.json sont déjà présentes dans en.json.")
else:
    for key_path in missing_keys:
        # Obtenir la valeur dans fr.json pour la clé manquante
        fr_value = get_nested_value(fr_data, key_path)
        print(f"Clé manquante : {key_path}")
        print(f"Valeur dans fr.json : {fr_value}")

        # Demander à l'utilisateur la valeur pour en.json
        en_value = input("Entrez la traduction pour en.json : ")

        # Ajouter la nouvelle valeur à en_data
        set_nested_value(en_data, key_path, en_value)

    # Sauvegarder les modifications dans en.json
    save_json(path_en, en_data)
    print("Les traductions manquantes ont été ajoutées à en.json.")
