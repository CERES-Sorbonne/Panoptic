import sqlite3
import sys

def update_paths(db_path, new_root_path):
    # Connexion à la base de données SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Récupération du root_path à remplacer
        cursor.execute("SELECT path FROM folders WHERE id=1")
        old_root_path = cursor.fetchone()[0]
        
        print("old path " + old_root_path)
        # Calcul de la longueur du root_path pour découper les chemins
        old_root_len = len(old_root_path)

        # Mise à jour des chemins en remplaçant le root_path
        cursor.execute("UPDATE folders SET path = ? || substr(path, ?) WHERE path LIKE ?",
                       (new_root_path, old_root_len + 1, old_root_path + "%"))

        cursor.execute("UPDATE instances SET url = ? || substr(url, ?) WHERE url LIKE ?",
                       (new_root_path, old_root_len + 1, old_root_path + "%"))


        conn.commit()
        print("Les chemins ont été mis à jour avec succès.")

    except sqlite3.Error as e:
        print("Erreur lors de la mise à jour des chemins :", e)

    finally:
        # Fermeture de la connexion
        conn.close()

if __name__ == "__main__":
    # Vérification des arguments en ligne de commande
    if len(sys.argv) != 3:
        print("Usage: python script.py chemin_base_de_données nouveau_root_path")
        sys.exit(1)

    db_path = sys.argv[1]
    new_root_path = sys.argv[2]

    # Appel de la fonction pour mettre à jour les chemins
    update_paths(db_path, new_root_path)
