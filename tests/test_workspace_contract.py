from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
JS = (ROOT / "app/static/workspace.js").read_text(encoding="utf-8")
GROUP_JS = (ROOT / "app/static/group-evidence.js").read_text(encoding="utf-8")
SHELL = (ROOT / "app/static/mrz-shell.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/workspace.css").read_text(encoding="utf-8")
API = (ROOT / "app/api.py").read_text(encoding="utf-8")
DERIVATIONS = (ROOT / "app/static/workspace-derivations.js").read_text(encoding="utf-8")
PEER_PRESSURE = (ROOT / "app/peer_pressure.py").read_text(encoding="utf-8")


class WorkspaceContractTests(unittest.TestCase):
    def test_persistent_navigation_and_routes(self) -> None:
        for route, label in (
            ("/mrz/watchlists", "Group Radar"),
            ("/mrz/symbols", "Symbols"),
            ("/mrz/alert-settings", "Alert Settings"),
            ("/mrz/location-distribution", "Location Distribution"),
            ("/mrz/formation-diagnostics", "Formation Diagnostics"),
            ("/mrz/events", "Events History"),
        ):
            with self.subTest(route=route):
                self.assertIn(route, SHELL)
                self.assertIn(f'@application.get("{route}"', API)
                self.assertIn(f'label: "{label}"', SHELL)
        self.assertNotIn('name: "overview"', SHELL)
        self.assertNotIn('name: "attention"', SHELL)
        self.assertIn('data-mrz-sidebar', HTML)
        self.assertIn('/static/mrz-shell.js', HTML)
        self.assertNotIn(">Views <", HTML)
        self.assertNotIn("data-diagnostics-trigger", HTML)
        trading = SHELL.split('section: "TRADING"', 1)[1].split('section: "MRZ RESEARCH"', 1)[0]
        self.assertNotIn('name: "pressure"', trading)
        self.assertNotIn('label: "Pressure"', trading)

    def test_group_member_board_exposes_current_authority_and_ote_fields(self) -> None:
        for label in (
            "MRZ Levels",
            "Route",
            "Location",
            "Last Pressure Direction",
            "Near Miss",
            "OTE (1D)",
            "OTE (1W)",
            "Latest OTE Alert",
        ):
            self.assertIn(label, GROUP_JS)
        self.assertIn("symbolUrl(member.symbol)", GROUP_JS)

    def test_group_overview_exposes_search_selection_and_responsive_table(self) -> None:
        self.assertIn('id="groupEvidenceSearch"', HTML)
        self.assertIn("group.name.toLowerCase().includes(state.search)", GROUP_JS)
        self.assertIn("row.classList.add(\"selected\")", GROUP_JS)
        self.assertIn("openGroup(group.id)", GROUP_JS)
        mobile_rules = CSS.split("@media (max-width: 820px)", 1)[1]
        self.assertIn(".radar-chart-grid", mobile_rules)
        self.assertNotIn(".group-evidence-route { display: none; }", mobile_rules)

    def test_attention_and_events_have_distinct_scopes(self) -> None:
        self.assertIn("Recent tracked symbol events", HTML)
        self.assertIn("Events History", SHELL)
        self.assertIn("/api/mrz/events?limit=500", GROUP_JS)
        self.assertIn("Group Radar remains available", GROUP_JS)

    def test_notification_controls_cover_scope_and_all_event_types(self) -> None:
        self.assertIn('href: "/mrz/alert-settings"', SHELL)
        self.assertIn('name: "alert-settings"', SHELL)
        self.assertIn('data-route-panel="alert-settings"', HTML)
        self.assertNotIn('id="alertSettingsDialog"', HTML)
        self.assertEqual(HTML.count('id="alertPreferencesForm"'), 1)
        self.assertIn("ALERTS ON/OFF", HTML)
        mobile_rules = CSS.split("@media (max-width: 820px)", 1)[1]
        self.assertIn(".header-alert-status { display: none; }", mobile_rules)
        self.assertNotIn(".workspace-navigation a { display: none; }", mobile_rules)
        self.assertIn('value="TRACKED_GROUPS_ONLY"', HTML)
        self.assertIn('value="ALL_SYMBOLS"', HTML)
        for control in ("prefActivation", "prefMigration", "prefPressure", "prefNearMiss"):
            self.assertIn(f'id="{control}"', HTML)
        self.assertIn("/api/notifications/preferences", JS)

    def test_shared_sidebar_is_collapsible_persistent_and_mobile_safe(self) -> None:
        self.assertIn('id="sidebarToggle"', SHELL)
        self.assertIn('aria-controls="mrzWorkspaceMain"', SHELL)
        self.assertIn('aria-expanded', SHELL)
        self.assertIn('edge2.mrz.sidebar.collapsed', SHELL)
        self.assertIn('localStorage', SHELL)
        self.assertIn('body.classList.toggle("sidebar-collapsed", collapsed)', SHELL)
        self.assertIn('body.classList.toggle("nav-open")', SHELL)
        self.assertIn('body.sidebar-collapsed .workspace-shell', CSS)
        mobile_rules = CSS.split("@media (max-width: 820px)", 1)[1]
        self.assertIn(".sidebar-toggle { display: none; }", mobile_rules)
        self.assertIn("body.sidebar-collapsed .workspace-sidebar", mobile_rules)

    def test_legacy_pressure_route_redirects_to_group_evidence_with_context(self) -> None:
        self.assertIn('@application.get("/mrz/pressure"', API)
        self.assertIn('url=f"/mrz/watchlists?{urlencode(params)}"', API)
        self.assertIn('params = {"group": "all", "window": "24H"}', API)
        self.assertIn("params.update(dict(request.query_params))", API)
        self.assertIn('normalized === "/mrz/pressure"', SHELL)
        self.assertIn('return "watchlists"', SHELL)
        self.assertNotIn('data-route-panel="pressure"', HTML)

    def test_location_distribution_reuses_canonical_buckets_on_its_own_route(self) -> None:
        distribution = HTML.split('data-route-panel="location-distribution"', 1)[1].split(
            'data-route-panel="events"', 1
        )[0]
        self.assertIn('id="locationFlowCanvas"', distribution)
        self.assertIn("function renderLocationDistribution()", JS)
        for key, label in (
            ("deep_discount", "Deep Discount"),
            ("shallow_discount", "Shallow Discount"),
            ("at_eqm", "At EQM"),
            ("shallow_premium", "Shallow Premium"),
            ("deep_premium", "Deep Premium"),
        ):
            with self.subTest(bucket=key):
                self.assertIn(f'{{ key: "{key}", label: "{label}"', DERIVATIONS)

    def test_location_distribution_contributors_show_exact_flow_members(self) -> None:
        self.assertNotIn('id="locationContributorSearch"', HTML)
        self.assertNotIn("filterLocationTransitionMembers", DERIVATIONS)
        self.assertIn("const members = cell.members", JS)
        self.assertIn("/mrz/symbols?symbol=", JS)
        mobile_rules = CSS.split("@media (max-width: 820px)", 1)[1]
        self.assertNotIn(".location-contributors-section { display: none; }", mobile_rules)

    def test_location_distribution_preserves_underlying_research_helpers(self) -> None:
        self.assertNotIn('/static/heatmap-state.js', HTML)
        self.assertTrue((ROOT / "app/static/heatmap-state.js").exists())
        self.assertIn("deriveBreadthLeadership", DERIVATIONS)
        self.assertIn("deriveResearchInterpretation", DERIVATIONS)
        self.assertIn("deriveLocationTransitionHeatmap", DERIVATIONS)
        self.assertNotIn("directional pressure", HTML.split('data-route-panel="location-distribution"', 1)[1].split('data-route-panel="events"', 1)[0].lower())

    def test_location_distribution_exposes_canonical_history_and_flow_windows(self) -> None:
        for window in ("24H", "5D", "20D"):
            self.assertIn(f'data-location-window="{window}"', HTML)
        for target in (
            "locationCoverageCards",
            "locationCoverageStrip",
            "locationTaxonomyCards",
            "locationTaxonomyLevel",
            "locationTaxonomySort",
            "locationFlowCanvas",
            "locationContributorRows",
        ):
            self.assertIn(f'id="{target}"', HTML)
        for sort_label in (
            "Most Symbols Moving Lower",
            "Most Symbols Moving Higher",
            "Highest % Moving Lower",
            "Highest % Moving Higher",
            "Taxonomy A–Z",
        ):
            self.assertIn(sort_label, HTML)
        self.assertIn('locationTaxonomySort: "lower"', JS)
        self.assertIn('["lower", "higher", "lower_pct", "higher_pct", "name"]', JS)
        self.assertIn('`${Math.round(share * 100)}%`', JS)
        self.assertIn('↓ ${group.lower} lower (${percentage(group.lower_share)})', JS)
        self.assertIn('↑ ${group.higher} higher (${percentage(group.higher_share)})', JS)
        sort_handler = JS.split('$("#locationTaxonomySort")?.addEventListener("change"', 1)[1].split("});", 1)[0]
        self.assertNotIn("locationTaxonomySelection = null", sort_handler)
        self.assertNotIn("locationFlowSelection = null", sort_handler)
        for removed_target in (
            "locationTrendRows",
            "locationUniverseDisclosure",
            "locationStructuralRead",
            "locationFlowSummary",
            "locationDominantTransitions",
            "locationFlowFilters",
        ):
            self.assertNotIn(f'id="{removed_target}"', HTML)
        self.assertIn("/api/location-distribution/history?window=", JS)
        self.assertIn("derive.deriveLocationTaxonomyOverview", JS)
        self.assertIn("derive.deriveLocationTaxonomyFlow", JS)
        for label in (
            "Eligible",
            "Comparable",
            "New observations",
            "No new observations",
            "Unavailable / incomparable",
        ):
            self.assertIn(label, JS)
        self.assertIn("Same bucket does not imply stability", HTML)
        self.assertIn('aria-label="Scrollable structural location bucket flow"', HTML)
        route = HTML.split('data-route-panel="location-distribution"', 1)[1].split('data-route-panel="events"', 1)[0]
        self.assertLess(route.index('id="locationCoverageCards"'), route.index('id="locationTaxonomyHeading"'))
        self.assertLess(route.index('id="locationTaxonomyHeading"'), route.index('id="locationFlowHeading"'))
        self.assertLess(route.index('id="locationFlowHeading"'), route.index('id="locationContributorsHeading"'))

    def test_breadth_leadership_page_is_removed_but_legacy_route_is_preserved(self) -> None:
        self.assertNotIn('data-route-panel="breadth-leadership"', HTML)
        self.assertNotIn('name: "breadth-leadership"', SHELL)
        self.assertNotIn('label: "Breadth & Leadership"', SHELL)
        self.assertNotIn('Breadth research', GROUP_JS)
        self.assertIn('@application.get("/mrz/breadth-leadership"', API)
        self.assertIn('destination = "/mrz/location-distribution"', API)
        self.assertIn('normalized === "/mrz/breadth-leadership"', SHELL)
        self.assertIn('return "location-distribution"', SHELL)
        self.assertNotIn("data-breadth-window", HTML)
        for target in (
            "breadthMetrics",
            "researchInterpretationHeading",
            "researchInterpretationDimensions",
            "researchInterpretationNarrative",
            "researchInterpretationEvidence",
            "pressureConfirmationRows",
            "confirmationRates",
            "breadthLeaders",
            "breadthLaggards",
            "higherLowerDivergences",
            "lowerHigherDivergences",
            "migrationBreadth",
            "locationPressureRows",
        ):
            self.assertNotIn(f'id="{target}"', HTML)
        self.assertNotIn("derive.deriveBreadthLeadership", JS)
        self.assertNotIn("derive.deriveResearchInterpretation(report)", JS)
        self.assertNotIn('<h1>Pressure</h1>', HTML)

    def test_mrz_research_navigation_contains_only_supported_pages(self) -> None:
        research = SHELL.split('section: "MRZ RESEARCH"', 1)[1].split("],", 1)[0]
        self.assertIn('label: "Location Distribution"', research)
        self.assertIn('label: "Formation Diagnostics"', research)
        self.assertIn('label: "Events History"', research)
        self.assertNotIn("Breadth", research)

    def test_standalone_pressure_presentation_is_removed_but_analytics_are_preserved(self) -> None:
        for target in (
            "pressureSelectedContext",
            "pressureSummary",
            "pressureSources",
            "pressureAssetClasses",
            "pressureSectors",
            "pressureIndustries",
            "pressureDrilldown",
            "pressureDrilldownGroups",
            "pressureMap",
        ):
            self.assertNotIn(f'id="{target}"', HTML)
        for renderer in (
            "renderPressure()",
            "renderPressureSources",
            "renderPressureAssetClasses",
            "renderPressureTaxonomy",
            "renderPressureDrilldown",
        ):
            self.assertNotIn(renderer, JS)
        self.assertNotIn("pressureSelection", JS)
        self.assertNotIn("pressureNeutralExpanded", JS)
        self.assertNotIn("Universe Pressure", GROUP_JS)
        self.assertNotIn(".pressure-taxonomy-grid", CSS)
        self.assertIn("Latest directional ·", JS)
        self.assertIn('id="detailPressure"', HTML)
        self.assertIn('"taxonomy_pressure": build_taxonomy_pressure_report(', API)
        self.assertIn("def build_taxonomy_pressure_report(", PEER_PRESSURE)
        for helper in (
            "groupPressureSourcesByAssetClass",
            "pressureDrilldownMembers",
            "directionalTaxonomyDrilldown",
            "pressureDetailPresentation",
        ):
            self.assertIn(helper, DERIVATIONS)

    def test_group_evidence_belongs_to_watchlists_and_is_mobile_safe(self) -> None:
        watchlists = HTML.split('data-route-panel="watchlists"', 1)[1].split(
            'data-route-panel="attention"', 1
        )[0]
        self.assertIn("Group Radar", watchlists)
        self.assertIn("Recent tracked symbol events", watchlists)
        self.assertNotIn('data-route-panel="pressure"', HTML)
        for target in (
            "groupEvidenceTitle",
            "groupEvidenceMeta",
            "groupEvidenceContent",
            "recentTrackedEventsBody",
        ):
            self.assertIn(f'id="{target}"', watchlists)
        for window in ("24H", "5D", "20D"):
            self.assertIn(f'data-group-window="{window}"', watchlists)
        self.assertIn("/api/group-evidence", GROUP_JS)
        self.assertIn("Last Pressure Direction", GROUP_JS)
        self.assertIn("Group Event Timeline", GROUP_JS)
        self.assertIn("OTE feed not connected", GROUP_JS)
        mobile_rules = CSS[CSS.index("@media (max-width: 560px)") :]
        for selector in (".radar-evidence-cards", ".opportunity-sheet", ".manage-group-row"):
            self.assertIn(selector, mobile_rules)

    def test_location_bucket_flow_exposes_accessible_symbol_drilldown(self) -> None:
        for target in (
            "locationFlowCanvas",
            "locationFlowTargets",
            "locationContributorRows",
        ):
            self.assertIn(f'id="{target}"', HTML)
        self.assertNotIn("filterLocationTransitionMembers", DERIVATIONS)
        self.assertIn('button.setAttribute("aria-pressed"', JS)
        self.assertIn("item.start_location_label", JS)
        self.assertIn("item.current_location_label", JS)
        self.assertIn("item.comparison_observed_at", JS)
        self.assertIn("item.current_observed_at", JS)
        self.assertIn("item.has_new_observation", JS)
        self.assertIn('symbolLink(item.symbol, "Open details")', JS)
        self.assertIn("Path2D", JS)
        self.assertIn("isPointInStroke", JS)
        self.assertIn(".location-flow-scroll", CSS)
        self.assertIn("overflow-x: auto", CSS)
        mobile_rules = CSS[CSS.index("@media (max-width: 560px)") :]
        self.assertIn(".location-contributors-table", mobile_rules)
        self.assertIn("display: block", mobile_rules)


if __name__ == "__main__":
    unittest.main()
