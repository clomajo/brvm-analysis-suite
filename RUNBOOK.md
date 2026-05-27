# Runbook — BRVM Analytics

Procédures opérationnelles pour diagnostiquer et résoudre les problèmes courants.

---

## 1. Pipeline GitHub Actions

### Vérifier le statut du pipeline
```
https://github.com/clomajo/brvm-analysis-suite/actions
```
Le pipeline tourne automatiquement chaque jour de bourse (lundi-vendredi).

### Lancer manuellement
```bash
# Via GitHub UI : Actions → brvm-analysis → Run workflow
# Ou via CLI (si gh installé) :
gh workflow run brvm-analysis.yml
```

### Interpréter les codes de sortie
| Code | Signification |
|---|---|
| 0 | Succès ou avertissements non bloquants |
| 2 | Erreur critique — pipeline arrêté |
| Autre | Erreur inattendue |

---

## 2. Diagnostics courants

### Moins de 47 tickers fetchés aujourd'hui (T1)
```bash
# Vérifier dans Supabase
SELECT COUNT(DISTINCT company_id)
FROM historical_data
WHERE trade_date = CURRENT_DATE;

# Si < 47, vérifier les logs GitHub Actions ÉTAPE 1
# Cause probable : brvm.org down ou structure HTML changée
```

### Anomalie de prix >40% détectée (T4)
```bash
# Identifier le ticker et la date
SELECT c.symbol, h.trade_date, prev.price as prev_price, h.price,
    ROUND(((h.price - prev.price) / prev.price) * 100, 2) as pct_change
FROM historical_data h
JOIN companies c ON h.company_id = c.id
JOIN LATERAL (
    SELECT price FROM historical_data
    WHERE company_id = h.company_id AND trade_date < h.trade_date
    ORDER BY trade_date DESC LIMIT 1
) prev ON true
WHERE ABS((h.price - prev.price) / prev.price) > 0.40
  AND h.trade_date >= CURRENT_DATE - INTERVAL '7 days';

# Vérifier sur brvm.org si c'est un vrai split ou une erreur
# Si erreur : corriger manuellement dans historical_data
# Si split : documenter dans CHANGELOG.md et créer ticket DATA-0X
```

### Signal ACHAT en régime BEAR (T6 — règle métier violée)
```bash
# Ne devrait jamais arriver — vérifier generate_decisions.py
SELECT ticker, date, signal, market_regime, score
FROM brvm_decisions
WHERE signal = 'ACHAT' AND market_regime = 'BEAR'
ORDER BY date DESC;

# Corriger immédiatement — supprimer les décisions incorrectes
DELETE FROM brvm_decisions
WHERE signal = 'ACHAT' AND market_regime = 'BEAR';
```

### Données stales (T8) — ticker non mis à jour depuis >3 jours
```bash
SELECT c.symbol, MAX(h.trade_date) as derniere_date,
    CURRENT_DATE - MAX(h.trade_date) as jours_retard
FROM historical_data h
JOIN companies c ON h.company_id = c.id
GROUP BY c.symbol
HAVING MAX(h.trade_date) < CURRENT_DATE - INTERVAL '3 days'
ORDER BY jours_retard DESC;

# Cause probable : ticker absent de brvm.org ce jour-là (pas de transaction)
# ou changement de symbole BRVM
```

### Dérive du modèle détectée (T11b)
```bash
# Comparer distribution des scores sur 30 jours
SELECT date,
    AVG(score) as avg_score,
    MIN(score) as min_score,
    MAX(score) as max_score,
    COUNT(*) as nb_decisions
FROM brvm_decisions
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY date
ORDER BY date DESC;

# Si dérive > 15 points sur moyenne → investiguer generate_decisions.py
```

---

## 3. Procédures de maintenance

### Déployer un fix frontend (brvm-analytics)
```bash
cd ~/Desktop/brvm-analytics
# Faire les modifications via Python patch (JAMAIS télécharger App.jsx)
npm run build          # Vérifier que le build passe
git add src/App.jsx
git commit -m "fix: description du fix"
git push               # Vercel déploie automatiquement en ~60 secondes
# Vérifier sur brvm-analytics.vercel.app après hard refresh (Cmd+Shift+R)
```

### Déployer un fix pipeline (brvm-analysis-suite)
```bash
cd ~/Desktop/brvm-analysis-suite
source brvm_env/bin/activate
# Tester localement d'abord
python data_collector_simple.py  # ou le script concerné
python test_pipeline.py          # Vérifier que tous les tests passent
git add fichier_modifie.py
git commit -m "fix: description du fix"
git push
```

### Corriger une anomalie de prix dans historical_data
```sql
-- Identifier l'entrée incorrecte
SELECT id, trade_date, price, volume
FROM historical_data
WHERE company_id = (SELECT id FROM companies WHERE symbol = 'TICKER')
  AND trade_date = '2026-XX-XX';

-- Corriger
UPDATE historical_data
SET price = PRIX_CORRECT
WHERE id = ID_ENREGISTREMENT;

-- Documenter dans CHANGELOG.md
```

---

## 4. Calendrier BRVM

| Événement | Date | Action |
|---|---|---|
| Première vérification live | 01/07/2026 | Analyser brvm_decisions_results |
| Dégel du modèle | 01/07/2026 | Activer chantiers FUND-01, DATA-05/06 |
| AG BOAC | 15/04/2026 | Surveiller annonce dividende FY2025 |
| AG ONTBF | 29/04/2026 | Surveiller résultats |
| Checkpoint validation GRU | 16/05/2026 | Dir.Acc J+2=56.1% — baseline établie |
| Checkpoint validation signaux | 16/05/2026 | Hit rate 52.2%/550 signaux — baseline établie |
| Dividende BOABF | 23/04/2026 | 397 FCFA net/action |

---

## 5. Contacts et ressources

| Ressource | URL |
|---|---|
| App production | https://brvm-analytics.vercel.app |
| Supabase dashboard | https://supabase.com/dashboard/project/lynevvhmstpcffobwudr |
| GitHub Actions | https://github.com/clomajo/brvm-analysis-suite/actions |
| BRVM officiel | https://www.brvm.org |
| Sikafinance (validation) | https://www.sikafinance.com |

---

## 6. Diagnostics spécifiques — scrape_boc_pdf.py

### PDF du jour non disponible (jour férié ou publication tardive)
```bash
# Le script tente automatiquement J-1 si J échoue
# Si les deux échouent, vérifier manuellement :
curl -I "https://www.brvm.org/sites/default/files/boc_$(date +%Y%m%d)_2.pdf" --insecure

# Jours fériés BRVM 2026 (pas de bulletin) :
# Jan 1, Mar 17, Mar 20, Avr 6, Mai 1, Mai 14, Mai 25, Mai 27, Aoû 7, Aoû 26, Déc 25
```

### Données aberrantes dans company_fundamentals après scrape
```bash
# Vérifier les rdt_net > 15% (probablement corrompus)
curl -s "$SUPABASE_URL/rest/v1/company_fundamentals?dividend_yield=gt.15&select=ticker,dividend_yield,dividend_per_share,scraped_at&order=scraped_at.desc" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY"

# Filtre sanité actuel : rdt_net > 20% = exclu automatiquement
# FTSC (75.73%) exclu — données bulletin BRVM aberrantes confirmées
```

### pymupdf absent en CI GitHub Actions
```bash
# Symptôme : scrape_boc_pdf.py échoue avec ModuleNotFoundError
# Fix : ajouter pymupdf dans requirements.txt
echo "pymupdf" >> requirements.txt
git add requirements.txt
git commit -m "fix: ajouter pymupdf dans requirements.txt CI"
git push
```

### Calendrier mis à jour — échéances clés

| Événement | Date | Action |
|---|---|---|
| Dégel modèle + vérification V1 | 01/07/2026 | Analyser brvm_decisions_results, déployer V2 |
| Modifier verify_decisions.py | 01/07/2026 | Horizon 90j → J+20 (ADR-019) |
| Activer signal cours cible V2 | 01/07/2026 | cours_cible = dividende / rendement_cible (ADR-017) |
| Convertir liquidité en filtre binaire | 01/07/2026 | Calibrer seuil volume_20j (ADR-018) |
| Ajouter pymupdf requirements.txt | Immédiat | DATA-14 — bloquant CI |
