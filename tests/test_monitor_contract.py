from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
JAVASCRIPT = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")
REPOSITORY = (ROOT / "app/repository.py").read_text(encoding="utf-8")
LATEST_INDEX = (ROOT / "migrations/002_latest_symbol_overview.sql").read_text(encoding="utf-8")


class MonitorContractTests(unittest.TestCase):
    def test_operational_title_replaces_lab_wording(self) -> None:
        self.assertIn("MRZ Monitor", HTML)
        self.assertNotIn("Symbol Lab", HTML)

    def test_monitor_assets_are_versioned_together(self) -> None:
        self.assertIn('/static/styles.css?v=location-heatmap-20260821', HTML)
        self.assertIn('/static/app.js?v=location-heatmap-20260821', HTML)

    def test_source_and_active_mrz_replace_who_and_where(self) -> None:
        self.assertIn(">SOURCE<", HTML)
        self.assertIn(">ACTIVE MRZ<", HTML)
        self.assertNotIn(">WHO<", HTML)
        self.assertNotIn(">WHERE<", HTML)

    def test_mrz_and_current_price_locations_are_separate(self) -> None:
        self.assertIn(">MRZ LOCATION<", HTML)
        self.assertIn(">CURRENT LOCATION<", HTML)
        self.assertNotIn(">CURRENT PRICE LOCATION<", HTML)
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

    def test_location_heatmap_precedes_selected_detail(self) -> None:
        self.assertIn(">LOCATION HEATMAP<", HTML)
        self.assertIn(">SELECTED SYMBOL DETAIL<", HTML)
        self.assertLess(HTML.index(">LOCATION HEATMAP<"), HTML.index(">SELECTED SYMBOL DETAIL<"))

    def test_heatmap_has_exactly_four_primary_and_three_fallback_keys(self) -> None:
        primary = JAVASCRIPT.split("const primaryLocationKeys = [", 1)[1].split("];", 1)[0]
        secondary = JAVASCRIPT.split("const secondaryLocationKeys = [", 1)[1].split("];", 1)[0]
        self.assertEqual(
            [line.strip(' ,\"') for line in primary.splitlines() if '"' in line],
            ["deep_discount", "shallow_discount", "shallow_premium", "deep_premium"],
        )
        self.assertEqual(
            [line.strip(' ,\"') for line in secondary.splitlines() if '"' in line],
            ["below_ipda_range", "above_ipda_range", "unavailable"],
        )
        self.assertIn('key === "unavailable" ? "Unavailable"', JAVASCRIPT)

    def test_heatmap_groups_each_symbol_once_and_sorts_alphabetically(self) -> None:
        self.assertIn('const key = allLocationKeys.has(currentLocation) ? currentLocation : "unavailable";', JAVASCRIPT)
        self.assertEqual(JAVASCRIPT.count("groups[key].push(symbol);"), 1)
        self.assertIn("symbolsInGroup.sort((left, right) => left.localeCompare(right))", JAVASCRIPT)
        self.assertIn('heatmapEmpty.textContent = "No symbols yet";', JAVASCRIPT)

    def test_heatmap_click_reuses_selector_and_lazy_detail_loader(self) -> None:
        self.assertIn('button.addEventListener("click", () => selectSymbol(symbol).catch(showError));', JAVASCRIPT)
        self.assertIn("select.value = symbol;", JAVASCRIPT)
        self.assertIn("await loadSymbol(symbol);", JAVASCRIPT)
        self.assertNotIn("window.location", JAVASCRIPT)

    def test_initial_overview_is_one_bounded_query_without_detail_requests(self) -> None:
        load_symbols = JAVASCRIPT.split("async function loadSymbols()", 1)[1].split(
            "async function selectSymbol", 1
        )[0]
        self.assertEqual(load_symbols.count('fetch("/api/symbols")'), 1)
        self.assertNotIn("loadSymbol(", load_symbols)

        symbols_method = REPOSITORY.split("    def symbols(self)", 1)[1].split(
            "    def health(self)", 1
        )[0]
        self.assertEqual(symbols_method.count("cursor.execute("), 1)
        self.assertIn("SELECT DISTINCT ON (o.symbol)", symbols_method)
        self.assertNotIn("SELECT * FROM observations", symbols_method)

    def test_latest_symbol_overview_has_a_covering_index(self) -> None:
        self.assertIn("idx_observations_symbol_latest", LATEST_INDEX)
        self.assertIn("symbol, observed_at DESC, received_at DESC, id DESC", LATEST_INDEX)
        self.assertIn("observation_price, ipda_20w_high, ipda_20w_low", LATEST_INDEX)

    def test_heatmap_is_two_columns_and_stacks_on_narrow_screens(self) -> None:
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", CSS)
        self.assertIn(".heatmap-grid, .heatmap-secondary { grid-template-columns: 1fr; }", CSS)


if __name__ == "__main__":
    unittest.main()
