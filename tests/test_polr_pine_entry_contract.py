from __future__ import annotations

import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PINE_SCRIPT = ROOT_DIR / "pine" / "POLR.pine"


class POLRPineEntryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PINE_SCRIPT.read_text(encoding="utf-8")

    def test_canonical_script_is_present_and_parent_states_are_unchanged(self) -> None:
        self.assertGreaterEqual(len(self.text.splitlines()), 3704)
        self.assertIn("//@version=6", self.text)
        self.assertIn(
            "state: 0 idle · 1 armed (range + failed push) · 2 swept · 3 live (MSS confirmed) · 4 frozen · 5 dead",
            self.text,
        )

    def test_entry_options_have_safe_defaults(self) -> None:
        for expected in (
            "input.bool(true, 'Track entry lifecycle'",
            "input.string('A+', 'Required grade', options = ['Off', 'A', 'A+']",
            "input.bool(true, 'OTE required'",
            "input.string('CE_RECLAIM', 'Confirmation', options = ['CE_RECLAIM', 'PROXIMAL_RECLAIM']",
            "input.int(1, 'Maximum confirmed entries'",
            "input.bool(false, 'Allow re-entry after a stopped entry'",
        ):
            self.assertIn(expected, self.text)

    def test_eligibility_uses_live_flags_not_drawing_handles(self) -> None:
        for flag in (
            "fvgLive",
            "viLive",
            "sbLive",
            "ifvgLive",
            "brkLive",
            "oteLive",
        ):
            self.assertIn(flag, self.text)
        self.assertIn("not f_entrySourceLive(s)", self.text)
        self.assertIn("entryRequireOte and not s.oteLive", self.text)

    def test_touch_does_not_backdate_and_same_bar_can_confirm(self) -> None:
        self.assertIn("time >= s.oteConfirmedAt", self.text)
        self.assertIn("s.entryTouchedAt := time", self.text)
        touch = self.text.index("f_queueEntryEvent(events, 'ENTRY_TOUCHED', s)")
        confirm = self.text.index("f_queueEntryEvent(events, 'ENTRY_CONFIRMED', s)")
        self.assertLess(touch, confirm)

    def test_no_entry_marker_exists_before_confirmation(self) -> None:
        touched_block = self.text.split("if touched", 1)[1].split(
            "if s.entryState == 1", 1
        )[0]
        self.assertNotIn("entryMarker :=", touched_block)
        self.assertIn("s.entryMarker := f_lbl", self.text)

    def test_schema_1_1_keeps_setup_and_entry_rr_separate(self) -> None:
        self.assertIn('"schema_version":"1.1"', self.text)
        self.assertIn('"setup_rr":', self.text)
        self.assertIn('"entry_rr":', self.text)
        self.assertIn('"ote_confirmed_at":', self.text)
        self.assertIn("f_lifecycleSetupId(e.dir, e.mssAt) + '-E'", self.text)

    def test_script_is_observation_only(self) -> None:
        for forbidden in ("strategy.entry", "strategy.order", "strategy.exit"):
            self.assertNotIn(forbidden, self.text)


if __name__ == "__main__":
    unittest.main()
