from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
JS = (ROOT / "app/static/workspace.js").read_text(encoding="utf-8")
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
            ("/mrz/formation-diagnostics", "Formation Diagnostics"),
            ("/mrz/events", "Events"),
        ):
            with self.subTest(route=route):
                self.assertIn(f'href="{route}"', HTML)
                self.assertIn(f'@application.get("{route}"', API)
                self.assertIn(label, HTML)
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
        trading_navigation = HTML.split("<p>TRADING</p>", 1)[1].split("<p>MRZ RESEARCH</p>", 1)[0]
        self.assertIn('href="/mrz/alert-settings"', trading_navigation)
        self.assertIn('data-route="alert-settings"', trading_navigation)
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

    def test_pressure_deep_link_preserves_selected_symbol_context(self) -> None:
        self.assertIn('id="pressureSelectedContext"', HTML)
        self.assertIn('get("symbol")', JS)
        self.assertIn('$("#pressureSelectedSymbol").textContent = selectedSymbol', JS)


if __name__ == "__main__":
    unittest.main()
