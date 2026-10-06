from __future__ import annotations

import unittest

from fastapi.testclient import TestClient
from psycopg2.extras import RealDictCursor
from pydantic import ValidationError

from app.api import create_app
from app.config import Settings
from app.db import connect
from app.validation import TradeDeskLifecyclePayload
from tests.db_support import clean, migrate_and_clean, require_test_database
from tests.test_tradedesk_entry_lifecycle import entry_payload
from tests.test_tradedesk_lifecycle import lifecycle_payload


def frozen_ladder() -> list[dict]:
    return [
        {"level_ids": ["C-MID"], "level_price": 1410, "eligible": False},
        {"level_ids": ["C-2W"], "level_price": 1300, "eligible": False},
        {"level_ids": ["C-1W"], "level_price": 1350, "eligible": False},
        {"level_ids": ["C+1W", "EQM"], "level_price": 1430, "eligible": True, "destination_order": 1},
        {"level_ids": ["P-MID"], "level_price": 1440, "eligible": True, "destination_order": 2},
        {"level_ids": ["C+2W"], "level_price": 1480, "eligible": True, "destination_order": 3},
        {"level_ids": ["P-2W"], "level_price": 1290, "eligible": False},
        {"level_ids": ["P-1W"], "level_price": 1380, "eligible": False},
        {"level_ids": ["P+1W"], "level_price": 1490, "eligible": True, "destination_order": 4},
        {"level_ids": ["P+2W"], "level_price": 1510, "eligible": False},
    ]


def schema12_confirmation(**overrides) -> dict:
    payload = entry_payload(
        "ENTRY_CONFIRMED",
        schema_version="1.2",
        initial_risk=16.42,
        mrz_context_id="ZECUSDT|S|A|C|1|1400|1420|P|0|1380|1400",
        exit_ladder_available=True,
        frozen_exit_ladder=frozen_ladder(),
    )
    payload.update(overrides)
    return payload


def schema12_reach(*, event_at: int = 1790771100000, **overrides) -> dict:
    payload = entry_payload(
        "ENTRY_EXIT_LEVEL_REACHED",
        schema_version="1.2",
        event_id="ZECUSDT-LONG-1790762700000-E1-EXIT-C+1W.EQM",
        event_at=event_at,
        entry_confirmed_at=1790770800000,
        grade_at_confirmation="A+",
        entry_price=1414.31,
        stop_price=1397.89,
        entry_rr=4.79,
        level_ids=["C+1W", "EQM"],
        level_price=1430,
        excursion_r=0.9555,
        contact_mode="RANGE_TOUCH",
    )
    payload.update(overrides)
    return payload


def schema12_terminal(event_type: str, **overrides) -> dict:
    payload = entry_payload(
        event_type,
        schema_version="1.2",
        event_at=1790771400000,
        initial_risk=16.42,
        mfe_pre_terminal_price=1432,
        mfe_pre_terminal_r=1.0779,
        mae_pre_terminal_price=1408,
        mae_pre_terminal_r=0.3843,
        mfe_inclusive_price=1440,
        mfe_inclusive_r=1.5646,
        mae_inclusive_price=1397.89,
        mae_inclusive_r=1,
        best_level_pre_terminal_ids=["C+1W", "EQM"],
        best_level_pre_terminal_price=1430,
        best_level_pre_terminal_r=0.9555,
        best_level_pre_terminal_at=1790771100000,
        terminal_bar_levels_touched=[
            {"level_ids": ["P-MID"], "level_price": 1440}
        ],
    )
    payload.update(overrides)
    return payload


class TradeDeskSchema12ValidationTests(unittest.TestCase):
    def test_schema_10_and_11_remain_accepted(self) -> None:
        self.assertEqual(
            TradeDeskLifecyclePayload.model_validate(lifecycle_payload()).schema_version,
            "1.0",
        )
        self.assertEqual(
            TradeDeskLifecyclePayload.model_validate(entry_payload()).schema_version,
            "1.1",
        )

    def test_schema_12_confirmation_freezes_all_eleven_identities(self) -> None:
        parsed = TradeDeskLifecyclePayload.model_validate(schema12_confirmation())
        self.assertEqual(parsed.schema_version, "1.2")
        self.assertEqual(sum(len(group.level_ids) for group in parsed.frozen_exit_ladder), 11)

    def test_schema_12_can_record_unavailable_mrz(self) -> None:
        parsed = TradeDeskLifecyclePayload.model_validate(
            schema12_confirmation(
                exit_ladder_available=False,
                mrz_context_id=None,
                frozen_exit_ladder=[],
            )
        )
        self.assertFalse(parsed.exit_ladder_available)

    def test_schema_11_cannot_smuggle_schema_12_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            TradeDeskLifecyclePayload.model_validate(
                entry_payload("ENTRY_CONFIRMED", initial_risk=16.42)
            )


class TradeDeskTradeResultPersistenceTests(unittest.TestCase):
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
                    max_request_bytes=65536,
                    log_level="CRITICAL",
                )
            )
        )
        cls.headers = {"X-EDGE2-Webhook-Secret": "test-webhook-secret"}

    def setUp(self) -> None:
        clean(self.database_url)

    def post(self, payload: dict):
        return self.client.post(
            "/api/tradedesk/lifecycle", json=payload, headers=self.headers
        )

    def fetchone(self, query: str, params: tuple = ()):
        connection = connect(self.database_url)
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()
        finally:
            connection.close()

    def execute(self, query: str, params: tuple = ()) -> None:
        connection = connect(self.database_url)
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
            connection.commit()
        finally:
            connection.close()

    def test_confirmation_creates_open_result_with_frozen_ladder(self) -> None:
        self.assertEqual(self.post(schema12_confirmation()).status_code, 200)
        result = self.fetchone("SELECT * FROM tradedesk_trade_results")
        self.assertEqual(result["status"], "OPEN")
        self.assertEqual(result["evidence_version"], "1.2")
        self.assertTrue(result["evidence_complete"])
        self.assertEqual(len(result["frozen_exit_ladder"]), 10)
        self.assertEqual(str(result["initial_risk"]), "16.42")

    def test_missing_mrz_is_explicit_and_not_replaced_by_reach(self) -> None:
        confirmation = schema12_confirmation(
            exit_ladder_available=False,
            mrz_context_id=None,
            frozen_exit_ladder=[],
        )
        self.assertEqual(self.post(confirmation).status_code, 200)
        result = self.fetchone("SELECT * FROM tradedesk_trade_results")
        self.assertIsNone(result["mrz_context_id"])
        self.assertEqual(result["frozen_exit_ladder"], [])

    def test_first_confirmation_freezes_ladder_against_later_context(self) -> None:
        original = schema12_confirmation()
        replacement = schema12_confirmation(
            event_id="ZECUSDT-LONG-1790762700000-E1-ENTRY_CONFIRMED-REPLAY",
            event_at=1790770900000,
            entry_confirmed_at=1790770900000,
            mrz_context_id="later-context-must-not-replace",
        )
        self.assertEqual(self.post(original).status_code, 200)
        self.assertEqual(self.post(replacement).status_code, 200)
        result = self.fetchone("SELECT mrz_context_id,opened_at FROM tradedesk_trade_results")
        self.assertEqual(result["mrz_context_id"], original["mrz_context_id"])
        self.assertEqual(int(result["opened_at"].timestamp() * 1000), 1790770800000)

    def test_first_reach_and_coincident_ids_are_idempotent(self) -> None:
        self.post(schema12_confirmation())
        payload = schema12_reach()
        self.assertEqual(self.post(payload).status_code, 200)
        self.assertEqual(self.post(payload).status_code, 200)
        result = self.fetchone(
            """
            SELECT (SELECT count(*) FROM tradedesk_lifecycle_events
                    WHERE event_type='ENTRY_EXIT_LEVEL_REACHED') AS event_count,
                   reached_levels
            FROM tradedesk_trade_results
            """
        )
        self.assertEqual(result["event_count"], 1)
        self.assertEqual(result["reached_levels"][0]["level_ids"], ["C+1W", "EQM"])
        self.assertEqual(result["reached_levels"][0]["contact_mode"], "RANGE_TOUCH")

    def test_same_frozen_group_cannot_persist_twice_with_another_event_id(self) -> None:
        self.post(schema12_confirmation())
        self.post(schema12_reach())
        self.post(schema12_reach(
            event_id="ZECUSDT-LONG-1790762700000-E1-EXIT-C+1W.EQM-RETRY",
            event_at=1790771200000,
        ))
        result = self.fetchone("SELECT reached_levels FROM tradedesk_trade_results")
        self.assertEqual(len(result["reached_levels"]), 1)

    def test_gap_cross_reach_is_supported(self) -> None:
        self.post(schema12_confirmation())
        self.assertEqual(
            self.post(schema12_reach(
                event_id="ZECUSDT-LONG-1790762700000-E1-EXIT-P-MID",
                level_ids=["P-MID"], level_price=1440, excursion_r=1.5646,
                contact_mode="GAP_CROSS",
            )).status_code,
            200,
        )
        result = self.fetchone("SELECT reached_levels FROM tradedesk_trade_results")
        self.assertEqual(result["reached_levels"][0]["contact_mode"], "GAP_CROSS")

    def test_terminal_status_and_excursion_projection(self) -> None:
        expected = {
            "ENTRY_STOPPED": "LOSS",
            "ENTRY_TARGET_TAKEN": "WIN",
            "ENTRY_AMBIGUOUS": "AMBIGUOUS",
        }
        for event_type, status in expected.items():
            with self.subTest(event_type=event_type):
                clean(self.database_url)
                self.post(schema12_confirmation())
                self.post(schema12_reach())
                self.assertEqual(self.post(schema12_terminal(event_type)).status_code, 200)
                result = self.fetchone("SELECT * FROM tradedesk_trade_results")
                self.assertEqual(result["status"], status)
                self.assertEqual(str(result["mfe_pre_terminal_r"]), "1.0779")
                self.assertEqual(str(result["mfe_inclusive_r"]), "1.5646")
                self.assertEqual(result["terminal_bar_levels_touched"][0]["level_ids"], ["P-MID"])
                self.assertEqual(result["reached_levels"][0]["level_ids"], ["C+1W", "EQM"])

    def test_terminal_bar_level_is_not_promoted_to_preterminal(self) -> None:
        self.post(schema12_confirmation())
        self.post(schema12_terminal("ENTRY_STOPPED"))
        result = self.fetchone(
            "SELECT reached_levels,best_level_pre_terminal_ids,terminal_bar_levels_touched FROM tradedesk_trade_results"
        )
        self.assertEqual(result["reached_levels"], [])
        self.assertEqual(result["best_level_pre_terminal_ids"], ["C+1W", "EQM"])
        self.assertEqual(result["terminal_bar_levels_touched"][0]["level_ids"], ["P-MID"])

    def test_preconfirmation_invalidation_creates_no_trade(self) -> None:
        self.assertEqual(self.post(entry_payload("ENTRY_INVALIDATED")).status_code, 200)
        result = self.fetchone("SELECT count(*) AS count FROM tradedesk_trade_results")
        self.assertEqual(result["count"], 0)

    def test_legacy_confirmation_is_explicitly_incomplete(self) -> None:
        self.assertEqual(self.post(entry_payload("ENTRY_CONFIRMED")).status_code, 200)
        result = self.fetchone("SELECT * FROM tradedesk_trade_results")
        self.assertEqual(result["evidence_version"], "1.1-legacy")
        self.assertFalse(result["evidence_complete"])
        self.assertIsNone(result["mfe_pre_terminal_r"])

    def test_reordered_delivery_converges_and_rebuild_is_exact(self) -> None:
        terminal = schema12_terminal("ENTRY_STOPPED")
        reach = schema12_reach()
        self.assertEqual(self.post(terminal).status_code, 200)
        self.assertEqual(self.post(reach).status_code, 200)
        self.assertEqual(self.post(schema12_confirmation()).status_code, 200)
        before = self.fetchone(
            "SELECT to_jsonb(result) - 'created_at' - 'updated_at' AS value FROM tradedesk_trade_results result"
        )["value"]
        self.client.app.state.repository.rebuild_tradedesk_trade_results()
        after = self.fetchone(
            "SELECT to_jsonb(result) - 'created_at' - 'updated_at' AS value FROM tradedesk_trade_results result"
        )["value"]
        self.assertEqual(after, before)

    def test_pending_mrz_uses_strict_authority_time_boundaries(self) -> None:
        self.post(schema12_confirmation())
        self.post(schema12_terminal("ENTRY_STOPPED"))
        for sequence, occurred_ms in enumerate(
            (1790770800000, 1790771100000, 1790771400000), start=1
        ):
            event_id = f"mrz-result-observation-{sequence}"
            self.execute(
                """
                INSERT INTO observations (
                    event_id, schema_version, symbol, route, observation_type,
                    observation_price, observation_price_tick,
                    ipda_20w_high, ipda_20w_low, observed_at, raw_payload
                ) VALUES (%s, '4.3', 'ZECUSDT', 'BTD', 'reclaim',
                          1400, 0.01, 1600, 1200, to_timestamp(%s / 1000.0), '{}')
                """,
                (event_id, occurred_ms),
            )
            self.execute(
                """
                INSERT INTO mrz_events (
                    event_key, sequence, event_type, symbol, route_owner,
                    occurred_at, trigger_event_id, old_core_mrz_lower,
                    old_core_mrz_upper, new_core_mrz_lower, new_core_mrz_upper,
                    new_core_mrz_midpoint, structural_location,
                    confirming_observation_count, new_supporting_observation_count,
                    activation_source
                ) VALUES (%s, %s, 'MRZ_MIGRATED', 'ZECUSDT', 'BTD',
                          to_timestamp(%s / 1000.0), %s, 1380, 1400,
                          1400, 1420, 1410, 'shallow_discount_core_mrz', 4, 4,
                          'PRODUCTION_QUALIFIED')
                """,
                (f"mrz-result-event-{sequence}", sequence, occurred_ms, event_id),
            )
        self.client.app.state.repository.rebuild_tradedesk_trade_results()
        result = self.fetchone(
            """
            SELECT mrz_migrated_while_open, pending_migration_count,
                   first_pending_migration_at, latest_pending_migration_at
            FROM tradedesk_trade_results
            """
        )
        self.assertTrue(result["mrz_migrated_while_open"])
        self.assertEqual(result["pending_migration_count"], 1)
        self.assertEqual(result["first_pending_migration_at"], result["latest_pending_migration_at"])
        self.assertEqual(
            int(result["first_pending_migration_at"].timestamp() * 1000),
            1790771100000,
        )


if __name__ == "__main__":
    unittest.main()
