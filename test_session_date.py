"""Tests de session_date.py (sans dépendance : python test_session_date.py)."""
import os
import sys
from datetime import date, datetime, timezone

os.environ.pop("SESSION_DATE", None)
os.environ.pop("FORCER_COLLECTE", None)
from session_date import date_seance, seance_en_cours


def utc(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


CAS = [
    # (heure UTC, date de séance attendue, séance en cours ?)
    ("2026-11-17 18:00", "2026-11-17", False),  # mardi 18h : cron nominal
    ("2026-11-17 23:57", "2026-11-17", False),  # run tardif avant minuit
    ("2026-11-18 00:23", "2026-11-17", False),  # run tardif après minuit (#292)
    ("2026-11-20 00:11", "2026-11-19", False),  # run tardif du 20/11 (#294)
    ("2026-11-10 01:05", "2026-11-09", False),  # run tardif du lundi 9 (#286)
    ("2026-11-21 00:30", "2026-11-20", False),  # vendredi tardif -> samedi 00h30
    ("2026-11-21 10:00", "2026-11-20", False),  # samedi
    ("2026-11-22 20:00", "2026-11-20", False),  # dimanche
    ("2026-11-23 00:30", "2026-11-20", False),  # lundi avant ouverture
    ("2026-11-23 08:59", "2026-11-20", False),
    ("2026-11-23 09:00", "2026-11-20", True),   # ouverture
    ("2026-11-23 15:59", "2026-11-20", True),   # séance en cours
    ("2026-11-23 16:00", "2026-11-23", False),  # clôture
]

echecs = 0
for h, attendu, en_cours in CAS:
    obtenu = date_seance(utc(h))
    ok = obtenu == date.fromisoformat(attendu) and seance_en_cours(utc(h)) == en_cours
    echecs += not ok
    print(f"{'OK  ' if ok else 'FAIL'} {h} -> {obtenu} (attendu {attendu}, en_cours={en_cours})")

os.environ["SESSION_DATE"] = "2026-10-26"
ok = date_seance(utc("2026-11-23 18:00")) == date(2026, 10, 26)
echecs += not ok
print(f"{'OK  ' if ok else 'FAIL'} SESSION_DATE explicite")
del os.environ["SESSION_DATE"]

os.environ["FORCER_COLLECTE"] = "1"
ok = date_seance(utc("2026-11-23 10:00")) == date(2026, 11, 23)
echecs += not ok
print(f"{'OK  ' if ok else 'FAIL'} FORCER_COLLECTE pendant la séance -> aujourd'hui")
ok = date_seance(utc("2026-11-24 00:20")) == date(2026, 11, 23)
echecs += not ok
print(f"{'OK  ' if ok else 'FAIL'} FORCER_COLLECTE hors séance : règle normale")

print(f"\n{'TOUT OK' if not echecs else str(echecs) + ' ECHEC(S)'}")
sys.exit(1 if echecs else 0)
