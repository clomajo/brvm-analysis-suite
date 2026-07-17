"""
config/params.py
T7 — Centralisation des constantes du modèle V2 cours cible, précédemment
codées en dur dans calculate_target_price.py.

Inventaire complet des occurrences 0.08/0.70/0.30 dans le repo : voir
REMEDIATION_LOG.md (T7). Seules les constantes ci-dessous, propres au
modèle cours cible V2, ont été centralisées ici. Toute autre occurrence
(pondérations de scoring technique/fondamental dans opportunity_scorer.py,
generate_decisions.py, report_generator.py, etc.) est hors périmètre de
cette tâche — référencée en BACKLOG.md, non modifiée.
"""

TAUX_ACTUALISATION = 0.08   # ADR-009 — origine non traçable, à revoir si taux BCEAO bouge
POIDS_PER = 0.70            # mix cours cible : part du cours PER
POIDS_DIVIDENDE = 0.30      # mix cours cible : part du cours Gordon (dividende actualisé)
