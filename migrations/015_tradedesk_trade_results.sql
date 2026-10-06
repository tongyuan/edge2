ALTER TABLE tradedesk_lifecycle_events
    DROP CONSTRAINT tradedesk_lifecycle_events_schema_version_check;
ALTER TABLE tradedesk_lifecycle_events
    ADD CONSTRAINT tradedesk_lifecycle_events_schema_version_check
    CHECK (schema_version IN ('1.0', '1.1', '1.2'));

ALTER TABLE tradedesk_lifecycle_events
    DROP CONSTRAINT tradedesk_lifecycle_events_event_type_check;
ALTER TABLE tradedesk_lifecycle_events
    ADD CONSTRAINT tradedesk_lifecycle_events_event_type_check
    CHECK (
        event_type IN (
            'MSS_CONFIRMED', 'RR_QUALIFIED', 'GRADE_A', 'GRADE_A_PLUS',
            'SETUP_FAILED', 'SETUP_RETIRED', 'TARGET_TAKEN',
            'ENTRY_TOUCHED', 'ENTRY_CONFIRMED', 'ENTRY_INVALIDATED',
            'ENTRY_STOPPED', 'ENTRY_TARGET_TAKEN', 'ENTRY_AMBIGUOUS',
            'ENTRY_EXIT_LEVEL_REACHED'
        )
    );

ALTER TABLE tradedesk_lifecycle_events
    ADD COLUMN mrz_context_id TEXT,
    ADD COLUMN exit_ladder_available BOOLEAN,
    ADD COLUMN frozen_exit_ladder JSONB,
    ADD COLUMN initial_risk NUMERIC,
    ADD COLUMN level_ids JSONB,
    ADD COLUMN level_price NUMERIC,
    ADD COLUMN excursion_r NUMERIC,
    ADD COLUMN contact_mode TEXT,
    ADD COLUMN mfe_pre_terminal_price NUMERIC,
    ADD COLUMN mfe_pre_terminal_r NUMERIC,
    ADD COLUMN mae_pre_terminal_price NUMERIC,
    ADD COLUMN mae_pre_terminal_r NUMERIC,
    ADD COLUMN mfe_inclusive_price NUMERIC,
    ADD COLUMN mfe_inclusive_r NUMERIC,
    ADD COLUMN mae_inclusive_price NUMERIC,
    ADD COLUMN mae_inclusive_r NUMERIC,
    ADD COLUMN best_level_pre_terminal_ids JSONB,
    ADD COLUMN best_level_pre_terminal_price NUMERIC,
    ADD COLUMN best_level_pre_terminal_r NUMERIC,
    ADD COLUMN best_level_pre_terminal_at TIMESTAMPTZ,
    ADD COLUMN terminal_bar_levels_touched JSONB;

ALTER TABLE tradedesk_lifecycle_events
    ADD CONSTRAINT tradedesk_lifecycle_initial_risk_check
        CHECK (initial_risk IS NULL OR initial_risk > 0),
    ADD CONSTRAINT tradedesk_lifecycle_excursion_check
        CHECK (
            (excursion_r IS NULL OR excursion_r >= 0)
            AND (mfe_pre_terminal_r IS NULL OR mfe_pre_terminal_r >= 0)
            AND (mae_pre_terminal_r IS NULL OR mae_pre_terminal_r >= 0)
            AND (mfe_inclusive_r IS NULL OR mfe_inclusive_r >= 0)
            AND (mae_inclusive_r IS NULL OR mae_inclusive_r >= 0)
            AND (best_level_pre_terminal_r IS NULL OR best_level_pre_terminal_r >= 0)
        ),
    ADD CONSTRAINT tradedesk_lifecycle_contact_mode_check
        CHECK (contact_mode IS NULL OR contact_mode IN ('RANGE_TOUCH', 'GAP_CROSS'));

CREATE TABLE tradedesk_trade_results (
    entry_id TEXT PRIMARY KEY REFERENCES tradedesk_entry_attempts(entry_id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('OPEN', 'WIN', 'LOSS', 'AMBIGUOUS')),
    opened_at TIMESTAMPTZ NOT NULL,
    closed_at TIMESTAMPTZ,
    terminal_event_id TEXT,
    terminal_event_type TEXT CHECK (
        terminal_event_type IS NULL OR terminal_event_type IN (
            'ENTRY_STOPPED', 'ENTRY_TARGET_TAKEN', 'ENTRY_AMBIGUOUS'
        )
    ),
    initial_risk NUMERIC NOT NULL CHECK (initial_risk > 0),
    mrz_context_id TEXT,
    frozen_exit_ladder JSONB,
    reached_levels JSONB NOT NULL DEFAULT '[]'::jsonb,
    best_level_pre_terminal_ids JSONB,
    best_level_pre_terminal_price NUMERIC,
    best_level_pre_terminal_r NUMERIC CHECK (
        best_level_pre_terminal_r IS NULL OR best_level_pre_terminal_r >= 0
    ),
    best_level_pre_terminal_at TIMESTAMPTZ,
    mfe_pre_terminal_price NUMERIC,
    mfe_pre_terminal_r NUMERIC CHECK (mfe_pre_terminal_r IS NULL OR mfe_pre_terminal_r >= 0),
    mae_pre_terminal_price NUMERIC,
    mae_pre_terminal_r NUMERIC CHECK (mae_pre_terminal_r IS NULL OR mae_pre_terminal_r >= 0),
    mfe_inclusive_price NUMERIC,
    mfe_inclusive_r NUMERIC CHECK (mfe_inclusive_r IS NULL OR mfe_inclusive_r >= 0),
    mae_inclusive_price NUMERIC,
    mae_inclusive_r NUMERIC CHECK (mae_inclusive_r IS NULL OR mae_inclusive_r >= 0),
    terminal_bar_levels_touched JSONB,
    mrz_migrated_while_open BOOLEAN NOT NULL DEFAULT FALSE,
    first_pending_migration_at TIMESTAMPTZ,
    latest_pending_migration_at TIMESTAMPTZ,
    pending_migration_count INTEGER NOT NULL DEFAULT 0 CHECK (pending_migration_count >= 0),
    evidence_version TEXT NOT NULL CHECK (evidence_version IN ('1.1-legacy', '1.2')),
    evidence_complete BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX idx_tradedesk_trade_results_status_opened
    ON tradedesk_trade_results(status, opened_at DESC);

INSERT INTO tradedesk_trade_results (
    entry_id, status, opened_at, closed_at, terminal_event_id, terminal_event_type,
    initial_risk, mrz_migrated_while_open, first_pending_migration_at,
    latest_pending_migration_at, pending_migration_count,
    evidence_version, evidence_complete
)
SELECT
    attempt.entry_id,
    CASE attempt.status
        WHEN 'TARGET_TAKEN' THEN 'WIN'
        WHEN 'STOPPED' THEN 'LOSS'
        WHEN 'AMBIGUOUS' THEN 'AMBIGUOUS'
        ELSE 'OPEN'
    END,
    attempt.confirmed_at,
    terminal.event_at,
    terminal.event_id,
    terminal.event_type,
    abs(attempt.entry_price - attempt.stop_price),
    migration.migration_count > 0,
    migration.first_at,
    migration.latest_at,
    migration.migration_count,
    '1.1-legacy',
    FALSE
FROM tradedesk_entry_attempts attempt
JOIN tradedesk_setups setup USING (setup_id)
LEFT JOIN LATERAL (
    SELECT event_id, event_type, event_at
    FROM tradedesk_lifecycle_events event
    WHERE event.entry_id = attempt.entry_id
      AND event.event_type IN ('ENTRY_STOPPED', 'ENTRY_TARGET_TAKEN', 'ENTRY_AMBIGUOUS')
    ORDER BY event_at,
        CASE event_type WHEN 'ENTRY_AMBIGUOUS' THEN 0 WHEN 'ENTRY_STOPPED' THEN 1 ELSE 2 END,
        id
    LIMIT 1
) terminal ON TRUE
LEFT JOIN LATERAL (
    SELECT min(occurred_at) AS first_at,
           max(occurred_at) AS latest_at,
           count(*) AS migration_count
    FROM mrz_events migration_event
    WHERE migration_event.symbol = setup.symbol
      AND migration_event.event_type = 'MRZ_MIGRATED'
      AND migration_event.occurred_at > attempt.confirmed_at
      AND (
          terminal.event_at IS NULL
          OR migration_event.occurred_at < terminal.event_at
      )
) migration ON TRUE
WHERE attempt.confirmed_at IS NOT NULL
  AND attempt.entry_price IS NOT NULL
  AND attempt.stop_price IS NOT NULL;
