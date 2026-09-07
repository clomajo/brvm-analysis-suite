"""Export de sauvegarde d'une table Supabase, pagine et verifie.
Usage : python3 tools/export_table_backup.py <table> [colonne_date] [debut] [fin]
Lecture seule.
"""
import os, sys, json, hashlib, logging, datetime
import requests
from dotenv import load_dotenv, find_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

load_dotenv(find_dotenv(usecwd=True))
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
PAGE = 1000


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: export_table_backup.py <table> [col_date] [debut] [fin]")
    table = sys.argv[1]
    filtre = ""
    suffixe = "integral"
    if len(sys.argv) >= 5:
        col, d1, d2 = sys.argv[2], sys.argv[3], sys.argv[4]
        filtre = f"&{col}=gte.{d1}&{col}=lte.{d2}"
        suffixe = f"{d1}_{d2}"

    r = requests.get(f"{URL}/rest/v1/{table}?select=id{filtre}",
                     headers={**H, "Prefer": "count=exact", "Range": "0-0"}, timeout=60)
    log.info("count body: %s", r.text[:200])
    r.raise_for_status()
    attendu = int(r.headers["content-range"].split("/")[-1])
    log.info("count exact attendu: %s", attendu)

    rows, off = [], 0
    while True:
        rr = requests.get(f"{URL}/rest/v1/{table}?select=*{filtre}"
                          f"&order=id.asc&limit={PAGE}&offset={off}", headers=H, timeout=120)
        if rr.status_code >= 400:
            log.error("offset=%s: %s", off, rr.text[:500])
        rr.raise_for_status()
        b = rr.json()
        rows += b
        log.info("offset=%s recu=%s cumul=%s", off, len(b), len(rows))
        if len(b) < PAGE:
            break
        off += PAGE

    if len(rows) != attendu:
        raise SystemExit(f"ECHEC: {len(rows)} lignes pour {attendu} attendues")
    ids = [x["id"] for x in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit("ECHEC: doublons d'id")

    os.makedirs("backups", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"backups/{table}_{suffixe}_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1, sort_keys=True, default=str)

    blob = open(path, "rb").read()
    relu = json.load(open(path, encoding="utf-8"))
    log.info("--- VERIFICATION")
    log.info("fichier : %s", path)
    log.info("taille  : %.2f Mo", len(blob) / 1e6)
    log.info("sha256  : %s", hashlib.sha256(blob).hexdigest())
    log.info("relues  : %s (attendu %s)", len(relu), attendu)
    log.info("colonnes: %s", len(relu[0].keys()))
    if len(relu) != attendu:
        raise SystemExit("ECHEC: relecture incoherente")
    log.info("EXPORT VALIDE")


if __name__ == "__main__":
    main()
