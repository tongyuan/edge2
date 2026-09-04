from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from psycopg2.extras import Json

from app.api import create_app
from app.config import Settings
from app.db import connect, transaction
from app.reconciliation import DerivedStateReconciler
from tests.db_support import clean, migrate_and_clean, require_test_database


NEAR_MISS_IPDA_HIGH = "1020.5882352941176470588235294"
NEAR_MISS_PRICES = ("941.52", "941.52", "941.52", "949.89")


class OperatorPromotionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = require_test_database(cls)
        migrate_and_clean(cls.database_url)
        cls.settings = Settings(
            app_env="test",
            database_url=cls.database_url,
            webhook_secret="test-webhook-secret",
            require_webhook_secret=True,
            symbol_ticks={},
            max_request_bytes=32768,
            log_level="CRITICAL",
        )
        cls.client = TestClient(create_app(cls.settings))

    def setUp(self) -> None:
        clean(self.database_url)
        self.base_time = datetime.now(timezone.utc) - timedelta(minutes=10)

    def payload(
        self,
        index: int,
        price: str,
        *,
        event_id: str | None = None,
        low: str = "200",
        high: str = NEAR_MISS_IPDA_HIGH,
        observed_at: datetime | None = None,
    ) -> dict[str, str]:
        timestamp = observed_at or (self.base_time + timedelta(seconds=index))
        return {
            "schema_version": "4.3",
            "event_id": event_id or f"mu-event-{index}",
            "symbol": "MU",
            "route": "STR",
            "observation_type": "rejection",
            "observation_price": price,
            "ipda_20w_high": high,
            "ipda_20w_low": low,
            "observed_at": timestamp.isoformat().replace("+00:00", "Z"),
            "webhook_secret": "test-webhook-secret",
        }

    def post(self, payload: dict[str, str], expected_status: int = 201):
        response = self.client.post("/webhook/tradingview", json=payload)
        self.assertEqual(response.status_code, expected_status, response.text)
        return response

    def seed_near_miss(self) -> dict[str, object]:
        for index, price in enumerate(NEAR_MISS_PRICES, 1):
            self.post(self.payload(index, price))
        report = self.client.get(
            "/api/diagnostics/activation-feasibility"
        ).json()
        current = report["diagnosis"]["current_production_near_misses"]
        self.assertEqual(len(current), 1)
        return current[0]

    def promote(self, candidate: dict[str, object], expected_status: int = 201):
        response = self.client.post(
            "/api/diagnostics/activation-feasibility/near-misses/MU/promote",
            json={
                "route": candidate["route"],
                "candidate_identity": candidate["candidate_identity"],
            },
        )
        self.assertEqual(response.status_code, expected_status, response.text)
        return response

    def rows(self, query: str, parameters: tuple[object, ...] = ()) -> list[tuple]:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, parameters)
                return cursor.fetchall()
        finally:
            connection.close()

    def scalar(self, query: str, parameters: tuple[object, ...] = ()):
        return self.rows(query, parameters)[0][0]

    def test_mu_near_miss_promotion_confirmation_and_genuine_migration(self) -> None:
        candidate = self.seed_near_miss()
        self.assertEqual(candidate["symbol"], "MU")
        self.assertEqual(candidate["route"], "STR")
        self.assertEqual(candidate["candidate_lower_boundary"], "941.52")
        self.assertEqual(candidate["candidate_upper_boundary"], "949.89")
        self.assertEqual(candidate["candidate_midpoint"], "945.705")
        self.assertEqual(Decimal(candidate["minimum_required_allowance_pct"]), Decimal("1.02"))
        self.assertEqual(candidate["configured_allowance_pct"], "1")
        self.assertEqual(candidate["candidate_observation_count"], 4)
        self.assertRegex(candidate["candidate_identity"], r"^[a-f0-9]{64}$")
        self.assertNotIn("supporting_observation_ids", candidate)
        self.assertNotIn("candidate_event_id", candidate)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM active_mrz"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM mrz_events"), 0)

        promoted = self.promote(candidate).json()
        self.assertTrue(promoted["promoted"])
        self.assertFalse(promoted["duplicate"])
        authority = promoted["state"]
        self.assertEqual(authority["activation_source"], "OPERATOR_PROMOTED")
        self.assertEqual(authority["core_mrz_lower"], 941.52)
        self.assertEqual(authority["core_mrz_upper"], 949.89)
        self.assertEqual(authority["core_mrz_midpoint"], 945.705)
        self.assertEqual(
            authority["operator_promotion"]["candidate_identity"],
            candidate["candidate_identity"],
        )
        self.assertEqual(
            authority["operator_promotion"]["minimum_required_allowance_pct"],
            1.02,
        )
        self.assertEqual(authority["operator_promotion"]["production_threshold_pct"], 1.0)
        self.assertIsNone(authority["operator_promotion"]["operator_identity"])
        promoted_at = authority["activated_at"]
        promotion_key = authority["operator_promotion"]["promotion_key"]
        self.assertEqual(
            self.rows(
                "SELECT event_type, activation_source FROM mrz_events ORDER BY sequence"
            ),
            [("MRZ_ACTIVATED", "OPERATOR_PROMOTED")],
        )
        self.assertEqual(
            self.client.get("/api/diagnostics/activation-feasibility").json()[
                "diagnosis"
            ]["current_production_near_misses"],
            [],
        )

        duplicate = self.promote(candidate, expected_status=200).json()
        self.assertTrue(duplicate["duplicate"])
        self.assertFalse(duplicate["promoted"])
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM operator_mrz_promotions"), 1)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM mrz_events WHERE event_type = 'MRZ_ACTIVATED'"),
            1,
        )

        after_promotion = datetime.now(timezone.utc) + timedelta(minutes=1)
        for index, price in enumerate(("930", "932", "934", "935.6"), 5):
            high = "950" if index < 8 else "977.319587628865979381443299"
            self.post(
                self.payload(
                    index,
                    price,
                    low="850" if index < 8 else "400",
                    high=high,
                    observed_at=after_promotion + timedelta(seconds=index),
                )
            )

        confirmed = self.client.get("/api/symbols/MU").json()
        self.assertEqual(confirmed["activation_source"], "OPERATOR_PROMOTED")
        self.assertEqual(confirmed["activated_at"], promoted_at)
        self.assertEqual(confirmed["core_mrz_lower"], 941.52)
        self.assertEqual(confirmed["core_mrz_upper"], 949.89)
        confirmation = confirmed["production_confirmation"]
        self.assertEqual(confirmation["qualified_lower"], 930.0)
        self.assertEqual(confirmation["qualified_upper"], 935.6)
        self.assertEqual(confirmation["qualified_midpoint"], 932.8)
        self.assertEqual(confirmation["minimum_required_allowance_pct"], 0.97)
        self.assertEqual(confirmation["production_threshold_pct"], 1.0)
        self.assertEqual(confirmation["supporting_observation_count"], 4)
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM mrz_events WHERE event_type = 'MRZ_ACTIVATED'"),
            1,
        )

        before_migration_promotion = self.rows(
            """
            SELECT promotion_key, candidate_identity, candidate_lower::text,
                   candidate_upper::text, promoted_at, operator_identity
            FROM operator_mrz_promotions
            """
        )[0]
        migration_time = datetime.now(timezone.utc) + timedelta(minutes=2)
        for index, price in enumerate(("970", "972", "974", "976"), 9):
            self.post(
                self.payload(
                    index,
                    price,
                    low="200",
                    high="1000",
                    observed_at=migration_time + timedelta(seconds=index),
                )
            )

        migrated = self.client.get("/api/symbols/MU").json()
        self.assertEqual(migrated["core_mrz_lower"], 970.0)
        self.assertEqual(migrated["core_mrz_upper"], 976.0)
        self.assertEqual(migrated["activation_source"], "OPERATOR_PROMOTED")
        self.assertTrue(migrated["migration"]["has_migrated"])
        self.assertEqual(migrated["operator_promotion"]["promotion_key"], promotion_key)
        self.assertEqual(migrated["production_confirmation"], confirmation)
        self.assertEqual(
            self.rows(
                "SELECT event_type, activation_source FROM mrz_events ORDER BY sequence"
            ),
            [
                ("MRZ_ACTIVATED", "OPERATOR_PROMOTED"),
                ("MRZ_MIGRATED", "OPERATOR_PROMOTED"),
            ],
        )
        self.assertEqual(
            self.rows(
                """
                SELECT promotion_key, candidate_identity, candidate_lower::text,
                       candidate_upper::text, promoted_at, operator_identity
                FROM operator_mrz_promotions
                """
            )[0],
            before_migration_promotion,
        )
        self.assertEqual(
            DerivedStateReconciler(self.database_url).dry_run(["MU"])["result"],
            "NO CHANGE",
        )

        notifications = self.client.get("/api/notifications/events?after=0").json()["events"]
        self.assertEqual(
            [item["event_type"] for item in notifications],
            ["MRZ_NEAR_MISS", "MRZ_ACTIVATED", "MRZ_MIGRATED"],
        )
        near_miss_notification = notifications[0]
        self.assertEqual(
            near_miss_notification["candidate_identity"],
            candidate["candidate_identity"],
        )
        self.assertEqual(near_miss_notification["minimum_required_allowance_pct"], "1.02")
        self.assertEqual(near_miss_notification["production_threshold_pct"], "1")
        self.assertEqual(near_miss_notification["supporting_observation_count"], 4)
        self.assertEqual(
            near_miss_notification["url"],
            "/diagnostics/activation-feasibility?symbol=MU&candidate="
            f"{candidate['candidate_identity']}#current-production-near-misses",
        )

        with self.assertRaises(Exception):
            with transaction(self.database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE operator_mrz_promotions SET operator_identity = 'changed' "
                        "WHERE symbol = 'MU'"
                    )

    def test_stale_candidate_and_existing_authority_are_server_side_conflicts(self) -> None:
        stale = self.seed_near_miss()
        self.post(self.payload(5, "943.10", low="850", high="950"))
        latest = self.client.get(
            "/api/diagnostics/activation-feasibility"
        ).json()["diagnosis"]["current_production_near_misses"][0]
        self.assertNotEqual(latest["candidate_identity"], stale["candidate_identity"])
        conflict = self.promote(stale, expected_status=409).json()["detail"]
        self.assertEqual(conflict["code"], "candidate_changed")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM active_mrz"), 0)
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM operator_mrz_promotions"), 0)

        clean(self.database_url)
        for index, price in enumerate(NEAR_MISS_PRICES, 1):
            self.post(self.payload(index, price, low="200", high="1100"))
        self.assertEqual(
            self.scalar("SELECT activation_source FROM active_mrz WHERE symbol = 'MU'"),
            "PRODUCTION_QUALIFIED",
        )
        existing = self.client.post(
            "/api/diagnostics/activation-feasibility/near-misses/MU/promote",
            json={"route": "STR", "candidate_identity": "a" * 64},
        )
        self.assertEqual(existing.status_code, 409)
        self.assertEqual(existing.json()["detail"]["code"], "active_mrz_exists")
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM operator_mrz_promotions"), 0)

    def test_near_miss_notification_is_once_per_episode(self) -> None:
        first = self.seed_near_miss()
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications WHERE event_type = 'MRZ_NEAR_MISS'"
            ),
            1,
        )
        continuation = self.payload(5, "943.10", low="850", high="950")
        self.post(continuation)
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications WHERE event_type = 'MRZ_NEAR_MISS'"
            ),
            1,
        )
        duplicate = self.post(continuation, expected_status=200)
        self.assertTrue(duplicate.json()["duplicate"])
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications WHERE event_type = 'MRZ_NEAR_MISS'"
            ),
            1,
        )

        self.post(self.payload(6, "980", low="900", high="1000"))
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM current_production_near_miss_episodes WHERE ended_at IS NOT NULL"),
            1,
        )
        self.post(self.payload(7, "930"))
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications WHERE event_type = 'MRZ_NEAR_MISS'"
            ),
            2,
        )
        identities = [
            row[0]
            for row in self.rows(
                "SELECT candidate_identity FROM web_push_notifications "
                "WHERE event_type = 'MRZ_NEAR_MISS' ORDER BY id"
            )
        ]
        self.assertEqual(identities[0], first["candidate_identity"])
        self.assertNotEqual(identities[0], identities[1])

    def test_preexisting_near_miss_is_baselined_without_replay_push(self) -> None:
        with transaction(self.database_url) as connection:
            with connection.cursor() as cursor:
                for index, price in enumerate(NEAR_MISS_PRICES, 1):
                    payload = self.payload(index, price)
                    raw_payload = {key: value for key, value in payload.items() if key != "webhook_secret"}
                    cursor.execute(
                        """
                        INSERT INTO observations (
                            event_id, schema_version, symbol, route,
                            observation_type, observation_price,
                            observation_price_tick, ipda_20w_high, ipda_20w_low,
                            observed_at, raw_payload
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            payload["event_id"],
                            payload["schema_version"],
                            payload["symbol"],
                            payload["route"],
                            payload["observation_type"],
                            payload["observation_price"],
                            "0.01",
                            payload["ipda_20w_high"],
                            payload["ipda_20w_low"],
                            payload["observed_at"],
                            Json(raw_payload),
                        ),
                    )

        self.post(self.payload(5, "949.89"))
        self.assertEqual(
            self.scalar("SELECT COUNT(*) FROM current_production_near_miss_episodes"),
            1,
        )
        self.assertFalse(
            self.scalar("SELECT deliverable FROM current_production_near_miss_episodes")
        )
        self.assertEqual(
            self.scalar(
                "SELECT COUNT(*) FROM web_push_notifications WHERE event_type = 'MRZ_NEAR_MISS'"
            ),
            0,
        )
        self.client.app.state.notification_service.recover()
        self.assertEqual(self.scalar("SELECT COUNT(*) FROM web_push_notifications"), 0)


if __name__ == "__main__":
    unittest.main()
