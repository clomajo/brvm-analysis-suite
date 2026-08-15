-- =============================================================================
-- BOC — Schema cible pour l'ingestion du Bulletin Officiel de la Cote
-- Session 11/08/2026 — ADR-046 (source), ADR-048 (ingesteur debranche)
--
-- EXECUTION : SQL Editor Supabase uniquement (ADR-026).
-- Idempotent : CREATE TABLE IF NOT EXISTS + ajout conditionnel de contraintes.
-- Aucun DROP. Aucune modification destructive de l'existant.
--
-- Perimetre : page 1 du BOC. Les tables par ticker (p.3-4) et le marche
-- obligataire detaille (p.5-9) ne sont PAS couverts ici.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. boc_indices — tous les indices, tous types confondus
--
-- Une seule table plutot que quatre : les colonnes sont identiques pour les
-- indices phares, les compartiments, le total return et les sectoriels.
-- Discriminant : type_indice.
--
-- base_reference etiquette le regime de base de l'indice (ADR-046 : la BRVM a
-- rebase ses indices au 02/01/2025, et la taxonomie sectorielle est passee de
-- 8 a 7 categories). On stocke le niveau publie tel quel, jamais retraite ;
-- le chainage entre regimes, s'il devient necessaire, sera un calcul a la
-- lecture, pas une reecriture de l'historique.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS boc_indices (
    id                  BIGSERIAL PRIMARY KEY,
    date_seance         DATE        NOT NULL,
    bulletin_numero     INTEGER,
    type_indice         TEXT        NOT NULL,
    indice              TEXT        NOT NULL,
    valeur              NUMERIC,
    var_jour_pct        NUMERIC,
    var_annuelle_pct    NUMERIC,
    nb_societes         INTEGER,
    volume              BIGINT,
    valeur_transigee    NUMERIC,
    per_moyen           NUMERIC,
    base_reference      TEXT,
    schema_version      TEXT        NOT NULL DEFAULT 'v2026',
    source_url          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT boc_indices_type_chk CHECK (
        type_indice IN ('PHARE', 'COMPARTIMENT', 'TOTAL_RETURN', 'SECTORIEL')
    )
);

-- Cle metier : un indice donne n'a qu'une valeur par seance.
-- Indispensable a l'upsert idempotent (rejouer un jour ne duplique pas).
CREATE UNIQUE INDEX IF NOT EXISTS boc_indices_uk
    ON boc_indices (date_seance, indice);

CREATE INDEX IF NOT EXISTS boc_indices_date_idx
    ON boc_indices (date_seance DESC);

CREATE INDEX IF NOT EXISTS boc_indices_type_date_idx
    ON boc_indices (type_indice, date_seance DESC);

COMMENT ON TABLE boc_indices IS
    'Indices BRVM extraits du Bulletin Officiel de la Cote, page 1. '
    'Source : boc_AAAAMMJJ_2.pdf. Niveaux publies, non retraites.';
COMMENT ON COLUMN boc_indices.base_reference IS
    'Regime de base de l''indice (ex. 2025-01-02). Les valeurs de regimes '
    'differents ne sont pas comparables directement — cf. ADR-046.';
COMMENT ON COLUMN boc_indices.per_moyen IS
    'PER moyen publie par la BRVM, calcule hors UNILEVER CI pour certains '
    'agregats (note (**) du bulletin). Non injecte dans V2 — cf. ADR-047.';


-- -----------------------------------------------------------------------------
-- 2. boc_market_stats — agregats marche ACTIONS et OBLIGATIONS
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS boc_market_stats (
    id                              BIGSERIAL PRIMARY KEY,
    date_seance                     DATE        NOT NULL,
    bulletin_numero                 INTEGER,
    marche                          TEXT        NOT NULL,

    capitalisation                  NUMERIC,
    capitalisation_evol_jour_pct    NUMERIC,
    volume_echange                  BIGINT,
    volume_echange_evol_jour_pct    NUMERIC,
    valeur_transigee                NUMERIC,
    valeur_transigee_evol_jour_pct  NUMERIC,

    nb_titres_transiges             INTEGER,
    nb_titres_transiges_evol_jour_pct NUMERIC,
    nb_hausse                       INTEGER,
    nb_hausse_evol_jour_pct         NUMERIC,
    nb_baisse                       INTEGER,
    nb_baisse_evol_jour_pct         NUMERIC,
    nb_inchanges                    INTEGER,
    nb_inchanges_evol_jour_pct      NUMERIC,

    schema_version                  TEXT        NOT NULL DEFAULT 'v2026',
    source_url                      TEXT,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT boc_market_stats_marche_chk CHECK (
        marche IN ('ACTIONS', 'OBLIGATIONS')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS boc_market_stats_uk
    ON boc_market_stats (date_seance, marche);

CREATE INDEX IF NOT EXISTS boc_market_stats_date_idx
    ON boc_market_stats (date_seance DESC);

COMMENT ON TABLE boc_market_stats IS
    'Agregats marche (capitalisation, volumes, market breadth) par seance et '
    'par marche, extraits du BOC page 1.';


-- -----------------------------------------------------------------------------
-- 3. boc_market_indicators — les 14 indicateurs de bas de page 1
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS boc_market_indicators (
    id                              BIGSERIAL PRIMARY KEY,
    date_seance                     DATE        NOT NULL,
    bulletin_numero                 INTEGER,

    per_moyen_marche                NUMERIC,
    taux_rendement_moyen            NUMERIC,
    taux_rentabilite_moyen          NUMERIC,
    nb_societes_cotees              INTEGER,
    nb_lignes_obligataires          INTEGER,
    volume_moyen_annuel_seance      NUMERIC,
    valeur_moyenne_annuelle_seance  NUMERIC,

    ratio_liquidite                 NUMERIC,
    ratio_satisfaction              NUMERIC,
    ratio_tendance                  NUMERIC,
    ratio_couverture                NUMERIC,
    taux_rotation                   NUMERIC,
    prime_risque                    NUMERIC,
    nb_sgi                          INTEGER,

    schema_version                  TEXT        NOT NULL DEFAULT 'v2026',
    source_url                      TEXT,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS boc_market_indicators_uk
    ON boc_market_indicators (date_seance);

COMMENT ON TABLE boc_market_indicators IS
    'Indicateurs de marche BRVM (PER moyen, taux de rendement, ratios de '
    'liquidite/satisfaction/tendance/couverture, prime de risque) par seance.';
COMMENT ON COLUMN boc_market_indicators.taux_rendement_moyen IS
    'Taux de rendement moyen empirique du marche. Rend caduc le 8 %% arbitraire '
    'du terme 3,75 x DPS de V2 — arbitrage reporte, cf. ADR-047.';


-- -----------------------------------------------------------------------------
-- 4. new_market_indicators — contrainte unique sur extraction_date
--
-- data_collector.py (L289) fait un ON CONFLICT (extraction_date) DO UPDATE.
-- Cette clause exige une contrainte unique sur extraction_date, absente de la
-- definition actuelle (seule la PK sur id est declaree). Sans elle, tout upsert
-- leve une erreur 42P10. La table etant vide, l'ajout est sans risque.
--
-- Table conservee et alimentee en parallele des tables boc_* : report_generator.py
-- la lit dans 3 requetes (cf. ADR-048). Sa migration est hors perimetre.
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'public.new_market_indicators'::regclass
          AND contype IN ('u', 'p')
          AND conkey = ARRAY[
              (SELECT attnum FROM pg_attribute
               WHERE attrelid = 'public.new_market_indicators'::regclass
                 AND attname = 'extraction_date')
          ]::smallint[]
    ) THEN
        ALTER TABLE public.new_market_indicators
            ADD CONSTRAINT new_market_indicators_extraction_date_uk
            UNIQUE (extraction_date);
        RAISE NOTICE 'Contrainte unique ajoutee sur new_market_indicators.extraction_date';
    ELSE
        RAISE NOTICE 'Contrainte unique deja presente — aucune action';
    END IF;
END
$$;


-- -----------------------------------------------------------------------------
-- 5. Lecture publique (RLS)
--
-- Ajoute le 15/08/2026, apres constat : le frontend (cle anon) recevait un
-- HTTP 200 avec un tableau vide sur les trois tables. RLS etait actif sans
-- aucune politique, donc aucune ligne visible. Le panneau d'indices de la home
-- ne s'affichait pas.
--
-- Ces donnees sont publiques par nature : elles proviennent du Bulletin Officiel
-- de la Cote, publie chaque jour par la BRVM. L'ecriture reste reservee au
-- service_role utilise par le pipeline.
-- -----------------------------------------------------------------------------
ALTER TABLE boc_indices           ENABLE ROW LEVEL SECURITY;
ALTER TABLE boc_market_stats      ENABLE ROW LEVEL SECURITY;
ALTER TABLE boc_market_indicators ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS boc_indices_read           ON boc_indices;
DROP POLICY IF EXISTS boc_market_stats_read      ON boc_market_stats;
DROP POLICY IF EXISTS boc_market_indicators_read ON boc_market_indicators;

CREATE POLICY boc_indices_read
    ON boc_indices FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY boc_market_stats_read
    ON boc_market_stats FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY boc_market_indicators_read
    ON boc_market_indicators FOR SELECT TO anon, authenticated USING (true);


-- =============================================================================
-- Verification post-execution
-- =============================================================================
SELECT
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns c
     WHERE c.table_name = t.table_name AND c.table_schema = 'public') AS nb_colonnes
FROM information_schema.tables t
WHERE t.table_schema = 'public'
  AND t.table_name IN ('boc_indices', 'boc_market_stats', 'boc_market_indicators')
ORDER BY table_name;

SELECT conname, contype
FROM pg_constraint
WHERE conrelid = 'public.new_market_indicators'::regclass
ORDER BY conname;
