"""
killswitch_check.py
--------------------
T10 (Volet B) — Kill-switch V1 : suspend l'alerte si la performance récente
des signaux V1 (mesurée en alpha vs benchmark, cf. T16) se dégrade.

PORTÉE / LIMITE CONNUE :
  brvm_decisions_results ne contient aujourd'hui que des vérifications de
  signaux V1 (signal ACHAT/SURVEILLER/ÉVITER dérivé du score composite).
  V2 (cours cible) n'a pas encore de vérifications propres en production —
  il reste en phase de validation statistique (T6 : IC95% non concluant à
  n=25). Ce kill-switch surveille donc V1 uniquement. Un kill-switch dédié
  à V2 (ou à une éventuelle combinaison V1/V2) devra être ajouté séparément
  le jour où V2 aura ses propres résultats vérifiés en base — décision
  explicitement reportée (cf. session 28/07/2026, DECISIONS.md ADR-036).

CRITÈRE (aligné sur T16, alpha vs benchmark plutôt que rendement brut) :
  Sur les N derniers signaux vérifiés (brvm_decisions_results, alpha non
  NULL) :
    - % positifs = proportion de lignes avec alpha > 0
    - médiane = médiane de alpha sur ces lignes
  Si n >= N_MIN ET (% positifs < SEUIL_POSITIFS OU médiane < SEUIL_MEDIANE)
    -> KILL-SWITCH DÉCLENCHÉ, exit(1)
  Sinon -> statut normal affiché, exit(0)

Exécution : step hebdomadaire GitHub Actions (lundi, if: always()) ET
exécutable manuellement en local.

Variables d'environnement requises :
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
"""

import logging
import os
import statistics
import sys

from dotenv import find_dotenv, load_dotenv
from supabase import create_client

# ----------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("killswitch_check")

load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------------------------------------------------------------
# Constantes (T10, confirmées par Jocelyn le 28/07/2026)
# ----------------------------------------------------------------------

N_MIN = 15              # nombre minimum de signaux vérifiés avant d'évaluer
SEUIL_POSITIFS = 0.50   # proportion minimale de alpha > 0
SEUIL_MEDIANE = 0.0     # médiane minimale de alpha

# Fenêtre : nombre de derniers signaux vérifiés pris en compte.
# Choix : pas de fenêtre temporelle stricte (ex. "30 derniers jours"), mais
# un nombre de LIGNES récentes (triées par verification_date desc), pour
# garantir un n stable même si le pipeline a des jours creux (week-ends,
# jours fériés BRVM, pannes ponctuelles).
FENETRE_N_SIGNAUX = 100


def get_recent_alpha_values():
    """
    Récupère les N derniers signaux vérifiés avec alpha renseigné
    (non NULL), triés du plus récent au plus ancien.
    """
    resp = (
        supabase.table("brvm_decisions_results")
        .select("ticker, verification_date, alpha")
        .not_.is_("alpha", "null")
        .order("verification_date", desc=True)
        .limit(FENETRE_N_SIGNAUX)
        .execute()
    )
    return resp.data


def evaluate_killswitch(rows):
    """
    Applique le critère de déclenchement sur une liste de lignes
    {ticker, verification_date, alpha}.

    Retourne (declenche: bool, n: int, pct_positifs: float, mediane: float)
    ou (None, n, None, None) si n < N_MIN (pas assez de données).
    """
    n = len(rows)

    if n < N_MIN:
        return None, n, None, None

    alphas = [r["alpha"] for r in rows]
    pct_positifs = sum(1 for a in alphas if a > 0) / n
    mediane = statistics.median(alphas)

    declenche = (pct_positifs < SEUIL_POSITIFS) or (mediane < SEUIL_MEDIANE)

    return declenche, n, pct_positifs, mediane


def main():
    logger.info("Kill-switch V1 — démarrage")
    logger.info(
        "Constantes : N_MIN=%d, SEUIL_POSITIFS=%.2f, SEUIL_MEDIANE=%.2f, "
        "FENETRE_N_SIGNAUX=%d",
        N_MIN, SEUIL_POSITIFS, SEUIL_MEDIANE, FENETRE_N_SIGNAUX,
    )
    logger.info(
        "PORTÉE : surveillance V1 uniquement (brvm_decisions_results ne "
        "contient pas encore de vérifications V2 — cf. ADR-036)."
    )

    rows = get_recent_alpha_values()
    declenche, n, pct_positifs, mediane = evaluate_killswitch(rows)

    if declenche is None:
        print(f"ℹ️  STATUT : données insuffisantes (n={n} < N_MIN={N_MIN}) "
              f"— kill-switch non évaluable, aucune alerte.")
        sys.exit(0)

    if declenche:
        print("🔴 KILL-SWITCH DÉCLENCHÉ — suspendre les achats V1")
        print(f"   n={n} | %positifs(alpha>0)={pct_positifs*100:.1f}% "
              f"(seuil {SEUIL_POSITIFS*100:.0f}%) | "
              f"médiane(alpha)={mediane:+.2f} pts (seuil {SEUIL_MEDIANE:+.2f})")
        sys.exit(1)
    else:
        print("🟢 STATUT NORMAL — aucune alerte")
        print(f"   n={n} | %positifs(alpha>0)={pct_positifs*100:.1f}% "
              f"(seuil {SEUIL_POSITIFS*100:.0f}%) | "
              f"médiane(alpha)={mediane:+.2f} pts (seuil {SEUIL_MEDIANE:+.2f})")
        sys.exit(0)


if __name__ == "__main__":
    main()
