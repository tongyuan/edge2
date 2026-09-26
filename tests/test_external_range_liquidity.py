from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PINE_SCRIPT = ROOT_DIR / "pine" / "ExternalRangeLiquidity.pine"


@dataclass(frozen=True)
class Pivot:
    side: str
    level: float
    source_time: int


class ExternalRangeModel:
    """Small deterministic oracle for the Pine state-transition contract."""

    OPEN = "OPEN"
    PURGED = "PURGED"
    WAITING = "WAITING"

    def __init__(self) -> None:
        self.bsl: float | None = None
        self.ssl: float | None = None
        self.bsl_state = self.WAITING
        self.ssl_state = self.WAITING
        self.bsl_established: int | None = None
        self.ssl_established: int | None = None
        self.bsl_purged: int | None = None
        self.ssl_purged: int | None = None
        self.bsl_line_end: int | None = None
        self.ssl_line_end: int | None = None
        self.pending_high: Pivot | None = None
        self.pending_low: Pivot | None = None
        self.last_time: int | None = None

    def process(
        self,
        event_time: int,
        high: float,
        low: float,
        pivots: tuple[Pivot, ...] = (),
    ) -> None:
        if self.last_time is not None and event_time <= self.last_time:
            raise ValueError("source events must be strictly chronological")
        self.last_time = event_time

        hit_bsl = (
            self.bsl_state == self.OPEN
            and self.bsl_established is not None
            and self.bsl_established < event_time
            and high > self.bsl
        )
        hit_ssl = (
            self.ssl_state == self.OPEN
            and self.ssl_established is not None
            and self.ssl_established < event_time
            and low < self.ssl
        )
        if hit_bsl:
            self.bsl_state = self.PURGED
            self.bsl_purged = event_time
            self.bsl_line_end = event_time
            self.pending_high = None
        if hit_ssl:
            self.ssl_state = self.PURGED
            self.ssl_purged = event_time
            self.ssl_line_end = event_time
            self.pending_low = None

        for pivot in pivots:
            if pivot.side == "H":
                if self.bsl_state == self.OPEN:
                    if pivot.level > self.bsl:
                        self._establish_bsl(pivot, event_time)
                elif self.bsl_purged is None or event_time > self.bsl_purged:
                    if self.pending_high is None or pivot.level > self.pending_high.level:
                        self.pending_high = pivot
            elif pivot.side == "L":
                if self.ssl_state == self.OPEN:
                    if pivot.level < self.ssl:
                        self._establish_ssl(pivot, event_time)
                elif self.ssl_purged is None or event_time > self.ssl_purged:
                    if self.pending_low is None or pivot.level < self.pending_low.level:
                        self.pending_low = pivot
            else:
                raise ValueError(f"unsupported pivot side: {pivot.side}")

        if (
            self.bsl_state != self.OPEN
            and self.ssl_state != self.OPEN
            and self.pending_high is not None
            and self.pending_low is not None
            and self.pending_high.level > self.pending_low.level
        ):
            self._establish_bsl(self.pending_high, event_time)
            self._establish_ssl(self.pending_low, event_time)
            self.pending_high = None
            self.pending_low = None
        else:
            if (
                self.bsl_state != self.OPEN
                and self.ssl_state == self.OPEN
                and self.pending_high is not None
                and self.pending_high.level > self.ssl
            ):
                self._establish_bsl(self.pending_high, event_time)
                self.pending_high = None
            if (
                self.ssl_state != self.OPEN
                and self.bsl_state == self.OPEN
                and self.pending_low is not None
                and self.pending_low.level < self.bsl
            ):
                self._establish_ssl(self.pending_low, event_time)
                self.pending_low = None

    def _establish_bsl(self, pivot: Pivot, event_time: int) -> None:
        self.bsl = pivot.level
        self.bsl_state = self.OPEN
        self.bsl_established = event_time
        self.bsl_purged = None
        self.bsl_line_end = None

    def _establish_ssl(self, pivot: Pivot, event_time: int) -> None:
        self.ssl = pivot.level
        self.ssl_state = self.OPEN
        self.ssl_established = event_time
        self.ssl_purged = None
        self.ssl_line_end = None

    def snapshot(self) -> tuple[object, ...]:
        return (
            self.bsl,
            self.ssl,
            self.bsl_state,
            self.ssl_state,
            self.bsl_established,
            self.ssl_established,
            self.bsl_purged,
            self.ssl_purged,
            self.bsl_line_end,
            self.ssl_line_end,
        )


def bootstrap() -> ExternalRangeModel:
    model = ExternalRangeModel()
    model.process(10, 99, 95, (Pivot("H", 100, 1),))
    model.process(20, 98, 94, (Pivot("L", 90, 2),))
    return model


class ExternalRangeFixtureTests(unittest.TestCase):
    def test_first_alternating_high_low_bootstraps_range(self) -> None:
        model = bootstrap()
        self.assertEqual((model.bsl, model.ssl), (100, 90))
        self.assertEqual((model.bsl_state, model.ssl_state), (model.OPEN, model.OPEN))
        self.assertEqual((model.bsl_established, model.ssl_established), (20, 20))

    def test_stronger_same_side_pivot_replaces_pending_bootstrap_pivot(self) -> None:
        model = ExternalRangeModel()
        model.process(10, 90, 80, (Pivot("H", 100, 1),))
        model.process(20, 90, 80, (Pivot("H", 105, 2),))
        model.process(30, 90, 80, (Pivot("L", 90, 3),))
        self.assertEqual((model.bsl, model.ssl), (105, 90))

    def test_internal_high_does_not_replace_external_bsl(self) -> None:
        model = bootstrap()
        model.process(30, 99, 91, (Pivot("H", 97, 3),))
        self.assertEqual(model.bsl, 100)

    def test_internal_low_does_not_replace_external_ssl(self) -> None:
        model = bootstrap()
        model.process(30, 99, 91, (Pivot("L", 93, 3),))
        self.assertEqual(model.ssl, 90)

    def test_swing_above_bsl_expands_range_upward(self) -> None:
        model = bootstrap()
        model.process(30, 99, 91, (Pivot("H", 110, 3),))
        self.assertEqual((model.bsl, model.ssl), (110, 90))
        self.assertEqual(model.bsl_established, 30)

    def test_swing_below_ssl_expands_range_downward(self) -> None:
        model = bootstrap()
        model.process(30, 99, 91, (Pivot("L", 80, 3),))
        self.assertEqual((model.bsl, model.ssl), (100, 80))
        self.assertEqual(model.ssl_established, 30)

    def test_wick_above_bsl_purges_bsl(self) -> None:
        model = bootstrap()
        model.process(30, 101, 95)
        self.assertEqual((model.bsl_state, model.bsl_purged), (model.PURGED, 30))

    def test_wick_below_ssl_purges_ssl(self) -> None:
        model = bootstrap()
        model.process(30, 95, 89)
        self.assertEqual((model.ssl_state, model.ssl_purged), (model.PURGED, 30))

    def test_exact_touch_is_not_a_purge(self) -> None:
        model = bootstrap()
        model.process(30, 100, 90)
        self.assertEqual((model.bsl_state, model.ssl_state), (model.OPEN, model.OPEN))

    def test_purged_level_freezes_at_purge_time(self) -> None:
        model = bootstrap()
        model.process(30, 101, 95)
        model.process(40, 99, 95)
        self.assertEqual(model.bsl_line_end, 30)

    def test_level_cannot_be_swept_on_its_establishment_candle(self) -> None:
        model = ExternalRangeModel()
        model.process(
            10,
            200,
            1,
            (Pivot("H", 100, 1), Pivot("L", 90, 2)),
        )
        self.assertEqual((model.bsl_state, model.ssl_state), (model.OPEN, model.OPEN))
        self.assertIsNone(model.bsl_purged)
        self.assertIsNone(model.ssl_purged)

    def test_purged_side_reopens_only_from_later_confirmed_swing(self) -> None:
        model = bootstrap()
        model.process(30, 101, 95, (Pivot("H", 108, 3),))
        self.assertEqual(model.bsl_state, model.PURGED)
        model.process(40, 99, 95)
        self.assertEqual(model.bsl_state, model.PURGED)
        model.process(50, 99, 95, (Pivot("H", 106, 4),))
        self.assertEqual((model.bsl_state, model.bsl, model.bsl_established), (model.OPEN, 106, 50))

    def test_source_chronology_is_strict_and_deterministic(self) -> None:
        events = (
            (10, 99, 95, (Pivot("H", 100, 1),)),
            (20, 98, 94, (Pivot("L", 90, 2),)),
            (30, 100, 90, (Pivot("H", 97, 3), Pivot("L", 93, 3))),
            (40, 101, 95, ()),
            (50, 99, 95, (Pivot("H", 106, 4),)),
        )
        first = ExternalRangeModel()
        second = ExternalRangeModel()
        for event in events:
            first.process(*event)
            second.process(*event)
        self.assertEqual(first.snapshot(), second.snapshot())
        with self.assertRaises(ValueError):
            first.process(50, 99, 95)


class PineStaticContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PINE_SCRIPT.read_text(encoding="utf-8")

    def test_is_standalone_pine_v6_with_expected_defaults(self) -> None:
        self.assertTrue(self.text.startswith("//@version=6\n"))
        self.assertIn('indicator("External Range Liquidity"', self.text)
        self.assertIn('input.timeframe("240", "Source Timeframe"', self.text)
        self.assertIn('input.int(7, "Swing Length"', self.text)
        self.assertIn('input.bool(false, "Show Swing Markers"', self.text)
        self.assertIn('input.bool(false, "Show Establishment Labels"', self.text)
        self.assertIn('input.bool(true, "Show Purge Labels"', self.text)

    def test_mtf_feed_is_confirmed_and_has_no_lookahead(self) -> None:
        self.assertIn("request.security(", self.text)
        self.assertIn("lookahead=barmerge.lookahead_off", self.text)
        self.assertIn("high[1]", self.text)
        self.assertIn("low[1]", self.text)
        self.assertIn("ta.pivothigh(high, swingLength, swingLength)[1]", self.text)
        self.assertIn("ta.pivotlow(low, swingLength, swingLength)[1]", self.text)
        self.assertIn("chartSeconds <= sourceSeconds", self.text)

    def test_sweep_rules_are_strict_level_crosses(self) -> None:
        self.assertIn("sourceEventHigh > bslLevel", self.text)
        self.assertIn("sourceEventLow < sslLevel", self.text)
        self.assertNotIn("ta.atr", self.text)

    def test_no_hindsight_and_post_purge_confirmation_gates_are_explicit(self) -> None:
        self.assertIn("bslEstablishedTime < sourceEventTime", self.text)
        self.assertIn("sslEstablishedTime < sourceEventTime", self.text)
        self.assertIn("sourceEventTime > bslPurgeTime", self.text)
        self.assertIn("sourceEventTime > sslPurgeTime", self.text)

    def test_purged_lines_freeze_and_retention_is_bounded(self) -> None:
        self.assertIn("line.set_extend(bslOpenLine, extend.none)", self.text)
        self.assertIn("line.set_x2(bslOpenLine, sourceEventTime)", self.text)
        self.assertIn("line.set_extend(sslOpenLine, extend.none)", self.text)
        self.assertIn("line.set_x2(sslOpenLine, sourceEventTime)", self.text)
        self.assertIn("while array.size(lines) > limit", self.text)
        self.assertIn("line.delete(oldest)", self.text)

    def test_alertconditions_are_factual_and_complete(self) -> None:
        for title in (
            "EXTERNAL_BSL_PURGED",
            "EXTERNAL_SSL_PURGED",
            "EXTERNAL_BSL_ESTABLISHED",
            "EXTERNAL_SSL_ESTABLISHED",
        ):
            self.assertIn(f'alertcondition(', self.text)
            self.assertIn(f'"{title}"', self.text)
        self.assertNotIn("BUY", self.text)
        self.assertNotIn("SELL", self.text)

    def test_forbidden_pairing_and_research_systems_are_absent(self) -> None:
        lowered = self.text.lower()
        for token in (
            "parent_pair_id",
            "nearest-pair",
            "smallest-price-distance",
            "migration",
            "trade recommendation",
        ):
            self.assertNotIn(token, lowered)


if __name__ == "__main__":
    unittest.main()
