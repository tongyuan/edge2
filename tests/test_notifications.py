from __future__ import annotations

import json
import unittest

from fastapi.testclient import TestClient
from pywebpush import WebPushException

from app.api import create_app
from app.config import Settings
from app.db import connect, transaction
from app.notifications import (
    PRESSURE_EVENT_TYPE,
    is_retryable_push_failure,
    should_notify_pressure_transition,
)
from app.validation import ObservationPayload
from tests.db_support import clean, migrate_and_clean, require_test_database
from tests.test_api import webhook_payload


PUBLIC_KEY = "B" + ("A" * 86)
PRIVATE_KEY = "C" * 43
SUBSCRIPTION = {
    "endpoint": "https://push.example.test/subscriptions/device-one",
    "keys": {"p256dh": "A" * 87, "auth": "B" * 22},
}


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.reason = "test failure"
        self.text = ""


class RecordingSender:
    def __init__(self, failure_status: int | None = None) -> None:
        self.failure_status = failure_status
        self.calls: list[dict] = []
        self.outcomes: list[int | BaseException | None] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0) if self.outcomes else self.failure_status
        if isinstance(outcome, BaseException):
            raise outcome
        if outcome is not None:
            raise WebPushException(
                "simulated delivery failure",
                response=FakeResponse(outcome),
            )
        return FakeResponse(201)


class PressureTransitionPolicyTests(unittest.TestCase):
    def test_only_directional_entries_and_flips_are_notifiable(self) -> None:
        matrix = {
            ("NEUTRAL", "UP"): True,
            ("NEUTRAL", "DOWN"): True,
            ("UP", "DOWN"): True,
            ("DOWN", "UP"): True,
            ("UP", "UP"): False,
            ("DOWN", "DOWN"): False,
            ("UP", "NEUTRAL"): False,
            ("DOWN", "NEUTRAL"): False,
            ("NEUTRAL", "NEUTRAL"): False,
        }
        for transition, expected in matrix.items():
            with self.subTest(transition=transition):
                self.assertEqual(
                    should_notify_pressure_transition(*transition),
                    expected,
                )


class NotificationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database(cls)
        migrate_and_clean(cls.database_url)

    def setUp(self) -> None:
        clean(self.database_url)
        self.sender = RecordingSender()
        settings = Settings(
            app_env="test",
            database_url=self.database_url,
            webhook_secret="test-webhook-secret",
            require_webhook_secret=True,
            symbol_ticks={},
            max_request_bytes=32768,
            log_level="CRITICAL",
            web_push_vapid_public_key=PUBLIC_KEY,
            web_push_vapid_private_key=PRIVATE_KEY,
            web_push_vapid_subject="mailto:operator@example.com",
        )
        self.client_context = TestClient(
            create_app(settings, web_push_sender=self.sender)
        )
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)

    def activate(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1):
            response = self.client.post(
                "/webhook/tradingview",
                json=webhook_payload(index, price),
            )
            self.assertEqual(response.status_code, 201)

    def post_btc_observation(
        self,
        index: int,
        price: str,
        *,
        route: str = "BTD",
    ):
        return self.client.post(
            "/webhook/tradingview",
            json=webhook_payload(
                index,
                price,
                event_id=f"btc-event-{index}",
                symbol="BTCUSDT",
                route=route,
                observation_type="reclaim" if route == "BTD" else "rejection",
                ipda_20w_low="70000",
                ipda_20w_high="90000",
            ),
        )

    def post_btc_cluster(
        self,
        start_index: int,
        prices: tuple[str, ...],
        *,
        route: str = "BTD",
    ) -> None:
        for offset, price in enumerate(prices):
            response = self.post_btc_observation(
                start_index + offset,
                price,
                route=route,
            )
            self.assertEqual(response.status_code, 201)

    def activate_btc(self) -> None:
        self.post_btc_cluster(
            1,
            ("77309.19", "77350", "77400", "77436.91"),
        )

    def post_mu_near_miss_observation(self, index: int, price: str):
        return self.client.post(
            "/webhook/tradingview",
            json=webhook_payload(
                index,
                price,
                event_id=f"mu-near-event-{index}",
                symbol="MU",
                route="STR",
                observation_type="rejection",
                ipda_20w_low="200",
                ipda_20w_high="1020.5882352941176470588235294",
            ),
        )

    def scalar(self, query: str):
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchone()[0]
        finally:
            connection.close()

    def active_mrz_signature(self) -> str:
        return self.scalar(
            """
            SELECT CONCAT_WS(
                '|', symbol, route_owner, core_mrz_lower::text,
                core_mrz_upper::text, activation_event_id,
                activated_at::text, updated_at::text
            )
            FROM active_mrz
            """
        )

    def active_authority_signature(self, symbol: str = "SPXUSDT") -> str:
        return self.scalar(
            f"""
            SELECT CONCAT_WS(
                '|', symbol, route_owner, core_mrz_lower::text,
                core_mrz_upper::text, activation_event_id, activated_at::text
            )
            FROM active_mrz
            WHERE symbol = '{symbol}'
            """
        )

    def post_spx(self, index: int, price: str):
        response = self.client.post(
            "/webhook/tradingview",
            json=webhook_payload(index, price),
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response

    def ingest_spx_without_notification(self, index: int, price: str) -> None:
        payload = ObservationPayload.model_validate(webhook_payload(index, price))
        self.client.app.state.repository.ingest(
            payload,
            payload.price_tick({}),
        )

    def pressure_notification_count(self) -> int:
        return self.scalar(
            "SELECT COUNT(*) FROM web_push_notifications "
            f"WHERE event_type = '{PRESSURE_EVENT_TYPE}'"
        )

    def current_pressure_state(self, symbol: str = "SPXUSDT") -> str:
        return self.scalar(
            "SELECT p.current_state FROM post_activation_pressure_states p "
            "INNER JOIN active_mrz a "
            "ON a.symbol = p.symbol "
            "AND a.activation_event_id = p.activation_event_id "
            f"WHERE p.symbol = '{symbol}'"
        )

    def pressure_events(self) -> list[dict]:
        return [
            event
            for event in self.client.get(
                "/api/notifications/events?after=0"
            ).json()["events"]
            if event["event_type"] == PRESSURE_EVENT_TYPE
        ]

    def test_ranging_to_upward_uses_shared_state_and_needs_no_successor(self) -> None:
        self.client.post("/api/notifications/subscriptions", json=SUBSCRIPTION)
        self.activate()
        self.assertEqual(self.current_pressure_state(), "NEUTRAL")

        # Remain balanced until four dispersed above-envelope observations
        # materially dominate two dispersed below-envelope observations.
        for index, price in enumerate(("120", "90", "140", "80", "160"), 5):
            self.post_spx(index, price)
        self.assertEqual(self.current_pressure_state(), "NEUTRAL")
        self.assertEqual(self.pressure_notification_count(), 0)
        self.post_spx(10, "180")

        self.assertEqual(self.current_pressure_state(), "UP")
        self.assertEqual(self.pressure_notification_count(), 1)
        event = self.pressure_events()[0]
        self.assertEqual(event["previous_state"], "NEUTRAL")
        self.assertEqual(event["current_state"], "UP")
        self.assertEqual(event["title"], "SPXUSDT · Upward Pressure")
        self.assertEqual(event["post_activation_observation_count"], 6)
        self.assertEqual(event["above_mrz_count"], 4)
        self.assertEqual(event["above_envelope_count"], 4)
        self.assertEqual(event["successor_status"], "NO_QUALIFYING_SUCCESSOR")
        self.assertEqual(event["successor_label"], "No qualifying successor")
        self.assertEqual(
            event["url"],
            "/diagnostics/mrz-robustness?symbol=SPXUSDT#post-activation",
        )
        self.assertIn("above-envelope", event["body"])

        self.post_spx(11, "170")
        self.assertEqual(self.current_pressure_state(), "UP")
        self.assertEqual(self.pressure_notification_count(), 1)

    def test_ranging_to_downward_and_unchanged_down_do_not_repeat(self) -> None:
        self.activate()
        self.post_spx(5, "90")
        self.post_spx(6, "50")
        self.assertEqual(self.current_pressure_state(), "DOWN")
        self.assertEqual(self.pressure_notification_count(), 1)
        event = self.pressure_events()[0]
        self.assertEqual(event["previous_state"], "NEUTRAL")
        self.assertEqual(event["current_state"], "DOWN")
        self.assertIn("below-envelope", event["body"])

        self.post_spx(7, "20")
        self.assertEqual(self.current_pressure_state(), "DOWN")
        self.assertEqual(self.pressure_notification_count(), 1)

    def test_neutral_resolution_is_persisted_and_reentry_is_new_episode(self) -> None:
        self.activate()
        self.post_spx(5, "120")
        self.post_spx(6, "150")
        first_key = self.scalar(
            "SELECT source_event_key FROM web_push_notifications "
            f"WHERE event_type = '{PRESSURE_EVENT_TYPE}'"
        )

        self.post_spx(7, "90")
        self.post_spx(8, "80")
        self.assertEqual(self.current_pressure_state(), "NEUTRAL")
        self.assertEqual(self.pressure_notification_count(), 1)

        self.post_spx(9, "170")
        self.assertEqual(self.current_pressure_state(), "NEUTRAL")
        self.post_spx(10, "180")
        self.assertEqual(self.current_pressure_state(), "UP")
        self.assertEqual(self.pressure_notification_count(), 2)
        keys = self.scalar(
            "SELECT COUNT(DISTINCT source_event_key) "
            "FROM web_push_notifications "
            f"WHERE event_type = '{PRESSURE_EVENT_TYPE}'"
        )
        self.assertEqual(keys, 2)
        self.assertNotEqual(self.pressure_events()[-1]["source_event_key"], first_key)

    def test_restart_recovery_can_flip_direction_without_duplicate_or_mrz_change(self) -> None:
        self.activate()
        self.post_spx(5, "120")
        self.post_spx(6, "150")
        self.assertEqual(self.current_pressure_state(), "UP")
        authority_before = self.active_authority_signature()

        for index, price in enumerate(("90", "80", "70", "60"), 7):
            self.ingest_spx_without_notification(index, price)
        self.client.app.state.notification_service.recover()

        self.assertEqual(self.current_pressure_state(), "DOWN")
        self.assertEqual(self.pressure_notification_count(), 2)
        downward = self.pressure_events()[-1]
        self.assertEqual(downward["previous_state"], "UP")
        self.assertEqual(downward["current_state"], "DOWN")
        self.assertEqual(self.active_authority_signature(), authority_before)

        for index, price in enumerate(("170", "180", "190", "195"), 11):
            self.ingest_spx_without_notification(index, price)
        self.client.app.state.notification_service.recover()
        self.assertEqual(self.current_pressure_state(), "UP")
        self.assertEqual(self.pressure_notification_count(), 3)
        upward = self.pressure_events()[-1]
        self.assertEqual(upward["previous_state"], "DOWN")
        self.assertEqual(upward["current_state"], "UP")
        self.assertEqual(self.active_authority_signature(), authority_before)

        duplicate = self.client.post(
            "/webhook/tradingview",
            json=webhook_payload(14, "195"),
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["duplicate"])
        self.client.app.state.notification_service.recover()
        self.assertEqual(self.pressure_notification_count(), 3)
        self.assertEqual(self.active_authority_signature(), authority_before)

    def test_pressure_delivery_retry_keeps_one_logical_notification(self) -> None:
        self.activate()
        self.client.post("/api/notifications/subscriptions", json=SUBSCRIPTION)
        self.sender.outcomes = [503, None]
        self.post_spx(5, "120")
        self.post_spx(6, "150")
        authority_before = self.active_authority_signature()

        self.assertEqual(self.pressure_notification_count(), 1)
        pressure_key = self.scalar(
            "SELECT source_event_key FROM web_push_notifications "
            f"WHERE event_type = '{PRESSURE_EVENT_TYPE}'"
        )
        self.assertEqual(len(self.sender.calls), 1)
        self.assertTrue(
            self.scalar(
                "SELECT d.retryable FROM web_push_delivery_attempts d "
                "INNER JOIN web_push_notifications n ON n.id = d.notification_id "
                f"WHERE n.event_type = '{PRESSURE_EVENT_TYPE}'"
            )
        )

        self.client.app.state.notification_service.recover()
        self.assertEqual(len(self.sender.calls), 2)
        self.assertEqual(self.pressure_notification_count(), 1)
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_delivery_attempts d "
                "INNER JOIN web_push_notifications n ON n.id = d.notification_id "
                f"WHERE n.event_type = '{PRESSURE_EVENT_TYPE}'"
            ),
            2,
        )
        payloads = [json.loads(call["data"]) for call in self.sender.calls]
        self.assertTrue(
            all(item["source_event_key"] == pressure_key for item in payloads)
        )
        self.assertEqual(self.active_authority_signature(), authority_before)

    def test_new_mrz_lifecycle_does_not_inherit_previous_pressure(self) -> None:
        self.activate_btc()
        self.post_btc_cluster(5, ("81000", "85000"))
        self.assertEqual(self.current_pressure_state("BTCUSDT"), "UP")
        self.post_btc_cluster(7, ("78919.34", "78950", "79000", "79030"))

        current_activation = self.scalar(
            "SELECT activation_event_id FROM active_mrz WHERE symbol = 'BTCUSDT'"
        )
        self.assertEqual(current_activation, "btc-event-10")
        self.assertEqual(self.current_pressure_state("BTCUSDT"), "NEUTRAL")
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM post_activation_pressure_states "
                "WHERE symbol = 'BTCUSDT'"
            ),
            2,
        )

        self.post_btc_cluster(11, ("82000", "87000"))
        self.assertEqual(self.current_pressure_state("BTCUSDT"), "UP")
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications "
                f"WHERE event_type = '{PRESSURE_EVENT_TYPE}' "
                "AND symbol = 'BTCUSDT'"
            ),
            2,
        )
        lifecycle_ids = self.scalar(
            "SELECT COUNT(DISTINCT lifecycle_activation_event_id) "
            "FROM web_push_notifications "
            f"WHERE event_type = '{PRESSURE_EVENT_TYPE}' "
            "AND symbol = 'BTCUSDT'"
        )
        self.assertEqual(lifecycle_ids, 2)

    def test_operator_promoted_authority_uses_the_same_pressure_path(self) -> None:
        for index, price in enumerate(("941.52", "941.52", "941.52", "949.89"), 1):
            self.assertEqual(
                self.post_mu_near_miss_observation(index, price).status_code,
                201,
            )
        candidate = self.client.get(
            "/api/diagnostics/activation-feasibility"
        ).json()["diagnosis"]["current_production_near_misses"][0]
        promoted = self.client.post(
            "/api/diagnostics/activation-feasibility/near-misses/MU/promote",
            json={
                "route": candidate["route"],
                "candidate_identity": candidate["candidate_identity"],
            },
        )
        self.assertEqual(promoted.status_code, 201, promoted.text)
        self.assertEqual(promoted.json()["state"]["activation_source"], "OPERATOR_PROMOTED")
        self.assertEqual(self.current_pressure_state("MU"), "NEUTRAL")

        self.assertEqual(self.post_mu_near_miss_observation(5, "900").status_code, 201)
        self.assertEqual(self.post_mu_near_miss_observation(6, "850").status_code, 201)
        self.assertEqual(self.current_pressure_state("MU"), "DOWN")
        pressure = [
            event for event in self.pressure_events() if event["symbol"] == "MU"
        ]
        self.assertEqual(len(pressure), 1)
        self.assertEqual(pressure[0]["current_state"], "DOWN")

    def test_preexisting_pressure_is_baselined_without_historical_push(self) -> None:
        self.activate()
        self.post_spx(5, "120")
        self.post_spx(6, "150")
        with transaction(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM web_push_notifications WHERE event_type = %s",
                    (PRESSURE_EVENT_TYPE,),
                )
                cursor.execute("DELETE FROM post_activation_pressure_states")
                cursor.execute(
                    """
                    UPDATE web_push_notification_cutovers
                    SET enabled_at = clock_timestamp() + INTERVAL '1 hour'
                    WHERE event_type = %s
                    """,
                    (PRESSURE_EVENT_TYPE,),
                )

        try:
            self.client.app.state.notification_service.recover()
            self.assertEqual(self.current_pressure_state(), "UP")
            self.assertEqual(self.pressure_notification_count(), 0)
            with transaction(self.database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE web_push_notification_cutovers
                        SET enabled_at = clock_timestamp() - INTERVAL '1 hour'
                        WHERE event_type = %s
                        """,
                        (PRESSURE_EVENT_TYPE,),
                    )
            for index, price in enumerate(("90", "80", "70", "60"), 7):
                self.ingest_spx_without_notification(index, price)
            self.client.app.state.notification_service.recover()
            self.assertEqual(self.current_pressure_state(), "DOWN")
            self.assertEqual(self.pressure_notification_count(), 1)
            self.assertEqual(self.pressure_events()[0]["current_state"], "DOWN")
        finally:
            with transaction(self.database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE web_push_notification_cutovers
                        SET enabled_at = clock_timestamp()
                        WHERE event_type = %s
                        """,
                        (PRESSURE_EVENT_TYPE,),
                    )

    def test_activation_creates_one_logical_notification_across_retry_and_replay(self) -> None:
        self.activate()
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM web_push_notifications"), 1)

        duplicate = self.client.post(
            "/webhook/tradingview",
            json=webhook_payload(4, "110.6"),
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["duplicate"])
        self.client.post(
            "/webhook/tradingview",
            json=webhook_payload(5, "110.3"),
        )

        self.assertEqual(self.scalar("SELECT COUNT(*) FROM web_push_notifications"), 1)
        self.assertEqual(
            self.scalar("SELECT source_event_key FROM web_push_notifications"),
            "SPXUSDT:1:MRZ_ACTIVATED:api-event-4",
        )

    def test_active_subscription_receives_one_delivery_attempt(self) -> None:
        subscribed = self.client.post(
            "/api/notifications/subscriptions",
            json=SUBSCRIPTION,
        )
        self.assertEqual(subscribed.status_code, 201)
        self.activate()

        self.assertEqual(len(self.sender.calls), 1)
        self.assertEqual(
            self.scalar("SELECT outcome FROM web_push_delivery_attempts"),
            "DELIVERED",
        )
        payload = self.sender.calls[0]["data"]
        self.assertIn('"event_type":"MRZ_ACTIVATED"', payload)
        self.assertIn('"url":"/?symbol=SPXUSDT"', payload)
        self.assertNotIn(PRIVATE_KEY, payload)

        site_events = self.client.get("/api/notifications/events?after=0")
        self.assertEqual(site_events.status_code, 200)
        self.assertIn("no-store", site_events.headers["cache-control"])
        self.assertEqual(len(site_events.json()["events"]), 1)
        self.assertEqual(
            site_events.json()["events"][0]["event_type"],
            "MRZ_ACTIVATED",
        )
        self.assertEqual(
            site_events.json()["events"][0]["url"],
            "/?symbol=SPXUSDT",
        )

        duplicate = self.client.post(
            "/webhook/tradingview",
            json=webhook_payload(4, "110.6"),
        )
        self.assertEqual(duplicate.status_code, 200)
        self.client.app.state.notification_service.recover()
        self.assertEqual(len(self.sender.calls), 1)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM web_push_delivery_attempts"),
            1,
        )
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM web_push_notifications"), 1)

    def test_404_and_410_disable_subscription_and_are_not_retried(self) -> None:
        for status in (404, 410):
            with self.subTest(status=status):
                clean(self.database_url)
                self.sender.calls.clear()
                self.sender.outcomes.clear()
                self.sender.failure_status = status
                self.client.post("/api/notifications/subscriptions", json=SUBSCRIPTION)
                self.activate()
                active_before = self.active_mrz_signature()

                self.client.app.state.notification_service.recover()
                self.client.post(
                    "/webhook/tradingview",
                    json=webhook_payload(4, "110.6"),
                )

                self.assertEqual(len(self.sender.calls), 1)
                self.assertEqual(self.scalar("SELECT COUNT(*) FROM active_mrz"), 1)
                self.assertEqual(self.active_mrz_signature(), active_before)
                self.assertEqual(
                    self.scalar("SELECT COUNT(*) FROM web_push_notifications"),
                    1,
                )
                self.assertEqual(
                    self.scalar("SELECT COUNT(*) FROM web_push_delivery_attempts"),
                    1,
                )
                self.assertFalse(
                    self.scalar("SELECT enabled FROM web_push_subscriptions")
                )
                self.assertEqual(
                    self.scalar(
                        "SELECT disabled_reason FROM web_push_subscriptions"
                    ),
                    "expired",
                )
                self.assertFalse(
                    self.scalar(
                        "SELECT retryable FROM web_push_delivery_attempts"
                    )
                )

                expired = self.client.post(
                    "/api/notifications/subscriptions",
                    json=SUBSCRIPTION,
                )
                self.assertEqual(expired.status_code, 410)
                renewed = {
                    **SUBSCRIPTION,
                    "keys": {"p256dh": "C" * 87, "auth": "D" * 22},
                }
                self.assertEqual(
                    self.client.post(
                        "/api/notifications/subscriptions",
                        json=renewed,
                    ).status_code,
                    201,
                )
        self.sender.failure_status = None

    def test_transient_failure_retries_and_succeeds_without_new_logical_event(self) -> None:
        self.sender.outcomes = [503, None]
        self.client.post("/api/notifications/subscriptions", json=SUBSCRIPTION)
        self.activate()
        active_before = self.active_mrz_signature()

        self.assertEqual(len(self.sender.calls), 1)
        self.assertTrue(
            self.scalar("SELECT retryable FROM web_push_delivery_attempts")
        )
        self.client.app.state.notification_service.recover()

        self.assertEqual(len(self.sender.calls), 2)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM web_push_notifications"), 1)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM web_push_delivery_attempts"),
            2,
        )
        self.assertEqual(
            self.scalar(
                """
                SELECT STRING_AGG(
                    attempt_number::text || ':' || outcome || ':' || retryable::text,
                    ',' ORDER BY attempt_number
                )
                FROM web_push_delivery_attempts
                """
            ),
            "1:FAILED:true,2:DELIVERED:false",
        )
        self.assertEqual(self.active_mrz_signature(), active_before)

        self.client.post(
            "/webhook/tradingview",
            json=webhook_payload(4, "110.6"),
        )
        self.client.app.state.notification_service.recover()
        self.assertEqual(len(self.sender.calls), 2)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM web_push_notifications"), 1)
        self.assertEqual(self.active_mrz_signature(), active_before)

    def test_near_miss_uses_existing_retry_outbox_and_exact_deep_link(self) -> None:
        self.sender.outcomes = [503, None]
        self.client.post("/api/notifications/subscriptions", json=SUBSCRIPTION)
        for index, price in enumerate(("941.52", "941.52", "941.52", "949.89"), 1):
            response = self.post_mu_near_miss_observation(index, price)
            self.assertEqual(response.status_code, 201)

        self.assertEqual(len(self.sender.calls), 1)
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications "
                "WHERE event_type = 'MRZ_NEAR_MISS'"
            ),
            1,
        )
        self.assertTrue(
            self.scalar(
                "SELECT retryable FROM web_push_delivery_attempts "
                "WHERE outcome = 'FAILED'"
            )
        )
        first_payload = json.loads(self.sender.calls[0]["data"])
        self.assertEqual(first_payload["event_type"], "MRZ_NEAR_MISS")
        self.assertEqual(first_payload["symbol"], "MU")
        self.assertEqual(first_payload["route_owner"], "STR")
        self.assertEqual(first_payload["candidate_lower"], "941.52")
        self.assertEqual(first_payload["candidate_upper"], "949.89")
        self.assertEqual(first_payload["minimum_required_allowance_pct"], "1.02")
        self.assertEqual(first_payload["production_threshold_pct"], "1")
        self.assertEqual(first_payload["supporting_observation_count"], 4)
        self.assertEqual(len(first_payload["candidate_identity"]), 64)
        self.assertEqual(
            first_payload["url"],
            "/diagnostics/activation-feasibility?symbol=MU&candidate="
            f"{first_payload['candidate_identity']}#current-production-near-misses",
        )

        self.client.app.state.notification_service.recover()
        self.assertEqual(len(self.sender.calls), 2)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM web_push_delivery_attempts"),
            2,
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM web_push_notifications"),
            1,
        )
        self.assertEqual(
            json.loads(self.sender.calls[1]["data"])["source_event_key"],
            first_payload["source_event_key"],
        )

    def test_transient_exceptions_are_bounded_to_three_attempts(self) -> None:
        self.sender.outcomes = [
            TimeoutError("simulated timeout one"),
            ConnectionError("simulated connection failure"),
            TimeoutError("simulated timeout three"),
            None,
        ]
        self.client.post("/api/notifications/subscriptions", json=SUBSCRIPTION)
        self.activate()
        active_before = self.active_mrz_signature()

        for _ in range(3):
            self.client.post(
                "/webhook/tradingview",
                json=webhook_payload(4, "110.6"),
            )
        self.client.app.state.notification_service.recover()

        self.assertEqual(len(self.sender.calls), 3)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM web_push_delivery_attempts"),
            3,
        )
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_delivery_attempts WHERE retryable = TRUE"
            ),
            3,
        )
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM web_push_notifications"), 1)
        self.assertEqual(self.active_mrz_signature(), active_before)

    def test_retryable_provider_status_classification(self) -> None:
        for status in (None, 408, 425, 429, 500, 503, 599):
            self.assertTrue(is_retryable_push_failure(status), status)
        for status in (400, 401, 403, 404, 410, 422):
            self.assertFalse(is_retryable_push_failure(status), status)

    def test_same_route_migration_uses_authoritative_provenance_and_timestamp(self) -> None:
        self.client.post("/api/notifications/subscriptions", json=SUBSCRIPTION)
        self.activate_btc()
        self.post_btc_cluster(
            5,
            ("78919.34", "78950", "79000", "79030"),
        )

        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications WHERE event_type IN "
                "('MRZ_ACTIVATED', 'MRZ_MIGRATED')"
            ),
            2,
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM mrz_events WHERE event_type = 'MRZ_MIGRATED'"),
            1,
        )
        self.assertEqual(len(self.sender.calls), 3)
        delivered_payloads = [json.loads(call["data"]) for call in self.sender.calls]
        activated_payload = next(
            item for item in delivered_payloads if item["event_type"] == "MRZ_ACTIVATED"
        )
        migrated_payload = next(
            item for item in delivered_payloads if item["event_type"] == "MRZ_MIGRATED"
        )

        self.assertEqual(activated_payload["title"], "BTCUSDT MRZ Activated")
        self.assertEqual(activated_payload["body"], "BTD · 77,309.19–77,436.91")
        self.assertEqual(migrated_payload["event_type"], "MRZ_MIGRATED")
        self.assertEqual(migrated_payload["title"], "BTCUSDT MRZ Migrated")
        self.assertEqual(
            migrated_payload["body"],
            "BTD · 77,309.19–77,436.91 → 78,919.34–79,030",
        )
        self.assertEqual(migrated_payload["previous_route_owner"], "BTD")
        self.assertEqual(migrated_payload["route_owner"], "BTD")
        self.assertEqual(migrated_payload["previous_mrz_lower"], "77309.19")
        self.assertEqual(migrated_payload["previous_mrz_upper"], "77436.91")
        self.assertEqual(migrated_payload["mrz_lower"], "78919.34")
        self.assertEqual(migrated_payload["mrz_upper"], "79030")
        self.assertEqual(migrated_payload["occurred_at"], "2026-08-20T12:00:08Z")
        self.assertEqual(migrated_payload["migrated_at"], migrated_payload["occurred_at"])
        self.assertEqual(migrated_payload["event_sequence"], 2)
        self.assertEqual(
            migrated_payload["source_event_key"],
            "BTCUSDT:2:MRZ_MIGRATED:btc-event-8",
        )

        # Notification provenance is copied from the persisted migration event,
        # not inferred later from mutable active_mrz presentation state.
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE active_mrz
                    SET core_mrz_lower = 88000, core_mrz_upper = 88100,
                        core_mrz_midpoint = 88050
                    WHERE symbol = 'BTCUSDT'
                    """
                )
            connection.commit()
        finally:
            connection.close()
        site_events = self.client.get("/api/notifications/events?after=0").json()["events"]
        site_migration = next(
            event for event in site_events if event["event_type"] == "MRZ_MIGRATED"
        )
        self.assertEqual(site_migration["previous_mrz_lower"], "77309.19")
        self.assertEqual(site_migration["mrz_lower"], "78919.34")

    def test_route_changing_migration_creates_one_migration_notification_only(self) -> None:
        self.activate_btc()
        self.post_btc_cluster(
            5,
            ("82040.41", "82100", "82150", "82226.01"),
            route="STR",
        )

        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM mrz_events WHERE event_type = 'MRZ_MIGRATED'"),
            1,
        )
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM mrz_events WHERE event_type = 'ROUTE_CHANGED'"),
            1,
        )
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications WHERE event_type IN "
                "('MRZ_ACTIVATED', 'MRZ_MIGRATED')"
            ),
            2,
        )
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications WHERE event_type = 'ROUTE_CHANGED'"
            ),
            0,
        )
        events = self.client.get("/api/notifications/events?after=0").json()["events"]
        migration = next(event for event in events if event["event_type"] == "MRZ_MIGRATED")
        self.assertEqual(
            migration["body"],
            "BTD → STR · 77,309.19–77,436.91 → 82,040.41–82,226.01",
        )

    def test_duplicate_migration_processing_keeps_one_logical_notification(self) -> None:
        self.activate_btc()
        self.post_btc_cluster(
            5,
            ("78919.34", "78950", "79000", "79030"),
        )
        migration_key = self.scalar(
            "SELECT source_event_key FROM web_push_notifications WHERE event_type = 'MRZ_MIGRATED'"
        )

        duplicate = self.post_btc_observation(8, "79030")
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.json()["duplicate"])
        self.client.app.state.notification_service.recover()

        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications WHERE event_type IN "
                "('MRZ_ACTIVATED', 'MRZ_MIGRATED')"
            ),
            2,
        )
        self.assertEqual(
            self.scalar(
                "SELECT source_event_key FROM web_push_notifications WHERE event_type = 'MRZ_MIGRATED'"
            ),
            migration_key,
        )

    def test_distinct_migration_chain_creates_three_distinct_notifications(self) -> None:
        self.activate_btc()
        self.post_btc_cluster(
            5,
            ("78919.34", "78950", "79000", "79030"),
        )
        self.post_btc_cluster(
            9,
            ("78040.41", "78100", "78150", "78226.01"),
        )
        self.post_btc_cluster(
            13,
            ("78850.69", "78900", "78950", "79030"),
        )

        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications WHERE event_type IN "
                "('MRZ_ACTIVATED', 'MRZ_MIGRATED')"
            ),
            4,
        )
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications WHERE event_type = 'MRZ_ACTIVATED'"
            ),
            1,
        )
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications WHERE event_type = 'MRZ_MIGRATED'"
            ),
            3,
        )
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(DISTINCT source_event_key) FROM web_push_notifications "
                "WHERE event_type IN ('MRZ_ACTIVATED', 'MRZ_MIGRATED')"
            ),
            4,
        )
        bodies = [
            event["body"]
            for event in self.client.get("/api/notifications/events?after=0").json()["events"]
            if event["event_type"] == "MRZ_MIGRATED"
        ]
        self.assertEqual(
            bodies,
            [
                "BTD · 77,309.19–77,436.91 → 78,919.34–79,030",
                "BTD · 78,919.34–79,030 → 78,040.41–78,226.01",
                "BTD · 78,040.41–78,226.01 → 78,850.69–79,030",
            ],
        )

    def test_historical_migration_replay_is_not_made_deliverable(self) -> None:
        self.activate_btc()
        self.post_btc_cluster(
            5,
            ("78919.34", "78950", "79000", "79030"),
        )
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE observations
                    SET received_at = (
                        SELECT enabled_at - INTERVAL '1 second'
                        FROM web_push_notification_cutovers
                        WHERE event_type = 'MRZ_MIGRATED'
                    )
                    WHERE event_id = 'btc-event-8'
                    """
                )
                cursor.execute(
                    """
                    DELETE FROM web_push_notifications
                    WHERE event_type = 'MRZ_MIGRATED'
                    """
                )
            connection.commit()
        finally:
            connection.close()

        self.client.app.state.notification_service.recover()

        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM mrz_events WHERE event_type = 'MRZ_MIGRATED'"),
            1,
        )
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications WHERE event_type = 'MRZ_MIGRATED'"
            ),
            0,
        )

    def test_config_exposes_only_public_vapid_material(self) -> None:
        response = self.client.get("/api/notifications/config")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["vapid_public_key"], PUBLIC_KEY)
        self.assertNotIn("private", response.text.lower())
        self.assertNotIn(PRIVATE_KEY, response.text)

    def test_manifest_and_root_scoped_service_worker_are_served_safely(self) -> None:
        manifest = self.client.get("/manifest.webmanifest")
        self.assertEqual(manifest.status_code, 200)
        self.assertTrue(
            manifest.headers["content-type"].startswith("application/manifest+json")
        )
        self.assertEqual(manifest.json()["scope"], "/")
        self.assertEqual(manifest.json()["display"], "standalone")

        worker = self.client.get("/service-worker.js")
        self.assertEqual(worker.status_code, 200)
        self.assertTrue(
            worker.headers["content-type"].startswith("application/javascript")
        )
        self.assertEqual(worker.headers["service-worker-allowed"], "/")
        self.assertIn("no-store", worker.headers["cache-control"])
        self.assertNotIn(PRIVATE_KEY, worker.text)

        root = self.client.get("/")
        self.assertEqual(root.status_code, 200)
        self.assertIn('href="/manifest.webmanifest"', root.text)
        self.assertIn('href="/static/edge-mrz-icon-180.png"', root.text)
        for icon_path, expected_type in (
            ("/static/edge-mrz-icon-180.png", "image/png"),
            ("/static/edge-mrz-icon-192.png", "image/png"),
            ("/static/edge-mrz-icon-512.png", "image/png"),
            ("/static/edge-mrz-icon.svg", "image/svg+xml"),
        ):
            icon = self.client.get(icon_path)
            self.assertEqual(icon.status_code, 200, icon_path)
            self.assertTrue(
                icon.headers["content-type"].startswith(expected_type),
                icon_path,
            )

    def test_operator_can_disable_a_subscription(self) -> None:
        self.assertEqual(
            self.client.post(
                "/api/notifications/subscriptions",
                json=SUBSCRIPTION,
            ).status_code,
            201,
        )
        disabled = self.client.request(
            "DELETE",
            "/api/notifications/subscriptions",
            json={"endpoint": SUBSCRIPTION["endpoint"]},
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertFalse(self.scalar("SELECT enabled FROM web_push_subscriptions"))
        self.assertEqual(
            self.scalar("SELECT disabled_reason FROM web_push_subscriptions"),
            "operator",
        )

    def test_subscription_endpoint_rejects_malformed_payload(self) -> None:
        response = self.client.post(
            "/api/notifications/subscriptions",
            json={
                "endpoint": "http://push.example.test/not-secure",
                "keys": {"p256dh": "short", "auth": "short"},
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM web_push_subscriptions"), 0)


if __name__ == "__main__":
    unittest.main()
