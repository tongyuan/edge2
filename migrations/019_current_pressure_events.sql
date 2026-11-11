CREATE TABLE IF NOT EXISTS current_pressure_states (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    lifecycle_activation_event_id TEXT NOT NULL REFERENCES observations(event_id),
    current_state TEXT NOT NULL CHECK (current_state IN ('NEUTRAL', 'UP', 'DOWN')),
    state_status TEXT NOT NULL,
    state_label TEXT NOT NULL,
    recent_pressure_observation_count INTEGER NOT NULL CHECK (
        recent_pressure_observation_count BETWEEN 0 AND 4
    ),
    recent_higher_observation_count INTEGER NOT NULL CHECK (
        recent_higher_observation_count BETWEEN 0 AND 4
    ),
    recent_lower_observation_count INTEGER NOT NULL CHECK (
        recent_lower_observation_count BETWEEN 0 AND 4
    ),
    transition_count INTEGER NOT NULL DEFAULT 0 CHECK (transition_count >= 0),
    last_evaluated_trigger_event_id TEXT NOT NULL REFERENCES observations(event_id),
    last_evaluated_observation_id BIGINT NOT NULL REFERENCES observations(id),
    last_evaluated_received_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (symbol, lifecycle_activation_event_id),
    CONSTRAINT current_pressure_recent_counts_check CHECK (
        recent_higher_observation_count + recent_lower_observation_count
            = recent_pressure_observation_count
    )
);

CREATE INDEX IF NOT EXISTS idx_current_pressure_states_symbol
    ON current_pressure_states (symbol, updated_at DESC);

CREATE TABLE IF NOT EXISTS current_pressure_events (
    id BIGSERIAL PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    lifecycle_activation_event_id TEXT NOT NULL REFERENCES observations(event_id),
    trigger_event_id TEXT NOT NULL REFERENCES observations(event_id),
    trigger_observation_id BIGINT NOT NULL REFERENCES observations(id),
    route_owner TEXT NOT NULL CHECK (route_owner IN ('BTD', 'STR')),
    previous_state TEXT NOT NULL CHECK (previous_state IN ('NEUTRAL', 'UP', 'DOWN')),
    current_state TEXT NOT NULL CHECK (current_state IN ('NEUTRAL', 'UP', 'DOWN')),
    state_status TEXT NOT NULL,
    state_label TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    supporting_observed_at TIMESTAMPTZ,
    recent_pressure_observation_count INTEGER NOT NULL CHECK (
        recent_pressure_observation_count BETWEEN 0 AND 4
    ),
    recent_higher_observation_count INTEGER NOT NULL CHECK (
        recent_higher_observation_count BETWEEN 0 AND 4
    ),
    recent_lower_observation_count INTEGER NOT NULL CHECK (
        recent_lower_observation_count BETWEEN 0 AND 4
    ),
    recent_window_size INTEGER NOT NULL DEFAULT 4 CHECK (recent_window_size = 4),
    confirmation_count INTEGER NOT NULL DEFAULT 3 CHECK (confirmation_count = 3),
    lower_migration_boundary NUMERIC NOT NULL,
    upper_migration_boundary NUMERIC NOT NULL,
    supporting_observations JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT current_pressure_event_changed_check CHECK (previous_state <> current_state),
    CONSTRAINT current_pressure_event_recent_counts_check CHECK (
        recent_higher_observation_count + recent_lower_observation_count
            = recent_pressure_observation_count
    )
);

CREATE INDEX IF NOT EXISTS idx_current_pressure_events_history
    ON current_pressure_events (occurred_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_current_pressure_events_symbol
    ON current_pressure_events (symbol, occurred_at DESC, id DESC);
