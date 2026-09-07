"""Export de sauvegarde de historical_data sur la plage de bascule ADR-052 amdt 3.
Lecture seule. Aucune ecriture cote Supabase.
"""
import os, json, logging, hashlib, datetime
import requests
from dotenv import load_dotenv, find_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

load_dotenv(find_dotenv(usecwd=True))
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}

D1, D2 = "2026-03-26", "2026-09-04"
PAGE = 1000
FILTRE = f"trade_date=gte.{D1}&trade_date=lte.{D2}"


def count_exact():
    r = requests.get(f"{URL}/rest/v1/historical_data?select=id&{FILTRE}",
                     headers={**H, "Prefer": "count=exact", "Range": "0-0"}, timeout=60)
    log.info("count body: %s", r.text[:300])
    r.raise_for_status()
    return int(r.headers["content-range"].split("/")[-1])


def fetch_all():
    rows, off = [], 0
    while True:
        r = requests.get(
            f"{URL}/rest/v1/historical_data?select=*&{FILTRE}"
            f"&order=id.asc&limit={PAGE}&offset={off}", headers=H, timeout=120)
        if r.status_code >= 400:
            log.error("erreur offset=%s: %s", off, r.text[:500])
        r.raise_for_status()
        batch = r.json()
        rows += batch
        log.info("offset=%s recu=%s cumul=%s", off, len(batch), len(rows))
        if len(batch) < PAGE:
            return rows
        off += PAGE


def main():
    attendu = count_exact()
    log.info("count exact attendu: %s", attendu)

    rows = fetch_all()
    if len(rows) != attendu:
        raise SystemExit(f"ECHEC: {len(rows)} lignes recuperees pour {attendu} attendues")

    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit("ECHEC: doublons d'id dans l'export")

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"backups/historical_data_{D1}_{D2}_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1, sort_keys=True, default=str)

    with open(path, "rb") as f:
        blob = f.read()
    sha = hashlib.sha256(blob).hexdigest()

    with open(path, encoding="utf-8") as f:
        relu = json.load(f)

    dates = sorted({r["trade_date"] for r in relu})
    idx = sum(1 for r in relu if r["company_id"] in (48, 49))
    log.info("--- VERIFICATION")
    log.info("fichier      : %s", path)
    log.info("taille       : %.2f Mo", len(blob) / 1e6)
    log.info("sha256       : %s", sha)
    log.info("lignes relues: %s (attendu %s)", len(relu), attendu)
    log.info("dates        : %s de %s a %s", len(dates), dates[0], dates[-1])
    log.info("indices 48/49: %s | actions: %s", idx, len(relu) - idx)
    if len(relu) != attendu:
        raise SystemExit("ECHEC: relecture incoherente")
    log.info("EXPORT VALIDE")


if __name__ == "__main__":
    main()
