from brvm_classifier import BRVMClassifier
from datetime import datetime

classifier = BRVMClassifier()
date_jour = datetime.now().strftime('%Y-%m-%d')

# Liste de tous les tickers BRVM (basée sur tes données)
tickers = ['SGBC', 'SIBC', 'ORAC', 'NTLC', 'ECOC', 'ONTBF', 'PALC', 
           'SMBC', 'SNTS', 'SPHC', 'TTLC', 'TTLS', 'ABJC', 'BOAC', 
           'CFAC', 'CIEC', 'BOAB', 'BOAM', 'BOAN', 'BOAS', 'CABC', 
           'ETIT', 'FTSC', 'NEIC', 'NSBC', 'PRSC', 'SAFC', 'SDCC', 
           'SEMC', 'SHEC', 'SICC', 'SIVC', 'SOGC', 'STAC', 'STBC', 
           'UNLC', 'UNXC', 'BNBC', 'BICB', 'BICC', 'LNBB', 'SCRC']

print(f"Classification officielle BRVM au {date_jour}")
print("=" * 60)

prestige = []
liquid = []
illiquid = []

for ticker in tickers:
    tier = classifier.get_tier(ticker, date_jour)
    if tier == 'prestige':
        prestige.append(ticker)
    elif tier == 'liquid':
        liquid.append(ticker)
    else:
        illiquid.append(ticker)

print(f"\n👑 PRESTIGE (seuil 60) : {len(prestige)} sociétés")
if prestige:
    print(f"   {', '.join(prestige)}")
else:
    print("   Aucune")

print(f"\n💧 LIQUIDE BRVM 30 (seuil 65) : {len(liquid)} sociétés")
if liquid:
    print(f"   {', '.join(liquid)}")
else:
    print("   Aucune")

print(f"\n⚠️ ILLIQUIDE (pas de signal ACHAT) : {len(illiquid)} sociétés")
if illiquid:
    print(f"   {', '.join(illiquid)}")

print("\n" + "=" * 60)
print("✅ Module de classification prêt pour la production")
