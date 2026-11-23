from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.db import connect
from app.notifications import NotificationRepository
from app.notifications import (
    NotificationPreferencesPayload,
    PushSubscriptionPayload,
)
from app.repository import EdgeRepository, StructuralTransitionConflict
from app.validation import ObservationPayload
from tests.db_support import clean, migrate_and_clean, require_test_database


BASE_TIME = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def payload(index: int, price: str, route: str = "BTD") -> ObservationPayload:
    return ObservationPayload.model_validate({
        "schema_version": "4.3",
        "event_id": f"transition-{route.lower()}-event-{index}",
        "symbol": "AMD",
        "route": route,
        "observation_type": "reclaim" if route == "BTD" else "rejection",
        "observation_price": price,
        "ipda_20w_high": "200",
        "ipda_20w_low": "100",
        "observed_at": BASE_TIME + timedelta(minutes=index),
    })


class LegacyStructuralTransitionRetirementTests(unittest.TestCase):
    """Opposite-route activation is retained as history, not a new trigger."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database(cls)
        migrate_and_clean(cls.database_url)

    def setUp(self) -> None:
        clean(self.database_url)
        self.repository = EdgeRepository(self.database_url)
        self.notifications = NotificationRepository(self.database_url)

    def activate_opposite_route(self) -> None:
        self.repository.ingest(payload(0, "150", "STR"), Decimal("0.01"))
        for index, price in enumerate(("110.0", "110.2", "110.4", "110.6"), 1):
            self.repository.ingest(payload(index, price), Decimal("0.01"))

    def insert_legacy_transition_notification(self) -> int:
        self.activate_opposite_route()
        connection = connect(self.database_url)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT event_key, trigger_event_id, symbol, route_owner,
                               occurred_at, new_core_mrz_lower,
                               new_core_mrz_upper, structural_location
                        FROM mrz_events
                        WHERE event_type = 'MRZ_ACTIVATED'
                        ORDER BY id DESC LIMIT 1
                        """
                    )
                    event = cursor.fetchone()
                    previous = "STR" if event[3] == "BTD" else "BTD"
                    cursor.execute(
                        """
                        INSERT INTO structural_transitions (
                            activation_event_key, trigger_event_id, symbol,
                            previous_hypothesis, candidate_hypothesis,
                            primary_hypothesis_version, activation_event_time,
                            core_mrz_lower, core_mrz_upper, structural_location,
                            confirming_observation_count
                        ) VALUES (%s, %s, %s, %s, %s, 1, %s, %s, %s, %s, 4)
                        RETURNING id
                        """,
                        (event[0], event[1], event[2], previous, event[3],
                         event[4], event[5], event[6], event[7]),
                    )
                    transition_id = int(cursor.fetchone()[0])
                    cursor.execute(
                        """
                        INSERT INTO web_push_notifications (
                            source_event_key, source_trigger_event_id, event_type,
                            symbol, route_owner, structural_location,
                            core_mrz_lower, core_mrz_upper, activated_at,
                            occurred_at, deliverable,
                            canonical_activation_event_key,
                            previous_hypothesis, candidate_hypothesis,
                            canonical_evidence_ref, structural_transition_id,
                            transition_review_status
                        ) VALUES (
                            %s, %s, 'STRUCTURAL_TRANSITION', %s, %s, %s,
                            %s, %s, %s, %s, TRUE, %s, %s, %s, %s, %s, 'PENDING'
                        )
                        """,
                        (f"legacy-transition:{transition_id}", event[1], event[2],
                         event[3], event[7], event[5], event[6], event[4],
                         event[4], event[0], previous, event[3], event[0],
                         transition_id),
                    )
                    return transition_id
        finally:
            connection.close()

    def insert_structural_development_notification(self, suffix: str = "live") -> int:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM mrz_events")
                has_events = int(cursor.fetchone()[0]) > 0
        finally:
            connection.close()
        if not has_events:
            self.activate_opposite_route()
        connection = connect(self.database_url)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT event_key, trigger_event_id, symbol, sequence,
                               occurred_at, created_at
                        FROM mrz_events
                        WHERE event_type = 'MRZ_ACTIVATED'
                        ORDER BY id DESC LIMIT 1
                        """
                    )
                    event_key, trigger_id, symbol, sequence, occurred_at, known_at = cursor.fetchone()
                    cursor.execute(
                        """
                        INSERT INTO structural_developments (
                            development_key, symbol, source_trigger_event_id,
                            development_type, maturity, migration_structure,
                            route_hypothesis, migration_sequence,
                            pivot_event_key, supporting_event_keys,
                            event_time, first_known_time, confirmation_time,
                            detector_version, live_eligible
                        ) VALUES (
                            %s, %s, %s, 'HL', 'confirmed',
                            'transitional', 'STR_DOMINANT_EMERGING_BTD', %s, %s,
                            jsonb_build_array(%s, %s), %s, %s, %s,
                            'SI-1.0.0', TRUE
                        )
                        RETURNING id
                        """,
                        (f"SD:test:{suffix}", symbol, trigger_id, sequence, event_key, event_key,
                         event_key, occurred_at, known_at, known_at),
                    )
                    development_id = int(cursor.fetchone()[0])
        finally:
            connection.close()
        self.notifications.reconcile_notifiable_events()
        return development_id

    def test_opposite_activation_does_not_create_legacy_transition(self) -> None:
        self.activate_opposite_route()
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM structural_transitions")
                self.assertEqual(cursor.fetchone()[0], 0)
        finally:
            connection.close()

    def test_opposite_activation_keeps_only_independent_mrz_notification(self) -> None:
        self.activate_opposite_route()
        ids = self.notifications.reconcile_notifiable_events("transition-btd-event-4")
        self.assertEqual(len(ids), 1)
        self.assertFalse(any(
            item["event_type"] == "STRUCTURAL_TRANSITION"
            for item in self.notifications.inbox()["items"]
        ))

    def test_structural_development_preference_is_default_disabled(self) -> None:
        preferences = self.notifications.notification_preferences()
        self.assertFalse(preferences["structural_development_enabled"])
        self.assertTrue(preferences["structural_development_available"])

    def test_opposite_activation_alone_creates_no_structural_development(self) -> None:
        self.activate_opposite_route()
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM structural_developments WHERE live_eligible = TRUE")
                self.assertEqual(cursor.fetchone()[0], 0)
                cursor.execute("SELECT count(*) FROM web_push_notifications WHERE event_type = 'STRUCTURAL_DEVELOPMENT'")
                self.assertEqual(cursor.fetchone()[0], 0)
        finally:
            connection.close()

    def test_preference_is_operator_controlled_and_persists(self) -> None:
        current = self.notifications.notification_preferences()
        payload = NotificationPreferencesPayload.model_validate({
            key: current[key]
            for key in (
                "alert_scope", "activation_enabled", "migration_enabled",
                "pressure_enabled", "near_miss_enabled",
                "structural_transition_enabled", "structural_development_enabled",
            )
        })
        enabled = payload.model_copy(update={"structural_development_enabled": True})
        enabled_preferences = self.notifications.update_notification_preferences(enabled)
        self.assertTrue(enabled_preferences["structural_development_enabled"])
        self.assertIsNotNone(enabled_preferences["structural_development_enabled_at"])
        disabled = enabled.model_copy(update={"structural_development_enabled": False})
        disabled_preferences = self.notifications.update_notification_preferences(disabled)
        self.assertFalse(disabled_preferences["structural_development_enabled"])
        self.assertIsNone(disabled_preferences["structural_development_enabled_at"])

    def test_unvalidated_release_cannot_be_enabled(self) -> None:
        connection = connect(self.database_url)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE structural_development_alert_release SET available = FALSE"
                    )
        finally:
            connection.close()
        current = self.notifications.notification_preferences()
        payload = NotificationPreferencesPayload.model_validate({
            **{key: current[key] for key in (
                "alert_scope", "activation_enabled", "migration_enabled",
                "pressure_enabled", "near_miss_enabled",
                "structural_transition_enabled",
            )},
            "structural_development_enabled": True,
        })
        with self.assertRaises(ValueError):
            self.notifications.update_notification_preferences(payload)

    def test_legacy_history_is_auditable_but_excluded_from_active_inbox(self) -> None:
        transition_id = self.insert_legacy_transition_notification()
        active = self.notifications.inbox()
        audit = self.notifications.event_history()
        self.assertFalse(any(item["event_type"] == "STRUCTURAL_TRANSITION" for item in active["items"]))
        self.assertTrue(any(item["event_type"] == "STRUCTURAL_TRANSITION" for item in audit))
        self.assertEqual(active["unread_count"], len(active["items"]))
        with self.assertRaises(StructuralTransitionConflict) as context:
            self.repository.review_structural_transition(
                transition_id,
                action="PROMOTE",
                expected_version=1,
                operator_identity="test-operator",
            )
        self.assertEqual(context.exception.code, "transition_review_retired")

    def test_only_post_boundary_development_enters_outbox_once(self) -> None:
        self.activate_opposite_route()
        connection = connect(self.database_url)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT event_key, trigger_event_id, symbol, sequence,
                               occurred_at, created_at
                        FROM mrz_events
                        WHERE event_type = 'MRZ_ACTIVATED'
                        ORDER BY id DESC LIMIT 1
                        """
                    )
                    event_key, trigger_id, symbol, sequence, occurred_at, known_at = cursor.fetchone()
                    for suffix, live_eligible in (("historical", False), ("live", True)):
                        cursor.execute(
                            """
                            INSERT INTO structural_developments (
                                development_key, symbol, source_trigger_event_id,
                                development_type, maturity, migration_structure,
                                route_hypothesis, migration_sequence,
                                pivot_event_key, supporting_event_keys,
                                event_time, first_known_time, confirmation_time,
                                detector_version, live_eligible
                            ) VALUES (
                                %s, %s, %s, 'HL', 'confirmed', 'transitional',
                                'STR_DOMINANT_EMERGING_BTD', %s, %s,
                                jsonb_build_array(%s, %s), %s, %s, %s,
                                'SI-1.0.0', %s
                            )
                            """,
                            (f"SD:test:{suffix}", symbol, trigger_id, sequence,
                             event_key, event_key, event_key, occurred_at,
                             known_at, known_at, live_eligible),
                        )
        finally:
            connection.close()

        self.notifications.reconcile_notifiable_events()
        self.notifications.reconcile_notifiable_events()
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*)
                    FROM web_push_notifications
                    WHERE event_type = 'STRUCTURAL_DEVELOPMENT'
                    """
                )
                self.assertEqual(cursor.fetchone()[0], 1)
        finally:
            connection.close()
        item = next(
            item for item in self.notifications.event_history()
            if item["event_type"] == "STRUCTURAL_DEVELOPMENT"
        )
        self.assertIn("focus=migration-path", item["destination"])
        history = self.repository.symbol_inspection_history("AMD")
        self.assertEqual(len(history["structural_developments"]), 2)

    def test_structural_delivery_respects_preference_scope_and_device(self) -> None:
        endpoint = "https://push.example.test/structural-device"
        subscription = PushSubscriptionPayload.model_validate({
            "endpoint": endpoint,
            "keys": {"p256dh": "A" * 87, "auth": "B" * 22},
        })
        self.notifications.upsert_subscription(subscription)
        self.insert_structural_development_notification()
        self.assertFalse(any(
            row["event_type"] == "STRUCTURAL_DEVELOPMENT"
            for row in self.notifications.pending_deliveries()
        ))

        current = self.notifications.notification_preferences()
        base = NotificationPreferencesPayload.model_validate({
            key: current[key]
            for key in (
                "alert_scope", "activation_enabled", "migration_enabled",
                "pressure_enabled", "near_miss_enabled",
                "structural_transition_enabled", "structural_development_enabled",
            )
        })
        enabled = base.model_copy(update={"structural_development_enabled": True})
        self.notifications.update_notification_preferences(enabled)
        self.assertFalse(any(
            row["event_type"] == "STRUCTURAL_DEVELOPMENT"
            for row in self.notifications.pending_deliveries()
        ), "enabling the preference must not release the pre-enable backlog")
        self.insert_structural_development_notification("after-enable")
        structural = [
            row for row in self.notifications.pending_deliveries()
            if row["event_type"] == "STRUCTURAL_DEVELOPMENT"
        ]
        self.assertEqual(len(structural), 1)

        tracked = enabled.model_copy(update={"alert_scope": "TRACKED_GROUPS_ONLY"})
        self.notifications.update_notification_preferences(tracked)
        self.assertFalse(any(
            row["event_type"] == "STRUCTURAL_DEVELOPMENT"
            for row in self.notifications.pending_deliveries()
        ))
        connection = connect(self.database_url)
        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO saved_symbol_groups (name, member_symbols)
                        VALUES ('Tracked', ARRAY['AMD'])
                        """
                    )
        finally:
            connection.close()
        self.assertEqual(
            len([
                row for row in self.notifications.pending_deliveries()
                if row["event_type"] == "STRUCTURAL_DEVELOPMENT"
            ]),
            1,
        )
        self.notifications.disable_subscription(endpoint)
        self.assertEqual(self.notifications.pending_deliveries(), [])

    def test_legacy_tables_remain_available_for_rollback(self) -> None:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.structural_transitions')")
                self.assertEqual(cursor.fetchone()[0], "structural_transitions")
                cursor.execute("SELECT to_regclass('public.structural_transition_review_history')")
                self.assertEqual(cursor.fetchone()[0], "structural_transition_review_history")
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
