from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.db import connect
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
        self.assertEqual(
            self.client.get("/api/symbols").json(),
            {
                "minimum_cluster_observations": 4,
                "location_migration_tendency": {
                    key: {
                        "migration_samples": 0,
                        "higher_count": 0,
                        "lower_count": 0,
                        "higher_pct": None,
                        "lower_pct": None,
                    }
                    for key in (
                        "deep_discount",
                        "shallow_discount",
                        "shallow_premium",
                        "deep_premium",
                    )
                },
                "symbols": [],
            },
        )

    def test_saved_group_crud_is_persistent_read_only_and_canonical(self) -> None:
        response = self.client.post(
            "/api/groups",
            json={
                "name": "MAG7",
                "members": [
                    "NASDAQ:aapl", "amzn", "GOOG", "META", "MSFT", "NVDA", "TSLA",
                ],
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        group = response.json()
        self.assertEqual(
            group["members"],
            ["AAPL", "AMZN", "GOOG", "META", "MSFT", "NVDA", "TSLA"],
        )
        self.assertEqual(group["current_state"]["active_mrz"], {"count": 0, "total": 7})
        self.assertEqual(
            group["current_state"]["migration_breadth"],
            {"higher": 0, "lower": 0, "no_migration": 7},
        )

        persisted = self.client.get("/api/groups")
        self.assertEqual(persisted.status_code, 200)
        self.assertEqual(persisted.json()["groups"][0]["name"], "MAG7")
        reopened = self.client.get(f"/api/groups/{group['id']}")
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(reopened.json()["members"], group["members"])
        path = self.client.get(f"/api/groups/{group['id']}/migration-path")
        self.assertEqual(path.status_code, 200)
        self.assertEqual(len(path.json()["paths"]), 7)
        self.assertTrue(all(not item["states"] for item in path.json()["paths"]))

        renamed = self.client.put(
            f"/api/groups/{group['id']}",
            json={"name": "Magnificent 7", "members": group["members"][:-1]},
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["name"], "Magnificent 7")
        self.assertEqual(renamed.json()["member_count"], 6)
        conflict = self.client.post(
            "/api/groups",
            json={"name": "magnificent 7", "members": ["AAPL"]},
        )
        self.assertEqual(conflict.status_code, 409)

        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                for table in ("observations", "active_mrz", "mrz_events"):
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    self.assertEqual(cursor.fetchone()[0], 0)
        finally:
            connection.close()

        deleted = self.client.delete(f"/api/groups/{group['id']}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()["deleted_group"]["name"], "Magnificent 7")
        self.assertEqual(self.client.get("/api/groups").json(), {"groups": []})

    def test_saved_group_validation_and_missing_ids_fail_safely(self) -> None:
        self.assertEqual(
            self.client.post("/api/groups", json={"name": "", "members": ["AAPL"]}).status_code,
            422,
        )
        self.assertEqual(
            self.client.post("/api/groups", json={"name": "MAG7", "members": []}).status_code,
            422,
        )
        self.assertEqual(self.client.get("/api/groups/999").status_code, 404)
        self.assertEqual(self.client.get("/api/groups/999/migration-path").status_code, 404)
        self.assertEqual(self.client.delete("/api/groups/999").status_code, 404)

    def test_monitor_shell_uses_current_terminology_and_is_not_cached(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        self.assertIn("MRZ Monitor", response.text)
        self.assertNotIn("Symbol Lab", response.text)

    def test_mrz_formation_diagnostics_page_keeps_compatible_route(self) -> None:
        response = self.client.get("/diagnostics/activation-feasibility")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        self.assertIn("MRZ Formation Diagnostics", response.text)
        self.assertNotIn(">Activation Feasibility<", response.text)
        self.assertIn("Observed MRZ formation frequency is descriptive", response.text)
        self.assertIn('id="productionContent"', response.text)
        self.assertIn("SYMBOL-ROUTE HISTORIES", response.text)
        self.assertNotIn("SYMBOL-ROUTE SEQUENCES", response.text)
        self.assertIn('id="currentNearMissContent"', response.text)
        self.assertIn('id="qualificationContent"', response.text)
        self.assertIn('id="productionSampleContent"', response.text)
        self.assertIn("Qualified under production rule", response.text)
        self.assertNotIn('id="summaryA"', response.text)
        self.assertNotIn('id="summaryB"', response.text)
        self.assertNotIn('id="matrixA"', response.text)
        self.assertNotIn('id="matrixB"', response.text)
        self.assertNotIn('id="comparisonTable"', response.text)
        self.assertNotIn('id="algorithmFilter"', response.text)
        self.assertNotIn("Algorithm B", response.text)
        self.assertNotIn("A/B comparison", response.text)
        self.assertNotIn('id="auditFilters"', response.text)
        self.assertNotIn('id="auditTable"', response.text)
        self.assertNotIn("What the current sample says", response.text)
        self.assertNotIn("Algorithm A scenario results", response.text)
        self.assertNotIn("Activation matrices", response.text)
        self.assertNotIn("Candidate Policy Evaluation", response.text)

    def test_mrz_robustness_page_is_separate_read_only_diagnostic(self) -> None:
        response = self.client.get("/diagnostics/mrz-robustness")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        self.assertIn("MRZ Operation Card", response.text)
        self.assertIn(
            "Current structural authority, robustness, pressure and migration state.",
            response.text,
        )
        self.assertIn("Observation only", response.text)
        self.assertIn("Operation Card", response.text)
        self.assertIn('id="activeReports"', response.text)
        self.assertNotIn('id="summaryA"', response.text)

    def test_mrz_robustness_report_page_is_hidden(self) -> None:
        response = self.client.get("/diagnostics/mrz-robustness-report")

        self.assertEqual(response.status_code, 404)

    def test_mrz_robustness_report_static_shell_is_hidden(self) -> None:
        response = self.client.get("/static/mrz-robustness-report.html")

        self.assertEqual(response.status_code, 404)

    def test_trading_window_feasibility_routes_are_removed(self) -> None:
        paths = (
            "/diagnostics/trading-window-feasibility",
            "/api/diagnostics/trading-window-feasibility",
            "/static/feasibility.html",
            "/static/feasibility.js",
            "/static/feasibility.css",
            "/static/formation-comparison.js",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_operator_page_navigation_is_reciprocal(self) -> None:
        monitor = self.client.get("/").text
        feasibility = self.client.get("/diagnostics/activation-feasibility").text
        robustness = self.client.get("/diagnostics/mrz-robustness").text

        pages = (monitor, feasibility, robustness)
        for page in pages:
            self.assertIn("Diagnostics", page)
            self.assertIn('data-diagnostics-trigger', page)
            self.assertIn('href="/diagnostics/activation-feasibility"', page)
            self.assertIn('href="/diagnostics/mrz-robustness"', page)
            self.assertIn("MRZ Formation Diagnostics", page)
            self.assertNotIn(">Activation Feasibility<", page)
            self.assertNotIn('href="/diagnostics/mrz-robustness-report"', page)
            self.assertNotIn('href="/diagnostics/trading-window-feasibility"', page)
            self.assertNotIn("Trading Window Feasibility", page)
        for page in (feasibility, robustness):
            self.assertIn('href="/">MRZ Monitor</a>', page)

    def test_mrz_robustness_report_api_is_hidden(self) -> None:
        response = self.client.get("/api/diagnostics/mrz-robustness-report")

        self.assertEqual(response.status_code, 404)

    def test_mrz_robustness_api_uses_authoritative_state_without_mutation(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6", "120"), 1):
            self.assertEqual(
                self.client.post(
                    "/webhook/tradingview",
                    json=webhook_payload(index, price),
                ).status_code,
                201,
            )

        before = self.client.get("/api/symbols/SPXUSDT").json()
        response = self.client.get("/api/diagnostics/mrz-robustness")
        after = self.client.get("/api/symbols/SPXUSDT").json()
        payload = response.json()
        report = payload["active_mrzs"][0]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        self.assertEqual(payload["active_mrz_count"], 1)
        self.assertEqual(report["symbol"], "SPXUSDT")
        self.assertEqual(report["route_owner"], "BTD")
        self.assertEqual(report["active_mrz"]["lower"], "110")
        self.assertEqual(report["active_mrz"]["upper"], "110.6")
        self.assertEqual(report["active_mrz"]["activated_at"], "2026-08-20T12:00:04Z")
        self.assertEqual(
            report["robustness_evidence"]["post_activation_observation_count"],
            1,
        )
        self.assertEqual(report["migration_pressure"]["status"], "UNDER_PRESSURE")
        self.assertEqual(report["migration_pressure"]["direction"], "UP")
        self.assertEqual(report["post_activation_robustness"]["status"], "UNDER_PRESSURE")
        self.assertEqual(report["structural_authority"]["label"], "Authoritative")
        self.assertEqual(report["structural_authority"]["structural_location_label"], "Deep Discount")
        self.assertEqual(
            report["observation_position"],
            {
                "above_active_mrz_observation_count": 1,
                "inside_active_mrz_observation_count": 0,
                "below_active_mrz_observation_count": 0,
                "total_observation_count": 1,
                "definition": (
                    "Mutually exclusive post-activation observation counts relative "
                    "to the inclusive frozen active MRZ bounds."
                ),
            },
        )
        self.assertEqual(
            report["mrz_displacement"][
                "median_signed_displacement_percentage_of_activation_ipda"
            ],
            "9.700",
        )
        self.assertEqual(report["mrz_displacement"]["direction"], "ABOVE")
        successor = report["successor_watch"]
        self.assertEqual(successor["status"], "EXTERNAL_OBSERVATIONS")
        self.assertEqual(successor["higher_external_observation_count"], 1)
        self.assertEqual(successor["lower_external_observation_count"], 0)
        self.assertIsNone(successor["candidate_lower"])
        self.assertIsNone(successor["candidate_upper"])
        self.assertIsNone(successor["route"])
        self.assertIsNone(successor["direction"])
        self.assertEqual(successor["production_allowance"], "0.01")
        self.assertEqual(
            successor["production_evaluation_result"],
            "INSUFFICIENT_OBSERVATIONS",
        )
        self.assertTrue(successor["current_mrz_remains_authoritative"])
        self.assertEqual(before, after)

    def test_monitor_and_robustness_share_current_migration_provenance(self) -> None:
        prices = (
            "110", "110.2", "110.4", "110.6",
            "120", "120.2", "120.4", "120.6", "120.3",
        )
        for index, price in enumerate(prices, 1):
            self.assertEqual(
                self.client.post(
                    "/webhook/tradingview",
                    json=webhook_payload(index, price),
                ).status_code,
                201,
            )

        monitor = self.client.get("/api/symbols/SPXUSDT").json()
        report = self.client.get(
            "/api/diagnostics/mrz-robustness"
        ).json()["active_mrzs"][0]

        self.assertTrue(monitor["migration"]["has_migrated"])
        self.assertEqual(
            monitor["migration"]["previous_activated_at"],
            "2026-08-20T12:00:04Z",
        )
        self.assertEqual(report["migration"], monitor["migration"])
        self.assertEqual(report["migration_pressure"]["status"], "STABLE")
        self.assertEqual(report["migration_pressure"]["direction"], "NEUTRAL")
        self.assertEqual(report["post_activation_robustness"]["status"], "STABLE")
        self.assertEqual(
            report["successor_watch"]["status"],
            "NO_SUCCESSOR_CANDIDATE",
        )

    def test_route_changing_successor_updates_monitor_who_where_and_timestamp(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1):
            self.assertEqual(
                self.client.post(
                    "/webhook/tradingview",
                    json=webhook_payload(index, price),
                ).status_code,
                201,
            )
        final_response = None
        for index, price in enumerate(("180", "180.2", "180.4", "180.6"), 5):
            final_response = self.client.post(
                "/webhook/tradingview",
                json=webhook_payload(
                    index,
                    price,
                    route="STR",
                    observation_type="rejection",
                ),
            )
            self.assertEqual(final_response.status_code, 201)

        monitor = self.client.get("/api/symbols/SPXUSDT").json()
        overview_payload = self.client.get("/api/symbols").json()
        overview = overview_payload["symbols"][0]
        operation_card = self.client.get(
            "/api/diagnostics/mrz-robustness"
        ).json()["active_mrzs"][0]

        self.assertEqual(final_response.json()["state"]["route_owner"], "STR")
        self.assertEqual(monitor["route_owner"], "STR")
        self.assertEqual(monitor["core_mrz_lower"], 180.0)
        self.assertEqual(monitor["core_mrz_upper"], 180.6)
        self.assertEqual(monitor["structural_location"], "deep_premium_core_mrz")
        self.assertEqual(monitor["activated_at"], "2026-08-20T12:00:08Z")
        self.assertEqual(monitor["activation_event_id"], "api-event-8")
        self.assertEqual(monitor["migration"]["route_owner"], "STR")
        self.assertEqual(monitor["migration"]["previous_lower"], 110.0)
        self.assertEqual(monitor["migration"]["current_lower"], 180.0)
        self.assertEqual(overview["route_owner"], "STR")
        self.assertEqual(overview["structural_location"], "deep_premium_core_mrz")
        self.assertTrue(overview["has_migrated"])
        self.assertEqual(
            overview_payload["location_migration_tendency"]["deep_discount"],
            {
                "migration_samples": 1,
                "higher_count": 1,
                "lower_count": 0,
                "higher_pct": 100.0,
                "lower_pct": 0.0,
            },
        )
        self.assertEqual(
            overview_payload["location_migration_tendency"]["deep_premium"][
                "migration_samples"
            ],
            0,
        )
        self.assertEqual(operation_card["route_owner"], "STR")
        self.assertEqual(operation_card["active_mrz"]["lower"], "180")
        self.assertEqual(operation_card["active_mrz"]["activated_at"], "2026-08-20T12:00:08Z")

    def test_activation_feasibility_api_empty_and_refreshes_without_stale_results(self) -> None:
        first = self.client.get("/api/diagnostics/activation-feasibility")
        second = self.client.get("/api/diagnostics/activation-feasibility")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.headers["cache-control"], "no-store, max-age=0")
        first_payload = first.json()
        second_payload = second.json()
        self.assertEqual(len(first_payload["scenarios"]), 30)
        self.assertEqual(len(first_payload["comparisons"]), 15)
        self.assertEqual(first_payload["sequence_details"], [])
        self.assertEqual(
            first_payload["diagnosis"]["sample_assessment"]["code"],
            "SAMPLE_PRELIMINARY",
        )
        self.assertNotEqual(first_payload["generated_at"], second_payload["generated_at"])
        first_payload.pop("generated_at")
        second_payload.pop("generated_at")
        self.assertEqual(first_payload, second_payload)

    def test_activation_feasibility_api_serializes_auditable_results_without_event_ids(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1):
            self.assertEqual(
                self.client.post("/webhook/tradingview", json=webhook_payload(index, price)).status_code,
                201,
            )

        response = self.client.get("/api/diagnostics/activation-feasibility")
        payload = response.json()
        production = payload["current_production_rule"]["result"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["total_observations_evaluated"], 4)
        self.assertEqual(payload["total_normalized_symbols"], 1)
        self.assertEqual(payload["total_symbol_route_sequences"], 1)
        self.assertEqual(production["scenario_id"], "A-4-1")
        self.assertEqual(production["hypothetical_activations"], 1)
        self.assertEqual(
            production["median_minimum_required_allowance_pct_at_qualification"],
            "0.600",
        )
        self.assertEqual(payload["current_production_rule"]["label"], "Algorithm A · 4 observations · 1.00%")
        self.assertEqual(
            payload["current_production_rule"]["activations"],
            [{
                "symbol": "SPXUSDT",
                "route": "BTD",
                "core_mrz_lower": "110",
                "core_mrz_upper": "110.6",
                "activated_at": "2026-08-20T12:00:04Z",
                "minimum_observations": 4,
                "allowance_percent": 1,
            }],
        )
        self.assertEqual(
            payload["diagnosis"]["production_feasibility"]["numerator"],
            1,
        )
        self.assertNotIn("event_id", response.text)
        self.assertNotIn("api-event", response.text)

    def test_valid_btd_valid_str_and_unestablished_responses(self) -> None:
        btd = self.client.post("/webhook/tradingview", json=webhook_payload())
        self.assertEqual(btd.status_code, 201)
        self.assertTrue(btd.json()["accepted"])
        detail = self.client.get("/api/symbols/SPXUSDT").json()
        self.assertEqual(detail["mrz_status"], "unestablished")
        self.assertEqual(detail["migration"], {"has_migrated": False})
        self.assertIsNone(detail["activated_at"])
        self.assertEqual(detail["current_price_location"], "deep_discount")
        self.assertEqual(detail["current_location_context"], "80% from EQM toward IPDA low")
        self.assertEqual(detail["latest_observed_at"], "2026-08-20T12:00:01Z")
        self.assertEqual(detail["latest_observation_route"], "BTD")
        self.assertEqual(detail["latest_observation_type"], "reclaim")
        self.assertEqual(detail["btd_window_observation_count"], 1)
        self.assertEqual(detail["btd_window_started_at"], "2026-08-20T12:00:01Z")
        self.assertEqual(detail["str_window_observation_count"], 0)
        self.assertIsNone(detail["str_window_started_at"])
        self.assertEqual(detail["concentration_checks"]["BTD"]["result"], "INSUFFICIENT_OBSERVATIONS")
        self.assertEqual(detail["concentration_checks"]["BTD"]["minimum_required_count"], 4)
        self.assertIsNone(detail["concentration_checks"]["BTD"]["selected_lower"])
        self.assertEqual(detail["concentration_checks"]["STR"]["retained_observation_count"], 0)
        self.assertNotIn("newest_observation_id", detail["concentration_checks"]["BTD"])
        self.assertNotIn("selected_observation_ids", detail["concentration_checks"]["BTD"])
        self.assertIsNone(detail["supporting_observation_count"])
        self.assertIsNone(detail["formation_started_at"])
        self.assertIsNone(detail["formation_completed_at"])
        self.assertIsNone(detail["formation_duration_seconds"])
        overview = self.client.get("/api/symbols").json()["symbols"]
        self.assertEqual(overview[0]["current_price_location"], "deep_discount")
        self.assertEqual(overview[0]["mrz_status"], "unestablished")
        self.assertFalse(overview[0]["has_migrated"])
        self.assertEqual(overview[0]["btd_window_observation_count"], 1)
        self.assertEqual(overview[0]["str_window_observation_count"], 0)
        str_packet = webhook_payload(
            2,
            "180",
            event_id="api-str-2",
            symbol="NASDAQ:NDX",
            route="STR",
            observation_type="rejection",
        )
        self.assertEqual(self.client.post("/webhook/tradingview", json=str_packet).status_code, 201)
        str_detail = self.client.get("/api/symbols/NASDAQ:NDX").json()
        self.assertEqual(str_detail["btd_window_observation_count"], 0)
        self.assertIsNone(str_detail["btd_window_started_at"])
        self.assertEqual(str_detail["str_window_observation_count"], 1)
        self.assertEqual(str_detail["str_window_started_at"], "2026-08-20T12:00:02Z")
        self.assertEqual(str_detail["concentration_checks"]["STR"]["result"], "INSUFFICIENT_OBSERVATIONS")

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
        self.assertEqual(detail["migration"], {"has_migrated": False})
        self.assertEqual(detail["route_owner"], "BTD")
        self.assertEqual(detail["core_mrz_lower"], 110.0)
        self.assertEqual(detail["core_mrz_upper"], 110.6)
        self.assertEqual(detail["structural_location"], "deep_discount_core_mrz")
        self.assertEqual(detail["current_price_location"], "deep_discount")
        self.assertEqual(detail["latest_observed_at"], "2026-08-20T12:00:04Z")
        self.assertEqual(detail["activated_at"], "2026-08-20T12:00:04Z")
        self.assertEqual(detail["supporting_observation_count"], 4)
        self.assertEqual(detail["formation_started_at"], "2026-08-20T12:00:01Z")
        self.assertEqual(detail["formation_completed_at"], "2026-08-20T12:00:04Z")
        self.assertEqual(detail["formation_duration_seconds"], 3.0)
        self.assertIsNone(detail["concentration_checks"])
        self.assertNotIn("recommendation", detail)
        self.assertNotIn("readiness", detail)
        overview = self.client.get("/api/symbols").json()["symbols"][0]
        self.assertEqual(overview["mrz_status"], "active")

    def test_unestablished_detail_reports_raw_retained_route_windows_without_progress(self) -> None:
        btd_prices = ("110", "120", "130")
        str_prices = ("160", "168", "176", "184", "192", "200")
        for index, price in enumerate(btd_prices, 1):
            self.assertEqual(
                self.client.post("/webhook/tradingview", json=webhook_payload(index, price)).status_code,
                201,
            )
        for index, price in enumerate(str_prices, 4):
            packet = webhook_payload(
                index,
                price,
                route="STR",
                observation_type="rejection",
            )
            self.assertEqual(self.client.post("/webhook/tradingview", json=packet).status_code, 201)

        detail = self.client.get("/api/symbols/SPXUSDT").json()
        self.assertEqual(detail["mrz_status"], "unestablished")
        self.assertIsNone(detail["route_owner"])
        self.assertEqual(detail["btd_window_observation_count"], 3)
        self.assertEqual(detail["btd_window_started_at"], "2026-08-20T12:00:01Z")
        self.assertEqual(detail["str_window_observation_count"], 6)
        self.assertEqual(detail["str_window_started_at"], "2026-08-20T12:00:04Z")
        btd_check = detail["concentration_checks"]["BTD"]
        str_check = detail["concentration_checks"]["STR"]
        self.assertEqual(btd_check["result"], "INSUFFICIENT_OBSERVATIONS")
        self.assertEqual(str_check["result"], "TOO_DISPERSED")
        self.assertEqual(str_check["retained_observation_count"], 6)
        self.assertEqual(str_check["selected_observation_count"], 4)
        self.assertEqual(str_check["selected_lower"], "176")
        self.assertEqual(str_check["selected_upper"], "200")
        self.assertEqual(str_check["observed_span"], "24")
        self.assertEqual(str_check["ipda_width"], "100")
        self.assertEqual(str_check["allowance"], "1.00")
        self.assertEqual(str_check["normalized_span"], "0.24")
        self.assertEqual(str_check["minimum_required_allowance_pct"], "24.00")
        self.assertEqual(str_check["configured_allowance_pct"], "1.00")
        self.assertEqual(str_check["allowance_difference_pct_points"], "23.00")
        self.assertEqual(str_check["allowance_comparison"], "SHORTFALL")
        self.assertFalse(str_check["concentration_passed"])
        self.assertTrue(str_check["structural_eligibility_passed"])
        overview = self.client.get("/api/symbols").json()["symbols"][0]
        self.assertEqual(overview["btd_window_observation_count"], 3)
        self.assertEqual(overview["str_window_observation_count"], 6)
        self.assertNotIn("formation_progress", detail)
        self.assertNotIn("progress", detail)
        self.assertNotIn("predicted_route_owner", detail)

    def test_overview_ranking_uses_the_tighter_independently_eligible_route(self) -> None:
        for index, price in enumerate(("110", "110.4", "110.9", "111.8"), 1):
            packet = webhook_payload(index, price, symbol="DUAL")
            self.assertEqual(self.client.post("/webhook/tradingview", json=packet).status_code, 201)
        for index, price in enumerate(("180", "180.7", "181.5", "182.4"), 5):
            packet = webhook_payload(
                index,
                price,
                symbol="DUAL",
                route="STR",
                observation_type="rejection",
            )
            self.assertEqual(self.client.post("/webhook/tradingview", json=packet).status_code, 201)

        detail = self.client.get("/api/symbols/DUAL").json()
        overview = self.client.get("/api/symbols").json()["symbols"][0]
        ranking = overview["concentration_ranking"]

        self.assertEqual(overview["mrz_status"], "unestablished")
        self.assertEqual(overview["btd_window_observation_count"], 4)
        self.assertEqual(overview["str_window_observation_count"], 4)
        self.assertLess(
            float(detail["concentration_checks"]["BTD"]["minimum_required_allowance_pct"]),
            float(detail["concentration_checks"]["STR"]["minimum_required_allowance_pct"]),
        )
        self.assertEqual(ranking["route"], "BTD")
        self.assertEqual(ranking["observation_count"], 4)
        self.assertEqual(
            ranking["minimum_required_allowance_pct"],
            detail["concentration_checks"]["BTD"]["minimum_required_allowance_pct"],
        )
        self.assertEqual(
            ranking["configured_allowance_pct"],
            detail["concentration_checks"]["BTD"]["configured_allowance_pct"],
        )

    def test_unestablished_route_window_counts_cap_at_twenty(self) -> None:
        for index in range(1, 26):
            price = f"{101 + (index * 1.8):.1f}"
            self.assertEqual(
                self.client.post("/webhook/tradingview", json=webhook_payload(index, price)).status_code,
                201,
            )

        detail = self.client.get("/api/symbols/SPXUSDT").json()
        self.assertEqual(detail["mrz_status"], "unestablished")
        self.assertEqual(detail["btd_window_observation_count"], 20)
        self.assertEqual(detail["btd_window_started_at"], "2026-08-20T12:00:06Z")
        self.assertEqual(detail["str_window_observation_count"], 0)
        self.assertIsNone(detail["str_window_started_at"])
        overview = self.client.get("/api/symbols").json()["symbols"][0]
        self.assertEqual(overview["btd_window_observation_count"], 20)
        self.assertEqual(overview["str_window_observation_count"], 0)

    def test_structurally_ineligible_diagnostic_uses_production_evaluator(self) -> None:
        for index, price in enumerate(("120", "120.2", "120.4", "120.6"), 1):
            packet = webhook_payload(
                index,
                price,
                route="STR",
                observation_type="rejection",
            )
            self.assertEqual(self.client.post("/webhook/tradingview", json=packet).status_code, 201)

        detail = self.client.get("/api/symbols/SPXUSDT").json()
        diagnostic = detail["concentration_checks"]["STR"]
        self.assertEqual(detail["mrz_status"], "unestablished")
        self.assertEqual(diagnostic["result"], "STRUCTURALLY_INELIGIBLE")
        self.assertEqual(diagnostic["selected_lower"], "120")
        self.assertEqual(diagnostic["selected_upper"], "120.6")
        self.assertEqual(diagnostic["observed_span"], "0.6")
        self.assertEqual(diagnostic["ipda_width"], "100")
        self.assertEqual(diagnostic["allowance"], "1.00")
        self.assertEqual(diagnostic["normalized_span"], "0.006")
        self.assertEqual(diagnostic["minimum_required_allowance_pct"], "0.600")
        self.assertEqual(diagnostic["configured_allowance_pct"], "1.00")
        self.assertEqual(diagnostic["allowance_difference_pct_points"], "-0.400")
        self.assertEqual(diagnostic["allowance_comparison"], "MARGIN")
        self.assertEqual(diagnostic["proposed_midpoint"], "120.3")
        self.assertEqual(diagnostic["proposed_structural_location"], "deep_discount")
        self.assertTrue(diagnostic["concentration_passed"])
        self.assertFalse(diagnostic["structural_eligibility_passed"])

    def test_unexpected_qualifying_unestablished_state_is_visible_and_logged(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1):
            self.assertEqual(
                self.client.post("/webhook/tradingview", json=webhook_payload(index, price)).status_code,
                201,
            )
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM active_mrz WHERE symbol = %s", ("SPXUSDT",))
            connection.commit()
        finally:
            connection.close()

        with self.assertLogs("edge2.repository", level="ERROR") as captured:
            detail = self.client.get("/api/symbols/SPXUSDT").json()
        self.assertEqual(detail["mrz_status"], "unestablished")
        self.assertEqual(detail["concentration_checks"]["BTD"]["result"], "QUALIFIES")
        self.assertIn("Concentration qualifies without active MRZ", captured.output[0])

    def test_four_dispersed_observations_remain_unestablished(self) -> None:
        for index, price in enumerate(("110", "120", "130", "140"), 1):
            self.assertEqual(
                self.client.post("/webhook/tradingview", json=webhook_payload(index, price)).status_code,
                201,
            )
        detail = self.client.get("/api/symbols/SPXUSDT").json()
        self.assertEqual(detail["mrz_status"], "unestablished")
        self.assertEqual(detail["btd_window_observation_count"], 4)
        self.assertIsNone(detail["route_owner"])

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
        self.assertEqual(after["activated_at"], before["activated_at"])
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
