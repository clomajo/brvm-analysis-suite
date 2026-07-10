"""
tests/test_parsing.py -- fige le comportement actuel (T2b) de :
  - BRVMAnalyzer._parse_date_from_titre()  (fundamental_analyzer.py)

Aucune modification du code de production.
"""
from datetime import date

from fundamental_analyzer import BRVMAnalyzer


def _analyzer():
    # _parse_date_from_titre ne fait aucun self. (confirme T2a) -> pas
    # besoin d'appeler __init__ (qui, lui, ouvrirait potentiellement une
    # connexion psycopg2). __new__ suffit pour obtenir une instance utilisable.
    return BRVMAnalyzer.__new__(BRVMAnalyzer)


class TestParseDateFromTitre:

    def test_rapport_annuel(self):
        a = _analyzer()
        assert a._parse_date_from_titre("Rapport d'activités annuel - Exercice 2024") == date(2024, 12, 31)

    def test_etats_financiers(self):
        a = _analyzer()
        assert a._parse_date_from_titre("États financiers au 31 décembre 2024") == date(2024, 12, 31)

    def test_premier_trimestre(self):
        a = _analyzer()
        assert a._parse_date_from_titre("Rapport d'activités - 1er trimestre 2026") == date(2026, 3, 31)

    def test_troisieme_trimestre(self):
        a = _analyzer()
        assert a._parse_date_from_titre("Rapport d'activités - 3ème trimestre 2025") == date(2025, 9, 30)

    def test_deuxieme_trimestre(self):
        a = _analyzer()
        assert a._parse_date_from_titre("Rapport d'activités - 2ème trimestre 2025") == date(2025, 6, 30)

    def test_premier_semestre(self):
        a = _analyzer()
        assert a._parse_date_from_titre("Rapport d'activités - 1er semestre 2025") == date(2025, 6, 30)

    def test_titre_sans_date_retourne_none(self):
        a = _analyzer()
        assert a._parse_date_from_titre("Communiqué de presse") is None

    def test_titre_vide_ou_nul_retourne_none(self):
        a = _analyzer()
        assert a._parse_date_from_titre("") is None
        assert a._parse_date_from_titre(None) is None

    def test_titre_avec_annee_type_non_reconnu_fallback_31_decembre(self):
        a = _analyzer()
        assert a._parse_date_from_titre("Communiqué financier 2024") == date(2024, 12, 31)
