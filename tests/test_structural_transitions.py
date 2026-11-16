from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.db import connect
from app.notifications import NotificationRepository, NotificationPreferencesPayload
from app.repository import EdgeRepository, StructuralTransitionConflict
from app.validation import ObservationPayload
from tests.db_support import clean, migrate_and_clean, require_test_database


BASE_TIME = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def payload(index: int, price: str, route: str = "BTD") -> ObservationPayload:
    return ObservationPayload.model_validate({
        "schema_version": "4.3",
        "event_id": f"transition-event-{index}",
        "symbol": "AMD",
        "route": route,
        "observation_type": "reclaim" if route == "BTD" else "rejection",
        "observation_price": price,
        "ipda_20w_high": "200",
        "ipda_20w_low": "100",
        "observed_at": BASE_TIME + timedelta(minutes=index),
    })


class StructuralTransitionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database(cls)
        migrate_and_clean(cls.database_url)

    def setUp(self) -> None:
        clean(self.database_url)
        self.repository = EdgeRepository(self.database_url)
        self.notifications = NotificationRepository(self.database_url)

    def activate_btd_against_str_primary(self) -> dict:
        self.repository.ingest(payload(1, "110.0"), Decimal("0.01"))
        self.repository.initialize_primary_hypothesis(
            "AMD", "STR", "test-operator", "Explicit research hypothesis"
        )
        for index, price in enumerate(("110.2", "110.4", "110.6"), 2):
            self.repository.ingest(payload(index, price), Decimal("0.01"))
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM structural_transitions")
                columns = [item.name for item in cursor.description]
                return dict(zip(columns, cursor.fetchone(), strict=True))
        finally:
            connection.close()

    def test_only_opposite_activation_creates_one_transition(self) -> None:
        transition = self.activate_btd_against_str_primary()
        self.assertEqual(transition["previous_hypothesis"], "STR")
        self.assertEqual(transition["candidate_hypothesis"], "BTD")
        self.assertEqual(transition["status"], "PENDING")

        duplicate = self.repository.ingest(payload(4, "110.6"), Decimal("0.01"))
        self.assertTrue(duplicate.duplicate)
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM structural_transitions")
                self.assertEqual(cursor.fetchone()[0], 1)
        finally:
            connection.close()

    def test_setting_primary_alone_never_creates_transition(self) -> None:
        self.repository.ingest(payload(1, "110.0"), Decimal("0.01"))
        self.repository.initialize_primary_hypothesis("AMD", "BTD", "operator")
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM structural_transitions")
                self.assertEqual(cursor.fetchone()[0], 0)
        finally:
            connection.close()

    def test_promote_is_atomic_audited_and_stale_safe(self) -> None:
        transition = self.activate_btd_against_str_primary()
        reviewed = self.repository.review_structural_transition(
            transition["id"], action="PROMOTE",
            expected_version=transition["version"],
            operator_identity="reviewer", note="Canonical evidence reviewed",
        )
        self.assertEqual(reviewed["status"], "PROMOTED")
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT hypothesis FROM symbol_primary_hypotheses WHERE symbol = 'AMD'")
                self.assertEqual(cursor.fetchone()[0], "BTD")
                cursor.execute("SELECT action, previous_hypothesis, new_hypothesis FROM structural_transition_review_history")
                self.assertEqual(cursor.fetchone(), ("PROMOTE", "STR", "BTD"))
                cursor.execute("SELECT action, transition_id FROM primary_hypothesis_history ORDER BY id DESC LIMIT 1")
                self.assertEqual(cursor.fetchone(), ("PROMOTED", transition["id"]))
        finally:
            connection.close()
        with self.assertRaises(StructuralTransitionConflict):
            self.repository.review_structural_transition(
                transition["id"], action="RETAIN_PRIMARY",
                expected_version=transition["version"], operator_identity="reviewer",
            )

    def test_defer_remains_pending_and_read_does_not_review(self) -> None:
        transition = self.activate_btd_against_str_primary()
        deferred = self.repository.review_structural_transition(
            transition["id"], action="DEFER",
            expected_version=transition["version"], operator_identity="reviewer",
        )
        self.assertEqual(deferred["status"], "PENDING")
        notification_ids = self.notifications.reconcile_notifiable_events(
            transition["trigger_event_id"]
        )
        self.assertEqual(len(notification_ids), 2)  # activation + distinct transition
        inbox = self.notifications.inbox()
        transition_item = next(
            item for item in inbox["items"]
            if item["event_type"] == "STRUCTURAL_TRANSITION"
        )
        self.notifications.mark_read(transition_item["id"])
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT status, reviewed_at FROM structural_transitions WHERE id = %s", (transition["id"],))
                self.assertEqual(cursor.fetchone(), ("PENDING", None))
        finally:
            connection.close()

    def test_notification_preference_is_independent_of_event_storage(self) -> None:
        transition = self.activate_btd_against_str_primary()
        self.notifications.update_notification_preferences(
            NotificationPreferencesPayload(
                alert_scope="ALL_SYMBOLS", activation_enabled=False,
                migration_enabled=True, pressure_enabled=False,
                near_miss_enabled=True, structural_transition_enabled=False,
            )
        )
        self.notifications.reconcile_notifiable_events(transition["trigger_event_id"])
        self.assertEqual(self.notifications.site_events_after(0), [])
        self.assertTrue(any(
            item["event_type"] == "STRUCTURAL_TRANSITION"
            for item in self.notifications.inbox()["items"]
        ))


if __name__ == "__main__":
    unittest.main()
