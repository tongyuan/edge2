from __future__ import annotations

import unittest

from fastapi.testclient import TestClient
from pywebpush import WebPushException

from app.api import create_app
from app.config import Settings
from app.db import connect
from app.notifications import is_retryable_push_failure
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

    def test_migration_does_not_create_a_v1_notification(self) -> None:
        self.activate()
        for index, price in enumerate(("120", "120.2", "120.4", "120.6"), 5):
            self.client.post(
                "/webhook/tradingview",
                json=webhook_payload(index, price),
            )

        self.assertEqual(self.scalar("SELECT COUNT(*) FROM web_push_notifications"), 1)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM mrz_events WHERE event_type = 'MRZ_MIGRATED'"),
            1,
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
