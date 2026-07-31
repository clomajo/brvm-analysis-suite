#!/usr/bin/env python3
"""Diagnostic : DIVIDEND_HISTORY.fiscal_year est-il decale d'un an ?

Lecture seule. Ne modifie rien.

Methode : a l'ex-date, le cours chute approximativement du montant detache.
Pour chaque EX_DIVIDEND, on compare la chute reelle a deux candidats :
  - candidat ACTUEL   : DIVIDEND_HISTORY de meme fiscal_year (jointure du code en prod)
  - candidat DECALE   : DIVIDEND_HISTORY de fiscal_year - 1
Le candidat le plus proche de la chute observee designe la bonne convention.

Ne depend d'aucune convention d'etiquetage : seuls les prix arbitrent.
"""
import logging
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

import requests
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

TICKERS = ["SNTS", "BOAC", "ONTBF", "BOAB", "BOABF", "ECOC", "ORAC", "CIEC", "NTLC", "SGBC"]
FENETRE_AVANT = 7   # jours calendaires pour trouver le dernier cours avant l'ex-date
FENETRE_APRES = 7   # jours calendaires pour trouver le premier cours a partir de l'ex-date


def get_env():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        logging.error("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY absent du .env")
        sys.exit(1)
    return url.rstrip("/"), key


def fetch(url, key, table, params):
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    rows, off = [], 0
    while True:
        r = requests.get(f"{url}/rest/v1/{table}",
                         headers={**headers, "Range": f"{off}-{off + 999}"},
                         params=params, timeout=30)
        r.raise_for_status()
        b = r.json()
        rows.extend(b)
        if len(b) < 1000:
            break
        off += 1000
    return rows


def charger(url, key):
    """Retourne (ex_dates_par_ticker, montants_par_ticker_fy, prix_par_ticker)."""
    comp = fetch(url, key, "companies", {"select": "id,symbol"})
    id_par_symbol = {c["symbol"]: c["id"] for c in comp}
    symbol_par_id = {c["id"]: c["symbol"] for c in comp}

    events = fetch(url, key, "corporate_events",
                   {"select": "ticker,event_type,event_date,fiscal_year,amount",
                    "order": "id"})

    ex_dates = defaultdict(list)
    montants = defaultdict(dict)
    for e in events:
        t = e.get("ticker")
        if t not in TICKERS:
            continue
        fy = str(e.get("fiscal_year") or "").strip()
        if not fy.isdigit():
            continue
        if e["event_type"] == "EX_DIVIDEND" and e.get("event_date"):
            ex_dates[t].append((int(fy), date.fromisoformat(e["event_date"])))
        elif e["event_type"] == "DIVIDEND_HISTORY" and e.get("amount") is not None:
            montants[t][int(fy)] = float(e["amount"])

    ids = [id_par_symbol[t] for t in TICKERS if t in id_par_symbol]
    prix_rows = fetch(url, key, "historical_data",
                      {"select": "company_id,trade_date,price",
                       "company_id": f"in.({','.join(str(i) for i in ids)})",
                       "order": "trade_date"})
    prix = defaultdict(dict)
    for p in prix_rows:
        t = symbol_par_id.get(p["company_id"])
        if t and p.get("price") is not None:
            prix[t][date.fromisoformat(p["trade_date"])] = float(p["price"])
    return ex_dates, montants, prix


def prix_avant(prix_t, d):
    """Dernier cours strictement avant d, dans la fenetre."""
    for i in range(1, FENETRE_AVANT + 1):
        v = prix_t.get(d - timedelta(days=i))
        if v is not None:
            return v, d - timedelta(days=i)
    return None, None


def prix_apres(prix_t, d):
    """Premier cours a partir de d (inclus), dans la fenetre."""
    for i in range(0, FENETRE_APRES + 1):
        v = prix_t.get(d + timedelta(days=i))
        if v is not None:
            return v, d + timedelta(days=i)
    return None, None


def main():
    url, key = get_env()
    ex_dates, montants, prix = charger(url, key)

    lignes, score_actuel, score_decale = [], 0, 0

    for t in TICKERS:
        for fy, exd in sorted(ex_dates.get(t, [])):
            p_av, d_av = prix_avant(prix.get(t, {}), exd)
            p_ap, d_ap = prix_apres(prix.get(t, {}), exd)
            if p_av is None or p_ap is None:
                continue
            chute = p_av - p_ap
            m_actuel = montants.get(t, {}).get(fy)
            m_decale = montants.get(t, {}).get(fy - 1)
            if m_actuel is None and m_decale is None:
                continue

            err_a = abs(chute - m_actuel) if m_actuel is not None else None
            err_d = abs(chute - m_decale) if m_decale is not None else None

            if err_a is not None and err_d is not None:
                gagnant = "ACTUEL" if err_a < err_d else "DECALE"
                if gagnant == "ACTUEL":
                    score_actuel += 1
                else:
                    score_decale += 1
            else:
                gagnant = "-"

            lignes.append((t, fy, exd, d_av, d_ap, p_av, p_ap, chute,
                           m_actuel, m_decale, gagnant))

    print(f"\n{'TICK':6} {'FY':5} {'ex-date':11} {'P avant':>9} {'P apres':>9} "
          f"{'chute':>8} {'m[FY]':>8} {'m[FY-1]':>8}  verdict")
    print("-" * 88)
    for (t, fy, exd, d_av, d_ap, p_av, p_ap, ch, ma, md, g) in lignes:
        sa = f"{ma:8.1f}" if ma is not None else "       -"
        sd = f"{md:8.1f}" if md is not None else "       -"
        print(f"{t:6} {fy:5} {exd.isoformat():11} {p_av:9.1f} {p_ap:9.1f} "
              f"{ch:8.1f} {sa} {sd}  {g}")

    total = score_actuel + score_decale
    print("\n" + "=" * 60)
    print(f"Cas comparables : {total}")
    if total:
        print(f"  jointure ACTUELLE (fiscal_year identique) gagne : {score_actuel} "
              f"({100*score_actuel/total:.0f}%)")
        print(f"  jointure DECALEE  (fiscal_year - 1)      gagne : {score_decale} "
              f"({100*score_decale/total:.0f}%)")
        if score_decale > score_actuel * 1.5:
            print("\n>>> DECALAGE CONFIRME : DIVIDEND_HISTORY.fiscal_year retarde d'un an.")
        elif score_actuel > score_decale * 1.5:
            print("\n>>> PAS DE DECALAGE : la jointure actuelle est correcte.")
        else:
            print("\n>>> NON CONCLUANT : les deux candidats se valent, bruit trop fort.")
    print("\nReserve : la chute a l'ex-date est bruitee (mouvement de marche du jour,")
    print("illiquidite, cours de reference manquant). Indicatif sur un cas, probant")
    print("sur l'ensemble.")


if __name__ == "__main__":
    main()
