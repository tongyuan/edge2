from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.repository import EdgeRepository, location_distribution_history_payload
from app.validation import ObservationPayload
from tests.db_support import clean, migrate_and_clean, require_test_database


NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def history_row(symbol: str, then_price: str | None, now_price: str | None):
    return {
        "symbol": symbol,
        "comparison_observation_price": then_price,
        "comparison_ipda_20w_high": "200" if then_price is not None else None,
        "comparison_ipda_20w_low": "100" if then_price is not None else None,
        "current_observation_price": now_price,
        "current_ipda_20w_high": "200" if now_price is not None else None,
        "current_ipda_20w_low": "100" if now_price is not None else None,
    }


class LocationDistributionHistoryPayloadTests(unittest.TestCase):
    def test_flow_exposes_offsetting_moves_and_denominator_changes(self) -> None:
        payload = location_distribution_history_payload(
            (
                history_row("UP", "110", "140"),
                history_row("DOWN", "140", "110"),
                history_row("SAME", "190", "190"),
                history_row("ADDED", None, "160"),
                history_row("REMOVED", "160", "210"),
            ),
            window="24H",
            current_at=NOW,
            comparison_at=NOW - timedelta(hours=24),
        )

        self.assertEqual(payload["window_semantics"], "elapsed_calendar_time")
        self.assertEqual(
            payload["universe"],
            {
                "now_eligible": 4,
                "then_eligible": 4,
                "common_eligible": 3,
                "added_or_became_eligible": 1,
                "removed_or_became_ineligible": 1,
            },
        )
        self.assertEqual(
            payload["flow"],
            {
                "moved_higher": 1,
                "moved_lower": 1,
                "unchanged": 1,
                "net_higher": 0,
                "comparable_symbols": 3,
            },
        )
        self.assertEqual(
            {item["key"]: item["now_count"] for item in payload["locations"]},
            {
                "deep_discount": 1,
                "shallow_discount": 1,
                "at_eqm": 0,
                "shallow_premium": 1,
                "deep_premium": 1,
            },
        )
        self.assertTrue(all(item["change_count"] == 0 for item in payload["locations"]))
        self.assertEqual(
            [(item["from_key"], item["to_key"], item["count"]) for item in payload["dominant_transitions"]],
            [
                ("deep_discount", "shallow_discount", 1),
                ("shallow_discount", "deep_discount", 1),
            ],
        )
        self.assertEqual(
            [(item["symbol"], item["direction"], item["magnitude"]) for item in payload["symbol_movements"]],
            [("UP", "higher", 1), ("DOWN", "lower", 1), ("SAME", "unchanged", 0)],
        )

    def test_empty_history_is_denominator_safe(self) -> None:
        payload = location_distribution_history_payload(
            (),
            window="20D",
            current_at=NOW,
            comparison_at=NOW - timedelta(days=20),
        )
        self.assertEqual(payload["universe"]["now_eligible"], 0)
        self.assertEqual(payload["universe"]["then_eligible"], 0)
        self.assertTrue(
            all(item["then_pct"] == 0.0 and item["now_pct"] == 0.0 for item in payload["locations"])
        )

    def test_structural_read_uses_distinct_discount_premium_and_extreme_shares(self) -> None:
        payload = location_distribution_history_payload(
            (
                history_row("A", "110", "140"),
                history_row("B", "110", "160"),
                history_row("C", "190", "190"),
            ),
            window="5D",
            current_at=NOW,
            comparison_at=NOW - timedelta(days=5),
        )

        self.assertEqual(
            payload["structural_read"],
            {
                "discount_share": {"then_pct": 66.7, "now_pct": 33.3, "change_pp": -33.4},
                "premium_share": {"then_pct": 33.3, "now_pct": 66.7, "change_pp": 33.4},
                "extreme_share": {"then_pct": 100.0, "now_pct": 33.3, "change_pp": -66.7},
            },
        )


class LocationDistributionHistoryRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database(cls)
        migrate_and_clean(cls.database_url)

    def setUp(self) -> None:
        clean(self.database_url)
        self.repository = EdgeRepository(self.database_url)

    def ingest(self, symbol: str, price: str, observed_at: datetime, index: int) -> None:
        payload = ObservationPayload.model_validate(
            {
                "schema_version": "4.3",
                "event_id": f"location-history-{symbol}-{index}",
                "symbol": symbol,
                "route": "BTD",
                "observation_type": "reclaim",
                "observation_price": price,
                "ipda_20w_high": "200",
                "ipda_20w_low": "100",
                "observed_at": observed_at,
            }
        )
        self.repository.ingest(payload, Decimal("0.01"))

    def test_repository_reads_canonical_observation_endpoints(self) -> None:
        old = NOW - timedelta(hours=25)
        new = NOW - timedelta(hours=1)
        for symbol, then_price, now_price in (
            ("UP", "110", "140"),
            ("DOWN", "140", "110"),
            ("SAME", "190", "190"),
            ("REMOVED", "160", "210"),
        ):
            self.ingest(symbol, then_price, old, 1)
            self.ingest(symbol, now_price, new, 2)
        self.ingest("ADDED", "160", new, 1)

        payload = self.repository.location_distribution_history("24H", now=NOW)

        self.assertEqual(payload["universe"]["now_eligible"], 4)
        self.assertEqual(payload["universe"]["then_eligible"], 4)
        self.assertEqual(payload["flow"]["comparable_symbols"], 3)
        self.assertEqual(payload["flow"]["moved_higher"], 1)
        self.assertEqual(payload["flow"]["moved_lower"], 1)
        self.assertEqual(payload["flow"]["unchanged"], 1)
        self.assertEqual(len(payload["symbol_movements"]), 3)
        self.assertEqual(payload["migration_events"], [])

    def test_repository_applies_5d_and_20d_elapsed_cutoffs(self) -> None:
        self.ingest("RANGE", "110", NOW - timedelta(days=25), 1)
        self.ingest("RANGE", "140", NOW - timedelta(days=10), 2)
        self.ingest("RANGE", "160", NOW - timedelta(hours=1), 3)

        five_day = self.repository.location_distribution_history("5D", now=NOW)
        twenty_day = self.repository.location_distribution_history("20D", now=NOW)
        five_then = {item["key"]: item["then_count"] for item in five_day["locations"]}
        twenty_then = {item["key"]: item["then_count"] for item in twenty_day["locations"]}

        self.assertEqual(five_then["shallow_discount"], 1)
        self.assertEqual(twenty_then["deep_discount"], 1)
        self.assertEqual(five_day["flow"]["moved_higher"], 1)
        self.assertEqual(twenty_day["flow"]["moved_higher"], 1)

    def test_multiple_intermediate_transitions_count_once_by_window_endpoints(self) -> None:
        self.ingest("MULTI", "110", NOW - timedelta(hours=25), 1)
        self.ingest("MULTI", "190", NOW - timedelta(hours=12), 2)
        self.ingest("MULTI", "140", NOW - timedelta(hours=1), 3)

        payload = self.repository.location_distribution_history("24H", now=NOW)

        self.assertEqual(payload["flow"]["moved_higher"], 1)
        self.assertEqual(payload["flow"]["moved_lower"], 0)
        self.assertEqual(payload["flow"]["unchanged"], 0)
        self.assertEqual(
            payload["dominant_transitions"],
            [
                {
                    "from_key": "deep_discount",
                    "from_label": "Deep Discount",
                    "to_key": "shallow_discount",
                    "to_label": "Shallow Discount",
                    "count": 1,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
