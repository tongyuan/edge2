from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings


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
        "rr_to_target": 2.74,
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
        settings = Settings(
            app_env="test",
            database_url="postgresql://unused",
            webhook_secret="test-webhook-secret",
            require_webhook_secret=True,
            symbol_ticks={},
            max_request_bytes=32768,
            log_level="CRITICAL",
        )
        cls.client = TestClient(create_app(settings))
        cls.headers = {"X-EDGE2-Webhook-Secret": "test-webhook-secret"}

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

    def test_null_rr_is_accepted(self) -> None:
        response = self.client.post(
            "/api/polr/lifecycle",
            json=lifecycle_payload(rr_to_target=None),
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)

    def test_non_finite_or_invalid_rr_is_rejected(self) -> None:
        for value in ("NaN", "Infinity", "not-a-number"):
            with self.subTest(value=value):
                response = self.client.post(
                    "/api/polr/lifecycle",
                    json=lifecycle_payload(rr_to_target=value),
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
        for event_type in (
            "MSS_CONFIRMED",
            "GRADE_A",
            "GRADE_A_PLUS",
            "SETUP_FAILED",
            "SETUP_RETIRED",
            "TARGET_TAKEN",
        ):
            with self.subTest(event_type=event_type):
                response = self.client.post(
                    "/api/polr/lifecycle",
                    json=lifecycle_payload(event_type=event_type),
                    headers=self.headers,
                )

                self.assertEqual(response.status_code, 200)

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
