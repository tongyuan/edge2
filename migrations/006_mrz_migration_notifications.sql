ALTER TABLE web_push_notifications
    ADD COLUMN IF NOT EXISTS source_event_sequence INTEGER,
    ADD COLUMN IF NOT EXISTS previous_route_owner TEXT,
    ADD COLUMN IF NOT EXISTS previous_core_mrz_lower NUMERIC,
    ADD COLUMN IF NOT EXISTS previous_core_mrz_upper NUMERIC,
    ADD COLUMN IF NOT EXISTS occurred_at TIMESTAMPTZ;

UPDATE web_push_notifications
SET occurred_at = activated_at
WHERE occurred_at IS NULL;

UPDATE web_push_notifications n
SET source_event_sequence = e.sequence,
    previous_route_owner = e.previous_route_owner,
    previous_core_mrz_lower = e.old_core_mrz_lower,
    previous_core_mrz_upper = e.old_core_mrz_upper
FROM mrz_events e
WHERE e.event_key = n.source_event_key;

ALTER TABLE web_push_notifications
    ALTER COLUMN occurred_at SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'web_push_notification_previous_route_check'
    ) THEN
        ALTER TABLE web_push_notifications
            ADD CONSTRAINT web_push_notification_previous_route_check CHECK (
                previous_route_owner IS NULL
                OR previous_route_owner IN ('BTD', 'STR')
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'web_push_notification_previous_bounds_check'
    ) THEN
        ALTER TABLE web_push_notifications
            ADD CONSTRAINT web_push_notification_previous_bounds_check CHECK (
                (
                    previous_core_mrz_lower IS NULL
                    AND previous_core_mrz_upper IS NULL
                )
                OR (
                    previous_core_mrz_lower IS NOT NULL
                    AND previous_core_mrz_upper IS NOT NULL
                    AND previous_core_mrz_upper >= previous_core_mrz_lower
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'web_push_notification_migration_provenance_check'
    ) THEN
        ALTER TABLE web_push_notifications
            ADD CONSTRAINT web_push_notification_migration_provenance_check CHECK (
                event_type <> 'MRZ_MIGRATED'
                OR (
                    source_event_sequence IS NOT NULL
                    AND previous_route_owner IS NOT NULL
                    AND previous_core_mrz_lower IS NOT NULL
                    AND previous_core_mrz_upper IS NOT NULL
                )
            );
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS web_push_notification_cutovers (
    event_type TEXT PRIMARY KEY CHECK (event_type = 'MRZ_MIGRATED'),
    enabled_at TIMESTAMPTZ NOT NULL
);

INSERT INTO web_push_notification_cutovers (event_type, enabled_at)
VALUES ('MRZ_MIGRATED', clock_timestamp())
ON CONFLICT (event_type) DO NOTHING;

-- Baseline every migration that predates this feature as non-deliverable. The
-- row survives canonical replay because source_event_key is deterministic.
INSERT INTO web_push_notifications (
    source_event_key,
    source_trigger_event_id,
    source_event_sequence,
    event_type,
    symbol,
    route_owner,
    previous_route_owner,
    structural_location,
    previous_core_mrz_lower,
    previous_core_mrz_upper,
    core_mrz_lower,
    core_mrz_upper,
    activated_at,
    occurred_at,
    deliverable
)
SELECT
    event_key,
    trigger_event_id,
    sequence,
    event_type,
    symbol,
    route_owner,
    previous_route_owner,
    structural_location,
    old_core_mrz_lower,
    old_core_mrz_upper,
    new_core_mrz_lower,
    new_core_mrz_upper,
    occurred_at,
    occurred_at,
    FALSE
FROM mrz_events
WHERE event_type = 'MRZ_MIGRATED'
ON CONFLICT (source_event_key) DO NOTHING;
