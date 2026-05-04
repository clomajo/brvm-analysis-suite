import pandas as pd
import numpy as np

# 1. Charger les compositions officielles
print("📁 Chargement des compositions officielles...")

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

classification_par_date = {}
for row in compositions:
    date = row['date']
    type_indice = row['type_indice']
    tickers = row['ticker_list']
    
    if date not in classification_par_date:
        classification_par_date[date] = {'prestige': [], 'brvm30': [], 'brvm10': []}
    
    classification_par_date[date][type_indice] = tickers

# Propager les données Prestige
dates_triees = sorted(classification_par_date.keys())
dernier_prestige = []
for date in dates_triees:
    if classification_par_date[date]['prestige']:
        dernier_prestige = classification_par_date[date]['prestige']
    else:
        classification_par_date[date]['prestige'] = dernier_prestige

print(f"✅ {len(classification_par_date)} périodes chargées")

# 2. Fonction pour obtenir le tier à une date donnée
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

# 3. Charger tes données de backtest (exemple avec un fichier CSV)
# Remplace par ton fichier réel
print("\n📁 Chargement des données de backtest...")

# Si tu as un fichier CSV :
# df = pd.read_csv('ton_fichier_backtest.csv')

# Sinon, on crée un exemple pour tester
df_test = pd.DataFrame({
    'ticker': ['SGBC', 'ABJC', 'UNKNOWN', 'ECOC', 'NTLC'] * 10,
    'trade_date': ['2024-01-15', '2024-04-15', '2024-07-15', '2024-10-15', '2025-01-15'] * 10,
    'score': np.random.randint(50, 80, 50)
})

# 4. Ajouter la colonne tier
df_test['tier'] = df_test.apply(
    lambda row: get_tier(row['ticker'], row['trade_date'], classification_par_date),
    axis=1
)

# 5. Ajouter le seuil d'ACHAT
seuils = {'prestige': 60, 'liquid': 65, 'illiquid': 72}
df_test['seuil_achat'] = df_test['tier'].map(seuils)

# 6. Déterminer si le signal est ACHAT
df_test['signal_officiel'] = df_test['score'] >= df_test['seuil_achat']

print("\n📊 Résultat :")
print(df_test.head(10))

print("\n📈 Répartition par tier :")
print(df_test['tier'].value_counts())

print("\n🎯 Taux de signaux ACHAT par tier :")
for tier in ['prestige', 'liquid', 'illiquid']:
    df_tier = df_test[df_test['tier'] == tier]
    if len(df_tier) > 0:
        pct_achat = df_tier['signal_officiel'].mean() * 100
        print(f"   {tier} : {pct_achat:.1f}% de ACHAT (seuil={seuils[tier]})")

print("\n✅ Prêt à être intégré dans ton backtest complet")
