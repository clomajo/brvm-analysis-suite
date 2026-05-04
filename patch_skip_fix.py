import re

path = '/Users/kaylam/Desktop/brvm-analysis-suite/generate_decisions.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Chercher le seuil actuel
found = []
for i, line in enumerate(content.split('\n')):
    if 'g_clean' in line and 'len' in line:
        found.append(f"  L{i+1}: {line.rstrip()}")
print("=== Lignes avec g_clean + len ===")
for l in found: print(l)

# 2. Abaisser le seuil
for old in ['if len(g_clean) < 55:', 'if len(g_clean)<55:', 'if len(g_clean) < 55 :']:
    if old in content:
        content = content.replace(old, 'if len(g_clean) < 30:')
        print(f"✅ Seuil trouvé et abaissé : '{old}' → 'if len(g_clean) < 30:'")
        break
else:
    print("❌ Seuil 55 introuvable — vérifier manuellement")

# 3. Remplacer le message skip + ajouter data_completeness
old_skip = 'print(f"  Skipping {symbol} — insufficient data ({len(g_clean)} rows)")\n        continue'
new_skip = 'data_completeness = \'Low\'\n        print(f"  Warning: {symbol} — limited data ({len(g_clean)} rows), data_completeness=Low")'
if old_skip in content:
    content = content.replace(old_skip, new_skip)
    print("✅ Skip remplacé par Warning + data_completeness=Low")
else:
    print("⚠️  Message skip exact non trouvé — cherche variante:")
    for i, line in enumerate(content.split('\n')):
        if 'Skipping' in line or 'insufficient' in line:
            print(f"  L{i+1}: {line.rstrip()}")

# 4. Injecter data_completeness=High au début du bloc ticker
old_tier = '    tier = classifier.get_tier(symbol, date_jour)'
new_tier = '    data_completeness = \'High\' if len(g_clean) >= 55 else \'Medium\'\n    tier = classifier.get_tier(symbol, date_jour)'
if old_tier in content:
    content = content.replace(old_tier, new_tier)
    print("✅ data_completeness High/Medium injecté avant tier")
else:
    print("⚠️  Ligne tier non trouvée")

# 5. Ajouter data_completeness dans le dict de décision
old_sig = "'signal': signal,"
new_sig = "'signal': signal,\n            'data_completeness': data_completeness,"
if old_sig in content:
    content = content.replace(old_sig, new_sig, 1)
    print("✅ data_completeness ajouté au dict décision")
else:
    print("⚠️  Clé 'signal' non trouvée dans dict décision")

# 6. Fallback SMA50 → SMA20 si NaN
old_sma = "    trend_sma50 = (row['price'] - row['sma50']) / row['sma50'] * 100"
new_sma = "    _sma50 = row.get('sma50') if isinstance(row.get('sma50'), float) and row.get('sma50') == row.get('sma50') else None\n    trend_sma50 = (row['price'] - _sma50) / _sma50 * 100 if _sma50 else trend_sma20"
if old_sma in content:
    content = content.replace(old_sma, new_sma)
    print("✅ SMA50 fallback → SMA20 si NaN")
else:
    print("⚠️  Ligne SMA50 non trouvée")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n=== Vérification finale ===")
for i, line in enumerate(content.split('\n')):
    if 'data_completeness' in line or ('g_clean' in line and 'len' in line):
        print(f"  L{i+1}: {line.rstrip()}")
