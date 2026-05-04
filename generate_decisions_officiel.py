import pandas as pd
from datetime import datetime
from brvm_classifier import BRVMClassifier

# Initialiser le classifier
classifier = BRVMClassifier()
date_jour = datetime.now().strftime('%Y-%m-%d')

print(f"📊 Génération des signaux BRVM - {date_jour}")
print("=" * 60)

# Charger tes données du jour (exemple)
# df = pd.read_csv('prix_du_jour.csv')
# Ou calculer tes scores techniques

# Exemple de données factices pour la démonstration
data = {
    'ticker': ['SGBC', 'ABJC', 'BNBC', 'ORAC', 'UNKNOWN'],
    'score': [62, 64, 75, 58, 70],
    'price': [34500, 1605, 5200, 15000, 1000]
}
df = pd.DataFrame(data)

print("\n📈 Résultats :")
print("-" * 60)

for _, row in df.iterrows():
    ticker = row['ticker']
    score = row['score']
    prix = row['price']
    
    tier = classifier.get_tier(ticker, date_jour)
    seuil = classifier.get_seuil_achat(ticker, date_jour)
    
    if tier == 'illiquid':
        signal = 'AVOID'
        raison = f"Peu liquide (hors indices officiels)"
    else:
        if score >= seuil:
            signal = 'ACHAT'
            raison = f"Score {score} ≥ seuil {seuil}"
        else:
            signal = 'WATCH'
            raison = f"Score {score} < seuil {seuil}"
    
    print(f"{ticker:6} | {signal:6} | {tier:8} | {raison}")

print("\n" + "=" * 60)
print("✅ Signaux générés avec classification officielle BRVM")
