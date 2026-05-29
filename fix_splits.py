#!/usr/bin/env python3
"""
fix_splits.py — Correction des splits historiques BRVM
=======================================================
Corrige les prix historiques dans la table historical_data (Supabase)
en appliquant les facteurs de fractionnement officiels documentés.

Sources : Avis officiels BRVM (PDFs), communiqués émetteurs, captures brvm.org/fr/esv/fractionnement

Usage :
    python3 fix_splits.py          # dry run (affiche les corrections sans les appliquer)
    python3 fix_splits.py --apply  # applique les corrections en base

Logique :
    Pour chaque split (ticker, date_effective, facteur) :
    Tous les prix AVANT la date_effective sont divisés par le facteur cumulatif.
    Les prix APRÈS restent inchangés.
    Les facteurs sont appliqués du plus récent au plus ancien pour éviter les doublons.
"""

import os
import sys
import requests
from datetime import date
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

DRY_RUN = "--apply" not in sys.argv

# ==============================================================================
# TABLE DES SPLITS OFFICIELS
# Format : (ticker, date_effective_str, facteur_float, source)
# Triée chronologiquement par ticker puis par date
# ==============================================================================
SPLITS = [
    # ── ABJC (SERVAIR ABIDJAN) ─────────────────────────────────────────────
    ("ABJC",  "2016-09-30",  20.0,   "Avis N°143-2016 BRVM/DG"),

    # ── BICC (BICI CI) ─────────────────────────────────────────────────────
    ("BICC",  "2017-10-06",  10.0,   "Avis N°179-2017 BRVM/DG"),

    # ── BNBC (BERNABE CI) ──────────────────────────────────────────────────
    ("BNBC",  "2017-07-27",  20.0,   "Avis N°106-2017 BRVM/DG"),

    # ── BOAB (BOA BENIN) ───────────────────────────────────────────────────
    ("BOAB",  "2017-06-20",   2.0,   "Augmentation capital par incorporation réserves"),
    ("BOAB",  "2017-10-31",  10.0,   "Avis N°219-2017 BRVM/DG"),
    ("BOAB",  "2024-09-03",   2.0,   "Avis N°204-2024 BRVM/DG — attribution 1p1"),

    # ── BOABF (BOA BURKINA FASO) ───────────────────────────────────────────
    ("BOABF", "2017-06-27",   2.0,   "Augmentation capital par incorporation réserves"),
    ("BOABF", "2017-10-24",  10.0,   "Avis N°210-2017 BRVM/DG"),
    ("BOABF", "2024-08-28",   2.0,   "Avis N°197-2024 BRVM/DG — attribution 1p1"),

    # ── BOAC (BOA COTE D'IVOIRE) ───────────────────────────────────────────
    ("BOAC",  "2017-06-21",   2.0,   "Augmentation capital par incorporation réserves"),
    ("BOAC",  "2017-10-26",  10.0,   "Avis N°199-2017 BRVM/DG"),
    ("BOAC",  "2024-10-25",   2.0,   "Avis N°257-2024 BRVM/DG — attribution 1p1"),

    # ── BOAM (BOA MALI) ────────────────────────────────────────────────────
    # Attribution gratuite 1p2 = facteur 1.5 (prix divisé par 1.5)
    ("BOAM",  "2017-09-20",   1.5,   "Avis N°174-2017 BRVM/DG — attribution 1p2"),
    ("BOAM",  "2017-12-22",   5.0,   "Avis N°252-2017 BRVM/DG"),
    ("BOAM",  "2024-08-28",   1.5,   "Avis N°196-2024 BRVM/DG — attribution 1p2"),

    # ── BOAN (BOA NIGER) ───────────────────────────────────────────────────
    ("BOAN",  "2017-10-27",  10.0,   "Avis N°215-2017 BRVM/DG"),
    # Attribution 3 nouvelles pour 5 anciennes = facteur 8/5 = 1.6667
    ("BOAN",  "2024-09-04",   8/5,   "Avis N°205-2024 BRVM/DG — attribution 3p5"),

    # ── BOAS (BOA SENEGAL) ─────────────────────────────────────────────────
    ("BOAS",  "2017-06-27",   2.0,   "Augmentation capital par incorporation réserves"),
    ("BOAS",  "2017-10-30",  10.0,   "Avis N°204-2017 BRVM/DG"),
    ("BOAS",  "2024-08-29",   1.5,   "Avis N°200-2024 BRVM/DG — attribution 1p2"),

    # ── CABC (SICABLE CI) ──────────────────────────────────────────────────
    ("CABC",  "2017-08-17",  40.0,   "Avis N°146-2017 BRVM/DG"),

    # ── CBIBF (CORIS BANK INTERNATIONAL) ──────────────────────────────────
    ("CBIBF", "2017-12-14",   5.0,   "Avis N°240-2017 BRVM/DG"),

    # ── CFAC (CFAO MOTORS CI) ──────────────────────────────────────────────
    ("CFAC",  "2017-12-13", 100.0,   "Avis N°236-2017 BRVM/DG"),

    # ── CIEC (CIE CI) ──────────────────────────────────────────────────────
    ("CIEC",  "2017-10-19",  20.0,   "Avis N°194-2017 + N°209-2017 BRVM/DG"),
    # Second split 2018 — observé ÷4.66x — estimé ÷5x (non documenté brvm.org)
    ("CIEC",  "2018-07-17",   5.0,   "ESTIMÉ ÷5x — non documenté officiellement"),

    # ── ECOC (ECOBANK CI) ──────────────────────────────────────────────────
    ("ECOC",  "2018-12-27",   5.0,   "Avis N°180-2018 + N°194-2018 BRVM/DG"),

    # ── FTSC (FILTISAC CI) ─────────────────────────────────────────────────
    ("FTSC",  "2018-01-31",   4.0,   "Avis N°009-2018 BRVM/DG"),
    # Split 2025 — observé ÷1.72x — estimé attribution gratuite 1p1.37 (non documenté)
    ("FTSC",  "2025-09-26",   1.72,  "ESTIMÉ — non documenté officiellement"),

    # ── NEIC (NEI-CEDA CI) ─────────────────────────────────────────────────
    ("NEIC",  "2017-08-10",  25.0,   "Communiqué NEI-CEDA 24/07/2017"),

    # ── NTLC (NESTLE CI) ───────────────────────────────────────────────────
    ("NTLC",  "2017-09-08",  20.0,   "Avis N°164-2017 BRVM/DG"),

    # ── ONTBF (ONATEL BF) ──────────────────────────────────────────────────
    ("ONTBF", "2018-08-29",   2.0,   "Avis N°123-2018 BRVM/DG"),
    # Split 2026 — observé ÷9.62x — estimé ÷10x
    ("ONTBF", "2026-03-24",  10.0,   "ESTIMÉ ÷10x — non documenté officiellement"),

    # ── ORGT ───────────────────────────────────────────────────────────────
    # Observé ÷3.85x — estimé ÷4x
    ("ORGT",  "2026-03-24",   4.0,   "ESTIMÉ ÷4x — non documenté officiellement"),

    # ── PALC (PALM CI) ─────────────────────────────────────────────────────
    ("PALC",  "2017-11-03",   2.0,   "Avis N°208-2017 BRVM/DG"),

    # ── PRSC (TRACTAFRIC MOTORS CI) ────────────────────────────────────────
    ("PRSC",  "2019-10-25",  64.0,   "Avis N°162-2019 BRVM/DG"),

    # ── SAFC (SAFCA CI) ────────────────────────────────────────────────────
    ("SAFC",  "2017-07-21",   5.0,   "Avis N°105-2017 BRVM/DG"),
    ("SAFC",  "2018-12-24",  25.0,   "Avis N°178-2018 + N°192-2018 BRVM/DG"),
    # Split 2026 — observé ÷1.32x — estimé attribution partielle
    ("SAFC",  "2026-04-25",   1.32,  "ESTIMÉ — non documenté officiellement"),

    # ── SCRC (SUCRIVOIRE CI) ───────────────────────────────────────────────
    ("SCRC",  "2017-12-04",   4.0,   "Avis N°233-2017 BRVM/DG"),
    # Split 2026 — observé ÷2.5x
    ("SCRC",  "2026-03-24",   2.5,   "ESTIMÉ ÷2.5x — non documenté officiellement"),

    # ── SDCC (SODECI CI) ───────────────────────────────────────────────────
    ("SDCC",  "2017-12-28",  10.0,   "Avis N°254-2017 + N°268-2017 BRVM/DG"),

    # ── SDSC (BOLLORE TRANSPORT & LOGISTICS CI) ────────────────────────────
    ("SDSC",  "2017-07-29",  50.0,   "Avis N°129-2017 BRVM/DG"),
    # Split 2026 — observé ÷4.01x
    ("SDSC",  "2026-03-24",   4.0,   "ESTIMÉ ÷4x — non documenté officiellement"),

    # ── SEMC (CROWN SIEM CI) ───────────────────────────────────────────────
    ("SEMC",  "2018-12-20",  40.0,   "Avis N°189-2018 BRVM/DG"),

    # ── SGBC (SGBCI) ───────────────────────────────────────────────────────
    ("SGBC",  "2017-08-25",  10.0,   "Avis N°139-2017 BRVM/DG"),

    # ── SIBC (SIB CI) ──────────────────────────────────────────────────────
    ("SIBC",  "2018-06-15",   5.0,   "Avis N°072-2018 + N°090-2018 BRVM/DG"),
    ("SIBC",  "2024-11-14",   2.0,   "Avis N°273-2024 BRVM/DG — attribution 1p1"),

    # ── SICC ───────────────────────────────────────────────────────────────
    # Observé ÷10.52x — estimé ÷10x (même vague que BICC même date)
    ("SICC",  "2017-10-09",  10.0,   "ESTIMÉ ÷10x — même vague que BICC"),
    # Split 2026 — observé ÷6.79x — estimé ÷7x
    ("SICC",  "2026-04-07",   7.0,   "ESTIMÉ ÷7x — non documenté officiellement"),

    # ── SIVC ───────────────────────────────────────────────────────────────
    # Observé ÷3.94x — estimé ÷4x
    ("SIVC",  "2017-12-05",   4.0,   "ESTIMÉ ÷4x — non documenté officiellement"),

    # ── SLBC (SOLIBRA CI) ──────────────────────────────────────────────────
    ("SLBC",  "2024-09-30",  10.0,   "Avis N°242-2024 BRVM/DG"),

    # ── SMBC (SMB CI) ──────────────────────────────────────────────────────
    ("SMBC",  "2019-02-25",   4.0,   "Avis N°016-2019 + N°024-2019 BRVM/DG"),

    # ── SNTS (SONATEL SN) ──────────────────────────────────────────────────
    # Observé ÷1.87x — attribution gratuite 1p1 (÷2x théorique)
    ("SNTS",  "2018-08-29",   2.0,   "ESTIMÉ ÷2x — attribution gratuite probable"),

    # ── SOGC (SOGB CI) ─────────────────────────────────────────────────────
    ("SOGC",  "2017-08-18",  10.0,   "Avis N°147-2017 BRVM/DG"),
    # Second split 2018 — observé ÷10.79x
    ("SOGC",  "2018-04-06",  10.0,   "ESTIMÉ ÷10x — non documenté officiellement"),

    # ── SPHC (SAPH CI) ─────────────────────────────────────────────────────
    ("SPHC",  "2017-07-21",   5.0,   "Avis N°105-2017 BRVM/DG"),

    # ── STAC (SETAO CI) ────────────────────────────────────────────────────
    ("STAC",  "2017-10-25", 100.0,   "Avis N°196-2017 BRVM/DG"),
    # Second split 2018 — observé ÷20.4x
    ("STAC",  "2018-07-31",  20.0,   "ESTIMÉ ÷20x — non documenté officiellement"),
    # Split 2025 — observé ÷4.6x
    ("STAC",  "2025-12-31",   5.0,   "ESTIMÉ ÷5x — non documenté officiellement"),

    # ── STBC (SITAB CI) ────────────────────────────────────────────────────
    ("STBC",  "2018-07-27",  20.0,   "Avis N°121-2018 BRVM/DG + communiqué SITAB"),

    # ── TTLC (TOTAL CI) ────────────────────────────────────────────────────
    ("TTLC",  "2018-02-12",   5.0,   "Avis N°011-2018 BRVM/DG"),

    # ── TTLS (TOTAL SENEGAL) ───────────────────────────────────────────────
    ("TTLS",  "2017-11-02",  10.0,   "Avis N°206-2017 BRVM/DG"),

    # ── UNLC (UNILEVER CI) ─────────────────────────────────────────────────
    # Observé ÷1.4x en jan 2020 — nature exacte inconnue
    ("UNLC",  "2020-01-03",   1.4,   "ESTIMÉ — nature opération non documentée"),

    # ── UNXC (UNIWAX CI) ───────────────────────────────────────────────────
    ("UNXC",  "2017-08-11",   5.0,   "Avis N°118-2017 BRVM/DG"),
]

# ==============================================================================
# FONCTIONS
# ==============================================================================

def get_company_ids():
    """Retourne dict {symbol: company_id}"""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol",
        headers=HEADERS
    )
    r.raise_for_status()
    return {c["symbol"]: c["id"] for c in r.json()}


def get_price_before(company_id, date_str):
    """Retourne le prix de clôture la veille du split pour vérification."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/historical_data"
        f"?select=trade_date,price&company_id=eq.{company_id}"
        f"&trade_date=lt.{date_str}&order=trade_date.desc&limit=1",
        headers=HEADERS
    )
    rows = r.json()
    return rows[0] if rows else None


def get_price_on_or_after(company_id, date_str):
    """Retourne le premier prix le jour du split ou après."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/historical_data"
        f"?select=trade_date,price&company_id=eq.{company_id}"
        f"&trade_date=gte.{date_str}&order=trade_date.asc&limit=1",
        headers=HEADERS
    )
    rows = r.json()
    return rows[0] if rows else None


def count_rows_before(company_id, date_str):
    """Compte les lignes à corriger."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/historical_data"
        f"?select=id&company_id=eq.{company_id}&trade_date=lt.{date_str}",
        headers={**HEADERS, "Prefer": "count=exact", "Range": "0-0"}
    )
    cr = r.headers.get("Content-Range", "0/0")
    total = cr.split("/")[-1]
    return int(total) if total.isdigit() else 0


def apply_split_correction(company_id, date_str, facteur, ticker, source, dry_run=True):
    """
    Divise tous les prix AVANT date_str par facteur.
    Détecte automatiquement si le split est déjà appliqué en base (ratio_obs ~ 1.0).
    """
    # Vérification préalable
    before = get_price_before(company_id, date_str)
    after  = get_price_on_or_after(company_id, date_str)
    n_rows = count_rows_before(company_id, date_str)

    if not before or not after:
        print(f"  ⚠️  {ticker} {date_str}: données insuffisantes — IGNORÉ")
        return 0

    ratio_obs = before["price"] / after["price"]

    # Détection split déjà appliqué : ratio obs proche de 1.0
    # (le prix avant ≈ prix après = split déjà intégré dans les données source)
    SEUIL_DEJA_APPLIQUE = 1.15
    deja_applique = ratio_obs < SEUIL_DEJA_APPLIQUE

    statut = "⏭️  DÉJÀ APPLIQUÉ — IGNORÉ" if deja_applique else ("✅" if not dry_run else "📋")
    print(f"\n{statut} {ticker} {date_str} ÷{facteur}x")
    print(f"  Source    : {source}")
    print(f"  Avant     : {before['trade_date']} → {before['price']:,.0f} FCFA")
    print(f"  Après     : {after['trade_date']}  → {after['price']:,.0f} FCFA")
    print(f"  Ratio obs : ÷{ratio_obs:.3f}x  (officiel: ÷{facteur}x)")

    if deja_applique:
        print(f"  → Ratio obs ({ratio_obs:.3f}x) < seuil {SEUIL_DEJA_APPLIQUE}x : split déjà dans les données")
        return 0

    print(f"  Lignes à corriger : {n_rows}")

    if dry_run:
        return n_rows

    # Application via UPDATE en batch (par pages de 1000)
    offset = 0
    total_updated = 0
    while True:
        # Récupérer batch de IDs + prix
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/historical_data"
            f"?select=id,price&company_id=eq.{company_id}"
            f"&trade_date=lt.{date_str}&order=trade_date.asc"
            f"&limit=1000&offset={offset}",
            headers=HEADERS
        )
        rows = r.json()
        if not rows:
            break

        # PATCH chaque ligne avec prix corrigé
        for row in rows:
            new_price = round(row["price"] / facteur, 2)
            rp = requests.patch(
                f"{SUPABASE_URL}/rest/v1/historical_data?id=eq.{row['id']}",
                headers=HEADERS,
                json={"price": new_price}
            )
            if rp.status_code not in (200, 204):
                print(f"  ❌ Erreur patch id={row['id']}: {rp.status_code}")

        total_updated += len(rows)
        offset += len(rows)
        if len(rows) < 1000:
            break

    print(f"  ✅ {total_updated} lignes mises à jour")
    return total_updated


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    print("=" * 70)
    print(f"fix_splits.py — {'DRY RUN (aucune modification)' if DRY_RUN else 'APPLY MODE — modifications en base'}")
    print("=" * 70)

    companies = get_company_ids()

    # Trier : du plus récent au plus ancien pour éviter double-correction
    splits_sorted = sorted(SPLITS, key=lambda x: x[1], reverse=True)

    total_lignes = 0
    not_found = []
    estimés = []

    for ticker, date_str, facteur, source in splits_sorted:
        company_id = companies.get(ticker)
        if not company_id:
            not_found.append(ticker)
            continue
        if "ESTIMÉ" in source:
            estimés.append((ticker, date_str, facteur))

        n = apply_split_correction(
            company_id, date_str, facteur, ticker, source, dry_run=DRY_RUN
        )
        total_lignes += n

    print("\n" + "=" * 70)
    print(f"TOTAL lignes {'à corriger' if DRY_RUN else 'corrigées'} : {total_lignes}")

    if not_found:
        print(f"\n⚠️  Tickers non trouvés en base : {', '.join(set(not_found))}")

    if estimés:
        print(f"\n⚠️  {len(estimés)} splits ESTIMÉS (facteur non officiellement confirmé) :")
        for t, d, f in estimés:
            print(f"   {t} {d} ÷{f}x")

    if DRY_RUN:
        print("\n→ Pour appliquer : python3 fix_splits.py --apply")
    else:
        print("\n✅ Correction terminée.")


if __name__ == "__main__":
    main()
