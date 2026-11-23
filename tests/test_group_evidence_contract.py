from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "app/api.py").read_text(encoding="utf-8")
REPOSITORY = (ROOT / "app/repository.py").read_text(encoding="utf-8")
AGGREGATOR = (ROOT / "app/group_evidence.py").read_text(encoding="utf-8")
HTML = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
JS = (ROOT / "app/static/group-evidence.js").read_text(encoding="utf-8")
OPPORTUNITY_JS = (ROOT / "app/static/opportunity-map.js").read_text(encoding="utf-8")
OPPORTUNITY_CSS = (ROOT / "app/static/opportunity-map.css").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/workspace.css").read_text(encoding="utf-8")
SHELL = (ROOT / "app/static/mrz-shell.js").read_text(encoding="utf-8")


class GroupEvidenceContractTests(unittest.TestCase):
    def test_group_evolution_exposes_flow_and_authoritative_structural_intelligence(self) -> None:
        self.assertIn('"location_flow": location_flow', AGGREGATOR)
        self.assertIn('"structural_intelligence": structural_intelligence', AGGREGATOR)
        self.assertIn('"Group Evolution"', OPPORTUNITY_JS)
        self.assertIn('IPDA Location Flow', OPPORTUNITY_JS)
        self.assertIn('Migration Structure (Group)', OPPORTUNITY_JS)
        self.assertIn('Structural Developments', OPPORTUNITY_JS)
        self.assertIn('Group Members — Structural Overview', OPPORTUNITY_JS)
        self.assertNotIn('onOpenTransition', OPPORTUNITY_JS)
        self.assertNotIn('symbols need a Primary Hypothesis', OPPORTUNITY_JS)
        self.assertNotIn('Set STR', OPPORTUNITY_JS)
        self.assertNotIn('/primary-hypothesis', OPPORTUNITY_JS)
        self.assertIn('/structural-intelligence', API)

    def test_structural_development_panel_removes_redundant_view_all(self) -> None:
        self.assertNotIn('"View All Events →"', OPPORTUNITY_JS)
        self.assertIn('open.href = symbolWorkspaceHref(item.symbol)', OPPORTUNITY_JS)

    def test_group_workspace_is_simplified_and_event_activity_is_canonical(self) -> None:
        group_renderer = OPPORTUNITY_JS.split("function renderGroup(target", 1)[1].split("async function renderSymbol", 1)[0]
        self.assertNotIn('"Developing context"', group_renderer)
        self.assertNotIn('"Structure established"', group_renderer)
        self.assertIn('Event Activity', OPPORTUNITY_JS)
        self.assertIn('Location Flow · Migration Structure · Structural Developments', OPPORTUNITY_JS)
        self.assertIn('item.event_type === "MRZ_ACTIVATED"', OPPORTUNITY_JS)
        self.assertIn('item.event_type === "MRZ_MIGRATED"', OPPORTUNITY_JS)
        self.assertIn('nearMissEvents.length', OPPORTUNITY_JS)
        self.assertIn('migrationDirectionBreakdown', OPPORTUNITY_JS)
        self.assertIn('migration: "MRZ Migration"', OPPORTUNITY_JS)
        self.assertIn('Previous midpoint', OPPORTUNITY_JS)
        self.assertIn('unique_symbols', OPPORTUNITY_JS)
        self.assertIn('unknown_events', AGGREGATOR)
        self.assertIn('instrument_tick', REPOSITORY)
        self.assertIn('migration.event_type = \'MRZ_MIGRATED\'', REPOSITORY)
        self.assertIn('migration.occurred_at > %s', REPOSITORY)
        self.assertIn('migration.occurred_at <= %s', REPOSITORY)
        self.assertIn('No new meaningful structural developments in this selected period.', OPPORTUNITY_JS)
        self.assertIn('No start-to-current location changes in this period.', OPPORTUNITY_JS)
        self.assertIn('group-flow-inspector', OPPORTUNITY_JS)
        self.assertIn('.group-structural-middle-row', OPPORTUNITY_CSS)
        self.assertIn('.group-structural-event-activity', OPPORTUNITY_CSS)
        self.assertIn('.group-structural-developments', OPPORTUNITY_CSS)
        self.assertNotIn('.group-event-activity {', OPPORTUNITY_CSS)
        self.assertNotIn('node("section", "group-event-activity")', OPPORTUNITY_JS)
        self.assertIn('Tracker Event Activity', OPPORTUNITY_JS)
        self.assertIn('Structural Development', OPPORTUNITY_JS)
        self.assertIn('No qualifying events in the selected period.', OPPORTUNITY_JS)
        self.assertIn('Distribution Focus', OPPORTUNITY_JS)
        self.assertIn('Mixed Developments', OPPORTUNITY_JS)
        self.assertIn('No New Structural Developments', OPPORTUNITY_JS)
        self.assertIn('Structure (Now)', OPPORTUNITY_JS)
        self.assertIn('isAccumulationCandidate', OPPORTUNITY_JS)
        self.assertIn('Location Flow · Migration Structure · Structural Developments', JS)
        self.assertIn('id="groupEvidenceBack"', HTML)
        self.assertIn('id="groupEvidenceEdit"', HTML)
        self.assertNotIn('body.group-opportunity-active .workspace-header,', CSS)

    def test_group_radar_uses_six_columns_and_filtered_structural_evidence_drawer(self) -> None:
        overview_renderer = JS.split("function renderOverviewTable()", 1)[1].split("function evidenceCard", 1)[0]
        self.assertIn('IPDA Breadth (P / E / D)', JS)
        self.assertIn('Location Flow (${state.scope.window})', JS)
        self.assertIn('Structural Events (${state.scope.window})', JS)
        self.assertIn('structuralEventBadge(group, "near_miss", "NM"', JS)
        self.assertIn('structuralEventBadge(group, "activation", "ACT"', JS)
        self.assertIn('structuralEventBadge(group, "migration", "MRZ"', JS)
        self.assertIn('renderStructuralEvidenceDrawer', JS)
        self.assertIn('MRZ_ACTIVATED', JS)
        self.assertIn('MRZ_MIGRATED', JS)
        self.assertIn('% Deviation', JS)
        self.assertNotIn('<th>Opportunity research</th>', overview_renderer)
        self.assertNotIn('<th>Migration</th>', overview_renderer)
        self.assertNotIn('<th>Near Miss</th>', overview_renderer)
        self.assertIn('.structural-evidence-overlay', CSS)
        self.assertIn('.structural-event-badge', CSS)

    def test_near_miss_map_uses_short_display_only_extension(self) -> None:
        self.assertIn('nearMissDisplayGeometry', OPPORTUNITY_JS)
        self.assertIn('extensionCssPixels = 48', OPPORTUNITY_JS)
        self.assertIn('item.effective_at || item.known_at', OPPORTUNITY_JS)
        self.assertIn('selectedNearZones', OPPORTUNITY_JS)
        self.assertIn('matchingZones', OPPORTUNITY_JS)
        self.assertNotIn('x(item.ended_at || detail.as_known_at)', OPPORTUNITY_JS)

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
        version = "structural-intelligence-20261123j"
        self.assertIn(f'/static/workspace.css?v={version}', HTML)
        self.assertIn(f'/static/group-evidence.js?v={version}', HTML)
        self.assertIn(f'/static/chart-viewport.js?v={version}', HTML)
        self.assertNotIn('#radarAlertsButton', JS)
        self.assertIn(f'/static/workspace.js?v={version}', HTML)

    def test_tracker_event_rows_are_clickable_and_open_symbol_workspaces(self) -> None:
        renderer = OPPORTUNITY_JS.split("function renderGroupEvolution", 1)[1]
        self.assertIn('[["near", "Near Miss", nearMissEvents.length], ["activation", "MRZ Activation", activationRecords.length]]', renderer)
        self.assertIn("metric.dataset.kind = tone", renderer)
        self.assertIn('migrationMetric.dataset.kind = "migration"', renderer)
        self.assertIn('metric.addEventListener("click", () => renderTrackerDetail(tone))', renderer)
        self.assertIn('migrationMetric.addEventListener("click", () => renderTrackerDetail("migration"))', renderer)
        self.assertIn('return `/mrz/symbols?${params}`', renderer)
        self.assertIn('open.href = symbolWorkspaceHref(symbol)', renderer)
        self.assertIn('link.href = groupSymbolUrl(groupId, symbol)', JS)
        self.assertIn('return `/mrz/symbols?${params}`', JS)

    def test_opportunity_map_viewport_and_current_readout_are_component_scoped(self) -> None:
        renderer = OPPORTUNITY_JS.split("function renderMapComponent", 1)[1].split("function evidenceLabel", 1)[0]
        for interaction in ("onwheel", "onpointerdown", "onpointermove", "onkeydown"):
            self.assertIn(interaction, renderer)
        self.assertNotIn("renderOpportunityWorkspace(", renderer)
        self.assertIn("renderCurrentReadout(detail)", OPPORTUNITY_JS)
        for label in (
            "IPDA Location", "Active MRZ", "Latest Near Miss", "Migration Structure",
            "Route Hypothesis", "Opportunity Evidence State",
        ):
            self.assertIn(label, OPPORTUNITY_JS)
        self.assertIn(".opportunity-current-readout", OPPORTUNITY_CSS)

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
        self.assertIn("Group Evolution", JS)
        self.assertIn("Time – Price · Structural Context · Migration Evidence", JS)

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
