#!/usr/bin/env python3
"""Run the complete Python test suite except tests backed by Pine sources."""

from __future__ import annotations

import sys
import unittest
from collections.abc import Iterator
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PINE_TEST_PREFIXES = (
    "test_external_range_liquidity.PineStaticContractTests.",
    "test_pinescript_contract.Edge2PineContractTests.",
    "test_trade_desk_no_external_liquidity.TradeDeskNoExternalLiquidityContractTests.",
    "test_trade_desk_observer_context.TradeDeskContextTests.",
    "test_trade_desk_pd_context.TradeDeskPdContextPineContractTests.",
    "test_trade_desk_pd_label_positioning.TradeDeskPdLabelPositioningPineContractTests.",
    "test_trade_desk_pd_visibility.TradeDeskPdVisibilityPineContractTests.",
    "test_tradedesk_pine_entry_contract.TradeDeskPineEntryContractTests.",
    "test_tradedesk_pine_result_contract.TradeDeskPineResultContractTests.",
)


def test_cases(suite: unittest.TestSuite) -> Iterator[unittest.TestCase]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from test_cases(item)
        else:
            yield item


def main() -> int:
    discovered = unittest.defaultTestLoader.discover("tests")
    selected = unittest.TestSuite()
    excluded: list[str] = []
    for case in test_cases(discovered):
        identity = case.id()
        if identity.startswith(PINE_TEST_PREFIXES):
            excluded.append(identity)
        else:
            selected.addTest(case)
    print(f"Excluded {len(excluded)} Pine-backed tests; running {selected.countTestCases()} non-Pine tests.")
    result = unittest.TextTestRunner(verbosity=2).run(selected)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
