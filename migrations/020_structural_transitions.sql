ALTER TABLE notification_preferences
    ADD COLUMN IF NOT EXISTS structural_transition_enabled BOOLEAN NOT NULL DEFAULT TRUE;

CREATE TABLE IF NOT EXISTS symbol_primary_hypotheses (
    symbol TEXT PRIMARY KEY REFERENCES instruments(symbol),
    hypothesis TEXT NOT NULL CHECK (hypothesis IN ('BTD', 'STR')),
    version BIGINT NOT NULL DEFAULT 1 CHECK (version > 0),
    established_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_by TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('OPERATOR_INITIALIZED', 'TRANSITION_PROMOTED'))
);

CREATE TABLE IF NOT EXISTS structural_transitions (
    id BIGSERIAL PRIMARY KEY,
    activation_event_key TEXT NOT NULL UNIQUE,
    trigger_event_id TEXT NOT NULL REFERENCES observations(event_id),
    symbol TEXT NOT NULL REFERENCES instruments(symbol),
    previous_hypothesis TEXT NOT NULL CHECK (previous_hypothesis IN ('BTD', 'STR')),
    primary_hypothesis_version BIGINT NOT NULL CHECK (primary_hypothesis_version > 0),
    candidate_hypothesis TEXT NOT NULL CHECK (candidate_hypothesis IN ('BTD', 'STR')),
    activation_event_time TIMESTAMPTZ NOT NULL,
    known_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    core_mrz_lower NUMERIC NOT NULL,
    core_mrz_upper NUMERIC NOT NULL,
    structural_location TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'PROMOTED', 'RETAINED_PRIMARY')),
    version BIGINT NOT NULL DEFAULT 1 CHECK (version > 0),
    reviewed_at TIMESTAMPTZ,
    reviewed_by TEXT,
    review_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT structural_transition_opposite_route_check CHECK (
        previous_hypothesis <> candidate_hypothesis
    ),
    CONSTRAINT structural_transition_bounds_check CHECK (
        core_mrz_upper >= core_mrz_lower
    ),
    CONSTRAINT structural_transition_review_check CHECK (
        (status = 'PENDING')
        OR (reviewed_at IS NOT NULL AND reviewed_by IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_structural_transitions_symbol_time
    ON structural_transitions (symbol, activation_event_time DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_structural_transitions_pending
    ON structural_transitions (known_at DESC, id DESC)
    WHERE status = 'PENDING';

CREATE TABLE IF NOT EXISTS structural_transition_review_history (
    id BIGSERIAL PRIMARY KEY,
    transition_id BIGINT NOT NULL REFERENCES structural_transitions(id),
    action TEXT NOT NULL CHECK (action IN ('DEFER', 'PROMOTE', 'RETAIN_PRIMARY')),
    previous_status TEXT NOT NULL CHECK (
        previous_status IN ('PENDING', 'PROMOTED', 'RETAINED_PRIMARY')
    ),
    new_status TEXT NOT NULL CHECK (
        new_status IN ('PENDING', 'PROMOTED', 'RETAINED_PRIMARY')
    ),
    previous_hypothesis TEXT NOT NULL CHECK (previous_hypothesis IN ('BTD', 'STR')),
    new_hypothesis TEXT NOT NULL CHECK (new_hypothesis IN ('BTD', 'STR')),
    operator_identity TEXT NOT NULL,
    note TEXT,
    acted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS idx_transition_review_history_transition
    ON structural_transition_review_history (transition_id, acted_at ASC, id ASC);

CREATE TABLE IF NOT EXISTS primary_hypothesis_history (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL REFERENCES instruments(symbol),
    previous_hypothesis TEXT CHECK (previous_hypothesis IN ('BTD', 'STR')),
    new_hypothesis TEXT NOT NULL CHECK (new_hypothesis IN ('BTD', 'STR')),
    action TEXT NOT NULL CHECK (action IN ('INITIALIZED', 'PROMOTED')),
    transition_id BIGINT REFERENCES structural_transitions(id),
    operator_identity TEXT NOT NULL,
    note TEXT,
    acted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_primary_hypothesis_history_transition
    ON primary_hypothesis_history (transition_id)
    WHERE transition_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_primary_hypothesis_history_symbol_time
    ON primary_hypothesis_history (symbol, acted_at DESC, id DESC);

ALTER TABLE web_push_notifications
    DROP CONSTRAINT IF EXISTS web_push_notifications_event_type_check;
ALTER TABLE web_push_notifications
    ADD CONSTRAINT web_push_notifications_event_type_check CHECK (
        event_type IN (
            'MRZ_ACTIVATED',
            'MRZ_MIGRATED',
            'ROUTE_CHANGED',
            'MRZ_NEAR_MISS',
            'POST_ACTIVATION_PRESSURE_CHANGED',
            'STRUCTURAL_TRANSITION'
        )
    );

ALTER TABLE web_push_notifications
    ADD COLUMN IF NOT EXISTS canonical_activation_event_key TEXT,
    ADD COLUMN IF NOT EXISTS previous_hypothesis TEXT,
    ADD COLUMN IF NOT EXISTS candidate_hypothesis TEXT,
    ADD COLUMN IF NOT EXISTS canonical_evidence_ref TEXT;

ALTER TABLE web_push_notifications
    DROP CONSTRAINT IF EXISTS web_push_notification_transition_payload_check;
ALTER TABLE web_push_notifications
    ADD CONSTRAINT web_push_notification_transition_payload_check CHECK (
        event_type <> 'STRUCTURAL_TRANSITION'
        OR (
            canonical_activation_event_key IS NOT NULL
            AND previous_hypothesis IN ('BTD', 'STR')
            AND candidate_hypothesis IN ('BTD', 'STR')
            AND previous_hypothesis <> candidate_hypothesis
            AND canonical_evidence_ref IS NOT NULL
        )
    );
