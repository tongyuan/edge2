from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app/static"
PAGES = {
    "monitor": (STATIC / "index.html").read_text(encoding="utf-8"),
    "operation_card": (STATIC / "mrz-robustness.html").read_text(encoding="utf-8"),
    "activation": (STATIC / "activation-feasibility.html").read_text(encoding="utf-8"),
}
SHELL = (STATIC / "mrz-shell.js").read_text(encoding="utf-8")


class DiagnosticsNavigationContractTests(unittest.TestCase):
    def test_views_dropdown_is_removed_everywhere(self) -> None:
        for name, html in PAGES.items():
            with self.subTest(page=name):
                self.assertNotIn("data-diagnostics-trigger", html)
                self.assertNotIn(">Views <", html)

    def test_shared_workspace_destinations_are_available(self) -> None:
        expected = (
            "/mrz/overview",
            "/mrz/watchlists",
            "/mrz/attention",
            "/mrz/symbols",
            "/mrz/pressure",
            "/mrz/alert-settings",
            "/mrz/location-distribution",
            "/mrz/breadth-leadership",
            "/mrz/formation-diagnostics",
            "/mrz/events",
        )
        for path in expected:
            self.assertIn(f'href: "{path}"', SHELL)
        for name in ("monitor", "activation"):
            with self.subTest(page=name):
                self.assertIn("data-mrz-sidebar", PAGES[name])
                self.assertIn("/static/mrz-shell.js", PAGES[name])

    def test_formation_diagnostics_uses_shared_shell_without_duplicate_nav(self) -> None:
        activation = PAGES["activation"]
        self.assertIn('class="workspace-shell"', activation)
        self.assertIn('class="workspace-main diagnostics-workspace-main"', activation)
        self.assertNotIn('class="mrz-subnav"', activation)
        self.assertNotIn('/static/mrz-subnav.css', activation)
        self.assertIn('normalized === "/mrz/formation-diagnostics"', SHELL)
        self.assertIn('normalized === "/diagnostics/activation-feasibility"', SHELL)

    def test_formation_diagnostics_uses_shared_header_actions(self) -> None:
        activation = PAGES["activation"]
        for element_id in (
            "headerHealth",
            "alertSettingsButton",
            "alertScopeLabel",
            "notificationInboxButton",
            "notificationUnreadBadge",
            "notificationInboxDialog",
            "notificationInboxSummary",
            "notificationInboxList",
            "notificationMarkAllRead",
            "notificationClearInbox",
        ):
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', activation)
        self.assertIn('href="/mrz/alert-settings"', activation)
        self.assertIn('/static/notifications.js', activation)


if __name__ == "__main__":
    unittest.main()
