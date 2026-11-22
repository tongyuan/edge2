-- Structural intelligence is derived from canonical MRZ history. Legacy
-- structural-transition records remain intact for audit and rollback only.

ALTER TABLE notification_preferences
    ADD COLUMN IF NOT EXISTS structural_development_enabled BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS structural_developments (
    id BIGSERIAL PRIMARY KEY,
    development_key TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL REFERENCES instruments(symbol),
    source_trigger_event_id TEXT NOT NULL REFERENCES observations(event_id),
    development_type TEXT NOT NULL CHECK (development_type IN ('HH', 'HL', 'LH', 'LL')),
    maturity TEXT NOT NULL CHECK (maturity IN ('developing', 'confirmed')),
    migration_structure TEXT NOT NULL CHECK (
        migration_structure IN ('ascending', 'descending', 'transitional', 'undetermined')
    ),
    route_hypothesis TEXT NOT NULL CHECK (
        route_hypothesis IN (
            'STR_DOMINANT', 'STR_DOMINANT_EMERGING_BTD',
            'BTD_DOMINANT', 'BTD_DOMINANT_EMERGING_STR',
            'UNRESOLVED', 'INSUFFICIENT_HISTORY'
        )
    ),
    migration_sequence INTEGER NOT NULL CHECK (migration_sequence > 0),
    pivot_event_key TEXT NOT NULL,
    supporting_event_keys JSONB NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    first_known_time TIMESTAMPTZ NOT NULL,
    confirmation_time TIMESTAMPTZ,
    detector_version TEXT NOT NULL,
    live_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT structural_development_support_check CHECK (
        jsonb_typeof(supporting_event_keys) = 'array'
        AND jsonb_array_length(supporting_event_keys) >= 2
    ),
    CONSTRAINT structural_development_confirmation_check CHECK (
        (maturity = 'developing' AND confirmation_time IS NULL)
        OR (maturity = 'confirmed' AND confirmation_time IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_structural_developments_symbol_time
    ON structural_developments (symbol, first_known_time DESC, id DESC);

ALTER TABLE web_push_notifications
    DROP CONSTRAINT IF EXISTS web_push_notifications_event_type_check;
ALTER TABLE web_push_notifications
    ADD CONSTRAINT web_push_notifications_event_type_check CHECK (
        event_type IN (
            'MRZ_ACTIVATED', 'MRZ_MIGRATED', 'ROUTE_CHANGED',
            'MRZ_NEAR_MISS', 'POST_ACTIVATION_PRESSURE_CHANGED',
            'STRUCTURAL_TRANSITION', 'STRUCTURAL_DEVELOPMENT'
        )
    );

ALTER TABLE web_push_notifications
    ADD COLUMN IF NOT EXISTS structural_development_id BIGINT
        REFERENCES structural_developments(id),
    ADD COLUMN IF NOT EXISTS structural_development_type TEXT,
    ADD COLUMN IF NOT EXISTS structural_development_maturity TEXT,
    ADD COLUMN IF NOT EXISTS migration_structure TEXT,
    ADD COLUMN IF NOT EXISTS route_hypothesis TEXT;

ALTER TABLE web_push_notifications
    ADD CONSTRAINT web_push_notifications_development_payload_check CHECK (
        event_type <> 'STRUCTURAL_DEVELOPMENT'
        OR (
            structural_development_id IS NOT NULL
            AND structural_development_type IN ('HH', 'HL', 'LH', 'LL')
            AND structural_development_maturity IN ('developing', 'confirmed')
            AND migration_structure IN ('ascending', 'descending', 'transitional', 'undetermined')
            AND route_hypothesis IS NOT NULL
        )
    );

CREATE UNIQUE INDEX IF NOT EXISTS idx_web_push_notifications_development
    ON web_push_notifications (structural_development_id)
    WHERE structural_development_id IS NOT NULL;

-- Do not map the legacy enabled preference. The new category remains opt-in.
UPDATE notification_preferences
SET structural_development_enabled = FALSE
WHERE structural_development_enabled IS DISTINCT FROM FALSE;
