"""
verify_predictions.py
---------------------
Vérifie les prévisions GRU vs cours réels enregistrés dans historical_data.
Upsert les résultats dans predictions_results.
À lancer quotidiennement via GitHub Actions après prediction_analyzer_v2.py.

Variables d'environnement requises :
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY (ou SUPABASE_KEY)
"""

import os
from datetime import date, timedelta
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_actual_price(company_id: int, target_date: date):
    """
    Récupère le prix réel le plus proche de target_date.
    Fenêtre ±3 jours pour couvrir weekends et jours fériés BRVM.
    """
    date_from = (target_date - timedelta(days=3)).isoformat()
    date_to   = (target_date + timedelta(days=3)).isoformat()

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


def get_previous_price(company_id: int, run_date: date):
    """
    Récupère le prix à la date de génération de la prévision (baseline).
    Utilisé pour calculer direction_predicted et direction_actual.
    """
    date_from = (run_date - timedelta(days=5)).isoformat()
    date_to   = run_date.isoformat()

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
    return resp.data[-1]["price"]


def verify_predictions():
    today = date.today()
    print(f"📅 Vérification des prévisions GRU au {today}")
    print("=" * 55)

    # 1. Récupérer toutes les prévisions dont la date est passée
    #    et qui ne sont pas encore vérifiées dans predictions_results
    resp = (
        supabase.table("predictions")
        .select("id, company_id, run_date, prediction_date, predicted_price, confidence_level")
        .lte("prediction_date", today.isoformat())
        .execute()
    )
    predictions = resp.data

    if not predictions:
        print("  ⚠️  Aucune prévision à vérifier.")
        return

    print(f"  {len(predictions)} prévisions candidates")

    # 2. Récupérer les prediction_id déjà vérifiés pour éviter doublons
    existing_resp = (
        supabase.table("predictions_results")
        .select("prediction_id")
        .execute()
    )
    existing_ids = {r["prediction_id"] for r in existing_resp.data} if existing_resp.data else set()
    print(f"  {len(existing_ids)} déjà vérifiées — ignorées")

    # 3. Récupérer les symboles via companies
    companies_resp = supabase.table("companies").select("id, symbol").execute()
    company_map = {c["id"]: c["symbol"] for c in companies_resp.data}

    # 4. Cache prix baseline par (company_id, run_date)
    baseline_cache = {}

    results = []
    skipped = 0

    for p in predictions:
        pred_id    = p["id"]
        company_id = p["company_id"]
        run_date   = date.fromisoformat(p["run_date"][:10])
        pred_date  = date.fromisoformat(p["prediction_date"])
        pred_price = float(p["predicted_price"])
        ticker     = company_map.get(company_id, f"ID{company_id}")

        # Ignorer si déjà vérifié
        if pred_id in existing_ids:
            skipped += 1
            continue

        # Prix réel à la date prévue
        actual_price = get_actual_price(company_id, pred_date)
        if actual_price is None:
            continue

        actual_price = float(actual_price)

        # Prix baseline (au moment de la génération)
        cache_key = (company_id, run_date)
        if cache_key not in baseline_cache:
            baseline_cache[cache_key] = get_previous_price(company_id, run_date)
        baseline_price = baseline_cache[cache_key]

        # Calculs
        error_pct = round((pred_price - actual_price) / actual_price * 100, 2)

        if baseline_price and float(baseline_price) > 0:
            direction_predicted = "UP" if pred_price > float(baseline_price) else "DOWN"
            direction_actual    = "UP" if actual_price > float(baseline_price) else "DOWN"
        else:
            direction_predicted = "UNKNOWN"
            direction_actual    = "UNKNOWN"

        direction_correct = (direction_predicted == direction_actual) if direction_predicted != "UNKNOWN" else None

        horizon_days = (pred_date - run_date).days

        results.append({
            "prediction_id"     : pred_id,
            "company_id"        : company_id,
            "ticker"            : ticker,
            "run_date"          : run_date.isoformat(),
            "prediction_date"   : pred_date.isoformat(),
            "predicted_price"   : pred_price,
            "actual_price"      : actual_price,
            "error_pct"         : error_pct,
            "direction_predicted": direction_predicted,
            "direction_actual"  : direction_actual,
            "direction_correct" : direction_correct,
        })

    print(f"  {skipped} ignorées (déjà vérifiées)")
    print(f"  {len(results)} nouvelles vérifications\n")

    if not results:
        print("  ✅ Rien à upserter — tout est à jour.")
        return

    # 5. Upsert par batch de 100
    batch_size = 100
    for i in range(0, len(results), batch_size):
        batch = results[i:i + batch_size]
        supabase.table("predictions_results").upsert(batch, on_conflict="company_id,run_date,prediction_date").execute()

    print(f"✅ {len(results)} résultats insérés dans predictions_results")

    # 6. Résumé par horizon
    print("\n📊 Précision directionnelle par horizon :")
    print(f"  {'Horizon':<10} {'Correct':<10} {'Total':<10} {'Dir.Acc':<10} {'MAE%'}")
    print("  " + "-" * 50)

    for h in [2, 5, 7, 10]:
        h_results = [r for r in results if (
            date.fromisoformat(r["prediction_date"]) - date.fromisoformat(r["run_date"])
        ).days == h and r["direction_correct"] is not None]

        if not h_results:
            continue

        correct  = sum(1 for r in h_results if r["direction_correct"])
        total    = len(h_results)
        dir_acc  = correct / total * 100
        mae_pct  = sum(abs(r["error_pct"]) for r in h_results) / total

        print(f"  J+{h:<8} {correct:<10} {total:<10} {dir_acc:<9.1f}% {mae_pct:.1f}%")

    # 7. Résumé global
    all_valid = [r for r in results if r["direction_correct"] is not None]
    if all_valid:
        correct_total = sum(1 for r in all_valid if r["direction_correct"])
        total_total   = len(all_valid)
        mae_global    = sum(abs(r["error_pct"]) for r in all_valid) / total_total
        print(f"\n  {'GLOBAL':<10} {correct_total:<10} {total_total:<10} {correct_total/total_total*100:<9.1f}% {mae_global:.1f}%")

    # 8. Top 5 meilleures prévisions (erreur la plus faible)
    sorted_results = sorted(results, key=lambda r: abs(r["error_pct"]))[:5]
    print("\n🎯 Top 5 prévisions les plus précises :")
    for r in sorted_results:
        h = (date.fromisoformat(r["prediction_date"]) - date.fromisoformat(r["run_date"])).days
        print(f"  {r['ticker']:<8} J+{h} | prédit {r['predicted_price']:.0f} | réel {r['actual_price']:.0f} | erreur {r['error_pct']:+.1f}%")


if __name__ == "__main__":
    verify_predictions()
