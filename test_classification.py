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

df_compositions = pd.DataFrame(compositions)

# Créer un dictionnaire pour les classifications
classification_par_date = {}

for _, row in df_compositions.iterrows():
    date = row['date']
    type_indice = row['type_indice']
    tickers = row['ticker_list']
    
    if date not in classification_par_date:
        classification_par_date[date] = {'prestige': [], 'brvm30': [], 'brvm10': []}
    
    classification_par_date[date][type_indice] = tickers

print("Dates disponibles :")
for d in sorted(classification_par_date.keys()):
    print(f"  {d}")

# Fonction pour déterminer le tier
def get_tier(ticker, date, classif):
    dates_disponibles = sorted(classif.keys())
    date_classe = None
    for d in dates_disponibles:
        if d <= date:
            date_classe = d
        else:
            break
    
    print(f"  Pour la date {date}, date retenue : {date_classe}")
    
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
test_date = '2024-06-15'

print(f"\nTest avec date : {test_date}")
for ticker in test_tickers:
    tier = get_tier(ticker, test_date, classification_par_date)
    print(f"   {ticker} → {tier}")
