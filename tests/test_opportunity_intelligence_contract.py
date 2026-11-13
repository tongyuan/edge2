from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "app/api.py").read_text(encoding="utf-8")
REPOSITORY = (ROOT / "app/repository.py").read_text(encoding="utf-8")
ENGINE = (ROOT / "app/opportunity_intelligence.py").read_text(encoding="utf-8")
HTML = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
GROUP_JS = (ROOT / "app/static/group-evidence.js").read_text(encoding="utf-8")
MAP_JS = (ROOT / "app/static/opportunity-map.js").read_text(encoding="utf-8")
COMPARISON_JS = (ROOT / "app/static/opportunity-comparison.js").read_text(encoding="utf-8")
MAP_CSS = (ROOT / "app/static/opportunity-map.css").read_text(encoding="utf-8")


class OpportunityIntelligenceContractTests(unittest.TestCase):
    def test_api_is_read_only_and_supports_replay(self) -> None:
        self.assertIn('@application.get("/api/opportunities")', API)
        self.assertIn('@application.get("/api/opportunities/compare")', API)
        self.assertIn('@application.get("/api/opportunities/{symbol}")', API)
        self.assertIn("as_known_at: datetime | None", API)
        for verb in ("post", "put", "patch", "delete"):
            self.assertNotIn(f'@application.{verb}("/api/opportunities', API)
        self.assertIn('"Cache-Control": "no-store, max-age=0"', API)

    def test_repository_projection_is_one_repeatable_read_snapshot(self) -> None:
        method = REPOSITORY.split("def opportunity_intelligence_inputs", 1)[1].split(
            "def activation_feasibility_inputs", 1
        )[0]
        self.assertIn("readonly=True", method)
        self.assertIn('isolation_level="REPEATABLE READ"', method)
        self.assertIn("transaction_timestamp() AS as_of", method)
        self.assertIn("trigger.received_at AS trigger_received_at", method)
        for forbidden in ("INSERT INTO", "UPDATE ", "DELETE FROM", "ALTER TABLE"):
            self.assertNotIn(forbidden, method)

    def test_engine_keeps_canonical_time_and_research_only_semantics(self) -> None:
        for required in (
            '"effective_at"',
            '"known_at"',
            '"CONFLICTING_EVIDENCE"',
            '"STRUCTURAL_DEVELOPMENT"',
            '"HISTORICAL_OUTCOME_EVIDENCE"',
            '"NOT_VERIFIED"',
            '"RECONSTRUCTED_AS_KNOWN_AT"',
            '"not_connected"',
        ):
            self.assertIn(required, ENGINE)
        for forbidden in ('"BUY"', '"SELL"', '"ACTION_NOW"', '"score"'):
            self.assertNotIn(forbidden, ENGINE)

    def test_group_radar_contains_map_replay_assessment_and_mobile_layout(self) -> None:
        self.assertIn("opportunity-map.css", HTML)
        self.assertIn("opportunity-map.js", HTML)
        self.assertIn("/api/opportunities", GROUP_JS)
        for copy in (
            "Opportunity Map (Time × Price)",
            "Historical Replay — As Known At",
            "opportunity-replay-slider",
            "opportunity-maximize-button",
        ):
            self.assertIn(copy, MAP_JS)
        self.assertNotIn("Opportunity Assessment", MAP_JS)
        self.assertNotIn("What happened?", MAP_JS)
        self.assertNotIn("renderAssessment", MAP_JS)
        self.assertIn("Open Canonical Evidence", MAP_JS)
        self.assertIn('node("span", "", "Evidence")', MAP_JS)
        self.assertIn("as_known_at: detail.as_known_at", MAP_JS)
        self.assertNotIn("OTE unavailable", MAP_JS)
        self.assertIn("proportionalPosition", MAP_JS)
        self.assertIn('btd: "#3B82F6"', MAP_JS)
        self.assertIn('str: "#A78BFA"', MAP_JS)
        self.assertIn('higher: "#22C55E"', MAP_JS)
        self.assertIn('lower: "#F87171"', MAP_JS)
        self.assertIn("@media (max-width: 560px)", MAP_CSS)
        self.assertIn("overflow-x: auto", MAP_CSS)

    def test_group_and_symbol_workspaces_are_progressive_and_interactive(self) -> None:
        for required in (
            "renderCandidateTable",
            "renderSymbol",
            "opportunity-breadcrumb",
            "opportunity-timeline-toggle",
            "eventIdentity",
            "selectedEventId",
            "timelineExpanded",
            "setMaximized",
            "drawCombinedMarker",
            'pressureStyle: "circle"',
            "opportunity-back-to-group",
        ):
            self.assertIn(required, MAP_JS + MAP_CSS)
        self.assertIn("Symbol Opportunity Candidates", MAP_JS)
        self.assertIn("Price / structural zone", MAP_JS)
        self.assertIn("Observed / known", MAP_JS)
        self.assertIn('timelineWrap.classList.toggle("expanded"', MAP_JS)
        self.assertIn(".opportunity-timeline-wrap.expanded", MAP_CSS)
        self.assertEqual(MAP_JS.count('node("table", "opportunity-timeline-table")'), 1)

    def test_group_comparison_is_shared_time_read_only_and_responsive(self) -> None:
        self.assertIn("opportunity-comparison.js", HTML)
        for required in (
            "Compare Maps",
            "comparisonSelection",
            "groupOpportunityComparison",
            "renderComparison",
        ):
            self.assertIn(required, GROUP_JS + MAP_JS + COMPARISON_JS)
        for required in (
            "Relative Structural Comparison",
            "Sync Replay",
            "unifiedCheckpoints",
            "comparisonTimeBounds",
            'pressureStyle: "circle"',
            "comparison_symbols_must_differ",
            "comparison_symbol_not_in_group",
            "No evidence available at this timestamp",
            "build_empty_symbol_opportunity",
        ):
            self.assertIn(required, COMPARISON_JS + MAP_JS + API)
        self.assertNotIn("Synchronise Replay", COMPARISON_JS)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", MAP_CSS)
        self.assertIn(".opportunity-comparison-workspace.maximized", MAP_CSS)


if __name__ == "__main__":
    unittest.main()
