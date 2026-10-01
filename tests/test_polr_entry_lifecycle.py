from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from psycopg2.extras import RealDictCursor
from pydantic import ValidationError

from app.api import create_app
from app.config import Settings
from app.db import connect
from app.validation import POLRLifecyclePayload
from tests.db_support import clean, migrate_and_clean, require_test_database
from tests.test_polr_lifecycle import lifecycle_payload


def entry_payload(event_type: str = "ENTRY_TOUCHED", **overrides):
    setup_id = "ZECUSDT-LONG-1790762700000"
    attempt = overrides.pop("entry_attempt", 1)
    payload = lifecycle_payload(
        schema_version="1.1",
        event_id=f"{setup_id}-E{attempt}-{event_type}",
        setup_id=setup_id,
        event_type=event_type,
        symbol="ZECUSDT",
        direction="LONG",
        mss_at=1790762700000,
        event_at=1790770500000,
        sweep_price=1397.89,
        target_price=1494.52,
        target_side="BSL",
        grade="A+",
        rr_qualified_at=1790763600000,
        rr_source="SB",
        rr_reference_price=1416.20,
        setup_rr=4.3,
        event_price=1414.31,
        entry_id=f"{setup_id}-E{attempt}",
        entry_attempt=attempt,
        entry_source="SB",
        confirmation_method="CE_RECLAIM",
        entry_zone_top=1416.20,
        entry_zone_bottom=1409.42,
        ote_top=1416.78,
        ote_bottom=1408.33,
        ote_confirmed_at=1790770200000,
        range_low=1409.42,
        range_high=1494.52,
        range_third="BOTTOM",
        ote_required=True,
        minimum_grade="A+",
        grade_at_touch="A+",
        entry_touched_at=1790770500000,
    )
    if event_type in {"ENTRY_CONFIRMED", "ENTRY_STOPPED", "ENTRY_AMBIGUOUS"}:
        payload.update(
            event_at=1790770800000,
            entry_confirmed_at=1790770800000,
            grade_at_confirmation="A+",
            entry_price=1414.31,
            stop_price=1397.89,
            entry_rr=4.79,
        )
    payload.update(overrides)
    return payload


class POLREntryPayloadValidationTests(unittest.TestCase):
    def test_grade_policy_is_an_option_and_defaults_can_be_recorded(self) -> None:
        for minimum_grade in ("Off", "A", "A+"):
            with self.subTest(minimum_grade=minimum_grade):
                parsed = POLRLifecyclePayload.model_validate(
                    entry_payload(minimum_grade=minimum_grade)
                )
                self.assertEqual(parsed.minimum_grade, minimum_grade)

    def test_entry_requires_schema_1_1_and_strict_fields(self) -> None:
        with self.assertRaises(ValidationError):
            POLRLifecyclePayload.model_validate(entry_payload(schema_version="1.0"))
        with self.assertRaises(ValidationError):
            POLRLifecyclePayload.model_validate(entry_payload(unexpected=True))

    def test_confirmed_entry_requires_actual_entry_risk_fields(self) -> None:
        payload = entry_payload("ENTRY_CONFIRMED")
        payload.pop("entry_price")
        with self.assertRaises(ValidationError):
            POLRLifecyclePayload.model_validate(payload)

    def test_long_confirmation_must_be_in_bottom_third(self) -> None:
        with self.assertRaises(ValidationError):
            POLRLifecyclePayload.model_validate(
                entry_payload("ENTRY_CONFIRMED", entry_price=1450.00)
            )

    def test_short_confirmation_uses_top_third(self) -> None:
        parsed = POLRLifecyclePayload.model_validate(
            entry_payload(
                "ENTRY_CONFIRMED",
                event_id="ZECUSDT-SHORT-1790762700000-E1-ENTRY_CONFIRMED",
                setup_id="ZECUSDT-SHORT-1790762700000",
                entry_id="ZECUSDT-SHORT-1790762700000-E1",
                direction="SHORT",
                sweep_price=1502.0,
                target_price=1409.42,
                target_side="SSL",
                range_third="TOP",
                entry_zone_top=1494.52,
                entry_zone_bottom=1480.0,
                ote_top=1494.52,
                ote_bottom=1480.0,
                entry_price=1490.0,
                stop_price=1502.0,
                entry_rr=4.0,
            )
        )
        self.assertEqual(parsed.range_third, "TOP")


class POLREntryPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database(cls)
        migrate_and_clean(cls.database_url)
        cls.client = TestClient(
            create_app(
                Settings(
                    app_env="test",
                    database_url=cls.database_url,
                    webhook_secret="test-webhook-secret",
                    require_webhook_secret=True,
                    symbol_ticks={},
                    max_request_bytes=32768,
                    log_level="CRITICAL",
                )
            )
        )
        cls.headers = {"X-EDGE2-Webhook-Secret": "test-webhook-secret"}

    def setUp(self) -> None:
        clean(self.database_url)

    def post(self, event_type: str = "ENTRY_TOUCHED", **overrides):
        return self.client.post(
            "/api/polr/lifecycle",
            json=entry_payload(event_type, **overrides),
            headers=self.headers,
        )

    def fetchone(self, query: str, params: tuple = ()):
        connection = connect(self.database_url)
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()
        finally:
            connection.close()

    def test_touch_then_confirmation_is_independent_of_parent_setup(self) -> None:
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(self.post("ENTRY_CONFIRMED").status_code, 200)

        setup = self.fetchone("SELECT * FROM polr_setups")
        attempt = self.fetchone("SELECT * FROM polr_entry_attempts")
        self.assertEqual(setup["status"], "LIVE")
        self.assertEqual(str(setup["setup_rr"]), "4.3")
        self.assertEqual(attempt["status"], "CONFIRMED")
        self.assertEqual(str(attempt["entry_rr"]), "4.79")
        self.assertEqual(attempt["minimum_grade"], "A+")

    def test_same_bar_touch_then_confirmation_remain_distinct_events(self) -> None:
        same_bar = 1790770500000
        self.post(event_at=same_bar)
        self.post("ENTRY_CONFIRMED", event_at=same_bar, entry_confirmed_at=same_bar)
        result = self.fetchone(
            "SELECT count(*) AS count FROM polr_lifecycle_events WHERE entry_id IS NOT NULL"
        )
        self.assertEqual(result["count"], 2)

    def test_delayed_touch_and_invalidation_do_not_regress_confirmation(self) -> None:
        self.post("ENTRY_CONFIRMED")
        self.post(
            event_id="ZECUSDT-LONG-1790762700000-E1-ENTRY_TOUCHED-DELAYED",
            event_at=1790770500000,
        )
        self.post(
            "ENTRY_INVALIDATED",
            event_id="ZECUSDT-LONG-1790762700000-E1-ENTRY_INVALIDATED-DELAYED",
            event_at=1790770600000,
        )
        attempt = self.fetchone("SELECT * FROM polr_entry_attempts")
        self.assertEqual(attempt["status"], "CONFIRMED")

    def test_stopped_entry_does_not_fail_setup(self) -> None:
        self.post("ENTRY_CONFIRMED")
        self.post("ENTRY_STOPPED", event_at=1790771100000)
        setup = self.fetchone("SELECT * FROM polr_setups")
        attempt = self.fetchone("SELECT * FROM polr_entry_attempts")
        self.assertEqual(setup["status"], "LIVE")
        self.assertEqual(attempt["status"], "STOPPED")

    def test_invalid_e1_can_be_followed_by_confirmed_e2(self) -> None:
        self.post("ENTRY_INVALIDATED")
        self.post(
            "ENTRY_CONFIRMED",
            entry_attempt=2,
            event_at=1790772000000,
            entry_touched_at=1790771700000,
            entry_confirmed_at=1790772000000,
        )
        result = self.fetchone(
            """
            SELECT array_agg(status ORDER BY attempt_no) AS statuses
            FROM polr_entry_attempts
            """
        )
        self.assertEqual(result["statuses"], ["INVALIDATED", "CONFIRMED"])

    def test_target_taken_derives_confirmed_entry_outcome(self) -> None:
        self.post("ENTRY_CONFIRMED")
        response = self.client.post(
            "/api/polr/lifecycle",
            json=lifecycle_payload(
                schema_version="1.1",
                event_id="ZECUSDT-LONG-1790762700000-TARGET_TAKEN",
                setup_id="ZECUSDT-LONG-1790762700000",
                event_type="TARGET_TAKEN",
                symbol="ZECUSDT",
                direction="LONG",
                mss_at=1790762700000,
                event_at=1790775000000,
                sweep_price=1397.89,
                target_price=1494.52,
                target_side="BSL",
                grade="A+",
            ),
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        attempt = self.fetchone("SELECT * FROM polr_entry_attempts")
        self.assertEqual(attempt["status"], "TARGET_TAKEN")

    def test_duplicate_and_concurrent_confirmation_are_idempotent(self) -> None:
        repository = self.client.app.state.repository
        payload = POLRLifecyclePayload.model_validate(entry_payload("ENTRY_CONFIRMED"))
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
                (SELECT count(*) FROM polr_entry_attempts) AS attempt_count
            """
        )
        self.assertEqual(sorted(item.duplicate for item in outcomes), [False, True])
        self.assertEqual(counts, {"event_count": 1, "attempt_count": 1})


if __name__ == "__main__":
    unittest.main()
