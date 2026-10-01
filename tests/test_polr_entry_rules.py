from __future__ import annotations

import unittest
from decimal import Decimal

from app.polr_entry import (
    confirmation_satisfied,
    grade_meets,
    intersect_entry_zone,
    range_third_bounds,
)


class POLREntryRuleTests(unittest.TestCase):
    def test_bottom_and_top_thirds_are_directional(self) -> None:
        low = Decimal("1409.42")
        high = Decimal("1494.52")
        long_bottom, long_top = range_third_bounds("LONG", low, high)
        short_bottom, short_top = range_third_bounds("SHORT", low, high)
        self.assertEqual(long_bottom, low)
        self.assertEqual(short_top, high)
        self.assertLess(long_top, short_bottom)
        self.assertEqual(long_top - long_bottom, short_top - short_bottom)

    def test_array_ote_and_third_intersection_freezes_the_eligible_zone(self) -> None:
        self.assertEqual(
            intersect_entry_zone(
                direction="LONG",
                range_low=Decimal("1409.42"),
                range_high=Decimal("1494.52"),
                source_bottom=Decimal("1408.00"),
                source_top=Decimal("1416.20"),
                ote_required=True,
                ote_bottom=Decimal("1408.33"),
                ote_top=Decimal("1416.78"),
            ),
            (Decimal("1409.42"), Decimal("1416.20")),
        )

    def test_non_overlapping_array_is_not_eligible(self) -> None:
        self.assertIsNone(
            intersect_entry_zone(
                direction="LONG",
                range_low=Decimal("1409.42"),
                range_high=Decimal("1494.52"),
                source_bottom=Decimal("1440"),
                source_top=Decimal("1445"),
                ote_required=True,
                ote_bottom=Decimal("1408.33"),
                ote_top=Decimal("1416.78"),
            )
        )

    def test_required_grade_choices(self) -> None:
        self.assertTrue(grade_meets(None, "Off"))
        self.assertTrue(grade_meets("A+", "A+"))
        self.assertTrue(grade_meets("A+", "A"))
        self.assertFalse(grade_meets("A", "A+"))

    def test_both_confirmation_methods_mirror_by_direction(self) -> None:
        common = {"zone_bottom": Decimal("1409.42"), "zone_top": Decimal("1416.20")}
        self.assertTrue(
            confirmation_satisfied(
                direction="LONG", method="CE_RECLAIM", close=Decimal("1413"), **common
            )
        )
        self.assertFalse(
            confirmation_satisfied(
                direction="LONG", method="PROXIMAL_RECLAIM", close=Decimal("1413"), **common
            )
        )
        self.assertTrue(
            confirmation_satisfied(
                direction="SHORT", method="CE_RECLAIM", close=Decimal("1412"), **common
            )
        )
        self.assertFalse(
            confirmation_satisfied(
                direction="SHORT", method="PROXIMAL_RECLAIM", close=Decimal("1412"), **common
            )
        )


if __name__ == "__main__":
    unittest.main()
