ALTER TABLE active_mrz
    ADD COLUMN IF NOT EXISTS supporting_observation_count INTEGER;

UPDATE active_mrz
SET supporting_observation_count = confirming_observation_count
WHERE supporting_observation_count IS NULL;

ALTER TABLE active_mrz
    ALTER COLUMN supporting_observation_count SET NOT NULL;

DO $$
BEGIN
    ALTER TABLE active_mrz
        ADD CONSTRAINT active_mrz_supporting_observation_count_check
        CHECK (supporting_observation_count >= confirming_observation_count);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

ALTER TABLE mrz_events
    ADD COLUMN IF NOT EXISTS old_supporting_observation_count INTEGER,
    ADD COLUMN IF NOT EXISTS new_supporting_observation_count INTEGER;

UPDATE mrz_events
SET new_supporting_observation_count = confirming_observation_count
WHERE new_supporting_observation_count IS NULL;

ALTER TABLE mrz_events
    ALTER COLUMN new_supporting_observation_count SET NOT NULL;

DO $$
BEGIN
    ALTER TABLE mrz_events
        ADD CONSTRAINT mrz_events_old_supporting_observation_count_check
        CHECK (old_supporting_observation_count IS NULL OR old_supporting_observation_count >= 4);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE mrz_events
        ADD CONSTRAINT mrz_events_new_supporting_observation_count_check
        CHECK (new_supporting_observation_count >= confirming_observation_count);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
