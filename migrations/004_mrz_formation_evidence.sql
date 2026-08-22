ALTER TABLE active_mrz
    ADD COLUMN IF NOT EXISTS formation_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS formation_completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS formation_duration_seconds NUMERIC;

DO $$
BEGIN
    ALTER TABLE active_mrz
        ADD CONSTRAINT active_mrz_formation_evidence_check
        CHECK (
            (
                formation_started_at IS NULL
                AND formation_completed_at IS NULL
                AND formation_duration_seconds IS NULL
            )
            OR (
                formation_started_at IS NOT NULL
                AND formation_completed_at IS NOT NULL
                AND formation_completed_at >= formation_started_at
                AND formation_duration_seconds IS NOT NULL
                AND formation_duration_seconds >= 0
                AND formation_duration_seconds = EXTRACT(
                    EPOCH FROM formation_completed_at - formation_started_at
                )
            )
        );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE mrz_events
    ADD COLUMN IF NOT EXISTS old_formation_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS old_formation_completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS old_formation_duration_seconds NUMERIC,
    ADD COLUMN IF NOT EXISTS new_formation_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS new_formation_completed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS new_formation_duration_seconds NUMERIC;

DO $$
BEGIN
    ALTER TABLE mrz_events
        ADD CONSTRAINT mrz_events_old_formation_evidence_check
        CHECK (
            (
                old_formation_started_at IS NULL
                AND old_formation_completed_at IS NULL
                AND old_formation_duration_seconds IS NULL
            )
            OR (
                old_formation_started_at IS NOT NULL
                AND old_formation_completed_at IS NOT NULL
                AND old_formation_completed_at >= old_formation_started_at
                AND old_formation_duration_seconds IS NOT NULL
                AND old_formation_duration_seconds >= 0
                AND old_formation_duration_seconds = EXTRACT(
                    EPOCH FROM old_formation_completed_at - old_formation_started_at
                )
            )
        );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE mrz_events
        ADD CONSTRAINT mrz_events_new_formation_evidence_check
        CHECK (
            (
                new_formation_started_at IS NULL
                AND new_formation_completed_at IS NULL
                AND new_formation_duration_seconds IS NULL
            )
            OR (
                new_formation_started_at IS NOT NULL
                AND new_formation_completed_at IS NOT NULL
                AND new_formation_completed_at >= new_formation_started_at
                AND new_formation_duration_seconds IS NOT NULL
                AND new_formation_duration_seconds >= 0
                AND new_formation_duration_seconds = EXTRACT(
                    EPOCH FROM new_formation_completed_at - new_formation_started_at
                )
            )
        );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
