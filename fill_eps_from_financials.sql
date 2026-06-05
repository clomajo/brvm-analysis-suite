-- ============================================================
-- fill_eps_from_financials.sql
-- Calcule EPS manquants depuis net_income / shares_outstanding
-- Calcule aussi ROE manquant depuis net_income / total_equity
-- À exécuter dans Supabase SQL Editor
-- Date : 2026-06-04
-- ============================================================

-- 1. Vérification avant modification
SELECT 
    ticker,
    fiscal_year,
    eps,
    net_income,
    shares_outstanding,
    CASE 
        WHEN shares_outstanding > 0 AND net_income IS NOT NULL 
        THEN ROUND((net_income / shares_outstanding)::numeric, 2)
        ELSE NULL 
    END AS eps_calcule,
    roe,
    net_income,
    total_equity,
    CASE 
        WHEN total_equity > 0 AND net_income IS NOT NULL 
        THEN ROUND((net_income / total_equity * 100)::numeric, 2)
        ELSE NULL 
    END AS roe_calcule
FROM company_fundamentals
WHERE fiscal_year = 'FY2025'
  AND (eps IS NULL OR roe IS NULL)
  AND net_income IS NOT NULL
  AND shares_outstanding > 0
ORDER BY ticker;

-- ============================================================
-- 2. Mise à jour EPS manquants
-- ============================================================
UPDATE company_fundamentals
SET eps = ROUND((net_income / shares_outstanding)::numeric, 2)
WHERE fiscal_year = 'FY2025'
  AND eps IS NULL
  AND net_income IS NOT NULL
  AND shares_outstanding > 0
  AND shares_outstanding IS NOT NULL;

-- ============================================================
-- 3. Mise à jour ROE manquants (depuis net_income / total_equity)
-- ============================================================
UPDATE company_fundamentals
SET roe = ROUND((net_income / total_equity * 100)::numeric, 2)
WHERE fiscal_year = 'FY2025'
  AND roe IS NULL
  AND net_income IS NOT NULL
  AND total_equity IS NOT NULL
  AND total_equity > 0;

-- ============================================================
-- 4. Vérification post-update
-- ============================================================
SELECT 
    COUNT(*) AS total,
    COUNT(eps) AS avec_eps,
    COUNT(roe) AS avec_roe,
    COUNT(pe_ratio) AS avec_per,
    COUNT(dividend_per_share) AS avec_dps,
    COUNT(market_cap) AS avec_mktcap
FROM company_fundamentals
WHERE fiscal_year = 'FY2025';

-- ============================================================
-- 5. Vue des tickers encore sans EPS ni ROE (à traiter manuellement)
-- ============================================================
SELECT ticker, eps, roe, net_income, shares_outstanding, total_equity
FROM company_fundamentals
WHERE fiscal_year = 'FY2025'
  AND (eps IS NULL OR roe IS NULL)
ORDER BY ticker;
