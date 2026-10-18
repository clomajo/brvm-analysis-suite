# -*- coding: utf-8 -*-
"""
fundamental_periode.py -- exercice, periode et type d'un rapport BRVM, lus dans son titre.

Fonction pure (aucun reseau, aucune base). Voir ADR-060.

    lire_titre("BOA CI : Rapport d'activites - 1er semestre 2026")
    -> RapportPeriode(fiscal_year=2026, periode='S1', period_end=date(2026, 6, 30),
                      type_rapport='ACTIVITES')

Renvoie None quand le titre ne permet pas de conclure (aucune annee, plusieurs
annees, periode introuvable). L'appelant doit alors mettre le rapport en revue
manuelle : ne jamais deviner un exercice.
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Optional

# (periode, mois de cloture, jour de cloture)
_FIN = {
    "T1": (3, 31), "T2": (6, 30), "T3": (9, 30), "T4": (12, 31),
    "S1": (6, 30), "S2": (12, 31), "FY": (12, 31),
}


@dataclass(frozen=True)
class RapportPeriode:
    fiscal_year: int
    periode: str          # T1 T2 T3 T4 S1 S2 FY
    period_end: date
    type_rapport: Optional[str]
    source: str = "titre"            # "titre" ou "url"
    publie_le: Optional[date] = None  # date de publication lue dans l'URL (AAAAMMJJ_...)


def _norm(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", txt.lower().replace("’", "'")).strip()


_RANG = r"(?:1er|1ere|1|premier|premiere|2eme|2e|2nd|2nde|2|deuxieme|second|seconde|3eme|3e|3|troisieme|4eme|4e|4|quatrieme)"


def _rang(mot: str) -> int:
    mot = mot.strip()
    if mot[0] == "1" or mot.startswith("premi"):
        return 1
    if mot[0] == "2" or mot.startswith(("deux", "second")):
        return 2
    if mot[0] == "3" or mot.startswith("trois"):
        return 3
    return 4


def _periode(t: str) -> Optional[str]:
    # Trimestres et semestres d'abord : un "etat financier" intermediaire
    # (ex. 1er semestre 2026) ne doit pas etre pris pour un exercice complet.
    m = re.search(rf"({_RANG})\s*(?:er|ere|eme|e|nd|nde)?\s*trimestre", t)
    if m:
        return f"T{_rang(m.group(1))}"
    m = re.search(rf"({_RANG})\s*(?:er|ere|eme|e|nd|nde)?\s*semestre", t)
    if m:
        r = _rang(m.group(1))
        return "S1" if r == 1 else "S2" if r == 2 else None
    m = re.search(r"\bt([1-4])\b", t)          # forme courte des noms de fichier : "t1-2026"
    if m:
        return f"T{m.group(1)}"
    m = re.search(r"\bs([12])\b", t)
    if m:
        return f"S{m.group(1)}"
    if re.search(r"\bannuel(?:le)?s?\b|\bexercice\b", t):
        return "FY"
    return None


def _type(t: str) -> Optional[str]:
    if "examen limite" in t:
        return "EXAMEN_LIMITE"
    if "commissaire" in t:
        return "CAC"
    if "etats financiers" in t or "etat financier" in t:
        return "ETATS_FIN"
    if "commentaire" in t:
        return "COMMENTAIRE"
    if "activite" in t:
        return "ACTIVITES"
    return None


def lire_titre(titre: str) -> Optional[RapportPeriode]:
    t = _norm(titre)
    annees = {int(a) for a in re.findall(r"(?<!\d)(20\d{2})(?!\d)", t)}
    if len(annees) != 1:
        return None
    periode = _periode(t)
    if periode is None:
        return None
    annee = annees.pop()
    mois, jour = _FIN[periode]
    return RapportPeriode(annee, periode, date(annee, mois, jour), _type(t))


_TITRE_GENERIQUE = {"", "telecharger"}


def _slug_url(url: str):
    """Nom de fichier BRVM -> (texte lisible, date de publication ou None)."""
    nom = (url or "").rsplit("/", 1)[-1]
    nom = re.sub(r"\.pdf$", "", nom, flags=re.I)
    publie = None
    m = re.match(r"(20\d{2})(\d{2})(\d{2})(?=[_-])", nom)
    if m:
        try:
            publie = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            publie = None
        nom = nom[m.end():]
    return re.sub(r"[_\-]+", " ", nom), publie


def lire_url(url: str) -> Optional[RapportPeriode]:
    texte, publie = _slug_url(url)
    r = lire_titre(texte)
    if r is None:
        return None
    return RapportPeriode(r.fiscal_year, r.periode, r.period_end, r.type_rapport, "url", publie)


def lire_rapport(titre: Optional[str], url: Optional[str]) -> Optional[RapportPeriode]:
    """Titre d'abord ; adresse du fichier si le titre est absent, generique
    ("Telecharger") ou illisible. None = revue manuelle. Si les deux sont lisibles
    et different, le titre l'emporte mais l'ecart est visible via lire_url()."""
    if _norm(titre) not in _TITRE_GENERIQUE:
        r = lire_titre(titre)
        if r is not None:
            _, publie = _slug_url(url)
            return RapportPeriode(r.fiscal_year, r.periode, r.period_end, r.type_rapport, "titre", publie)
    return lire_url(url)
