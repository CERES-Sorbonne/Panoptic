import os
import random
from datetime import datetime, timedelta
import csv
import numpy as np

# Fonction pour générer une date bimodale
def generate_bimodal_date(start_date, end_date, peak1, peak2, spread):
    # Randomly choose between the two peaks
    if random.random() < 0.5:
        peak = peak1
    else:
        peak = peak2
    
    # Generate a date around the chosen peak
    days_diff = int(np.random.normal(loc=0, scale=spread))
    random_date = peak + timedelta(days=days_diff)
    
    # Ensure the date is within the range
    if random_date < start_date:
        random_date = start_date
    elif random_date > end_date:
        random_date = end_date
    
    return random_date

# Configuration
input_folder = "D:\CorpusImage\sous_corpus_gallica"
output_csv = "D:\CorpusImage\sous_corpus_gallica.csv"
start_date = datetime(2024, 1, 1)
end_date = datetime(2024, 6, 10)
peak1 = datetime(2024, 2, 15)  # Example peak dates
peak2 = datetime(2024, 5, 1)
spread = 10  # Example spread (standard deviation in days)

# Get list of images
images = [f for f in os.listdir(input_folder) if os.path.isfile(os.path.join(input_folder, f))]

# Open CSV file for writing
with open(output_csv, mode='w', newline='') as file:
    writer = csv.writer(file, delimiter=';')
    writer.writerow(["path", "date[date]", "categorie[tag]"])

    for image in images:
        # Generate random date with bimodal distribution
        random_date = generate_bimodal_date(start_date, end_date, peak1, peak2, spread)
        formatted_date = random_date.strftime("%d/%m/%Y")
        
        # Randomly choose a category
        category = random.choice(["categorie1", "categorie2", "categorie3"])
        
        # Write to CSV
        writer.writerow([os.path.join(input_folder, image), f"{formatted_date}", f"{category}"])

print("CSV file has been created successfully.")
