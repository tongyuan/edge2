from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from tests.db_support import clean, migrate_and_clean, require_test_database


def webhook_payload(index: int = 1, price: str = "110", **overrides):
    value = {
        "schema_version": "4.3",
        "event_id": f"api-event-{index}",
        "symbol": "SPXUSDT",
        "route": "BTD",
        "observation_type": "reclaim",
        "observation_price": price,
        "ipda_20w_high": "200",
        "ipda_20w_low": "100",
        "observed_at": f"2026-08-20T12:00:{index:02d}Z",
        "webhook_secret": "test-webhook-secret",
    }
    value.update(overrides)
    return value


class APIIntegrationTests(unittest.TestCase):
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

    def setUp(self) -> None:
        clean(self.database_url)

    def test_health_and_empty_symbol_collection(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["database"], "ok")
        self.assertEqual(self.client.get("/api/symbols").json(), {"symbols": []})

    def test_monitor_shell_uses_current_terminology_and_is_not_cached(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        self.assertIn("MRZ Monitor", response.text)
        self.assertNotIn("Symbol Lab", response.text)

    def test_valid_btd_valid_str_and_unestablished_responses(self) -> None:
        btd = self.client.post("/webhook/tradingview", json=webhook_payload())
        self.assertEqual(btd.status_code, 201)
        self.assertTrue(btd.json()["accepted"])
        detail = self.client.get("/api/symbols/SPXUSDT").json()
        self.assertEqual(detail["mrz_status"], "unestablished")
        self.assertEqual(detail["current_price_location"], "deep_discount")
        self.assertEqual(detail["latest_observed_at"], "2026-08-20T12:00:01Z")
        self.assertIsNone(detail["supporting_observation_count"])
        overview = self.client.get("/api/symbols").json()["symbols"]
        self.assertEqual(overview[0]["current_price_location"], "deep_discount")
        self.assertEqual(overview[0]["mrz_status"], "unestablished")
        str_packet = webhook_payload(
            2,
            "180",
            event_id="api-str-2",
            symbol="NASDAQ:NDX",
            route="STR",
            observation_type="rejection",
        )
        self.assertEqual(self.client.post("/webhook/tradingview", json=str_packet).status_code, 201)

    def test_duplicate_event_is_successful_no_op(self) -> None:
        packet = webhook_payload()
        self.assertEqual(self.client.post("/webhook/tradingview", json=packet).status_code, 201)
        duplicate = self.client.post("/webhook/tradingview", json=packet)
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["duplicate"])
        health = self.client.get("/health").json()
        self.assertEqual(health["accepted_payload_count"], 1)
        self.assertEqual(health["duplicate_payload_count"], 1)

    def test_activation_response_prioritizes_source_and_active_mrz(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1):
            response = self.client.post("/webhook/tradingview", json=webhook_payload(index, price))
            self.assertEqual(response.status_code, 201)
        detail = self.client.get("/api/symbols/SPXUSDT/mrz").json()
        self.assertEqual(detail["mrz_status"], "active")
        self.assertEqual(detail["route_owner"], "BTD")
        self.assertEqual(detail["core_mrz_lower"], 110.0)
        self.assertEqual(detail["core_mrz_upper"], 110.6)
        self.assertEqual(detail["structural_location"], "deep_discount_core_mrz")
        self.assertEqual(detail["current_price_location"], "deep_discount")
        self.assertEqual(detail["latest_observed_at"], "2026-08-20T12:00:04Z")
        self.assertEqual(detail["supporting_observation_count"], 4)
        self.assertNotIn("recommendation", detail)
        self.assertNotIn("readiness", detail)
        overview = self.client.get("/api/symbols").json()["symbols"][0]
        self.assertEqual(overview["mrz_status"], "active")

    def test_active_mrz_support_count_accepts_only_valid_frozen_core_evidence(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1):
            self.assertEqual(
                self.client.post("/webhook/tradingview", json=webhook_payload(index, price)).status_code,
                201,
            )
        activated = self.client.get("/api/symbols/SPXUSDT").json()
        self.assertEqual(activated["supporting_observation_count"], 4)

        support = webhook_payload(5, "110.3", event_id="active-core-support")
        self.assertEqual(self.client.post("/webhook/tradingview", json=support).status_code, 201)
        supported = self.client.get("/api/symbols/SPXUSDT").json()
        self.assertEqual(supported["supporting_observation_count"], 5)
        self.assertEqual(supported["core_mrz_lower"], activated["core_mrz_lower"])
        self.assertEqual(supported["core_mrz_upper"], activated["core_mrz_upper"])

        self.assertEqual(self.client.post("/webhook/tradingview", json=support).status_code, 200)
        inside_envelope = webhook_payload(6, "111", event_id="inside-envelope-not-support")
        successor = webhook_payload(7, "120", event_id="successor-not-current-support")
        opposite = webhook_payload(
            8,
            "180",
            event_id="opposite-route-not-support",
            route="STR",
            observation_type="rejection",
        )
        rejected = webhook_payload(
            9,
            "110.4",
            event_id="rejected-not-support",
            observation_type="rejection",
        )
        for packet in (inside_envelope, successor, opposite):
            self.assertEqual(self.client.post("/webhook/tradingview", json=packet).status_code, 201)
        self.assertEqual(self.client.post("/webhook/tradingview", json=rejected).status_code, 400)

        final = self.client.get("/api/symbols/SPXUSDT").json()
        self.assertEqual(final["supporting_observation_count"], 5)
        self.assertEqual(final["core_mrz_lower"], activated["core_mrz_lower"])
        self.assertEqual(final["core_mrz_upper"], activated["core_mrz_upper"])

    def test_current_price_location_is_independent_from_active_mrz_state(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1):
            response = self.client.post("/webhook/tradingview", json=webhook_payload(index, price))
            self.assertEqual(response.status_code, 201)
        before = self.client.get("/api/symbols/SPXUSDT/mrz").json()
        events_before = self.client.app.state.repository.audit_events("SPXUSDT")

        price_shift = webhook_payload(
            5,
            "160",
            event_id="current-price-shift",
            route="STR",
            observation_type="rejection",
        )
        response = self.client.post("/webhook/tradingview", json=price_shift)
        self.assertEqual(response.status_code, 201)
        after = self.client.get("/api/symbols/SPXUSDT/mrz").json()
        overview_after = self.client.get("/api/symbols").json()["symbols"][0]
        events_after = self.client.app.state.repository.audit_events("SPXUSDT")

        self.assertEqual(after["current_price_location"], "shallow_premium")
        self.assertEqual(after["latest_observed_at"], "2026-08-20T12:00:05Z")
        self.assertNotEqual(after["latest_observed_at"], after["activated_at"])
        self.assertEqual(overview_after["current_price_location"], "shallow_premium")
        self.assertEqual(overview_after["structural_location"], "deep_discount_core_mrz")
        self.assertEqual(after["route_owner"], before["route_owner"])
        self.assertEqual(after["core_mrz_lower"], before["core_mrz_lower"])
        self.assertEqual(after["core_mrz_upper"], before["core_mrz_upper"])
        transition_fields = (
            "event_key",
            "sequence",
            "event_type",
            "route_owner",
            "trigger_event_id",
            "new_core_mrz_lower",
            "new_core_mrz_upper",
        )
        self.assertEqual(
            [tuple(event[field] for field in transition_fields) for event in events_after],
            [tuple(event[field] for field in transition_fields) for event in events_before],
        )

    def test_current_price_at_exact_eqm_is_explicitly_unclassified(self) -> None:
        response = self.client.post("/webhook/tradingview", json=webhook_payload(price="150"))
        self.assertEqual(response.status_code, 201)
        detail = self.client.get("/api/symbols/SPXUSDT").json()
        self.assertIsNone(detail["current_price_location"])

    def test_symbols_overview_classifies_every_current_location_without_an_active_mrz(self) -> None:
        cases = (
            ("DD", "110", "deep_discount"),
            ("SD", "130", "shallow_discount"),
            ("SP", "160", "shallow_premium"),
            ("DP", "180", "deep_premium"),
            ("BELOW", "90", "below_ipda_range"),
            ("ABOVE", "210", "above_ipda_range"),
            ("EQM", "150", None),
        )
        for index, (symbol, price, _) in enumerate(cases, 1):
            packet = webhook_payload(
                index,
                price,
                event_id=f"overview-{index}",
                symbol=symbol,
            )
            self.assertEqual(self.client.post("/webhook/tradingview", json=packet).status_code, 201)

        symbols = self.client.get("/api/symbols").json()["symbols"]
        by_symbol = {item["symbol"]: item for item in symbols}
        self.assertEqual([item["symbol"] for item in symbols], sorted(by_symbol))
        for symbol, _, expected in cases:
            with self.subTest(symbol=symbol):
                self.assertEqual(by_symbol[symbol]["current_price_location"], expected)
                self.assertEqual(by_symbol[symbol]["mrz_status"], "unestablished")

        update = webhook_payload(
            8,
            "160",
            event_id="overview-location-update",
            symbol="DD",
        )
        self.assertEqual(self.client.post("/webhook/tradingview", json=update).status_code, 201)
        updated = {
            item["symbol"]: item for item in self.client.get("/api/symbols").json()["symbols"]
        }
        self.assertEqual(updated["DD"]["current_price_location"], "shallow_premium")

    def test_authentication_is_required_and_secret_is_redacted(self) -> None:
        packet = webhook_payload()
        packet.pop("webhook_secret")
        response = self.client.post("/webhook/tradingview", json=packet)
        self.assertEqual(response.status_code, 401)
        health = self.client.get("/health").json()
        self.assertEqual(health["rejected_payload_count"], 1)

    def test_header_authentication_is_supported(self) -> None:
        packet = webhook_payload()
        packet.pop("webhook_secret")
        response = self.client.post(
            "/webhook/tradingview",
            json=packet,
            headers={"X-EDGE2-Webhook-Secret": "test-webhook-secret"},
        )
        self.assertEqual(response.status_code, 201)

    def test_invalid_json_is_rejected_and_counted(self) -> None:
        response = self.client.post(
            "/webhook/tradingview",
            content=b"{not-json",
            headers={"content-type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/health").json()["rejected_payload_count"], 1)

    def test_schema_validation_matrix(self) -> None:
        invalid_cases = (
            {"observation_price": "not-a-number"},
            {"ipda_20w_high": "100", "ipda_20w_low": "100"},
            {"schema_version": "4.2"},
            {"route": "BTD", "observation_type": "rejection"},
            {"route": "STR", "observation_type": "reclaim"},
            {"observed_at": "2026-08-20T12:00:00"},
        )
        for index, overrides in enumerate(invalid_cases, 1):
            packet = webhook_payload(index, event_id=f"invalid-{index}", **overrides)
            with self.subTest(overrides=overrides):
                response = self.client.post("/webhook/tradingview", json=packet)
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get("/health").json()["rejected_payload_count"], len(invalid_cases))

    def test_unknown_symbol_returns_404(self) -> None:
        self.assertEqual(self.client.get("/api/symbols/UNKNOWN").status_code, 404)
