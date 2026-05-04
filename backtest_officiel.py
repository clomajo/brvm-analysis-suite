import pandas as pd
import numpy as np
import openpyxl
from datetime import datetime

print("=" * 70)
print("BACKTEST AVEC CLASSIFICATIONS OFFICIELLES BRVM")
print("=" * 70)

# 1. Charger les compositions officielles
print("\n📁 Chargement des compositions officielles...")

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

# 2. Fonction pour obtenir le tier
seuils = {'prestige': 60, 'liquid': 65, 'illiquid': 72}

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

# 3. Charger les données de backtest
print("\n📁 Chargement des données de backtest...")
df = pd.read_pickle('backtest_v4.pkl')
print(f"   {len(df)} lignes chargées")

# 4. Ajouter la classification officielle pour chaque ligne
print("\n🏷️ Application des classifications officielles...")
df['trade_date_str'] = df['trade_date'].dt.strftime('%Y-%m-%d')
df['tier_officiel'] = df.apply(
    lambda row: get_tier(row['symbol'], row['trade_date_str'], classification_par_date),
    axis=1
)
df['seuil_achat_officiel'] = df['tier_officiel'].map(seuils)

# 5. Comparer avec l'ancienne méthode
print("\n📊 Comparaison des classifications :")
print(f"   Ancienne méthode (vol_avg20 >= 1277) : {df['is_liquid'].sum():,} liquid")
print(f"   Nouvelle méthode (BRVM officiel)     : {(df['tier_officiel'] != 'illiquid').sum():,} liquid/prestige")

# 6. Filtrer les signaux ACHAT avec la nouvelle classification
hc_officiel = df[
    (df['signal_v2'] == 'ACHAT') &
    (df['confidence'] >= 70) &
    (df['tier_officiel'] != 'illiquid')  # On garde prestige et liquid
].copy()

print(f"\n📈 Signaux ACHAT haut-conviction (officiel) : {len(hc_officiel):,}")

# 7. Calculer les performances par tier
print("\n📊 Performances par tier :")
for tier in ['prestige', 'liquid']:
    df_tier = hc_officiel[hc_officiel['tier_officiel'] == tier]
    if len(df_tier) > 0:
        pct_pos = (df_tier['eop_return_90'] > 0).mean() * 100
        print(f"   {tier} (seuil={seuils[tier]}) : {len(df_tier):,} signaux, {pct_pos:.1f}% positifs")

# 8. Résumé final
print("\n" + "=" * 70)
print("RÉSUMÉ DES SEUILS D'ACHAT")
print("=" * 70)
print(f"   Prestige (BRVM Prestige) → score ≥ {seuils['prestige']}")
print(f"   Liquid (BRVM 30)         → score ≥ {seuils['liquid']}")
print(f"   Illiquid (hors indices)   → score ≥ {seuils['illiquid']} (non utilisé pour ACHAT)")

print("\n✅ Backtest avec classifications officielles prêt")
