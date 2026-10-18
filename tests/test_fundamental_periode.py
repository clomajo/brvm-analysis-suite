"""tests/test_fundamental_periode.py -- lecture exercice / periode / type (ADR-060).
Aucun reseau. Les titres de la premiere serie sont ceux de la page BRVM de BOA CI (18/10/2026)."""
from datetime import date

import pytest

from fundamental_periode import lire_titre


@pytest.mark.parametrize("titre, annee, periode, fin, type_", [
    ("BOA CI : Rapport d'activités - 1er semestre 2026", 2026, "S1", date(2026, 6, 30), "ACTIVITES"),
    ("BOA CI : Rapport d’examen limité des états financiers - 1er semestre 2026", 2026, "S1", date(2026, 6, 30), "EXAMEN_LIMITE"),
    ("BOA CI : Rapport des Commissaires Aux Comptes et Etats Financiers annuels - Exercice 2025", 2025, "FY", date(2025, 12, 31), "CAC"),
    ("BOA CI : Rapport d'activités - 1er trimestre 2026", 2026, "T1", date(2026, 3, 31), "ACTIVITES"),
    ("Rapport d'activités - 3ème trimestre 2025", 2025, "T3", date(2025, 9, 30), "ACTIVITES"),
    ("Rapport d'activités annuel - Exercice 2024", 2024, "FY", date(2024, 12, 31), "ACTIVITES"),
    ("Etats financiers - Exercice 2023", 2023, "FY", date(2023, 12, 31), "ETATS_FIN"),
    ("Etats financiers - 2ème semestre 2024", 2024, "S2", date(2024, 12, 31), "ETATS_FIN"),
    ("Rapport d'activités - 2e trimestre 2026", 2026, "T2", date(2026, 6, 30), "ACTIVITES"),
    ("Rapport d'activités - 4ème trimestre 2025", 2025, "T4", date(2025, 12, 31), "ACTIVITES"),
])
def test_titres_reconnus(titre, annee, periode, fin, type_):
    r = lire_titre(titre)
    assert (r.fiscal_year, r.periode, r.period_end, r.type_rapport) == (annee, periode, fin, type_)


def test_etat_financier_intermediaire_n_est_pas_un_exercice():
    assert lire_titre("Etats financiers - 1er semestre 2026").periode == "S1"


@pytest.mark.parametrize("titre", [
    "",
    None,
    "Commentaires sur l'activité",                       # aucune annee
    "Rapport d'activités - 1er semestre",                # aucune annee
    "Rapport annuel - Exercice 2024-2025",               # deux annees : a revoir a la main
    "Rapport 2026",                                      # annee sans periode
    "Rapport d'activités - 5ème trimestre 2026",         # periode impossible
])
def test_titres_non_concluants_renvoient_none(titre):
    assert lire_titre(titre) is None
