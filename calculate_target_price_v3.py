# -*- coding: utf-8 -*-
"""
calculate_target_price_v3.py
=============================
Calcule la Fair Value V3 pour chaque ticker BRVM :
  - Pondération progressive DDM ↔ P/E selon régularité dividende
  - Décote liquidité (volume/capitalisation)
  - Score qualité Couche 2 (ROE, croissance, dividende, liquidité)
  - Bornes de confiance ±15% ou ±30%
  - Signal : ACHAT / SURVEILLER / PASSER

ADR-nouveau : Fair Value V3
Remplace : calculate_target_price.py (V2 — DDM pur)
Bascule prévue : 01/07/2026
Date : 2026-06-04
"""

import os
import json
import time
import requests
from datetime import date, timedelta
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates,return=minimal",
}

# ── PER sectoriels manuels (calibrés sur données BRVM réelles) ────────────────
# Basés sur SKILL.md ADR + mesures réelles 2026-06-04
PER_SECTORIEL = {
    "banque":       11.6,
    "telecom":      14.0,
    "agro":         10.2,
    "distribution": 13.2,
    "industrie":    12.0,
    "autre":        12.0,
}

# Mapping ticker → secteur
SECTEUR_MAP = {
    # Banques
    "BOAB": "banque", "BOABF": "banque", "BOAC": "banque", "BOAM": "banque",
    "BOAN": "banque", "BOAS": "banque", "SGBC": "banque", "SIBC": "banque",
    "NSBC": "banque", "BICC": "banque", "BICB": "banque", "CBIBF": "banque",
    "CABC": "banque", "ECOC": "banque", "STBC": "banque", "SLBC": "banque",
    "LNBB": "banque", "ABJC": "banque", "BNBC": "banque", "SMBC": "banque",
    "SAFC": "banque", "NEIC": "banque", "NSBC": "banque",
    # Télécom
    "ORAC": "telecom", "ONTBF": "telecom", "ORGT": "telecom",
    # Agro-industrie
    "PALC": "agro", "SOGC": "agro", "CFAC": "agro", "SIVC": "agro",
    "SDSC": "agro", "UNXC": "agro",
    # Distribution / Commerce
    "TTLC": "distribution", "TTLS": "distribution", "SDCC": "distribution",
    "SEMC": "distribution", "SCRC": "distribution", "SHEC": "distribution",
    "PRSC": "distribution",
    # Industrie / Autres
    "SNTS": "industrie", "SPHC": "industrie", "SICC": "industrie",
    "STAC": "industrie", "FTSC": "industrie", "ETIT": "industrie",
    "CIEC": "industrie", "BICC": "industrie", "UNLC": "industrie",
    "NTLC": "industrie", "SOGC": "industrie", "SAFC": "industrie",
    "SOGC": "industrie",
}

# Seuil minimum de qualité pour signal ACHAT
QUALITE_MIN_ACHAT = 2   # sur 4
UPSIDE_MIN = 0.05       # +5% minimum


# ── Helpers Supabase ───────────────────────────────────────────────────────────

def sb_get(table, params):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers={**HEADERS, "Range": "0-999"},
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def sb_upsert(table, records):
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=HEADERS,
        json=records,
        timeout=30,
    )
    r.raise_for_status()


# ── Données marché ─────────────────────────────────────────────────────────────

def get_cours_actuel(company_id, historical_df):
    """Dernier cours connu pour un ticker."""
    rows = [r for r in historical_df if r["company_id"] == company_id]
    if not rows:
        return None
    rows.sort(key=lambda x: x["trade_date"], reverse=True)
    return rows[0]["price"]


def get_volume_moyen(company_id, historical_df, jours=20):
    """Volume moyen sur les N derniers jours."""
    rows = [r for r in historical_df if r["company_id"] == company_id]
    rows.sort(key=lambda x: x["trade_date"], reverse=True)
    recent = rows[:jours]
    volumes = [r["volume"] for r in recent if r.get("volume") and r["volume"] > 0]
    return sum(volumes) / len(volumes) if volumes else 0


# ── Score qualité (Couche 2) ───────────────────────────────────────────────────

def score_qualite(fund):
    """
    Score qualité 0-4 :
      1 pt : ROE >= 15% (seuil BRVM adapté)
      1 pt : Croissance CA/PNB > 5%
      1 pt : Dividende versé (dps > 0)
      1 pt : Liquidité (volume_ratio > seuil)
    """
    score = 0
    details = []

    # Critère 1 — ROE
    roe = fund.get("roe")
    if roe is not None and roe >= 15:
        score += 1
        details.append(f"ROE={roe:.1f}% ✅")
    else:
        details.append(f"ROE={roe}% ❌" if roe is not None else "ROE=null ❌")

    # Critère 2 — Croissance CA
    growth = fund.get("revenue_growth") or fund.get("croissance_ca_pct")
    if growth is not None and growth > 5:
        score += 1
        details.append(f"Croissance={growth:.1f}% ✅")
    else:
        details.append(f"Croissance={growth}% ❌" if growth is not None else "Croissance=null ❌")

    # Critère 3 — Dividende
    dps = fund.get("dividend_per_share")
    if dps is not None and dps > 0:
        score += 1
        details.append(f"DPS={dps:.0f} FCFA ✅")
    else:
        details.append("DPS=null/0 ❌")

    # Critère 4 — Liquidité (via volume_ratio stocké ou market_cap proxy)
    # On donne 1 pt si market_cap > 50 milliards (proxy liquidité)
    mktcap = fund.get("market_cap")
    if mktcap is not None and mktcap > 50_000_000_000:
        score += 1
        details.append(f"MktCap={mktcap/1e9:.0f}G ✅")
    else:
        details.append(f"MktCap={mktcap/1e9:.0f}G ❌" if mktcap else "MktCap=null ❌")

    return score, details


# ── Décote liquidité ──────────────────────────────────────────────────────────

def decote_liquidite(volume_moyen, shares_outstanding):
    """
    Décote sur Fair Value selon ratio volume/shares_outstanding :
      > 0.1%  → 0%   (liquide)
      0.01–0.1% → 10%  (peu liquide)
      < 0.01% → 20%  (illiquide)
      données manquantes → 10% (prudence modérée, pas maximale)
    """
    if not shares_outstanding or shares_outstanding <= 0:
        return 0.10  # données manquantes → décote modérée

    if volume_moyen <= 0:
        return 0.10  # pas de volume récent → décote modérée

    ratio = volume_moyen / shares_outstanding

    if ratio >= 0.001:    # > 0.1% des actions échangées/jour
        return 0.0
    elif ratio >= 0.0001: # 0.01–0.1%
        return 0.10
    else:
        return 0.20


# ── Calcul Fair Value V3 ──────────────────────────────────────────────────────

def fair_value_v3(ticker, fund, historical_df, company_id, boa_by_ticker=None):
    """
    Calcule la Fair Value V3 pour un ticker.
    Retourne un dict avec tous les champs pour upsert dans target_prices.
    """
    result = {
        "ticker":          ticker,
        "calcul_date":     date.today().isoformat(),
        "fair_value_v3":   None,
        "borne_basse":     None,
        "borne_haute":     None,
        "w_ddm":           None,
        "decote_pct":      None,
        "qualite_score":   None,
        "signal_v3":       "PASSER",
        "methode":         None,
        "upside_pct":      None,
    }

    # 1. Cours actuel
    cours = get_cours_actuel(company_id, historical_df)
    if not cours:
        result["signal_v3"] = "NO_DATA"
        return result

    # 2. DPS et pondération DDM
    dps = fund.get("dividend_per_share") or 0

    # Rendement cible BOA (source primaire) ou fallback sectoriel
    boa = (boa_by_ticker or {}).get(ticker, {})
    rdt_raw = boa.get("rendement")
    if rdt_raw and float(rdt_raw) > 0:
        rdt_cible = float(rdt_raw) / 100.0  # BOA stocke en % (ex: 7.36 → 0.0736)
        rdt_source = "BOA"
    else:
        # Fallback : rendement moyen sectoriel estimé
        secteur_tmp = SECTEUR_MAP.get(ticker, "autre")
        rdt_fallback = {"banque": 0.065, "telecom": 0.05, "agro": 0.055,
                        "distribution": 0.055, "industrie": 0.06, "autre": 0.06}
        rdt_cible = rdt_fallback.get(secteur_tmp, 0.06)
        rdt_source = "fallback"

    # Pondération DDM : 0 si pas de DPS, 1 si DPS disponible
    nb_dividendes = 1 if dps > 0 else 0
    w = min(1.0, nb_dividendes / 1.0)

    valeur_ddm = (dps / rdt_cible) if dps > 0 and rdt_cible > 0 else None

    # 3. Valeur P/E
    eps = fund.get("eps")
    secteur = SECTEUR_MAP.get(ticker, "autre")
    per_sectoriel = PER_SECTORIEL.get(secteur, 12.0)
    valeur_pe = (eps * per_sectoriel) if eps and eps > 0 else None

    # 4. Fair Value hybride
    if valeur_ddm and valeur_pe:
        fair_brute = w * valeur_ddm + (1 - w) * valeur_pe
        methode = f"DDM({int(w*100)}%,{rdt_source})+PE({int((1-w)*100)}%)"
    elif valeur_ddm:
        fair_brute = valeur_ddm
        methode = f"DDM_seul({rdt_source},{rdt_cible*100:.1f}%)"
    elif valeur_pe:
        fair_brute = valeur_pe
        methode = f"PE_seul({secteur}×{per_sectoriel}x)"
    else:
        result["signal_v3"] = "NO_DATA"
        result["methode"] = "insuffisant"
        return result

    # 5. Décote liquidité
    vol_moyen = get_volume_moyen(company_id, historical_df)
    shares = fund.get("shares_outstanding") or 0
    decote = decote_liquidite(vol_moyen, shares)
    # Décote informative seulement — ne réduit pas la FV
    # (la liquidité est un filtre de taille de position, pas de valorisation)
    fair_net = fair_brute  # décote affichée séparément dans l'UI

    # 6. Score qualité
    qualite, details = score_qualite(fund)
    marge = 0.15 if qualite >= 3 else 0.30

    # 7. Signal — pénaliser qualité si illiquide (décote > 0)
    qualite_effective = qualite - 1 if decote >= 0.20 else qualite

    upside = (fair_net - cours) / cours
    if cours < fair_net * (1 - marge) and qualite_effective >= QUALITE_MIN_ACHAT and upside >= UPSIDE_MIN:
        signal = "ACHAT"
    elif cours < fair_net and upside >= UPSIDE_MIN:
        signal = "SURVEILLER"
    else:
        signal = "PASSER"

    result.update({
        "fair_value_v3": round(fair_net),
        "borne_basse":   round(fair_net * (1 - marge)),
        "borne_haute":   round(fair_net * (1 + marge)),
        "w_ddm":         round(w * 100),
        "decote_pct":    round(decote * 100),
        "qualite_score": qualite,
        "signal_v3":     signal,
        "methode":       methode,
        "upside_pct":    round(upside * 100, 1),
        "cours_actuel":  cours,
        "qualite_detail": " | ".join(details),
    })

    return result


# ── Pipeline principal ─────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("calculate_target_price_v3.py — Fair Value V3")
    print(f"Date : {date.today()}")
    print("=" * 65)

    # Chargement des données
    print("\n📥 Chargement des données...")

    companies = sb_get("companies", {"select": "id,symbol"})
    sym_to_id = {c["symbol"]: c["id"] for c in companies}
    id_to_sym = {c["id"]: c["symbol"] for c in companies}
    print(f"   {len(companies)} sociétés")

    fundamentals = sb_get("company_fundamentals", {
        "select": "*",
        "fiscal_year": "eq.FY2025",
    })
    fund_by_ticker = {f["ticker"]: f for f in fundamentals}
    print(f"   {len(fundamentals)} lignes fundamentals FY2025")

    # Historique 30 derniers jours pour volumes + cours
    date_depuis = (date.today() - timedelta(days=30)).isoformat()
    historical = sb_get("historical_data", {
        "select": "company_id,trade_date,price,volume",
        "trade_date": f"gte.{date_depuis}",
        "order": "trade_date.desc",
    })
    print(f"   {len(historical)} lignes historiques (30j)")

    # Rendements cibles BOA (plus récent par ticker)
    boa_rows = sb_get("boa_recommendations", {
        "select": "ticker,rendement,cours_pot,action,date_end",
        "order":  "date_end.desc",
    })
    boa_by_ticker = {}
    for r in boa_rows:
        if not isinstance(r, dict): continue
        t = r.get("ticker")
        if t and t not in boa_by_ticker:
            boa_by_ticker[t] = r
    print(f"   {len(boa_by_ticker)} rendements BOA chargés")

    # Calcul Fair Value V3
    print("\n🔍 Calcul Fair Value V3...\n")
    results = []
    stats = {"achat": 0, "surveiller": 0, "passer": 0, "no_data": 0}

    for ticker, fund in sorted(fund_by_ticker.items()):
        company_id = sym_to_id.get(ticker)
        if not company_id:
            continue

        res = fair_value_v3(ticker, fund, historical, company_id, boa_by_ticker)

        signal = res.get("signal_v3", "NO_DATA")
        fv = res.get("fair_value_v3")
        upside = res.get("upside_pct")
        qualite = res.get("qualite_score")
        methode = res.get("methode", "—")

        if signal == "NO_DATA":
            stats["no_data"] += 1
            print(f"  ⚫ {ticker:<8} NO_DATA ({methode})")
        elif signal == "ACHAT":
            stats["achat"] += 1
            print(f"  🟢 {ticker:<8} ACHAT      FV={fv:>7,.0f} | upside={upside:+.1f}% | qualité={qualite}/4 | {methode}")
        elif signal == "SURVEILLER":
            stats["surveiller"] += 1
            print(f"  🟡 {ticker:<8} SURVEILLER FV={fv:>7,.0f} | upside={upside:+.1f}% | qualité={qualite}/4 | {methode}")
        else:
            stats["passer"] += 1
            print(f"  🔴 {ticker:<8} PASSER     FV={fv:>7,.0f} | upside={upside:+.1f}% | qualité={qualite}/4 | {methode}")

        results.append(res)

    # Résumé
    print("\n" + "=" * 65)
    print("📊 RÉSUMÉ")
    print(f"   🟢 ACHAT      : {stats['achat']}")
    print(f"   🟡 SURVEILLER : {stats['surveiller']}")
    print(f"   🔴 PASSER     : {stats['passer']}")
    print(f"   ⚫ NO_DATA    : {stats['no_data']}")
    print("=" * 65)

    # Afficher les signaux ACHAT
    achats = [r for r in results if r.get("signal_v3") == "ACHAT"]
    if achats:
        print("\n🎯 SIGNAUX ACHAT V3 :")
        for r in sorted(achats, key=lambda x: x.get("upside_pct", 0), reverse=True):
            print(f"   {r['ticker']:<8} FV={r['fair_value_v3']:>7,.0f} FCFA | "
                  f"upside={r['upside_pct']:+.1f}% | "
                  f"qualité={r['qualite_score']}/4 | "
                  f"bornes [{r['borne_basse']:,.0f} – {r['borne_haute']:,.0f}]")

    # Upsert dans target_prices (dry run d'abord)
    print("\n💾 Upsert dans target_prices... (désactivé — dry run)")
    print("   → Relancer avec --apply pour écrire en base")

    import sys
    if "--apply" in sys.argv:
        upsert_records = []
        for r in results:
            if r.get("fair_value_v3"):
                upsert_records.append({
                    "ticker":       r["ticker"],
                    "calcul_date":  r["calcul_date"],
                    "cours_cible":  r["fair_value_v3"],
                    "borne_basse":  r["borne_basse"],
                    "borne_haute":  r["borne_haute"],
                    "decote_pct":   r["decote_pct"],
                    "signal_v2":    r["signal_v3"],  # colonne existante
                    "qualite_score": r["qualite_score"],
                    "methode_v3":   r["methode"],
                    "upside_pct":   r["upside_pct"],
                })

        if upsert_records:
            sb_upsert("target_prices", upsert_records)
            print(f"   ✅ {len(upsert_records)} lignes upsertées dans target_prices")


if __name__ == "__main__":
    main()
