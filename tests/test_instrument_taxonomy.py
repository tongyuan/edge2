from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.db import connect, transaction
from app.peer_pressure import (
    build_taxonomy_pressure_report,
    build_universe_pressure_report,
)
from app.repository import EdgeRepository
from app.taxonomy import TaxonomyValidationError, validate_instrument_taxonomy
from app.taxonomy_import import apply_taxonomy_import, plan_taxonomy_import
from app.validation import ObservationPayload
from tests.db_support import clean, migrate_and_clean, require_test_database
from tests.test_peer_pressure import active, observation, symbol_state


BASE_TIME = datetime(2026, 10, 12, 12, 0, tzinfo=timezone.utc)
ROOT_DIR = Path(__file__).resolve().parents[1]
MIGRATION = ROOT_DIR / "migrations" / "018_instrument_taxonomy.sql"


def packet(symbol: str, index: int, price: str = "110") -> ObservationPayload:
    return ObservationPayload.model_validate(
        {
            "schema_version": "4.3",
            "event_id": f"taxonomy-{symbol}-{index}",
            "symbol": symbol,
            "route": "BTD",
            "observation_type": "reclaim",
            "observation_price": price,
            "ipda_20w_high": "200",
            "ipda_20w_low": "100",
            "observed_at": BASE_TIME + timedelta(seconds=index),
        }
    )


class InstrumentTaxonomyValidationTests(unittest.TestCase):
    def test_allowed_asset_classes_and_incomplete_rollout(self) -> None:
        for asset_class in ("EQUITY", "ETF", "INDEX", "CRYPTO", "COMMODITY", "FX"):
            taxonomy = validate_instrument_taxonomy(
                symbol="nasdaq:nvda" if asset_class == "EQUITY" else asset_class,
                asset_class=asset_class,
            )
            self.assertEqual(taxonomy.asset_class, asset_class)
            self.assertEqual(taxonomy.complete, asset_class != "EQUITY")
        placeholder = validate_instrument_taxonomy(symbol="AAPL")
        self.assertIsNone(placeholder.asset_class)
        self.assertFalse(placeholder.complete)

    def test_invalid_asset_class_and_corporate_taxonomy_rules(self) -> None:
        with self.assertRaises(TaxonomyValidationError):
            validate_instrument_taxonomy(symbol="AAPL", asset_class="STOCK")
        with self.assertRaisesRegex(TaxonomyValidationError, "industry requires sector"):
            validate_instrument_taxonomy(
                symbol="AAPL", asset_class="EQUITY", industry="Software"
            )
        with self.assertRaisesRegex(TaxonomyValidationError, "only for EQUITY"):
            validate_instrument_taxonomy(
                symbol="QQQ", asset_class="ETF", sector="Technology"
            )
        with self.assertRaisesRegex(TaxonomyValidationError, "not valid"):
            validate_instrument_taxonomy(
                symbol="JPM",
                asset_class="EQUITY",
                sector="Technology",
                industry="Banks",
            )

    def test_complete_equity_uses_controlled_vocabulary(self) -> None:
        taxonomy = validate_instrument_taxonomy(
            symbol="nvda",
            asset_class="equity",
            sector="Technology",
            industry="Semiconductors",
            require_complete_equity=True,
        )
        self.assertEqual(taxonomy.symbol, "NVDA")
        self.assertTrue(taxonomy.complete)
        dat = validate_instrument_taxonomy(
            symbol="MSTR",
            asset_class="EQUITY",
            sector="Financials",
            industry="Digital Asset Treasury",
            require_complete_equity=True,
        )
        xiaomi = validate_instrument_taxonomy(
            symbol="1810",
            asset_class="EQUITY",
            sector="Technology",
            industry="Consumer Electronics",
            require_complete_equity=True,
        )
        self.assertTrue(dat.complete)
        self.assertTrue(xiaomi.complete)
        with self.assertRaisesRegex(TaxonomyValidationError, "require both"):
            validate_instrument_taxonomy(
                symbol="NVDA",
                asset_class="EQUITY",
                require_complete_equity=True,
            )


class TaxonomyPressureTests(unittest.TestCase):
    def test_complete_equity_groups_reconcile_without_changing_pressure(self) -> None:
        states = (
            symbol_state("UP", "deep_discount"),
            symbol_state("DOWN", "deep_premium"),
            symbol_state("ETF", "shallow_discount"),
        )
        pressure = build_universe_pressure_report(
            states,
            (active("UP"), active("DOWN"), active("ETF")),
            (
                observation("UP", 1, "114"),
                observation("UP", 2, "115"),
                observation("UP", 3, "116"),
                observation("DOWN", 4, "107"),
                observation("DOWN", 5, "106"),
                observation("DOWN", 6, "105"),
            ),
        )
        before = {
            direction: [item["symbol"] for item in pressure["categories"][direction]]
            for direction in ("higher", "neutral", "lower")
        }
        taxonomy = build_taxonomy_pressure_report(
            pressure,
            (
                {
                    "symbol": "UP",
                    "asset_class": "EQUITY",
                    "sector": "Technology",
                    "industry": "Software",
                },
                {
                    "symbol": "DOWN",
                    "asset_class": "EQUITY",
                    "sector": "Financials",
                    "industry": "Banks",
                },
                {"symbol": "ETF", "asset_class": "ETF", "sector": None, "industry": None},
            ),
        )
        self.assertEqual(taxonomy["counts"], {"higher": 1, "neutral": 0, "lower": 1})
        self.assertEqual(taxonomy["included_equity_count"], 2)
        self.assertEqual(taxonomy["excluded_count"], 1)
        self.assertEqual(
            [(group["name"], group["total"]) for group in taxonomy["asset_classes"]],
            [("EQUITY", 2), ("ETF", 1)],
        )
        self.assertEqual(taxonomy["asset_class_included_count"], 3)
        self.assertEqual(taxonomy["asset_class_excluded_count"], 0)
        self.assertEqual(sum(group["total"] for group in taxonomy["sectors"]), 2)
        self.assertEqual(
            [source["symbol"] for source in taxonomy["sources"]["higher"]],
            ["UP"],
        )
        neutral_source = taxonomy["sources"]["neutral"][0]
        self.assertEqual(neutral_source["symbol"], "ETF")
        self.assertEqual(neutral_source["asset_class"], "ETF")
        self.assertIsNone(neutral_source["sector"])
        self.assertIsNone(neutral_source["industry"])
        technology = next(
            group for group in taxonomy["sectors"] if group["name"] == "Technology"
        )
        self.assertEqual(
            technology["counts"],
            {"higher": 1, "lower": 0, "neutral": 0},
        )
        self.assertEqual(
            technology["members"]["higher"][0]["industry"],
            "Software",
        )
        self.assertEqual(
            taxonomy["concentration"]["higher"]["top_sector"],
            "Technology",
        )
        self.assertEqual(
            taxonomy["concentration"]["higher"]["top_sector_share_pct"],
            100.0,
        )
        self.assertEqual(
            before,
            {
                direction: [item["symbol"] for item in pressure["categories"][direction]]
                for direction in ("higher", "neutral", "lower")
            },
        )

    def test_sector_and_industry_constituents_reconcile_and_sort_by_relevance(self) -> None:
        def source(symbol: str, direction: str) -> dict[str, object]:
            return {
                "symbol": symbol,
                "direction": direction,
                "current_location": "deep_premium",
                "current_location_label": "Deep Premium",
                "active_mrz": {"route_owner": "STR"},
                "evidence": {"latest_pressure_observed_at": "2026-10-12T00:00:00Z"},
            }

        pressure = {
            "categories": {
                "higher": [source("NVDA", "higher"), source("MSFT", "higher")],
                "neutral": [source("D05", "neutral"), source("ETF", "neutral")],
                "lower": [source("MSTR", "lower"), source("O39", "lower")],
            }
        }
        instruments = (
            {"symbol": "NVDA", "asset_class": "EQUITY", "sector": "Technology", "industry": "Semiconductors"},
            {"symbol": "MSFT", "asset_class": "EQUITY", "sector": "Technology", "industry": "Software"},
            {"symbol": "D05", "asset_class": "EQUITY", "sector": "Financials", "industry": "Banks"},
            {"symbol": "O39", "asset_class": "EQUITY", "sector": "Financials", "industry": "Banks"},
            {"symbol": "MSTR", "asset_class": "EQUITY", "sector": "Financials", "industry": "Digital Asset Treasury"},
            {"symbol": "ETF", "asset_class": "ETF", "sector": None, "industry": None},
        )
        report = build_taxonomy_pressure_report(pressure, instruments)

        self.assertEqual([group["name"] for group in report["sectors"]], ["Financials", "Technology"])
        self.assertEqual(report["included_equity_count"], 5)
        self.assertEqual(report["excluded_count"], 1)
        self.assertEqual(
            {direction: sum(group["counts"][direction] for group in report["sectors"]) for direction in ("higher", "lower", "neutral")},
            report["counts"],
        )
        financials = next(group for group in report["sectors"] if group["name"] == "Financials")
        financial_industries = [group for group in report["industries"] if group["sector"] == "Financials"]
        self.assertEqual(
            {direction: sum(group["counts"][direction] for group in financial_industries) for direction in ("higher", "lower", "neutral")},
            financials["counts"],
        )
        dat = next(group for group in report["industries"] if group["name"] == "Digital Asset Treasury")
        self.assertEqual(dat["symbols"]["lower"], ["MSTR"])
        banks = next(group for group in report["industries"] if group["name"] == "Banks")
        self.assertEqual(banks["symbols"]["neutral"], ["D05"])
        self.assertEqual(banks["symbols"]["lower"], ["O39"])
        all_sector_symbols = [symbol for group in report["sectors"] for symbols in group["symbols"].values() for symbol in symbols]
        self.assertEqual(len(all_sector_symbols), len(set(all_sector_symbols)))
        self.assertIsNone(report["sources"]["neutral"][-1]["sector"])
        self.assertIsNone(report["sources"]["neutral"][-1]["industry"])

    def test_asset_class_groups_reconcile_every_pressure_member_without_duplicates(self) -> None:
        classes = ("EQUITY", "ETF", "INDEX", "CRYPTO", "COMMODITY", "FX")
        directions = ("higher", "neutral", "lower", "neutral", "higher", "lower")
        categories = {direction: [] for direction in ("higher", "neutral", "lower")}
        instruments = []
        for asset_class, direction in zip(classes, directions, strict=True):
            symbol = f"{asset_class}_ONE"
            categories[direction].append({
                "symbol": symbol,
                "direction": direction,
                "current_location": "deep_discount",
                "current_location_label": "Deep Discount",
                "active_mrz": {"route_owner": "BTD"},
                "evidence": {"latest_pressure_observed_at": "2026-10-12T00:00:00Z"},
            })
            instruments.append({
                "symbol": symbol,
                "asset_class": asset_class,
                "sector": "Technology" if asset_class == "EQUITY" else None,
                "industry": "Software" if asset_class == "EQUITY" else None,
            })

        report = build_taxonomy_pressure_report(
            {"categories": categories}, instruments
        )
        self.assertEqual(
            [group["name"] for group in report["asset_classes"]],
            list(classes),
        )
        self.assertEqual(
            sum(group["total"] for group in report["asset_classes"]), 6
        )
        self.assertEqual(report["asset_class_included_count"], 6)
        self.assertEqual(report["asset_class_excluded_count"], 0)
        asset_symbols = [
            symbol
            for group in report["asset_classes"]
            for symbols in group["symbols"].values()
            for symbol in symbols
        ]
        self.assertEqual(len(asset_symbols), len(set(asset_symbols)))
        for group in report["asset_classes"]:
            self.assertEqual(sum(group["counts"].values()), group["total"])
        self.assertEqual(report["included_equity_count"], 1)
        self.assertEqual(sum(group["total"] for group in report["sectors"]), 1)
        for source in (
            item
            for direction in report["sources"].values()
            for item in direction
            if item["asset_class"] != "EQUITY"
        ):
            self.assertIsNone(source["sector"])
            self.assertIsNone(source["industry"])

    def test_latest_directional_event_is_independent_of_current_pressure(self) -> None:
        def state(symbol: str, direction: str) -> dict[str, object]:
            return {
                "symbol": symbol,
                "direction": direction,
                "current_location": "deep_premium",
                "current_location_label": "Deep Premium",
                "active_mrz": {"route_owner": "STR"},
                "evidence": {"latest_pressure_observed_at": "2026-10-13T01:00:00Z"},
            }

        pressure = {
            "categories": {
                "higher": [state("CURRENT_HIGH", "higher")],
                "neutral": [
                    state("NEUTRAL_AFTER_HIGH", "neutral"),
                    state("NEUTRAL_AFTER_LOW", "neutral"),
                    state("NEVER_DIRECTIONAL", "neutral"),
                ],
                "lower": [state("CURRENT_LOW", "lower")],
            }
        }
        instruments = [
            {"symbol": symbol, "asset_class": "CRYPTO", "sector": None, "industry": None}
            for symbol in (
                "CURRENT_HIGH", "NEUTRAL_AFTER_HIGH", "NEUTRAL_AFTER_LOW",
                "NEVER_DIRECTIONAL", "CURRENT_LOW",
            )
        ]
        events = (
            {"symbol": "NEUTRAL_AFTER_HIGH", "current_state": "UP", "occurred_at": "2026-10-12T10:00:00Z", "event_id": "up-1"},
            {"symbol": "NEUTRAL_AFTER_LOW", "current_state": "DOWN", "occurred_at": "2026-10-12T11:00:00Z", "event_id": "down-1"},
            {"symbol": "CURRENT_LOW", "current_state": "DOWN", "occurred_at": "2026-10-12T12:00:00Z", "event_id": "down-2"},
            {"symbol": "CURRENT_HIGH", "current_state": "UP", "occurred_at": "2026-10-12T13:00:00Z", "event_id": "up-2"},
        )

        report = build_taxonomy_pressure_report(pressure, instruments, events)
        sources = {
            item["symbol"]: item
            for members in report["sources"].values()
            for item in members
        }
        self.assertEqual(sources["NEUTRAL_AFTER_HIGH"]["direction"], "neutral")
        self.assertEqual(
            sources["NEUTRAL_AFTER_HIGH"]["latest_directional_pressure"],
            {"direction": "higher", "occurred_at": "2026-10-12T10:00:00Z", "event_id": "up-1"},
        )
        self.assertEqual(sources["NEUTRAL_AFTER_LOW"]["direction"], "neutral")
        self.assertEqual(sources["NEUTRAL_AFTER_LOW"]["latest_directional_pressure"]["direction"], "lower")
        self.assertEqual(sources["CURRENT_LOW"]["direction"], "lower")
        self.assertEqual(sources["CURRENT_LOW"]["latest_directional_pressure"]["direction"], "lower")
        self.assertEqual(sources["CURRENT_HIGH"]["direction"], "higher")
        self.assertEqual(sources["CURRENT_HIGH"]["latest_directional_pressure"]["direction"], "higher")
        self.assertIsNone(sources["NEVER_DIRECTIONAL"]["latest_directional_pressure"])
        self.assertEqual(
            sources["NEUTRAL_AFTER_HIGH"]["latest_directional_pressure"]["occurred_at"],
            events[0]["occurred_at"],
            "the displayed timestamp belongs to the same canonical event as its direction",
        )


class InstrumentTaxonomyIntegrationTests(unittest.TestCase):
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

    def setUp(self) -> None:
        clean(self.database_url)
        self.repository = EdgeRepository(self.database_url)

    def ingest(self, symbol: str, index: int, price: str = "110") -> None:
        self.repository.ingest(packet(symbol, index, price), Decimal("0.01"))

    def csv_file(self, body: str) -> tempfile.NamedTemporaryFile:
        stream = tempfile.NamedTemporaryFile(mode="w+", suffix=".csv", encoding="utf-8")
        stream.write("symbol,asset_class,sector,industry\n")
        stream.write(body)
        stream.flush()
        return stream

    def test_first_observation_registration_and_duplicate_safety(self) -> None:
        payload = packet("nasdaq:nvda", 1)
        first = self.repository.ingest(payload, Decimal("0.01"))
        duplicate = self.repository.ingest(payload, Decimal("0.01"))
        self.assertTrue(first.accepted)
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(
            self.repository.get_instrument_taxonomy("NVDA"),
            {
                "symbol": "NVDA",
                "asset_class": None,
                "sector": None,
                "industry": None,
                "taxonomy_complete": False,
                "created_at": self.repository.get_instrument_taxonomy("NVDA")["created_at"],
                "updated_at": self.repository.get_instrument_taxonomy("NVDA")["updated_at"],
            },
        )
        self.assertEqual(len(self.repository.list_instrument_taxonomy()), 1)
        self.assertEqual(self.repository.count_incomplete_taxonomy_records(), 1)

    def test_migration_is_idempotent_preserves_observations_and_backfills(self) -> None:
        for index, symbol in enumerate(("AAPL", "QQQ", "BTCUSDT"), 1):
            self.ingest(symbol, index)
        with transaction(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM instruments")
                cursor.execute("SELECT COUNT(*), MIN(event_id), MAX(event_id) FROM observations")
                before = cursor.fetchone()
                sql = MIGRATION.read_text(encoding="utf-8")
                cursor.execute(sql)
                cursor.execute(sql)
                cursor.execute("SELECT COUNT(*), MIN(event_id), MAX(event_id) FROM observations")
                after = cursor.fetchone()
                cursor.execute("SELECT COUNT(*) FROM instruments")
                placeholders = cursor.fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(placeholders, 3)
        self.assertEqual(self.repository.count_incomplete_taxonomy_records(), 3)

    def test_taxonomy_edit_preserves_mrz_and_watchlist_state_and_serializes(self) -> None:
        for index, price in enumerate(("110", "110.2", "110.4", "110.6"), 1):
            self.ingest("NVDA", index, price)
        group = self.repository.create_saved_group("Operator list", ["NVDA"])
        before_detail = self.repository.symbol_detail("NVDA")
        before_events = self.repository.audit_events("NVDA")
        before_group = self.repository.saved_group_report(group["id"])

        updated = self.repository.update_instrument_taxonomy(
            "NVDA",
            asset_class="EQUITY",
            sector="Technology",
            industry="Semiconductors",
        )
        self.assertTrue(updated["taxonomy_complete"])
        after_detail = self.repository.symbol_detail("NVDA")
        self.assertEqual(after_detail["asset_class"], "EQUITY")
        self.assertEqual(after_detail["sector"], "Technology")
        self.assertEqual(after_detail["industry"], "Semiconductors")
        self.assertTrue(after_detail["taxonomy_complete"])
        self.assertEqual(after_detail["core_mrz_lower"], before_detail["core_mrz_lower"])
        self.assertEqual(after_detail["core_mrz_upper"], before_detail["core_mrz_upper"])
        self.assertEqual(self.repository.audit_events("NVDA"), before_events)
        self.assertEqual(self.repository.saved_group_report(group["id"]), before_group)

        client = TestClient(create_app(self.settings))
        collection = client.get("/api/symbols").json()
        self.assertEqual(collection["incomplete_taxonomy_count"], 0)
        self.assertEqual(collection["symbols"][0]["asset_class"], "EQUITY")
        self.assertEqual(client.get("/api/symbols/NVDA").json()["industry"], "Semiconductors")

    def test_csv_dry_run_apply_idempotency_unknowns_and_transactional_rejection(self) -> None:
        self.ingest("AAPL", 1)
        self.ingest("MSFT", 2)
        valid = self.csv_file(
            'AAPL,EQUITY,Technology,"Technology Hardware, Storage & Peripherals"\n'
            "MSFT,EQUITY,Technology,Software\n"
        )
        try:
            dry_run = plan_taxonomy_import(self.database_url, Path(valid.name))
            self.assertTrue(dry_run.valid)
            self.assertEqual(dry_run.changes, ("AAPL", "MSFT"))
            self.assertEqual(self.repository.count_incomplete_taxonomy_records(), 2)
            applied = apply_taxonomy_import(self.database_url, Path(valid.name))
            self.assertTrue(applied["applied"])
            self.assertEqual(applied["after"]["complete"], 2)
            repeated = plan_taxonomy_import(self.database_url, Path(valid.name))
            self.assertEqual(repeated.changes, ())
            self.assertEqual(repeated.unchanged, ("AAPL", "MSFT"))
        finally:
            valid.close()

        unknown = self.csv_file("UNKNOWN,ETF,,\n")
        try:
            plan = plan_taxonomy_import(self.database_url, Path(unknown.name))
            self.assertFalse(plan.valid)
            self.assertEqual(plan.issues[0].code, "unknown_symbol")
        finally:
            unknown.close()

        invalid = self.csv_file(
            "AAPL,EQUITY,Technology,Software\n"
            "MSFT,ETF,Technology,Software\n"
        )
        try:
            before = self.repository.list_instrument_taxonomy()
            result = apply_taxonomy_import(self.database_url, Path(invalid.name))
            self.assertFalse(result["valid"])
            self.assertFalse(result["applied"])
            self.assertEqual(self.repository.list_instrument_taxonomy(), before)
        finally:
            invalid.close()

    def test_import_flags_exchange_qualified_identity(self) -> None:
        self.ingest("PLTR", 1)
        ambiguous = self.csv_file("NASDAQ:PLTR,EQUITY,Technology,Software\n")
        try:
            plan = plan_taxonomy_import(self.database_url, Path(ambiguous.name))
            self.assertFalse(plan.valid)
            self.assertEqual(
                plan.issues[0].code,
                "ambiguous_exchange_qualified_symbol",
            )
        finally:
            ambiguous.close()

    def test_csv_apply_rolls_back_every_row_on_database_failure(self) -> None:
        self.ingest("AAPL", 1)
        self.ingest("MSFT", 2)
        reviewed = self.csv_file(
            "AAPL,EQUITY,Technology,Software\n"
            "MSFT,EQUITY,Technology,Software\n"
        )
        try:
            with transaction(self.database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE OR REPLACE FUNCTION reject_taxonomy_test_update()
                        RETURNS trigger LANGUAGE plpgsql AS $$
                        BEGIN
                            IF NEW.symbol = 'MSFT' THEN
                                RAISE EXCEPTION 'simulated taxonomy write failure';
                            END IF;
                            RETURN NEW;
                        END;
                        $$
                        """
                    )
                    cursor.execute(
                        """
                        CREATE TRIGGER reject_taxonomy_test_update
                        BEFORE UPDATE ON instruments
                        FOR EACH ROW EXECUTE FUNCTION reject_taxonomy_test_update()
                        """
                    )
            before = self.repository.list_instrument_taxonomy()
            with self.assertRaisesRegex(Exception, "simulated taxonomy write failure"):
                apply_taxonomy_import(self.database_url, Path(reviewed.name))
            self.assertEqual(self.repository.list_instrument_taxonomy(), before)
        finally:
            with transaction(self.database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DROP TRIGGER IF EXISTS reject_taxonomy_test_update ON instruments"
                    )
                    cursor.execute(
                        "DROP FUNCTION IF EXISTS reject_taxonomy_test_update()"
                    )
            reviewed.close()


if __name__ == "__main__":
    unittest.main()
