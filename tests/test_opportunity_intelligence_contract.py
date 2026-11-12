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
MAP_CSS = (ROOT / "app/static/opportunity-map.css").read_text(encoding="utf-8")


class OpportunityIntelligenceContractTests(unittest.TestCase):
    def test_api_is_read_only_and_supports_replay(self) -> None:
        self.assertIn('@application.get("/api/opportunities")', API)
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
            "Opportunity Assessment",
            "Is an entry verified?",
            "OTE unavailable",
        ):
            self.assertIn(copy, MAP_JS)
        self.assertIn("proportionalPosition", MAP_JS)
        self.assertIn("@media (max-width: 560px)", MAP_CSS)
        self.assertIn("overflow-x: auto", MAP_CSS)


if __name__ == "__main__":
    unittest.main()
