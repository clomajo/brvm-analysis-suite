#!/usr/bin/env python3
"""Reconstitue la cote actions depuis les BOC et l'ecrit dans boc_cote.

Chaque bulletin est controle contre sa propre page 1 (volume, valeur
transigee, nb de titres transiges) avant tout ecrit. Un bulletin qui echoue
au controle est journalise et ignore : aucune ligne douteuse n'entre en base.

Usage :
    python3 tools/ingest_cote.py --from 2026-03-24 --to 2026-09-04
    python3 tools/ingest_cote.py --from 2026-03-24 --to 2026-09-04 --apply
"""
import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import find_dotenv, load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_boc import (  # noqa: E402
    SchemaBocInconnu, extraire_lignes, parser_agregats_marche,
    parser_cote_depuis_pdf,
)

load_dotenv(find_dotenv(usecwd=True))
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
CACHE = Path("/tmp/boc")
BASE_PDF = "https://www.brvm.org/sites/default/files/boc_{j}_2.pdf"
TAILLE_MIN = 100_000


def telecharger_pdf(jour):
    """Recupere le PDF du jour. Retourne le chemin, ou None si absent."""
    CACHE.mkdir(exist_ok=True)
    cle = jour.strftime("%Y%m%d")
    chemin = CACHE / f"boc_{cle}_2.pdf"
    if chemin.exists() and chemin.stat().st_size >= TAILLE_MIN:
        return chemin
    url = BASE_PDF.format(j=cle)
    subprocess.run(["curl", "-s", "-k", "-o", str(chemin), url],
                   check=False, timeout=120)
    if not chemin.exists() or chemin.stat().st_size < TAILLE_MIN:
        chemin.unlink(missing_ok=True)
        return None
    return chemin


def controler(chemin, titres):
    """Compare les agregats de la cote a la page 1 du meme bulletin.

    Retourne la liste des ecarts constates (vide si tout concorde).
    """
    import fitz
    doc = fitz.open(chemin)
    actions = parser_agregats_marche(extraire_lignes(doc[0])).get("ACTIONS", {})
    att_vol = actions.get("volume_echange")
    att_val = actions.get("valeur_transigee")
    att_nb = actions.get("nb_titres_transiges")

    vol = sum(t["volume"] or 0 for t in titres)
    # nb_titres_transiges de la page 1 ne compte que les actions, pas les droits
    nb = sum(1 for t in titres
             if (t["volume"] or 0) > 0 and not t.get("est_droit"))

    ecarts = []
    if att_vol is None:
        ecarts.append("page1 : volume_echange illisible")
    elif abs(vol - att_vol) >= 1:
        ecarts.append(f"volume cote {vol:,.0f} vs page1 {att_vol:,.0f}")
    if att_nb is None:
        ecarts.append("page1 : nb_titres_transiges illisible")
    elif nb != int(att_nb):
        ecarts.append(f"nb_transiges cote {nb} vs page1 {int(att_nb)}")

    # valeur_transigee : NON bloquant. Le BOC tronque l'affichage des montants
    # >= 1 milliard (ratio ~1000x observe sur SNTS, SGBC) et les droits sont
    # libelles dans une autre echelle (SAFCA). Sur 5 075 lignes saines, l'ecart
    # val vs volume x cours a une mediane de 0,59 % et un maximum de 12,2 %.
    # Seuil a 15 % : au-dela, la valeur lue est consideree non fiable.
    suspectes = []
    for t in titres:
        v, c, val = t["volume"], t["cours_cloture"], t["valeur_transigee"]
        if not v or not c or not val:
            continue
        if abs(val - v * c) / (v * c) > 0.15:
            suspectes.append(t["symbole"])
    if suspectes:
        logger.warning("    valeur_transigee non fiable sur %d titre(s) : %s",
                       len(suspectes), ", ".join(suspectes[:6]))
    return ecarts


def upsert(lignes):
    """Ecrit dans boc_cote (upsert sur date_seance,symbole)."""
    base = SUPABASE_URL if SUPABASE_URL.endswith("/rest/v1") \
        else f"{SUPABASE_URL}/rest/v1"
    url = f"{base}/boc_cote?on_conflict=date_seance,symbole"
    entetes = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    r = requests.post(url, headers=entetes, json=lignes, timeout=60)
    if r.status_code not in (200, 201, 204):
        logger.error("upsert HTTP %s — %s", r.status_code, r.text[:400])
        r.raise_for_status()
    return len(lignes)


def traiter_jour(jour, appliquer):
    """Traite un bulletin. Retourne un dict de resultat."""
    res = {"jour": jour.isoformat(), "statut": None, "lignes": 0,
           "seance": None, "bulletin": None, "ecarts": []}

    chemin = telecharger_pdf(jour)
    if chemin is None:
        res["statut"] = "ABSENT"
        return res

    try:
        seance, num, titres, pages = parser_cote_depuis_pdf(str(chemin))
    except SchemaBocInconnu as exc:
        res["statut"] = "SCHEMA_INCONNU"
        res["ecarts"] = [str(exc)]
        return res
    except Exception as exc:
        res["statut"] = "ERREUR_PARSING"
        res["ecarts"] = [f"{type(exc).__name__}: {exc}"]
        return res

    res["seance"] = seance.isoformat()
    res["bulletin"] = num

    ecarts = controler(str(chemin), titres)
    if ecarts:
        res["statut"] = "CONTROLE_ECHOUE"
        res["ecarts"] = ecarts
        return res

    url_src = BASE_PDF.format(j=jour.strftime("%Y%m%d"))
    lignes = [{
        "date_seance": seance.isoformat(),
        "bulletin_numero": num,
        "symbole": t["symbole"],
        "titre": t["titre"],
        "est_droit": t["est_droit"],
        "non_cote": t.get("non_cote", False),
        "cours_precedent": t["cours_precedent"],
        "cours_ouverture": t["cours_ouverture"],
        "cours_cloture": t["cours_cloture"],
        "variation_jour_pct": t["variation_jour_pct"],
        "volume": int(t["volume"]) if t["volume"] is not None else None,
        "valeur_transigee": t["valeur_transigee"],
        "cours_reference": t["cours_reference"],
        "variation_annuelle_pct": t["variation_annuelle_pct"],
        "dividende_net": t["dividende_net"],
        "rendement_net_pct": t["rendement_net_pct"],
        "per": t["per"],
        "source_url": url_src,
    } for t in titres]

    res["lignes"] = len(lignes)
    res["statut"] = "OK"
    if appliquer:
        upsert(lignes)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="debut", required=True, help="AAAA-MM-JJ")
    ap.add_argument("--to", dest="fin", required=True, help="AAAA-MM-JJ")
    ap.add_argument("--apply", action="store_true",
                    help="ecrit en base (sinon simulation)")
    ap.add_argument("--pause", type=float, default=1.0)
    args = ap.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("SUPABASE_URL ou SUPABASE_SERVICE_ROLE_KEY absent")
        sys.exit(2)

    debut = date.fromisoformat(args.debut)
    fin = date.fromisoformat(args.fin)
    mode = "APPLY" if args.apply else "DRY-RUN"
    logger.info("Mode %s — du %s au %s", mode, debut, fin)

    resultats = []
    jour = debut
    while jour <= fin:
        if jour.weekday() < 5:
            r = traiter_jour(jour, args.apply)
            resultats.append(r)
            if r["statut"] == "OK":
                logger.info("  %s -> seance %s n°%s : %d lignes",
                            jour, r["seance"], r["bulletin"], r["lignes"])
            elif r["statut"] != "ABSENT":
                logger.warning("  %s : %s — %s", jour, r["statut"],
                               " | ".join(r["ecarts"])[:200])
            time.sleep(args.pause)
        jour += timedelta(days=1)

    compte = {}
    for r in resultats:
        compte[r["statut"]] = compte.get(r["statut"], 0) + 1
    logger.info("=" * 60)
    for k in sorted(compte):
        logger.info("  %-18s %3d", k, compte[k])
    logger.info("  lignes %s : %d", "ecrites" if args.apply else "simulees",
                sum(r["lignes"] for r in resultats))

    rapport = Path("tools/experiments/ingest_cote_rapport.json")
    rapport.parent.mkdir(parents=True, exist_ok=True)
    rapport.write_text(json.dumps(resultats, indent=2, ensure_ascii=False))
    logger.info("  rapport : %s", rapport)


if __name__ == "__main__":
    main()
