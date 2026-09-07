"""Audit du plafond PostgREST 5000. Lecture seule, aucune requete reseau.
Analyse statique : pour chaque appel REST visant une table >5000 lignes,
extrait 12 lignes de contexte et cherche les marqueurs de pagination.
"""
import os, re, logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

GROSSES = ["historical_data", "brvm_decisions", "boc_cote", "v_historical_prices"]
PAGIN = ["limit", "offset", "Range", "count=exact", "range_", "page"]
SKIP = ("venv311/", "brvm_env/", "/.git/", ".bak")

def fichiers():
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in ("venv311", "brvm_env", ".git", "node_modules")]
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(root, f).replace("./", "")
                if not any(s in p for s in SKIP):
                    yield p

resultats = []
for path in sorted(fichiers()):
    try:
        lignes = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError as e:
        log.warning("illisible %s: %s", path, e)
        continue
    for i, l in enumerate(lignes):
        if "rest/v1" not in l:
            continue
        ctx = "\n".join(lignes[max(0, i - 4):i + 12])
        tables = [t for t in GROSSES if t in ctx]
        if not tables:
            continue
        if re.search(r"\.post\(|\.patch\(|\.delete\(|on_conflict", ctx):
            continue
        trouves = [m for m in PAGIN if m in ctx]
        resultats.append((path, i + 1, tables, trouves))

log.info("=== SANS AUCUN MARQUEUR DE PAGINATION (a examiner) ===")
for p, n, t, f in resultats:
    if not f:
        log.info("%-58s L%-5s %s", p, n, ",".join(sorted(set(t))))

log.info("\n=== AVEC MARQUEURS (a verifier au cas par cas) ===")
for p, n, t, f in resultats:
    if f:
        log.info("%-58s L%-5s %-28s [%s]", p, n, ",".join(sorted(set(t))), ",".join(f))

log.info("\ntotal appels analysés : %s", len(resultats))
