import os
import sys
import requests
from datetime import date, datetime, timedelta
from collections import Counter
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("FAIL: Variables SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY manquantes")
    sys.exit(2)

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

EXPECTED_TICKERS = 47
MAX_PRICE_CHANGE = 0.40
MAX_DATA_AGE_DAYS = 3

errors = []
warnings = []

def get(endpoint, params=""):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{endpoint}{params}", headers=headers)
    if r.status_code != 200:
        raise Exception(f"API error {r.status_code}: {r.text}")
    return r.json()

def is_trading_day(d):
    """Retourne True si d est un jour ouvré (lundi-vendredi)."""
    return d.weekday() < 5

def last_trading_day():
    """Retourne le dernier jour ouvré (aujourd'hui si ouvré, sinon vendredi)."""
    d = date.today()
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d

today = last_trading_day()
print(f"{'='*60}")
print(f"BRVM Analytics — Tests Qualité Pipeline")
print(f"Date de référence : {today}")
print(f"{'='*60}\n")

# ── TEST 1 : Nombre de tickers uniques fetchés aujourd'hui ────────────────
try:
    data = get("historical_data", f"?trade_date=eq.{today}&select=company_id")
    nb = len(set(d['company_id'] for d in data))
    if nb < EXPECTED_TICKERS:
        errors.append(f"T1: Seulement {nb}/{EXPECTED_TICKERS} tickers uniques fetchés le {today}")
    else:
        print(f"OK   T1: {nb} tickers fetchés le {today}")
except Exception as e:
    errors.append(f"T1: Exception — {e}")

# ── TEST 2 : Aucun prix nul ou négatif ────────────────────────────────────
try:
    data = get("historical_data", f"?trade_date=eq.{today}&price=lte.0&select=company_id,price")
    if data:
        errors.append(f"T2: {len(data)} prix <= 0 détectés le {today}")
    else:
        print(f"OK   T2: Aucun prix nul ou négatif")
except Exception as e:
    errors.append(f"T2: Exception — {e}")

# ── TEST 3 : Doublons (company_id, trade_date) ────────────────────────────
try:
    data = get("historical_data", f"?trade_date=eq.{today}&select=company_id")
    company_ids = [d['company_id'] for d in data]
    dupes = [cid for cid, count in Counter(company_ids).items() if count > 1]
    if dupes:
        errors.append(f"T3: Doublons détectés pour company_ids {dupes} le {today}")
    else:
        print(f"OK   T3: Aucun doublon")
except Exception as e:
    errors.append(f"T3: Exception — {e}")

# ── TEST 4 : Anomalies de prix >40% (splits non ajustés) — 7 derniers jours
try:
    seven_days_ago = (today - timedelta(days=7)).isoformat()
    data = get("historical_data",
        f"?trade_date=gte.{seven_days_ago}&select=company_id,trade_date,price&order=company_id,trade_date.asc")
    
    anomalies = []
    by_company = {}
    for row in data:
        cid = row['company_id']
        if cid not in by_company:
            by_company[cid] = []
        by_company[cid].append(row)
    
    for cid, rows in by_company.items():
        for i in range(1, len(rows)):
            prev_price = rows[i-1]['price']
            curr_price = rows[i]['price']
            if prev_price and prev_price > 0:
                chg = abs((curr_price - prev_price) / prev_price)
                if chg > MAX_PRICE_CHANGE:
                    anomalies.append(
                        f"company_id={cid} {rows[i]['trade_date']}: "
                        f"{prev_price}→{curr_price} ({chg*100:.1f}%)"
                    )
    
    if anomalies:
        errors.append(f"T4: {len(anomalies)} anomalie(s) de prix >40% sur 7 jours:\n    " + "\n    ".join(anomalies))
    else:
        print(f"OK   T4: Aucune anomalie de prix >40% sur 7 jours")
except Exception as e:
    errors.append(f"T4: Exception — {e}")

# ── TEST 5 : Décisions générées aujourd'hui ───────────────────────────────
try:
    data = get("brvm_decisions", f"?date=eq.{today}&select=ticker,signal,score")
    if len(data) < 40:
        warnings.append(f"T5: Seulement {len(data)} décisions générées le {today} (attendu >=40)")
    else:
        print(f"OK   T5: {len(data)} décisions générées")
except Exception as e:
    warnings.append(f"T5: Exception — {e}")

# ── TEST 6 : Aucun signal ACHAT en régime BEAR ────────────────────────────
try:
    data = get("brvm_decisions", f"?signal=eq.ACHAT&market_regime=eq.BEAR&select=ticker,date")
    if data:
        errors.append(f"T6: RÈGLE MÉTIER VIOLÉE — {len(data)} signaux ACHAT en régime BEAR: "
                      f"{[d['ticker'] for d in data[:5]]}")
    else:
        print(f"OK   T6: Aucun ACHAT en régime BEAR")
except Exception as e:
    errors.append(f"T6: Exception — {e}")

# ── TEST 7 : Scores dans [0, 100] ─────────────────────────────────────────
try:
    data = get("brvm_decisions", f"?date=eq.{today}&select=ticker,score")
    bad = [d for d in data if d['score'] is not None and (d['score'] < 0 or d['score'] > 100)]
    if bad:
        errors.append(f"T7: {len(bad)} scores hors [0-100]: {[(d['ticker'], d['score']) for d in bad]}")
    else:
        print(f"OK   T7: Tous les scores dans [0-100]")
except Exception as e:
    errors.append(f"T7: Exception — {e}")

# ── TEST 8 : Fraîcheur des données (requête SQL unique) ───────────────────
try:
    # Calcul du seuil en tenant compte des weekends
    threshold = today - timedelta(days=MAX_DATA_AGE_DAYS)
    data = get("historical_data",
        f"?select=company_id,trade_date&order=company_id,trade_date.desc")
    
    # Trouver la dernière date par company_id
    latest = {}
    for row in data:
        cid = row['company_id']
        if cid not in latest:
            latest[cid] = datetime.strptime(row['trade_date'], '%Y-%m-%d').date()
    
    companies = get("companies", "?select=id,symbol")
    company_map = {c['id']: c['symbol'] for c in companies}
    
    stale = []
    for cid, last_date in latest.items():
        age = (today - last_date).days
        if age > MAX_DATA_AGE_DAYS:
            symbol = company_map.get(cid, f"id={cid}")
            stale.append(f"{symbol} ({age}j)")
    
    if stale:
        warnings.append(f"T8: Données stales (>{MAX_DATA_AGE_DAYS}j): {', '.join(stale)}")
    else:
        print(f"OK   T8: Toutes les données fraîches (<={MAX_DATA_AGE_DAYS}j)")
except Exception as e:
    warnings.append(f"T8: Exception — {e}")

# ── TEST 9 : Variation sur données non consécutives (bug ETIT) ────────────
try:
    companies = get("companies", "?select=id,symbol")
    company_map = {c['id']: c['symbol'] for c in companies}
    
    data = get("historical_data",
        f"?select=company_id,trade_date,price&order=company_id,trade_date.desc")
    
    # Grouper par company_id et prendre les 2 dernières dates
    by_company = {}
    for row in data:
        cid = row['company_id']
        if cid not in by_company:
            by_company[cid] = []
        if len(by_company[cid]) < 2:
            by_company[cid].append(row)
    
    non_consecutive = []
    for cid, rows in by_company.items():
        if len(rows) == 2:
            d1 = datetime.strptime(rows[0]['trade_date'], '%Y-%m-%d').date()
            d2 = datetime.strptime(rows[1]['trade_date'], '%Y-%m-%d').date()
            gap = (d1 - d2).days
            # Plus de 5 jours d'écart = données non consécutives
            if gap > 5:
                symbol = company_map.get(cid, f"id={cid}")
                non_consecutive.append(f"{symbol} (écart {gap}j: {d2}→{d1})")
    
    if non_consecutive:
        warnings.append(f"T9: Variation journalière incorrecte pour {len(non_consecutive)} tickers "
                        f"(données non consécutives): {', '.join(non_consecutive[:5])}")
    else:
        print(f"OK   T9: Variations journalières calculées sur données consécutives")
except Exception as e:
    warnings.append(f"T9: Exception — {e}")

# ── TEST 10 : Signaux sans prix correspondant ─────────────────────────────
try:
    decisions_today = get("brvm_decisions", f"?date=eq.{today}&select=ticker")
    tickers_with_decisions = set(d['ticker'] for d in decisions_today)
    
    companies = get("companies", "?select=id,symbol")
    company_map = {c['symbol']: c['id'] for c in companies}
    
    prices_today = get("historical_data", f"?trade_date=eq.{today}&select=company_id")
    company_ids_with_prices = set(d['company_id'] for d in prices_today)
    
    orphaned = []
    for ticker in tickers_with_decisions:
        cid = company_map.get(ticker)
        if cid and cid not in company_ids_with_prices:
            orphaned.append(ticker)
    
    if orphaned:
        errors.append(f"T10: {len(orphaned)} signaux sans prix correspondant: {orphaned}")
    else:
        print(f"OK   T10: Tous les signaux ont un prix correspondant")
except Exception as e:
    warnings.append(f"T10: Exception — {e}")

# ── RÉSUMÉ FINAL ──────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"RÉSUMÉ: {len(errors)} erreur(s) critique(s), {len(warnings)} avertissement(s)")
print(f"{'='*60}")

if errors:
    print("\n❌ ERREURS CRITIQUES:")
    for e in errors:
        print(f"  • {e}")

if warnings:
    print("\n⚠️  AVERTISSEMENTS:")
    for w in warnings:
        print(f"  • {w}")

if not errors and not warnings:
    print("\n✅ Pipeline sain — tous les tests passent.")

# ── TEST 11b : Détection de dérive du modèle (30 jours) ─────────────────
try:
    last_30 = get("brvm_decisions", "?select=date,score&order=date.desc&limit=1500")
    daily_avg = {}
    for d in last_30:
        day = d["date"]
        if day not in daily_avg:
            daily_avg[day] = []
        if d["score"] is not None:
            daily_avg[day].append(d["score"])
    
    if len(daily_avg) >= 7:
        today_str = str(today)
        today_scores = daily_avg.get(today_str, [])
        historical_scores = [s for day, scores in daily_avg.items() 
                            if day != today_str for s in scores]
        
        if today_scores and historical_scores:
            recent_avg = sum(today_scores) / len(today_scores)
            hist_avg = sum(historical_scores) / len(historical_scores)
            drift = abs(recent_avg - hist_avg)
            if drift > 15:
                warnings.append(f"T11b: Dérive modèle détectée — aujourd'hui {recent_avg:.1f} vs historique {hist_avg:.1f} (écart {drift:.1f})")
            else:
                print(f"OK   T11b: Pas de dérive modèle (aujourd'hui {recent_avg:.1f} vs historique {hist_avg:.1f})")
        else:
            print(f"OK   T11b: Pas assez de données aujourd'hui pour comparer")
    else:
        print(f"OK   T11b: Historique insuffisant ({len(daily_avg)} jours) — test actif à partir de 7 jours")
except Exception as e:
    warnings.append(f"T11b: Exception — {e}")

# Codes de sortie explicites
if errors:
    sys.exit(2)   # Erreurs critiques → bloque le pipeline
elif warnings:
    sys.exit(0)   # Avertissements → pipeline continue mais logge
else:
    sys.exit(0)   # Tout bon
