"""
verify_decisions.py
-------------------
Vérifie les signaux BRVM à 90 jours et upsert dans brvm_decisions_results.
À lancer quotidiennement via GitHub Actions (après generate_decisions.py).

Variables d'environnement requises :
  SUPABASE_URL
  SUPABASE_KEY (service_role)
"""

import os
from datetime import date, timedelta
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

VERIFICATION_WINDOW = 90  # jours


def get_price_at_date(company_id: int, target_date: date):
    """
    Récupère le prix le plus proche de target_date pour un company_id.
    Fenêtre ±5 jours pour couvrir weekends et jours fériés BRVM.
    """
    date_from = (target_date - timedelta(days=5)).isoformat()
    date_to   = (target_date + timedelta(days=5)).isoformat()

    resp = (
        supabase.table("historical_data")
        .select("trade_date, price")
        .eq("company_id", company_id)
        .gte("trade_date", date_from)
        .lte("trade_date", date_to)
        .order("trade_date", desc=False)
        .execute()
    )
    if not resp.data:
        return None

    closest = min(
        resp.data,
        key=lambda x: abs((date.fromisoformat(x["trade_date"]) - target_date).days)
    )
    return closest["price"]


def resolve_company_id(ticker: str):
    """Résout company_id depuis le symbole (table companies.symbol)."""
    co = supabase.table("companies").select("id").eq("symbol", ticker).execute()
    if not co.data:
        return None
    return co.data[0]["id"]


def verify_decisions():
    today  = date.today()
    cutoff = today - timedelta(days=VERIFICATION_WINDOW)

    print(f"📅 Vérification des décisions du {cutoff} (J-{VERIFICATION_WINDOW})")
    print(f"   Date de vérification : {today}")
    print("=" * 55)

    # 1. Récupérer les décisions à vérifier
    resp = (
        supabase.table("brvm_decisions")
        .select("id, ticker, signal, score, date, upside_target, downside_target")
        .eq("date", cutoff.isoformat())
        .execute()
    )
    decisions = resp.data

    if not decisions:
        print(f"  ⚠️  Aucune décision trouvée pour le {cutoff}")
        print("  → Essai sur les 5 jours précédents...")
        # Fallback : chercher la date la plus proche avec des décisions
        for delta in range(1, 6):
            fallback_date = cutoff - timedelta(days=delta)
            resp2 = (
                supabase.table("brvm_decisions")
                .select("id, ticker, signal, score, date, upside_target, downside_target")
                .eq("date", fallback_date.isoformat())
                .execute()
            )
            if resp2.data:
                decisions = resp2.data
                print(f"  → Décisions trouvées pour le {fallback_date}")
                break

    if not decisions:
        print("  ❌ Aucune décision à vérifier. Script terminé.")
        return

    print(f"  {len(decisions)} décisions à vérifier\n")

    # Cache company_id pour éviter les requêtes répétées
    company_cache = {}
    results = []

    for d in decisions:
        ticker      = d["ticker"]
        signal      = d["signal"]
        signal_date = date.fromisoformat(d["date"])
        decision_id = d["id"]

        # Résoudre company_id
        if ticker not in company_cache:
            company_cache[ticker] = resolve_company_id(ticker)
        company_id = company_cache[ticker]

        if not company_id:
            print(f"  ⚠️  {ticker} : company_id introuvable — ignoré")
            continue

        # 2. Prix au moment du signal
        prix_signal = get_price_at_date(company_id, signal_date)
        if not prix_signal:
            print(f"  ⚠️  {ticker} : prix signal ({signal_date}) introuvable — ignoré")
            continue

        # 3. Prix à la date de vérification
        prix_verification = get_price_at_date(company_id, today)
        if not prix_verification:
            print(f"  ⚠️  {ticker} : prix vérification ({today}) introuvable — ignoré")
            continue

        # 4. Variation
        variation_pct = round(
            (prix_verification - prix_signal) / prix_signal * 100, 2
        )

        # 5. Signal correct ?
        if signal in ("BUY", "ACHAT", "ACHETER"):
            signal_correct = variation_pct > 0
        elif signal in ("SELL", "VENTE", "VENDRE", "ÉVITER"):
            signal_correct = variation_pct < 0
        else:  # HOLD / CONSERVER / NEUTRE
            signal_correct = abs(variation_pct) < 5

        results.append({
            "decision_id"      : decision_id,
            "ticker"           : ticker,
            "signal"           : signal,
            "score"            : d["score"],
            "signal_date"      : signal_date.isoformat(),
            "verification_date": today.isoformat(),
            "prix_signal"      : float(prix_signal),
            "prix_verification": float(prix_verification),
            "variation_pct"    : variation_pct,
            "signal_correct"   : signal_correct,
        })

        status = "✅" if signal_correct else "❌"
        print(f"  {status} {ticker:<8} | {signal:<10} | {variation_pct:+6.1f}% "
              f"| {prix_signal:.0f} → {prix_verification:.0f} FCFA")

    # 6. Upsert dans brvm_decisions_results
    if results:
        supabase.table("brvm_decisions_results").upsert(
            results,
            on_conflict="decision_id"
        ).execute()
        print(f"\n✅ {len(results)} résultats upsertés dans brvm_decisions_results")
    else:
        print("\n⚠️  Aucun résultat à upserter.")
        return

    # 7. Résumé hit rate du jour
    correct = sum(1 for r in results if r["signal_correct"])
    total   = len(results)
    print(f"\n📊 Hit rate J-{VERIFICATION_WINDOW} : {correct}/{total} = {correct/total*100:.1f}%")

    # 8. Résumé global cumulé
    all_results = supabase.table("brvm_decisions_results").select("signal_correct").execute()
    if all_results.data:
        total_global   = len(all_results.data)
        correct_global = sum(1 for r in all_results.data if r["signal_correct"])
        print(f"📈 Hit rate global cumulé : {correct_global}/{total_global} = {correct_global/total_global*100:.1f}%")


if __name__ == "__main__":
    verify_decisions()
