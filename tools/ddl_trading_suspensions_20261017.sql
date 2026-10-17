-- =============================================================================
-- trading_suspensions — suspensions de cotation BRVM
-- Session 17/10/2026
--
-- EXECUTION : SQL Editor Supabase uniquement (ADR-026).
-- Idempotent : CREATE TABLE IF NOT EXISTS + INSERT ... ON CONFLICT DO NOTHING.
-- Aucun DROP de table, aucune modification destructive de l'existant.
--
-- Usage : generate_decisions.py lit cette table et publie le signal
-- 'SUSPENDU' pour tout titre dont la suspension est en cours, au lieu de
-- calculer RSI / SMA / ATR sur un cours fige (volume 0, prix inchange).
--
-- Semantique des dates :
--   date_debut = premiere seance suspendue (inclusive)
--   date_fin   = derniere seance suspendue (inclusive) ; NULL = en cours
--   Une reprise de cotation le jour J s'enregistre avec date_fin = seance
--   precedente (J - 1 seance).
--
-- Quand un avis de reprise sort : UPDATE trading_suspensions
--   SET date_fin = '<derniere seance suspendue>' WHERE symbol = '...' AND date_fin IS NULL;
-- =============================================================================

CREATE TABLE IF NOT EXISTS trading_suspensions (
    id           BIGSERIAL PRIMARY KEY,
    symbol       TEXT        NOT NULL,
    motif        TEXT        NOT NULL,
    avis_ref     TEXT,
    date_debut   DATE        NOT NULL,
    date_fin     DATE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT trading_suspensions_dates_chk
        CHECK (date_fin IS NULL OR date_fin >= date_debut)
);

CREATE UNIQUE INDEX IF NOT EXISTS trading_suspensions_uk
    ON trading_suspensions (symbol, date_debut);

CREATE INDEX IF NOT EXISTS trading_suspensions_symbol_idx
    ON trading_suspensions (symbol);


-- -----------------------------------------------------------------------------
-- RLS : lecture publique (le frontend lit avec la cle anon), ecriture reservee
-- au service_role. Meme regle que les tables boc_* (voir ddl_boc_20260811.sql).
-- -----------------------------------------------------------------------------
ALTER TABLE trading_suspensions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS trading_suspensions_read ON trading_suspensions;

CREATE POLICY trading_suspensions_read
    ON trading_suspensions FOR SELECT TO anon, authenticated USING (true);


-- -----------------------------------------------------------------------------
-- Donnees initiales (avis BRVM 268/269/270-2026 du 16/09/2026)
--
-- Verifie sur historical_data le 17/10/2026 :
--   SICC : volume 0 et cours fige a 8400 depuis le 16/09 -> suspension en cours
--   SEMC : volume 0 et cours fige a 1495 depuis le 16/09 -> suspension en cours
--   SCRC : volume 0 les 16, 17, 18 et 21/09 (cours fige a 3085), reprise le
--          22/09 (volume 26456, cours 2905) -> suspension levee, date_fin = 21/09
--
-- L'attribution avis -> societe n'a pas ete reverifiee ligne a ligne :
-- avis_ref est donc indicatif ("268/269/270-2026") et non individualise.
-- -----------------------------------------------------------------------------
INSERT INTO trading_suspensions (symbol, motif, avis_ref, date_debut, date_fin)
VALUES
    ('SICC', 'Non-respect de la diffusion des informations financieres periodiques (levee conditionnee a la regularisation)',
     'Avis BRVM 268/269/270-2026', '2026-09-16', NULL),
    ('SEMC', 'Non-respect de la diffusion des informations financieres periodiques (levee conditionnee a la regularisation)',
     'Avis BRVM 268/269/270-2026', '2026-09-16', NULL),
    ('SCRC', 'Information importante en attente de communique (Instruction II-C) - reprise le 22/09/2026',
     'Avis BRVM 268/269/270-2026', '2026-09-16', '2026-09-21')
ON CONFLICT (symbol, date_debut) DO NOTHING;


-- =============================================================================
-- Verification post-execution
-- =============================================================================
SELECT symbol, motif, date_debut, date_fin,
       CASE WHEN date_fin IS NULL THEN 'EN COURS' ELSE 'LEVEE' END AS statut
FROM trading_suspensions
ORDER BY symbol, date_debut;
