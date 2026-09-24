from __future__ import annotations

import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TRADE_DESK = ROOT_DIR / "pine" / "TradeDesk.pine"


def label_center(left: int, right: int) -> int:
    return left + (right - left) // 2


class PdLabelPositioningBehaviorTests(unittest.TestCase):
    def test_even_width_uses_exact_horizontal_midpoint(self) -> None:
        self.assertEqual(label_center(10, 20), 15)

    def test_odd_width_rounds_down_like_pine_math_floor(self) -> None:
        self.assertEqual(label_center(10, 21), 15)

    def test_active_geometry_center_moves_with_right_edge(self) -> None:
        self.assertEqual(label_center(10, 20), 15)
        self.assertEqual(label_center(10, 30), 20)

    def test_terminal_geometry_center_freezes_at_terminal_edge(self) -> None:
        terminal_right = 26
        frozen_center = label_center(10, terminal_right)
        self.assertEqual(frozen_center, 18)
        self.assertEqual(label_center(10, terminal_right), frozen_center)

    def test_time_coordinates_use_the_same_geometry_midpoint(self) -> None:
        left_time = 1_788_912_000_000
        right_time = left_time + 600_000
        self.assertEqual(label_center(left_time, right_time), left_time + 300_000)


class TradeDeskPdLabelPositioningPineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = TRADE_DESK.read_text(encoding="utf-8")

    def test_shared_center_helper_uses_required_floor_formula(self) -> None:
        self.assertIn("f_pdLabelCenter(int _left, int _right) =>", self.source)
        self.assertIn("_left + int(math.floor((_right - _left) / 2.0))", self.source)

    def test_fvg_label_tracks_live_edge_and_freezes_at_mitigation(self) -> None:
        for statement in (
            "int fvgDisplayedRightBar = fvgMitigated and not na(fvgMitigationBar) ? fvgMitigationBar : bar_index",
            "int fvgLabelCenterBar = f_pdLabelCenter(fvgCreationBar, fvgDisplayedRightBar)",
            "label.new(fvgLabelCenterBar, fvgCe, fvgLabelText",
            "label.set_x(fvgLabel, fvgLabelCenterBar)",
        ):
            self.assertIn(statement, self.source)

    def test_vi_label_tracks_live_edge_and_freezes_at_mitigation(self) -> None:
        for statement in (
            "int viDisplayedRightBar = viMitigated and not na(viMitigationBar) ? viMitigationBar : bar_index",
            "int viLabelCenterBar = f_pdLabelCenter(viCreationBar, viDisplayedRightBar)",
            "label.new(viLabelCenterBar, viCe, viLabelText",
            "label.set_x(viLabel, viLabelCenterBar)",
        ):
            self.assertIn(statement, self.source)

    def test_ob_label_tracks_box_time_geometry(self) -> None:
        for statement in (
            "int activeObLabelCenterTime = f_pdLabelCenter(activeObLeftTime, time)",
            "label.new(activeObLabelCenterTime, activeObCe, activeObLabelText",
            "label.set_x(activeObLabel, activeObLabelCenterTime)",
        ):
            self.assertIn(statement, self.source)

    def test_labels_keep_existing_visibility_gates(self) -> None:
        for gate in (
            "showProximalFvg and showFvgLabels and fvgPresentationVisible",
            "showProximalVi and showViLabels and viPresentationVisible",
            "showActiveOb and showObLabels and activeObPresentationVisible",
        ):
            self.assertIn(gate, self.source)

    def test_displacement_has_no_pd_label_to_reposition(self) -> None:
        displacement_section = self.source.split("// One confirmed retained displacement", 1)[1].split(
            "// Canonical chart-timeframe FVG", 1
        )[0]
        self.assertNotIn("label.new", displacement_section)


if __name__ == "__main__":
    unittest.main()
