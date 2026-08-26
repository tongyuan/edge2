from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
JAVASCRIPT = (ROOT / "app/static/app.js").read_text(encoding="utf-8")
HEATMAP_STATE = (ROOT / "app/static/heatmap-state.js").read_text(encoding="utf-8")
OPERATOR_TIME = (ROOT / "app/static/operator-time.js").read_text(encoding="utf-8")
MONITOR_PRESENTATION = (ROOT / "app/static/monitor-presentation.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/styles.css").read_text(encoding="utf-8")
REPOSITORY = (ROOT / "app/repository.py").read_text(encoding="utf-8")
CONCENTRATION = (ROOT / "app/concentration.py").read_text(encoding="utf-8")
STATE_ENGINE = (ROOT / "app/state_engine.py").read_text(encoding="utf-8")
API = (ROOT / "app/api.py").read_text(encoding="utf-8")
LATEST_INDEX = (ROOT / "migrations/002_latest_symbol_overview.sql").read_text(encoding="utf-8")
EVIDENCE_MIGRATION = (ROOT / "migrations/003_active_mrz_supporting_evidence.sql").read_text(
    encoding="utf-8"
)
FORMATION_MIGRATION = (ROOT / "migrations/004_mrz_formation_evidence.sql").read_text(
    encoding="utf-8"
)


class MonitorContractTests(unittest.TestCase):
    def test_operational_title_replaces_lab_wording(self) -> None:
        self.assertIn("MRZ Monitor", HTML)
        self.assertNotIn("Symbol Lab", HTML)

    def test_monitor_assets_are_versioned_together(self) -> None:
        version = "evidence-ready-20260826"
        self.assertIn(f'/static/styles.css?v={version}', HTML)
        self.assertIn(f'/static/heatmap-state.js?v={version}', HTML)
        self.assertIn(f'/static/operator-time.js?v={version}', HTML)
        self.assertIn(f'/static/monitor-presentation.js?v={version}', HTML)
        self.assertIn(f'/static/app.js?v={version}', HTML)
        self.assertLess(HTML.index("heatmap-state.js"), HTML.index("app.js"))
        self.assertLess(HTML.index("monitor-presentation.js"), HTML.index("app.js"))

    def test_monitor_links_to_both_read_only_diagnostics(self) -> None:
        self.assertIn('href="/diagnostics/activation-feasibility">Activation Feasibility</a>', HTML)
        self.assertIn('href="/diagnostics/mrz-robustness">MRZ Operation Card</a>', HTML)
        self.assertIn('aria-label="Diagnostic navigation"', HTML)

    def test_source_and_active_mrz_replace_who_and_where(self) -> None:
        self.assertIn(">SOURCE<", HTML)
        self.assertIn(">ACTIVE MRZ<", HTML)
        self.assertNotIn(">WHO<", HTML)
        self.assertNotIn(">WHERE<", HTML)

    def test_active_mrz_displays_authoritative_activation_timestamp(self) -> None:
        self.assertIn('id="mrzActivation" hidden', HTML)
        self.assertIn('id="mrzActivatedAt"', HTML)
        self.assertIn(">Activated<", HTML)
        self.assertIn("formatActivatedAt(state, formatOperatorTimestampUtcMinus4)", JAVASCRIPT)
        self.assertIn("timestampFormatter(state.activated_at)", MONITOR_PRESENTATION)
        self.assertIn('state.mrz_status !== "active"', MONITOR_PRESENTATION)
        self.assertIn("fields.activation.hidden = !activatedAt;", JAVASCRIPT)
        self.assertIn('fields.activatedAt.textContent = activatedAt || "—";', JAVASCRIPT)
        self.assertIn(".mrz-activation[hidden] { display: none; }", CSS)

    def test_current_migration_provenance_is_persistent_and_explicit(self) -> None:
        self.assertIn('id="mrzMigration" hidden', HTML)
        self.assertIn('id="mrzMigrationTitle">↑ MIGRATED<', HTML)
        self.assertIn('id="mrzMigratedAt"', HTML)
        self.assertIn('id="mrzPreviousRange"', HTML)
        self.assertIn("buildMigrationPresentation(", JAVASCRIPT)
        self.assertIn('migration.direction === "DOWN" ? "↓" : "↑"', MONITOR_PRESENTATION)
        self.assertIn('title: `${arrow} MIGRATED`', MONITOR_PRESENTATION)
        self.assertIn("fields.migration.hidden = migration === null;", JAVASCRIPT)
        migration_style = CSS.split(".mrz-migration {", 1)[1].split("}", 1)[0]
        self.assertNotIn("animation", migration_style)

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
        primary = HEATMAP_STATE.split("const primaryLocationKeys = [", 1)[1].split("];", 1)[0]
        secondary = HEATMAP_STATE.split("const secondaryLocationKeys = [", 1)[1].split("];", 1)[0]
        self.assertEqual(
            [line.strip(' ,\"') for line in primary.splitlines() if '"' in line],
            ["deep_discount", "shallow_discount", "shallow_premium", "deep_premium"],
        )
        self.assertEqual(
            [line.strip(' ,\"') for line in secondary.splitlines() if '"' in line],
            ["below_ipda_range", "above_ipda_range", "unavailable"],
        )
        self.assertIn('key === "unavailable" ? "Unavailable"', JAVASCRIPT)

    def test_heatmap_groups_each_symbol_once_and_sorts_by_activity_then_symbol(self) -> None:
        self.assertIn('const key = allLocationKeys.has(currentLocation) ? currentLocation : "unavailable";', HEATMAP_STATE)
        self.assertEqual(HEATMAP_STATE.count("groups[key].push(symbolState);"), 1)
        self.assertIn("function compareSymbolsByActivity(left, right)", HEATMAP_STATE)
        self.assertIn("routeAlignedObservationCount(right)", HEATMAP_STATE)
        self.assertIn("routeAlignedObservationCount(left)", HEATMAP_STATE)
        self.assertIn("String(left.symbol).localeCompare(String(right.symbol))", HEATMAP_STATE)
        self.assertIn("symbolsInGroup.sort(compareSymbolsByActivity)", HEATMAP_STATE)
        self.assertIn('heatmapEmpty.textContent = "No symbols yet";', JAVASCRIPT)

    def test_heatmap_refresh_preserves_selected_symbol_after_reordering(self) -> None:
        self.assertIn("function preservedSelectedSymbol(currentSymbol, symbols)", HEATMAP_STATE)
        load_symbols = JAVASCRIPT.split("async function loadSymbols()", 1)[1].split(
            "async function selectSymbol", 1
        )[0]
        self.assertIn("preservedSelectedSymbol(select.value, payload.symbols)", load_symbols)
        self.assertIn("select.value = selectedSymbol;", load_symbols)
        self.assertIn("updateSelectedChip(selectedSymbol);", load_symbols)

    def test_heatmap_active_indicator_uses_authoritative_status_and_is_accessible(self) -> None:
        self.assertIn('return symbolState.mrz_status === "active";', HEATMAP_STATE)
        active_method = HEATMAP_STATE.split("function hasActiveMrz", 1)[1].split(
            "function safeActivityCount", 1
        )[0]
        self.assertNotIn("confirming_observation_count", active_method)
        self.assertNotIn("route_owner", active_method)
        heatmap_group = JAVASCRIPT.split("function createLocationGroup", 1)[1].split(
            "function renderLocationHeatmap", 1
        )[0]
        self.assertIn("const active = hasActiveMrz(symbolState);", heatmap_group)
        self.assertIn('indicator.className = "active-mrz-dot";', heatmap_group)
        self.assertIn('indicator.setAttribute("aria-hidden", "true");', heatmap_group)
        self.assertIn("accessibleChipLabel(symbolState, locationLabel)", heatmap_group)
        self.assertNotIn("BTD", heatmap_group)
        self.assertNotIn("STR", heatmap_group)

    def test_heatmap_has_one_quiet_active_legend_without_animation(self) -> None:
        self.assertEqual(HTML.count(">Active MRZ<"), 1)
        self.assertIn('class="heatmap-legend"', HTML)
        self.assertIn('class="active-mrz-dot" aria-hidden="true"', HTML)
        active_style = CSS.split(".active-mrz-dot", 1)[1].split(".heatmap-grid", 1)[0]
        self.assertNotIn("animation", active_style)
        self.assertNotIn("pulse", active_style)

    def test_heatmap_has_minimal_neutral_activity_legend(self) -> None:
        self.assertIn("Chip intensity · Observation activity", HTML)
        self.assertIn('class="activity-legend-swatch" aria-hidden="true"', HTML)
        swatch_style = CSS.split(".activity-legend-swatch", 1)[1].split(".heatmap-grid", 1)[0]
        self.assertIn("background: rgba(112, 132, 160, 0.3);", swatch_style)
        self.assertNotIn("green", swatch_style.lower())
        self.assertNotIn("animation", swatch_style)

    def test_heatmap_marks_production_count_eligibility_with_only_a_bright_outline(self) -> None:
        self.assertIn("Bright outline · Concentration-check eligible", HTML)
        self.assertIn('class="evidence-ready-legend-swatch" aria-hidden="true"', HTML)
        self.assertIn("function concentrationCheckEligible(symbolState, minimumObservations)", HEATMAP_STATE)
        self.assertIn("btdCount >= minimum", HEATMAP_STATE)
        self.assertIn("strCount >= minimum", HEATMAP_STATE)
        self.assertNotIn("btdCount + strCount", HEATMAP_STATE)
        self.assertIn("payload.minimum_cluster_observations", JAVASCRIPT)
        self.assertIn('"evidence-ready",', JAVASCRIPT)
        eligible_style = CSS.split(".symbol-chip.evidence-ready {", 1)[1].split("}", 1)[0]
        self.assertIn("border-color: #aebbd0;", eligible_style)
        self.assertIn("box-shadow: inset", eligible_style)
        self.assertNotIn("animation", eligible_style)

    def test_heatmap_evidence_outline_coexists_with_active_selected_and_activity_states(self) -> None:
        heatmap_group = JAVASCRIPT.split("function createLocationGroup", 1)[1].split(
            "function renderLocationHeatmap", 1
        )[0]
        self.assertIn('button.classList.toggle("active-mrz", active);', heatmap_group)
        self.assertIn('"evidence-ready",', heatmap_group)
        self.assertIn("routeAlignedActivity(symbolState)", heatmap_group)
        self.assertIn('button.classList.add(`activity-${activity.tier}`);', heatmap_group)
        self.assertIn('indicator.className = "active-mrz-dot";', heatmap_group)
        self.assertIn(".symbol-chip.evidence-ready.selected {", CSS)
        self.assertNotIn("evidence-ready", HEATMAP_STATE.split("function groupSymbolsByLocation", 1)[1])

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
        self.assertIn("LEFT JOIN LATERAL", symbols_method)
        self.assertEqual(symbols_method.count("LIMIT %s"), 2)
        self.assertIn("WHERE symbol = o.symbol AND route = 'BTD'", symbols_method)
        self.assertIn("WHERE symbol = o.symbol AND route = 'STR'", symbols_method)

    def test_latest_symbol_overview_has_a_covering_index(self) -> None:
        self.assertIn("idx_observations_symbol_latest", LATEST_INDEX)
        self.assertIn("symbol, observed_at DESC, received_at DESC, id DESC", LATEST_INDEX)
        self.assertIn("observation_price, ipda_20w_high, ipda_20w_low", LATEST_INDEX)

    def test_heatmap_is_two_columns_and_stacks_on_narrow_screens(self) -> None:
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", CSS)
        self.assertIn(".heatmap-grid, .heatmap-secondary { grid-template-columns: 1fr; }", CSS)
        self.assertIn(".symbol-chips { display: flex; flex-wrap: wrap; gap: 7px; }", CSS)

    def test_active_evidence_uses_supporting_count_route_type_and_duration(self) -> None:
        self.assertIn(">EVIDENCE<", HTML)
        self.assertIn("state.supporting_observation_count", MONITOR_PRESENTATION)
        self.assertIn('state.route_owner === "STR" ? "rejection" : "reclaim"', MONITOR_PRESENTATION)
        self.assertIn("qualifying ${type} observation", MONITOR_PRESENTATION)
        self.assertIn("Formation duration · ${duration}", MONITOR_PRESENTATION)
        self.assertNotIn("confirming_observation_count", MONITOR_PRESENTATION)
        self.assertIn(".fact-primary { display: block; color: var(--text); }", CSS)
        self.assertIn("color: var(--muted);", CSS.split(".fact-support", 1)[1])

    def test_unestablished_state_shows_raw_windows_without_progress_semantics(self) -> None:
        self.assertIn('primary: "No qualifying concentration"', MONITOR_PRESENTATION)
        self.assertIn('`BTD · ${observationCount(btdCount, "reclaim")}`', MONITOR_PRESENTATION)
        self.assertIn('`BTD window since · ${btdWindowStartedAt}`', MONITOR_PRESENTATION)
        self.assertIn('`STR · ${observationCount(strCount, "rejection")}`', MONITOR_PRESENTATION)
        self.assertIn('`STR window since · ${strWindowStartedAt}`', MONITOR_PRESENTATION)
        self.assertIn("buildEvidencePresentation(", JAVASCRIPT)
        self.assertIn("formatOperatorTimestampUtcMinus4,", JAVASCRIPT)
        self.assertIn("formatPrice,", JAVASCRIPT)
        self.assertIn("formatLocation,", JAVASCRIPT)
        self.assertIn('`CONCENTRATION CHECK · ${check.route}`', MONITOR_PRESENTATION)
        combined = HTML + JAVASCRIPT + MONITOR_PRESENTATION
        self.assertNotIn("3 / 4", combined)
        self.assertNotIn("progress", combined.lower())
        self.assertNotIn("predicted", combined.lower())

    def test_pre_activation_diagnostic_reuses_the_production_evaluator(self) -> None:
        self.assertIn("class ConcentrationDiagnostic", CONCENTRATION)
        self.assertIn("def evaluate_concentration(", CONCENTRATION)
        self.assertIn("_select_seed_and_cluster", CONCENTRATION)
        self.assertIn("evaluate_concentration(tuple(route_window), incoming.route)", STATE_ENGINE)
        self.assertIn("evaluate_concentration(route_windows[route], route).diagnostic", REPOSITORY)
        self.assertNotIn("evaluate_concentration", API)
        self.assertIn("MIN_CLUSTER_OBSERVATIONS", API)
        self.assertNotIn("CONCENTRATION_SPAN_THRESHOLD", JAVASCRIPT + MONITOR_PRESENTATION)
        self.assertIn('INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"', CONCENTRATION)
        self.assertIn('TOO_DISPERSED = "TOO_DISPERSED"', CONCENTRATION)
        self.assertIn('STRUCTURALLY_INELIGIBLE = "STRUCTURALLY_INELIGIBLE"', CONCENTRATION)
        self.assertIn('QUALIFIES = "QUALIFIES"', CONCENTRATION)

    def test_public_diagnostic_omits_audit_observation_ids(self) -> None:
        payload = REPOSITORY.split("def concentration_diagnostic_payload", 1)[1].split(
            "def log_unestablished_qualifying_concentration", 1
        )[0]
        self.assertNotIn('"newest_observation_id"', payload)
        self.assertNotIn('"selected_observation_ids"', payload)
        self.assertIn('"newest_observation_included"', payload)
        self.assertIn('"selected_observation_count"', payload)

    def test_concentration_check_uses_muted_readable_fact_layout(self) -> None:
        self.assertIn('label.className = "fact-section-label";', JAVASCRIPT)
        self.assertIn('line.className = "fact-diagnostic";', JAVASCRIPT)
        self.assertIn(".fact-section-label { display: block;", CSS)
        diagnostic_style = CSS.split(".fact-diagnostic {", 1)[1].split("}", 1)[0]
        self.assertIn("color: var(--muted);", diagnostic_style)
        self.assertIn("overflow-wrap: anywhere;", diagnostic_style)
        self.assertIn("line-height: 1.35;", diagnostic_style)

    def test_active_mrz_hides_pre_activation_diagnostic(self) -> None:
        active_branch = MONITOR_PRESENTATION.split('if (state.mrz_status === "active")', 1)[1].split(
            "const btdCount", 1
        )[0]
        self.assertIn("checks: []", active_branch)
        self.assertIn("Formation duration · ${duration}", active_branch)

    def test_heatmap_chips_do_not_include_evidence_counts(self) -> None:
        heatmap_group = JAVASCRIPT.split("function createLocationGroup", 1)[1].split(
            "function renderLocationHeatmap", 1
        )[0]
        self.assertNotIn("supporting_observation_count", heatmap_group)
        self.assertNotIn("confirming_observation_count", heatmap_group)
        self.assertIn("label.textContent = symbol;", heatmap_group)
        self.assertNotIn("label.textContent = tooltipText", heatmap_group)

    def test_activity_tiers_change_only_neutral_fill_and_preserve_chip_dimensions(self) -> None:
        tiers = ("low", "medium", "medium-high", "high", "strongest")
        for index, tier in enumerate(tiers):
            start = CSS.index(f".symbol-chip.activity-{tier}")
            end = CSS.find("\n", start)
            rule = CSS[start:end]
            self.assertIn("background-color: rgba(112, 132, 160", rule)
            for dimension in ("padding", "width", "height", "font-size", "border"):
                self.assertNotIn(dimension, rule)
            if index:
                previous = CSS.index(f".symbol-chip.activity-{tiers[index - 1]}")
                self.assertGreater(start, previous)

    def test_selected_active_hover_and_focus_treatments_remain_distinct(self) -> None:
        self.assertIn(".symbol-chip.active-mrz {", CSS)
        self.assertIn("background-color: transparent;", CSS.split(".symbol-chip.active-mrz", 1)[1])
        self.assertIn(".symbol-chip:hover {", CSS)
        self.assertIn(".symbol-chip.selected {", CSS)
        self.assertIn("box-shadow: 0 0 0 1px", CSS.split(".symbol-chip.selected", 1)[1])
        self.assertIn(".symbol-chip:focus-visible { outline: 2px solid var(--accent);", CSS)

    def test_activity_tooltip_is_custom_accessible_and_not_clipped_by_cards(self) -> None:
        self.assertIn('id="heatmapActivityTooltip" role="tooltip" hidden', HTML)
        self.assertIn('button.addEventListener("mouseenter",', JAVASCRIPT)
        self.assertIn('button.addEventListener("mouseleave",', JAVASCRIPT)
        self.assertIn('button.addEventListener("focus",', JAVASCRIPT)
        self.assertIn('button.addEventListener("blur",', JAVASCRIPT)
        self.assertIn('button.setAttribute("aria-describedby", activityTooltip.id);', JAVASCRIPT)
        self.assertIn('button.removeAttribute("aria-describedby");', JAVASCRIPT)
        tooltip_style = CSS.split(".activity-tooltip {", 1)[1].split("}", 1)[0]
        self.assertIn("position: fixed;", tooltip_style)
        self.assertIn("pointer-events: none;", tooltip_style)
        self.assertIn("max-width: calc(100vw - 16px);", tooltip_style)
        self.assertIn("window.innerWidth", JAVASCRIPT)
        self.assertIn("window.innerHeight", JAVASCRIPT)
        self.assertNotIn("title =", JAVASCRIPT)

    def test_activity_accessible_name_keeps_full_context(self) -> None:
        self.assertIn("activityTooltipText", HEATMAP_STATE)
        self.assertIn("accessibleChipLabel", HEATMAP_STATE)
        self.assertIn("no qualifying concentration, MRZ unestablished", HEATMAP_STATE)
        self.assertIn("activity.route", HEATMAP_STATE)
        self.assertIn("activity.observationType", HEATMAP_STATE)

    def test_evidence_migration_preserves_confirmation_and_audit_counts(self) -> None:
        self.assertIn("supporting_observation_count", EVIDENCE_MIGRATION)
        self.assertIn("old_supporting_observation_count", EVIDENCE_MIGRATION)
        self.assertIn("new_supporting_observation_count", EVIDENCE_MIGRATION)
        self.assertIn("SET supporting_observation_count = confirming_observation_count", EVIDENCE_MIGRATION)

    def test_formation_migration_is_nullable_and_does_not_fabricate_history(self) -> None:
        self.assertIn("formation_started_at", FORMATION_MIGRATION)
        self.assertIn("formation_completed_at", FORMATION_MIGRATION)
        self.assertIn("formation_duration_seconds", FORMATION_MIGRATION)
        self.assertIn("old_formation_started_at", FORMATION_MIGRATION)
        self.assertIn("new_formation_started_at", FORMATION_MIGRATION)
        self.assertNotIn("UPDATE active_mrz", FORMATION_MIGRATION)
        self.assertNotIn("SET formation_", FORMATION_MIGRATION)

    def test_current_location_uses_only_directional_structural_context(self) -> None:
        self.assertIn('id="currentLocationContext">—<', HTML)
        self.assertIn(
            'fields.currentLocationContext.textContent = state.current_location_context || "—";',
            JAVASCRIPT,
        )
        self.assertNotIn("Latest observation inside IPDA 20W", HTML + JAVASCRIPT)
        current_location_render = JAVASCRIPT.split("fields.currentLocation.textContent", 1)[1].split(
            "const evidence", 1
        )[0]
        self.assertNotIn("latest_observed_at", current_location_render)

    def test_latest_observation_combines_price_route_type_and_timestamp_once(self) -> None:
        self.assertIn(">LATEST OBSERVATION<", HTML)
        self.assertIn("formatPrice(state.latest_observation_price)", JAVASCRIPT)
        self.assertIn("formatLatestObservationContext(state, formatOperatorTimestampUtcMinus4)", JAVASCRIPT)
        self.assertIn("state.latest_observation_route", MONITOR_PRESENTATION)
        self.assertIn("state.latest_observation_type", MONITOR_PRESENTATION)
        self.assertEqual(JAVASCRIPT.count("state.latest_observed_at"), 0)
        self.assertEqual(MONITOR_PRESENTATION.count("state.latest_observed_at"), 1)

    def test_observation_timestamp_uses_canonical_observed_at_not_delivery_time(self) -> None:
        detail_payload = REPOSITORY.split("def detail_payload", 1)[1].split(
            "def current_price_location_value", 1
        )[0]
        self.assertIn('"latest_observed_at": iso(latest["observed_at"])', detail_payload)
        self.assertNotIn('iso(latest["received_at"])', detail_payload)

    def test_observation_timestamp_uses_shared_fixed_utc_minus_4_formatter(self) -> None:
        self.assertIn("function formatOperatorTimestampUtcMinus4(value)", OPERATOR_TIME)
        self.assertIn("UTC_MINUS_4_OFFSET_MILLISECONDS = 4 * 60 * 60 * 1000", OPERATOR_TIME)
        self.assertIn('timeZone: "UTC"', OPERATOR_TIME)
        self.assertIn('hourCycle: "h23"', OPERATOR_TIME)
        self.assertNotIn("Asia/Singapore", OPERATOR_TIME + JAVASCRIPT)
        self.assertNotIn("second:", OPERATOR_TIME)
        self.assertNotIn("timeZoneName:", OPERATOR_TIME)
        self.assertIn("UTC−4`", OPERATOR_TIME)
        self.assertIn("formatOperatorTimestampUtcMinus4", JAVASCRIPT)

    def test_observation_timestamp_has_neutral_fallback_and_is_not_mrz_gated(self) -> None:
        self.assertIn("if (!value) return null;", OPERATOR_TIME)
        latest_formatter = MONITOR_PRESENTATION.split("function formatLatestObservationContext", 1)[1].split(
            "function formatActivatedAt", 1
        )[0]
        self.assertNotIn("mrz_status", latest_formatter)

    def test_bottom_facts_remain_three_columns_and_responsive(self) -> None:
        self.assertIn("grid-template-columns: repeat(3, 1fr);", CSS)
        self.assertIn(".answer-grid, .context-grid, .facts { grid-template-columns: 1fr; }", CSS)
        self.assertIn(".fact-support {", CSS)
        self.assertIn("display: block;", CSS.split(".fact-support", 1)[1])
        self.assertIn("line-height: 1.35;", CSS.split(".fact-support", 1)[1])

    def test_selected_timestamp_adds_no_observation_history_request(self) -> None:
        load_symbol = JAVASCRIPT.split("async function loadSymbol(symbol)", 1)[1].split(
            "function renderSymbol", 1
        )[0]
        self.assertEqual(load_symbol.count("fetch("), 1)
        self.assertNotIn("observations", load_symbol)
        self.assertNotIn("history", load_symbol)


if __name__ == "__main__":
    unittest.main()
