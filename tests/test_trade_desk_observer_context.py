"""Source-backed TD_1.0 context replay, not a Pine compiler or TV server emulator.

Only the observer's scalar Pine subset is translated. Geometry, reset/contact
statements, helpers, payload builders and table expressions come from the actual
source; detection rules are not copied into a parallel observer implementation.
Inputs changing within a runner test the existing identity guard defensively.
Real TradingView input/symbol/timeframe changes restart a matching script run.
"""
from __future__ import annotations

import copy
import json
import os
import re
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("TRADE_DESK_PINE_SOURCE", ROOT / "pine/TradeDesk.pine"))


def outside_positions(text):
    """Characters outside quoted literals, preserving literal Pine JSON/text."""
    quote = None
    escaped = False
    for i, char in enumerate(text):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        else:
            yield i, char


def expression(text):
    """Translate nested Pine ternaries and the scalar names used by this block."""
    text = text.strip()
    chars = dict(outside_positions(text))
    # Translate parenthesized arguments/subexpressions first.
    start = None
    depth = 0
    pieces = []
    cursor = 0
    for i, char in chars.items():
        if char == "(":
            if depth == 0:
                start = i
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                pieces.append(text[cursor:start + 1])
                # Commas separate function arguments, not a ternary branch.
                inside = text[start + 1:i]
                arg_depth = 0
                arg_start = 0
                args = []
                for j, token in outside_positions(inside):
                    if token == "(":
                        arg_depth += 1
                    elif token == ")":
                        arg_depth -= 1
                    elif token == "," and arg_depth == 0:
                        args.append(expression(inside[arg_start:j]))
                        arg_start = j + 1
                args.append(expression(inside[arg_start:]))
                pieces.append(", ".join(args) + ")")
                cursor = i + 1
    if pieces:
        text = "".join(pieces) + text[cursor:]
    depth = 0
    question = None
    ternary_depth = 0
    for i, char in outside_positions(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and char == "?":
            if question is None:
                question = i
            ternary_depth += 1
        elif depth == 0 and char == ":" and question is not None:
            ternary_depth -= 1
            if ternary_depth == 0:
                return (f"({expression(text[question + 1:i])} if "
                        f"{expression(text[:question])} else {expression(text[i + 1:])})")
    # Never alter string literals while replacing Pine names.
    output = []
    cursor = 0
    for match in re.finditer(r"\b(?:true|false|na)\b", text):
        if match.start() not in dict(outside_positions(text)):
            continue
        output.append(text[cursor:match.start()])
        name = match.group()
        output.append({"true": "True", "false": "False"}.get(
            name, "is_na" if text[match.end():].lstrip().startswith("(") else "None"))
        cursor = match.end()
    return "".join(output) + text[cursor:]


def statements(source):
    result = []
    for line in source.splitlines():
        content = line.strip()
        if not content or content.startswith("//"):
            continue
        indent = line[:len(line) - len(line.lstrip())]
        if content.startswith("else if "):
            translated = "elif " + expression(content[8:]) + ":"
        elif content == "else":
            translated = "else:"
        elif content.startswith(("if ", "while ")):
            keyword, condition = content.split(" ", 1)
            translated = keyword + " " + expression(condition) + ":"
        else:
            content = re.sub(r"^(?:(?:const|var) )?(?:int|float|string|bool|label\[\]|label) ", "", content)
            content = content.replace(":=", "=")
            assignment = re.match(r"^(\w+\s*(?:\+=|=(?!=))\s*)(.*)$", content)
            translated = assignment[1] + expression(assignment[2]) if assignment else expression(content)
        result.append(indent + translated)
    return "\n".join(result)


class SourceObserver:
    def __init__(self, source):
        self.source = source
        self.alerts = []
        self.env = {
            "is_na": lambda value: value is None,
            "math": SimpleNamespace(min=min, max=max, round_to_mintick=lambda value:
                float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))),
            "format": SimpleNamespace(mintick="mintick"),
            "str": SimpleNamespace(tostring=lambda value, style=None:
                f"{value:.2f}" if style == "mintick" else str(value), format_time=self.format_time),
            "ticker": SimpleNamespace(standard=lambda symbol: symbol),
            "syminfo": SimpleNamespace(tickerid="BINANCE:SOLUSDT", ticker="SOLUSDT"),
            "timeframe": SimpleNamespace(period="1"),
            "barstate": SimpleNamespace(isconfirmed=True, islast=True, isrealtime=True),
            "array": SimpleNamespace(new_label=lambda: [], size=len, shift=lambda items: items.pop(0)),
            "label": SimpleNamespace(delete=lambda item: None),
            "alert": self.record_alert,
            "alert_frequency": "close",
            "f_alertSymbol": lambda: self.env["syminfo"].ticker,
            "configuredSymbol": "BINANCE:SOLUSDT", "activeMrzSlot": "A",
            # Bounds/slot observed in the two affected SOLUSDT alert-log entries.
            # Alert activation values were not exposed; replay activations are synthetic.
            "slotALower": 101.98, "slotAUpper": 102.32, "slotAActivationTime": 1,
            "slotBLower": 103.61, "slotBUpper": 104.04, "slotBActivationTime": 1,
            "showPreviousMrz": True, "showCurrentEnvelope": False,
            "showPreviousEnvelope": False, "showEqmProximalZone": True,
            "eqmProximalZoneWidthPercent": 50, "enableStateTransitionObserver": True,
            "enableAnchorTransitionAlerts": True, "enableSecondEqmContactAlert": True,
            "showStateDebugPanel": True, "ipda20Ready": False,
            "ipda20Low": None, "ipda20High": None, "ipda20Eqm": None,
            "ipda20Quarter": None, "ipda20ThreeQuarter": None,
        }
        constant_block = source.split("const int OBS_STATE_PRE_ACTIVATION", 1)[1].split("f_observerStateText", 1)[0]
        exec(statements("const int OBS_STATE_PRE_ACTIVATION" + constant_block), self.env)
        helpers = source.split("f_observerStateText", 1)[1].split("bool stateObserverGeometryAvailable", 1)[0]
        for block in re.split(r"\n(?=f_\w+\()", "f_observerStateText" + helpers):
            signature, body = block.split("=>", 1)
            body_lines = statements(body).splitlines()
            body_lines[-1] = "    return " + body_lines[-1].strip()
            exec("def " + signature.strip() + ":\n" + "\n".join(body_lines), self.env)
        initialization = source.split("var int observerState", 1)[1].split("bool observerCurrentMidReachedEvent", 1)[0]
        exec(statements("var int observerState" + initialization), self.env)
        self.geometry = statements("bool slotAIsActive" + source.split("bool slotAIsActive", 1)[1].split("int EQM_SIDE_UNKNOWN", 1)[0])
        self.widths = statements("float currentMrzWidth" + source.split("float currentMrzWidth", 1)[1].split("// Minimal direction-neutral", 1)[0])
        self.derived = statements("bool stateObserverGeometryAvailable" + source.split("bool stateObserverGeometryAvailable", 1)[1].split("var int observerState", 1)[0])
        self.core = statements("bool observerCurrentMidReachedEvent" + source.split("bool observerCurrentMidReachedEvent", 1)[1].split("if observerCurrentMidReachedEvent", 1)[0])
        emission = "if enableAnchorTransitionAlerts" + source.split("if enableAnchorTransitionAlerts", 1)[1].split("while array.size(observerStateLabels) > MAX_STATE_OBSERVER_LABELS", 1)[0]
        self.emission = statements(emission.replace("alert.freq_once_per_bar_close", "alert_frequency"))
        panel = source.split("var table stateObserverPanel", 1)[1].split("color currentUpperColor", 1)[0]
        self.panel_expressions = re.findall(r'table.cell\(stateObserverPanel, ([01]), (\d+), (.*?), text_color', panel)

    @staticmethod
    def format_time(value, pattern, zone):
        offset = -4 if zone == "UTC-4" else 0
        date = datetime.fromtimestamp(value / 1000, timezone(timedelta(hours=offset)))
        return date.strftime("%d %b %Y · %H:%M" if zone == "UTC-4" else "%Y-%m-%dT%H:%M:%SZ")

    def record_alert(self, payload, frequency):
        if self.env["barstate"].isrealtime:
            self.alerts.append(json.loads(payload))

    def bar(self, low, high=None, close=None, *, confirmed=True, realtime=True, **context):
        self.env.update(context)
        index = self.env.get("bar_index", -1) + 1
        self.env.update(low=low, high=low if high is None else high,
                        close=low if close is None else close, bar_index=index,
                        time=1000 + index * 60000, time_close=61000 + index * 60000,
                        barstate=SimpleNamespace(isconfirmed=confirmed, islast=True, isrealtime=realtime))
        self.alerts = []
        for block in (self.geometry, self.widths, self.derived, self.core, self.emission):
            exec(block, self.env)
        cells = {}
        if self.env["showStateDebugPanel"]:
            for column, row, value in self.panel_expressions:
                cells[int(column), int(row)] = eval(expression(value), self.env)
        panel = {cells[0, row]: value for (column, row), value in cells.items() if column == 1}
        return copy.deepcopy(panel), copy.deepcopy(self.alerts)


class TradeDeskContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text(encoding="utf-8")

    def new(self):
        observer = SourceObserver(self.source)
        observer.bar(101)  # Existing first-context baseline: no inferred contact.
        return observer

    def assert_reset(self, observer, panel, alerts):
        self.assertEqual(alerts, [])
        self.assertEqual(panel["Path Step #"], "0")
        self.assertEqual(panel["Distinct EQM Contacts"], "0")
        self.assertEqual(panel["Last Reached Anchor"], "NONE")
        self.assertEqual(panel["Previous Reached Anchor"], "NONE")
        self.assertEqual(panel["Last Contact"], "NONE")
        self.assertEqual(panel["Last Contact At"], "-")
        self.assertEqual(observer.env["observerStateLabels"], [])

    def assert_transition(self, observer, panel, alerts, expected_step, expected_anchor):
        payload = next(item for item in alerts if item["event_type"] == "MRZ_ANCHOR_TRANSITION")
        self.assertEqual(panel["Path Step #"], str(payload["path_step"]))
        self.assertEqual(payload["path_step"], expected_step)
        self.assertEqual(panel["Last Reached Anchor"], payload["last_reached_anchor"])
        self.assertEqual(payload["last_reached_anchor"], expected_anchor)
        self.assertEqual(panel["Last Contact"], payload["current_contact"])
        for key, variable in (("current_mrz_midpoint", "currentMrzMidpoint"),
                              ("previous_mrz_midpoint", "previousMrzMidpoint"),
                              ("migration_eqm", "migrationEqm")):
            self.assertEqual(payload[key], observer.env[variable])
        self.assertEqual(payload["observed_at"], observer.env["observerLastReachedAt"])
        self.assertEqual(panel["Last Contact At"], observer.env["f_observerPanelTimeText"](payload["observed_at"]))
        return payload

    def test_sol_geometry_and_migration_directions(self):
        observer = self.new()
        panel, _ = observer.bar(102.5)
        self.assertEqual((observer.env["currentMrzMidpoint"], observer.env["migrationEqm"], observer.env["previousMrzMidpoint"]), (102.15, 102.99, 103.83))
        self.assertEqual(panel["MRZ Migration"], "LOWER")
        self.assertEqual(panel["Lower Anchor"], "CURRENT MIDPOINT @ 102.15")
        panel, _ = observer.bar(102.5, activeMrzSlot="B")
        self.assertEqual(panel["MRZ Migration"], "HIGHER")
        panel, _ = observer.bar(102.5, slotALower=103.61, slotAUpper=104.04)
        self.assertEqual(panel["MRZ Migration"], "COINCIDENT")

    def test_sol_current_eqm_previous_steps_23_24_share_state(self):
        observer = self.new()
        for _ in range(22):
            observer.bar(102.14, 102.16, 102.15)
            observer.bar(101)
        panel, alerts = observer.bar(102.98, 103.0, 102.99)
        payload = self.assert_transition(observer, panel, alerts, 23, "MIGRATION EQM")
        self.assertEqual(payload["alert"], "SOLUSDT · CURRENT MID → EQM")
        self.assertEqual(panel["Previous Reached Anchor"], "CURRENT MRZ MIDPOINT")
        panel, alerts = observer.bar(103.82, 103.84, 103.83)
        payload = self.assert_transition(observer, panel, alerts, 24, "PREVIOUS MRZ MIDPOINT")
        self.assertEqual(payload["alert"], "SOLUSDT · EQM → PREV MID")
        self.assertEqual(panel["Previous Reached Anchor"], "MIGRATION EQM")
        self.assertNotIn("previous_reached_anchor", payload)  # Existing schema, not an invented field.

    def test_each_authoritative_identity_change_resets_and_baselines(self):
        changes = ({"slotALower": 101.9}, {"slotAUpper": 102.4}, {"slotAActivationTime": 2},
                   {"slotBLower": 103.6}, {"slotBUpper": 104.0}, {"slotBActivationTime": 2},
                   {"activeMrzSlot": "B"}, {"configuredSymbol": "BYBIT:SOLUSDT",
                    "syminfo": SimpleNamespace(tickerid="BYBIT:SOLUSDT", ticker="SOLUSDT")})
        for change in changes:
            with self.subTest(change=change):
                observer = self.new()
                observer.bar(102.98, 103.0, 102.99)
                observer.env["observerStateLabels"].append("old-context-label")
                panel, alerts = observer.bar(101, **change)
                self.assert_reset(observer, panel, alerts)
                midpoint = observer.env["currentMrzMidpoint"]
                panel, alerts = observer.bar(midpoint - .01, midpoint + .01, midpoint)
                self.assert_transition(observer, panel, alerts, 1, "CURRENT MRZ MIDPOINT")

    def test_wrong_symbol_invalid_bounds_and_before_activation_clear_state(self):
        for change in ({"configuredSymbol": "BINANCE:BTCUSDT"}, {"slotAUpper": 101.98},
                       {"slotBUpper": 103.61}, {"slotAActivationTime": 10**15}):
            with self.subTest(change=change):
                observer = self.new()
                observer.bar(102.98, 103.0, 102.99)
                panel, alerts = observer.bar(101, **change)
                self.assert_reset(observer, panel, alerts)
                self.assertEqual(panel["Observer Status"], "PRE_ACTIVATION")

    def test_reset_bar_contact_does_not_emit_or_count(self):
        observer = self.new()
        panel, alerts = observer.bar(102.19, 102.21, 102.2, slotAUpper=102.42)
        self.assert_reset(observer, panel, alerts)
        panel, alerts = observer.bar(102.19, 102.21, 102.2)
        self.assert_reset(observer, panel, alerts)
        observer.bar(101)
        panel, alerts = observer.bar(102.19, 102.21, 102.2)
        self.assert_transition(observer, panel, alerts, 1, "CURRENT MRZ MIDPOINT")

    def test_intrabar_no_path_mutation_and_close_has_post_update_table(self):
        observer = self.new()
        panel, alerts = observer.bar(102.14, 102.16, 102.15, confirmed=False)
        self.assert_reset(observer, panel, alerts)
        panel, alerts = observer.bar(102.14, 102.16, 102.15)
        self.assert_transition(observer, panel, alerts, 1, "CURRENT MRZ MIDPOINT")

    def test_raw_repeat_contacts_and_distinct_eqm_preserve_semantics(self):
        observer = self.new()
        observer.bar(102.98, 103.0, 102.99)
        observer.bar(101)
        panel, alerts = observer.bar(102.98, 103.0, 102.99)
        self.assertEqual(panel["Path Step #"], "2")
        self.assertEqual(panel["Distinct EQM Contacts"], "2")
        self.assertEqual([item["event_type"] for item in alerts], ["MRZ_SECOND_EQM_CONTACT"])
        self.assertEqual(alerts[0]["path_step"], 2)
        self.assertEqual(alerts[0]["eqm_contact_count"], 2)

    def test_replay_reload_and_timeframe_run_are_deterministic(self):
        bars = [(101,), (102.14, 102.16, 102.15), (102.98, 103.0, 102.99),
                (103.82, 103.84, 103.83)]
        def replay(period, realtime):
            observer = SourceObserver(self.source)
            observer.env["timeframe"] = SimpleNamespace(period=period)
            for bar in bars:
                panel, _ = observer.bar(*bar, realtime=realtime)
            return panel, observer
        first, _ = replay("1", True)
        reloaded, observer = replay("1", False)
        self.assertEqual(first, reloaded)
        self.assertEqual(observer.alerts, [])  # Historical replay does not notify.
        switched, _ = replay("5", False)  # A new run; actual new-timeframe OHLC can differ.
        self.assertEqual(switched, first)

    def test_observed_chart_and_saved_alert_contexts_reproduce_contradiction(self):
        alert_run = self.new()
        chart_run = SourceObserver(self.source)
        # Read-only chart Settings inspection: Slot B active, exactly these bounds.
        chart_run.env.update(activeMrzSlot="B", slotALower=99.63, slotAUpper=100.07,
                             slotBLower=101.28, slotBUpper=101.70)
        chart_run.bar(100)
        for _ in range(6):
            chart_run.bar(101.48, 101.50, 101.49)
            chart_run.bar(100)
        panel, _ = chart_run.bar(101.6)
        self.assertEqual(panel["Lower Anchor"], "CURRENT MIDPOINT @ 101.49")
        self.assertEqual(panel["MRZ Migration"], "HIGHER")
        self.assertEqual(chart_run.env["previousMrzMidpoint"], 99.85)
        self.assertEqual(chart_run.env["migrationEqm"], 100.67)
        self.assertEqual(panel["Path Step #"], "6")
        self.assertEqual(panel["Previous Reached Anchor"], "CURRENT MRZ MIDPOINT")
        _, alerts = alert_run.bar(102.98, 103.0, 102.99)
        self.assertEqual(alerts[0]["current_mrz_midpoint"], 102.15)
        # Bounds were observed live; bars, activation values and counts here are
        # deterministic synthetic replay, NOT a recovery of real chart OHLC.

    def test_single_definitions_execution_order_and_existing_identity(self):
        for variable in ("currentMrzMidpoint", "previousMrzMidpoint", "migrationEqm"):
            self.assertEqual(len(re.findall(r"^float " + variable + r" =", self.source, re.M)), 1)
        self.assertIn("string observerMrzMigration =", self.source)
        self.assertNotIn("var string observerMrzMigration", self.source)
        self.assertNotIn("barstate.isnew", self.source)
        mutation = self.source.index("observerObservedPathSteps += 1")
        emission = self.source.index("if enableAnchorTransitionAlerts")
        render = self.source.index("if barstate.islast and showStateDebugPanel")
        self.assertLess(mutation, emission)
        self.assertLess(emission, render)
        for field in ("ActiveMrzSlot", "TickerId", "CurrentLower", "CurrentUpper",
                      "CurrentActivation", "PreviousLower", "PreviousUpper", "PreviousActivation"):
            self.assertIn("observerStored" + field + " !=", self.source)


if __name__ == "__main__":
    unittest.main()
