"""Test de restauration de l'export historical_data dans une table jetable.
N'ecrit QUE dans historical_data_restore_test. historical_data n'est jamais
touchee (aucune requete d'ecriture ne la vise).
"""
import os, json, glob, logging
import requests
from dotenv import load_dotenv, find_dotenv

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

load_dotenv(find_dotenv(usecwd=True))
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
CIBLE = "historical_data_restore_test"
PAGE = 500
COLS = ["id", "company_id", "trade_date", "price", "volume", "value",
        "created_at", "open_price", "high_price", "low_price"]


def get_all(table, qs="select=*"):
    out, off = [], 0
    while True:
        r = requests.get(f"{URL}/rest/v1/{table}?{qs}&order=id.asc&limit=1000&offset={off}",
                         headers=H, timeout=120)
        if r.status_code >= 400:
            log.error("%s", r.text[:500])
        r.raise_for_status()
        b = r.json()
        out += b
        if len(b) < 1000:
            return out
        off += 1000


def main():
    path = sorted(glob.glob("backups/historical_data_2026-03-26_2026-09-04_*.json"))[-1]
    snap = json.load(open(path, encoding="utf-8"))
    log.info("export : %s (%s lignes)", path, len(snap))

    deja = get_all(CIBLE, "select=id")
    if deja:
        raise SystemExit(f"ARRET: {CIBLE} contient deja {len(deja)} lignes. Vider avant.")
    log.info("table cible vide, OK")

    log.info("--- insertion par lots de %s", PAGE)
    for i in range(0, len(snap), PAGE):
        lot = snap[i:i + PAGE]
        r = requests.post(f"{URL}/rest/v1/{CIBLE}", headers={**H,
                          "Content-Type": "application/json",
                          "Prefer": "return=minimal"},
                          json=lot, timeout=120)
        if r.status_code >= 400:
            log.error("ECHEC lot %s-%s: %s", i, i + len(lot), r.text[:600])
            r.raise_for_status()
        log.info("lot %s-%s insere (%s)", i, i + len(lot), r.status_code)

    log.info("--- comparaison")
    restaure = get_all(CIBLE)
    log.info("lignes restaurees : %s (attendu %s)", len(restaure), len(snap))
    if len(restaure) != len(snap):
        raise SystemExit("ECHEC: nombre de lignes different")

    a = {r["id"]: r for r in snap}
    b = {r["id"]: r for r in restaure}
    if set(a) != set(b):
        raise SystemExit(f"ECHEC: ids differents ({len(set(a) ^ set(b))} ecarts)")
    log.info("ids identiques : OK")

    ecarts = []
    for i in a:
        for c in COLS:
            va, vb = a[i].get(c), b[i].get(c)
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                if abs(float(va) - float(vb)) > 1e-9:
                    ecarts.append((i, c, va, vb))
            elif str(va) != str(vb):
                ecarts.append((i, c, va, vb))
    if ecarts:
        log.error("ECARTS (%s) — 10 premiers :", len(ecarts))
        for e in ecarts[:10]:
            log.error("  id=%s col=%s export=%r restaure=%r", *e)
        raise SystemExit("ECHEC: contenu different")

    log.info("champ par champ sur %s colonnes : IDENTIQUE", len(COLS))
    log.info("\nRESTAURATION VALIDEE — %s lignes rejouables a l'identique", len(snap))


if __name__ == "__main__":
    main()
