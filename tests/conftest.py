"""
tests/conftest.py

Contrainte T2b : aucune connexion reseau. Toutes les donnees de test sont
des dicts/fixtures en dur.

Note (T2b) : calculate_target_price.py lit SUPABASE_URL et
SUPABASE_SERVICE_ROLE_KEY via os.environ["..."] (acces direct, pas
.getenv()) au niveau module -- un import sans ces variables leve une
KeyError avant meme d'atteindre evaluer_qualite_eps(). On definit donc des
valeurs factices ici, AVANT toute collecte des modules de test par pytest
(conftest.py est garanti charge en premier). Ces valeurs ne sont jamais
utilisees pour un vrai appel reseau : aucun test n'appelle une fonction qui
fait une requete HTTP.
"""
import os

os.environ.setdefault("SUPABASE_URL", "https://test.invalid")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-key-fake")

import pytest


@pytest.fixture
def ticker_rows_factory():
    """
    Fabrique de listes de rows {fiscal_year, eps} pour evaluer_qualite_eps().
    Usage: ticker_rows_factory([("FY2025", 100), ("FY2024", 90), ...])
    """
    def _make(pairs):
        return [{"fiscal_year": fy, "eps": eps} for fy, eps in pairs]
    return _make
