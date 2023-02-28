import sqlite3

# Connexion à la base de données SQLite
conn = sqlite3.connect('database.db')


# Fonction utilitaire pour exécuter une requête SQL et commettre les modifications
def execute_query(query: str, parameters: tuple = None):
    cursor = conn.cursor()
    if parameters:
        cursor.execute(query, parameters)
    else:
        cursor.execute(query)
    conn.commit()
    return cursor


# Fonction utilitaire pour créer une metadata
def create_metadata(metadata):
    query = """
        INSERT INTO metadata (id, nom, type, hierarchical)
        VALUES (?, ?, ?, ?)
    """
    execute_query(query, (metadata["id"], metadata["nom"], metadata["type"], metadata["hierarchical"]))