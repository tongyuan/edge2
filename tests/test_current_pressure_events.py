from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.db import connect
from app.mrz_robustness import post_activation_snapshot
from app.notifications import NotificationRepository
from app.repository import EdgeRepository
from app.validation import ObservationPayload
from tests.db_support import clean, migrate_and_clean, require_test_database


BASE_TIME = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc)


class CurrentPressureEventIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database(cls)
        migrate_and_clean(cls.database_url)

    def setUp(self) -> None:
        clean(self.database_url)
        self.repository = EdgeRepository(self.database_url)

    def ingest(
        self,
        event_id: str,
        price: str,
        observed_offset: int,
        *,
        route: str = "BTD",
        symbol: str = "SPXUSDT",
    ):
        payload = ObservationPayload.model_validate({
            "schema_version": "4.3",
            "event_id": event_id,
            "symbol": symbol,
            "route": route,
            "observation_type": "reclaim" if route == "BTD" else "rejection",
            "observation_price": price,
            "ipda_20w_high": "200",
            "ipda_20w_low": "100",
            "observed_at": BASE_TIME + timedelta(seconds=observed_offset),
        })
        return self.repository.ingest(payload, Decimal("0.01"))

    def activate(self, *, symbol: str = "SPXUSDT") -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1):
            self.ingest(f"activation-{symbol}-{index}", price, index, symbol=symbol)

    def rows(self, query: str):
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchall()
        finally:
            connection.close()

    def test_directional_neutral_and_flip_transitions_are_persisted_once(self) -> None:
        self.activate()
        for index, price in enumerate(("120", "121", "122", "100", "99", "98"), 5):
            self.ingest(f"pressure-{index}", price, index)

        events = self.rows(
            "SELECT previous_state, current_state, supporting_observations "
            "FROM current_pressure_events ORDER BY id"
        )
        self.assertEqual(
            [(previous, current) for previous, current, _ in events],
            [("NEUTRAL", "UP"), ("UP", "NEUTRAL"), ("NEUTRAL", "DOWN")],
        )
        self.assertEqual(
            [item["direction"] for item in events[-1][2]],
            ["UP", "DOWN", "DOWN", "DOWN"],
        )

        duplicate = self.ingest("pressure-10", "98", 10)
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(
            self.rows("SELECT COUNT(*) FROM current_pressure_events")[0][0],
            3,
        )

    def test_late_observation_uses_canonical_order_and_trigger_provenance(self) -> None:
        self.activate()
        self.ingest("up-5", "120", 5)
        self.ingest("up-6", "121", 6)
        self.ingest("down-8", "100", 8)
        self.ingest("late-up-7", "122", 7)

        event = self.rows(
            "SELECT trigger_event_id, current_state, supporting_observations "
            "FROM current_pressure_events"
        )[0]
        self.assertEqual(event[0], "late-up-7")
        self.assertEqual(event[1], "UP")
        self.assertEqual(
            [item["event_id"] for item in event[2]],
            ["up-5", "up-6", "late-up-7", "down-8"],
        )

    def test_new_mrz_lifecycle_is_baselined_without_historical_transition(self) -> None:
        self.activate()
        for index, price in enumerate(("120", "121", "122"), 5):
            self.ingest(f"pressure-{index}", price, index)
        original_event_count = self.rows(
            "SELECT COUNT(*) FROM current_pressure_events"
        )[0][0]

        for index, price in enumerate(("130", "130.2", "130.4", "130.6"), 8):
            self.ingest(f"migration-{index}", price, index)

        lifecycle_rows = self.rows(
            "SELECT lifecycle_activation_event_id, current_state "
            "FROM current_pressure_states ORDER BY id"
        )
        self.assertGreaterEqual(len(lifecycle_rows), 2)
        self.assertEqual(lifecycle_rows[-1][1], "NEUTRAL")
        self.assertEqual(
            self.rows("SELECT COUNT(*) FROM current_pressure_events")[0][0],
            original_event_count,
        )

    def test_history_includes_current_transitions_but_push_stream_does_not(self) -> None:
        self.activate()
        for index, price in enumerate(("120", "121", "122"), 5):
            self.ingest(f"pressure-{index}", price, index)

        notifications = NotificationRepository(self.database_url)
        history = notifications.event_history(limit=20)
        current = next(
            item for item in history
            if item["event_type"] == "CURRENT_PRESSURE_CHANGED"
        )
        self.assertEqual(current["previous_state"], "NEUTRAL")
        self.assertEqual(current["current_state"], "UP")
        self.assertEqual(current["recent_higher_observation_count"], 3)
        self.assertEqual(notifications.site_events_after(0), [])
        self.assertEqual(
            self.rows("SELECT COUNT(*) FROM web_push_notifications")[0][0],
            0,
        )

    def test_startup_reconciliation_baselines_without_backfill(self) -> None:
        self.activate()
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM current_pressure_states")
            connection.commit()
        finally:
            connection.close()

        result = self.repository.reconcile_current_pressure_states()
        self.assertEqual(result, {"baselined": 1, "recovered": 0})
        self.assertEqual(
            self.rows("SELECT COUNT(*) FROM current_pressure_events")[0][0],
            0,
        )

    def test_grab_lower_neutral_higher_keeps_cumulative_pressure_lower(self) -> None:
        symbol = "GRAB"
        self.activate(symbol=symbol)
        for index, price in enumerate(
            ("100", "98", "96", "94", "92", "90", "88", "86", "84"),
            5,
        ):
            self.ingest(f"grab-lower-{index}", price, index, symbol=symbol)
        for index, price in enumerate(("120", "122", "124", "126"), 14):
            self.ingest(f"grab-higher-{index}", price, index, symbol=symbol)

        transitions = self.rows(
            "SELECT previous_state, current_state "
            "FROM current_pressure_events WHERE symbol = 'GRAB' ORDER BY id"
        )
        self.assertEqual(
            transitions,
            [("NEUTRAL", "DOWN"), ("DOWN", "NEUTRAL"), ("NEUTRAL", "UP")],
        )

        active_mrzs, observations, _ = self.repository.mrz_robustness_inputs()
        active = next(item for item in active_mrzs if item.symbol == symbol)
        snapshot = post_activation_snapshot(active, observations)
        self.assertEqual(snapshot.current_pressure.state.direction, "UP")
        self.assertEqual(
            [item.direction for item in snapshot.current_pressure.recent_evidence],
            ["UP", "UP", "UP", "UP"],
        )
        self.assertEqual(snapshot.current_pressure.recent_higher_count, 4)
        self.assertEqual(snapshot.state.direction, "DOWN")
        self.assertEqual(snapshot.above_envelope_count, 4)
        self.assertEqual(snapshot.below_envelope_count, 9)
