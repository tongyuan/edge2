from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TRADE_DESK = ROOT_DIR / "pine" / "TradeDesk.pine"


@dataclass
class InteractionObject:
    side: str
    source_bar: int
    detection_bar: int
    level: float
    zone_top: float
    zone_bottom: float
    breached: bool = False
    active: bool = False
    start_bar: int | None = None
    start_time: int | None = None
    box_top: float | None = None
    box_bottom: float | None = None
    completions: int = 0
    labels: int = 0

    @property
    def object_id(self) -> str:
        return f"{self.side}|{self.source_bar}|{self.detection_bar}|{self.level:.2f}"


class InteractionCompletionReplay:
    def __init__(self, retention: int = 3) -> None:
        self.retention = retention
        self.objects: dict[str, list[InteractionObject]] = {"BSL": [], "SSL": []}
        self.alerts: list[dict[str, object]] = []
        self.labels: list[dict[str, object]] = []

    def add(self, obj: InteractionObject) -> None:
        self.objects[obj.side].insert(0, obj)
        del self.objects[obj.side][self.retention :]

    def bar(
        self,
        side: str,
        bar_index: int,
        *,
        high: float,
        low: float,
        confirmed: bool = True,
        timestamp: int | None = None,
        atr: float = 1.0,
        margin: float = 2.3,
        alerts_enabled: bool = True,
        labels_enabled: bool = True,
    ) -> None:
        timestamp = bar_index * 60_000 if timestamp is None else timestamp
        for obj in self.objects[side]:
            if not obj.breached:
                breach = high > obj.zone_top if side == "BSL" else low < obj.zone_bottom
                if confirmed and breach:
                    obj.breached = True
                    obj.active = True
                    obj.start_bar = bar_index
                    obj.start_time = timestamp
                    if side == "BSL":
                        obj.box_top = min(obj.level + margin * atr, high)
                        obj.box_bottom = obj.level
                    else:
                        obj.box_top = obj.level
                        obj.box_bottom = max(obj.level - margin * atr, low)
                continue

            if not obj.active or not confirmed:
                continue

            remains_inside = low > obj.level - margin * atr and high < obj.level + margin * atr
            if remains_inside:
                if side == "BSL":
                    obj.box_top = max(obj.box_top or obj.level, min(obj.level + margin * atr, high))
                else:
                    obj.box_bottom = min(obj.box_bottom or obj.level, max(obj.level - margin * atr, low))
                continue

            obj.active = False
            obj.completions += 1
            payload: dict[str, object] = {
                "schema_version": "1.0",
                "event_type": f"{side}_INTERACTION_COMPLETE",
                "liquidity_side": side,
                "object_id": obj.object_id,
                "source_bar": obj.source_bar,
                "detection_bar": obj.detection_bar,
                "liquidity_level": obj.level,
                "interaction_start_bar": obj.start_bar,
                "interaction_end_bar": bar_index,
                "interaction_duration_bars": bar_index - int(obj.start_bar),
                "interaction_box_top": obj.box_top,
                "interaction_box_bottom": obj.box_bottom,
            }
            if alerts_enabled:
                self.alerts.append(payload)
            if labels_enabled:
                obj.labels += 1
                self.labels.append(
                    {
                        "text": f"{side} IC",
                        "bar_index": bar_index,
                        "placement": "above" if side == "BSL" else "below",
                        "tooltip": payload,
                    }
                )


def liquidity_object(side: str, source_bar: int = 10, detection_bar: int = 20) -> InteractionObject:
    return InteractionObject(
        side=side,
        source_bar=source_bar,
        detection_bar=detection_bar,
        level=100.0,
        zone_top=101.0,
        zone_bottom=99.0,
    )


class InteractionCompletionReplayTests(unittest.TestCase):
    def test_bsl_starts_and_continues_without_completion_then_emits_once(self) -> None:
        replay = InteractionCompletionReplay()
        obj = liquidity_object("BSL")
        replay.add(obj)

        replay.bar("BSL", 30, high=102.0, low=100.0)
        self.assertTrue(obj.active)
        self.assertEqual(replay.alerts, [])
        self.assertEqual(replay.labels, [])

        replay.bar("BSL", 31, high=101.5, low=99.5)
        replay.bar("BSL", 32, high=101.8, low=99.4)
        self.assertTrue(obj.active)
        self.assertEqual(replay.alerts, [])

        frozen_top = obj.box_top
        frozen_bottom = obj.box_bottom
        replay.bar("BSL", 33, high=103.0, low=99.0)
        self.assertFalse(obj.active)
        self.assertEqual(obj.completions, 1)
        self.assertEqual(len(replay.alerts), 1)
        self.assertEqual(len(replay.labels), 1)
        self.assertEqual(replay.labels[0]["bar_index"], 33)
        self.assertEqual(replay.labels[0]["placement"], "above")
        self.assertEqual(replay.alerts[0]["interaction_box_top"], frozen_top)
        self.assertEqual(replay.alerts[0]["interaction_box_bottom"], frozen_bottom)

        replay.bar("BSL", 34, high=104.0, low=98.0)
        self.assertEqual(len(replay.alerts), 1)
        self.assertEqual(len(replay.labels), 1)

    def test_ssl_completion_is_mirrored_and_label_is_on_completion_candle(self) -> None:
        replay = InteractionCompletionReplay()
        obj = liquidity_object("SSL")
        replay.add(obj)
        replay.bar("SSL", 40, high=100.0, low=98.0)
        replay.bar("SSL", 41, high=100.5, low=98.5)
        replay.bar("SSL", 42, high=101.0, low=97.0)

        self.assertEqual(obj.completions, 1)
        self.assertEqual(replay.alerts[0]["event_type"], "SSL_INTERACTION_COMPLETE")
        self.assertEqual(replay.labels[0]["text"], "SSL IC")
        self.assertEqual(replay.labels[0]["bar_index"], 42)
        self.assertEqual(replay.labels[0]["placement"], "below")

    def test_unconfirmed_excursion_does_not_complete(self) -> None:
        replay = InteractionCompletionReplay()
        obj = liquidity_object("BSL")
        replay.add(obj)
        replay.bar("BSL", 30, high=102.0, low=100.0)
        replay.bar("BSL", 31, high=104.0, low=98.0, confirmed=False)
        self.assertTrue(obj.active)
        self.assertEqual(obj.completions, 0)
        self.assertEqual(replay.alerts, [])

    def test_nearby_objects_complete_independently(self) -> None:
        replay = InteractionCompletionReplay()
        first = liquidity_object("BSL", source_bar=10, detection_bar=20)
        second = InteractionObject("BSL", 11, 21, 100.4, 101.4, 99.4)
        replay.add(first)
        replay.add(second)
        replay.bar("BSL", 30, high=102.0, low=100.0)
        replay.bar("BSL", 31, high=103.0, low=99.8)
        completed_ids = {event["object_id"] for event in replay.alerts}
        self.assertEqual(completed_ids, {first.object_id, second.object_id})

    def test_nearby_ssl_objects_complete_independently(self) -> None:
        replay = InteractionCompletionReplay()
        first = liquidity_object("SSL", source_bar=10, detection_bar=20)
        second = InteractionObject("SSL", 11, 21, 99.6, 100.6, 98.6)
        replay.add(first)
        replay.add(second)
        replay.bar("SSL", 30, high=100.0, low=98.0)
        replay.bar("SSL", 31, high=100.2, low=97.0)
        completed_ids = {event["object_id"] for event in replay.alerts}
        self.assertEqual(completed_ids, {first.object_id, second.object_id})

    def test_pruned_object_cannot_complete(self) -> None:
        replay = InteractionCompletionReplay(retention=1)
        pruned = liquidity_object("BSL", source_bar=1, detection_bar=10)
        retained = liquidity_object("BSL", source_bar=2, detection_bar=11)
        replay.add(pruned)
        replay.add(retained)
        replay.bar("BSL", 30, high=102.0, low=100.0)
        replay.bar("BSL", 31, high=103.0, low=99.0)
        self.assertNotIn(pruned.object_id, {event["object_id"] for event in replay.alerts})

    def test_payload_identity_geometry_and_duration_are_exact(self) -> None:
        replay = InteractionCompletionReplay()
        obj = liquidity_object("BSL", source_bar=7, detection_bar=15)
        replay.add(obj)
        replay.bar("BSL", 20, high=102.0, low=100.0)
        replay.bar("BSL", 21, high=101.7, low=99.5)
        replay.bar("BSL", 24, high=103.0, low=99.0)
        payload = replay.alerts[0]
        self.assertEqual(payload["object_id"], "BSL|7|15|100.00")
        self.assertEqual(payload["source_bar"], 7)
        self.assertEqual(payload["detection_bar"], 15)
        self.assertEqual(payload["interaction_duration_bars"], 4)
        self.assertEqual(payload["interaction_box_top"], obj.box_top)
        self.assertEqual(payload["interaction_box_bottom"], obj.box_bottom)
        self.assertEqual(replay.labels[0]["tooltip"], payload)

    def test_label_toggle_does_not_change_alert_or_lifecycle(self) -> None:
        replay = InteractionCompletionReplay()
        obj = liquidity_object("SSL")
        replay.add(obj)
        replay.bar("SSL", 30, high=100.0, low=98.0, labels_enabled=False)
        replay.bar("SSL", 31, high=101.0, low=97.0, labels_enabled=False)
        self.assertFalse(obj.active)
        self.assertEqual(obj.completions, 1)
        self.assertEqual(len(replay.alerts), 1)
        self.assertEqual(replay.labels, [])


class InteractionCompletionPineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = TRADE_DESK.read_text(encoding="utf-8")
        cls.external = cls.source.split("// EXTERNAL LIQUIDITY CONTEXT", 1)[1].split(
            "// Minimal direction-neutral", 1
        )[0]

    def test_inputs_default_true(self) -> None:
        self.assertIn(
            'input.bool(true, "Enable BSL / SSL Interaction Complete Alerts", group = GROUP_EXTERNAL_LIQUIDITY)',
            self.source,
        )
        self.assertIn(
            'input.bool(true, "Show Interaction Complete Labels", group = GROUP_EXTERNAL_LIQUIDITY)',
            self.source,
        )

    def test_only_requested_liquidity_event_vocabulary_exists(self) -> None:
        self.assertIn("BSL_INTERACTION_COMPLETE", self.external)
        self.assertIn("SSL_INTERACTION_COMPLETE", self.external)
        for forbidden in (
            "BSL_BREACHED",
            "SSL_BREACHED",
            "BSL_REJECTED",
            "SSL_REJECTED",
            "BSL_ACCEPTED",
            "SSL_ACCEPTED",
        ):
            self.assertNotIn(forbidden, self.source)

    def test_completion_is_confirmed_and_uses_unchanged_continuation_formula(self) -> None:
        self.assertEqual(
            self.external.count("else if breached and breachActive and barstate.isconfirmed"),
            2,
        )
        self.assertIn(
            "low > level - buysideBreachAtrMargin * externalLiquidityAtr and high < level + buysideBreachAtrMargin * externalLiquidityAtr",
            self.external,
        )
        self.assertIn(
            "low > level - sellsideBreachAtrMargin * externalLiquidityAtr and high < level + sellsideBreachAtrMargin * externalLiquidityAtr",
            self.external,
        )
        self.assertEqual(self.external.count("interactionCompletedOnCurrentBar := true"), 2)

    def test_alerts_are_one_shot_transition_consumers_and_allow_independent_objects(self) -> None:
        self.assertEqual(
            self.external.count("alert(interactionCompletePayload, alert.freq_all)"), 2
        )
        self.assertNotIn("array index", self.external)
        self.assertIn('f_externalLiquidityObjectId("BSL", sourceBar, detectionBar, level)', self.external)
        self.assertIn('f_externalLiquidityObjectId("SSL", sourceBar, detectionBar, level)', self.external)

    def test_payload_schema_contains_required_episode_identity_and_geometry(self) -> None:
        for field in (
            "schema_version",
            "event_type",
            "symbol",
            "liquidity_side",
            "object_id",
            "source_bar",
            "detection_bar",
            "liquidity_level",
            "detection_zone_top",
            "detection_zone_bottom",
            "interaction_start_bar",
            "interaction_start_time",
            "interaction_end_bar",
            "interaction_end_time",
            "interaction_duration_bars",
            "interaction_box_top",
            "interaction_box_bottom",
            "timeframe",
            "observed_at",
            "price",
        ):
            self.assertIn(f'"{field}"', self.external)

    def test_labels_are_compact_on_completion_bar_with_identity_tooltip(self) -> None:
        self.assertIn("max_labels_count = 500", self.source)
        self.assertIn('label.new(bar_index, high, "BSL IC"', self.external)
        self.assertIn("style = label.style_label_down", self.external)
        self.assertIn('label.new(bar_index, low, "SSL IC"', self.external)
        self.assertIn("style = label.style_label_up", self.external)
        self.assertIn("f_externalLiquidityInteractionCompleteTooltip", self.external)

    def test_start_geometry_and_label_handles_follow_object_retention(self) -> None:
        for side in ("Bsl", "Ssl"):
            for suffix in (
                "InteractionStartBars",
                "InteractionStartTimes",
                "InteractionBoxTops",
                "InteractionBoxBottoms",
                "InteractionCompleteLabels",
            ):
                name = f"ext{side}{suffix}"
                declaration_type = "label[]" if suffix == "InteractionCompleteLabels" else (
                    "float[]" if "Box" in suffix else "int[]"
                )
                self.assertIn(f"var {declaration_type} {name}", self.source)
                self.assertIn(f"array.unshift({name}", self.external)
                self.assertIn(f"array.pop({name})", self.external)


if __name__ == "__main__":
    unittest.main()
