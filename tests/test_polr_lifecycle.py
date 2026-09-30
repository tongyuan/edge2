from __future__ import annotations

import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from psycopg2.errors import RaiseException
from psycopg2.extras import RealDictCursor

from app.api import create_app
from app.config import Settings
from app.db import connect
from app.validation import POLRLifecyclePayload
from tests.db_support import clean, migrate_and_clean, require_test_database


def lifecycle_payload(**overrides):
    payload = {
        "schema_version": "1.0",
        "event_id": "ORCL-LONG-1790759700000-GRADE_A",
        "setup_id": "ORCL-LONG-1790759700000",
        "event_type": "GRADE_A",
        "symbol": "ORCL",
        "direction": "LONG",
        "mss_at": 1790759700000,
        "event_at": 1790763300000,
        "sweep_price": 131.58,
        "target_price": 140.88,
        "target_side": "BSL",
        "grade": "A",
        "rr_qualified_at": 1790761500000,
        "rr_source": "BISI",
        "rr_reference_price": 134.25,
        "setup_rr": 2.74,
        "event_price": 135.10,
        "chart_timeframe": "5",
        "range_timeframe": "60",
        "message": "POLR · GRADE A · ORCL · LONG · BSL 140.88",
    }
    payload.update(overrides)
    return payload


class POLRLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database(cls)
        migrate_and_clean(cls.database_url)
        settings = Settings(
            app_env="test",
            database_url=cls.database_url,
            webhook_secret="test-webhook-secret",
            require_webhook_secret=True,
            symbol_ticks={},
            max_request_bytes=32768,
            log_level="CRITICAL",
        )
        cls.client = TestClient(create_app(settings))
        cls.headers = {"X-EDGE2-Webhook-Secret": "test-webhook-secret"}

    def setUp(self) -> None:
        clean(self.database_url)

    def post(self, **overrides):
        return self.client.post(
            "/api/polr/lifecycle",
            json=lifecycle_payload(**overrides),
            headers=self.headers,
        )

    def fetchone(self, query: str, params: tuple = ()):
        connection = connect(self.database_url)
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                return cursor.fetchone()
        finally:
            connection.close()

    def test_mss_confirmed_creates_event_and_live_setup(self) -> None:
        response = self.post(
            event_id="ORCL-LONG-1790759700000-MSS_CONFIRMED",
            event_type="MSS_CONFIRMED",
            event_at=1790759700000,
            grade=None,
            rr_qualified_at=None,
            rr_source=None,
            rr_reference_price=None,
            setup_rr=None,
        )

        event = self.fetchone("SELECT * FROM polr_lifecycle_events")
        setup = self.fetchone("SELECT * FROM polr_setups")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(event["event_type"], "MSS_CONFIRMED")
        self.assertEqual(setup["status"], "LIVE")
        self.assertIsNone(setup["setup_rr"])

    def test_rr_qualified_populates_frozen_rr_fields(self) -> None:
        response = self.post(
            event_id="ORCL-LONG-1790759700000-RR_QUALIFIED",
            event_type="RR_QUALIFIED",
            grade=None,
        )

        setup = self.fetchone("SELECT * FROM polr_setups")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(setup["rr_source"], "BISI")
        self.assertEqual(str(setup["rr_reference_price"]), "134.25")
        self.assertEqual(str(setup["setup_rr"]), "2.74")
        self.assertIsNotNone(setup["rr_qualified_at"])

    def test_grade_progression_and_delayed_grade_do_not_downgrade(self) -> None:
        self.assertEqual(self.post(event_type="GRADE_A").status_code, 200)
        self.assertEqual(
            self.fetchone("SELECT highest_grade FROM polr_setups")["highest_grade"],
            "A",
        )
        self.assertEqual(
            self.post(
                event_id="ORCL-LONG-1790759700000-GRADE_A_PLUS",
                event_type="GRADE_A_PLUS",
                event_at=1790766900000,
                grade="A+",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.post(
                event_id="ORCL-LONG-1790759700000-GRADE_A-DELAYED",
                event_type="GRADE_A",
                event_at=1790760000000,
                grade="A",
            ).status_code,
            200,
        )

        setup = self.fetchone("SELECT * FROM polr_setups")
        self.assertEqual(setup["highest_grade"], "A+")
        self.assertEqual(int(setup["last_event_at"].timestamp() * 1000), 1790766900000)

    def test_setup_failed_sets_failed(self) -> None:
        self.assertEqual(
            self.post(event_type="SETUP_FAILED", grade=None).status_code,
            200,
        )
        self.assertEqual(
            self.fetchone("SELECT status FROM polr_setups")["status"],
            "FAILED",
        )

    def test_retired_setup_can_transition_to_target_taken(self) -> None:
        self.assertEqual(
            self.post(event_type="SETUP_RETIRED", grade=None).status_code,
            200,
        )
        self.assertEqual(
            self.fetchone("SELECT status FROM polr_setups")["status"],
            "RETIRED",
        )
        self.assertEqual(
            self.post(
                event_id="ORCL-LONG-1790759700000-TARGET_TAKEN",
                event_type="TARGET_TAKEN",
                event_at=1790766900000,
            ).status_code,
            200,
        )
        self.assertEqual(
            self.fetchone("SELECT status FROM polr_setups")["status"],
            "TARGET_TAKEN",
        )

    def test_target_taken_is_not_regressed_by_delayed_grade(self) -> None:
        self.post(event_type="TARGET_TAKEN", grade="A+")
        self.post(
            event_id="ORCL-LONG-1790759700000-GRADE_A-DELAYED",
            event_type="GRADE_A",
            event_at=1790759700000,
            grade="A",
        )

        setup = self.fetchone("SELECT * FROM polr_setups")
        self.assertEqual(setup["status"], "TARGET_TAKEN")
        self.assertEqual(setup["highest_grade"], "A+")
        self.assertEqual(int(setup["last_event_at"].timestamp() * 1000), 1790763300000)

    def test_target_taken_is_not_replaced_by_delayed_terminal_events(self) -> None:
        self.post(
            event_id="ORCL-LONG-1790759700000-TARGET_TAKEN",
            event_type="TARGET_TAKEN",
            event_at=1790766900000,
            grade="A+",
        )
        for event_type in ("SETUP_FAILED", "SETUP_RETIRED"):
            with self.subTest(event_type=event_type):
                self.post(
                    event_id=f"ORCL-LONG-1790759700000-{event_type}-DELAYED",
                    event_type=event_type,
                    event_at=1790760000000,
                    grade="A",
                )
                setup = self.fetchone("SELECT * FROM polr_setups")
                self.assertEqual(setup["status"], "TARGET_TAKEN")
                self.assertEqual(setup["highest_grade"], "A+")
                self.assertEqual(
                    int(setup["last_event_at"].timestamp() * 1000),
                    1790766900000,
                )

    def test_first_received_grade_creates_enriched_setup_without_fabricated_events(self) -> None:
        response = self.post()

        counts = self.fetchone(
            """
            SELECT
                (SELECT count(*) FROM polr_lifecycle_events) AS event_count,
                (SELECT count(*) FROM polr_setups) AS setup_count
            """
        )
        event = self.fetchone("SELECT event_type FROM polr_lifecycle_events")
        setup = self.fetchone("SELECT * FROM polr_setups")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(counts, {"event_count": 1, "setup_count": 1})
        self.assertEqual(event["event_type"], "GRADE_A")
        self.assertEqual(setup["status"], "LIVE")
        self.assertEqual(setup["highest_grade"], "A")
        self.assertEqual(setup["rr_source"], "BISI")
        self.assertEqual(str(setup["setup_rr"]), "2.74")

    def test_duplicate_event_id_is_successful_and_inserted_once(self) -> None:
        first = self.post()
        duplicate = self.post()

        counts = self.fetchone(
            """
            SELECT
                (SELECT count(*) FROM polr_lifecycle_events) AS event_count,
                (SELECT count(*) FROM polr_setups) AS setup_count
            """
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json(), first.json())
        self.assertEqual(counts, {"event_count": 1, "setup_count": 1})

    def test_concurrent_duplicate_event_id_is_race_safe(self) -> None:
        repository = self.client.app.state.repository
        payload = POLRLifecyclePayload.model_validate(lifecycle_payload())
        barrier = Barrier(2)

        def ingest():
            barrier.wait()
            return repository.ingest_polr_lifecycle(payload)

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _index: ingest(), range(2)))

        counts = self.fetchone(
            """
            SELECT
                (SELECT count(*) FROM polr_lifecycle_events) AS event_count,
                (SELECT count(*) FROM polr_setups) AS setup_count
            """
        )
        self.assertEqual(sorted(outcome.duplicate for outcome in outcomes), [False, True])
        self.assertEqual(counts, {"event_count": 1, "setup_count": 1})

    def test_received_event_truth_rejects_update_and_delete(self) -> None:
        self.post()
        for statement in (
            "UPDATE polr_lifecycle_events SET message = 'changed'",
            "DELETE FROM polr_lifecycle_events",
        ):
            with self.subTest(statement=statement):
                connection = connect(self.database_url)
                try:
                    with self.assertRaises(RaiseException):
                        with connection.cursor() as cursor:
                            cursor.execute(statement)
                finally:
                    connection.rollback()
                    connection.close()

    def test_different_same_bar_events_for_one_setup_are_both_persisted(self) -> None:
        same_bar = 1790759700000
        self.post(
            event_id="ORCL-LONG-1790759700000-MSS_CONFIRMED",
            event_type="MSS_CONFIRMED",
            event_at=same_bar,
            grade=None,
            rr_qualified_at=None,
            rr_source=None,
            rr_reference_price=None,
            setup_rr=None,
        )
        self.post(
            event_id="ORCL-LONG-1790759700000-RR_QUALIFIED",
            event_type="RR_QUALIFIED",
            event_at=same_bar,
            grade=None,
        )

        result = self.fetchone(
            """
            SELECT count(*) AS event_count,
                   count(DISTINCT event_id) AS distinct_event_count
            FROM polr_lifecycle_events
            """
        )
        self.assertEqual(result, {"event_count": 2, "distinct_event_count": 2})

    def test_later_rr_fields_fill_null_snapshot(self) -> None:
        self.post(
            event_id="ORCL-LONG-1790759700000-MSS_CONFIRMED",
            event_type="MSS_CONFIRMED",
            grade=None,
            rr_qualified_at=None,
            rr_source=None,
            rr_reference_price=None,
            setup_rr=None,
        )
        before = self.fetchone("SELECT * FROM polr_setups")
        self.post(
            event_id="ORCL-LONG-1790759700000-RR_QUALIFIED",
            event_type="RR_QUALIFIED",
            grade=None,
        )
        after = self.fetchone("SELECT * FROM polr_setups")

        self.assertIsNone(before["setup_rr"])
        self.assertEqual(after["rr_source"], "BISI")
        self.assertEqual(str(after["rr_reference_price"]), "134.25")
        self.assertEqual(str(after["setup_rr"]), "2.74")

        self.post(
            event_id="ORCL-LONG-1790759700000-MSS_CONFIRMED-DELAYED",
            event_type="MSS_CONFIRMED",
            event_at=1790759700000,
            grade=None,
            rr_qualified_at=None,
            rr_source=None,
            rr_reference_price=None,
            setup_rr=None,
        )
        after_null = self.fetchone("SELECT * FROM polr_setups")
        self.assertEqual(after_null["rr_source"], "BISI")
        self.assertEqual(str(after_null["rr_reference_price"]), "134.25")
        self.assertEqual(str(after_null["setup_rr"]), "2.74")

    def test_receipt_timestamps_and_event_chronology_are_monotonic(self) -> None:
        self.post(
            event_id="ORCL-LONG-1790759700000-GRADE_A_PLUS",
            event_type="GRADE_A_PLUS",
            event_at=1790766900000,
            grade="A+",
        )
        initial = self.fetchone("SELECT * FROM polr_setups")

        time.sleep(0.01)
        self.post(
            event_id="ORCL-LONG-1790759700000-GRADE_A-DELAYED",
            event_type="GRADE_A",
            event_at=1790760000000,
            grade="A",
        )
        delayed = self.fetchone("SELECT * FROM polr_setups")
        self.assertEqual(delayed["first_seen_at"], initial["first_seen_at"])
        self.assertGreater(delayed["last_received_at"], initial["last_received_at"])
        self.assertEqual(delayed["last_event_at"], initial["last_event_at"])

        time.sleep(0.01)
        self.post(
            event_id="ORCL-LONG-1790759700000-GRADE_A-DELAYED",
            event_type="GRADE_A",
            event_at=1790760000000,
            grade="A",
        )
        duplicate = self.fetchone("SELECT * FROM polr_setups")
        self.assertEqual(duplicate["first_seen_at"], initial["first_seen_at"])
        self.assertGreater(duplicate["last_received_at"], delayed["last_received_at"])
        self.assertEqual(duplicate["last_event_at"], initial["last_event_at"])

    def test_conflicting_frozen_rr_is_persisted_as_event_but_not_overwritten(self) -> None:
        self.post(
            event_id="ORCL-LONG-1790759700000-RR_QUALIFIED",
            event_type="RR_QUALIFIED",
            grade=None,
        )
        response = self.post(
            event_id="ORCL-LONG-1790759700000-GRADE_A-CONFLICT",
            event_type="GRADE_A",
            rr_qualified_at=1790762400000,
            rr_source="VI",
            rr_reference_price=133.0,
            setup_rr=9.99,
        )

        setup = self.fetchone("SELECT * FROM polr_setups")
        event = self.fetchone(
            "SELECT * FROM polr_lifecycle_events WHERE event_id = %s",
            ("ORCL-LONG-1790759700000-GRADE_A-CONFLICT",),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(setup["rr_source"], "BISI")
        self.assertEqual(str(setup["rr_reference_price"]), "134.25")
        self.assertEqual(str(setup["setup_rr"]), "2.74")
        self.assertEqual(event["rr_source"], "VI")
        self.assertEqual(str(event["rr_reference_price"]), "133.0")
        self.assertEqual(str(event["setup_rr"]), "9.99")

    def test_persistence_schema_uses_only_setup_rr_and_database_uniqueness(self) -> None:
        result = self.fetchone(
            """
            SELECT
                EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'polr_lifecycle_events'
                      AND column_name = 'setup_rr'
                ) AS event_setup_rr,
                EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'polr_setups'
                      AND column_name = 'setup_rr'
                ) AS snapshot_setup_rr,
                EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name IN ('polr_lifecycle_events', 'polr_setups')
                      AND column_name = 'rr_to_target'
                ) AS legacy_rr,
                EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE tablename = 'polr_lifecycle_events'
                      AND indexdef LIKE 'CREATE UNIQUE INDEX%event_id%'
                ) AS event_id_unique,
                EXISTS (
                    SELECT 1 FROM pg_indexes
                    WHERE tablename = 'polr_setups'
                      AND indexdef LIKE 'CREATE UNIQUE INDEX%setup_id%'
                ) AS setup_id_unique
            """
        )
        self.assertEqual(
            result,
            {
                "event_setup_rr": True,
                "snapshot_setup_rr": True,
                "legacy_rr": False,
                "event_id_unique": True,
                "setup_id_unique": True,
            },
        )

    def test_valid_payload_returns_matching_event_id(self) -> None:
        response = self.client.post(
            "/api/polr/lifecycle",
            json=lifecycle_payload(),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "ok": True,
                "event_id": "ORCL-LONG-1790759700000-GRADE_A",
            },
        )

    def test_unsupported_event_type_is_rejected(self) -> None:
        response = self.client.post(
            "/api/polr/lifecycle",
            json=lifecycle_payload(event_type="UNKNOWN"),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 422)

    def test_rr_qualified_payload_is_accepted(self) -> None:
        response = self.client.post(
            "/api/polr/lifecycle",
            json=lifecycle_payload(
                event_id="ORCL-LONG-1790759700000-RR_QUALIFIED",
                event_type="RR_QUALIFIED",
                grade=None,
                message="POLR · RR QUALIFIED · ORCL · LONG · BISI 134.25 · 2.7R · BSL 140.88",
            ),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["event_id"], "ORCL-LONG-1790759700000-RR_QUALIFIED")

    def test_obsolete_rr_event_names_are_rejected(self) -> None:
        for event_type in ("ENTRY_READY", "SETUP_RR_READY"):
            with self.subTest(event_type=event_type):
                response = self.client.post(
                    "/api/polr/lifecycle",
                    json=lifecycle_payload(event_type=event_type),
                    headers=self.headers,
                )

                self.assertEqual(response.status_code, 422)

    def test_invalid_rr_source_is_rejected(self) -> None:
        response = self.client.post(
            "/api/polr/lifecycle",
            json=lifecycle_payload(rr_source="BREAKER"),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 422)

    def test_null_rr_qualification_fields_are_accepted_before_qualification(self) -> None:
        response = self.client.post(
            "/api/polr/lifecycle",
            json=lifecycle_payload(
                event_id="ORCL-LONG-1790759700000-MSS_CONFIRMED",
                event_type="MSS_CONFIRMED",
                grade=None,
                rr_qualified_at=None,
                rr_source=None,
                rr_reference_price=None,
                setup_rr=None,
            ),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)

    def test_null_setup_rr_is_accepted(self) -> None:
        response = self.client.post(
            "/api/polr/lifecycle",
            json=lifecycle_payload(setup_rr=None),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)

    def test_finite_setup_rr_is_accepted(self) -> None:
        response = self.client.post(
            "/api/polr/lifecycle",
            json=lifecycle_payload(setup_rr=3.2),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)

    def test_non_finite_or_invalid_setup_rr_is_rejected(self) -> None:
        for value in ("NaN", "Infinity", "not-a-number"):
            with self.subTest(value=value):
                response = self.client.post(
                    "/api/polr/lifecycle",
                    json=lifecycle_payload(setup_rr=value),
                    headers=self.headers,
                )

                self.assertEqual(response.status_code, 422)

    def test_rr_to_target_is_rejected(self) -> None:
        response = self.client.post(
            "/api/polr/lifecycle",
            json=lifecycle_payload(rr_to_target=2.74),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 422)

    def test_rr_reference_setup_rr_and_event_price_must_be_finite(self) -> None:
        for field in ("rr_reference_price", "setup_rr", "event_price"):
            for value in ("NaN", "Infinity", "not-a-number"):
                with self.subTest(field=field, value=value):
                    response = self.client.post(
                        "/api/polr/lifecycle",
                        json=lifecycle_payload(**{field: value}),
                        headers=self.headers,
                    )

                    self.assertEqual(response.status_code, 422)

    def test_event_price_is_required(self) -> None:
        payload = lifecycle_payload()
        payload.pop("event_price")

        response = self.client.post(
            "/api/polr/lifecycle",
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 422)

    def test_lifecycle_outcomes_accept_frozen_rr_qualification_fields(self) -> None:
        cases = {
            "MSS_CONFIRMED": ("LIVE", None),
            "RR_QUALIFIED": ("LIVE", None),
            "GRADE_A": ("LIVE", "A"),
            "GRADE_A_PLUS": ("LIVE", "A+"),
            "SETUP_FAILED": ("FAILED", "A"),
            "SETUP_RETIRED": ("RETIRED", "A"),
            "TARGET_TAKEN": ("TARGET_TAKEN", "A"),
        }
        for event_type, (expected_status, grade) in cases.items():
            with self.subTest(event_type=event_type):
                clean(self.database_url)
                response = self.post(
                    event_id=f"ORCL-LONG-1790759700000-{event_type}",
                    event_type=event_type,
                    grade=grade,
                )
                persisted = self.fetchone(
                    """
                    SELECT
                        (SELECT count(*) FROM polr_lifecycle_events) AS event_count,
                        (SELECT count(*) FROM polr_setups) AS setup_count,
                        (SELECT status FROM polr_setups) AS status
                    """
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    persisted,
                    {
                        "event_count": 1,
                        "setup_count": 1,
                        "status": expected_status,
                    },
                )

    def test_operator_entry_fields_are_rejected(self) -> None:
        for field in ("entry_ready_at", "entry_source", "entry_price", "entry_rr"):
            with self.subTest(field=field):
                response = self.client.post(
                    "/api/polr/lifecycle",
                    json=lifecycle_payload(**{field: 1}),
                    headers=self.headers,
                )

                self.assertEqual(response.status_code, 422)

    def test_invalid_direction_is_rejected(self) -> None:
        response = self.client.post(
            "/api/polr/lifecycle",
            json=lifecycle_payload(direction="FLAT"),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 422)

    def test_missing_required_field_is_rejected(self) -> None:
        payload = lifecycle_payload()
        payload.pop("setup_id")

        response = self.client.post(
            "/api/polr/lifecycle",
            json=payload,
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
