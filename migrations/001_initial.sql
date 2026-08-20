CREATE TABLE IF NOT EXISTS observations (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    schema_version TEXT NOT NULL CHECK (schema_version = '4.3'),
    symbol TEXT NOT NULL,
    route TEXT NOT NULL CHECK (route IN ('BTD', 'STR')),
    observation_type TEXT NOT NULL CHECK (observation_type IN ('reclaim', 'rejection')),
    observation_price NUMERIC NOT NULL CHECK (observation_price > 0),
    observation_price_tick NUMERIC NOT NULL CHECK (observation_price_tick > 0),
    ipda_20w_high NUMERIC NOT NULL,
    ipda_20w_low NUMERIC NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    raw_payload JSONB NOT NULL,
    CONSTRAINT observations_route_type_check CHECK (
        (route = 'BTD' AND observation_type = 'reclaim') OR
        (route = 'STR' AND observation_type = 'rejection')
    ),
    CONSTRAINT observations_ipda_range_check CHECK (ipda_20w_high > ipda_20w_low)
);

CREATE INDEX IF NOT EXISTS idx_observations_symbol
    ON observations (symbol);

CREATE INDEX IF NOT EXISTS idx_observations_symbol_route_order
    ON observations (symbol, route, observed_at DESC, received_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS active_mrz (
    symbol TEXT PRIMARY KEY,
    route_owner TEXT NOT NULL CHECK (route_owner IN ('BTD', 'STR')),
    core_mrz_lower NUMERIC NOT NULL,
    core_mrz_upper NUMERIC NOT NULL,
    core_mrz_midpoint NUMERIC NOT NULL,
    structural_location TEXT NOT NULL CHECK (
        structural_location IN (
            'deep_discount_core_mrz',
            'shallow_discount_core_mrz',
            'shallow_premium_core_mrz',
            'deep_premium_core_mrz'
        )
    ),
    confirming_observation_count INTEGER NOT NULL CHECK (confirming_observation_count >= 4),
    activated_at TIMESTAMPTZ NOT NULL,
    activation_event_id TEXT NOT NULL REFERENCES observations(event_id),
    ipda_20w_high_at_activation NUMERIC NOT NULL,
    ipda_20w_low_at_activation NUMERIC NOT NULL,
    ipda_width_at_activation NUMERIC NOT NULL CHECK (ipda_width_at_activation > 0),
    normalized_span_at_activation NUMERIC NOT NULL CHECK (normalized_span_at_activation <= 0.01),
    instrument_tick NUMERIC NOT NULL CHECK (instrument_tick > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT active_mrz_bounds_check CHECK (core_mrz_upper >= core_mrz_lower)
);

CREATE INDEX IF NOT EXISTS idx_active_mrz_route_owner
    ON active_mrz (route_owner);

CREATE TABLE IF NOT EXISTS mrz_events (
    id BIGSERIAL PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    event_type TEXT NOT NULL CHECK (event_type IN ('MRZ_ACTIVATED', 'MRZ_MIGRATED', 'ROUTE_CHANGED')),
    symbol TEXT NOT NULL,
    route_owner TEXT NOT NULL CHECK (route_owner IN ('BTD', 'STR')),
    previous_route_owner TEXT NULL CHECK (previous_route_owner IS NULL OR previous_route_owner IN ('BTD', 'STR')),
    occurred_at TIMESTAMPTZ NOT NULL,
    trigger_event_id TEXT NOT NULL REFERENCES observations(event_id),
    old_core_mrz_lower NUMERIC NULL,
    old_core_mrz_upper NUMERIC NULL,
    new_core_mrz_lower NUMERIC NOT NULL,
    new_core_mrz_upper NUMERIC NOT NULL,
    new_core_mrz_midpoint NUMERIC NOT NULL,
    structural_location TEXT NOT NULL,
    confirming_observation_count INTEGER NOT NULL CHECK (confirming_observation_count >= 4),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (symbol, sequence)
);

CREATE INDEX IF NOT EXISTS idx_mrz_events_symbol_order
    ON mrz_events (symbol, sequence DESC);

CREATE TABLE IF NOT EXISTS ingestion_rejections (
    id BIGSERIAL PRIMARY KEY,
    received_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    event_id TEXT NULL,
    reason_code TEXT NOT NULL,
    diagnostics JSONB NOT NULL,
    payload_fingerprint TEXT NOT NULL,
    sanitized_payload JSONB NULL
);

CREATE INDEX IF NOT EXISTS idx_ingestion_rejections_received_at
    ON ingestion_rejections (received_at DESC);

CREATE INDEX IF NOT EXISTS idx_ingestion_rejections_event_id
    ON ingestion_rejections (event_id) WHERE event_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS ingestion_metrics (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    accepted_payload_count BIGINT NOT NULL DEFAULT 0,
    rejected_payload_count BIGINT NOT NULL DEFAULT 0,
    duplicate_payload_count BIGINT NOT NULL DEFAULT 0,
    latest_accepted_webhook_at TIMESTAMPTZ NULL
);

INSERT INTO ingestion_metrics (singleton)
VALUES (TRUE)
ON CONFLICT (singleton) DO NOTHING;
