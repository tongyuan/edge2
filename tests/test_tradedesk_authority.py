from __future__ import annotations

import unittest
from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from psycopg2 import sql

from app.api import create_app
from app.config import Settings
from app.db import connect
from app.validation import normalize_symbol
from tests.db_support import clean, migrate_and_clean, require_test_database


def webhook_payload(
    symbol: str,
    index: int,
    price: Decimal,
    *,
    route: str = "BTD",
) -> dict[str, str]:
    canonical_symbol = normalize_symbol(symbol)
    return {
        "schema_version": "4.3",
        "event_id": f"tradedesk-{canonical_symbol}-{index}",
        "symbol": symbol,
        "route": route,
        "observation_type": "reclaim" if route == "BTD" else "rejection",
        "observation_price": format(price, "f"),
        "ipda_20w_high": "200",
        "ipda_20w_low": "100",
        "observed_at": f"2026-09-28T10:00:{index:02d}Z",
        "webhook_secret": "test-webhook-secret",
    }


class TradeDeskAuthorityApiTests(unittest.TestCase):
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

    def ingest_cluster(
        self,
        symbol: str,
        lower: str,
        *,
        starting_index: int = 1,
        route: str = "BTD",
    ) -> None:
        lower_decimal = Decimal(lower)
        for offset, increment in enumerate(("0", "0.2", "0.4", "0.6")):
            index = starting_index + offset
            response = self.client.post(
                "/webhook/tradingview",
                json=webhook_payload(
                    symbol,
                    index,
                    lower_decimal + Decimal(increment),
                    route=route,
                ),
            )
            self.assertEqual(response.status_code, 201)

    def database_signature(self) -> tuple[tuple[str, int, str], ...]:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                    ORDER BY table_name ASC
                    """
                )
                tables = [str(row[0]) for row in cursor.fetchall()]
                signatures = []
                for table in tables:
                    cursor.execute(
                        sql.SQL(
                            """
                            SELECT
                                COUNT(*),
                                COALESCE(
                                    md5(string_agg(
                                        to_jsonb(snapshot)::text,
                                        E'\\n'
                                        ORDER BY to_jsonb(snapshot)::text
                                    )),
                                    md5('')
                                )
                            FROM {} snapshot
                            """
                        ).format(sql.Identifier(table))
                    )
                    count, digest = cursor.fetchone()
                    signatures.append((table, int(count), str(digest)))
                return tuple(signatures)
        finally:
            connection.close()

    def test_authoritative_symbol_without_previous_mrz(self) -> None:
        self.ingest_cluster("nasdaq:spxusdt", "110")

        response = self.client.get("/api/tradedesk-authority")
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")
        self.assertEqual(set(payload), {"schema_version", "generated_at", "symbols"})
        self.assertEqual(payload["schema_version"], 1)
        generated_at = datetime.fromisoformat(payload["generated_at"].replace("Z", "+00:00"))
        self.assertIsNotNone(generated_at.utcoffset())
        self.assertTrue(payload["generated_at"].endswith("Z"))
        self.assertEqual(
            payload["symbols"],
            [
                {
                    "symbol": "SPXUSDT",
                    "current_mrz": {
                        "lower": "110",
                        "upper": "110.6",
                        "activated_at": "2026-09-28T10:00:04Z",
                        "activation_event_id": "tradedesk-SPXUSDT-4",
                    },
                    "previous_mrz": None,
                }
            ],
        )
        self.assertEqual(
            set(payload["symbols"][0]),
            {"symbol", "current_mrz", "previous_mrz"},
        )
        self.assertEqual(
            set(payload["symbols"][0]["current_mrz"]),
            {"lower", "upper", "activated_at", "activation_event_id"},
        )

    def test_authoritative_symbol_with_current_and_previous_mrz(self) -> None:
        self.ingest_cluster("SPXUSDT", "110")
        self.ingest_cluster(
            "SPXUSDT",
            "180",
            starting_index=5,
            route="STR",
        )

        symbol = self.client.get("/api/tradedesk-authority").json()["symbols"][0]

        self.assertEqual(
            symbol,
            {
                "symbol": "SPXUSDT",
                "current_mrz": {
                    "lower": "180",
                    "upper": "180.6",
                    "activated_at": "2026-09-28T10:00:08Z",
                    "activation_event_id": "tradedesk-SPXUSDT-8",
                },
                "previous_mrz": {
                    "lower": "110",
                    "upper": "110.6",
                    "activated_at": "2026-09-28T10:00:04Z",
                    "activation_event_id": "tradedesk-SPXUSDT-4",
                },
            },
        )

    def test_multiple_symbols_are_deterministic_and_sorted(self) -> None:
        self.ingest_cluster("ZETA", "120")
        self.ingest_cluster("nasdaq:aapl", "110")

        first = self.client.get("/api/tradedesk-authority").json()
        second = self.client.get("/api/tradedesk-authority").json()

        self.assertEqual(
            [item["symbol"] for item in first["symbols"]],
            ["AAPL", "ZETA"],
        )
        first.pop("generated_at")
        second.pop("generated_at")
        self.assertEqual(first, second)

    def test_malformed_or_inconsistent_authority_is_not_emitted(self) -> None:
        for corruption in ("invalid_bounds", "wrong_event"):
            with self.subTest(corruption=corruption):
                clean(self.database_url)
                self.ingest_cluster("SPXUSDT", "110")
                connection = connect(self.database_url)
                try:
                    with connection.cursor() as cursor:
                        if corruption == "invalid_bounds":
                            cursor.execute(
                                """
                                UPDATE active_mrz
                                SET core_mrz_upper = core_mrz_lower,
                                    core_mrz_midpoint = core_mrz_lower
                                WHERE symbol = 'SPXUSDT'
                                """
                            )
                        else:
                            cursor.execute(
                                """
                                UPDATE active_mrz
                                SET activation_event_id = 'tradedesk-SPXUSDT-3'
                                WHERE symbol = 'SPXUSDT'
                                """
                            )
                    connection.commit()
                finally:
                    connection.close()

                response = self.client.get("/api/tradedesk-authority")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(
                    response.json()["detail"]["code"],
                    "authoritative_state_inconsistent",
                )
                self.assertIn("SPXUSDT", response.json()["detail"]["message"])
                self.assertNotIn("symbols", response.json())

    def test_endpoint_is_read_only_for_every_database_table(self) -> None:
        self.ingest_cluster("SPXUSDT", "110")
        self.ingest_cluster("SPXUSDT", "120", starting_index=5)
        before = self.database_signature()

        first = self.client.get("/api/tradedesk-authority")
        second = self.client.get("/api/tradedesk-authority")
        post = self.client.post("/api/tradedesk-authority", json={})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(post.status_code, 405)
        self.assertEqual(
            set(self.client.app.openapi()["paths"]["/api/tradedesk-authority"]),
            {"get"},
        )
        self.assertEqual(self.database_signature(), before)
