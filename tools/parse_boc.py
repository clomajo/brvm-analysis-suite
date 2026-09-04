#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parser BOC (Bulletin Officiel de la Cote) — page 1 uniquement.

Perimetre v1 (ADR-045 / ADR-046) :
  - 3 indices phares : BRVM COMPOSITE, BRVM 30, BRVM PRESTIGE
  - agregats marche ACTIONS et OBLIGATIONS (capitalisation, volume, valeur, breadth)
  - indices par compartiment : BRVM-PRESTIGE, BRVM-PRINCIPAL
  - indice total return : BRVM - COMPOSITE TOTAL RETURN
  - 7 indices sectoriels + PER moyen par secteur
  - indicateurs de marche (PER moyen, taux rendement, ratios, etc.)

Methode : extraction positionnelle (pymupdf, get_text('words')).
Le flux texte lineaire de ce PDF entrelace les colonnes Actions et Obligations :
un parsing par regex sur le texte brut apparie les mauvaises valeurs. L'appariement
se fait donc par coordonnees (x, y).

Ce script N'ECRIT PAS en base. Il extrait, valide, et emet du JSON.
L'ecriture Supabase fera l'objet d'un script distinct, une fois le schema cible cree.

Usage :
    python3 parse_boc.py --file /tmp/boc/boc_20260810_2.pdf
    python3 parse_boc.py --date 2026-08-10            # telecharge depuis brvm.org
    python3 parse_boc.py --date 2026-08-10 --out boc.json
    python3 parse_boc.py --file X.pdf --strict        # code retour 1 si invariant KO
"""

import argparse
import json
import logging
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

try:
    import fitz  # pymupdf
except ImportError:
    print("ERREUR: pymupdf absent. pip install pymupdf", file=sys.stderr)
    raise

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

URL_TEMPLATE = "https://www.brvm.org/sites/default/files/boc_{ymd}_2.pdf"

# --- Tolerance de regroupement des mots en lignes (points PDF) ---
# Les libelles et valeurs d'une meme ligne visuelle different jusqu'a ~1.5 pt.
Y_TOLERANCE = 2.5

# --- Bornes de colonnes, schema BOC v2026 (refonte du 02/01/2026) ---
# Relevees sur boc_20260810_2.pdf, page 595x842 pt.
ZONE_INDICE_PHARE = {"composite": (110, 200), "brvm30": (300, 405), "prestige": (500, 600)}
ZONE_MARCHE = {"actions": (0, 300), "obligations": (300, 600)}
COL_MARCHE_ACTIONS = {"label": (0, 160), "niveau": (160, 240), "evol": (240, 300)}
COL_MARCHE_OBLIG = {"label": (300, 460), "niveau": (460, 540), "evol": (540, 600)}
COL_INDICE = {
    "label": (0, 140),
    "nb_societes": (140, 200),
    "valeur": (200, 280),
    "evol_jour": (280, 330),
    "evol_annuelle": (330, 390),
    "volume": (390, 455),
    "valeur_transigee": (455, 520),
    "per_moyen": (520, 600),
}

MOIS_FR = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
}

RE_NUM = re.compile(r"^-?\d+(?:[.,]\d+)?$")

LIGNES_MARCHE = [
    ("capitalisation", "capitalisation boursiere"),
    ("volume_echange", "volume echange"),
    ("valeur_transigee", "valeur transigee"),
    ("nb_titres_transiges", "nombre de titres transiges"),
    ("nb_hausse", "nombre de titres en hausse"),
    ("nb_baisse", "nombre de titres en baisse"),
    ("nb_inchanges", "nombre de titres inchanges"),
]

LIGNES_INDICATEURS = [
    ("per_moyen_marche", "per moyen du marche"),
    ("taux_rendement_moyen", "taux de rendement moyen du marche"),
    ("taux_rentabilite_moyen", "taux de rentabilite moyen du marche"),
    ("nb_societes_cotees", "nombre de societes cotees"),
    ("nb_lignes_obligataires", "nombre de lignes obligataires"),
    ("volume_moyen_annuel_seance", "volume moyen annuel par seance"),
    ("valeur_moyenne_annuelle_seance", "valeur moyenne annuelle par seance"),
    ("ratio_liquidite", "ratio moyen de liquidite"),
    ("ratio_satisfaction", "ratio moyen de satisfaction"),
    ("ratio_tendance", "ratio moyen de tendance"),
    ("ratio_couverture", "ratio moyen de couverture"),
    ("taux_rotation", "taux de rotation moyen du marche"),
    ("prime_risque", "prime de risque du marche"),
    ("nb_sgi", "nombre de sgi participantes"),
]

SECTEURS_ATTENDUS = [
    "BRVM - TELECOMMUNICATIONS",
    "BRVM - CONSOMMATION DISCRETIONNAIRE",
    "BRVM - SERVICES FINANCIERS",
    "BRVM - CONSOMMATION DE BASE",
    "BRVM - INDUSTRIELS",
    "BRVM - ENERGIE",
    "BRVM - SERVICES PUBLICS",
]


class SchemaBocInconnu(Exception):
    """Le bulletin ne suit pas le schema v2026 attendu."""


def norm(texte):
    """Minuscule, sans accent, espaces normalises — pour comparer des libelles."""
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFD", texte)
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sans_accent.lower()).strip()


def extraire_lignes(page):
    """Regroupe les mots de la page en lignes par proximite verticale.

    Retourne une liste de (y_moyen, [(x0, x1, mot), ...]) triee par y.
    """
    mots = page.get_text("words")  # (x0, y0, x1, y1, mot, block, line, word)
    if not mots:
        raise SchemaBocInconnu("page 1 sans mot extractible (PDF image ?)")

    mots = sorted(mots, key=lambda m: (m[1], m[0]))
    lignes = []
    courante, y_ref = [], None

    for x0, y0, x1, _y1, mot, *_ in mots:
        if y_ref is None or abs(y0 - y_ref) <= Y_TOLERANCE:
            courante.append((x0, x1, mot))
            y_ref = y0 if y_ref is None else y_ref
        else:
            lignes.append((y_ref, sorted(courante)))
            courante, y_ref = [(x0, x1, mot)], y0

    if courante:
        lignes.append((y_ref, sorted(courante)))
    return lignes


def texte_zone(mots, x_min, x_max):
    """Concatene les mots dont x0 est dans [x_min, x_max)."""
    return " ".join(m for x0, _x1, m in mots if x_min <= x0 < x_max)


def nombre_zone(mots, x_min, x_max):
    """Reconstruit le nombre d'une zone.

    Les milliers sont separes par des espaces dans le PDF et ressortent en mots
    distincts : '18','895','907','784','609' -> 18895907784609.
    Le signe % est un mot separe, exclu par RE_NUM.
    """
    fragments = [m for x0, _x1, m in mots if x_min <= x0 < x_max and RE_NUM.match(m)]
    if not fragments:
        return None
    brut = "".join(fragments).replace(",", ".")
    try:
        valeur = float(brut)
    except ValueError:
        logger.debug("nombre illisible en zone [%s,%s): %r", x_min, x_max, fragments)
        return None
    return valeur


def parser_date_seance(lignes):
    """Extrait la date de seance et le numero de bulletin (ligne d'en-tete)."""
    for _y, mots in lignes[:5]:
        texte = norm(texte_zone(mots, 0, 600))
        m = re.search(r"(\d{1,2})\s+([a-z]+)\s+(20\d{2})", texte)
        if not m:
            continue
        jour, mois_txt, annee = int(m.group(1)), m.group(2), int(m.group(3))
        if mois_txt not in MOIS_FR:
            continue
        num = None
        m_num = re.search(r"n[°o]\s*(\d+)", texte)
        if m_num:
            num = int(m_num.group(1))
        return date(annee, MOIS_FR[mois_txt], jour), num
    raise SchemaBocInconnu("date de seance introuvable en tete de page 1")


def verifier_schema(lignes):
    """Rejette les bulletins anterieurs a la refonte du 02/01/2026.

    ADR-046 : la taxonomie sectorielle est passee de 8 a 7 categories et les
    indices phares de (BRVM 10, Composite) a (Composite, 30, Prestige).
    Un parsing v2026 applique a un bulletin v2022 produirait des valeurs
    silencieusement fausses.
    """
    texte_page = norm(" ".join(texte_zone(mots, 0, 600) for _y, mots in lignes))

    if "brvm 10" in texte_page:
        raise SchemaBocInconnu(
            "bulletin au schema pre-2026 (BRVM 10 present) — parser v2026 inapplicable"
        )
    for ancien in ("brvm - industrie ", "brvm - transport", "brvm - agriculture",
                   "brvm - distribution", "brvm - petites capitalisations"):
        if ancien in texte_page:
            raise SchemaBocInconnu(
                f"taxonomie sectorielle pre-2025 detectee ({ancien.strip()!r})"
            )
    if "brvm prestige" not in texte_page:
        raise SchemaBocInconnu("BRVM PRESTIGE absent — structure inattendue")
    return True


def parser_indices_phares(lignes):
    """Les 3 indices phares : valeur, variation jour, variation annuelle."""
    resultat = {
        "BRVM_COMPOSITE": {"zone": "composite"},
        "BRVM_30": {"zone": "brvm30"},
        "BRVM_PRESTIGE": {"zone": "prestige"},
    }
    champs = {}

    for _y, mots in lignes:
        if _y > 140:
            break
        texte = norm(texte_zone(mots, 0, 600))
        if "variation jour" in texte:
            champs["var_jour_pct"] = mots
        elif "variation annuelle" in texte:
            champs["var_annuelle_pct"] = mots
        elif "brvm composite" in texte or "brvm prestige" in texte:
            champs["valeur"] = mots

    if "valeur" not in champs:
        raise SchemaBocInconnu("ligne des indices phares introuvable")

    for nom, meta in resultat.items():
        x_min, x_max = ZONE_INDICE_PHARE[meta.pop("zone")]
        for champ, mots in champs.items():
            meta[champ] = nombre_zone(mots, x_min, x_max)
    return resultat


def parser_agregats_marche(lignes):
    """Blocs Actions et Obligations : niveau + evolution jour, 7 lignes chacun."""
    sortie = {"ACTIONS": {}, "OBLIGATIONS": {}}

    for _y, mots in lignes:
        if not (270 <= _y <= 365):
            continue
        for marche, cols in (("ACTIONS", COL_MARCHE_ACTIONS),
                             ("OBLIGATIONS", COL_MARCHE_OBLIG)):
            label = norm(texte_zone(mots, *cols["label"]))
            for cle, motif in LIGNES_MARCHE:
                if label.startswith(motif):
                    sortie[marche][cle] = nombre_zone(mots, *cols["niveau"])
                    sortie[marche][f"{cle}_evol_jour_pct"] = nombre_zone(
                        mots, *cols["evol"])
                    break
    return sortie


def _ligne_indice(mots):
    """Extrait les 7 colonnes numeriques d'une ligne d'indice."""
    return {
        cle: nombre_zone(mots, *bornes)
        for cle, bornes in COL_INDICE.items()
        if cle != "label"
    }


def parser_indices_tables(lignes):
    """Compartiments, total return et sectoriels — meme grille de colonnes."""
    compartiments, total_return, sectoriels = {}, {}, {}

    for _y, mots in lignes:
        if _y < 480:
            continue
        label = texte_zone(mots, *COL_INDICE["label"]).strip()
        label_n = norm(label)

        if label_n.startswith("(**)"):  # note de bas de tableau
            continue

        if label_n.startswith("brvm-prestige") or label_n.startswith("brvm-principal"):
            compartiments[label.replace(" (**)", "").strip()] = _ligne_indice(mots)
        elif "composite total return" in label_n:
            total_return["BRVM - COMPOSITE TOTAL RETURN"] = _ligne_indice(mots)
        # Certains bulletins perdent une lettre du libelle a l'encodage
        # (ex. 15/07/2026 : "RVM - CONSOMMATION DE BASE"). On accepte donc
        # aussi la forme tronquee, sinon le secteur disparait silencieusement.
        elif (label_n.startswith("brvm -") or label_n.startswith("brvm-")
              or label_n.startswith("rvm -")):
            propre = re.sub(r"\s*\(\*\*\)\s*", "", label).strip()
            if propre.upper().startswith("RVM "):
                propre = "B" + propre
            if norm(propre) in {norm(s) for s in SECTEURS_ATTENDUS}:
                sectoriels[propre] = _ligne_indice(mots)

    return compartiments, total_return, sectoriels


def parser_indicateurs(lignes):
    """Bas de page : deux tableaux d'indicateurs, apparies par libelle.

    Volontairement label-based et non positionnel : ce bloc est moins regulier
    que les tableaux d'indices, et la derniere valeur numerique de la zone suffit.
    """
    sortie = {}
    for _y, mots in lignes:
        if _y < 640:
            continue
        for x_min, x_max in ((0, 300), (300, 600)):
            label = norm(texte_zone(mots, x_min, x_max))
            for cle, motif in LIGNES_INDICATEURS:
                if cle in sortie:
                    continue
                if label.startswith(motif):
                    val = nombre_zone(mots, x_min + 130, x_max)
                    if val is not None:
                        sortie[cle] = val
                    break
    return sortie


def controles_coherence(data):
    """Invariants arithmetiques internes au bulletin.

    Ces egalites doivent tenir par construction. Une seule qui casse signale un
    appariement de colonnes errone — c'est le garde-fou contre l'echec silencieux.
    """
    controles = []

    def ajouter(nom, gauche, droite, tol=0.5):
        if gauche is None or droite is None:
            controles.append({"controle": nom, "statut": "INDISPONIBLE",
                              "gauche": gauche, "droite": droite})
            return
        ok = abs(gauche - droite) <= tol
        controles.append({
            "controle": nom,
            "statut": "OK" if ok else "ECHEC",
            "gauche": gauche, "droite": droite,
        })

    for marche in ("ACTIONS", "OBLIGATIONS"):
        bloc = data["agregats_marche"].get(marche, {})
        parts = [bloc.get("nb_hausse"), bloc.get("nb_baisse"), bloc.get("nb_inchanges")]
        somme = sum(p for p in parts if p is not None) if all(
            p is not None for p in parts) else None
        ajouter(f"breadth_{marche.lower()}", somme, bloc.get("nb_titres_transiges"))

    sect = data["indices_sectoriels"]
    nb = [v.get("nb_societes") for v in sect.values()]
    somme_nb = sum(n for n in nb) if nb and all(n is not None for n in nb) else None
    ajouter("societes_sectorielles_vs_cotees",
            somme_nb, data["indicateurs"].get("nb_societes_cotees"))

    # Le bloc du haut totalise "Actions & Droits", les compartiments ne
    # totalisent que les actions. Quand le marche des droits cote (observe du
    # 28/04 au 09/06/2026), le total du haut est superieur — ce n'est pas une
    # erreur de parsing. L'invariant ne vaut donc que dans un sens : la somme
    # des compartiments ne peut pas DEPASSER le total, et l'ecart mesure
    # l'activite du marche des droits.
    comp = data["indices_compartiments"]
    for champ, nom in (("volume", "volume"), ("valeur_transigee", "valeur")):
        vals = [v.get(champ) for v in comp.values()]
        somme = sum(v for v in vals) if vals and all(v is not None for v in vals) else None
        cible = data["agregats_marche"].get("ACTIONS", {}).get(
            "volume_echange" if champ == "volume" else "valeur_transigee")
        if somme is None or cible is None:
            controles.append({"controle": f"compartiments_{nom}_vs_total_actions",
                              "statut": "INDISPONIBLE",
                              "gauche": somme, "droite": cible})
        elif somme > cible + 1.0:
            controles.append({"controle": f"compartiments_{nom}_vs_total_actions",
                              "statut": "ECHEC",
                              "gauche": somme, "droite": cible})
        else:
            controles.append({"controle": f"compartiments_{nom}_vs_total_actions",
                              "statut": "OK",
                              "gauche": somme, "droite": cible})

    ajouter("nb_secteurs", float(len(sect)), 7.0, tol=0.0)

    # Recoupement des indices phares contre le tableau des compartiments.
    # Les deux blocs sont independants dans le document : un ecart signale un
    # appariement de colonnes errone dans l'encadre du haut.
    prestige_haut = data["indices_phares"].get("BRVM_PRESTIGE", {}).get("valeur")
    prestige_bas = comp.get("BRVM-PRESTIGE", {}).get("valeur")
    ajouter("prestige_phare_vs_compartiment", prestige_haut, prestige_bas, tol=0.01)

    # Le Composite est un indice de prix, le Total Return reinvestit les
    # dividendes : les deux divergent les jours de detachement (ecarts observes
    # de 5 a 8 pb les 03 et 05/08/2026). L'egalite stricte est donc fausse — la
    # tolerance vise a detecter un appariement de colonnes errone (ecart de
    # plusieurs points), pas l'ecart economique normal entre les deux indices.
    composite_haut = data["indices_phares"].get("BRVM_COMPOSITE", {}).get("var_jour_pct")
    tr = data["indice_total_return"].get("BRVM - COMPOSITE TOTAL RETURN", {})
    # Amplitude observee en pleine saison de distribution : 1.51 pt le
    # 22/05/2026 (Composite -0.13 %, TR +1.38 %, veille de l'AG SICOR),
    # 0.63 pt le 05/06. La tolerance couvre le detachement de dividendes ;
    # un appariement de colonnes errone produirait un ecart d'un autre ordre
    # de grandeur (plusieurs dizaines de points).
    ajouter("composite_evol_vs_total_return", composite_haut, tr.get("evol_jour"),
            tol=3.0)

    # Garde-fou d'ordre de grandeur : un libelle numerique capte dans une zone de
    # valeur (ex. le '30' de 'BRVM 30') produit une valeur hors plage plausible.
    for nom, meta in data["indices_phares"].items():
        val = meta.get("valeur")
        if val is not None and not (50.0 <= val <= 5000.0):
            controles.append({"controle": f"plage_{nom}", "statut": "ECHEC",
                              "gauche": val, "droite": "50-5000"})

    return controles


def parser_boc(chemin_pdf):
    """Parse la page 1 d'un BOC. Retourne un dict serialisable."""
    with fitz.open(chemin_pdf) as doc:
        if doc.page_count < 1:
            raise SchemaBocInconnu("PDF vide")
        lignes = extraire_lignes(doc[0])

    verifier_schema(lignes)
    date_seance, numero = parser_date_seance(lignes)
    compartiments, total_return, sectoriels = parser_indices_tables(lignes)

    data = {
        "date_seance": date_seance.isoformat(),
        "bulletin_numero": numero,
        "source_fichier": str(chemin_pdf),
        "schema_version": "v2026",
        "indices_phares": parser_indices_phares(lignes),
        "agregats_marche": parser_agregats_marche(lignes),
        "indices_compartiments": compartiments,
        "indice_total_return": total_return,
        "indices_sectoriels": sectoriels,
        "indicateurs": parser_indicateurs(lignes),
        "parse_timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    data["controles"] = controles_coherence(data)
    return data


def telecharger(jour):
    """Telecharge le BOC du jour donne. 404 = jour non ouvre (ADR-046)."""
    import requests

    url = URL_TEMPLATE.format(ymd=jour.strftime("%Y%m%d"))
    logger.info("GET %s", url)
    reponse = requests.get(url, timeout=60)

    if reponse.status_code == 404:
        logger.warning("404 — pas de bulletin le %s (jour non ouvre)", jour)
        return None
    if reponse.status_code != 200:
        logger.error("HTTP %s sur %s", reponse.status_code, url)
        reponse.raise_for_status()

    cible = Path(f"/tmp/boc/boc_{jour.strftime('%Y%m%d')}_2.pdf")
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_bytes(reponse.content)
    logger.info("%d octets -> %s", len(reponse.content), cible)
    return cible


def main():
    parseur = argparse.ArgumentParser(description="Parser BOC page 1")
    source = parseur.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", help="chemin d'un BOC deja telecharge")
    source.add_argument("--date", help="date de seance AAAA-MM-JJ (telechargement)")
    parseur.add_argument("--out", help="ecrire le JSON dans ce fichier")
    parseur.add_argument("--strict", action="store_true",
                         help="code retour 1 si un controle echoue")
    args = parseur.parse_args()

    if args.file:
        chemin = Path(args.file).expanduser()
        if not chemin.is_file():
            logger.error("fichier introuvable : %s", chemin)
            return 1
    else:
        try:
            jour = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            logger.error("date invalide : %r (attendu AAAA-MM-JJ)", args.date)
            return 1
        chemin = telecharger(jour)
        if chemin is None:
            return 0  # jour non ouvre : sortie normale, pas une erreur

    try:
        data = parser_boc(chemin)
    except SchemaBocInconnu as exc:
        logger.error("schema non reconnu : %s", exc)
        return 1

    rendu = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(rendu, encoding="utf-8")
        logger.info("JSON -> %s", args.out)
    else:
        print(rendu)

    echecs = [c for c in data["controles"] if c["statut"] == "ECHEC"]
    indispo = [c for c in data["controles"] if c["statut"] == "INDISPONIBLE"]

    print("\n--- Controles de coherence ---", file=sys.stderr)
    for controle in data["controles"]:
        print(f"  {controle['statut']:<13} {controle['controle']:<40} "
              f"{controle['gauche']} vs {controle['droite']}", file=sys.stderr)

    if echecs:
        logger.error("%d controle(s) en echec — appariement de colonnes suspect",
                     len(echecs))
        if args.strict:
            return 1
    elif indispo:
        logger.warning("%d controle(s) indisponibles (valeur manquante)", len(indispo))
    else:
        logger.info("tous les controles passent")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ── Cote des actions (pages 3-4) ────────────────────────────────────────────
# Bornes relevees sur boc_20260826_2.pdf (595x842). Le titre peut deborder sur
# la ligne du secteur : on ancre sur le symbole et on lit les nombres par zone.
COLONNES_COTE = {
    "cours_precedent":   (150, 195),
    "cours_ouverture":   (195, 222),
    "cours_cloture":     (222, 255),
    "variation_jour_pct":(255, 285),
    "volume":            (285, 320),
    "valeur_transigee":  (320, 370),
    "cours_reference":   (370, 420),
    "variation_annuelle_pct": (420, 470),
    "dividende_net":     (470, 492),
    "rendement_net_pct": (520, 558),
    "per":               (558, 595),
}
RE_SYMBOLE = re.compile(r"^[A-Z]{3,7}$")


def parser_cote_actions(pages_lignes):
    """Extrait la cote titre par titre des pages actions du BOC.

    pages_lignes : liste de listes de lignes (sortie d'extraire_lignes).
    Retourne [{symbole, cours_cloture, volume, ...}, ...].
    """
    titres = []
    for lignes in pages_lignes:
        for _y, mots in lignes:
            zone_sym = [m for x0, _x1, m in mots if 30 <= x0 < 65]
            if len(zone_sym) != 1:
                continue
            sym = zone_sym[0].strip()
            if not RE_SYMBOLE.match(sym) or sym == "TOTAL":
                continue
            titre = texte_zone(mots, 65, 150).strip() or None
            ligne = {"symbole": sym,
                     "titre": titre,
                     "est_droit": bool(titre and "droit" in norm(titre))}
            for champ, (a, b) in COLONNES_COTE.items():
                ligne[champ] = nombre_zone(mots, a, b)
            if ligne["cours_cloture"] is None:
                logger.debug("%s : cours de cloture illisible, ignore", sym)
                continue
            titres.append(ligne)
    return titres


def controle_cote(titres, volume_page1, valeur_page1, nb_titres_page1):
    """Compare les agregats de la cote a ceux de la page 1 du meme bulletin."""
    vol = sum(t["volume"] or 0 for t in titres)
    val = sum(t["valeur_transigee"] or 0 for t in titres)
    nb = sum(1 for t in titres if (t["volume"] or 0) > 0)
    return [
        {"controle": "nb_titres", "cote": len(titres), "attendu": None},
        {"controle": "volume", "cote": vol, "page1": volume_page1,
         "statut": "OK" if volume_page1 and abs(vol - volume_page1) < 1 else "ECART"},
        {"controle": "valeur_transigee", "cote": val, "page1": valeur_page1,
         "statut": "OK" if valeur_page1 and abs(val - valeur_page1) < 1 else "ECART"},
        {"controle": "nb_transiges", "cote": nb, "page1": nb_titres_page1,
         "statut": "OK" if nb == nb_titres_page1 else "ECART"},
    ]


def pages_cote_actions(doc, seuil=0.70, min_lignes=3):
    """Localise les pages de la cote actions dans un BOC.

    Detection structurelle, sans dependance aux libelles : une page de cote
    actions a des symboles tous distincts et verifie valeur ~ volume x cours
    sur la quasi-totalite de ses lignes. Les pages obligations echouent aux
    deux criteres (symboles repetes, valeur_transigee absente).

    Retourne la liste des index de pages (0-based).
    """
    trouvees = []
    for i in range(len(doc)):
        try:
            lignes = parser_cote_actions([extraire_lignes(doc[i])])
        except SchemaBocInconnu:
            continue
        if len(lignes) < min_lignes:
            continue
        if len({x["symbole"] for x in lignes}) != len(lignes):
            continue
        coherentes = sum(
            1 for x in lignes
            if x["volume"] and x["cours_cloture"] and x["valeur_transigee"]
            and abs(x["valeur_transigee"] - x["volume"] * x["cours_cloture"])
            / max(x["valeur_transigee"], 1) < 0.30
        )
        if coherentes / len(lignes) >= seuil:
            trouvees.append(i)
    return trouvees


def parser_cote_depuis_pdf(chemin_pdf):
    """Ouvre un BOC, localise la cote actions et l'extrait avec sa date.

    Retourne (date_seance, numero_bulletin, [titres], [pages_utilisees]).
    """
    import fitz
    doc = fitz.open(chemin_pdf)
    date_s, num = parser_date_seance(extraire_lignes(doc[0]))
    pages = pages_cote_actions(doc)
    if not pages:
        raise SchemaBocInconnu(f"aucune page de cote actions dans {chemin_pdf}")
    titres = parser_cote_actions([extraire_lignes(doc[i]) for i in pages])
    return date_s, num, titres, pages
