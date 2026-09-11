ALTER TABLE current_production_near_miss_episodes
    ADD COLUMN IF NOT EXISTS canonical_candidate_identity TEXT,
    ADD COLUMN IF NOT EXISTS canonical_candidate_event_id TEXT REFERENCES observations(event_id),
    ADD COLUMN IF NOT EXISTS canonical_candidate_lower NUMERIC,
    ADD COLUMN IF NOT EXISTS canonical_candidate_upper NUMERIC,
    ADD COLUMN IF NOT EXISTS canonical_candidate_midpoint NUMERIC,
    ADD COLUMN IF NOT EXISTS canonical_structural_location TEXT,
    ADD COLUMN IF NOT EXISTS canonical_minimum_required_allowance_pct NUMERIC,
    ADD COLUMN IF NOT EXISTS canonical_shortfall_percentage_points NUMERIC,
    ADD COLUMN IF NOT EXISTS canonical_supporting_observation_count INTEGER,
    ADD COLUMN IF NOT EXISTS canonical_supporting_observation_ids JSONB,
    ADD COLUMN IF NOT EXISTS canonical_candidate_timestamp TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS canonical_snapshot_reliable BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS canonical_updated_at TIMESTAMPTZ;

ALTER TABLE current_production_near_miss_episodes
    ADD CONSTRAINT current_near_miss_canonical_snapshot_check CHECK (
        canonical_snapshot_reliable = FALSE
        OR (
            canonical_candidate_identity ~ '^[a-f0-9]{64}$'
            AND canonical_candidate_event_id IS NOT NULL
            AND canonical_candidate_upper >= canonical_candidate_lower
            AND canonical_candidate_midpoint
                = (canonical_candidate_lower + canonical_candidate_upper) / 2
            AND canonical_structural_location IN (
                'deep_discount_core_mrz',
                'shallow_discount_core_mrz',
                'shallow_premium_core_mrz',
                'deep_premium_core_mrz'
            )
            AND canonical_minimum_required_allowance_pct > 1.00
            AND canonical_minimum_required_allowance_pct <= 2.00
            AND canonical_shortfall_percentage_points > 0
            AND canonical_supporting_observation_count >= 4
            AND jsonb_typeof(canonical_supporting_observation_ids) = 'array'
            AND jsonb_array_length(canonical_supporting_observation_ids)
                = canonical_supporting_observation_count
            AND canonical_candidate_timestamp IS NOT NULL
            AND canonical_updated_at IS NOT NULL
        )
    );

CREATE INDEX IF NOT EXISTS idx_current_near_miss_diagnosis_history
    ON current_production_near_miss_episodes (
        symbol, route_owner, canonical_snapshot_reliable, started_at DESC
    );

-- Deliberately no historical backfill: legacy rows hold the entry snapshot, not
-- necessarily the final eligible candidate. Open rows become trustworthy on their
-- next canonical synchronization; newly created rows are trustworthy immediately.
