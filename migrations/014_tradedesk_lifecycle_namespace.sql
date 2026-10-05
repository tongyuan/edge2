ALTER TABLE polr_lifecycle_events RENAME TO tradedesk_lifecycle_events;
ALTER TABLE polr_setups RENAME TO tradedesk_setups;
ALTER TABLE polr_entry_attempts RENAME TO tradedesk_entry_attempts;

ALTER SEQUENCE IF EXISTS polr_lifecycle_events_id_seq
    RENAME TO tradedesk_lifecycle_events_id_seq;

ALTER TABLE tradedesk_lifecycle_events
    RENAME CONSTRAINT polr_lifecycle_events_pkey TO tradedesk_lifecycle_events_pkey;
ALTER TABLE tradedesk_lifecycle_events
    RENAME CONSTRAINT polr_lifecycle_events_event_id_key TO tradedesk_lifecycle_events_event_id_key;
ALTER TABLE tradedesk_lifecycle_events
    RENAME CONSTRAINT polr_lifecycle_events_schema_version_check TO tradedesk_lifecycle_events_schema_version_check;
ALTER TABLE tradedesk_lifecycle_events
    RENAME CONSTRAINT polr_lifecycle_events_event_type_check TO tradedesk_lifecycle_events_event_type_check;
ALTER TABLE tradedesk_lifecycle_events
    RENAME CONSTRAINT polr_lifecycle_events_direction_check TO tradedesk_lifecycle_events_direction_check;
ALTER TABLE tradedesk_lifecycle_events
    RENAME CONSTRAINT polr_lifecycle_events_target_side_check TO tradedesk_lifecycle_events_target_side_check;
ALTER TABLE tradedesk_lifecycle_events
    RENAME CONSTRAINT polr_lifecycle_events_entry_attempt_check TO tradedesk_lifecycle_events_entry_attempt_check;
ALTER TABLE tradedesk_lifecycle_events
    RENAME CONSTRAINT polr_lifecycle_events_entry_zone_check TO tradedesk_lifecycle_events_entry_zone_check;
ALTER TABLE tradedesk_lifecycle_events
    RENAME CONSTRAINT polr_lifecycle_events_ote_zone_check TO tradedesk_lifecycle_events_ote_zone_check;
ALTER TABLE tradedesk_lifecycle_events
    RENAME CONSTRAINT polr_lifecycle_events_range_check TO tradedesk_lifecycle_events_range_check;

ALTER TABLE tradedesk_setups
    RENAME CONSTRAINT polr_setups_pkey TO tradedesk_setups_pkey;
ALTER TABLE tradedesk_setups
    RENAME CONSTRAINT polr_setups_direction_check TO tradedesk_setups_direction_check;
ALTER TABLE tradedesk_setups
    RENAME CONSTRAINT polr_setups_target_side_check TO tradedesk_setups_target_side_check;
ALTER TABLE tradedesk_setups
    RENAME CONSTRAINT polr_setups_highest_grade_check TO tradedesk_setups_highest_grade_check;
ALTER TABLE tradedesk_setups
    RENAME CONSTRAINT polr_setups_status_check TO tradedesk_setups_status_check;

ALTER TABLE tradedesk_entry_attempts
    RENAME CONSTRAINT polr_entry_attempts_pkey TO tradedesk_entry_attempts_pkey;
ALTER TABLE tradedesk_entry_attempts
    RENAME CONSTRAINT polr_entry_attempts_setup_id_attempt_no_key TO tradedesk_entry_attempts_setup_id_attempt_no_key;
ALTER TABLE tradedesk_entry_attempts
    RENAME CONSTRAINT polr_entry_attempts_setup_id_fkey TO tradedesk_entry_attempts_setup_id_fkey;
ALTER TABLE tradedesk_entry_attempts
    RENAME CONSTRAINT polr_entry_attempts_attempt_no_check TO tradedesk_entry_attempts_attempt_no_check;
ALTER TABLE tradedesk_entry_attempts
    RENAME CONSTRAINT polr_entry_attempts_status_check TO tradedesk_entry_attempts_status_check;
ALTER TABLE tradedesk_entry_attempts
    RENAME CONSTRAINT polr_entry_attempts_source_check TO tradedesk_entry_attempts_source_check;
ALTER TABLE tradedesk_entry_attempts
    RENAME CONSTRAINT polr_entry_attempts_confirmation_method_check TO tradedesk_entry_attempts_confirmation_method_check;
ALTER TABLE tradedesk_entry_attempts
    RENAME CONSTRAINT polr_entry_attempts_range_third_check TO tradedesk_entry_attempts_range_third_check;
ALTER TABLE tradedesk_entry_attempts
    RENAME CONSTRAINT polr_entry_attempts_minimum_grade_check TO tradedesk_entry_attempts_minimum_grade_check;
ALTER TABLE tradedesk_entry_attempts
    RENAME CONSTRAINT polr_entry_attempts_grade_at_touch_check TO tradedesk_entry_attempts_grade_at_touch_check;
ALTER TABLE tradedesk_entry_attempts
    RENAME CONSTRAINT polr_entry_attempts_grade_at_confirmation_check TO tradedesk_entry_attempts_grade_at_confirmation_check;
ALTER TABLE tradedesk_entry_attempts
    RENAME CONSTRAINT polr_entry_attempts_check TO tradedesk_entry_attempts_check;
ALTER TABLE tradedesk_entry_attempts
    RENAME CONSTRAINT polr_entry_attempts_check1 TO tradedesk_entry_attempts_check1;
ALTER TABLE tradedesk_entry_attempts
    RENAME CONSTRAINT polr_entry_attempts_check2 TO tradedesk_entry_attempts_check2;

ALTER INDEX idx_polr_lifecycle_events_setup_order
    RENAME TO idx_tradedesk_lifecycle_events_setup_order;
ALTER INDEX idx_polr_lifecycle_events_entry_order
    RENAME TO idx_tradedesk_lifecycle_events_entry_order;
ALTER INDEX idx_polr_setups_symbol_status
    RENAME TO idx_tradedesk_setups_symbol_status;
ALTER INDEX idx_polr_entry_attempts_setup_status
    RENAME TO idx_tradedesk_entry_attempts_setup_status;
ALTER INDEX idx_polr_entry_attempts_status_event
    RENAME TO idx_tradedesk_entry_attempts_status_event;

ALTER FUNCTION reject_polr_lifecycle_event_mutation()
    RENAME TO reject_tradedesk_lifecycle_event_mutation;
ALTER TRIGGER polr_lifecycle_events_immutable ON tradedesk_lifecycle_events
    RENAME TO tradedesk_lifecycle_events_immutable;

ALTER FUNCTION reject_polr_entry_attempt_identity_mutation()
    RENAME TO reject_tradedesk_entry_attempt_identity_mutation;
ALTER TRIGGER polr_entry_attempt_identity_immutable ON tradedesk_entry_attempts
    RENAME TO tradedesk_entry_attempt_identity_immutable;

ALTER TABLE tradedesk_lifecycle_events
    DROP CONSTRAINT tradedesk_lifecycle_events_event_type_check;
ALTER TABLE tradedesk_lifecycle_events
    ADD CONSTRAINT tradedesk_lifecycle_events_event_type_check
    CHECK (
        event_type IN (
            'MSS_CONFIRMED',
            'RR_QUALIFIED',
            'GRADE_A',
            'GRADE_A_PLUS',
            'SETUP_FAILED',
            'SETUP_RETIRED',
            'TARGET_TAKEN',
            'ENTRY_TOUCHED',
            'ENTRY_CONFIRMED',
            'ENTRY_INVALIDATED',
            'ENTRY_STOPPED',
            'ENTRY_TARGET_TAKEN',
            'ENTRY_AMBIGUOUS'
        )
    );
