from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
JS = (ROOT / "app/static/workspace.js").read_text(encoding="utf-8")
SHELL = (ROOT / "app/static/mrz-shell.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/workspace.css").read_text(encoding="utf-8")
API = (ROOT / "app/api.py").read_text(encoding="utf-8")


class WorkspaceContractTests(unittest.TestCase):
    def test_persistent_navigation_and_routes(self) -> None:
        for route, label in (
            ("/mrz/overview", "Overview"),
            ("/mrz/watchlists", "Watchlists"),
            ("/mrz/attention", "Attention"),
            ("/mrz/symbols", "Symbols"),
            ("/mrz/pressure", "Pressure"),
            ("/mrz/alert-settings", "Alert Settings"),
            ("/mrz/location-distribution", "Location Distribution"),
            ("/mrz/formation-diagnostics", "Formation Diagnostics"),
            ("/mrz/events", "Events"),
        ):
            with self.subTest(route=route):
                self.assertIn(f'href: "{route}"', SHELL)
                self.assertIn(f'@application.get("{route}"', API)
                self.assertIn(f'label: "{label}"', SHELL)
        self.assertIn('data-mrz-sidebar', HTML)
        self.assertIn('/static/mrz-shell.js', HTML)
        self.assertNotIn(">Views <", HTML)
        self.assertNotIn("data-diagnostics-trigger", HTML)

    def test_watchlist_board_exposes_current_authority_fields(self) -> None:
        for label in (
            "MRZ status",
            "Current authority",
            "Route",
            "Activated",
            "Structural location",
            "Pressure",
            "Latest meaningful event",
        ):
            self.assertIn(label, HTML)
        self.assertIn("activatedAt", JS)
        self.assertIn("latestEvent", JS)

    def test_attention_and_events_have_distinct_scopes(self) -> None:
        self.assertIn("Tracked symbols only", HTML)
        self.assertIn("Global canonical event history", HTML)
        self.assertIn("derive.deriveAttention", JS)
        self.assertIn("/api/mrz/events?limit=500", JS)

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

    def test_pressure_deep_link_preserves_selected_symbol_context(self) -> None:
        self.assertIn('id="pressureSelectedContext"', HTML)
        self.assertIn('get("symbol")', JS)
        self.assertIn('$("#pressureSelectedSymbol").textContent = selectedSymbol', JS)

    def test_location_distribution_reuses_canonical_buckets_on_its_own_route(self) -> None:
        pressure = HTML.split('data-route-panel="pressure"', 1)[1].split(
            'data-route-panel="alert-settings"', 1
        )[0]
        distribution = HTML.split('data-route-panel="location-distribution"', 1)[1].split(
            'data-route-panel="events"', 1
        )[0]
        self.assertNotIn('id="locationHeatmap"', pressure)
        self.assertIn('id="locationHeatmap"', distribution)
        self.assertIn("function renderLocationDistribution()", JS)
        for key, label in (
            ("deep_discount", "Deep Discount"),
            ("shallow_discount", "Shallow Discount"),
            ("at_eqm", "At EQM"),
            ("shallow_premium", "Shallow Premium"),
            ("deep_premium", "Deep Premium"),
        ):
            with self.subTest(bucket=key):
                self.assertIn(f'"{key}"', JS)
                self.assertIn(f'{key}: "{label}"', JS)

    def test_location_distribution_restores_historical_migration_outcomes(self) -> None:
        self.assertIn('/static/heatmap-state.js', HTML)
        self.assertIn("migrationTendencyPresentation", JS)
        self.assertIn("state.symbolPayload?.location_migration_tendency", JS)
        self.assertIn("Historical migration outcomes", JS)
        self.assertIn("migration.higherPercentageLabel", JS)
        self.assertIn("migration.lowerPercentageLabel", JS)
        self.assertIn("migration.higherCountLabel", JS)
        self.assertIn("migration.lowerCountLabel", JS)
        self.assertIn("migration.sampleLabel", JS)
        self.assertIn("No migration history", JS)

    def test_location_distribution_exposes_canonical_history_and_flow_windows(self) -> None:
        for window in ("24H", "5D", "20D"):
            self.assertIn(f'data-location-window="{window}"', HTML)
        for target in (
            "locationTrendRows",
            "locationUniverseDisclosure",
            "locationStructuralRead",
            "locationFlowSummary",
            "locationDominantTransitions",
        ):
            self.assertIn(f'id="{target}"', HTML)
        self.assertIn("/api/location-distribution/history?window=", JS)
        self.assertIn("% of universe", JS)
        self.assertIn("added/became eligible", JS)
        self.assertIn("removed/became ineligible", JS)
        self.assertIn("elapsed calendar time", JS)
        self.assertIn("Dominant transitions", HTML)
        for label in ("DISCOUNT SHARE", "PREMIUM SHARE", "EXTREME SHARE", "NET LOCATION FLOW"):
            self.assertIn(label, JS)
        self.assertIn("Start/end bucket per comparable symbol", HTML)
        self.assertIn('netFlow < 0 ? "lower" : "balanced"', JS)
        self.assertNotIn('formatSigned(flow.net_higher)} higher', JS)


if __name__ == "__main__":
    unittest.main()
