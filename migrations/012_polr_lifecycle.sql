CREATE TABLE IF NOT EXISTS polr_lifecycle_events (
    id BIGSERIAL PRIMARY KEY,
    schema_version TEXT NOT NULL CHECK (schema_version = '1.0'),
    event_id TEXT NOT NULL UNIQUE,
    setup_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'MSS_CONFIRMED',
            'RR_QUALIFIED',
            'GRADE_A',
            'GRADE_A_PLUS',
            'SETUP_FAILED',
            'SETUP_RETIRED',
            'TARGET_TAKEN'
        )
    ),
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    mss_at TIMESTAMPTZ NOT NULL,
    event_at TIMESTAMPTZ NOT NULL,
    sweep_price NUMERIC NOT NULL,
    target_price NUMERIC NOT NULL,
    target_side TEXT NOT NULL CHECK (target_side IN ('BSL', 'SSL')),
    grade TEXT,
    rr_qualified_at TIMESTAMPTZ,
    rr_source TEXT,
    rr_reference_price NUMERIC,
    setup_rr NUMERIC,
    event_price NUMERIC NOT NULL,
    chart_timeframe TEXT NOT NULL,
    range_timeframe TEXT NOT NULL,
    message TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_polr_lifecycle_events_setup_order
    ON polr_lifecycle_events (setup_id, event_at, received_at, id);

CREATE OR REPLACE FUNCTION reject_polr_lifecycle_event_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'POLR lifecycle received-event truth is immutable';
END;
$$;

DROP TRIGGER IF EXISTS polr_lifecycle_events_immutable
    ON polr_lifecycle_events;
CREATE TRIGGER polr_lifecycle_events_immutable
BEFORE UPDATE OR DELETE ON polr_lifecycle_events
FOR EACH ROW EXECUTE FUNCTION reject_polr_lifecycle_event_mutation();

CREATE TABLE IF NOT EXISTS polr_setups (
    setup_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    mss_at TIMESTAMPTZ NOT NULL,
    sweep_price NUMERIC NOT NULL,
    target_price NUMERIC NOT NULL,
    target_side TEXT NOT NULL CHECK (target_side IN ('BSL', 'SSL')),
    rr_qualified_at TIMESTAMPTZ,
    rr_source TEXT,
    rr_reference_price NUMERIC,
    setup_rr NUMERIC,
    highest_grade TEXT CHECK (highest_grade IS NULL OR highest_grade IN ('A', 'A+')),
    status TEXT NOT NULL CHECK (status IN ('LIVE', 'FAILED', 'RETIRED', 'TARGET_TAKEN')),
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_event_at TIMESTAMPTZ NOT NULL,
    last_received_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_polr_setups_symbol_status
    ON polr_setups (symbol, status, last_event_at DESC);
