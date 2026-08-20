from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
JAVASCRIPT = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")


class MonitorContractTests(unittest.TestCase):
    def test_operational_title_replaces_lab_wording(self) -> None:
        self.assertIn("MRZ Monitor", HTML)
        self.assertNotIn("Symbol Lab", HTML)

    def test_monitor_assets_are_versioned_together(self) -> None:
        self.assertIn('/static/styles.css?v=mrz-monitor-20260821', HTML)
        self.assertIn('/static/app.js?v=mrz-monitor-20260821', HTML)

    def test_source_and_active_mrz_replace_who_and_where(self) -> None:
        self.assertIn(">SOURCE<", HTML)
        self.assertIn(">ACTIVE MRZ<", HTML)
        self.assertNotIn(">WHO<", HTML)
        self.assertNotIn(">WHERE<", HTML)

    def test_mrz_and_current_price_locations_are_separate(self) -> None:
        self.assertIn(">MRZ LOCATION<", HTML)
        self.assertIn(">CURRENT PRICE LOCATION<", HTML)
        self.assertIn('id="structuralLocation"', HTML)
        self.assertIn('id="currentPriceLocation"', HTML)
        self.assertIn("formatLocation(state.current_price_location)", JAVASCRIPT)

    def test_empty_source_and_mrz_values_are_neutral(self) -> None:
        self.assertIn('class="answer route unestablished"', HTML)
        self.assertIn('fields.owner.textContent = active ? state.route_owner : "—";', JAVASCRIPT)
        self.assertIn('fields.owner.classList.toggle("unestablished", !active);', JAVASCRIPT)
        self.assertIn(': "—";', JAVASCRIPT)
        self.assertIn(".answer.route.unestablished { color: var(--muted); }", CSS)

    def test_only_established_routes_receive_route_color(self) -> None:
        self.assertIn(".answer.route.btd { color: var(--accent); }", CSS)
        self.assertIn(".answer.route.str { color: var(--str); }", CSS)
        self.assertIn('fields.owner.classList.toggle("btd", active && state.route_owner === "BTD");', JAVASCRIPT)
        self.assertIn('fields.owner.classList.toggle("str", active && state.route_owner === "STR");', JAVASCRIPT)

    def test_all_api_location_values_have_operator_labels(self) -> None:
        for value in (
            "deep_discount",
            "shallow_discount",
            "shallow_premium",
            "deep_premium",
            "below_ipda_range",
            "above_ipda_range",
        ):
            with self.subTest(value=value):
                self.assertIn(f'{value}: "', JAVASCRIPT)


if __name__ == "__main__":
    unittest.main()
