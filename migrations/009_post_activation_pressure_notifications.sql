ALTER TABLE web_push_notification_cutovers
    DROP CONSTRAINT IF EXISTS web_push_notification_cutovers_event_type_check;
ALTER TABLE web_push_notification_cutovers
    ADD CONSTRAINT web_push_notification_cutovers_event_type_check CHECK (
        event_type IN ('MRZ_MIGRATED', 'POST_ACTIVATION_PRESSURE_CHANGED')
    );

INSERT INTO web_push_notification_cutovers (event_type, enabled_at)
VALUES ('POST_ACTIVATION_PRESSURE_CHANGED', clock_timestamp())
ON CONFLICT (event_type) DO NOTHING;

CREATE TABLE IF NOT EXISTS post_activation_pressure_states (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    activation_event_id TEXT NOT NULL REFERENCES observations(event_id),
    current_state TEXT NOT NULL CHECK (current_state IN ('NEUTRAL', 'UP', 'DOWN')),
    state_status TEXT NOT NULL,
    state_label TEXT NOT NULL,
    post_activation_observation_count INTEGER NOT NULL CHECK (
        post_activation_observation_count >= 0
    ),
    above_mrz_count INTEGER NOT NULL CHECK (above_mrz_count >= 0),
    inside_mrz_count INTEGER NOT NULL CHECK (inside_mrz_count >= 0),
    below_mrz_count INTEGER NOT NULL CHECK (below_mrz_count >= 0),
    above_envelope_count INTEGER NOT NULL CHECK (above_envelope_count >= 0),
    below_envelope_count INTEGER NOT NULL CHECK (below_envelope_count >= 0),
    displacement NUMERIC,
    successor_status TEXT NOT NULL,
    successor_label TEXT NOT NULL,
    transition_count INTEGER NOT NULL DEFAULT 0 CHECK (transition_count >= 0),
    last_evaluated_trigger_event_id TEXT NOT NULL REFERENCES observations(event_id),
    last_evaluated_observation_id BIGINT NOT NULL REFERENCES observations(id),
    last_evaluated_received_at TIMESTAMPTZ NOT NULL,
    last_evaluated_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (symbol, activation_event_id),
    CONSTRAINT post_activation_pressure_position_counts_check CHECK (
        above_mrz_count + inside_mrz_count + below_mrz_count
            = post_activation_observation_count
    ),
    CONSTRAINT post_activation_pressure_envelope_counts_check CHECK (
        above_envelope_count + below_envelope_count
            <= post_activation_observation_count
    )
);

CREATE INDEX IF NOT EXISTS idx_post_activation_pressure_states_symbol
    ON post_activation_pressure_states (symbol, updated_at DESC);

ALTER TABLE web_push_notifications
    DROP CONSTRAINT IF EXISTS web_push_notifications_event_type_check;
ALTER TABLE web_push_notifications
    ADD CONSTRAINT web_push_notifications_event_type_check CHECK (
        event_type IN (
            'MRZ_ACTIVATED',
            'MRZ_MIGRATED',
            'ROUTE_CHANGED',
            'MRZ_NEAR_MISS',
            'POST_ACTIVATION_PRESSURE_CHANGED'
        )
    );

ALTER TABLE web_push_notifications
    ADD COLUMN IF NOT EXISTS lifecycle_activation_event_id TEXT,
    ADD COLUMN IF NOT EXISTS previous_pressure_state TEXT,
    ADD COLUMN IF NOT EXISTS current_pressure_state TEXT,
    ADD COLUMN IF NOT EXISTS pressure_state_label TEXT,
    ADD COLUMN IF NOT EXISTS post_activation_observation_count INTEGER,
    ADD COLUMN IF NOT EXISTS above_mrz_count INTEGER,
    ADD COLUMN IF NOT EXISTS inside_mrz_count INTEGER,
    ADD COLUMN IF NOT EXISTS below_mrz_count INTEGER,
    ADD COLUMN IF NOT EXISTS above_envelope_count INTEGER,
    ADD COLUMN IF NOT EXISTS below_envelope_count INTEGER,
    ADD COLUMN IF NOT EXISTS displacement NUMERIC,
    ADD COLUMN IF NOT EXISTS successor_status TEXT,
    ADD COLUMN IF NOT EXISTS successor_label TEXT;

ALTER TABLE web_push_notifications
    DROP CONSTRAINT IF EXISTS web_push_notification_pressure_payload_check;
ALTER TABLE web_push_notifications
    ADD CONSTRAINT web_push_notification_pressure_payload_check CHECK (
        event_type <> 'POST_ACTIVATION_PRESSURE_CHANGED'
        OR (
            lifecycle_activation_event_id IS NOT NULL
            AND previous_pressure_state IN ('NEUTRAL', 'UP', 'DOWN')
            AND current_pressure_state IN ('UP', 'DOWN')
            AND previous_pressure_state <> current_pressure_state
            AND pressure_state_label IS NOT NULL
            AND post_activation_observation_count >= 0
            AND above_mrz_count >= 0
            AND inside_mrz_count >= 0
            AND below_mrz_count >= 0
            AND above_mrz_count + inside_mrz_count + below_mrz_count
                = post_activation_observation_count
            AND above_envelope_count >= 0
            AND below_envelope_count >= 0
            AND above_envelope_count + below_envelope_count
                <= post_activation_observation_count
            AND successor_status IS NOT NULL
            AND successor_label IS NOT NULL
        )
    );
