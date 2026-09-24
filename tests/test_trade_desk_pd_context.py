from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TRADE_DESK = ROOT_DIR / "pine" / "TradeDesk.pine"

OUTSIDE = "OUTSIDE"
PROXIMAL = "PROXIMAL"
NEAR_1W = "NEAR_1W"
OUTER_2W = "OUTER_2W"
NONE = "NONE"
CURRENT = "CURRENT"
PREVIOUS = "PREVIOUS"


@dataclass(frozen=True)
class Mrz:
    lower: float
    upper: float

    @property
    def midpoint(self) -> float:
        return (self.lower + self.upper) / 2.0

    def envelope(self, multiple: int) -> tuple[float, float]:
        width = self.upper - self.lower
        return self.lower - multiple * width, self.upper + multiple * width


def intersects(low: float, high: float, context: tuple[float, float]) -> bool:
    return high >= context[0] and low <= context[1]


def classify(
    low: float,
    high: float,
    *,
    is_proximal: bool,
    current: Mrz | None,
    previous: Mrz | None,
) -> tuple[str, str]:
    """Executable mirror of the Pine tier/owner contract."""
    if is_proximal:
        return PROXIMAL, NONE

    center = (low + high) / 2.0
    for tier, multiple in ((NEAR_1W, 1), (OUTER_2W, 2)):
        current_match = current is not None and intersects(low, high, current.envelope(multiple))
        previous_match = previous is not None and intersects(low, high, previous.envelope(multiple))
        if current_match or previous_match:
            if current_match and previous_match:
                current_distance = abs(center - current.midpoint)
                previous_distance = abs(center - previous.midpoint)
                # Exact ties deliberately resolve to CURRENT.
                owner = PREVIOUS if previous_distance < current_distance else CURRENT
            else:
                owner = CURRENT if current_match else PREVIOUS
            return tier, owner
    return OUTSIDE, NONE


class PdContextClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.current = Mrz(100.0, 110.0)
        self.previous = Mrz(150.0, 160.0)

    def test_a_strict_proximal_wins_before_wider_context(self) -> None:
        self.assertEqual(
            classify(107.0, 108.0, is_proximal=True, current=self.current, previous=self.previous),
            (PROXIMAL, NONE),
        )

    def test_b_current_near_1w(self) -> None:
        self.assertEqual(
            classify(115.0, 116.0, is_proximal=False, current=self.current, previous=self.previous),
            (NEAR_1W, CURRENT),
        )

    def test_c_current_outer_2w(self) -> None:
        self.assertEqual(
            classify(125.0, 126.0, is_proximal=False, current=self.current, previous=self.previous),
            (OUTER_2W, CURRENT),
        )

    def test_d_outside_2w_is_ignored(self) -> None:
        self.assertEqual(
            classify(185.0, 186.0, is_proximal=False, current=self.current, previous=self.previous),
            (OUTSIDE, NONE),
        )

    def test_e_previous_context_is_independent(self) -> None:
        self.assertEqual(
            classify(165.0, 166.0, is_proximal=False, current=self.current, previous=self.previous),
            (NEAR_1W, PREVIOUS),
        )
        self.assertEqual(
            classify(175.0, 176.0, is_proximal=False, current=self.current, previous=self.previous),
            (OUTER_2W, PREVIOUS),
        )

    def test_f_overlap_owner_uses_closest_midpoint_and_ties_current(self) -> None:
        overlapping_current = Mrz(100.0, 110.0)
        overlapping_previous = Mrz(110.0, 120.0)
        self.assertEqual(
            classify(113.0, 114.0, is_proximal=False, current=overlapping_current, previous=overlapping_previous),
            (NEAR_1W, PREVIOUS),
        )
        self.assertEqual(
            classify(109.0, 111.0, is_proximal=False, current=overlapping_current, previous=overlapping_previous),
            (NEAR_1W, CURRENT),
        )

    def test_g_no_giant_bridge_between_current_and_previous(self) -> None:
        separated_current = Mrz(0.0, 10.0)
        separated_previous = Mrz(100.0, 110.0)
        self.assertEqual(
            classify(49.0, 51.0, is_proximal=False, current=separated_current, previous=separated_previous),
            (OUTSIDE, NONE),
        )

    def test_h_previous_unavailable_cannot_own_context(self) -> None:
        self.assertEqual(
            classify(165.0, 166.0, is_proximal=False, current=self.current, previous=None),
            (OUTSIDE, NONE),
        )
        self.assertEqual(
            classify(115.0, 116.0, is_proximal=False, current=self.current, previous=None),
            (NEAR_1W, CURRENT),
        )

    def test_eth_bullish_ob_near_current_plus_1w(self) -> None:
        eth_current = Mrz(2_600.0, 2_610.0)
        eth_previous = Mrz(2_500.0, 2_510.0)
        self.assertEqual(
            classify(2_618.0, 2_622.0, is_proximal=False, current=eth_current, previous=eth_previous),
            (NEAR_1W, CURRENT),
        )


class TradeDeskPdContextPineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = TRADE_DESK.read_text(encoding="utf-8")

    def test_one_central_classifier_enforces_priority_and_individual_envelopes(self) -> None:
        self.assertEqual(self.source.count("f_classifyPdContext(float"), 1)
        classifier = self.source.split("f_classifyPdContext(float", 1)[1].split("f_pdContextSuffix", 1)[0]
        self.assertLess(classifier.index("if _isProximal"), classifier.index("else if intersectsCurrent1W"))
        self.assertLess(classifier.index("else if intersectsCurrent1W"), classifier.index("else if intersectsCurrent2W"))
        for token in (
            "currentMinus1W, currentPlus1W",
            "previousMinus1W, previousPlus1W",
            "currentMinus2W, currentPlus2W",
            "previousMinus2W, previousPlus2W",
        ):
            self.assertIn(token, classifier)
        self.assertNotIn("evidenceEnvelopeLow", classifier)
        self.assertNotIn("evidenceEnvelopeHigh", classifier)

    def test_existing_strict_proximal_predicates_remain_authoritative(self) -> None:
        required = (
            "bool activeDisplacementQualified = activeEvidenceGeometryAvailable and displacementIntersectsEvidenceEnvelope and (bullishDisplacement or bearishDisplacement)",
            "bool createBearishProximalFvg = activeEvidenceGeometryAvailable and barstate.isconfirmed and (bearishRunawayFromActiveDisplacement or bearishBreakerFvgQualified)",
            "bool createBullishProximalFvg = activeEvidenceGeometryAvailable and barstate.isconfirmed and (bullishRunawayFromActiveDisplacement or bullishBreakerFvgQualified)",
            "bool createBullishProximalVi = activeEvidenceGeometryAvailable and barstate.isconfirmed and bullishViSignal and viIntersectsEvidenceEnvelope",
            "bool createBearishProximalVi = activeEvidenceGeometryAvailable and barstate.isconfirmed and bearishViSignal and viIntersectsEvidenceEnvelope",
            "bool bullishActiveObQualified = activeEvidenceGeometryAvailable and newBullishObSignal and obIntersectsEvidenceEnvelope",
            "bool bearishActiveObQualified = activeEvidenceGeometryAvailable and newBearishObSignal and obIntersectsEvidenceEnvelope",
        )
        for predicate in required:
            self.assertIn(predicate, self.source)

    def test_all_four_types_classify_their_actual_structural_range(self) -> None:
        for call in (
            "f_classifyPdContext(low, high, proximalDisplacement)",
            "f_classifyPdContext(bearishFvgBottom, bearishFvgTop, createBearishProximalFvg)",
            "f_classifyPdContext(bullishFvgBottom, bullishFvgTop, createBullishProximalFvg)",
            "f_classifyPdContext(viBottom, viTop, createBullishProximalVi or createBearishProximalVi)",
            "f_classifyPdContext(obBottom, obTop, createBullishActiveOb or createBearishActiveOb)",
        ):
            self.assertIn(call, self.source)
        self.assertNotIn("f_classifyPdContext(displacementCe", self.source)
        self.assertNotIn("f_classifyPdContext(fvgCe", self.source)
        self.assertNotIn("f_classifyPdContext(viCe", self.source)
        self.assertNotIn("f_classifyPdContext(activeObCe", self.source)

    def test_tier_and_owner_are_stored_once_at_creation(self) -> None:
        for array_name in (
            "proximalDisplacementContextTiers",
            "proximalDisplacementContextOwners",
            "proximalFvgContextTiers",
            "proximalFvgContextOwners",
            "proximalViContextTiers",
            "proximalViContextOwners",
            "activeObContextTiers",
            "activeObContextOwners",
        ):
            self.assertIn(f"array.push({array_name}", self.source)
            self.assertNotIn(f"array.set({array_name}", self.source)

    def test_context_labels_and_diagnostics_are_exposed_without_new_colors(self) -> None:
        self.assertIn('f_pdContextLabel("FVG", fvgContextTier)', self.source)
        self.assertIn('f_pdContextLabel("VI", viContextTier)', self.source)
        self.assertIn("f_pdContextLabel(activeObBaseLabel, activeObContextTier)", self.source)
        self.assertIn('\\nTier: " + f_pdContextTierText(_tier)', self.source)
        self.assertIn('\\nOwner: " + f_pdContextOwnerText(_owner)', self.source)

    def test_existing_lifecycle_rules_are_unchanged(self) -> None:
        for rule in (
            "bar_index > creationBar and bodyTouchesCe",
            "fvgDirection == 1 ? close < fvgCe : close > fvgCe",
            "viDirection == 1 ? close < viCe : close > viCe",
            "activeObDirection == 1 ? close < activeObBottom : close > activeObTop",
        ):
            self.assertIn(rule, self.source)


if __name__ == "__main__":
    unittest.main()
