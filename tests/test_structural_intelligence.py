from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.structural_intelligence import classify_structural_history, meaningful_development


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def history(midpoints: list[float], *, known_delay: int = 0) -> list[dict]:
    rows = []
    for index, midpoint in enumerate(midpoints, start=1):
        occurred = BASE + timedelta(days=index)
        rows.append({
            "event_key": f"e{index}",
            "sequence": index,
            "event_type": "MRZ_ACTIVATED" if index == 1 else "MRZ_MIGRATED",
            "symbol": "TEST",
            "route_owner": "BTD" if index % 2 else "STR",
            "occurred_at": occurred,
            "created_at": occurred + timedelta(hours=known_delay),
            "new_core_mrz_lower": Decimal(str(midpoint - .5)),
            "new_core_mrz_upper": Decimal(str(midpoint + .5)),
            "new_core_mrz_midpoint": Decimal(str(midpoint)),
            "instrument_tick": Decimal("0.01"),
        })
    return rows


class StructuralIntelligenceTests(unittest.TestCase):
    def test_clear_descending_structure_and_route(self):
        result = classify_structural_history(history([100, 96, 92, 88]))
        self.assertEqual(result["migration_structure"], "descending")
        self.assertEqual(result["route_hypothesis"], "STR_DOMINANT")

    def test_clear_ascending_structure_and_route(self):
        result = classify_structural_history(history([88, 92, 96, 100]))
        self.assertEqual(result["migration_structure"], "ascending")
        self.assertEqual(result["route_hypothesis"], "BTD_DOMINANT")

    def test_single_opposite_migration_does_not_establish_reversal(self):
        result = classify_structural_history(history([100, 96, 92, 88, 90]))
        self.assertNotEqual(result["migration_structure"], "ascending")
        self.assertNotEqual(result["route_hypothesis"], "BTD_DOMINANT")

    def test_confirmed_higher_low(self):
        result = classify_structural_history(history([100, 90, 95, 92, 97]))
        self.assertIn("HL", [item["type"] for item in result["pivots"]])
        pivot = next(item for item in result["pivots"] if item["type"] == "HL")
        self.assertEqual(pivot["maturity"], "confirmed")
        self.assertIsNotNone(pivot["confirmation_time"])

    def test_developing_higher_low_is_not_confirmed(self):
        result = classify_structural_history(history([100, 90, 95, 92]))
        self.assertEqual(result["latest_development"]["type"], "HL")
        self.assertEqual(result["latest_development"]["maturity"], "developing")
        self.assertIsNone(result["latest_development"]["confirmation_time"])

    def test_confirmed_lower_high(self):
        result = classify_structural_history(history([90, 100, 95, 98, 92]))
        self.assertIn("LH", [item["type"] for item in result["pivots"]])

    def test_equal_levels_respect_canonical_tick(self):
        result = classify_structural_history(history([100, 100.004, 100, 100.003]))
        self.assertEqual(result["migration_structure"], "undetermined")

    def test_insufficient_and_missing_history(self):
        self.assertEqual(classify_structural_history(history([100, 101]))["migration_structure"], "undetermined")
        self.assertEqual(classify_structural_history([])["route_hypothesis"], "INSUFFICIENT_HISTORY")

    def test_no_future_knowledge_leakage(self):
        rows = history([100, 90, 95, 92, 97], known_delay=12)
        cutoff = rows[3]["occurred_at"] + timedelta(hours=13)
        result = classify_structural_history(rows, as_known_at=cutoff)
        self.assertLess(result["history_state_count"], len(rows))
        self.assertFalse(any(item["pivot_event_key"] == "e4" and item["maturity"] == "confirmed" for item in result["pivots"]))

    def test_meaningful_development_deduplicates_lifecycle_identity(self):
        current = classify_structural_history(history([100, 90, 95, 92]))
        self.assertIsNotNone(meaningful_development(None, current))
        self.assertIsNone(meaningful_development(current, current))


if __name__ == "__main__":
    unittest.main()
