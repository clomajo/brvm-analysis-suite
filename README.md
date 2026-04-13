# BRVM Analysis Suite

Pipeline automatisé d'analyse quantitative de la BRVM (Bourse Régionale des Valeurs Mobilières).
Alimente la plateforme [BRVM Analytics](https://brvm-analytics.vercel.app).

---

## Architecture

```
brvm.org → data_collector_simple.py → Supabase
                                          ↓
                          technical_analyzer_simple.py
                                          ↓
                          opportunity_scorer_simple.py
                                          ↓
                            generate_decisions.py
                                          ↓
                            verify_decisions.py (J+90)
```

## Prérequis

- Python 3.11
- Compte Supabase avec les tables requises
- Clés API : Supabase, Mistral, Anthropic

## Installation

```bash
git clone https://github.com/clomajo/brvm-analysis-suite
cd brvm-analysis-suite
python -m venv brvm_env
source brvm_env/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Remplir avec vos clés
```

## Variables d'environnement

```
SUPABASE_URL=https://lynevvhmstpcffobwudr.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
MISTRAL_API_KEY=...
ANTHROPIC_API_KEY=...
```

## Lancement manuel

```bash
source brvm_env/bin/activate
python data_collector_simple.py   # Collecte des prix
python test_pipeline.py           # Tests qualité (12 tests)
python generate_decisions.py      # Génération des signaux
```

## Tests qualité

```bash
python test_pipeline.py
# Attendu : 0 erreur, 0 avertissement
# Exit 0 = OK, Exit 2 = erreur critique
```

## Pipeline automatique

GitHub Actions tourne chaque jour ouvré.
Voir `.github/workflows/brvm-analysis.yml`.

## Documentation

- [CHANGELOG.md](CHANGELOG.md) — Historique des changements
- [ARCHITECTURE.md](ARCHITECTURE.md) — Vue d'ensemble technique
- [RUNBOOK.md](RUNBOOK.md) — Procédures opérationnelles
- [DECISIONS.md](DECISIONS.md) — Décisions architecturales

## Modèle de scoring

Gel actif jusqu'au **01/07/2026** (première vérification live).
Ne pas modifier `generate_decisions.py` avant cette date.

| Signal | Condition |
|---|---|
| ACHAT | Score >= 65 ET régime BULL |
| SURVEILLER | Score 30-64 |
| EVITER | Score < 30 |

Performance documentée : +1.82% alpha vs random (toutes conditions).
