from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TRADE_DESK = ROOT_DIR / "pine" / "TradeDesk.pine"


def presentation_visible(*, type_enabled: bool, mitigated: bool, show_mitigated: bool) -> bool:
    return type_enabled and (not mitigated or show_mitigated)


@dataclass
class RetainedPresentation:
    mitigated: bool
    context_tier: str
    handle: int | None = None
    created_handles: int = 0

    def render(self, *, type_enabled: bool, show_mitigated: bool) -> None:
        visible = presentation_visible(
            type_enabled=type_enabled,
            mitigated=self.mitigated,
            show_mitigated=show_mitigated,
        )
        if visible and self.handle is None:
            self.created_handles += 1
            self.handle = self.created_handles
        elif not visible:
            self.handle = None


class PdVisibilityBehaviorTests(unittest.TestCase):
    def test_active_displacement_visible_with_toggle_on_or_off(self) -> None:
        self.assertTrue(presentation_visible(type_enabled=True, mitigated=False, show_mitigated=True))
        self.assertTrue(presentation_visible(type_enabled=True, mitigated=False, show_mitigated=False))

    def test_mitigated_displacement_obeys_toggle(self) -> None:
        self.assertTrue(presentation_visible(type_enabled=True, mitigated=True, show_mitigated=True))
        self.assertFalse(presentation_visible(type_enabled=True, mitigated=True, show_mitigated=False))

    def test_fvg_active_and_mitigated_cases(self) -> None:
        self.assertTrue(presentation_visible(type_enabled=True, mitigated=False, show_mitigated=False))
        self.assertTrue(presentation_visible(type_enabled=True, mitigated=True, show_mitigated=True))
        self.assertFalse(presentation_visible(type_enabled=True, mitigated=True, show_mitigated=False))

    def test_vi_active_and_mitigated_cases(self) -> None:
        self.assertTrue(presentation_visible(type_enabled=True, mitigated=False, show_mitigated=False))
        self.assertTrue(presentation_visible(type_enabled=True, mitigated=True, show_mitigated=True))
        self.assertFalse(presentation_visible(type_enabled=True, mitigated=True, show_mitigated=False))

    def test_ob_invalidated_state_is_the_historical_state_governed_by_toggle(self) -> None:
        self.assertTrue(presentation_visible(type_enabled=True, mitigated=False, show_mitigated=False))
        self.assertTrue(presentation_visible(type_enabled=True, mitigated=True, show_mitigated=True))
        self.assertFalse(presentation_visible(type_enabled=True, mitigated=True, show_mitigated=False))

    def test_type_toggle_remains_authoritative(self) -> None:
        self.assertFalse(presentation_visible(type_enabled=False, mitigated=False, show_mitigated=True))
        self.assertFalse(presentation_visible(type_enabled=False, mitigated=True, show_mitigated=True))

    def test_off_on_restores_retained_visual_without_state_change_or_leak(self) -> None:
        evidence = RetainedPresentation(mitigated=True, context_tier="OUTER_2W")
        evidence.render(type_enabled=True, show_mitigated=True)
        first_handle = evidence.handle
        self.assertIsNotNone(first_handle)

        evidence.render(type_enabled=True, show_mitigated=False)
        evidence.render(type_enabled=True, show_mitigated=False)
        self.assertIsNone(evidence.handle)
        self.assertTrue(evidence.mitigated)
        self.assertEqual(evidence.context_tier, "OUTER_2W")
        self.assertEqual(evidence.created_handles, 1)

        evidence.render(type_enabled=True, show_mitigated=True)
        restored_handle = evidence.handle
        evidence.render(type_enabled=True, show_mitigated=True)
        self.assertIsNotNone(restored_handle)
        self.assertNotEqual(restored_handle, first_handle)
        self.assertEqual(evidence.handle, restored_handle)
        self.assertEqual(evidence.created_handles, 2)
        self.assertTrue(evidence.mitigated)
        self.assertEqual(evidence.context_tier, "OUTER_2W")


class TradeDeskPdVisibilityPineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = TRADE_DESK.read_text(encoding="utf-8")

    def test_master_input_defaults_true_in_existing_evidence_group(self) -> None:
        self.assertIn(
            'bool showMitigatedPdArrays = input.bool(true, "Show Mitigated PD Arrays", group = GROUP_EQM_PD_ARRAYS)',
            self.source,
        )

    def test_each_pd_type_has_subordinate_presentation_gate(self) -> None:
        required = (
            "bool displacementPresentationVisible = not isMitigated or showMitigatedPdArrays",
            "showProximalDisplacement and showDisplacementCe and displacementPresentationVisible",
            "bool fvgPresentationVisible = not fvgMitigated or showMitigatedPdArrays",
            "showProximalFvg and showFvgCe and fvgPresentationVisible",
            "showProximalFvg and showFvgLabels and fvgPresentationVisible",
            "bool viPresentationVisible = not viMitigated or showMitigatedPdArrays",
            "showProximalVi and showViCe and viPresentationVisible",
            "showProximalVi and showViLabels and viPresentationVisible",
            "bool activeObPresentationVisible = not obInvalidated or showMitigatedPdArrays",
            "showActiveOb and activeObPresentationVisible",
            "showActiveOb and showObCe and activeObPresentationVisible",
            "showActiveOb and showObLabels and activeObPresentationVisible",
        )
        for expression in required:
            self.assertIn(expression, self.source)

    def test_mitigation_and_invalidation_rules_are_unchanged(self) -> None:
        for rule in (
            "bar_index > creationBar and bodyTouchesCe",
            "fvgDirection == 1 ? close < fvgCe : close > fvgCe",
            "viDirection == 1 ? close < viCe : close > viCe",
            "activeObDirection == 1 ? close < activeObBottom : close > activeObTop",
        ):
            self.assertIn(rule, self.source)

    def test_hiding_deletes_only_disposable_presentation_handles(self) -> None:
        for delete_statement in (
            "line.delete(displacementCeLine)",
            "line.delete(fvgCeLine)",
            "label.delete(fvgLabel)",
            "line.delete(viCeLine)",
            "label.delete(viLabel)",
            "box.delete(activeObBox)",
            "line.delete(activeObCeLine)",
            "label.delete(activeObLabel)",
        ):
            self.assertIn(delete_statement, self.source)

    def test_visibility_toggle_does_not_mutate_lifecycle_or_context_arrays(self) -> None:
        toggle_lines = [line for line in self.source.splitlines() if "showMitigatedPdArrays" in line]
        self.assertGreaterEqual(len(toggle_lines), 5)
        for line in toggle_lines:
            self.assertNotIn("array.set", line)
            self.assertNotIn("array.shift", line)
            self.assertNotIn("array.remove", line)
        for context_array in (
            "proximalDisplacementContextTiers",
            "proximalFvgContextTiers",
            "proximalViContextTiers",
            "activeObContextTiers",
        ):
            self.assertNotIn(f"array.set({context_array}", self.source)


if __name__ == "__main__":
    unittest.main()
