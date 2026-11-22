from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.db import connect
from app.notifications import NotificationRepository
from app.repository import EdgeRepository
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
        self.assertFalse(
            self.notifications.notification_preferences()["structural_development_enabled"]
        )

    def test_shadow_developments_cannot_enter_live_outbox(self) -> None:
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
