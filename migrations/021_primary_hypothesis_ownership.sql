ALTER TABLE symbol_primary_hypotheses
    ADD COLUMN IF NOT EXISTS derived_hypothesis TEXT,
    ADD COLUMN IF NOT EXISTS operator_override_hypothesis TEXT;

ALTER TABLE symbol_primary_hypotheses
    DROP CONSTRAINT IF EXISTS symbol_primary_hypotheses_source_check;

WITH initial_hypothesis AS (
    SELECT DISTINCT ON (symbol)
        symbol,
        route AS hypothesis,
        received_at AS established_at
    FROM observations
    ORDER BY symbol ASC, received_at ASC, observed_at ASC, id ASC
)
UPDATE symbol_primary_hypotheses AS primary_state
SET derived_hypothesis = initial.hypothesis,
    hypothesis = CASE
        WHEN primary_state.source = 'OPERATOR_INITIALIZED' THEN initial.hypothesis
        ELSE primary_state.hypothesis
    END,
    operator_override_hypothesis = CASE
        WHEN primary_state.source = 'TRANSITION_PROMOTED' THEN primary_state.hypothesis
        ELSE NULL
    END,
    established_at = LEAST(primary_state.established_at, initial.established_at),
    updated_at = clock_timestamp(),
    updated_by = CASE
        WHEN primary_state.source = 'OPERATOR_INITIALIZED' THEN 'EDGE_DERIVED_BACKFILL'
        ELSE primary_state.updated_by
    END,
    source = CASE
        WHEN primary_state.source = 'OPERATOR_INITIALIZED' THEN 'EDGE_DERIVED'
        ELSE primary_state.source
    END
FROM initial_hypothesis AS initial
WHERE initial.symbol = primary_state.symbol;

INSERT INTO symbol_primary_hypotheses (
    symbol, hypothesis, derived_hypothesis,
    operator_override_hypothesis, version,
    established_at, updated_at, updated_by, source
)
SELECT
    initial.symbol, initial.hypothesis, initial.hypothesis,
    NULL, 1,
    initial.established_at, initial.established_at,
    'EDGE_DERIVED_BACKFILL', 'EDGE_DERIVED'
FROM (
    SELECT DISTINCT ON (symbol)
        symbol,
        route AS hypothesis,
        received_at AS established_at
    FROM observations
    ORDER BY symbol ASC, received_at ASC, observed_at ASC, id ASC
) AS initial
ON CONFLICT (symbol) DO NOTHING;

UPDATE symbol_primary_hypotheses
SET derived_hypothesis = hypothesis,
    operator_override_hypothesis = NULL,
    source = 'EDGE_DERIVED',
    updated_by = 'EDGE_DERIVED_BACKFILL',
    updated_at = clock_timestamp()
WHERE derived_hypothesis IS NULL;

ALTER TABLE symbol_primary_hypotheses
    ALTER COLUMN derived_hypothesis SET NOT NULL;

ALTER TABLE symbol_primary_hypotheses
    ADD CONSTRAINT symbol_primary_hypotheses_derived_check
        CHECK (derived_hypothesis IN ('BTD', 'STR')),
    ADD CONSTRAINT symbol_primary_hypotheses_override_check
        CHECK (
            operator_override_hypothesis IS NULL
            OR operator_override_hypothesis IN ('BTD', 'STR')
        ),
    ADD CONSTRAINT symbol_primary_hypotheses_source_check
        CHECK (source IN ('EDGE_DERIVED', 'TRANSITION_PROMOTED')),
    ADD CONSTRAINT symbol_primary_hypotheses_effective_check
        CHECK (
            (source = 'EDGE_DERIVED'
                AND operator_override_hypothesis IS NULL
                AND hypothesis = derived_hypothesis)
            OR
            (source = 'TRANSITION_PROMOTED'
                AND operator_override_hypothesis = hypothesis)
        );

ALTER TABLE primary_hypothesis_history
    DROP CONSTRAINT IF EXISTS primary_hypothesis_history_action_check;
ALTER TABLE primary_hypothesis_history
    ADD CONSTRAINT primary_hypothesis_history_action_check
        CHECK (action IN ('INITIALIZED', 'EDGE_DERIVED_INITIALIZED', 'PROMOTED'));

ALTER TABLE structural_transitions
    ADD COLUMN IF NOT EXISTS confirming_observation_count INTEGER;
UPDATE structural_transitions
SET confirming_observation_count = 4
WHERE confirming_observation_count IS NULL;
ALTER TABLE structural_transitions
    ALTER COLUMN confirming_observation_count SET NOT NULL,
    ADD CONSTRAINT structural_transitions_confirming_count_check
        CHECK (confirming_observation_count >= 4);

ALTER TABLE web_push_notifications
    ADD COLUMN IF NOT EXISTS structural_transition_id BIGINT
        REFERENCES structural_transitions(id),
    ADD COLUMN IF NOT EXISTS transition_review_status TEXT;

ALTER TABLE web_push_notifications
    ADD CONSTRAINT web_push_notifications_transition_status_check
        CHECK (
            transition_review_status IS NULL
            OR transition_review_status IN ('PENDING', 'PROMOTED', 'RETAINED_PRIMARY')
        );

UPDATE web_push_notifications AS notification
SET structural_transition_id = transition.id,
    transition_review_status = transition.status
FROM structural_transitions AS transition
WHERE notification.event_type = 'STRUCTURAL_TRANSITION'
  AND notification.canonical_activation_event_key = transition.activation_event_key;

ALTER TABLE web_push_notifications
    DROP CONSTRAINT IF EXISTS web_push_notification_transition_payload_check;
ALTER TABLE web_push_notifications
    ADD CONSTRAINT web_push_notification_transition_payload_check CHECK (
        event_type <> 'STRUCTURAL_TRANSITION'
        OR (
            structural_transition_id IS NOT NULL
            AND transition_review_status IS NOT NULL
            AND canonical_activation_event_key IS NOT NULL
            AND previous_hypothesis IN ('BTD', 'STR')
            AND candidate_hypothesis IN ('BTD', 'STR')
            AND previous_hypothesis <> candidate_hypothesis
            AND canonical_evidence_ref IS NOT NULL
        )
    );

CREATE UNIQUE INDEX IF NOT EXISTS idx_web_push_notifications_transition
    ON web_push_notifications (structural_transition_id)
    WHERE structural_transition_id IS NOT NULL;
