"""
tests/test_health.py -- fige le comportement actuel (T2b) de la logique
week-end / jour ferie de health_check.main() (T1).

Aucune modification du code de production. Les appels reseau
(get_supabase_config, get_exact_count, get_missing_tickers) sont mockes :
pour les cas jour ferie / week-end, on verifie explicitement qu'ils ne sont
JAMAIS appeles (main() doit sortir avant).
"""
from datetime import datetime, timezone

import pytest

import health_check


def _freeze(monkeypatch, iso_datetime_utc):
    fixed = datetime.fromisoformat(iso_datetime_utc).replace(tzinfo=timezone.utc)

    class _FrozenDatetime:
        @staticmethod
        def now(tz=None):
            return fixed

    monkeypatch.setattr(health_check, "datetime", _FrozenDatetime)


def _network_calls_must_not_happen(monkeypatch):
    def _fail(*a, **k):
        raise AssertionError(
            "Appel reseau inattendu : week-end/jour ferie doit court-circuiter "
            "avant get_supabase_config()."
        )
    monkeypatch.setattr(health_check, "get_supabase_config", _fail)
    monkeypatch.setattr(health_check, "get_exact_count", _fail)
    monkeypatch.setattr(health_check, "get_missing_tickers", _fail)


class TestMainWeekendJourFerie:

    def test_jour_ferie_exit_0_sans_appel_reseau(self, monkeypatch):
        # 2026-01-01 = Jour de l'an, present dans JOURS_FERIES_BRVM_2026
        _freeze(monkeypatch, "2026-01-01T10:00:00")
        _network_calls_must_not_happen(monkeypatch)
        monkeypatch.setattr(health_check, "write_report", lambda md: None)

        with pytest.raises(SystemExit) as exc_info:
            health_check.main()
        assert exc_info.value.code == 0

    def test_weekend_samedi_exit_0_sans_appel_reseau(self, monkeypatch):
        # 2026-01-03 est un samedi (2026-01-01 est un jeudi)
        _freeze(monkeypatch, "2026-01-03T10:00:00")
        _network_calls_must_not_happen(monkeypatch)
        monkeypatch.setattr(health_check, "write_report", lambda md: None)

        with pytest.raises(SystemExit) as exc_info:
            health_check.main()
        assert exc_info.value.code == 0

    def test_jour_ouvre_vide_exit_1(self, monkeypatch):
        # 2026-01-05 est un lundi, ni ferie ni week-end -> bilan calcule
        _freeze(monkeypatch, "2026-01-05T10:00:00")
        monkeypatch.setattr(health_check, "get_supabase_config", lambda: ("https://test.invalid", {}))
        monkeypatch.setattr(health_check, "get_exact_count", lambda *a, **k: 0)
        monkeypatch.setattr(health_check, "get_missing_tickers", lambda *a, **k: [])
        monkeypatch.setattr(health_check, "write_report", lambda md: None)

        with pytest.raises(SystemExit) as exc_info:
            health_check.main()
        # nb_prices=0 sur jour ouvre -> zero_prices_on_business_day -> exit 1
        assert exc_info.value.code == 1
