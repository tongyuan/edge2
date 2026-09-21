ALTER TABLE web_push_notifications
    ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS dismissed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_web_push_notifications_inbox_active
    ON web_push_notifications (occurred_at DESC, id DESC)
    WHERE deliverable = TRUE AND dismissed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_web_push_notifications_inbox_unread
    ON web_push_notifications (id)
    WHERE deliverable = TRUE
      AND read_at IS NULL
      AND dismissed_at IS NULL;
