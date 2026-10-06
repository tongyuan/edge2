from __future__ import annotations

import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PINE_SCRIPT = ROOT_DIR / "pine" / "TradeDesk.pine"


class TradeDeskPineResultContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PINE_SCRIPT.read_text(encoding="utf-8")

    def test_schema_1_2_and_reach_event_are_emitted(self) -> None:
        self.assertIn('"schema_version":"1.2"', self.text)
        self.assertIn("'ENTRY_EXIT_LEVEL_REACHED'", self.text)
        self.assertIn("e.eventType + e.eventSuffix", self.text)
        self.assertIn("reached.eventSuffix := '-L' + str.tostring(mask)", self.text)
        self.assertIn('"contact_mode":"', self.text)

    def test_all_eleven_frozen_level_identities_are_present(self) -> None:
        identities = (
            "C-MID,C-2W,C-1W,C+1W,C+2W,EQM,"
            "P-MID,P-2W,P-1W,P+1W,P+2W"
        )
        self.assertIn(identities, self.text)
        self.assertIn("frozen_exit_ladder", self.text)
        self.assertIn("destination_order", self.text)

    def test_result_identity_includes_attempt(self) -> None:
        find = self.text.split("f_resultFind(Setup s) =>", 1)[1].split(
            "f_exitEligible", 1
        )[0]
        self.assertIn("x.dir == s.dir", find)
        self.assertIn("x.mssAt == s.mssTm", find)
        self.assertIn("x.attempt == s.entryAttempt", find)

    def test_ladder_is_frozen_once_at_confirmation(self) -> None:
        opened = self.text.split("f_resultOpen(Setup s) =>", 1)[1].split(
            "f_resultR", 1
        )[0]
        self.assertIn("mrzGeometryAvailable ? array.from(", opened)
        self.assertIn("contextId = mrzGeometryAvailable ? mrzContextId", opened)
        self.assertIn("prices = prices", opened)
        confirmation = self.text.index("ExitState result = f_resultOpen(s)")
        confirmed_event = self.text.index(
            "f_queueEntryEvent(events, 'ENTRY_CONFIRMED', s)"
        )
        self.assertLess(confirmation, confirmed_event)

        advance = self.text.split("f_resultAdvance", 1)[1].split(
            "f_resultTerminal", 1
        )[0]
        display = self.text.split("f_exitStep(ExitState x, Setup s) =>", 1)[1]
        for mutable_name in (
            "currentMrzMidpoint",
            "previousMrzMidpoint",
            "migrationEqm",
            "mrzContextId",
        ):
            self.assertNotIn(mutable_name, advance)
            self.assertNotIn(mutable_name, display)

    def test_confirmation_candle_is_excluded(self) -> None:
        before_call = self.text.index("f_entryBeforeSetup(bull, entryEvents)")
        after_call = self.text.index("f_updateEntry(bull, entryEvents")
        self.assertLess(before_call, after_call)
        opened = self.text.split("f_resultOpen(Setup s) =>", 1)[1].split(
            "f_resultR", 1
        )[0]
        self.assertIn("mfePrice = s.entryPrice, maePrice = s.entryPrice", opened)
        self.assertNotIn("high", opened)
        self.assertNotIn("low", opened)

    def test_excursion_formulas_are_directional_and_nonnegative(self) -> None:
        result_r = self.text.split("f_resultR", 1)[1].split(
            "f_ladderJson", 1
        )[0]
        self.assertIn("math.max(0.0", result_r)
        self.assertIn("x.dir * (p - x.entryPrice)", result_r)
        advance = self.text.split("f_resultAdvance", 1)[1].split(
            "f_resultTerminal", 1
        )[0]
        self.assertIn("math.max(x.mfePrice, high)", advance)
        self.assertIn("math.min(x.mfePrice, low)", advance)
        self.assertIn("math.min(x.maePrice, low)", advance)
        self.assertIn("math.max(x.maePrice, high)", advance)

    def test_terminal_snapshot_precedes_inclusive_bar_processing(self) -> None:
        terminal = self.text.split("f_resultTerminal(Setup s) =>", 1)[1].split(
            "f_entryInvalidate", 1
        )[0]
        self.assertIn('"mfe_pre_terminal_price":', terminal)
        self.assertIn('"mfe_inclusive_price":', terminal)
        self.assertIn('"terminal_bar_levels_touched":', terminal)
        self.assertIn("f_terminalLevels(x)", terminal)
        terminal_levels = self.text.split("f_terminalLevels", 1)[1].split(
            "f_resultAdvance", 1
        )[0]
        self.assertNotIn("f_exitEligible", terminal_levels)
        before = self.text.split("f_entryBeforeSetup", 1)[1].split(
            "f_entryAfterSetup", 1
        )[0]
        self.assertLess(before.index("f_resultTerminal(s)"), before.index("s.entryState := 6"))
        self.assertNotIn("f_resultAdvance(s, events)", before.split("if stopHit and targetHit", 1)[1].split("else", 1)[0])

    def test_setup_udt_was_not_extended_with_result_fields(self) -> None:
        setup = self.text.split("type Setup", 1)[1].split("type Ev", 1)[0]
        for forbidden in (
            "initialRisk",
            "mfePrice",
            "maePrice",
            "reachedMask",
            "frozenExitLadder",
        ):
            self.assertNotIn(forbidden, setup)


if __name__ == "__main__":
    unittest.main()
