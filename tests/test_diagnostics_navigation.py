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


class DiagnosticsNavigationContractTests(unittest.TestCase):
    def test_views_dropdown_is_removed_everywhere(self) -> None:
        for name, html in PAGES.items():
            with self.subTest(page=name):
                self.assertNotIn("data-diagnostics-trigger", html)
                self.assertNotIn(">Views <", html)

    def test_persistent_workspace_destinations_are_available(self) -> None:
        expected = (
            "/mrz/overview",
            "/mrz/watchlists",
            "/mrz/attention",
            "/mrz/symbols",
            "/mrz/pressure",
            "/mrz/alert-settings",
            "/mrz/formation-diagnostics",
            "/mrz/events",
        )
        for name, html in PAGES.items():
            with self.subTest(page=name):
                for path in expected:
                    self.assertIn(f'href="{path}"', html)

    def test_formation_diagnostics_marks_its_current_destination(self) -> None:
        self.assertIn(
            'href="/mrz/formation-diagnostics" aria-current="page"',
            PAGES["activation"],
        )


if __name__ == "__main__":
    unittest.main()
