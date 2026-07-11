"""
tests/test_eps.py -- fige le comportement actuel (T2b) de :
  - check_eps_coherence()      (scrape_all_v4.py)
  - evaluer_qualite_eps()      (calculate_target_price.py)

Aucune modification du code de production. Cf. PLAN_REMEDIATION.md T2 phase 2.
"""
from scrape_all_v4 import check_eps_coherence
from calculate_target_price import evaluer_qualite_eps


class TestCheckEpsCoherence:

    def test_eps_coherent_pas_de_warning(self):
        eps_recalcule, warning = check_eps_coherence(
            eps_scraped=100.0,
            net_income=1000,
            shares_outstanding=10_000_000,
            ticker="TEST",
            fy="FY2025",
        )
        assert eps_recalcule == 100.0
        assert warning is None

    def test_ratio_20x_type_ntlc_declenche_warning(self):
        eps_recalcule, warning = check_eps_coherence(
            eps_scraped=2000.0,
            net_income=1000,
            shares_outstanding=10_000_000,
            ticker="NTLC",
            fy="FY2016",
        )
        assert eps_recalcule == 100.0
        assert warning is not None
        assert "NTLC" in warning
        assert "ratio" in warning

    def test_ratio_073x_type_sogc_declenche_warning(self):
        eps_recalcule, warning = check_eps_coherence(
            eps_scraped=73.0,
            net_income=1000,
            shares_outstanding=10_000_000,
            ticker="SOGC",
            fy="FY2022",
        )
        assert eps_recalcule == 100.0
        assert warning is not None
        assert "SOGC" in warning

    def test_shares_outstanding_zero_pas_de_crash_pas_de_warning(self):
        # Comportement REEL actuel (pas la spec idealisee, cf. discussion
        # T2b) : `not shares_outstanding` est True pour 0 -> retourne
        # (None, None) SANS warning. Ecart note, a traiter eventuellement
        # en T4 -- pas corrige ici (T2b = zero modification de code de prod).
        eps_recalcule, warning = check_eps_coherence(
            eps_scraped=100.0,
            net_income=1000,
            shares_outstanding=0,
            ticker="TEST",
            fy="FY2025",
        )
        assert eps_recalcule is None
        assert warning is None

    def test_shares_outstanding_none_pas_de_crash_pas_de_warning(self):
        eps_recalcule, warning = check_eps_coherence(
            eps_scraped=100.0,
            net_income=1000,
            shares_outstanding=None,
            ticker="TEST",
            fy="FY2025",
        )
        assert eps_recalcule is None
        assert warning is None

    def test_eps_scraped_zero_retourne_recalcule_sans_warning(self):
        eps_recalcule, warning = check_eps_coherence(
            eps_scraped=0,
            net_income=1000,
            shares_outstanding=10_000_000,
            ticker="TEST",
            fy="FY2025",
        )
        assert eps_recalcule == 100.0
        assert warning is None


class TestEvaluerQualiteEps:

    def test_une_annee_exploitable_acceptee_sans_controle(self, ticker_rows_factory):
        rows = ticker_rows_factory([("FY2025", 50.0)])
        valide, raison, nb_annees = evaluer_qualite_eps(rows)
        assert valide is True
        assert raison is None
        assert nb_annees == 1

    def test_deux_annees_non_consecutives_rejete(self, ticker_rows_factory):
        rows = ticker_rows_factory([("FY2025", 50.0), ("FY2023", 45.0)])
        valide, raison, nb_annees = evaluer_qualite_eps(rows)
        assert valide is False
        assert "non consécutives" in raison
        assert nb_annees == 0

    def test_collapse_plus_80_pct_yoy_rejete(self, ticker_rows_factory):
        rows = ticker_rows_factory([("FY2025", 19.66), ("FY2024", 480.0)])
        valide, raison, nb_annees = evaluer_qualite_eps(rows)
        assert valide is False
        assert "collapse" in raison
        assert nb_annees == 0

    def test_trois_annees_consecutives_sans_collapse_accepte(self, ticker_rows_factory):
        rows = ticker_rows_factory([
            ("FY2025", 100.0), ("FY2024", 95.0), ("FY2023", 90.0),
        ])
        valide, raison, nb_annees = evaluer_qualite_eps(rows)
        assert valide is True
        assert raison is None
        assert nb_annees == 3

    def test_aucune_annee_exploitable_rejete(self):
        valide, raison, nb_annees = evaluer_qualite_eps([])
        assert valide is False
        assert raison == "aucune année EPS exploitable"
        assert nb_annees == 0

    def test_eps_none_ignore_dans_le_comptage(self):
        rows = [
            {"fiscal_year": "FY2025", "eps": None},
            {"fiscal_year": "FY2024", "eps": 50.0},
        ]
        valide, raison, nb_annees = evaluer_qualite_eps(rows)
        assert valide is True
        assert nb_annees == 1
