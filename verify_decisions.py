import os
import logging
from datetime import date, timedelta
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
LOOKBACK_DAYS = 30

def run_verification():
    today = date.today()
    signal_date = today - timedelta(days=LOOKBACK_DAYS)
    logging.info(f"🔍 Vérification des signaux du {signal_date} (J-{LOOKBACK_DAYS})")

    # 1. Décisions à vérifier
    res = supabase.table("brvm_decisions").select("id,ticker,signal,score,date,upside_target,downside_target").eq("date", str(signal_date)).in_("signal", ["ACHAT","SURVEILLER","EVITER"]).execute()
    decisions = res.data

    if not decisions:
        # Date la plus proche
        res2 = supabase.table("brvm_decisions").select("date").lte("date", str(signal_date)).order("date", desc=True).limit(1).execute()
        if not res2.data:
            logging.info("Aucune décision disponible.")
            return
        signal_date = res2.data[0]["date"]
        logging.info(f"📅 Date ajustée : {signal_date}")
        res = supabase.table("brvm_decisions").select("id,ticker,signal,score,date,upside_target,downside_target").eq("date", signal_date).in_("signal", ["ACHAT","SURVEILLER","EVITER"]).execute()
        decisions = res.data

    logging.info(f"📋 {len(decisions)} décision(s) trouvée(s)")

    # 2. Company map
    comp_res = supabase.table("companies").select("id,symbol").execute()
    sym_to_id = {c["symbol"]: c["id"] for c in comp_res.data}

    inserted = skipped = correct = total = 0

    for d in decisions:
        ticker = d["ticker"]
        company_id = sym_to_id.get(ticker)
        if not company_id:
            continue

        # Prix signal
        p1 = supabase.table("historical_data").select("price").eq("company_id", company_id).lte("trade_date", signal_date).order("trade_date", desc=True).limit(1).execute()
        if not p1.data:
            continue
        prix_signal = float(p1.data[0]["price"])

        # Prix actuel
        p2 = supabase.table("historical_data").select("price").eq("company_id", company_id).lte("trade_date", str(today)).order("trade_date", desc=True).limit(1).execute()
        if not p2.data:
            continue
        prix_actuel = float(p2.data[0]["price"])

        # Filtre données corrompues
        if abs((prix_actuel - prix_signal) / prix_signal * 100) > 50:
            logging.warning(f"⚠️  {ticker} : données suspectes ({prix_signal} -> {prix_actuel}), ignoré")
            continue

        variation_pct = round((prix_actuel - prix_signal) / prix_signal * 100, 2)
        signal = d["signal"]

        if signal == "ACHAT":
            signal_correct = variation_pct > 0
        elif signal == "EVITER":
            signal_correct = variation_pct < 0
        else:
            signal_correct = abs(variation_pct) < 5

        if signal_correct:
            correct += 1
        total += 1

        row = {
            "decision_id": d["id"],
            "ticker": ticker,
            "signal": signal,
            "score": d["score"],
            "signal_date": signal_date,
            "verification_date": str(today),
            "prix_signal": prix_signal,
            "prix_verification": prix_actuel,
            "variation_pct": variation_pct,
            "signal_correct": signal_correct
        }

        supabase.table("brvm_decisions_results").upsert(row, on_conflict="decision_id").execute()
        inserted += 1
        status = "✅" if signal_correct else "❌"
        logging.info(f"{status} {ticker} | {signal} | {variation_pct:+.2f}%")

    hit_rate = round(correct / total * 100, 1) if total > 0 else 0
    logging.info(f"")
    logging.info(f"📊 RÉSULTATS : {correct}/{total} = {hit_rate}% hit rate")
    logging.info(f"✅ {inserted} insérés/mis à jour")

if __name__ == "__main__":
    run_verification()
