from __future__ import annotations

import re
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TRADE_DESK = ROOT_DIR / "pine" / "TradeDesk.pine"


@dataclass
class LiquidityObject:
    side: str
    source_bar: int
    detection_bar: int
    level: float
    zone_top: float
    zone_bottom: float
    breached: bool = False
    interaction_active: bool = False
    extension_right: int | None = None
    box_right: int | None = None
    events: int = 0

    @property
    def object_id(self) -> str:
        return f"{self.side}|{self.source_bar}|{self.detection_bar}|{self.level:.2f}"


class SourceFaithfulLiquidityReplay:
    """Small deterministic replay of the standalone per-object lifecycle."""

    def __init__(self, visible_levels: int = 3) -> None:
        self.visible_levels = visible_levels
        self.objects: dict[str, list[LiquidityObject]] = {"BSL": [], "SSL": []}
        self.events: list[tuple[str, int]] = []

    def detect(
        self,
        side: str,
        source_bar: int,
        detection_bar: int,
        level: float,
        zone_top: float,
        zone_bottom: float,
    ) -> LiquidityObject:
        objects = self.objects[side]
        if objects and objects[0].source_bar == source_bar:
            objects[0].zone_top = zone_top
            objects[0].zone_bottom = zone_bottom
            return objects[0]

        created = LiquidityObject(
            side,
            source_bar,
            detection_bar,
            level,
            zone_top,
            zone_bottom,
            extension_right=detection_bar,
        )
        objects.insert(0, created)
        del objects[self.visible_levels :]
        return created

    def confirmed_bar(
        self,
        side: str,
        bar_index: int,
        high: float,
        low: float,
        *,
        confirmed: bool = True,
        atr: float = 1.0,
        margin: float = 2.3,
    ) -> None:
        for obj in self.objects[side]:
            if not obj.breached:
                obj.extension_right = bar_index
                breached = (
                    high > obj.zone_top if side == "BSL" else low < obj.zone_bottom
                )
                if confirmed and breached:
                    obj.breached = True
                    obj.interaction_active = True
                    obj.events += 1
                    obj.box_right = bar_index + 1
                    self.events.append((obj.object_id, bar_index))
            elif obj.interaction_active:
                remains_inside = (
                    low > obj.level - margin * atr
                    and high < obj.level + margin * atr
                )
                if remains_inside:
                    obj.extension_right = bar_index + 1
                    obj.box_right = bar_index + 1
                else:
                    obj.interaction_active = False

    def nearest(self, side: str, close: float) -> float | None:
        candidates = [
            obj.level
            for obj in self.objects[side]
            if not obj.breached
            and ((side == "BSL" and obj.level > close) or (side == "SSL" and obj.level < close))
        ]
        if not candidates:
            return None
        return min(candidates) if side == "BSL" else max(candidates)


class TradeDeskExternalLiquidityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = TRADE_DESK.read_text(encoding="utf-8")

    def test_pine_uses_source_retention_and_no_consumed_area_abstraction(self) -> None:
        self.assertNotIn("extConsumed", self.text)
        self.assertNotIn("externalLiquidityRetainedLevels", self.text)
        self.assertEqual(
            self.text.count(
                "while array.size(extBslLevels) > externalLiquidityVisibleLevels"
            ),
            1,
        )
        self.assertEqual(
            self.text.count(
                "while array.size(extSslLevels) > externalLiquidityVisibleLevels"
            ),
            1,
        )

    def test_same_source_update_preserves_original_level(self) -> None:
        update_blocks = re.findall(
            r"if updateExisting\n(.*?)\n\s+else", self.text, flags=re.DOTALL
        )
        self.assertEqual(len(update_blocks), 2)
        self.assertNotIn("extBslLevels", update_blocks[0])
        self.assertNotIn("extSslLevels", update_blocks[1])
        self.assertIn("extBslZoneTops", update_blocks[0])
        self.assertIn("extSslZoneBottoms", update_blocks[1])

    def test_payload_and_tooltips_include_stable_source_identity(self) -> None:
        for field in (
            '"object_id"',
            '"source_bar"',
            '"detection_bar"',
            '"liquidity_level"',
            '"zone_top"',
            '"zone_bottom"',
            '"timeframe"',
            '"observed_at"',
            '"price"',
        ):
            self.assertIn(field, self.text)
        self.assertIn("Source Bar:", self.text)
        self.assertIn("Detected Bar:", self.text)

    def test_confirmed_breach_and_extension_contracts_are_explicit(self) -> None:
        self.assertIn(
            "not breached and barstate.isconfirmed and high > zoneTop", self.text
        )
        self.assertIn(
            "not breached and barstate.isconfirmed and low < zoneBottom", self.text
        )
        self.assertEqual(
            self.text.count(
                "breached and breachActive and not breachedThisBar ? bar_index + 1 : bar_index"
            ),
            2,
        )
        self.assertEqual(self.text.count("detectedBar + 11"), 4)


class TradeDeskExternalLiquidityReplayTests(unittest.TestCase):
    def test_eth_nearby_bsl_objects_remain_independent(self) -> None:
        replay = SourceFaithfulLiquidityReplay()
        breached = replay.detect("BSL", 2278, 2328, 2774.41, 2777.79, 2771.62)
        active = replay.detect("BSL", 1979, 2332, 2783.97, 2789.77, 2782.20)

        replay.confirmed_bar("BSL", 2332, high=2780.00, low=2775.00)

        self.assertTrue(breached.breached)
        self.assertFalse(active.breached)
        self.assertEqual(breached.events, 1)
        self.assertEqual(replay.nearest("BSL", close=2775.00), 2783.97)

    def test_nearby_ssl_objects_have_independent_lifecycles(self) -> None:
        replay = SourceFaithfulLiquidityReplay()
        active = replay.detect("SSL", 100, 120, 2710.0, 2712.0, 2708.0)
        breached = replay.detect("SSL", 105, 125, 2720.0, 2722.0, 2718.0)

        replay.confirmed_bar("SSL", 130, high=2720.0, low=2715.0)

        self.assertFalse(active.breached)
        self.assertTrue(breached.breached)
        self.assertEqual(replay.nearest("SSL", close=2730.0), 2710.0)

    def test_same_source_updates_bounds_but_preserves_identity_and_level(self) -> None:
        replay = SourceFaithfulLiquidityReplay()
        original = replay.detect("BSL", 50, 70, 100.25, 101.0, 99.0)
        updated = replay.detect("BSL", 50, 75, 100.75, 102.0, 98.0)

        self.assertIs(original, updated)
        self.assertEqual(updated.level, 100.25)
        self.assertEqual(updated.detection_bar, 70)
        self.assertEqual((updated.zone_top, updated.zone_bottom), (102.0, 98.0))

    def test_interaction_continues_then_rejects_and_never_restarts(self) -> None:
        replay = SourceFaithfulLiquidityReplay()
        obj = replay.detect("BSL", 10, 20, 100.0, 101.0, 99.0)
        replay.confirmed_bar("BSL", 30, high=102.0, low=100.0)
        self.assertEqual(obj.extension_right, 30)
        self.assertEqual(obj.box_right, 31)

        replay.confirmed_bar("BSL", 31, high=101.0, low=99.0)
        self.assertEqual(obj.extension_right, 32)
        replay.confirmed_bar("BSL", 32, high=103.0, low=99.0)
        frozen_extension = obj.extension_right
        frozen_box = obj.box_right
        self.assertFalse(obj.interaction_active)

        replay.confirmed_bar("BSL", 33, high=101.0, low=99.0)
        self.assertEqual(obj.extension_right, frozen_extension)
        self.assertEqual(obj.box_right, frozen_box)
        self.assertEqual(obj.events, 1)

    def test_pruned_ssl_cannot_emit_later_event(self) -> None:
        replay = SourceFaithfulLiquidityReplay(visible_levels=3)
        pruned = replay.detect("SSL", 1, 10, 2719.39, 2723.35, 2710.42)
        replay.detect("SSL", 2, 11, 2748.86, 2750.27, 2744.58)
        replay.detect("SSL", 3, 12, 2715.91, 2719.98, 2712.93)
        replay.detect("SSL", 4, 13, 2712.20, 2714.55, 2705.37)

        self.assertNotIn(pruned, replay.objects["SSL"])
        replay.confirmed_bar("SSL", 20, high=2720.0, low=2707.72)
        self.assertNotIn(pruned.object_id, [event[0] for event in replay.events])
        self.assertNotEqual(replay.nearest("SSL", close=2730.0), pruned.level)

    def test_far_apart_objects_and_confirmed_bar_timing(self) -> None:
        replay = SourceFaithfulLiquidityReplay()
        near = replay.detect("BSL", 1, 10, 100.0, 101.0, 99.0)
        far = replay.detect("BSL", 2, 11, 150.0, 151.0, 149.0)

        replay.confirmed_bar("BSL", 20, high=110.0, low=100.0, confirmed=False)
        self.assertFalse(near.breached)
        replay.confirmed_bar("BSL", 21, high=110.0, low=100.0, confirmed=True)

        self.assertTrue(near.breached)
        self.assertFalse(far.breached)
        self.assertEqual(replay.events, [(near.object_id, 21)])


if __name__ == "__main__":
    unittest.main()
