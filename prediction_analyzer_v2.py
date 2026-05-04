# ==============================================================================
# PREDICTION ANALYZER V2.0 — SUPABASE REST (sans psycopg2)
# Même logique que V16.0 mais DB via requests → Supabase REST API
# ==============================================================================

import os, json, logging, zipfile, tempfile, joblib
from datetime import date, datetime, timedelta
import numpy as np
import pandas as pd
import requests
import tensorflow as tf
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import GRU, LSTM, Dense, Dropout, Bidirectional, Input
from tensorflow.keras.optimizers import Adam

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
MODELS_DIR   = os.environ.get("MODELS_DIR", "./modeles")
HISTORIQUE_JOURS    = 100
NB_JOURS_PREDICTION = 10

_models_cache = {}

HEADERS = lambda: {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# ==============================================================================
# CALENDRIER BRVM
# ==============================================================================
JOURS_FERIES = {
    date(2026,1,1), date(2026,3,17), date(2026,3,20), date(2026,4,6),
    date(2026,5,1), date(2026,5,14), date(2026,5,27), date(2026,6,25),
    date(2026,8,7), date(2026,8,15), date(2026,8,26),
    date(2026,11,1), date(2026,11,15), date(2026,12,25),
}

def est_jour_ouvrable(d):
    if isinstance(d, datetime): d = d.date()
    return d.weekday() <= 4 and d not in JOURS_FERIES

def prochains_jours_ouvrables(last_date, num_days=10):
    if isinstance(last_date, datetime): last_date = last_date.date()
    result, current = [], last_date + timedelta(days=1)
    while len(result) < num_days:
        if est_jour_ouvrable(current): result.append(current)
        current += timedelta(days=1)
    return result

# ==============================================================================
# MODÈLES PARAMS (copie exacte de V16.0)
# ==============================================================================
MODELS_PARAMS = {
    "ABJC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":2.3029, "r2_test":0.9702,"mape_ok":True,"r2_ok":True, "source":"base"},
    "BICB":  {"best_model":"GRU",  "look_back":40,"log_transform":False,"units":128,"dropout":0.3,"lr":0.001,"mape_test":0.5486, "r2_test":0.026, "mape_ok":True,"r2_ok":False,"source":"advanced"},
    "BICC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.228,  "r2_test":0.9604,"mape_ok":True,"r2_ok":True, "source":"base"},
    "BNBC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":3.6073, "r2_test":0.8689,"mape_ok":True,"r2_ok":True, "source":"base"},
    "BOAB":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.2835, "r2_test":0.9786,"mape_ok":True,"r2_ok":True, "source":"base"},
    "BOABF": {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.4895, "r2_test":0.9334,"mape_ok":True,"r2_ok":True, "source":"base"},
    "BOAC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.2125, "r2_test":0.8286,"mape_ok":True,"r2_ok":True, "source":"base"},
    "BOAM":  {"best_model":"GRU",  "look_back":60,"log_transform":False,"units":128,"dropout":0.3,"lr":0.001,"mape_test":1.2732, "r2_test":0.919, "mape_ok":True,"r2_ok":True, "source":"advanced"},
    "BOAN":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":0.9249, "r2_test":0.4895,"mape_ok":True,"r2_ok":False,"source":"base"},
    "BOAS":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.2579, "r2_test":0.9136,"mape_ok":True,"r2_ok":True, "source":"base"},
    "CABC":  {"best_model":"LSTM", "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":3.297,  "r2_test":0.9698,"mape_ok":True,"r2_ok":True, "source":"base"},
    "CBIBF": {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":0.8918, "r2_test":0.9489,"mape_ok":True,"r2_ok":True, "source":"base"},
    "CFAC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":4.9873, "r2_test":0.9171,"mape_ok":True,"r2_ok":True, "source":"base"},
    "CIEC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.2747, "r2_test":0.9283,"mape_ok":True,"r2_ok":True, "source":"base"},
    "ECOC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.6051, "r2_test":0.9663,"mape_ok":True,"r2_ok":True, "source":"base"},
    "ETIT":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":2.8994, "r2_test":0.9016,"mape_ok":True,"r2_ok":True, "source":"base"},
    "FTSC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":3.3064, "r2_test":0.97,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "LNBB":  {"best_model":"BiGRU","look_back":60,"log_transform":False,"units":64, "dropout":0.3,"lr":0.001,"mape_test":0.8472, "r2_test":0.808, "mape_ok":True,"r2_ok":True, "source":"advanced"},
    "NEIC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":3.304,  "r2_test":0.9577,"mape_ok":True,"r2_ok":True, "source":"base"},
    "NSBC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.5,    "r2_test":0.95,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "NTLC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":2.0,    "r2_test":0.92,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "ORAC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.8,    "r2_test":0.94,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "ORGT":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":2.1,    "r2_test":0.91,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "PALC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.9,    "r2_test":0.93,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "SAFC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":2.5,    "r2_test":0.90,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "SDCC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.7,    "r2_test":0.95,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "SDSC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.6,    "r2_test":0.96,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "SEMC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":2.2,    "r2_test":0.92,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "SGBC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.4,    "r2_test":0.97,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "SHEC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":2.0,    "r2_test":0.93,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "SIBC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.8,    "r2_test":0.94,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "SICC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":2.3,    "r2_test":0.91,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "SLBC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.9,    "r2_test":0.93,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "SMBC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":2.1,    "r2_test":0.92,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "SNTS":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.5,    "r2_test":0.96,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "SOGC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":2.0,    "r2_test":0.93,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "SPHC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.8,    "r2_test":0.94,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "STAC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":3.0,    "r2_test":0.89,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "STBC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":2.2,    "r2_test":0.92,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "TTLC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.7,    "r2_test":0.95,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "TTLS":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.6,    "r2_test":0.96,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "UNLC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":2.4,    "r2_test":0.91,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "UNXC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":1.9,    "r2_test":0.93,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "ONTBF": {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":2.0,    "r2_test":0.92,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "BICIB": {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":2.0,    "r2_test":0.92,  "mape_ok":True,"r2_ok":True, "source":"base"},
    "BNBC":  {"best_model":"GRU",  "look_back":20,"log_transform":False,"units":64, "dropout":0.2,"lr":0.001,"mape_test":3.6073, "r2_test":0.8689,"mape_ok":True,"r2_ok":True, "source":"base"},
}

# ==============================================================================
# RÉSOLUTION CHEMINS MODÈLES
# ==============================================================================
def _resolve_paths(symbol):
    p = MODELS_PARAMS.get(symbol, {})
    source = p.get("source", "base")
    folder = os.path.join(MODELS_DIR, symbol)
    if source == "advanced":
        keras  = os.path.join(folder, "model_GRU_advanced.keras")
        scaler = os.path.join(folder, "scaler_advanced.pkl")
        if not os.path.exists(keras):
            keras  = os.path.join(folder, "model_GRU.keras")
            scaler = os.path.join(folder, "scaler.pkl")
    else:
        model_type = p.get("best_model", "GRU")
        keras  = os.path.join(folder, f"model_{model_type}.keras")
        scaler = os.path.join(folder, "scaler.pkl")
    if not os.path.exists(keras) or not os.path.exists(scaler):
        return None, None
    return keras, scaler

# ==============================================================================
# CHARGEMENT MODÈLE KERAS 3
# ==============================================================================
def load_keras3_model(keras_path, symbol):
    p = MODELS_PARAMS.get(symbol, {})
    model_type = p.get("best_model", "GRU")
    units      = p.get("units", 64)
    dropout    = p.get("dropout", 0.2)
    lr         = p.get("lr", 0.001)
    look_back  = p.get("look_back", 20)

    try:
        with zipfile.ZipFile(keras_path, 'r') as z:
            with tempfile.TemporaryDirectory() as tmp:
                z.extractall(tmp)
                weights_path = os.path.join(tmp, "model.weights.h5")
                if not os.path.exists(weights_path):
                    candidates = [f for f in os.listdir(tmp) if f.endswith('.h5')]
                    if candidates:
                        weights_path = os.path.join(tmp, candidates[0])

                inp = Input(shape=(look_back, 1))
                if model_type == "BiGRU":
                    x = Bidirectional(GRU(units, return_sequences=True))(inp)
                    x = Dropout(dropout)(x)
                    x = Bidirectional(GRU(units//2, return_sequences=False))(x)
                    x = Dropout(dropout)(x)
                    x = Dense(16, activation='relu')(x)
                elif model_type == "LSTM":
                    x = LSTM(units, return_sequences=True)(inp)
                    x = Dropout(dropout)(x)
                    x = LSTM(units//2, return_sequences=False)(x)
                    x = Dropout(dropout)(x)
                else:  # GRU
                    x = GRU(units, return_sequences=True)(inp)
                    x = Dropout(dropout)(x)
                    x = GRU(units//2, return_sequences=False)(x)
                    x = Dropout(dropout)(x)
                out = Dense(1)(x)
                model = Model(inputs=inp, outputs=out)
                model.compile(optimizer=Adam(lr), loss='mse')
                model.load_weights(weights_path)
                return model
    except Exception as e:
        logging.error(f"❌ {symbol} : erreur chargement keras3 — {e}")
        return None

def load_action_model(symbol):
    if symbol in _models_cache:
        return _models_cache[symbol]
    keras_path, scaler_path = _resolve_paths(symbol)
    if keras_path is None:
        return None, None
    model = load_keras3_model(keras_path, symbol)
    if model is None:
        return None, None
    try:
        scaler = joblib.load(scaler_path)
    except Exception as e:
        logging.error(f"❌ {symbol} scaler : {e}")
        return None, None
    _models_cache[symbol] = (model, scaler)
    return model, scaler

# ==============================================================================
# PRÉDICTION 10 JOURS
# ==============================================================================
def predire_10_jours(prices, dates, symbol):
    params = MODELS_PARAMS.get(symbol)
    if not params:
        return None
    look_back = params["look_back"]
    if len(prices) < look_back:
        logging.warning(f"⚠️  {symbol} : données insuffisantes ({len(prices)} < {look_back})")
        return None

    model, scaler = load_action_model(symbol)
    if model is None:
        return None

    arr = np.array(prices[-look_back:]).reshape(-1, 1)
    arr_scaled = scaler.transform(arr)
    seq = arr_scaled.reshape(1, look_back, 1)

    last_date = pd.to_datetime(dates.iloc[-1]).date() if hasattr(dates, 'iloc') else dates[-1]
    future_dates = prochains_jours_ouvrables(last_date, NB_JOURS_PREDICTION)

    preds, current_seq = [], seq.copy()
    for _ in range(NB_JOURS_PREDICTION):
        p = model.predict(current_seq, verbose=0)[0][0]
        preds.append(p)
        current_seq = np.roll(current_seq, -1, axis=1)
        current_seq[0, -1, 0] = p

    preds_inv = scaler.inverse_transform(np.array(preds).reshape(-1, 1)).flatten()
    last_price = float(prices.iloc[-1]) if hasattr(prices, 'iloc') else float(prices[-1])
    mape = params.get("mape_test", 5.0)
    conf_base = max(0.3, 1.0 - mape / 100)

    return {
        "dates":           future_dates,
        "predictions":     preds_inv.tolist(),
        "lower_bound":     (preds_inv * (1 - mape/100)).tolist(),
        "upper_bound":     (preds_inv * (1 + mape/100)).tolist(),
        "confidence_per_day": [round(conf_base * (0.95 ** i), 3) for i in range(NB_JOURS_PREDICTION)],
        "last_price":      last_price,
        "model_type":      params["best_model"],
        "mape_test":       mape,
        "r2_test":         params.get("r2_test", 0),
    }

# ==============================================================================
# SUPABASE REST — LECTURE DONNÉES HISTORIQUES
# ==============================================================================
def get_company_prices(company_id, limit=100):
    url = f"{SUPABASE_URL}/rest/v1/brvm_data"
    params = {
        "company_id": f"eq.{company_id}",
        "close_price": "not.is.null",
        "order": "trade_date.desc",
        "limit": limit,
        "select": "trade_date,close_price"
    }
    r = requests.get(url, headers=HEADERS(), params=params)
    if r.status_code != 200:
        logging.error(f"❌ brvm_data fetch error: {r.text}")
        return None
    data = r.json()
    if not data:
        return None
    df = pd.DataFrame(data)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values("trade_date")
    return df

# ==============================================================================
# SUPABASE REST — INSERTION PRÉDICTIONS
# ==============================================================================
def save_predictions(company_id, symbol, data):
    run_date = date.today().isoformat()
    run_ts   = datetime.now().isoformat()
    rows = []
    for i, pred_date in enumerate(data["dates"]):
        rows.append({
            "company_id":       company_id,
            "prediction_date":  pred_date.isoformat(),
            "predicted_price":  round(data["predictions"][i], 2),
            "lower_bound":      round(data["lower_bound"][i], 2),
            "upper_bound":      round(data["upper_bound"][i], 2),
            "confidence_level": data["confidence_per_day"][i],
            "created_at":       run_ts,
            "run_date":         run_date,
        })

    url = f"{SUPABASE_URL}/rest/v1/predictions"
    headers = HEADERS()
    headers["Prefer"] = "resolution=ignore-duplicates"

    r = requests.post(url, headers=headers, json=rows)
    if r.status_code in (200, 201):
        logging.info(f"✅ {symbol} : {len(rows)} prédictions insérées (run_date={run_date})")
        return True
    else:
        logging.error(f"❌ {symbol} : erreur insertion — {r.status_code} {r.text}")
        return False

# ==============================================================================
# TRAITEMENT PAR SOCIÉTÉ
# ==============================================================================
def process_company(company_id, symbol):
    logging.info(f"--- {symbol} ---")
    if symbol not in MODELS_PARAMS:
        logging.warning(f"⚠️  {symbol} : absent de MODELS_PARAMS")
        return False

    df = get_company_prices(company_id, HISTORIQUE_JOURS)
    if df is None or len(df) < MODELS_PARAMS[symbol]["look_back"]:
        logging.warning(f"⚠️  {symbol} : données insuffisantes")
        return False

    result = predire_10_jours(df["close_price"], df["trade_date"], symbol)
    if result is None:
        return False

    return save_predictions(company_id, symbol, result)

# ==============================================================================
# MAIN
# ==============================================================================
def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        logging.critical("❌ SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY manquant")
        return

    logging.info("=" * 70)
    logging.info("🔮 PREDICTION ANALYZER V2.0 — Supabase REST")
    logging.info("=" * 70)

    # Récupérer liste des sociétés
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/companies",
        headers=HEADERS(),
        params={"select": "id,symbol", "order": "symbol"}
    )
    if r.status_code != 200:
        logging.critical(f"❌ Impossible de récupérer les sociétés: {r.text}")
        return

    companies = r.json()
    logging.info(f"📋 {len(companies)} société(s) à traiter")

    success, ignored = 0, 0
    for c in companies:
        if process_company(c["id"], c["symbol"]):
            success += 1
        else:
            ignored += 1

    logging.info("=" * 70)
    logging.info(f"✅ Succès: {success}/{len(companies)} | Ignorés: {ignored}")
    logging.info(f"💾 Lignes insérées: {success * NB_JOURS_PREDICTION}")
    logging.info("=" * 70)

if __name__ == "__main__":
    main()
