from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.db import connect
from app.repository import EdgeRepository
from app.validation import ObservationPayload
from tests.db_support import clean, migrate_and_clean, require_test_database


BASE_TIME = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def schema_payload(index: int, price: str, *, observed_offset: int | None = None, route: str = "BTD"):
    return ObservationPayload.model_validate(
        {
            "schema_version": "4.3",
            "event_id": f"db-event-{index}",
            "symbol": "SPXUSDT",
            "route": route,
            "observation_type": "reclaim" if route == "BTD" else "rejection",
            "observation_price": price,
            "ipda_20w_high": "200",
            "ipda_20w_low": "100",
            "observed_at": BASE_TIME + timedelta(seconds=observed_offset if observed_offset is not None else index),
        }
    )


class RepositoryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database(cls)
        migrate_and_clean(cls.database_url)

    def setUp(self) -> None:
        clean(self.database_url)
        self.repository = EdgeRepository(self.database_url)

    def ingest(self, index: int, price: str, **kwargs):
        payload = schema_payload(index, price, **kwargs)
        return self.repository.ingest(payload, Decimal("0.01"))

    def test_duplicate_event_is_idempotently_ignored(self) -> None:
        payload = schema_payload(1, "110")
        first = self.repository.ingest(payload, Decimal("0.01"))
        duplicate = self.repository.ingest(payload, Decimal("0.01"))
        health = self.repository.health()
        self.assertTrue(first.accepted)
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(health["accepted_payload_count"], 1)
        self.assertEqual(health["duplicate_payload_count"], 1)

    def test_activation_persists_across_repository_restart(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1):
            self.ingest(index, price)
        before = self.repository.symbol_detail("SPXUSDT")
        restarted = EdgeRepository(self.database_url)
        after = restarted.symbol_detail("SPXUSDT")
        self.assertEqual(before, after)
        self.assertEqual(after["activation_event_id"], "db-event-4")
        self.assertEqual(after["supporting_observation_count"], 4)

    def test_late_event_replays_in_canonical_timestamp_order(self) -> None:
        self.ingest(1, "110", observed_offset=1)
        self.ingest(2, "110.2", observed_offset=2)
        self.ingest(4, "110.6", observed_offset=4)
        self.ingest(3, "110.4", observed_offset=3)
        detail = self.repository.symbol_detail("SPXUSDT")
        self.assertEqual(detail["activation_event_id"], "db-event-4")
        self.assertEqual(detail["core_mrz_lower"], 110.0)
        self.assertEqual(detail["core_mrz_upper"], 110.6)

    def test_migration_and_old_state_audit_are_committed_together(self) -> None:
        prices = (
            "110", "110.2", "110.4", "110.6",
            "110.3", "110.5",
            "120", "120.2", "120.4", "120.6",
        )
        for index, price in enumerate(prices, 1):
            self.ingest(index, price)
        detail = self.repository.symbol_detail("SPXUSDT")
        events = self.repository.audit_events("SPXUSDT")
        self.assertEqual(detail["core_mrz_lower"], 120.0)
        self.assertEqual([event["event_type"] for event in events], ["MRZ_ACTIVATED", "MRZ_MIGRATED"])
        self.assertEqual(Decimal(events[-1]["old_core_mrz_lower"]), Decimal("110"))
        self.assertEqual(Decimal(events[-1]["new_core_mrz_lower"]), Decimal("120"))
        self.assertEqual(events[-1]["old_supporting_observation_count"], 6)
        self.assertEqual(events[-1]["new_supporting_observation_count"], 4)
        self.assertEqual(detail["supporting_observation_count"], 4)

    def test_active_core_support_persists_without_resizing_bounds(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1):
            self.ingest(index, price)
        activated = self.repository.symbol_detail("SPXUSDT")

        self.ingest(5, "110.3")
        self.ingest(6, "110.5")
        supported = EdgeRepository(self.database_url).symbol_detail("SPXUSDT")

        self.assertEqual(supported["supporting_observation_count"], 6)
        self.assertEqual(supported["confirming_observation_count"], 4)
        self.assertEqual(supported["core_mrz_lower"], activated["core_mrz_lower"])
        self.assertEqual(supported["core_mrz_upper"], activated["core_mrz_upper"])

    def test_duplicate_packet_cannot_increment_evidence(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1):
            self.ingest(index, price)
        original = self.repository.symbol_detail("SPXUSDT")
        payload = schema_payload(4, "110.6")
        self.repository.ingest(payload, Decimal("0.01"))
        after = self.repository.symbol_detail("SPXUSDT")
        self.assertEqual(after["confirming_observation_count"], original["confirming_observation_count"])
        self.assertEqual(after["supporting_observation_count"], original["supporting_observation_count"])

    def test_one_active_row_per_symbol_enforces_singular_owner(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1):
            self.ingest(index, price)
        for index, price in enumerate(("180", "180.2", "180.4", "180.6"), 5):
            self.ingest(index, price, route="STR")
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*), MIN(route_owner), MAX(route_owner) FROM active_mrz WHERE symbol = %s", ("SPXUSDT",))
                count, minimum, maximum = cursor.fetchone()
        finally:
            connection.close()
        self.assertEqual(count, 1)
        self.assertEqual((minimum, maximum), ("BTD", "BTD"))
