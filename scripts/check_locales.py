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


def get_missing_text_keys(fr_data, en_data, prefix=""):
    """Trouve les clés textuelles présentes dans fr.json mais absentes de en.json."""
    missing_text_keys = {}
    for key, fr_value in fr_data.items():
        current_key_path = f"{prefix}.{key}" if prefix else key
        en_value = en_data.get(key)

        # Si la clé est un sous-dictionnaire, on descend récursivement
        if isinstance(fr_value, dict):
            # Descend dans les sous-dictionnaires
            if isinstance(en_value, dict):
                missing_text_keys.update(get_missing_text_keys(fr_value, en_value, current_key_path))
            else:
                missing_text_keys.update(get_missing_text_keys(fr_value, {}, current_key_path))

        # Si la valeur est textuelle et n'existe pas dans en.json, on l'ajoute
        elif isinstance(fr_value, str) and en_value is None:
            missing_text_keys[current_key_path] = fr_value

    return missing_text_keys


def set_nested_value(data, key_path, value):
    """Modifie ou ajoute la valeur d'une clé imbriquée dans le dictionnaire."""
    keys = key_path.split('.')
    for key in keys[:-1]:
        data = data.setdefault(key, {})
    data[keys[-1]] = value


# Charger les fichiers JSON
en_data = load_json(path_en)
fr_data = load_json(path_fr)

# Obtenir les clés textuelles manquantes dans en.json
missing_text_keys = get_missing_text_keys(fr_data, en_data)

if not missing_text_keys:
    print("Toutes les clés de texte de fr.json sont déjà présentes dans en.json.")
else:
    for key_path, fr_value in missing_text_keys.items():
        print(f"Clé manquante : {key_path}")
        print(f"Valeur dans fr.json : {fr_value}")

        # Demander à l'utilisateur la valeur pour en.json
        en_value = input("Entrez la traduction pour en.json : ")

        # Ajouter la nouvelle valeur à en_data
        set_nested_value(en_data, key_path, en_value)

    # Sauvegarder les modifications dans en.json
    save_json(path_en, en_data)
    print("Les traductions manquantes ont été ajoutées à en.json.")
