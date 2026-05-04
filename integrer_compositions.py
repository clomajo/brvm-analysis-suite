import pandas as pd

# Charger le CSV avec un séparateur différent (virgule, mais les tickers sont déjà en colonne unique)
# En fait, le problème est que pandas lit les virgules entre les tickers comme des séparateurs.
# On va lire le fichier ligne par ligne.

compositions = []

with open('compositions_brvm_officielles.csv', 'r') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        # Séparer la date et le type du reste
        parts = line.split(',')
        date = parts[0]
        type_indice = parts[1]
        # Le reste est la liste des tickers (tout après la 2ème virgule)
        tickers_str = ','.join(parts[2:])
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

print(f"✅ {len(classification_par_date)} périodes chargées")
print(f"   Période : {min(classification_par_date.keys())} → {max(classification_par_date.keys())}")

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
test_tickers = ['SGBC', 'ABJC', 'UNKNOWN', 'ECOC', 'NTLC']
test_date = '2024-06-15'

print("\n📋 Test de classification :")
for ticker in test_tickers:
    tier = get_tier(ticker, test_date, classification_par_date)
    print(f"   {ticker} → {tier}")

# Seuils
seuils = {'prestige': 60, 'liquid': 65, 'illiquid': 72}
print(f"\n🎯 Seuils d'ACHAT :")
for tier, seuil in seuils.items():
    print(f"   {tier} → score ≥ {seuil}")

print("\n✅ Prêt à être intégré")
