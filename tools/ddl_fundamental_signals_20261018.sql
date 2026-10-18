-- =============================================================================
-- fundamental_signals -- historique des signaux fondamentaux, une ligne par rapport
-- Session 18/10/2026 -- voir ADR-060
--
-- EXECUTION : SQL Editor Supabase uniquement (ADR-026).
-- Idempotent : CREATE TABLE IF NOT EXISTS. Aucun DROP, aucune modification de
-- l'existant. La table est creee VIDE ; rien ne la lit pour l'instant.
--
-- Principe : un rapport analyse = une ligne. Aucun ecrasement : un nouveau rapport
-- ajoute une ligne. Deux rapports de la meme periode (par exemple le rapport
-- d'activites et le rapport d'examen limite du 1er semestre 2026) sont deux lignes.
--
-- Regle : company_id ET ticker sont obligatoires (incident BBGC, ADR-059).
--
-- signal : 'negatif' sans accent. generate_decisions.py accepte les deux graphies
-- pour company_fundamentals ; ici une seule, pour ne pas dedoubler les comptages.
-- =============================================================================

CREATE TABLE IF NOT EXISTS fundamental_signals (
    id                BIGSERIAL PRIMARY KEY,
    company_id        INTEGER     NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    ticker            TEXT        NOT NULL,
    fiscal_year       INTEGER     NOT NULL,
    periode           TEXT        NOT NULL,
    period_end        DATE        NOT NULL,
    type_rapport      TEXT,
    report_url        TEXT        NOT NULL,
    report_title      TEXT,
    report_date       DATE,
    signal            TEXT        NOT NULL,
    croissance_ca_pct NUMERIC,
    tendance          TEXT,
    resume            TEXT,
    modele            TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fundamental_signals_periode_chk
        CHECK (periode IN ('T1','T2','T3','T4','S1','S2','FY')),
    CONSTRAINT fundamental_signals_signal_chk
        CHECK (signal IN ('positif','neutre','negatif')),
    CONSTRAINT fundamental_signals_type_chk
        CHECK (type_rapport IS NULL OR type_rapport IN
               ('ACTIVITES','EXAMEN_LIMITE','CAC','ETATS_FIN','COMMENTAIRE')),
    CONSTRAINT fundamental_signals_ticker_chk
        CHECK (length(btrim(ticker)) > 0)
);

-- Un rapport ne produit qu'une ligne (cle d'idempotence du remplissage).
CREATE UNIQUE INDEX IF NOT EXISTS fundamental_signals_report_uk
    ON fundamental_signals (report_url);

-- Lecture "periode la plus recente par societe" et series par societe.
CREATE INDEX IF NOT EXISTS fundamental_signals_ticker_periode_idx
    ON fundamental_signals (ticker, period_end DESC, report_date DESC);

-- RLS : lecture publique (frontend, cle anon), ecriture reservee au service_role.
ALTER TABLE fundamental_signals ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS fundamental_signals_read ON fundamental_signals;
CREATE POLICY fundamental_signals_read
    ON fundamental_signals FOR SELECT TO anon, authenticated USING (true);

-- =============================================================================
-- Verification post-execution (table vide attendue : 0 ligne)
-- =============================================================================
SELECT count(*) AS lignes FROM fundamental_signals;
