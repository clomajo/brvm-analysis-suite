"""
Saisie manuelle MENSUELLE du P/E sectoriel BRVM, depuis le Tableau de Bord
quotidien BOA Capital Securities, vers la table Supabase sector_per_history.

Pourquoi mensuel : le P/E sectoriel reflète des résultats annuels clôturés (ex: "2024")
agrégés sur plusieurs sociétés par secteur (jusqu'à 15 pour Services Financiers) — il
dérive lentement. Une cadence mensuelle suffit à capter une dérive de marché (rally,
correction) sans la charge d'un geste hebdomadaire ou quotidien.

Usage (1 fois par mois, ex: le 1er du mois en lisant le Tableau de Bord du jour) :
    cd ~/Desktop/brvm-analysis-suite
    python3 update_sector_per.py

Prérequis : SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY dans le .env du projet.
"""

import os
import requests
from datetime import date
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://lynevvhmstpcffobwudr.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_KEY:
    raise SystemExit("SUPABASE_SERVICE_ROLE_KEY introuvable dans le .env.")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",  # upsert si même secteur+date déjà saisi aujourd'hui
}

SECTEURS = [
    "CONSOMMATION_DE_BASE",
    "CONSOMMATION_DISCRETIONNAIRE",
    "ENERGIE",
    "INDUSTRIELS",
    "SERVICES_FINANCIERS",
    "SERVICES_PUBLICS",
    "TELECOMMUNICATIONS",
]


def main():
    print("=== Saisie mensuelle des P/E sectoriels (source : Tableau de Bord BOA) ===")
    print("Entrer le P/E 2024 affiché pour chaque secteur (ex: 6.5). Laisser vide pour passer.\n")

    rows = []
    today = date.today().isoformat()

    for secteur in SECTEURS:
        label = secteur.replace("_", " ").title()
        raw = input(f"  {label:32s} P/E 2024 : ").strip().replace(",", ".")
        if not raw:
            print(f"    → ignoré (pas de valeur saisie)")
            continue
        try:
            value = float(raw)
        except ValueError:
            print(f"    ⚠️  Valeur invalide '{raw}', ignorée.")
            continue
        rows.append({
            "secteur": secteur,
            "per_2024": value,
            "date_releve": today,
            "source": "boa_tableau_de_bord",
        })

    if not rows:
        print("\nAucune valeur saisie, rien à envoyer.")
        return

    print(f"\n→ Envoi de {len(rows)} ligne(s) vers Supabase...")
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/sector_per_history",
        headers=HEADERS,
        json=rows,
    )
    if resp.status_code in (200, 201):
        print("✅ Enregistré avec succès.")
    else:
        print(f"❌ Erreur ({resp.status_code}) : {resp.text}")


if __name__ == "__main__":
    main()
