"""Diagnostic de l'ecart entre ADR-052 amdt 3 (281 idx / 7549 act) et le live
du 07/09 (275 / 7471). Lecture seule. Aucune ecriture.

Hypothese H1 : la mesure de l'amdt 3 est fausse (plafond PostgREST 5000).
Hypothese H2 : 84 lignes ont ete supprimees entre le 04/09 et le 07/09.
"""
import os, json, glob, logging, collections, datetime
import requests
from dotenv import load_dotenv, find_dotenv

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

load_dotenv(find_dotenv(usecwd=True))
URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
D1, D2 = "2026-03-26", "2026-09-04"
PAGE = 1000


def count(table, qs):
    r = requests.get(f"{URL}/rest/v1/{table}?select=id&{qs}",
                     headers={**H, "Prefer": "count=exact", "Range": "0-0"}, timeout=60)
    if r.status_code >= 400:
        log.error("%s %s -> %s", table, qs, r.text[:400])
    r.raise_for_status()
    return int(r.headers["content-range"].split("/")[-1])


def get_all(table, qs, order="id.asc"):
    out, off = [], 0
    while True:
        r = requests.get(f"{URL}/rest/v1/{table}?{qs}&order={order}&limit={PAGE}&offset={off}",
                         headers=H, timeout=120)
        if r.status_code >= 400:
            log.error("%s -> %s", table, r.text[:400])
        r.raise_for_status()
        b = r.json()
        out += b
        if len(b) < PAGE:
            return out
        off += PAGE


def main():
    path = sorted(glob.glob("backups/historical_data_2026-03-26_2026-09-04_*.json"))[-1]
    log.info("=== SNAPSHOT LOCAL : %s", path)
    with open(path, encoding="utf-8") as f:
        snap = json.load(f)
    log.info("lignes snapshot : %s", len(snap))

    s_act = [r for r in snap if r["company_id"] not in (48, 49)]
    s_idx = [r for r in snap if r["company_id"] in (48, 49)]
    log.info("actions / indices : %s / %s", len(s_act), len(s_idx))

    log.info("\n=== H2 : la base a-t-elle bouge depuis l'export ?")
    live_tot = count("historical_data", f"trade_date=gte.{D1}&trade_date=lte.{D2}")
    live_idx = count("historical_data", f"trade_date=gte.{D1}&trade_date=lte.{D2}&company_id=in.(48,49)")
    log.info("live total  : %s (snapshot %s) -> %s", live_tot, len(snap),
             "STABLE" if live_tot == len(snap) else "A BOUGE")
    log.info("live indices: %s (snapshot %s)", live_idx, len(s_idx))

    ids_live = {r["id"] for r in get_all(
        "historical_data", f"select=id&trade_date=gte.{D1}&trade_date=lte.{D2}")}
    ids_snap = {r["id"] for r in snap}
    log.info("ids disparus depuis l'export : %s", sorted(ids_snap - ids_live)[:20])
    log.info("ids apparus depuis l'export  : %s", sorted(ids_live - ids_snap)[:20])

    log.info("\n=== Structure des indices (48/49) dans le snapshot")
    per_cid = collections.Counter(r["company_id"] for r in s_idx)
    log.info("par company_id : %s", dict(per_cid))
    d48 = sorted({r["trade_date"] for r in s_idx if r["company_id"] == 48})
    d49 = sorted({r["trade_date"] for r in s_idx if r["company_id"] == 49})
    log.info("dates 48 : %s (%s -> %s)", len(d48), d48[0] if d48 else "-", d48[-1] if d48 else "-")
    log.info("dates 49 : %s (%s -> %s)", len(d49), d49[0] if d49 else "-", d49[-1] if d49 else "-")
    log.info("dates 48 sans 49 : %s", sorted(set(d48) - set(d49))[:15])
    log.info("dates 49 sans 48 : %s", sorted(set(d49) - set(d48))[:15])
    log.info("281 - 275 = 6 ; ecart |48|-|49| = %s", abs(len(d48) - len(d49)))

    log.info("\n=== boc_cote (pagine)")
    n_boc = count("boc_cote", "est_droit=is.false")
    bc = get_all("boc_cote", "select=date_seance,symbole,volume&est_droit=is.false")
    log.info("count exact : %s | rapatrie : %s -> %s", n_boc, len(bc),
             "OK" if n_boc == len(bc) else "INCOHERENT")
    bd = sorted({r["date_seance"] for r in bc})
    log.info("seances BOC : %s (%s -> %s)", len(bd), bd[0], bd[-1])
    wk = [d for d in bd if datetime.date.fromisoformat(d).weekday() >= 5]
    log.info("BOC en week-end : %s", wk)

    log.info("\n=== Couverture croisee (snapshot actions x boc_cote)")
    sd = sorted({r["trade_date"] for r in s_act})
    sd_wk = [d for d in sd if datetime.date.fromisoformat(d).weekday() >= 5]
    log.info("dates HD actions : %s | dont week-end : %s", len(sd), len(sd_wk))
    log.info("BOC sans HD : %s", sorted(set(bd) - set(sd)))
    log.info("HD sans BOC en semaine : %s",
             sorted(d for d in set(sd) - set(bd) if datetime.date.fromisoformat(d).weekday() < 5))

    log.info("\n=== Cible reelle de l'etape 4")
    log.info("actions attendues apres bascule : %s", len(bc))
    log.info("indices conserves (live)        : %s", live_idx)
    log.info("TOTAL cible                     : %s", len(bc) + live_idx)


if __name__ == "__main__":
    main()
