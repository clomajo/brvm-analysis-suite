"""
calculate_target_price.py
Calcule un cours cible par ticker BRVM via méthode PER normalisé + Gordon
Produit : table target_prices (ticker, cours_cible, decote_pct, methode, date)

=== CHANGEMENTS (ADR-009, ADR-010 — 20/06/2026) ===
- PER sectoriels : ne sont plus hardcodés. Lus dynamiquement depuis la table
  Supabase `sector_per_history` (saisie manuelle mensuelle depuis le Tableau de
  Bord BOA Capital Securities). Si un secteur n'a pas de valeur en base, on
  retombe sur PER_FALLBACK avec un warning explicite et un champ
  `per_source: "fallback"` tracé dans le résultat (jamais silencieux).
- Nomenclature sectorielle : migration des 5 anciennes catégories
  (banque/agro/industrie/telecom/distribution) vers les 7 catégories OFFICIELLES
  BRVM (en vigueur depuis 02/01/2025) : Consommation de Base, Consommation
  Discrétionnaire, Énergie, Industriels, Services Financiers, Services Publics,
  Télécommunications.
- Mapping ticker -> secteur reconstruit depuis richbourse.com (source exhaustive,
  47/47 tickers confirmés) — corrige un bug préexistant où CFAC apparaissait dans
  2 secteurs à la fois (agro ET distribution).
- TAUX_REQUIS (8%) : inchangé, cf. ADR-009 — origine non traçable mais maintenu
  faute de méthodologie de remplacement fiable.
"""

import os
import requests
from datetime import date
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Mapping ticker -> secteur officiel BRVM (7 catégories, nomenclature 02/01/2025+)
# Source : richbourse.com/common/variation/index (20/06/2026), 47/47 tickers confirmés.
SECTEUR_OFFICIEL = {
    # CONSOMMATION DE BASE (9)
    "NTLC": "CONSOMMATION_DE_BASE", "PALC": "CONSOMMATION_DE_BASE",
    "SPHC": "CONSOMMATION_DE_BASE", "SICC": "CONSOMMATION_DE_BASE",
    "STBC": "CONSOMMATION_DE_BASE", "SOGC": "CONSOMMATION_DE_BASE",
    "SLBC": "CONSOMMATION_DE_BASE", "SCRC": "CONSOMMATION_DE_BASE",
    "UNLC": "CONSOMMATION_DE_BASE",

    # CONSOMMATION DISCRETIONNAIRE (7)
    "BNBC": "CONSOMMATION_DISCRETIONNAIRE", "CFAC": "CONSOMMATION_DISCRETIONNAIRE",
    "LNBB": "CONSOMMATION_DISCRETIONNAIRE", "NEIC": "CONSOMMATION_DISCRETIONNAIRE",
    "ABJC": "CONSOMMATION_DISCRETIONNAIRE",  # Servair Abidjan
    "PRSC": "CONSOMMATION_DISCRETIONNAIRE",  # Tractafric Motors
    "UNXC": "CONSOMMATION_DISCRETIONNAIRE",

    # ENERGIE (4)
    "SMBC": "ENERGIE", "TTLC": "ENERGIE", "TTLS": "ENERGIE", "SHEC": "ENERGIE",

    # INDUSTRIELS (6)
    "SDSC": "INDUSTRIELS", "SEMC": "INDUSTRIELS", "SIVC": "INDUSTRIELS",
    "FTSC": "INDUSTRIELS",
    "STAC": "INDUSTRIELS",  # SETAO — ne pas confondre avec STBC (Sitab)
    "CABC": "INDUSTRIELS",

    # SERVICES FINANCIERS (16)
    "BOAB": "SERVICES_FINANCIERS", "BOABF": "SERVICES_FINANCIERS",
    "BOAC": "SERVICES_FINANCIERS", "BOAM": "SERVICES_FINANCIERS",
    "BOAN": "SERVICES_FINANCIERS", "BOAS": "SERVICES_FINANCIERS",
    "BICB": "SERVICES_FINANCIERS", "BICC": "SERVICES_FINANCIERS",
    "CBIBF": "SERVICES_FINANCIERS", "ECOC": "SERVICES_FINANCIERS",
    "ETIT": "SERVICES_FINANCIERS", "NSBC": "SERVICES_FINANCIERS",
    "ORGT": "SERVICES_FINANCIERS", "SAFC": "SERVICES_FINANCIERS",
    "SGBC": "SERVICES_FINANCIERS", "SIBC": "SERVICES_FINANCIERS",

    # SERVICES PUBLICS (2)
    "CIEC": "SERVICES_PUBLICS", "SDCC": "SERVICES_PUBLICS",

    # TELECOMMUNICATIONS (3)
    "ONTBF": "TELECOMMUNICATIONS", "ORAC": "TELECOMMUNICATIONS",
    "SNTS": "TELECOMMUNICATIONS",
}

# Fallback explicite si un secteur manque en base (jamais silencieux, cf. discussion 20/06/2026).
# Valeurs reprises des dernières connues lues le 18/06/2026 dans le Tableau de Bord BOA,
# à date de rédaction de ce patch — seront périmées dès que sector_per_history sera alimentée.
PER_FALLBACK = {
    "CONSOMMATION_DE_BASE": 6.5,
    "CONSOMMATION_DISCRETIONNAIRE": 10.0,
    "ENERGIE": 5.1,
    "INDUSTRIELS": 3.5,
    "SERVICES_FINANCIERS": 14.7,
    "SERVICES_PUBLICS": 6.0,
    "TELECOMMUNICATIONS": 14.7,
    "AUTRE": 11.0,  # ticker non mappé à un secteur connu
}

TAUX_REQUIS = 0.08  # 8% — maintenu, cf. ADR-009 (origine non traçable, pas de base de remplacement fiable)


def get_secteur(ticker):
    return SECTEUR_OFFICIEL.get(ticker, "AUTRE")


def fetch_per_sectoriels():
    """
    Lit le P/E sectoriel le plus récent par secteur depuis sector_per_history.
    Retourne un dict {secteur: (per_value, source)} où source est
    'sector_per_history' ou 'fallback'.
    """
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/sector_per_history"
        f"?select=secteur,per_2024,date_releve&order=date_releve.desc",
        headers=HEADERS,
    )
    rows = r.json() if r.status_code == 200 else []

    per_par_secteur = {}
    for row in rows:
        secteur = row["secteur"]
        if secteur not in per_par_secteur:  # garde la plus récente (tri desc)
            per_par_secteur[secteur] = (row["per_2024"], "sector_per_history")

    secteurs_attendus = list(PER_FALLBACK.keys())
    secteurs_attendus.remove("AUTRE")  # AUTRE n'a jamais de ligne en base, fallback systématique

    for secteur in secteurs_attendus:
        if secteur not in per_par_secteur:
            print(f"  ⚠️  ATTENTION : aucun P/E trouvé pour '{secteur}' dans sector_per_history.")
            print(f"      → Fallback sur {PER_FALLBACK[secteur]}x (valeur figée, à vérifier/mettre à jour).")
            per_par_secteur[secteur] = (PER_FALLBACK[secteur], "fallback")

    per_par_secteur["AUTRE"] = (PER_FALLBACK["AUTRE"], "fallback")
    return per_par_secteur


def evaluer_qualite_eps(rows_ticker):
    """
    Applique le filtre data-quality (cf. session du 13/06/2026, assoupli le 21/06/2026) :
    1. Minimum 1 année EPS exploitable. Si 2+ années disponibles (jusqu'à 3), elles
       doivent être CONSÉCUTIVES et sans collapse — sinon le ticker est exclu même
       avec 1 seule année "propre" parmi des années plus anciennes incohérentes.
    2. Filtre de collapse : si l'EPS le plus récent chute de >80% par rapport
       à l'année précédente, le ticker est exclu (cas BOAN : -92% YoY).

    LIMITE ASSUMÉE : avec 1 SEULE année EPS disponible, ni la consécutivité ni le
    collapse ne sont vérifiables (il faut au moins 2 points pour comparer). Le
    ticker est alors accepté SANS AUCUN CONTRÔLE DE QUALITÉ — l'EPS retenu peut
    être une année atypique non représentative (résultat exceptionnel, charge non
    récurrente, etc.), exactement le risque que ce filtre visait à exclure à
    l'origine. Choix assumé (21/06/2026) pour ne pas perdre des tickers comme ORAC
    (Orange CI) juste pour profondeur d'historique insuffisante.

    rows_ticker : liste de dicts {fiscal_year, eps, ...} triée par fiscal_year DESC.

    Retourne (valide: bool, raison: str|None, nb_annees_utilisees: int).
    """
    annees_eps = []
    for row in rows_ticker:
        fy = row.get("fiscal_year")
        eps = row.get("eps")
        if fy is None or eps is None:
            continue
        try:
            annee_num = int(str(fy).replace("FY", "").strip())
        except (ValueError, TypeError):
            continue
        annees_eps.append((annee_num, eps))

    if len(annees_eps) < 1:
        return False, "aucune année EPS exploitable", 0

    annees_eps.sort(key=lambda x: x[0], reverse=True)

    # Cas particulier : une seule année dispo -> acceptée sans contrôle (cf. docstring)
    if len(annees_eps) == 1:
        return True, None, 1

    # 2+ années : on utilise jusqu'à 3, avec contrôle consécutivité + collapse
    n_annees = min(3, len(annees_eps))
    annees_retenues = annees_eps[:n_annees]
    annees_seules = [a for a, _ in annees_retenues]

    for i in range(len(annees_seules) - 1):
        if annees_seules[i] - annees_seules[i + 1] != 1:
            return False, f"années non consécutives : {annees_seules}", 0

    eps_recent = annees_retenues[0][1]
    eps_precedent = annees_retenues[1][1]
    if eps_precedent and eps_precedent != 0:
        variation_pct = (eps_recent - eps_precedent) / abs(eps_precedent) * 100
        if variation_pct <= -80:
            return False, f"collapse EPS {variation_pct:.1f}% YoY ({eps_precedent} -> {eps_recent})", 0

    return True, None, n_annees


def fetch_fundamentals():
    """
    Récupère EPS moyen 3 ans + dividende le plus recent par ticker (V2-07).

    === CHANGEMENT (ADR-011, 21/06/2026) ===
    Remplace l'ancienne logique implicite (pas de filtre du tout — un bug latent
    qui laissait passer NTLC, ETIT, BOAN avec des données non représentatives,
    cf. session du 13/06/2026) par un vrai filtre data-quality :
    - 3 années fiscales les plus récentes CONSÉCUTIVES avec EPS non-null
    - Exclusion si collapse EPS >80% YoY sur l'année la plus récente
    Les tickers qui échouent sont explicitement loggés avec leur raison
    d'exclusion (jamais de silence — cf. discussion du 20/06/2026 sur les
    fallbacks tracés).
    """
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/company_fundamentals"
        f"?select=ticker,fiscal_year,eps,dividend_per_share,pe_ratio"
        f"&eps=not.is.null&order=ticker.asc,fiscal_year.desc",
        headers={**HEADERS, "Range": "0-2999"}
    )
    data = r.json()

    # Grouper par ticker — on garde TOUTES les années disponibles ici (pas de limite à 3)
    # pour pouvoir vérifier correctement la consécutivité avant de tronquer.
    grouped = {}
    for row in data:
        t = row["ticker"]
        grouped.setdefault(t, []).append(row)

    result = {}
    exclus = []

    for ticker, rows in grouped.items():
        valide, raison, n_annees = evaluer_qualite_eps(rows)
        if not valide:
            exclus.append((ticker, raison))
            continue

        # Une fois validé, on calcule l'EPS moyen sur les n_annees retenues (2 ou 3)
        rows_retenues = rows[:n_annees]  # déjà trié fiscal_year.desc par la requête
        eps_values = [r["eps"] for r in rows_retenues if r["eps"] and abs(r["eps"]) < 1e7]
        eps_avg = round(sum(eps_values) / len(eps_values), 2) if eps_values else None
        latest = rows_retenues[0]
        result[ticker] = {
            "ticker": ticker,
            "fiscal_year": latest["fiscal_year"],
            "eps": eps_avg,
            "eps_years": len(eps_values),
            "dividend_per_share": latest["dividend_per_share"],
            "pe_ratio": latest["pe_ratio"],
        }

    if exclus:
        print(f"\n  🚫 {len(exclus)} ticker(s) exclu(s) par le filtre data-quality (ADR-011) :")
        for ticker, raison in sorted(exclus):
            print(f"      {ticker:8s} → {raison}")

    return result


def fetch_prix_actuels():
    """Récupère le dernier prix connu par ticker."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/historical_data"
        f"?select=company_id,trade_date,price&order=trade_date.desc",
        headers=HEADERS
    )
    rows = r.json()
    rc = requests.get(
        f"{SUPABASE_URL}/rest/v1/companies?select=id,symbol",
        headers=HEADERS
    )
    companies = {c["id"]: c["symbol"] for c in rc.json()}

    prix = {}
    for row in rows:
        symbol = companies.get(row["company_id"])
        if symbol and symbol not in prix:
            prix[symbol] = row["price"]
    return prix


def calculer_cours_cible(eps, dividende, secteur, per_par_secteur):
    """Retourne (cours_cible, methode, per_ref, per_source)."""
    per_ref, per_source = per_par_secteur.get(secteur, per_par_secteur["AUTRE"])

    cours_per = None
    if eps and eps > 0 and abs(eps) < 1e7:
        cours_per = eps * per_ref

    cours_gordon = None
    if dividende and dividende > 0:
        cours_gordon = dividende / TAUX_REQUIS

    if cours_per and cours_gordon:
        cours_cible = 0.70 * cours_per + 0.30 * cours_gordon
        methode = "PER70+Gordon30"
    elif cours_per:
        cours_cible = cours_per
        methode = "PER100"
    elif cours_gordon:
        cours_cible = cours_gordon
        methode = "Gordon100"
    else:
        return None, None, per_ref, per_source

    return round(cours_cible, 2), methode, per_ref, per_source


def run():
    print("=== Calcul cours cibles BRVM (V2 — PER sectoriels dynamiques, ADR-010) ===")

    print("\n→ Lecture des PER sectoriels (sector_per_history)...")
    per_par_secteur = fetch_per_sectoriels()

    fundamentals = fetch_fundamentals()
    prix_actuels = fetch_prix_actuels()

    print(f"\nTickers avec fondamentaux : {len(fundamentals)}")
    print(f"Tickers avec prix : {len(prix_actuels)}")

    resultats = []
    today = date.today().isoformat()

    for ticker, row in sorted(fundamentals.items()):
        eps = row.get("eps")
        dividende = row.get("dividend_per_share")
        fiscal_year = row.get("fiscal_year")
        prix_actuel = prix_actuels.get(ticker)
        secteur = get_secteur(ticker)

        cours_cible, methode, per_ref, per_source = calculer_cours_cible(
            eps, dividende, secteur, per_par_secteur
        )

        if not cours_cible or not prix_actuel:
            print(f"  ⚠️  {ticker}: données insuffisantes (cours_cible={cours_cible}, prix={prix_actuel})")
            continue

        decote_pct = round((cours_cible - prix_actuel) / prix_actuel * 100, 2)
        signal = "ACHAT" if decote_pct > 15 else "VENTE" if decote_pct < -15 else "NEUTRE"

        resultats.append({
            "ticker": ticker,
            "fiscal_year": fiscal_year,
            "secteur": secteur,
            "eps": eps,
            "dividende": dividende,
            "per_ref": per_ref,
            "per_source": per_source,  # 'sector_per_history' ou 'fallback' — traçabilité
            "cours_cible": cours_cible,
            "prix_actuel": prix_actuel,
            "decote_pct": decote_pct,
            "signal_v2": signal,
            "methode": methode,
            "calcul_date": today,
        })

        flag = "🟢" if signal == "ACHAT" else "🔴" if signal == "VENTE" else "⚪"
        n_years = row.get("eps_years", 1)
        src_flag = "" if per_source == "sector_per_history" else " [FALLBACK]"
        print(f"  {flag} {ticker} ({secteur}{src_flag}) | EPS={eps} (moy {n_years}ans) | PER={per_ref}x | Cible={cours_cible} | Actuel={prix_actuel} | Décote={decote_pct}% | {signal}")

    resultats.sort(key=lambda x: x["decote_pct"], reverse=True)

    print(f"\n=== Résumé ===")
    print(f"ACHAT  : {sum(1 for r in resultats if r['signal_v2']=='ACHAT')}")
    print(f"NEUTRE : {sum(1 for r in resultats if r['signal_v2']=='NEUTRE')}")
    print(f"VENTE  : {sum(1 for r in resultats if r['signal_v2']=='VENTE')}")

    n_fallback = sum(1 for r in resultats if r["per_source"] == "fallback")
    if n_fallback:
        print(f"\n⚠️  {n_fallback} ligne(s) calculée(s) avec un PER fallback (pas sector_per_history).")
        print("   Vérifier que sector_per_history est bien à jour (saisie mensuelle, cf. update_sector_per.py).")

    print(f"\n=== Top 5 décotes (ACHAT) ===")
    for r in resultats[:5]:
        print(f"  {r['ticker']}: cible={r['cours_cible']} vs actuel={r['prix_actuel']} ({r['decote_pct']}%)")

    print(f"\n=== Top 5 surcotes (VENTE) ===")
    for r in resultats[-5:]:
        print(f"  {r['ticker']}: cible={r['cours_cible']} vs actuel={r['prix_actuel']} ({r['decote_pct']}%)")

    if resultats:
        print(f"\n=== Upsert Supabase ({len(resultats)} lignes) ===")
        for i in range(0, len(resultats), 50):
            batch = resultats[i:i+50]
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/target_prices?on_conflict=ticker,calcul_date",
                headers={**HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"},
                json=batch
            )
            if r.status_code in [200, 201]:
                print(f"  ✅ Batch {i//50+1} : {len(batch)} lignes insérées/mises à jour")
            else:
                print(f"  ❌ Erreur batch {i//50+1} : {r.status_code} {r.text[:200]}")

    return resultats


if __name__ == "__main__":
    run()
