import pandas as pd

# Lire le fichier CSV manuellement
compositions = []

with open('compositions_brvm_officielles.csv', 'r') as f:
    lignes = f.readlines()

for line in lignes[1:]:
    line = line.strip()
    if not line:
        continue
    
    premiere_virgule = line.find(',')
    if premiere_virgule == -1:
        continue
    
    date = line[:premiere_virgule]
    reste = line[premiere_virgule + 1:]
    
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

# Créer un dictionnaire pour les classifications
classification_par_date = {}

for _, row in pd.DataFrame(compositions).iterrows():
    date = row['date']
    type_indice = row['type_indice']
    tickers = row['ticker_list']
    
    if date not in classification_par_date:
        classification_par_date[date] = {'prestige': [], 'brvm30': [], 'brvm10': []}
    
    classification_par_date[date][type_indice] = tickers

# PROPAGER LES DONNÉES PRESTIGE DANS LE TEMPS
dates_triees = sorted(classification_par_date.keys())
dernier_prestige = []

for i, date in enumerate(dates_triees):
    if classification_par_date[date]['prestige']:
        dernier_prestige = classification_par_date[date]['prestige']
    else:
        classification_par_date[date]['prestige'] = dernier_prestige

print("Dates disponibles (avec Prestige propagé) :")
for d in dates_triees:
    nb_prestige = len(classification_par_date[d]['prestige'])
    print(f"  {d} : {nb_prestige} tickers Prestige")

# Fonction pour déterminer le tier
def get_tier(ticker, date, classif):
    dates_disponibles = sorted(classif.keys())
    date_classe = None
    for d in dates_disponibles:
        if d <= date:
            date_classe = d
        else:
            break
    
    if date_classe is None:
        return 'illiquid'
    
    c = classif[date_classe]
    if ticker in c['prestige']:
        return 'prestige'
    elif ticker in c['brvm30'] or ticker in c['brvm10']:
        return 'liquid'
    else:
        return 'illiquid'

# Test
test_tickers = ['SGBC', 'ABJC', 'ECOC', 'NTLC']
test_dates = ['2024-01-15', '2024-04-15', '2024-07-15', '2024-10-15']

print("\n📋 Test de classification :")
for test_date in test_dates:
    print(f"\n  Date : {test_date}")
    for ticker in test_tickers:
        tier = get_tier(ticker, test_date, classification_par_date)
        print(f"     {ticker} → {tier}")
