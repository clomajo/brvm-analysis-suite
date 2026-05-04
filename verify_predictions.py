# ==============================================================================
# VERIFY PREDICTIONS — Compare GRU predictions vs actual prices
# Runs daily — checks predictions where prediction_date = today
# ==============================================================================

import os, logging, requests
from datetime import date, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

def headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def get_predictions_for_today():
    today = date.today().isoformat()
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/predictions",
        headers=headers(),
        params={
            "prediction_date": f"eq.{today}",
            "select": "company_id,run_date,prediction_date,predicted_price",
            "order": "company_id.asc"
        }
    )
    if r.status_code != 200:
        logging.error(f"❌ Fetch predictions: {r.text}")
        return []
    return r.json()

def get_actual_price(company_id, trade_date):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/historical_data",
        headers=headers(),
        params={
            "company_id": f"eq.{company_id}",
            "trade_date": f"eq.{trade_date}",
            "select": "price,trade_date"
        }
    )
    if r.status_code != 200 or not r.json():
        return None
    return float(r.json()[0]["price"])

def get_previous_price(company_id, before_date):
    """Prix du jour avant prediction_date pour calculer direction prédite"""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/historical_data",
        headers=headers(),
        params={
            "company_id": f"eq.{company_id}",
            "trade_date": f"lt.{before_date}",
            "price": "not.is.null",
            "select": "price,trade_date",
            "order": "trade_date.desc",
            "limit": 1
        }
    )
    if r.status_code != 200 or not r.json():
        return None
    return float(r.json()[0]["price"])

def get_ticker(company_id):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/companies",
        headers=headers(),
        params={"id": f"eq.{company_id}", "select": "symbol"}
    )
    if r.status_code != 200 or not r.json():
        return str(company_id)
    return r.json()[0]["symbol"]

def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        logging.critical("❌ SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY manquant")
        return

    today = date.today().isoformat()
    logging.info("=" * 60)
    logging.info(f"🔍 VERIFY PREDICTIONS — {today}")
    logging.info("=" * 60)

    predictions = get_predictions_for_today()
    if not predictions:
        logging.info(f"⏭️  Aucune prédiction à vérifier pour {today}")
        return

    logging.info(f"📋 {len(predictions)} prédiction(s) à vérifier")

    results = []
    verified = 0
    no_data = 0

    for p in predictions:
        company_id    = p["company_id"]
        run_date      = p["run_date"]
        pred_date     = p["prediction_date"]
        predicted     = float(p["predicted_price"])
        ticker        = get_ticker(company_id)

        actual = get_actual_price(company_id, pred_date)
        if actual is None:
            logging.warning(f"⚠️  {ticker} : prix réel introuvable pour {pred_date}")
            no_data += 1
            continue

        prev_price = get_previous_price(company_id, pred_date)
        if prev_price is None:
            prev_price = predicted  # fallback

        error_pct = round(abs(predicted - actual) / actual * 100, 2)
        dir_predicted = "UP" if predicted >= prev_price else "DOWN"
        dir_actual    = "UP" if actual >= prev_price else "DOWN"
        dir_correct   = dir_predicted == dir_actual

        results.append({
            "company_id":          company_id,
            "ticker":              ticker,
            "run_date":            run_date,
            "prediction_date":     pred_date,
            "predicted_price":     predicted,
            "actual_price":        actual,
            "error_pct":           error_pct,
            "direction_predicted": dir_predicted,
            "direction_actual":    dir_actual,
            "direction_correct":   dir_correct,
        })

        icon = "✅" if dir_correct else "❌"
        logging.info(f"{icon} {ticker} | prédit {predicted:.0f} | réel {actual:.0f} | erreur {error_pct:.1f}% | direction {'✓' if dir_correct else '✗'}")
        verified += 1

    if results:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/predictions_results",
            headers=headers(),
            json=results
        )
        if r.status_code in (200, 201):
            logging.info(f"\n✅ {len(results)} résultats sauvegardés")
        else:
            logging.error(f"❌ Erreur insertion: {r.status_code} {r.text}")

    logging.info("=" * 60)
    logging.info(f"✅ Vérifiés : {verified} | Sans données : {no_data}")
    if results:
        correct = sum(1 for r in results if r["direction_correct"])
        avg_err = sum(r["error_pct"] for r in results) / len(results)
        logging.info(f"📊 Direction correcte : {correct}/{len(results)} ({correct/len(results)*100:.0f}%)")
        logging.info(f"📊 MAPE moyen : {avg_err:.2f}%")
    logging.info("=" * 60)

if __name__ == "__main__":
    main()
