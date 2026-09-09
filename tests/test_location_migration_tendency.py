from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.db import connect
from app.repository import EdgeRepository, location_migration_tendency_payload
from app.validation import ObservationPayload
from tests.db_support import clean, migrate_and_clean, require_test_database


BASE_TIME = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def payload(
    index: int,
    price: str,
    *,
    symbol: str,
    route: str,
) -> ObservationPayload:
    return ObservationPayload.model_validate(
        {
            "schema_version": "4.3",
            "event_id": f"{symbol.lower()}-migration-{index}",
            "symbol": symbol,
            "route": route,
            "observation_type": "reclaim" if route == "BTD" else "rejection",
            "observation_price": price,
            "ipda_20w_high": "200",
            "ipda_20w_low": "100",
            "observed_at": BASE_TIME + timedelta(seconds=index),
        }
    )


def migration_row(
    index: int,
    direction: str,
    *,
    symbol: str | None = None,
) -> dict[str, object]:
    source_midpoint = Decimal("180.5")
    destination_midpoint = (
        source_midpoint + Decimal("10")
        if direction == "HIGHER"
        else source_midpoint - Decimal("10")
    )
    return {
        "event_key": f"migration-event-{index}",
        "trigger_event_id": f"observation-{index}",
        "symbol": symbol or f"SYMBOL-{index}",
        "occurred_at": BASE_TIME + timedelta(hours=index),
        "sequence": index,
        "source_route_owner": "STR",
        "destination_route_owner": "STR",
        "old_core_mrz_lower": Decimal("180"),
        "old_core_mrz_upper": Decimal("181"),
        "new_core_mrz_lower": destination_midpoint - Decimal("0.5"),
        "new_core_mrz_upper": destination_midpoint + Decimal("0.5"),
        "new_core_mrz_midpoint": destination_midpoint,
        "starting_structural_location": "deep_premium_core_mrz",
        "destination_structural_location": "shallow_premium_core_mrz",
        "source_event_key": f"source-event-{index}",
        "source_activated_at": BASE_TIME + timedelta(hours=index - 1),
        "source_activation_source": "PRODUCTION_QUALIFIED",
        "destination_activation_source": "PRODUCTION_QUALIFIED",
        "confirming_observation_count": 4,
        "direction": direction,
    }


class LocationMigrationTendencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database(cls)
        migrate_and_clean(cls.database_url)

    def setUp(self) -> None:
        clean(self.database_url)
        self.repository = EdgeRepository(self.database_url)

    def ingest_cluster(
        self,
        symbol: str,
        start_index: int,
        prices: tuple[str, ...],
        *,
        route: str,
    ) -> None:
        for offset, price in enumerate(prices):
            self.repository.ingest(
                payload(start_index + offset, price, symbol=symbol, route=route),
                Decimal("0.01"),
            )

    def test_completed_transitions_aggregate_by_old_authority_location(self) -> None:
        self.ingest_cluster("SPX", 1, ("110", "110.2", "110.4", "110.6"), route="BTD")
        self.ingest_cluster("SPX", 5, ("130", "130.2", "130.4", "130.6"), route="BTD")
        self.ingest_cluster("SPX", 9, ("110", "110.2", "110.4", "110.6"), route="BTD")

        self.ingest_cluster("NDX", 101, ("180", "180.2", "180.4", "180.6"), route="STR")
        self.ingest_cluster("NDX", 105, ("160", "160.2", "160.4", "160.6"), route="STR")
        self.ingest_cluster("NDX", 109, ("190", "190.2", "190.4", "190.6"), route="STR")

        self.ingest_cluster("RUT", 201, ("110", "110.2", "110.4", "110.6"), route="BTD")
        self.ingest_cluster("RUT", 205, ("130", "130.2", "130.4", "130.6"), route="BTD")

        self.ingest_cluster("IDLE", 301, ("140", "140.2", "140.4", "140.6"), route="BTD")

        tendency = self.repository.location_migration_tendency()

        self.assertEqual(
            {
                key: tendency["deep_discount"][key]
                for key in (
                    "migration_samples",
                    "higher_count",
                    "lower_count",
                    "higher_pct",
                    "lower_pct",
                )
            },
            {
                "migration_samples": 2,
                "higher_count": 2,
                "lower_count": 0,
                "higher_pct": 100.0,
                "lower_pct": 0.0,
            },
        )
        self.assertEqual(len(tendency["deep_discount"]["higher_records"]), 2)
        self.assertEqual(tendency["deep_discount"]["lower_records"], [])
        self.assertTrue(
            all(
                record["direction"] == "HIGHER"
                for record in tendency["deep_discount"]["higher_records"]
            )
        )
        self.assertEqual(tendency["shallow_discount"]["migration_samples"], 1)
        self.assertEqual(tendency["shallow_discount"]["higher_count"], 0)
        self.assertEqual(tendency["shallow_discount"]["lower_count"], 1)
        self.assertEqual(tendency["deep_premium"]["migration_samples"], 1)
        self.assertEqual(tendency["deep_premium"]["lower_count"], 1)
        self.assertEqual(tendency["shallow_premium"]["migration_samples"], 1)
        self.assertEqual(tendency["shallow_premium"]["higher_count"], 1)

        for bucket in tendency.values():
            self.assertEqual(
                bucket["migration_samples"],
                bucket["higher_count"] + bucket["lower_count"],
            )
            if bucket["migration_samples"]:
                self.assertAlmostEqual(
                    bucket["higher_pct"] + bucket["lower_pct"],
                    100.0,
                )

        self.assertEqual(
            [event["event_type"] for event in self.repository.audit_events("SPX")],
            ["MRZ_ACTIVATED", "MRZ_MIGRATED", "MRZ_MIGRATED"],
        )
        self.assertEqual(
            [event["event_type"] for event in self.repository.audit_events("IDLE")],
            ["MRZ_ACTIVATED"],
        )

    def test_route_change_replay_and_created_at_do_not_duplicate_or_rebucket_history(self) -> None:
        self.ingest_cluster("CROSS", 1, ("110", "110.2", "110.4", "110.6"), route="BTD")
        self.ingest_cluster("CROSS", 5, ("180", "180.2", "180.4", "180.6"), route="STR")

        events = self.repository.audit_events("CROSS")
        self.assertEqual(
            [event["event_type"] for event in events],
            ["MRZ_ACTIVATED", "MRZ_MIGRATED", "ROUTE_CHANGED"],
        )
        before = self.repository.location_migration_tendency()
        self.assertEqual(before["deep_discount"]["migration_samples"], 1)
        self.assertEqual(before["deep_discount"]["higher_count"], 1)
        self.assertEqual(before["deep_premium"]["migration_samples"], 0)

        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE mrz_events
                    SET created_at = CASE sequence
                        WHEN 1 THEN '2040-01-01T00:00:00Z'::timestamptz
                        WHEN 2 THEN '2030-01-01T00:00:00Z'::timestamptz
                        ELSE '2020-01-01T00:00:00Z'::timestamptz
                    END
                    WHERE symbol = 'CROSS'
                    """
                )
            connection.commit()
        finally:
            connection.close()

        self.assertEqual(self.repository.location_migration_tendency(), before)

        replay_payload = payload(9, "180.3", symbol="CROSS", route="STR")
        self.repository.ingest(replay_payload, Decimal("0.01"))
        self.assertEqual(self.repository.location_migration_tendency(), before)
        duplicate = self.repository.ingest(replay_payload, Decimal("0.01"))
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(self.repository.location_migration_tendency(), before)

    def test_empty_and_equal_midpoint_history_are_handled_explicitly(self) -> None:
        empty = location_migration_tendency_payload(())
        self.assertEqual(
            set(empty),
            {"deep_discount", "shallow_discount", "shallow_premium", "deep_premium"},
        )
        for bucket in empty.values():
            self.assertEqual(bucket["migration_samples"], 0)
            self.assertIsNone(bucket["higher_pct"])
            self.assertIsNone(bucket["lower_pct"])
            self.assertEqual(bucket["higher_records"], [])
            self.assertEqual(bucket["lower_records"], [])

        with self.assertRaisesRegex(ValueError, "equal old/new midpoints"):
            location_migration_tendency_payload(
                (
                    {
                        "starting_structural_location": "deep_discount_core_mrz",
                        "direction": "EQUAL",
                    },
                )
            )

    def test_deep_premium_aggregate_and_evidence_share_exactly_eight_events(self) -> None:
        rows = tuple(
            migration_row(
                index,
                "HIGHER" if index <= 4 else "LOWER",
                symbol="BTCUSDT" if index in {1, 8} else None,
            )
            for index in range(1, 9)
        )

        bucket = location_migration_tendency_payload(rows)["deep_premium"]

        self.assertEqual(bucket["migration_samples"], 8)
        self.assertEqual(bucket["higher_count"], 4)
        self.assertEqual(bucket["lower_count"], 4)
        self.assertEqual(bucket["higher_pct"], 50.0)
        self.assertEqual(bucket["lower_pct"], 50.0)
        self.assertEqual(len(bucket["higher_records"]), 4)
        self.assertEqual(len(bucket["lower_records"]), 4)
        self.assertTrue(
            all(record["direction"] == "HIGHER" for record in bucket["higher_records"])
        )
        self.assertTrue(
            all(record["direction"] == "LOWER" for record in bucket["lower_records"])
        )
        self.assertEqual(
            [record["migration_event_key"] for record in bucket["lower_records"]],
            [f"migration-event-{index}" for index in range(8, 4, -1)],
        )
        records = [*bucket["higher_records"], *bucket["lower_records"]]
        self.assertEqual(len({record["migration_event_key"] for record in records}), 8)
        self.assertEqual(sum(record["symbol"] == "BTCUSDT" for record in records), 2)
        self.assertTrue(
            all(
                record["source"]["structural_location"]
                == "deep_premium_core_mrz"
                and record["destination"]["structural_location"]
                == "shallow_premium_core_mrz"
                for record in records
            )
        )


if __name__ == "__main__":
    unittest.main()
