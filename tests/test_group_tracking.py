from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.db import connect
from app.repository import EdgeRepository
from app.validation import ObservationPayload
from tests.db_support import clean, migrate_and_clean, require_test_database


BASE_TIME = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
MAG7 = ["AAPL", "AMZN", "GOOG", "META", "MSFT", "NVDA", "TSLA"]


class GroupTrackingIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database(cls)
        migrate_and_clean(cls.database_url)

    def setUp(self) -> None:
        clean(self.database_url)
        self.repository = EdgeRepository(self.database_url)
        self.packet_index = 0

    def ingest_series(
        self,
        symbol: str,
        prices: tuple[str, ...],
        *,
        route: str = "BTD",
        start_minutes: int = 0,
    ) -> None:
        for offset, price in enumerate(prices, 1):
            self.packet_index += 1
            payload = ObservationPayload.model_validate(
                {
                    "schema_version": "4.3",
                    "event_id": f"group-{symbol}-{self.packet_index}",
                    "symbol": symbol,
                    "route": route,
                    "observation_type": "reclaim" if route == "BTD" else "rejection",
                    "observation_price": price,
                    "ipda_20w_high": "200",
                    "ipda_20w_low": "100",
                    "observed_at": BASE_TIME
                    + timedelta(minutes=start_minutes, seconds=offset),
                }
            )
            self.repository.ingest(payload, Decimal("0.01"))

    def seed_mag7_history(self) -> None:
        self.ingest_series(
            "AAPL",
            ("110", "110.2", "110.4", "110.6", "120", "120.2", "120.4", "120.6"),
            start_minutes=0,
        )
        self.ingest_series(
            "AMZN",
            ("120", "120.2", "120.4", "120.6", "110.6", "110.4", "110.2", "110"),
            start_minutes=20,
        )
        self.ingest_series(
            "GOOG",
            ("140", "140.2", "140.4", "140.6"),
            start_minutes=40,
        )
        self.ingest_series("META", ("160",), route="STR", start_minutes=60)
        self.ingest_series(
            "MSFT",
            (
                "110", "110.2", "110.4", "110.6",
                "120", "120.2", "120.4", "120.6",
                "130", "130.2", "130.4", "130.6",
            ),
            start_minutes=80,
        )
        self.ingest_series(
            "NVDA",
            ("180", "180.2", "180.4", "180.6"),
            route="STR",
            start_minutes=120,
        )
        self.ingest_series("TSLA", ("190",), route="STR", start_minutes=140)

    def domain_counts(self) -> tuple[int, int, int]:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM observations")
                observations = int(cursor.fetchone()[0])
                cursor.execute("SELECT COUNT(*) FROM active_mrz")
                active = int(cursor.fetchone()[0])
                cursor.execute("SELECT COUNT(*) FROM mrz_events")
                events = int(cursor.fetchone()[0])
                return observations, active, events
        finally:
            connection.close()

    def test_mag7_persists_canonical_members_without_creating_domain_events(self) -> None:
        self.seed_mag7_history()
        before = self.domain_counts()

        saved = self.repository.create_saved_group(
            "MAG7",
            ["NASDAQ:aapl", "amzn", "GOOG", " meta ", "MSFT", "NVDA", "TSLA"],
        )

        self.assertEqual(saved["name"], "MAG7")
        self.assertEqual(saved["members"], MAG7)
        self.assertEqual(saved["member_count"], 7)
        self.assertEqual(self.domain_counts(), before)
        reopened = EdgeRepository(self.database_url).saved_groups()
        self.assertEqual(len(reopened), 1)
        self.assertEqual(reopened[0]["members"], MAG7)
        self.assertEqual(reopened[0]["created_at"], saved["created_at"])

    def test_current_state_and_existing_migration_path_are_available_immediately(self) -> None:
        self.seed_mag7_history()
        saved = self.repository.create_saved_group("MAG7", MAG7)

        report = self.repository.saved_group_report(saved["id"])
        self.assertEqual(report["current_state"]["location"], {
            "deep_discount": 2,
            "shallow_discount": 2,
            "shallow_premium": 1,
            "deep_premium": 2,
        })
        self.assertEqual(report["current_state"]["active_mrz"], {"count": 5, "total": 7})
        self.assertEqual(report["current_state"]["migration_breadth"], {
            "higher": 2,
            "lower": 1,
            "no_migration": 4,
        })
        self.assertEqual(sum(report["current_state"]["migration_breadth"].values()), 7)

        before_path = self.domain_counts()
        path = self.repository.saved_group_migration_path(saved["id"])
        self.assertEqual(self.domain_counts(), before_path)
        by_symbol = {item["symbol"]: item["states"] for item in path["paths"]}
        self.assertEqual([state["direction"] for state in by_symbol["AAPL"]], [None, "higher"])
        self.assertEqual([state["direction"] for state in by_symbol["AMZN"]], [None, "lower"])
        self.assertEqual(
            [state["direction"] for state in by_symbol["MSFT"]],
            [None, "higher", "higher"],
        )
        self.assertEqual(len(by_symbol["GOOG"]), 1)
        self.assertEqual(by_symbol["META"], [])
        self.assertEqual(by_symbol["TSLA"], [])

    def test_path_uses_occurred_at_persisted_location_and_is_replay_safe(self) -> None:
        self.seed_mag7_history()
        saved = self.repository.create_saved_group("MAG7", MAG7)
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE mrz_events
                    SET created_at = CASE
                        WHEN sequence = 1 THEN '2040-01-01T00:00:00Z'::timestamptz
                        ELSE '2030-01-01T00:00:00Z'::timestamptz
                    END
                    WHERE symbol IN ('AAPL', 'MSFT')
                    """
                )
                cursor.execute(
                    """
                    UPDATE observations
                    SET ipda_20w_low = 0, ipda_20w_high = 200
                    WHERE symbol = 'AAPL'
                      AND id = (SELECT MAX(id) FROM observations WHERE symbol = 'AAPL')
                    """
                )
            connection.commit()
        finally:
            connection.close()

        first_path = self.repository.saved_group_migration_path(saved["id"])
        aapl_states = next(item["states"] for item in first_path["paths"] if item["symbol"] == "AAPL")
        current_after_frame_change = self.repository.saved_group_report(saved["id"])
        self.assertEqual(current_after_frame_change["current_state"]["location"]["shallow_premium"], 2)
        self.assertEqual(
            [state["occurred_at"] for state in aapl_states],
            sorted(state["occurred_at"] for state in aapl_states),
        )
        self.assertEqual([state["location_code"] for state in aapl_states], ["DD", "DD"])
        msft_states = next(item["states"] for item in first_path["paths"] if item["symbol"] == "MSFT")

        self.ingest_series("MSFT", ("130.3",), start_minutes=160)
        replayed_path = self.repository.saved_group_migration_path(saved["id"])
        replayed_states = next(
            item["states"] for item in replayed_path["paths"] if item["symbol"] == "MSFT"
        )
        self.assertEqual(len(replayed_states), 3)
        self.assertEqual(len({state["event_key"] for state in replayed_states}), 3)
        self.assertEqual(
            [(state["event_type"], state["occurred_at"], state["location"]) for state in replayed_states],
            [(state["event_type"], state["occurred_at"], state["location"]) for state in msft_states],
        )

    def test_edit_delete_and_future_migrations_only_change_the_saved_view(self) -> None:
        self.seed_mag7_history()
        saved = self.repository.create_saved_group("MAG7", MAG7)
        original_counts = self.domain_counts()
        initial_path = self.repository.saved_group_migration_path(saved["id"])
        goog_initial = next(item["states"] for item in initial_path["paths"] if item["symbol"] == "GOOG")
        self.assertEqual(len(goog_initial), 1)

        self.ingest_series(
            "GOOG",
            ("160", "160.2", "160.4", "160.6"),
            route="STR",
            start_minutes=180,
        )
        extended_path = self.repository.saved_group_migration_path(saved["id"])
        goog_extended = next(item["states"] for item in extended_path["paths"] if item["symbol"] == "GOOG")
        self.assertEqual(len(goog_extended), 2)
        self.assertEqual(goog_extended[-1]["direction"], "higher")

        counts_after_market_event = self.domain_counts()
        updated = self.repository.update_saved_group(saved["id"], "MAG 7", MAG7[:-1])
        self.assertEqual(updated["members"], MAG7[:-1])
        edited_report = self.repository.saved_group_report(saved["id"])
        self.assertEqual(edited_report["current_state"]["active_mrz"]["total"], 6)
        self.assertEqual(self.domain_counts(), counts_after_market_event)

        deleted = self.repository.delete_saved_group(saved["id"])
        self.assertEqual(deleted["name"], "MAG 7")
        self.assertEqual(self.repository.saved_groups(), [])
        self.assertEqual(self.domain_counts(), counts_after_market_event)
        self.assertGreater(counts_after_market_event[0], original_counts[0])


if __name__ == "__main__":
    unittest.main()
