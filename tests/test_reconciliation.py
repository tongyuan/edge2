from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from psycopg2.extras import Json

from app.db import connect, transaction
from app.mrz_robustness import MRZRobustnessService
from app.reconciliation import (
    RESULT_NO_CHANGE,
    RESULT_RECONCILIATION_REQUIRED,
    DerivedStateReconciler,
    ReconciliationError,
    ReconciliationPlanChanged,
)
from app.repository import EdgeRepository
from app.validation import ObservationPayload
from tests.db_support import clean, migrate_and_clean, require_test_database


BASE_TIME = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)


def payload(
    index: int,
    price: str,
    *,
    symbol: str,
    route: str = "BTD",
    ipda_low: str = "100",
    ipda_high: str = "200",
) -> ObservationPayload:
    return ObservationPayload.model_validate(
        {
            "schema_version": "4.3",
            "event_id": f"{symbol}-event-{index}",
            "symbol": symbol,
            "route": route,
            "observation_type": "reclaim" if route == "BTD" else "rejection",
            "observation_price": price,
            "ipda_20w_high": ipda_high,
            "ipda_20w_low": ipda_low,
            "observed_at": BASE_TIME + timedelta(seconds=index),
        }
    )


class FailingRepository(EdgeRepository):
    def _replace_derived_state(self, cursor, replay) -> None:
        super()._replace_derived_state(cursor, replay)
        raise RuntimeError("injected reconciliation persistence failure")


class DerivedStateReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database(cls)
        migrate_and_clean(cls.database_url)

    def setUp(self) -> None:
        clean(self.database_url)
        self.repository = EdgeRepository(self.database_url)
        self.reconciler = DerivedStateReconciler(
            self.database_url,
            clock=lambda: BASE_TIME,
        )

    def ingest(self, row: ObservationPayload, tick: str = "0.01") -> None:
        self.repository.ingest(row, Decimal(tick))

    def insert_observation_only(
        self,
        row: ObservationPayload,
        tick: str = "0.01",
    ) -> None:
        with transaction(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO observations (
                        event_id, schema_version, symbol, route, observation_type,
                        observation_price, observation_price_tick,
                        ipda_20w_high, ipda_20w_low,
                        observed_at, received_at, raw_payload
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        row.event_id,
                        row.schema_version,
                        row.symbol,
                        row.route.value,
                        row.observation_type.value,
                        row.observation_price,
                        Decimal(tick),
                        row.ipda_20w_high,
                        row.ipda_20w_low,
                        row.observed_at,
                        row.observed_at,
                        Json(row.model_dump(mode="json")),
                    ),
                )

    def observation_snapshot(self, symbol: str) -> tuple[tuple[object, ...], ...]:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, event_id, schema_version, symbol, route, observation_type,
                           observation_price, observation_price_tick,
                           ipda_20w_high, ipda_20w_low,
                           observed_at, received_at, raw_payload::text
                    FROM observations
                    WHERE symbol = %s
                    ORDER BY observed_at, received_at, id
                    """,
                    (symbol,),
                )
                return tuple(cursor.fetchall())
        finally:
            connection.close()

    def seed_stale_successor(
        self,
        *,
        symbol: str,
        initial: tuple[str, ...],
        successor: tuple[str, ...],
        route: str,
    ) -> None:
        for index, price in enumerate(initial, 1):
            self.ingest(payload(index, price, symbol=symbol, route=route))
        for index, price in enumerate(successor, len(initial) + 1):
            self.insert_observation_only(
                payload(index, price, symbol=symbol, route=route)
            )

    def seed_xagusd(self) -> None:
        initial = (
            "68.9205",
            "69.46925",
            "69.508",
            "68.995",
            "68.909",
            "68.8155",
        )
        later = (
            "67.9315",
            "67.912",
            "68.9306",
            "69.114",
            "68.5345",
            "67.9235",
            "68.5325",
            "68.6455",
            "68.2545",
            "69.2185",
            "69.233",
        )
        for index, price in enumerate(initial, 1):
            self.ingest(
                payload(
                    index,
                    price,
                    symbol="XAGUSD",
                    ipda_low="54.776",
                    ipda_high="89.3797",
                ),
                tick="0.0001",
            )
        for index, price in enumerate(later, len(initial) + 1):
            self.insert_observation_only(
                payload(
                    index,
                    price,
                    symbol="XAGUSD",
                    ipda_low="54.776",
                    ipda_high="89.3797",
                ),
                tick="0.0001",
            )

    def test_dry_run_reports_no_change_when_persisted_state_matches_replay(self) -> None:
        for index, price in enumerate(
            ("110", "110.2", "110.4", "110.6", "120", "120.2", "120.4", "120.6"),
            1,
        ):
            self.ingest(payload(index, price, symbol="CURRENT"))

        report = self.reconciler.dry_run()

        self.assertEqual(report["result"], RESULT_NO_CHANGE)
        self.assertEqual(report["reconciliation_required_count"], 0)
        self.assertEqual(report["symbols"][0]["result"], RESULT_NO_CHANGE)

    def test_dry_run_detects_direction_neutral_lower_btd_and_higher_str(self) -> None:
        self.seed_stale_successor(
            symbol="LOWERBTD",
            initial=("130", "130.2", "130.4", "130.6"),
            successor=("110", "110.2", "110.4", "110.6"),
            route="BTD",
        )
        self.seed_stale_successor(
            symbol="HIGHERSTR",
            initial=("170", "170.2", "170.4", "170.6"),
            successor=("180", "180.2", "180.4", "180.6"),
            route="STR",
        )

        report = self.reconciler.dry_run()
        by_symbol = {row["symbol"]: row for row in report["symbols"]}

        self.assertEqual(report["reconciliation_required_count"], 2)
        self.assertEqual(
            by_symbol["LOWERBTD"]["replay_active_mrz"]["core_mrz_lower"],
            "110",
        )
        self.assertEqual(
            by_symbol["HIGHERSTR"]["replay_active_mrz"]["core_mrz_lower"],
            "180",
        )
        self.assertEqual(
            by_symbol["LOWERBTD"]["missing_historical_migrations"],
            1,
        )
        self.assertEqual(
            by_symbol["HIGHERSTR"]["missing_historical_migrations"],
            1,
        )

    def test_xagusd_apply_rebuilds_history_authority_and_operator_surfaces(self) -> None:
        self.seed_xagusd()
        observations_before = self.observation_snapshot("XAGUSD")

        dry_run = self.reconciler.dry_run(["XAGUSD"])
        proposed = dry_run["symbols"][0]

        self.assertEqual(proposed["result"], RESULT_RECONCILIATION_REQUIRED)
        self.assertEqual(
            proposed["persisted_active_mrz"]["core_mrz_lower"],
            "68.8155",
        )
        self.assertEqual(
            proposed["persisted_active_mrz"]["core_mrz_upper"],
            "68.995",
        )
        self.assertEqual(
            [item["core_mrz_lower"] for item in proposed["reconstructed_mrz_path"]],
            ["68.8155", "67.912", "68.995"],
        )
        self.assertEqual(
            [item["core_mrz_upper"] for item in proposed["reconstructed_mrz_path"]],
            ["68.995", "68.2545", "69.233"],
        )
        self.assertEqual(proposed["missing_historical_migrations"], 2)
        self.assertEqual(proposed["replay_migration_event_count"], 2)

        applied = self.reconciler.apply(
            ["XAGUSD"],
            expected_plan_digest=dry_run["plan_digest"],
        )

        self.assertEqual(applied["result"], "APPLIED")
        self.assertEqual(applied["applied_symbols"], ["XAGUSD"])
        self.assertEqual(self.observation_snapshot("XAGUSD"), observations_before)
        monitor = self.repository.symbol_detail("XAGUSD")
        self.assertEqual(monitor["route_owner"], "BTD")
        self.assertEqual(monitor["core_mrz_lower"], 68.995)
        self.assertEqual(monitor["core_mrz_upper"], 69.233)
        events = self.repository.audit_events("XAGUSD")
        self.assertEqual(
            [event["event_type"] for event in events],
            ["MRZ_ACTIVATED", "MRZ_MIGRATED", "MRZ_MIGRATED"],
        )
        self.assertEqual(
            [Decimal(event["new_core_mrz_lower"]) for event in events],
            [Decimal("68.8155"), Decimal("67.912"), Decimal("68.995")],
        )
        self.assertEqual(len({event["event_key"] for event in events}), 3)

        card = MRZRobustnessService(
            self.repository.mrz_robustness_inputs,
            clock=lambda: BASE_TIME + timedelta(days=30),
        ).generate_report()["active_mrzs"][0]
        self.assertEqual(card["route_owner"], "BTD")
        self.assertEqual(card["active_mrz"]["lower"], "68.995")
        self.assertEqual(card["active_mrz"]["upper"], "69.233")

        after = self.reconciler.dry_run(["XAGUSD"])
        self.assertEqual(after["result"], RESULT_NO_CHANGE)
        with self.assertRaises(ReconciliationPlanChanged):
            self.reconciler.apply(
                ["XAGUSD"],
                expected_plan_digest=dry_run["plan_digest"],
            )
        reapplied = self.reconciler.apply(
            ["XAGUSD"],
            expected_plan_digest=after["plan_digest"],
        )
        self.assertEqual(reapplied["result"], "NO CHANGES")
        self.assertEqual(reapplied["applied_symbol_count"], 0)

    def test_apply_is_atomic_when_derived_persistence_fails(self) -> None:
        self.seed_stale_successor(
            symbol="ATOMIC",
            initial=("130", "130.2", "130.4", "130.6"),
            successor=("110", "110.2", "110.4", "110.6"),
            route="BTD",
        )
        before_active = self.repository.symbol_detail("ATOMIC")
        before_events = self.repository.audit_events("ATOMIC")
        failing = DerivedStateReconciler(
            self.database_url,
            repository=FailingRepository(self.database_url),
        )

        with self.assertRaisesRegex(
            ReconciliationError,
            "Failed to persist derived state for ATOMIC: "
            "injected reconciliation persistence failure",
        ):
            failing.apply(["ATOMIC"])

        self.assertEqual(self.repository.symbol_detail("ATOMIC"), before_active)
        self.assertEqual(self.repository.audit_events("ATOMIC"), before_events)
