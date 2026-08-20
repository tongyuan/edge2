from __future__ import annotations

import unittest
from decimal import Decimal

from pydantic import ValidationError

from app.validation import ObservationPayload, decimal_tick, normalize_symbol


def payload(**overrides):
    value = {
        "schema_version": "4.3",
        "event_id": "evt-1",
        "symbol": "BINANCE:spxusdt",
        "route": "BTD",
        "observation_type": "reclaim",
        "observation_price": "110.25",
        "ipda_20w_high": "200",
        "ipda_20w_low": "100",
        "observed_at": "2026-08-20T12:00:00Z",
    }
    value.update(overrides)
    return value


class Schema43ValidationTests(unittest.TestCase):
    def test_valid_btd_and_symbol_normalization(self) -> None:
        parsed = ObservationPayload.model_validate(payload())
        self.assertEqual(parsed.symbol, "SPXUSDT")
        self.assertEqual(parsed.price_tick({}), Decimal("0.01"))

    def test_valid_str(self) -> None:
        parsed = ObservationPayload.model_validate(
            payload(route="STR", observation_type="rejection", observation_price="180.5")
        )
        self.assertEqual(parsed.route.value, "STR")

    def assert_invalid(self, **overrides) -> None:
        with self.assertRaises(ValidationError):
            ObservationPayload.model_validate(payload(**overrides))

    def test_malformed_or_non_positive_price(self) -> None:
        for value in ("not-a-number", "NaN", "Infinity", "0", "-1"):
            with self.subTest(value=value):
                self.assert_invalid(observation_price=value)

    def test_invalid_high_low(self) -> None:
        for high, low in (("100", "100"), ("99", "100"), ("NaN", "100")):
            with self.subTest(high=high, low=low):
                self.assert_invalid(ipda_20w_high=high, ipda_20w_low=low)

    def test_wrong_schema(self) -> None:
        self.assert_invalid(schema_version="4.2")

    def test_route_observation_mismatch(self) -> None:
        self.assert_invalid(route="BTD", observation_type="rejection")
        self.assert_invalid(route="STR", observation_type="reclaim")

    def test_timestamp_requires_timezone(self) -> None:
        self.assert_invalid(observed_at="2026-08-20T12:00:00")

    def test_event_id_required(self) -> None:
        self.assert_invalid(event_id="")

    def test_normalize_symbol_rejects_unapproved_characters(self) -> None:
        self.assertEqual(normalize_symbol("NASDAQ:pltr"), "PLTR")
        with self.assertRaises(ValueError):
            normalize_symbol("SPX/USDT")

    def test_decimal_tick_uses_payload_precision(self) -> None:
        self.assertEqual(decimal_tick(Decimal("110.2500")), Decimal("0.0001"))
        self.assertEqual(decimal_tick(Decimal("110")), Decimal("1"))
