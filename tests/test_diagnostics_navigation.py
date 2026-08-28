from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app/static"
PAGES = {
    "monitor": (STATIC / "index.html").read_text(encoding="utf-8"),
    "operation_card": (STATIC / "mrz-robustness.html").read_text(encoding="utf-8"),
    "activation": (STATIC / "activation-feasibility.html").read_text(encoding="utf-8"),
    "trading_window": (STATIC / "feasibility.html").read_text(encoding="utf-8"),
}
JAVASCRIPT = (STATIC / "diagnostics-nav.js").read_text(encoding="utf-8")
CSS = (STATIC / "diagnostics-nav.css").read_text(encoding="utf-8")

IMPLEMENTED_ITEMS = [
    ("/diagnostics/mrz-robustness", "MRZ Operation Card"),
    ("/diagnostics/activation-feasibility", "Activation Feasibility"),
    ("/diagnostics/trading-window-feasibility", "Trading Window Feasibility"),
]


def navigation_fragment(html: str) -> str:
    match = re.search(
        r'<nav[^>]*data-diagnostics-nav[^>]*>(.*?)</nav>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError("Diagnostics navigation is missing")
    return match.group(1)


def menu_fragment(html: str) -> str:
    navigation = navigation_fragment(html)
    match = re.search(
        r'<div class="diagnostics-dropdown"[^>]*>(.*?)</div>',
        navigation,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError("Diagnostics dropdown is missing")
    return match.group(1)


class DiagnosticsNavigationContractTests(unittest.TestCase):
    def test_all_pages_use_the_shared_accessible_click_menu(self) -> None:
        for name, html in PAGES.items():
            with self.subTest(page=name):
                self.assertIn("Diagnostics", html)
                self.assertIn('data-diagnostics-trigger', html)
                self.assertIn('type="button"', navigation_fragment(html))
                self.assertIn('aria-expanded="false"', navigation_fragment(html))
                self.assertIn('aria-haspopup="menu"', navigation_fragment(html))
                self.assertIn('role="menu"', navigation_fragment(html))
                self.assertIn('/static/diagnostics-nav.css?v=diagnostics-menu-20260827', html)
                self.assertIn('/static/diagnostics-nav.js?v=diagnostics-menu-20260827', html)

    def test_diagnostic_links_are_nested_and_keep_their_existing_routes(self) -> None:
        for name, html in PAGES.items():
            navigation = navigation_fragment(html)
            top_level = navigation.split('<div class="diagnostics-menu', 1)[0]
            menu = menu_fragment(html)
            with self.subTest(page=name):
                self.assertNotIn("/diagnostics/", top_level)
                links = re.findall(
                    r'<a href="([^"]+)" role="menuitem"[^>]*>([^<]+)</a>',
                    menu,
                )
                self.assertEqual(links, IMPLEMENTED_ITEMS)

    def test_menu_order_excludes_hidden_robustness_report(self) -> None:
        expected = [
            "MRZ Operation Card",
            "Activation Feasibility",
            "Trading Window Feasibility",
        ]
        for name, html in PAGES.items():
            menu = menu_fragment(html)
            with self.subTest(page=name):
                positions = [menu.index(label) for label in expected]
                self.assertEqual(positions, sorted(positions))
                self.assertNotIn("diagnostics-disabled-item", menu)
                self.assertNotIn("UNAVAILABLE", menu)
                self.assertNotIn("Migration Path", menu)
                self.assertNotIn("MRZ Robustness", menu)
                self.assertNotIn("/diagnostics/mrz-robustness-report", menu)

    def test_each_existing_diagnostic_page_marks_its_current_child(self) -> None:
        expected_active_label = {
            "operation_card": "MRZ Operation Card",
            "activation": "Activation Feasibility",
            "trading_window": "Trading Window Feasibility",
        }
        self.assertNotIn('aria-current="page"', menu_fragment(PAGES["monitor"]))
        for name, label in expected_active_label.items():
            menu = menu_fragment(PAGES[name])
            with self.subTest(page=name):
                active = re.findall(
                    r'<a [^>]*aria-current="page"[^>]*>([^<]+)</a>',
                    menu,
                )
                self.assertEqual(active, [label])
                self.assertIn("has-current-page", navigation_fragment(PAGES[name]))

    def test_shared_behavior_covers_click_outside_escape_and_keyboard_navigation(self) -> None:
        self.assertIn('trigger.addEventListener("click", onTriggerClick)', JAVASCRIPT)
        self.assertIn('!navigation.contains(event.target)', JAVASCRIPT)
        self.assertIn('event.key === "Escape"', JAVASCRIPT)
        self.assertIn('event.key === "ArrowDown"', JAVASCRIPT)
        self.assertIn('event.key === "ArrowUp"', JAVASCRIPT)
        self.assertIn('event.key === "Home"', JAVASCRIPT)
        self.assertIn('event.key === "End"', JAVASCRIPT)

    def test_narrow_layout_is_bounded_and_touch_targets_remain_usable(self) -> None:
        self.assertIn("min-height: 44px;", CSS)
        self.assertIn("max-width: calc(100vw - 32px);", CSS)
        self.assertIn("@media (max-width: 680px)", CSS)
        responsive = CSS.split("@media (max-width: 680px)", 1)[1]
        self.assertIn("left: 0;", responsive)
        self.assertIn("right: auto;", responsive)


if __name__ == "__main__":
    unittest.main()
