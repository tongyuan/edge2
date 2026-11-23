-- Structural Development notifications are released independently from the
-- legacy Structural Transition workflow.  The activation timestamp is a hard
-- boundary: evidence first known before it remains historical/shadow data.

CREATE TABLE IF NOT EXISTS structural_development_alert_release (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    available BOOLEAN NOT NULL DEFAULT FALSE,
    detector_version TEXT NOT NULL,
    live_after TIMESTAMPTZ NOT NULL,
    validated_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

ALTER TABLE notification_preferences
    ADD COLUMN IF NOT EXISTS structural_development_enabled_at TIMESTAMPTZ;

INSERT INTO structural_development_alert_release (
    singleton, available, detector_version, live_after, validated_at
) VALUES (
    TRUE, TRUE, 'SI-1.0.0', clock_timestamp(), clock_timestamp()
)
ON CONFLICT (singleton) DO NOTHING;

-- Never inherit the retired category's preference.  The new category remains
-- an explicit operator opt-in after this release migration is approved.
UPDATE notification_preferences
SET structural_development_enabled = FALSE,
    structural_development_enabled_at = NULL
WHERE structural_development_enabled IS DISTINCT FROM FALSE
   OR structural_development_enabled_at IS NOT NULL;

-- Pre-release detector output remains useful for audit, but cannot cross the
-- live-notification boundary.
UPDATE structural_developments AS development
SET live_eligible = FALSE
WHERE development.first_known_time < (
    SELECT release.live_after
    FROM structural_development_alert_release AS release
    WHERE release.singleton = TRUE
);
