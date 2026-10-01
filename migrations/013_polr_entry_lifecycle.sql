ALTER TABLE polr_lifecycle_events
    DROP CONSTRAINT IF EXISTS polr_lifecycle_events_schema_version_check;

ALTER TABLE polr_lifecycle_events
    ADD CONSTRAINT polr_lifecycle_events_schema_version_check
    CHECK (schema_version IN ('1.0', '1.1'));

ALTER TABLE polr_lifecycle_events
    DROP CONSTRAINT IF EXISTS polr_lifecycle_events_event_type_check;

ALTER TABLE polr_lifecycle_events
    ADD CONSTRAINT polr_lifecycle_events_event_type_check
    CHECK (
        event_type IN (
            'MSS_CONFIRMED',
            'RR_QUALIFIED',
            'GRADE_A',
            'GRADE_A_PLUS',
            'SETUP_FAILED',
            'SETUP_RETIRED',
            'TARGET_TAKEN',
            'ENTRY_TOUCHED',
            'ENTRY_CONFIRMED',
            'ENTRY_INVALIDATED',
            'ENTRY_STOPPED',
            'ENTRY_AMBIGUOUS'
        )
    );

ALTER TABLE polr_lifecycle_events
    ADD COLUMN IF NOT EXISTS entry_id TEXT,
    ADD COLUMN IF NOT EXISTS entry_attempt INTEGER,
    ADD COLUMN IF NOT EXISTS entry_source TEXT,
    ADD COLUMN IF NOT EXISTS confirmation_method TEXT,
    ADD COLUMN IF NOT EXISTS entry_zone_top NUMERIC,
    ADD COLUMN IF NOT EXISTS entry_zone_bottom NUMERIC,
    ADD COLUMN IF NOT EXISTS ote_top NUMERIC,
    ADD COLUMN IF NOT EXISTS ote_bottom NUMERIC,
    ADD COLUMN IF NOT EXISTS ote_confirmed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS range_low NUMERIC,
    ADD COLUMN IF NOT EXISTS range_high NUMERIC,
    ADD COLUMN IF NOT EXISTS range_third TEXT,
    ADD COLUMN IF NOT EXISTS ote_required BOOLEAN,
    ADD COLUMN IF NOT EXISTS minimum_grade TEXT,
    ADD COLUMN IF NOT EXISTS grade_at_touch TEXT,
    ADD COLUMN IF NOT EXISTS grade_at_confirmation TEXT,
    ADD COLUMN IF NOT EXISTS entry_touched_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS entry_confirmed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS entry_price NUMERIC,
    ADD COLUMN IF NOT EXISTS stop_price NUMERIC,
    ADD COLUMN IF NOT EXISTS entry_rr NUMERIC;

ALTER TABLE polr_lifecycle_events
    ADD CONSTRAINT polr_lifecycle_events_entry_attempt_check
        CHECK (entry_attempt IS NULL OR entry_attempt > 0),
    ADD CONSTRAINT polr_lifecycle_events_entry_zone_check
        CHECK (
            (entry_zone_top IS NULL AND entry_zone_bottom IS NULL)
            OR (
                entry_zone_top IS NOT NULL
                AND entry_zone_bottom IS NOT NULL
                AND entry_zone_top > entry_zone_bottom
            )
        ),
    ADD CONSTRAINT polr_lifecycle_events_ote_zone_check
        CHECK (
            (ote_top IS NULL AND ote_bottom IS NULL)
            OR (ote_top IS NOT NULL AND ote_bottom IS NOT NULL AND ote_top > ote_bottom)
        ),
    ADD CONSTRAINT polr_lifecycle_events_range_check
        CHECK (
            (range_high IS NULL AND range_low IS NULL)
            OR (range_high IS NOT NULL AND range_low IS NOT NULL AND range_high > range_low)
        );

CREATE INDEX IF NOT EXISTS idx_polr_lifecycle_events_entry_order
    ON polr_lifecycle_events (entry_id, event_at, received_at, id)
    WHERE entry_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS polr_entry_attempts (
    entry_id TEXT PRIMARY KEY,
    setup_id TEXT NOT NULL REFERENCES polr_setups (setup_id),
    attempt_no INTEGER NOT NULL CHECK (attempt_no > 0),
    status TEXT NOT NULL CHECK (
        status IN (
            'CANDIDATE',
            'CONFIRMED',
            'INVALIDATED',
            'STOPPED',
            'TARGET_TAKEN',
            'AMBIGUOUS'
        )
    ),
    source TEXT NOT NULL CHECK (
        source IN ('SB', 'BISI', 'SIBI', 'FVG', 'VI', 'IFVG', 'BREAKER')
    ),
    confirmation_method TEXT NOT NULL CHECK (
        confirmation_method IN ('CE_RECLAIM', 'PROXIMAL_RECLAIM')
    ),
    zone_top NUMERIC NOT NULL,
    zone_bottom NUMERIC NOT NULL CHECK (zone_top > zone_bottom),
    ote_top NUMERIC,
    ote_bottom NUMERIC,
    ote_confirmed_at TIMESTAMPTZ,
    range_low NUMERIC NOT NULL,
    range_high NUMERIC NOT NULL CHECK (range_high > range_low),
    range_third TEXT NOT NULL CHECK (range_third IN ('BOTTOM', 'TOP')),
    ote_required BOOLEAN,
    minimum_grade TEXT CHECK (minimum_grade IN ('Off', 'A', 'A+')),
    grade_at_touch TEXT CHECK (grade_at_touch IN ('A', 'A+')),
    grade_at_confirmation TEXT CHECK (grade_at_confirmation IN ('A', 'A+')),
    touched_at TIMESTAMPTZ NOT NULL,
    confirmed_at TIMESTAMPTZ,
    entry_price NUMERIC,
    stop_price NUMERIC,
    target_price NUMERIC NOT NULL,
    entry_rr NUMERIC,
    last_event_at TIMESTAMPTZ NOT NULL,
    last_received_at TIMESTAMPTZ NOT NULL,
    CHECK (
        (ote_top IS NULL AND ote_bottom IS NULL AND ote_confirmed_at IS NULL)
        OR (
            ote_top IS NOT NULL
            AND ote_bottom IS NOT NULL
            AND ote_confirmed_at IS NOT NULL
            AND ote_top > ote_bottom
        )
    ),
    UNIQUE (setup_id, attempt_no)
);

CREATE INDEX IF NOT EXISTS idx_polr_entry_attempts_setup_status
    ON polr_entry_attempts (setup_id, status, attempt_no);

CREATE INDEX IF NOT EXISTS idx_polr_entry_attempts_status_event
    ON polr_entry_attempts (status, last_event_at DESC);

CREATE OR REPLACE FUNCTION reject_polr_entry_attempt_identity_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.entry_id IS DISTINCT FROM OLD.entry_id
       OR NEW.setup_id IS DISTINCT FROM OLD.setup_id
       OR NEW.attempt_no IS DISTINCT FROM OLD.attempt_no
       OR NEW.source IS DISTINCT FROM OLD.source
       OR NEW.confirmation_method IS DISTINCT FROM OLD.confirmation_method
       OR NEW.zone_top IS DISTINCT FROM OLD.zone_top
       OR NEW.zone_bottom IS DISTINCT FROM OLD.zone_bottom
       OR NEW.ote_top IS DISTINCT FROM OLD.ote_top
       OR NEW.ote_bottom IS DISTINCT FROM OLD.ote_bottom
       OR NEW.ote_confirmed_at IS DISTINCT FROM OLD.ote_confirmed_at
       OR NEW.range_low IS DISTINCT FROM OLD.range_low
       OR NEW.range_high IS DISTINCT FROM OLD.range_high
       OR NEW.range_third IS DISTINCT FROM OLD.range_third
       OR NEW.ote_required IS DISTINCT FROM OLD.ote_required
       OR NEW.touched_at IS DISTINCT FROM OLD.touched_at
       OR NEW.target_price IS DISTINCT FROM OLD.target_price THEN
        RAISE EXCEPTION 'POLR entry attempt identity and frozen geometry are immutable';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS polr_entry_attempt_identity_immutable
    ON polr_entry_attempts;
CREATE TRIGGER polr_entry_attempt_identity_immutable
BEFORE UPDATE ON polr_entry_attempts
FOR EACH ROW EXECUTE FUNCTION reject_polr_entry_attempt_identity_mutation();
