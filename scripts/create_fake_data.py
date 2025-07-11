import csv
import random

input_file = "data.csv"
output_file = "data_big.csv"
nb_duplicates = 500  # Nombre de lignes générées par path
nb_cols = 20

# Générateurs de texte arbitraire
def generer_commentaire():
    exemples = [
        "Analyse en cours",
        "Objet mystérieux",
        "Interprétation en débat",
        "Icône d'une culture oubliée",
        "Ajout récent à la base"
    ]
    return random.choice(exemples)


def generer_auteur():
    noms = ["Dr. Martin", "Équipe CNRS", "Jean Dupont", "Historien inconnu", "ClioLab"]
    return random.choice(noms)


# Lecture du fichier CSV d'entrée
with open(input_file, newline='', encoding='utf-8') as infile, \
        open(output_file, 'w', newline='', encoding='utf-8') as outfile:
    reader = csv.DictReader(infile, delimiter=';')
    fieldnames = reader.fieldnames + ["commentaire[text]", "auteur[tag]", "auteurs[multi_tags]"] + [f"description{i}[text]" for i in range(nb_cols)]
    writer = csv.DictWriter(outfile, fieldnames=fieldnames, delimiter=';')

    writer.writeheader()

    for row in reader:
        for _ in range(nb_duplicates):
            nouvelle_ligne = row.copy()
            nouvelle_ligne["commentaire[text]"] = generer_commentaire()
            nouvelle_ligne["auteur[tag]"] = generer_auteur()
            nouvelle_ligne["auteurs[multi_tags]"] = ",".join([generer_auteur() for i in range(3)])
            for i in range(nb_cols):
                key = f"description{i}[text]"
                nouvelle_ligne[key] = "Lorem ipsum sic dolor amet et turpido et siquitur del alma possibile"
            writer.writerow(nouvelle_ligne)
