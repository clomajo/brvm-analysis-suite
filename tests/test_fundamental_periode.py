"""tests/test_fundamental_periode.py -- lecture exercice / periode / type (ADR-060).
Aucun reseau. Les titres de la premiere serie sont ceux de la page BRVM de BOA CI (18/10/2026)."""
from datetime import date

import pytest

from fundamental_periode import lire_titre


@pytest.mark.parametrize("titre, annee, periode, fin, type_", [
    ("BOA CI : Rapport d'activités - 1er semestre 2026", 2026, "S1", date(2026, 6, 30), "ACTIVITES"),
    ("BOA CI : Rapport d’examen limité des états financiers - 1er semestre 2026", 2026, "S1", date(2026, 6, 30), "EXAMEN_LIMITE"),
    ("BOA CI : Rapport des Commissaires Aux Comptes et Etats Financiers annuels - Exercice 2025", 2025, "FY", date(2025, 12, 31), "CAC"),
    ("BOA CI : Rapport d'activités - 1er trimestre 2026", 2026, "T1", date(2026, 3, 31), "ACTIVITES"),
    ("Rapport d'activités - 3ème trimestre 2025", 2025, "T3", date(2025, 9, 30), "ACTIVITES"),
    ("Rapport d'activités annuel - Exercice 2024", 2024, "FY", date(2024, 12, 31), "ACTIVITES"),
    ("Etats financiers - Exercice 2023", 2023, "FY", date(2023, 12, 31), "ETATS_FIN"),
    ("Etats financiers - 2ème semestre 2024", 2024, "S2", date(2024, 12, 31), "ETATS_FIN"),
    ("Rapport d'activités - 2e trimestre 2026", 2026, "T2", date(2026, 6, 30), "ACTIVITES"),
    ("Rapport d'activités - 4ème trimestre 2025", 2025, "T4", date(2025, 12, 31), "ACTIVITES"),
])
def test_titres_reconnus(titre, annee, periode, fin, type_):
    r = lire_titre(titre)
    assert (r.fiscal_year, r.periode, r.period_end, r.type_rapport) == (annee, periode, fin, type_)


def test_etat_financier_intermediaire_n_est_pas_un_exercice():
    assert lire_titre("Etats financiers - 1er semestre 2026").periode == "S1"


@pytest.mark.parametrize("titre", [
    "",
    None,
    "Commentaires sur l'activité",                       # aucune annee
    "Rapport d'activités - 1er semestre",                # aucune annee
    "Rapport annuel - Exercice 2024-2025",               # deux annees : a revoir a la main
    "Rapport 2026",                                      # annee sans periode
    "Rapport d'activités - 5ème trimestre 2026",         # periode impossible
])
def test_titres_non_concluants_renvoient_none(titre):
    assert lire_titre(titre) is None


B = "https://www.brvm.org/sites/default/files/"


@pytest.mark.parametrize("fichier, annee, periode, publie", [
    ("20251029_-_rapport_dactivites_-_3eme_trimestre_2025_-_nsia_banque_ci.pdf", 2025, "T3", date(2025, 10, 29)),
    ("20250919_-_rapport_dactivites_-_1er_semestre_2025_-_boa_ml.pdf", 2025, "S1", date(2025, 9, 19)),
    ("20260703_-_rapport_dactivites_-_4e_trimestre_2024_-_safca_ci.pdf", 2024, "T4", date(2026, 7, 3)),
    ("20241205_-_rapport_annuel_-_exercice_2023_-_sicor_ci.pdf", 2023, "FY", date(2024, 12, 5)),
    ("20260217_-_etats_financiers_-_exercice_2025_-_orange_ci.pdf", 2025, "FY", date(2026, 2, 17)),
    ("20250829_-_etats_financiers_et_rapport_des_cac_-_exercice_2024_-_africa_global_logistics_ci.pdf", 2024, "FY", date(2025, 8, 29)),
    ("20251016_-_attestation_des_commissaires_aux_comptes_sur_le_rapport_dactivites_-_1er_semestre_2025_-_totalenergies_marketing_ci.pdf", 2025, "S1", date(2025, 10, 16)),
    ("eviosys_packaging_siem_rapport_dactivites_1er_trimestre_2023.pdf", 2023, "T1", None),
    ("20260422-rapport-boas-t1-2026.pdf", 2026, "T1", date(2026, 4, 22)),
    ("20230503_-_rapport_dactivite_provisoire_exercice_2022_-_unilever_ci.pdf", 2022, "FY", date(2023, 5, 3)),
    ("20260324_-_rapport_du_conseil_dadministration_a_lassemblee_generale_ordinaire_des_actionnaires_-_exercice_2025_-_boa_ng_annule_et_remplace_le_precedent.pdf", 2025, "FY", date(2026, 3, 24)),
])
def test_adresses_reconnues(fichier, annee, periode, publie):
    from fundamental_periode import lire_url
    r = lire_url(B + fichier)
    assert (r.fiscal_year, r.periode, r.publie_le, r.source) == (annee, periode, publie, "url")


def test_plusieurs_annees_dans_l_adresse_vont_en_revue():
    from fundamental_periode import lire_url
    assert lire_url(B + "20250617_-_etats_financiers_-_exercices_2018_a_2023_-_tractafric_motors_ci_annule_et_remplace_le_precedent.pdf") is None


def test_titre_generique_bascule_sur_l_adresse():
    from fundamental_periode import lire_rapport
    r = lire_rapport("Télécharger", B + "20251029_-_rapport_dactivites_-_3eme_trimestre_2025_-_nsia_banque_ci.pdf")
    assert (r.fiscal_year, r.periode, r.source) == (2025, "T3", "url")


def test_titre_lisible_prime_sur_l_adresse():
    from fundamental_periode import lire_rapport
    r = lire_rapport("BOA CI : Rapport d'activités - 1er trimestre 2026", B + "20260101_-_autre_-_exercice_2020.pdf")
    assert (r.fiscal_year, r.periode, r.source) == (2026, "T1", "titre")


def test_rien_de_lisible_renvoie_none():
    from fundamental_periode import lire_rapport
    assert lire_rapport("Télécharger", B + "document.pdf") is None
    assert lire_rapport(None, None) is None
