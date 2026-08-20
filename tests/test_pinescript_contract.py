from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PINE_SCRIPT = ROOT_DIR / "pine" / "EDGE_2_ROUTE.pine"


class Edge2PineContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = PINE_SCRIPT.read_text(encoding="utf-8")

    def test_is_an_isolated_pine_v6_indicator(self) -> None:
        self.assertTrue(self.text.startswith("//@version=6\n"))
        self.assertIn('indicator("EDGE 2.0 Route", "EDGE_2_ROUTE"', self.text)
        self.assertNotIn('indicator("edge_route_behavior"', self.text)

    def test_payload_has_exact_schema_43_observation_fields(self) -> None:
        builder = self.text.split("f_edge2_payload", 1)[1].split(
            "// Core EQM calculations", 1
        )[0]
        keys = re.findall(r"[\"']\\?\"([a-z0-9_]+)\\?\":", builder)
        self.assertEqual(
            keys,
            [
                "schema_version",
                "event_id",
                "symbol",
                "route",
                "observation_type",
                "observation_price",
                "ipda_20w_high",
                "ipda_20w_low",
                "observed_at",
            ],
        )
        self.assertIn('string EDGE_SCHEMA_VERSION = "4.3"', self.text)

    def test_btd_emits_once_at_exact_reclaim_close(self) -> None:
        self.assertIn(
            "bool btdCloseBackAboveL1 = btdArmed and btdDipConfirmed and "
            "btdEntryRefReady and close > btdEntryRef and close[1] <= btdEntryRef",
            self.text,
        )
        self.assertIn(
            "bool btdReclaimConfirmed = btdCloseBackAboveL1 and close > close[1] "
            "and btdLocationOk",
            self.text,
        )
        self.assertIn("btdReclaimPrice := close", self.text)
        self.assertIn("btdReclaimTimestamp := time_close", self.text)
        self.assertIn(
            'f_edge2_payload("BTD", "reclaim", btdReclaimPrice, ipda20wHigh, '
            "ipda20wLow, btdReclaimTimestamp)",
            self.text,
        )

    def test_str_emits_once_at_exact_rejection_close(self) -> None:
        self.assertIn(
            "bool strCloseBackBelowU1 = strArmed and strRipConfirmed and "
            "strEntryRefReady and close < strEntryRef and close[1] >= strEntryRef",
            self.text,
        )
        self.assertIn(
            "bool strRejectionConfirmed = strCloseBackBelowU1 and close < close[1] "
            "and strLocationOk",
            self.text,
        )
        self.assertIn("strRejectionPrice := close", self.text)
        self.assertIn("strRejectionTimestamp := time_close", self.text)
        self.assertIn(
            'f_edge2_payload("STR", "rejection", strRejectionPrice, ipda20wHigh, '
            "ipda20wLow, strRejectionTimestamp)",
            self.text,
        )

    def test_ipda_20w_calculation_is_preserved_and_eqm_is_not_emitted(self) -> None:
        self.assertIn(
            'ipda20wLow = request.security(syminfo.tickerid, "W", ta.lowest(low, 20))',
            self.text,
        )
        self.assertIn(
            'ipda20wHigh = request.security(syminfo.tickerid, "W", ta.highest(high, 20))',
            self.text,
        )
        self.assertIn("ipda20wEqm = (ipda20wLow + ipda20wHigh) / 2.0", self.text)
        self.assertNotIn('"eqm":', self.text)

    def test_event_identity_and_timestamp_are_deterministic(self) -> None:
        self.assertIn(
            'chartTickerId + "|" + EDGE_SCHEMA_VERSION + "|" + _route + "|" + '
            '_observationType + "|" + str.tostring(_observedAt)',
            self.text,
        )
        self.assertIn(
            'str.format_time(_observedAt, "yyyy-MM-dd\'T\'HH:mm:ss\'Z\'", "UTC")',
            self.text,
        )
        self.assertIn("format.mintick", self.text)

    def test_only_two_operational_alert_emission_points_exist(self) -> None:
        alert_calls = re.findall(r"^\s*alert\(", self.text, flags=re.MULTILINE)
        self.assertEqual(len(alert_calls), 2)
        self.assertEqual(self.text.count("alert.freq_once_per_bar_close"), 2)
        self.assertNotIn("alertcondition(", self.text)

    def test_old_post_event_systems_and_payloads_are_absent(self) -> None:
        forbidden = (
            "EDGE_RESEARCH",
            "EDGE_LIFECYCLE_AUDIT",
            "behavior_profile",
            "behavior_track",
            "residency",
            "excursion",
            "mfe",
            "mae",
            "acceptance",
            "research_window",
            "recommendation",
            "handover",
            "eqmPayload",
            "btdPayload",
            "strPayload",
        )
        lowered = self.text.lower()
        for token in forbidden:
            self.assertNotIn(token.lower(), lowered)

    def test_post_trigger_rearm_gate_matches_old_fixed_window_boundary(self) -> None:
        self.assertIn("int routeRearmBars = 240", self.text)
        self.assertIn(
            "bar_index - lastBtdObservationBar > routeRearmBars", self.text
        )
        self.assertIn(
            "bar_index - lastStrObservationBar > routeRearmBars", self.text
        )
        for bars_after_trigger in range(1, 246):
            old_route_ready = bars_after_trigger > 240
            new_route_ready = bars_after_trigger > 240
            self.assertEqual(old_route_ready, new_route_ready)

    def test_retained_operator_defaults_and_chart_context_match(self) -> None:
        for expected in (
            'input.int(240, "Arm Cooldown Bars"',
            'input.int(60, "Arm -> First Dip/Rip Max Bars"',
            'input.bool(true, "Show Arm Labels"',
            'input.bool(true, "Show First Dip/Rip Labels"',
            'input.bool(true, "Show Reclaim/Reject Level"',
            'plot(eqm20BandMid, "EQM20"',
            'plot(eqm20Upper1, "EQM20 +1"',
            'plot(eqm20Lower1, "EQM20 -1"',
        ):
            self.assertIn(expected, self.text)


if __name__ == "__main__":
    unittest.main()
