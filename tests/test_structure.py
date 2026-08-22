from __future__ import annotations

import unittest
from decimal import Decimal

from app.domain import PriceLocation, Route, StructuralLocation
from app.structure import (
    classify_ipda_location,
    classify_structural_location,
    ipda_directional_context,
    structural_geometry,
)


class StructuralClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.low = Decimal("100")
        self.high = Decimal("200")

    def test_geometry(self) -> None:
        self.assertEqual(
            structural_geometry(self.high, self.low),
            {
                "ipda_width": Decimal("100"),
                "eqm": Decimal("150"),
                "discount_midpoint": Decimal("125"),
                "premium_midpoint": Decimal("175"),
            },
        )

    def test_deep_and_shallow_discount_boundaries(self) -> None:
        self.assertEqual(
            classify_structural_location(Route.BTD, Decimal("100"), self.high, self.low),
            StructuralLocation.DEEP_DISCOUNT,
        )
        self.assertEqual(
            classify_structural_location(Route.BTD, Decimal("124.999"), self.high, self.low),
            StructuralLocation.DEEP_DISCOUNT,
        )
        self.assertEqual(
            classify_structural_location(Route.BTD, Decimal("125"), self.high, self.low),
            StructuralLocation.SHALLOW_DISCOUNT,
        )
        self.assertEqual(
            classify_structural_location(Route.BTD, Decimal("149.999"), self.high, self.low),
            StructuralLocation.SHALLOW_DISCOUNT,
        )

    def test_eqm_is_invalid_for_both_routes(self) -> None:
        self.assertIsNone(classify_structural_location(Route.BTD, Decimal("150"), self.high, self.low))
        self.assertIsNone(classify_structural_location(Route.STR, Decimal("150"), self.high, self.low))

    def test_shallow_and_deep_premium_boundaries(self) -> None:
        self.assertEqual(
            classify_structural_location(Route.STR, Decimal("150.001"), self.high, self.low),
            StructuralLocation.SHALLOW_PREMIUM,
        )
        self.assertEqual(
            classify_structural_location(Route.STR, Decimal("175"), self.high, self.low),
            StructuralLocation.SHALLOW_PREMIUM,
        )
        self.assertEqual(
            classify_structural_location(Route.STR, Decimal("175.001"), self.high, self.low),
            StructuralLocation.DEEP_PREMIUM,
        )
        self.assertEqual(
            classify_structural_location(Route.STR, Decimal("200"), self.high, self.low),
            StructuralLocation.DEEP_PREMIUM,
        )

    def test_btd_premium_and_str_discount_are_invalid(self) -> None:
        self.assertIsNone(classify_structural_location(Route.BTD, Decimal("180"), self.high, self.low))
        self.assertIsNone(classify_structural_location(Route.STR, Decimal("120"), self.high, self.low))

    def test_current_price_location_boundaries(self) -> None:
        cases = (
            ("99.999", PriceLocation.BELOW_IPDA_RANGE),
            ("100", PriceLocation.DEEP_DISCOUNT),
            ("124.999", PriceLocation.DEEP_DISCOUNT),
            ("125", PriceLocation.SHALLOW_DISCOUNT),
            ("149.999", PriceLocation.SHALLOW_DISCOUNT),
            ("150.001", PriceLocation.SHALLOW_PREMIUM),
            ("175", PriceLocation.SHALLOW_PREMIUM),
            ("175.001", PriceLocation.DEEP_PREMIUM),
            ("200", PriceLocation.DEEP_PREMIUM),
            ("200.001", PriceLocation.ABOVE_IPDA_RANGE),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(
                    classify_ipda_location(Decimal(value), self.high, self.low),
                    expected,
                )

    def test_current_price_at_exact_eqm_has_no_location_bucket(self) -> None:
        self.assertIsNone(classify_ipda_location(Decimal("150"), self.high, self.low))

    def test_directional_context_across_discount_and_premium_depths(self) -> None:
        cases = (
            ("160", "20% from EQM toward IPDA high", PriceLocation.SHALLOW_PREMIUM),
            ("180", "60% from EQM toward IPDA high", PriceLocation.DEEP_PREMIUM),
            ("130", "40% from EQM toward IPDA low", PriceLocation.SHALLOW_DISCOUNT),
            ("110", "80% from EQM toward IPDA low", PriceLocation.DEEP_DISCOUNT),
        )
        for value, expected_context, expected_location in cases:
            with self.subTest(value=value):
                price = Decimal(value)
                self.assertEqual(ipda_directional_context(price, self.high, self.low), expected_context)
                self.assertEqual(classify_ipda_location(price, self.high, self.low), expected_location)

    def test_directional_context_handles_eqm_range_edges_and_outside_truthfully(self) -> None:
        cases = (
            ("150", "At IPDA EQM"),
            ("200", "100% from EQM toward IPDA high"),
            ("100", "100% from EQM toward IPDA low"),
            ("201", "Above IPDA high"),
            ("99", "Below IPDA low"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(
                    ipda_directional_context(Decimal(value), self.high, self.low),
                    expected,
                )
