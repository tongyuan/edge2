from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TRADE_DESK = ROOT_DIR / "pine" / "TradeDesk.pine"


class TradeDeskNoExternalLiquidityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = TRADE_DESK.read_text(encoding="utf-8")

    def test_external_liquidity_inputs_and_group_are_absent(self) -> None:
        for removed in (
            "GROUP_EXTERNAL_LIQUIDITY",
            "showExternalLiquidity",
            "externalLiquidityMode",
            "externalLiquidityDetectionLength",
            "externalLiquidityMarginInput",
            "showBuysideLiquidity",
            "showSellsideLiquidity",
            "externalLiquidityVisibleLevels",
            "showLiquidityBreachZones",
            "buysideBreachAtrMargin",
            "sellsideBreachAtrMargin",
            "buysideLiquidityColor",
            "sellsideLiquidityColor",
        ):
            self.assertNotIn(removed, self.source)

    def test_detector_state_and_rendering_are_absent(self) -> None:
        for removed in (
            "EXT_LIQ_MAX_PIVOTS",
            "extLiqPivot",
            "extBsl",
            "extSsl",
            "breachActive",
            "BSL IC",
            "SSL IC",
            'text = "BSL"',
            'text = "SSL"',
        ):
            self.assertNotIn(removed, self.source)

    def test_external_liquidity_events_and_payload_fields_are_absent(self) -> None:
        for removed in (
            "BSL_BREACHED",
            "SSL_BREACHED",
            "BSL_INTERACTION_COMPLETE",
            "SSL_INTERACTION_COMPLETE",
            "f_externalLiquidityObjectId",
            "f_externalLiquidityInteractionCompletePayload",
            "f_externalLiquidityInteractionCompleteTooltip",
            '"nearest_active_bsl_above"',
            '"nearest_active_ssl_below"',
        ):
            self.assertNotIn(removed, self.source)

    def test_no_bsl_or_ssl_authority_remains(self) -> None:
        self.assertIsNone(re.search(r"\bBSL\b|\bSSL\b", self.source, re.IGNORECASE))
        self.assertNotIn("EXTERNAL LIQUIDITY", self.source.upper())
        self.assertNotIn("NEAREST ACTIVE", self.source.upper())
        self.assertNotIn("INTERACTION COMPLETE", self.source.upper())

    def test_observer_panel_contains_only_the_twelve_non_liquidity_rows(self) -> None:
        self.assertIn("table.new(position.bottom_right, 2, 12)", self.source)
        self.assertNotIn("Nearest Active BSL", self.source)
        self.assertNotIn("Nearest Active SSL", self.source)

    def test_non_liquidity_observer_and_pd_array_contracts_remain_present(self) -> None:
        for preserved in (
            "f_observerEqmReachedPayload",
            "f_observerEndpointEqmReachedPayload",
            "currentMrzMidpoint",
            "previousMrzMidpoint",
            "migrationEqm",
            "eqmProximalZoneLow",
            "proximalDisplacementCeLevels",
            "proximalFvgCeLevels",
            "proximalViCeLevels",
            "activeObTops",
        ):
            self.assertIn(preserved, self.source)

    def test_resource_limits_reflect_remaining_pd_and_observer_objects(self) -> None:
        declaration = self.source.splitlines()[2]
        self.assertIn("max_boxes_count = 100", declaration)
        self.assertIn("max_labels_count = 250", declaration)
        self.assertIn("max_lines_count = 500", declaration)


if __name__ == "__main__":
    unittest.main()
