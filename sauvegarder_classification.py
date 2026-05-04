import pickle
import pandas as pd

print("📁 Lecture du fichier CSV...")

# Lire le fichier CSV manuellement
compositions = []

with open('compositions_brvm_officielles.csv', 'r') as f:
    lignes = f.readlines()

# Ignorer l'en-tête
for line in lignes[1:]:
    line = line.strip()
    if not line:
        continue
    
    # Trouver la première virgule (sépare date)
    premiere_virgule = line.find(',')
    if premiere_virgule == -1:
        continue
    
    date = line[:premiere_virgule]
    reste = line[premiere_virgule + 1:]
    
    # Trouver la deuxième virgule (sépare type_indice)
    deuxieme_virgule = reste.find(',')
    if deuxieme_virgule == -1:
        continue
    
    type_indice = reste[:deuxieme_virgule]
    tickers_str = reste[deuxieme_virgule + 1:]
    tickers = tickers_str.split(',')
    
    compositions.append({
        'date': date,
        'type_indice': type_indice,
        'ticker_list': tickers
    })

print(f"   {len(compositions)} entrées lues")

# Construire le dictionnaire de classification
classification_par_date = {}

for row in compositions:
    date = row['date']
    type_indice = row['type_indice']
    tickers = row['ticker_list']
    
    if date not in classification_par_date:
        classification_par_date[date] = {'prestige': [], 'brvm30': [], 'brvm10': []}
    
    classification_par_date[date][type_indice] = tickers

print(f"   {len(classification_par_date)} dates uniques avant propagation")

# Propager les données Prestige dans le temps
dates_triees = sorted(classification_par_date.keys())
dernier_prestige = []

for date in dates_triees:
    if classification_par_date[date]['prestige']:
        dernier_prestige = classification_par_date[date]['prestige']
    else:
        classification_par_date[date]['prestige'] = dernier_prestige

print(f"   {len(classification_par_date)} dates après propagation")

# Sauvegarder
with open('classification_officielle.pkl', 'wb') as f:
    pickle.dump(classification_par_date, f)

print(f"\n✅ Classification sauvegardée dans classification_officielle.pkl")
print(f"   Période : {min(classification_par_date.keys())} → {max(classification_par_date.keys())}")
print(f"   Nombre de périodes : {len(classification_par_date)}")
