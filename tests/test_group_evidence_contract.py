from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "app/api.py").read_text(encoding="utf-8")
REPOSITORY = (ROOT / "app/repository.py").read_text(encoding="utf-8")
AGGREGATOR = (ROOT / "app/group_evidence.py").read_text(encoding="utf-8")
HTML = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
JS = (ROOT / "app/static/group-evidence.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/workspace.css").read_text(encoding="utf-8")
SHELL = (ROOT / "app/static/mrz-shell.js").read_text(encoding="utf-8")


class GroupEvidenceContractTests(unittest.TestCase):
    def test_only_two_read_endpoints_are_added(self) -> None:
        self.assertIn('@application.get("/api/group-evidence")', API)
        self.assertIn('@application.get("/api/group-evidence/{group_id}")', API)
        for verb in ("post", "put", "patch", "delete"):
            self.assertNotIn(f'@application.{verb}("/api/group-evidence', API)
        self.assertIn('pattern=r"^(24H|5D|20D)$"', API)
        self.assertIn('"Cache-Control": "no-store, max-age=0"', API)

    def test_repository_uses_one_read_only_repeatable_read_snapshot(self) -> None:
        method = REPOSITORY.split("def group_evidence_inputs", 1)[1].split("def saved_groups", 1)[0]
        self.assertIn('readonly=True', method)
        self.assertIn('isolation_level="REPEATABLE READ"', method)
        self.assertIn("transaction_timestamp() AS as_of", method)
        self.assertIn("INNER JOIN active_mrz AS authority", method)
        self.assertIn("observation.observed_at >= authority.activated_at", method)
        self.assertIn("occurred_at > %s", method)
        self.assertIn("occurred_at <= %s", method)
        self.assertIn("SELECT DISTINCT ON (symbol)", method)
        self.assertIn('"latest_pressure_events"', method)
        for forbidden in ("INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE INDEX", "ALTER TABLE"):
            self.assertNotIn(forbidden, method)

    def test_projection_preserves_stage_a_vocabulary(self) -> None:
        self.assertIn('"same_bucket"', AGGREGATOR)
        self.assertIn('"current_neutral"', AGGREGATOR)
        self.assertIn('"current_unavailable"', AGGREGATOR)
        self.assertIn('"current_membership_at_snapshot"', AGGREGATOR)
        for forbidden in (
            '"condition"', '"attention_state"', '"score"', '"priority"',
            '"materiality"', '"resolved"', '"superseded"',
        ):
            self.assertNotIn(forbidden, AGGREGATOR)

    def test_all_groups_is_default_and_overview_attention_are_consolidated(self) -> None:
        self.assertIn("/mrz/watchlists?group=all&window=24H", API)
        self.assertNotIn('name: "overview"', SHELL)
        self.assertNotIn('name: "attention"', SHELL)
        self.assertIn('label: "Group Radar"', SHELL)
        self.assertIn('label: "Events History"', SHELL)

    def test_initial_watchlist_load_is_decoupled_from_global_sources(self) -> None:
        workspace_js = (ROOT / "app/static/workspace.js").read_text(encoding="utf-8")
        initialize = workspace_js.split("async function initialize()", 1)[1]
        self.assertLess(initialize.index('routeName() === "watchlists"'), initialize.index('fetch("/api/symbols"'))
        self.assertIn("/api/group-evidence", JS)
        self.assertIn("/api/mrz/events?limit=500", JS)
        self.assertIn("recentTrackedEventsToggle", JS)

        render_all = workspace_js.split("function renderAll()", 1)[1].split("async function initialize()", 1)[0]
        self.assertNotIn("renderWatchlists", render_all)

    def test_stage_a_assets_share_a_fresh_cache_version(self) -> None:
        version = "pressure-ui-retirement-20261114"
        self.assertIn(f'/static/workspace.css?v={version}', HTML)
        self.assertIn(f'/static/group-evidence.js?v={version}', HTML)
        self.assertIn(f'/static/workspace.js?v={version}', HTML)

    def test_url_state_stale_response_and_accessibility_contracts_exist(self) -> None:
        for key in ("group", "window", "dimension", "bucket", "evidence"):
            self.assertIn(key, JS)
        self.assertIn("AbortController", JS)
        self.assertIn("requestId !== state.requestId", JS)
        self.assertIn('aria-live="polite"', HTML)
        self.assertIn('aria-pressed="true"', HTML)
        self.assertIn("aria-label", JS)
        self.assertIn("@media (prefers-reduced-motion: reduce)", CSS)
        mobile = CSS[CSS.index("@media (max-width: 560px)") :]
        self.assertNotIn(".event-row .event-open { display: none; }", mobile)
        self.assertIn(".recent-tracked-event-list .quiet-button", mobile)
        self.assertIn(".selected-group-workspace { display: grid", CSS)
        self.assertIn(".radar-table-wrap { width: 100%; overflow-x: auto; }", CSS)

    def test_opportunity_radar_contract_exposes_research_and_management_without_pressure_or_group_evidence(self) -> None:
        for copy in (
            "Group Radar",
            "Migration",
            "Near Miss",
        ):
            self.assertIn(copy, HTML + JS)
        for removed in (
            'node("strong", "", "Group Evidence")',
            'node("details", "group-canonical-evidence panel")',
            "Current Pressure State",
            "Lower Pressure",
            "Higher Pressure",
        ):
            self.assertNotIn(removed, HTML + JS)
        for removed in ("OTE (1D)", "OTE (1W)", "Latest OTE Alert", "OTE feed not connected", "OTE (from EDGE_BOT)"):
            self.assertNotIn(removed, HTML + JS)
        for action in ("edit", "duplicate", "delete", "all"):
            self.assertIn(f'data-manage-action="{action}"', HTML)
        self.assertIn("globalObject.confirm", JS)
        self.assertIn("openManageAll", JS)
        self.assertIn("duplicateGroup", JS)

    def test_group_radar_uses_three_exclusive_workspace_states(self) -> None:
        for required in (
            'view === "overview"',
            'view === "group"',
            'view === "symbol"',
            "openOpportunitySymbol",
            "symbol-opportunity-intelligence",
        ):
            self.assertIn(required, JS + CSS)
        self.assertIn("Candidate symbols · Opportunity research", JS)
        self.assertIn("Time · Price · Structural context", JS)

    def test_repository_snapshot_includes_near_miss_and_location_history_inputs(self) -> None:
        method = REPOSITORY.split("def group_evidence_inputs", 1)[1].split("def saved_groups", 1)[0]
        self.assertIn("current_production_near_miss_episodes", method)
        self.assertIn('"near_miss_episodes"', method)
        self.assertIn('"location_observations"', method)
        self.assertIn('"latest_pressure_events"', method)
        self.assertIn('"status": "not_connected"', AGGREGATOR)
        self.assertIn('"source": "EDGE_BOT"', AGGREGATOR)

    def test_no_schema_or_runtime_dependency_was_added(self) -> None:
        migration_names = {path.name for path in (ROOT / "migrations").glob("*.sql")}
        self.assertIn("018_instrument_taxonomy.sql", migration_names)
        self.assertFalse(any("group_evidence" in name for name in migration_names))
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertNotIn("group-evidence", requirements)


if __name__ == "__main__":
    unittest.main()
