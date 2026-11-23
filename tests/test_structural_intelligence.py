from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.structural_intelligence import (
    ROUTE_HYPOTHESIS_LABELS,
    classify_structural_history,
    meaningful_development,
    persisted_route_hypothesis,
)


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def history(
    midpoints: list[float],
    *,
    route: str = "BTD",
    routes: list[str] | None = None,
    known_delay: int = 0,
    symbol: str = "TEST",
) -> list[dict]:
    rows = []
    for index, midpoint in enumerate(midpoints, start=1):
        occurred = BASE + timedelta(days=index)
        rows.append({
            "event_key": f"e{index}",
            "sequence": index,
            "event_type": "MRZ_ACTIVATED" if index == 1 else "MRZ_MIGRATED",
            "symbol": symbol,
            "route_owner": routes[index - 1] if routes else route,
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
        result = classify_structural_history(history([100, 96, 92, 88], route="STR"))
        self.assertEqual(result["migration_structure"], "descending")
        self.assertEqual(result["route_hypothesis"], "STR_SUPPORTIVE")
        self.assertEqual(result["route_hypothesis_label"], "STR-supportive")
        self.assertEqual(result["migration_alignment"], "reinforced")

    def test_clear_ascending_structure_and_route(self):
        result = classify_structural_history(history([88, 92, 96, 100]))
        self.assertEqual(result["migration_structure"], "ascending")
        self.assertEqual(result["route_hypothesis"], "BTD_SUPPORTIVE")
        self.assertEqual(result["route_hypothesis_label"], "BTD-supportive")

    def test_single_opposite_migration_does_not_establish_reversal(self):
        result = classify_structural_history(history([100, 96, 92, 88, 90]))
        self.assertNotEqual(result["migration_structure"], "ascending")
        self.assertEqual(result["route_hypothesis"], "BTD_SUPPORTIVE_PROVISIONAL")

    def test_confirmed_higher_low(self):
        result = classify_structural_history(history([100, 90, 95, 92, 97]))
        self.assertIn("HL", [item["type"] for item in result["pivots"]])
        pivot = next(item for item in result["pivots"] if item["type"] == "HL")
        self.assertEqual(pivot["maturity"], "confirmed")
        self.assertIsNotNone(pivot["confirmation_time"])
        self.assertEqual(pivot["first_known_time"], pivot["confirmation_time"])

    def test_developing_higher_low_is_not_confirmed(self):
        result = classify_structural_history(history([100, 90, 95, 92]))
        self.assertEqual(result["latest_development"]["type"], "HL")
        self.assertEqual(result["latest_development"]["maturity"], "developing")
        self.assertIsNone(result["latest_development"]["confirmation_time"])

    def test_confirmed_lower_high(self):
        result = classify_structural_history(history([90, 100, 95, 98, 92]))
        self.assertIn("LH", [item["type"] for item in result["pivots"]])

    def test_developing_lower_high_is_not_confirmed(self):
        result = classify_structural_history(history([90, 100, 95, 98]))
        self.assertEqual(result["latest_development"]["type"], "LH")
        self.assertEqual(result["latest_development"]["maturity"], "developing")

    def test_meaningful_higher_high_and_lower_low_extensions(self):
        higher = classify_structural_history(history([100, 90, 95, 92, 97, 101]))
        lower = classify_structural_history(history([90, 100, 95, 98, 92, 88]))
        self.assertEqual(higher["latest_development"]["type"], "HH")
        self.assertEqual(higher["latest_development"]["maturity"], "confirmed")
        self.assertEqual(lower["latest_development"]["type"], "LL")
        self.assertEqual(lower["latest_development"]["maturity"], "confirmed")

    def test_confirmed_lifecycle_has_a_distinct_stable_identity(self):
        developing = classify_structural_history(history([100, 90, 95, 92]))
        confirmed = classify_structural_history(history([100, 90, 95, 92, 97]))
        self.assertNotEqual(
            developing["latest_development"]["development_id"],
            confirmed["latest_development"]["development_id"],
        )
        self.assertEqual(
            developing["latest_development"]["pivot_event_key"],
            confirmed["latest_development"]["pivot_event_key"],
        )
        self.assertIsNotNone(meaningful_development(developing, confirmed))

    def test_equal_levels_respect_canonical_tick(self):
        result = classify_structural_history(history([100, 100.004, 100, 100.003]))
        self.assertEqual(result["migration_structure"], "undetermined")

    def test_insufficient_and_missing_history(self):
        self.assertEqual(classify_structural_history(history([100, 101]))["migration_structure"], "undetermined")
        self.assertEqual(classify_structural_history([])["route_hypothesis"], "UNRESOLVED")

    def test_route_alignment_matrix_uses_route_identity_not_direction(self):
        ascending_btd = classify_structural_history(history([88, 92, 96, 100], route="BTD"))
        descending_btd = classify_structural_history(history([100, 96, 92, 88], route="BTD"))
        descending_str = classify_structural_history(history([100, 96, 92, 88], route="STR"))
        ascending_str = classify_structural_history(history([88, 92, 96, 100], route="STR"))
        self.assertEqual(ascending_btd["route_hypothesis"], "BTD_SUPPORTIVE")
        self.assertEqual(descending_btd["route_hypothesis"], "BTD_SUPPORTIVE_PROVISIONAL")
        self.assertEqual(descending_str["route_hypothesis"], "STR_SUPPORTIVE")
        self.assertEqual(ascending_str["route_hypothesis"], "STR_SUPPORTIVE_PROVISIONAL")
        self.assertEqual(descending_btd["eligible_route"], "BTD")
        self.assertEqual(ascending_str["eligible_route"], "STR")

    def test_no_or_one_migration_keeps_valid_route_provisional(self):
        cases = (
            (history([100], route="BTD"), "BTD_SUPPORTIVE_PROVISIONAL"),
            (history([100], route="STR"), "STR_SUPPORTIVE_PROVISIONAL"),
            (history([100, 110], route="BTD"), "BTD_SUPPORTIVE_PROVISIONAL"),
            (history([100, 90], route="BTD"), "BTD_SUPPORTIVE_PROVISIONAL"),
            (history([100, 90], route="STR"), "STR_SUPPORTIVE_PROVISIONAL"),
            (history([100, 110], route="STR"), "STR_SUPPORTIVE_PROVISIONAL"),
        )
        for rows, expected in cases:
            with self.subTest(expected=expected, midpoints=[row["new_core_mrz_midpoint"] for row in rows]):
                result = classify_structural_history(rows)
                self.assertEqual(result["migration_structure"], "undetermined")
                self.assertEqual(result["route_hypothesis"], expected)

    def test_mixed_history_is_provisional_and_structure_stays_independent(self):
        btd = classify_structural_history(history([100, 110, 95, 105], route="BTD"))
        str_result = classify_structural_history(history([100, 110, 95, 105], route="STR"))
        self.assertIn(btd["migration_structure"], {"transitional", "undetermined"})
        self.assertEqual(btd["migration_structure"], str_result["migration_structure"])
        self.assertEqual(btd["route_hypothesis"], "BTD_SUPPORTIVE_PROVISIONAL")
        self.assertEqual(str_result["route_hypothesis"], "STR_SUPPORTIVE_PROVISIONAL")

    def test_invalid_route_is_unresolved_and_exactly_five_statuses_exist(self):
        invalid = classify_structural_history(history([100, 110, 120, 130], route="MIXED"))
        self.assertEqual(invalid["route_hypothesis"], "UNRESOLVED")
        self.assertIsNone(invalid["eligible_route"])
        self.assertEqual(
            set(ROUTE_HYPOTHESIS_LABELS),
            {
                "BTD_SUPPORTIVE",
                "BTD_SUPPORTIVE_PROVISIONAL",
                "STR_SUPPORTIVE",
                "STR_SUPPORTIVE_PROVISIONAL",
                "UNRESOLVED",
            },
        )

    def test_9988_downward_migration_remains_btd_provisional(self):
        result = classify_structural_history(
            history([110.00, 106.40], route="BTD", symbol="9988.HK")
        )
        self.assertEqual(result["symbol"], "9988.HK")
        self.assertEqual(result["migration_structure"], "undetermined")
        self.assertEqual(result["eligible_route"], "BTD")
        self.assertEqual(result["route_hypothesis"], "BTD_SUPPORTIVE_PROVISIONAL")
        self.assertEqual(result["route_hypothesis_label"], "BTD-supportive (Provisional)")

    def test_route_status_uses_latest_canonical_route_without_rewriting_history(self):
        rows = history([100, 96, 92, 88], routes=["STR", "STR", "STR", "BTD"])
        result = classify_structural_history(rows)
        self.assertEqual([state["route"] for state in result["states"]], ["STR", "STR", "STR", "BTD"])
        self.assertEqual(result["migration_structure"], "descending")
        self.assertEqual(result["route_hypothesis"], "BTD_SUPPORTIVE_PROVISIONAL")

    def test_legacy_persistence_mapping_requires_no_schema_or_data_change(self):
        self.assertEqual(persisted_route_hypothesis("BTD_SUPPORTIVE"), "BTD_DOMINANT")
        self.assertEqual(persisted_route_hypothesis("BTD_SUPPORTIVE_PROVISIONAL"), "BTD_DOMINANT")
        self.assertEqual(persisted_route_hypothesis("STR_SUPPORTIVE"), "STR_DOMINANT")
        self.assertEqual(persisted_route_hypothesis("STR_SUPPORTIVE_PROVISIONAL"), "STR_DOMINANT")
        self.assertEqual(persisted_route_hypothesis("UNRESOLVED"), "UNRESOLVED")

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
