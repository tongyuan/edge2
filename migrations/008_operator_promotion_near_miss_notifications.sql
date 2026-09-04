CREATE TABLE IF NOT EXISTS operator_mrz_promotions (
    id BIGSERIAL PRIMARY KEY,
    promotion_key TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL UNIQUE,
    route_owner TEXT NOT NULL CHECK (route_owner IN ('BTD', 'STR')),
    candidate_identity TEXT NOT NULL UNIQUE CHECK (
        candidate_identity ~ '^[a-f0-9]{64}$'
    ),
    evaluator_identity TEXT NOT NULL,
    candidate_lower NUMERIC NOT NULL,
    candidate_upper NUMERIC NOT NULL,
    candidate_midpoint NUMERIC NOT NULL,
    structural_location TEXT NOT NULL CHECK (
        structural_location IN (
            'deep_discount_core_mrz',
            'shallow_discount_core_mrz',
            'shallow_premium_core_mrz',
            'deep_premium_core_mrz'
        )
    ),
    normalized_span NUMERIC NOT NULL CHECK (
        normalized_span > 0.01 AND normalized_span <= 0.02
    ),
    minimum_required_allowance_pct NUMERIC NOT NULL CHECK (
        minimum_required_allowance_pct > 1.00
        AND minimum_required_allowance_pct <= 2.00
    ),
    production_threshold_pct NUMERIC NOT NULL CHECK (
        production_threshold_pct = 1.00
    ),
    shortfall_percentage_points NUMERIC NOT NULL CHECK (
        shortfall_percentage_points > 0
    ),
    supporting_observation_count INTEGER NOT NULL CHECK (
        supporting_observation_count >= 4
    ),
    supporting_observation_ids JSONB NOT NULL,
    candidate_timestamp TIMESTAMPTZ NOT NULL,
    trigger_event_id TEXT NOT NULL REFERENCES observations(event_id),
    formation_started_at TIMESTAMPTZ NOT NULL,
    formation_completed_at TIMESTAMPTZ NOT NULL,
    formation_duration_seconds NUMERIC NOT NULL CHECK (
        formation_duration_seconds >= 0
    ),
    ipda_20w_high NUMERIC NOT NULL,
    ipda_20w_low NUMERIC NOT NULL,
    ipda_width NUMERIC NOT NULL CHECK (ipda_width > 0),
    instrument_tick NUMERIC NOT NULL CHECK (instrument_tick > 0),
    promoted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    operator_identity TEXT,
    CONSTRAINT operator_mrz_promotion_bounds_check CHECK (
        candidate_upper >= candidate_lower
        AND candidate_midpoint = (candidate_lower + candidate_upper) / 2
    ),
    CONSTRAINT operator_mrz_promotion_allowance_check CHECK (
        minimum_required_allowance_pct - production_threshold_pct
            = shortfall_percentage_points
        AND normalized_span * 100 = minimum_required_allowance_pct
    ),
    CONSTRAINT operator_mrz_promotion_formation_check CHECK (
        formation_completed_at >= formation_started_at
        AND formation_duration_seconds = EXTRACT(
            EPOCH FROM formation_completed_at - formation_started_at
        )
    ),
    CONSTRAINT operator_mrz_promotion_supporting_ids_check CHECK (
        jsonb_typeof(supporting_observation_ids) = 'array'
        AND jsonb_array_length(supporting_observation_ids)
            = supporting_observation_count
    )
);

CREATE OR REPLACE FUNCTION reject_operator_mrz_promotion_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'operator MRZ promotion provenance is immutable';
END;
$$;

DROP TRIGGER IF EXISTS operator_mrz_promotions_immutable
    ON operator_mrz_promotions;
CREATE TRIGGER operator_mrz_promotions_immutable
BEFORE UPDATE OR DELETE ON operator_mrz_promotions
FOR EACH ROW EXECUTE FUNCTION reject_operator_mrz_promotion_mutation();

ALTER TABLE active_mrz
    ADD COLUMN IF NOT EXISTS activation_source TEXT;

UPDATE active_mrz
SET activation_source = 'PRODUCTION_QUALIFIED'
WHERE activation_source IS NULL;

ALTER TABLE active_mrz
    ALTER COLUMN activation_source SET NOT NULL;

ALTER TABLE active_mrz
    DROP CONSTRAINT IF EXISTS active_mrz_activation_source_check;
ALTER TABLE active_mrz
    ADD CONSTRAINT active_mrz_activation_source_check CHECK (
        activation_source IN ('PRODUCTION_QUALIFIED', 'OPERATOR_PROMOTED')
    );

ALTER TABLE active_mrz
    DROP CONSTRAINT IF EXISTS active_mrz_normalized_span_at_activation_check;
ALTER TABLE active_mrz
    ADD CONSTRAINT active_mrz_normalized_span_at_activation_check CHECK (
        (
            activation_source = 'PRODUCTION_QUALIFIED'
            AND normalized_span_at_activation <= 0.01
        )
        OR (
            activation_source = 'OPERATOR_PROMOTED'
            AND normalized_span_at_activation <= 0.02
        )
    );

ALTER TABLE mrz_events
    ADD COLUMN IF NOT EXISTS activation_source TEXT;

UPDATE mrz_events
SET activation_source = 'PRODUCTION_QUALIFIED'
WHERE activation_source IS NULL;

ALTER TABLE mrz_events
    ALTER COLUMN activation_source SET NOT NULL;

ALTER TABLE mrz_events
    DROP CONSTRAINT IF EXISTS mrz_events_activation_source_check;
ALTER TABLE mrz_events
    ADD CONSTRAINT mrz_events_activation_source_check CHECK (
        activation_source IN ('PRODUCTION_QUALIFIED', 'OPERATOR_PROMOTED')
    );

CREATE TABLE IF NOT EXISTS mrz_production_confirmations (
    id BIGSERIAL PRIMARY KEY,
    confirmation_key TEXT NOT NULL UNIQUE,
    promotion_id BIGINT NOT NULL UNIQUE
        REFERENCES operator_mrz_promotions(id),
    symbol TEXT NOT NULL,
    route_owner TEXT NOT NULL CHECK (route_owner IN ('BTD', 'STR')),
    evaluator_identity TEXT NOT NULL,
    evaluation_identity TEXT NOT NULL,
    qualified_lower NUMERIC NOT NULL,
    qualified_upper NUMERIC NOT NULL,
    qualified_midpoint NUMERIC NOT NULL,
    structural_location TEXT NOT NULL CHECK (
        structural_location IN (
            'deep_discount_core_mrz',
            'shallow_discount_core_mrz',
            'shallow_premium_core_mrz',
            'deep_premium_core_mrz'
        )
    ),
    qualified_at TIMESTAMPTZ NOT NULL,
    trigger_event_id TEXT NOT NULL REFERENCES observations(event_id),
    normalized_span NUMERIC NOT NULL CHECK (normalized_span <= 0.01),
    minimum_required_allowance_pct NUMERIC NOT NULL CHECK (
        minimum_required_allowance_pct <= 1.00
    ),
    production_threshold_pct NUMERIC NOT NULL CHECK (
        production_threshold_pct = 1.00
    ),
    supporting_observation_count INTEGER NOT NULL CHECK (
        supporting_observation_count >= 4
    ),
    supporting_observation_ids JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT mrz_production_confirmation_bounds_check CHECK (
        qualified_upper >= qualified_lower
        AND qualified_midpoint = (qualified_lower + qualified_upper) / 2
    ),
    CONSTRAINT mrz_production_confirmation_allowance_check CHECK (
        normalized_span * 100 = minimum_required_allowance_pct
    ),
    CONSTRAINT mrz_production_confirmation_supporting_ids_check CHECK (
        jsonb_typeof(supporting_observation_ids) = 'array'
        AND jsonb_array_length(supporting_observation_ids)
            = supporting_observation_count
    )
);

CREATE INDEX IF NOT EXISTS idx_mrz_production_confirmations_symbol
    ON mrz_production_confirmations (symbol, qualified_at DESC);

CREATE TABLE IF NOT EXISTS current_production_near_miss_episodes (
    id BIGSERIAL PRIMARY KEY,
    episode_key TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    route_owner TEXT NOT NULL CHECK (route_owner IN ('BTD', 'STR')),
    source_trigger_event_id TEXT NOT NULL REFERENCES observations(event_id),
    candidate_identity TEXT NOT NULL CHECK (
        candidate_identity ~ '^[a-f0-9]{64}$'
    ),
    evaluator_identity TEXT NOT NULL,
    candidate_lower NUMERIC NOT NULL,
    candidate_upper NUMERIC NOT NULL,
    candidate_midpoint NUMERIC NOT NULL,
    structural_location TEXT NOT NULL CHECK (
        structural_location IN (
            'deep_discount_core_mrz',
            'shallow_discount_core_mrz',
            'shallow_premium_core_mrz',
            'deep_premium_core_mrz'
        )
    ),
    minimum_required_allowance_pct NUMERIC NOT NULL CHECK (
        minimum_required_allowance_pct > 1.00
        AND minimum_required_allowance_pct <= 2.00
    ),
    production_threshold_pct NUMERIC NOT NULL CHECK (
        production_threshold_pct = 1.00
    ),
    shortfall_percentage_points NUMERIC NOT NULL CHECK (
        shortfall_percentage_points > 0
    ),
    supporting_observation_count INTEGER NOT NULL CHECK (
        supporting_observation_count >= 4
    ),
    supporting_observation_ids JSONB NOT NULL,
    candidate_timestamp TIMESTAMPTZ NOT NULL,
    deliverable BOOLEAN NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    ended_at TIMESTAMPTZ,
    ended_reason TEXT CHECK (
        ended_reason IS NULL OR ended_reason IN (
            'NO_LONGER_CURRENT',
            'SYMBOL_ACTIVATED',
            'OPERATOR_PROMOTED'
        )
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT current_near_miss_episode_bounds_check CHECK (
        candidate_upper >= candidate_lower
        AND candidate_midpoint = (candidate_lower + candidate_upper) / 2
    ),
    CONSTRAINT current_near_miss_episode_end_check CHECK (
        (ended_at IS NULL AND ended_reason IS NULL)
        OR (ended_at IS NOT NULL AND ended_reason IS NOT NULL)
    ),
    CONSTRAINT current_near_miss_episode_supporting_ids_check CHECK (
        jsonb_typeof(supporting_observation_ids) = 'array'
        AND jsonb_array_length(supporting_observation_ids)
            = supporting_observation_count
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_current_near_miss_open_symbol_route
    ON current_production_near_miss_episodes (symbol, route_owner)
    WHERE ended_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_current_near_miss_trigger
    ON current_production_near_miss_episodes (source_trigger_event_id);

ALTER TABLE web_push_notifications
    DROP CONSTRAINT IF EXISTS web_push_notifications_event_type_check;
ALTER TABLE web_push_notifications
    ADD CONSTRAINT web_push_notifications_event_type_check CHECK (
        event_type IN (
            'MRZ_ACTIVATED',
            'MRZ_MIGRATED',
            'ROUTE_CHANGED',
            'MRZ_NEAR_MISS'
        )
    );

ALTER TABLE web_push_notifications
    ADD COLUMN IF NOT EXISTS candidate_identity TEXT,
    ADD COLUMN IF NOT EXISTS evaluator_identity TEXT,
    ADD COLUMN IF NOT EXISTS minimum_required_allowance_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS production_threshold_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS shortfall_percentage_points NUMERIC,
    ADD COLUMN IF NOT EXISTS supporting_observation_count INTEGER,
    ADD COLUMN IF NOT EXISTS candidate_timestamp TIMESTAMPTZ;

ALTER TABLE web_push_notifications
    DROP CONSTRAINT IF EXISTS web_push_notification_near_miss_payload_check;
ALTER TABLE web_push_notifications
    ADD CONSTRAINT web_push_notification_near_miss_payload_check CHECK (
        event_type <> 'MRZ_NEAR_MISS'
        OR (
            candidate_identity IS NOT NULL
            AND evaluator_identity IS NOT NULL
            AND minimum_required_allowance_pct > 1.00
            AND minimum_required_allowance_pct <= 2.00
            AND production_threshold_pct = 1.00
            AND shortfall_percentage_points > 0
            AND supporting_observation_count >= 4
            AND candidate_timestamp IS NOT NULL
        )
    );
