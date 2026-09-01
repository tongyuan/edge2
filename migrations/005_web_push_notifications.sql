CREATE TABLE IF NOT EXISTS web_push_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    endpoint TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    disabled_reason TEXT CHECK (
        disabled_reason IS NULL OR disabled_reason IN ('operator', 'expired')
    ),
    enabled_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    failure_count INTEGER NOT NULL DEFAULT 0 CHECK (failure_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_web_push_subscriptions_enabled
    ON web_push_subscriptions (id)
    WHERE enabled = TRUE;

CREATE TABLE IF NOT EXISTS web_push_notifications (
    id BIGSERIAL PRIMARY KEY,
    source_event_key TEXT NOT NULL UNIQUE,
    source_trigger_event_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (
        event_type IN ('MRZ_ACTIVATED', 'MRZ_MIGRATED', 'ROUTE_CHANGED')
    ),
    symbol TEXT NOT NULL,
    route_owner TEXT NOT NULL CHECK (route_owner IN ('BTD', 'STR')),
    structural_location TEXT NOT NULL,
    core_mrz_lower NUMERIC NOT NULL,
    core_mrz_upper NUMERIC NOT NULL,
    activated_at TIMESTAMPTZ NOT NULL,
    deliverable BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT web_push_notification_bounds_check CHECK (
        core_mrz_upper >= core_mrz_lower
    )
);

CREATE INDEX IF NOT EXISTS idx_web_push_notifications_deliverable
    ON web_push_notifications (id)
    WHERE deliverable = TRUE;

CREATE TABLE IF NOT EXISTS web_push_delivery_attempts (
    id BIGSERIAL PRIMARY KEY,
    notification_id BIGINT NOT NULL REFERENCES web_push_notifications(id) ON DELETE CASCADE,
    subscription_id BIGINT NOT NULL REFERENCES web_push_subscriptions(id) ON DELETE CASCADE,
    attempt_number SMALLINT NOT NULL CHECK (attempt_number BETWEEN 1 AND 3),
    outcome TEXT NOT NULL CHECK (outcome IN ('CLAIMED', 'DELIVERED', 'FAILED')),
    retryable BOOLEAN NOT NULL DEFAULT FALSE,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    completed_at TIMESTAMPTZ,
    http_status INTEGER,
    error_code TEXT,
    CONSTRAINT web_push_delivery_retryable_outcome_check CHECK (
        retryable = FALSE OR outcome = 'FAILED'
    ),
    UNIQUE (notification_id, subscription_id, attempt_number)
);

CREATE INDEX IF NOT EXISTS idx_web_push_delivery_attempts_notification
    ON web_push_delivery_attempts (notification_id, subscription_id);

-- Establish a non-deliverable baseline for activation history that predates
-- this subsystem. This prevents deployment or replay from notifying old MRZs.
INSERT INTO web_push_notifications (
    source_event_key,
    source_trigger_event_id,
    event_type,
    symbol,
    route_owner,
    structural_location,
    core_mrz_lower,
    core_mrz_upper,
    activated_at,
    deliverable
)
SELECT
    event_key,
    trigger_event_id,
    event_type,
    symbol,
    route_owner,
    structural_location,
    new_core_mrz_lower,
    new_core_mrz_upper,
    occurred_at,
    FALSE
FROM mrz_events
WHERE event_type = 'MRZ_ACTIVATED'
ON CONFLICT (source_event_key) DO NOTHING;
