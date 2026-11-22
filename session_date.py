"""Date de séance BRVM : source unique pour tout le pipeline.

Problème traité (runs du 3 au 20/11/2026) : le cron GitHub de 18h00 UTC démarre
avec 4 à 7 h de retard. Passé minuit UTC, date.today() / now() donnent le
lendemain : la séance n'est pas collectée, les tests cherchent des données qui
n'existent pas encore, et les lignes d'indices sont datées d'un jour trop tard.

Règle : la date de séance est celle de la dernière séance CLOSE.
  - jour ouvré à partir de 16h00 UTC          -> aujourd'hui
  - sinon (nuit, matin, séance en cours, week-end) -> jour ouvré précédent
Entre 00h00 et 09h00 UTC la page brvm.org affiche encore la clôture de la
veille (ADR-052) : une collecte tardive est donc datée correctement.

Limite connue : les jours fériés BRVM ne sont pas connus ici. Un jour férié
en semaine donnerait la date de ce jour pour des cours de la séance précédente.

Surcharges :
  SESSION_DATE=AAAA-MM-JJ  date explicite (reprises manuelles)
  FORCER_COLLECTE=1        pendant la séance (09h-16h UTC) : date du jour,
                           comportement historique, volumes partiels
"""
import os
import sys
from datetime import date, datetime, timedelta, timezone

HEURE_OUVERTURE_UTC = 9
HEURE_CLOTURE_UTC = 16


def _maintenant(maintenant=None):
    return maintenant or datetime.now(timezone.utc)


def seance_en_cours(maintenant=None):
    """True un jour ouvré entre 09h00 et 16h00 UTC (volumes partiels)."""
    n = _maintenant(maintenant)
    return n.weekday() < 5 and HEURE_OUVERTURE_UTC <= n.hour < HEURE_CLOTURE_UTC


def _jour_ouvre_precedent(d):
    d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def date_seance(maintenant=None):
    """Date (datetime.date) de la dernière séance close."""
    explicite = os.getenv("SESSION_DATE")
    if explicite:
        return date.fromisoformat(explicite)
    n = _maintenant(maintenant)
    if os.getenv("FORCER_COLLECTE") == "1" and seance_en_cours(n):
        return n.date()
    if n.weekday() < 5 and n.hour >= HEURE_CLOTURE_UTC:
        return n.date()
    return _jour_ouvre_precedent(n.date())


if __name__ == "__main__":
    print(date_seance().isoformat())
    sys.exit(0)
