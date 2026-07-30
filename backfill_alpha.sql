-- T16-backfill — Rétro-remplissage benchmark_return / alpha
-- Exécuté le 30/07/2026 via SQL Editor (ADR-026). 3088 lignes mises à jour.
-- Clé de cohorte : (signal_date, verification_date) — cf. ADR-035 amendé.
-- Les 47 lignes du 28/07 (écrites par verify_decisions.py) sont épargnées
-- par le filtre alpha IS NULL et servent de témoin de conformité.

WITH b AS (
  SELECT signal_date, verification_date, AVG(variation_pct) AS br
  FROM brvm_decisions_results
  GROUP BY signal_date, verification_date
)
UPDATE brvm_decisions_results r
SET benchmark_return = round(b.br::numeric, 2),
    alpha = round((r.variation_pct - b.br)::numeric, 2)
FROM b
WHERE r.signal_date = b.signal_date
  AND r.verification_date = b.verification_date
  AND r.alpha IS NULL;
