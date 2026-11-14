from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.db import connect
from app.notifications import NotificationRepository
from app.repository import EdgeRepository
from app.validation import ObservationPayload
from tests.db_support import clean, migrate_and_clean, require_test_database


BASE_TIME = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)


class PressureRetirementIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database(cls)
        migrate_and_clean(cls.database_url)

    def setUp(self) -> None:
        clean(self.database_url)
        self.repository = EdgeRepository(self.database_url)

    def count(self, table: str) -> int:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                return int(cursor.fetchone()[0])
        finally:
            connection.close()

    def pressure_notification_count(self) -> int:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM web_push_notifications "
                    "WHERE event_type = 'POST_ACTIVATION_PRESSURE_CHANGED'"
                )
                return int(cursor.fetchone()[0])
        finally:
            connection.close()

    def ingest(self, index: int, price: str) -> None:
        payload = ObservationPayload.model_validate({
            "schema_version": "4.3",
            "event_id": f"retirement-{index}",
            "symbol": "SPXUSDT",
            "route": "BTD",
            "observation_type": "reclaim",
            "observation_price": price,
            "ipda_20w_high": "200",
            "ipda_20w_low": "100",
            "observed_at": BASE_TIME + timedelta(seconds=index),
        })
        self.repository.ingest(payload, Decimal("0.01"))

    def test_ingestion_never_creates_pressure_state_events_or_notifications(self) -> None:
        for index, price in enumerate(
            ("110", "110.2", "110.4", "110.6", "120", "121", "122"),
            1,
        ):
            self.ingest(index, price)

        self.assertEqual(self.count("current_pressure_states"), 0)
        self.assertEqual(self.count("current_pressure_events"), 0)
        self.assertEqual(self.count("post_activation_pressure_states"), 0)
        self.assertEqual(self.pressure_notification_count(), 0)

    def test_startup_and_legacy_notification_entry_points_are_inert(self) -> None:
        self.assertEqual(
            self.repository.reconcile_current_pressure_states(),
            {"baselined": 0, "recovered": 0, "retired": 1},
        )
        notifications = NotificationRepository(self.database_url)
        self.assertIsNone(notifications.reconcile_pressure_state({}, "legacy-event"))
        self.assertEqual(self.count("current_pressure_states"), 0)
        self.assertEqual(self.count("current_pressure_events"), 0)
        self.assertEqual(self.count("post_activation_pressure_states"), 0)
        self.assertEqual(self.count("web_push_notifications"), 0)

    def test_queued_historical_pressure_notification_cannot_be_claimed(self) -> None:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO web_push_subscriptions (endpoint, p256dh, auth)
                    VALUES ('https://push.example.test/retired', 'key', 'auth')
                    RETURNING id
                    """
                )
                subscription_id = int(cursor.fetchone()[0])
                cursor.execute(
                    """
                    INSERT INTO web_push_notifications (
                        source_event_key, source_trigger_event_id, event_type,
                        symbol, route_owner, structural_location,
                        core_mrz_lower, core_mrz_upper, activated_at, occurred_at,
                        deliverable, lifecycle_activation_event_id,
                        previous_pressure_state, current_pressure_state,
                        pressure_state_label, post_activation_observation_count,
                        above_mrz_count, inside_mrz_count, below_mrz_count,
                        above_envelope_count, below_envelope_count, displacement,
                        successor_status, successor_label
                    ) VALUES (
                        'historical-pressure:test', 'legacy-trigger',
                        'POST_ACTIVATION_PRESSURE_CHANGED', 'SPXUSDT', 'BTD',
                        'deep_discount', 110, 111, clock_timestamp(),
                        clock_timestamp(), TRUE, 'legacy-activation',
                        'NEUTRAL', 'UP', 'Upward Pressure', 3, 3, 0, 0,
                        3, 0, 4.2, 'NO_SUCCESSOR', 'No successor'
                    ) RETURNING id
                    """
                )
                notification_id = int(cursor.fetchone()[0])
            connection.commit()
        finally:
            connection.close()

        notifications = NotificationRepository(self.database_url)
        self.assertEqual(notifications.pending_deliveries([notification_id]), [])
        self.assertIsNone(
            notifications.claim_delivery(notification_id, subscription_id)
        )
        self.assertEqual(self.count("web_push_delivery_attempts"), 0)


if __name__ == "__main__":
    unittest.main()
