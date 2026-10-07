CREATE TABLE IF NOT EXISTS notification_preferences (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    alert_scope TEXT NOT NULL DEFAULT 'ALL_SYMBOLS'
        CHECK (alert_scope IN ('TRACKED_GROUPS_ONLY', 'ALL_SYMBOLS')),
    activation_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    migration_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    pressure_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    near_miss_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Preserve the pre-preference behavior for existing installations. Operators can
-- opt into tracked-only interruption without changing canonical event storage.
INSERT INTO notification_preferences (singleton, alert_scope)
VALUES (TRUE, 'ALL_SYMBOLS')
ON CONFLICT (singleton) DO NOTHING;
