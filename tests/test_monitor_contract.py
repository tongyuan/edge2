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
SAVED_GROUP_MIGRATION = (ROOT / "migrations/007_saved_symbol_groups.sql").read_text(
    encoding="utf-8"
)


class MonitorContractTests(unittest.TestCase):
    def test_operational_title_replaces_lab_wording(self) -> None:
        self.assertIn("MRZ Monitor", HTML)
        self.assertNotIn("Symbol Lab", HTML)

    def test_monitor_assets_are_versioned_together(self) -> None:
        version = "migration-eqm-20260904"
        self.assertIn(f'/static/styles.css?v={version}', HTML)
        self.assertIn(f'/static/heatmap-state.js?v={version}', HTML)
        self.assertIn(f'/static/operator-time.js?v={version}', HTML)
        self.assertIn(f'/static/monitor-presentation.js?v={version}', HTML)
        self.assertIn(f'/static/app.js?v={version}', HTML)
        self.assertLess(HTML.index("heatmap-state.js"), HTML.index("app.js"))
        self.assertLess(HTML.index("monitor-presentation.js"), HTML.index("app.js"))
        self.assertIn(
            "/static/diagnostics-nav.css?v=diagnostics-menu-20260827", HTML
        )
        self.assertIn(
            "/static/diagnostics-nav.js?v=diagnostics-menu-20260827", HTML
        )

    def test_monitor_consolidates_diagnostic_links_in_shared_dropdown(self) -> None:
        self.assertIn('href="/diagnostics/activation-feasibility"', HTML)
        self.assertIn("MRZ Formation Diagnostics", HTML)
        self.assertNotIn(">Activation Feasibility<", HTML)
        self.assertIn('href="/diagnostics/mrz-robustness"', HTML)
        self.assertNotIn('href="/diagnostics/mrz-robustness-report"', HTML)
        self.assertNotIn('href="/diagnostics/trading-window-feasibility"', HTML)
        self.assertNotIn("Trading Window Feasibility", HTML)
        self.assertIn('aria-label="Operator navigation"', HTML)
        self.assertIn('data-diagnostics-trigger', HTML)

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
        self.assertIn(">CURRENT PRICE LOCATION<", HTML)
        self.assertNotIn(">CURRENT LOCATION<", HTML)
        self.assertIn('id="structuralLocation"', HTML)
        self.assertIn('id="currentPriceLocation"', HTML)
        self.assertIn("formatLocation(state.current_price_location)", JAVASCRIPT)

        detail_payload = REPOSITORY.split("def detail_payload", 1)[1].split(
            "def current_price_location_value", 1
        )[0]
        current_price_classifier = REPOSITORY.split(
            "def current_price_location_value", 1
        )[1].split("def sanitize_payload", 1)[0]
        self.assertIn('"structural_location": active.structural_location.value', detail_payload)
        self.assertIn('"current_price_location": current_price_location_value(latest)', detail_payload)
        self.assertIn('Decimal(latest["observation_price"])', current_price_classifier)
        self.assertNotIn("active.core_mrz_midpoint", current_price_classifier)

    def test_symbol_header_links_active_authority_to_its_exact_operator_card(self) -> None:
        self.assertIn('id="operatorCardLink" hidden>Operator Card</a>', HTML)
        self.assertIn("operatorCardHref(state)", JAVASCRIPT)
        self.assertIn("fields.operatorCard.hidden = operatorCardUrl === null;", JAVASCRIPT)
        self.assertIn("fields.operatorCard.href = operatorCardUrl;", JAVASCRIPT)
        self.assertIn('state?.mrz_status !== "active"', MONITOR_PRESENTATION)
        self.assertIn("encodeURIComponent(state.symbol)", MONITOR_PRESENTATION)
        self.assertIn("/diagnostics/mrz-robustness?symbol=", MONITOR_PRESENTATION)

    def test_operator_card_link_is_navigation_only_and_mobile_safe(self) -> None:
        self.assertNotIn('/api/diagnostics/mrz-robustness', JAVASCRIPT)
        symbol_renderer = JAVASCRIPT.split("function renderSymbol(state)", 1)[1].split(
            'select.addEventListener("change"', 1
        )[0]
        self.assertNotIn("preventDefault", symbol_renderer)
        self.assertNotIn("window.history", symbol_renderer)
        self.assertNotIn("globalThis.history", symbol_renderer)
        self.assertIn(".operator-card-link[hidden] { display: none; }", CSS)
        responsive = CSS.split("@media (max-width: 680px)", 1)[1]
        self.assertIn(".symbol-header-actions { justify-content: flex-start; width: 100%; }", responsive)

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
        self.assertIn(">LOCATION DISTRIBUTION<", HTML)
        self.assertIn(">LOCATION HEATMAP<", HTML)
        self.assertIn(">SELECTED SYMBOL DETAIL<", HTML)
        self.assertLess(HTML.index(">LOCATION DISTRIBUTION<"), HTML.index(">LOCATION HEATMAP<"))
        self.assertLess(HTML.index(">LOCATION HEATMAP<"), HTML.index(">SELECTED SYMBOL DETAIL<"))

    def test_location_distribution_has_four_canonical_buckets_and_two_halves(self) -> None:
        self.assertEqual(HTML.count('class="location-distribution-cell"'), 4)
        for label in (
            "Deep Discount",
            "Shallow Discount",
            "Shallow Premium",
            "Deep Premium",
        ):
            with self.subTest(label=label):
                self.assertIn(f"<h3>{label}</h3>", HTML)
        self.assertIn('id="distributionDiscountTotal"', HTML)
        self.assertIn('id="distributionPremiumTotal"', HTML)
        self.assertEqual(HTML.count(">Current<"), 4)
        self.assertEqual(HTML.count(">Historical migration<"), 4)
        self.assertEqual(HTML.count(">No migration history<"), 4)
        for prefix in (
            "DeepDiscount",
            "ShallowDiscount",
            "ShallowPremium",
            "DeepPremium",
        ):
            with self.subTest(prefix=prefix):
                self.assertIn(f'id="distribution{prefix}History" hidden', HTML)
                self.assertIn(f'id="distribution{prefix}Higher"', HTML)
                self.assertIn(f'id="distribution{prefix}Lower"', HTML)
                self.assertIn(f'id="distribution{prefix}Samples">n = 0<', HTML)
        self.assertNotIn("Bullish", HTML)
        self.assertNotIn("Bearish", HTML)

    def test_distribution_reuses_the_exact_grouped_heatmap_population(self) -> None:
        render_overview = JAVASCRIPT.split("function renderMonitorOverview", 1)[1].split(
            "function updateSelectedChip", 1
        )[0]
        self.assertEqual(
            render_overview.count(
                "const allGroups = groupSymbolsByLocation(overviewSymbols, minimumClusterObservations);"
            ),
            1,
        )
        self.assertIn(
            "renderLocationDistribution(allGroups, locationMigrationTendency);",
            render_overview,
        )
        self.assertIn("visibleSymbolsForGroupTracking(overviewSymbols, groupTrackingState)", render_overview)
        self.assertLess(
            render_overview.index(
                "renderLocationDistribution(allGroups, locationMigrationTendency);"
            ),
            render_overview.index("visibleSymbolsForGroupTracking"),
        )
        self.assertIn("locationDistributionFromGroups(groups)", JAVASCRIPT)
        distribution_builder = HEATMAP_STATE.split(
            "function locationDistributionFromGroups(groups)", 1
        )[1].split("function formatLocationPercentage", 1)[0]
        self.assertIn("primaryLocationKeys", distribution_builder)
        self.assertNotIn("current_price_location", distribution_builder)
        self.assertNotIn("hasActiveMrz", distribution_builder)
        self.assertNotIn("fetch(", distribution_builder)
        self.assertNotIn("location_distribution", API)

    def test_historical_migration_uses_canonical_old_authority_provenance(self) -> None:
        tendency_method = REPOSITORY.split(
            "    def location_migration_tendency(self)", 1
        )[1].split("\n    def ", 1)[0]
        self.assertIn("current_event.event_type = 'MRZ_MIGRATED'", tendency_method)
        self.assertIn("current_event.old_core_mrz_lower", tendency_method)
        self.assertIn("current_event.old_core_mrz_upper", tendency_method)
        self.assertIn("current_event.new_core_mrz_midpoint", tendency_method)
        self.assertIn(
            "previous_authority.structural_location\n                                AS starting_structural_location",
            tendency_method,
        )
        self.assertIn(
            "source_event.event_type IN (\n                                  'MRZ_ACTIVATED', 'MRZ_MIGRATED'",
            tendency_method,
        )
        self.assertIn("source_event.occurred_at <= current_event.occurred_at", tendency_method)
        self.assertIn("SELECT DISTINCT ON (current_event.event_key)", tendency_method)
        self.assertNotIn("created_at", tendency_method)
        self.assertNotIn("ROUTE_CHANGED", tendency_method)

    def test_migration_tendency_is_added_to_existing_overview_fetch(self) -> None:
        self.assertIn(
            '"location_migration_tendency": repository.location_migration_tendency()',
            API,
        )
        load_symbols = JAVASCRIPT.split("async function loadSymbols()", 1)[1].split(
            "async function handleHeatmapChipClick", 1
        )[0]
        self.assertEqual(load_symbols.count('fetch("/api/symbols")'), 1)
        self.assertIn(
            "locationMigrationTendency = payload.location_migration_tendency || {};",
            load_symbols,
        )
        renderer = JAVASCRIPT.split("function renderLocationDistribution", 1)[1].split(
            "function renderSelectedGroupPanel", 1
        )[0]
        self.assertIn("migrationTendencyPresentation(migrationTendency?.[key])", renderer)
        self.assertIn("fieldsForLocation.history.hidden = !migration.hasHistory;", renderer)
        self.assertIn("fieldsForLocation.historyEmpty.hidden = migration.hasHistory;", renderer)
        self.assertIn("fieldsForLocation.samples.textContent = migration.sampleLabel;", renderer)

    def test_distribution_is_compact_and_mobile_safe(self) -> None:
        self.assertIn(
            ".location-distribution-grid {\n  display: grid;\n  grid-template-columns: repeat(4, minmax(0, 1fr));",
            CSS,
        )
        self.assertIn(
            ".location-distribution-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }",
            CSS,
        )
        self.assertIn("max-width: 100%;", CSS.split(".location-distribution-grid", 1)[1])
        self.assertIn("min-width: 0;", CSS.split(".location-distribution-cell", 1)[1])
        self.assertIn(
            ".location-migration-directions { grid-template-columns: 1fr; gap: 4px; }",
            CSS,
        )

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

    def test_heatmap_groups_each_symbol_once_and_uses_deterministic_ranking_hierarchy(self) -> None:
        self.assertIn('const key = allLocationKeys.has(currentLocation) ? currentLocation : "unavailable";', HEATMAP_STATE)
        self.assertEqual(HEATMAP_STATE.count("groups[key].push(symbolState);"), 1)
        self.assertIn("function compareSymbolsByActivity(left, right)", HEATMAP_STATE)
        self.assertIn("function compareSymbolsForHeatmap(left, right, minimumObservations)", HEATMAP_STATE)
        self.assertIn("Number(hasActiveMrz(right)) - Number(hasActiveMrz(left))", HEATMAP_STATE)
        self.assertIn("Number(rightEligible) - Number(leftEligible)", HEATMAP_STATE)
        self.assertIn("leftRanking.minimumAllowance - rightRanking.minimumAllowance", HEATMAP_STATE)
        self.assertIn("rightRanking.observationCount - leftRanking.observationCount", HEATMAP_STATE)
        self.assertIn("return compareSymbolsByActivity(left, right);", HEATMAP_STATE)
        self.assertIn("String(left.symbol).localeCompare(String(right.symbol))", HEATMAP_STATE)
        self.assertIn("compareSymbolsForHeatmap(left, right, minimumObservations)", HEATMAP_STATE)
        self.assertIn('heatmapEmpty.textContent = "No symbols yet";', JAVASCRIPT)

    def test_heatmap_refresh_preserves_selected_symbol_after_reordering(self) -> None:
        self.assertIn("function preservedSelectedSymbol(currentSymbol, symbols)", HEATMAP_STATE)
        load_symbols = JAVASCRIPT.split("async function loadSymbols()", 1)[1].split(
            "async function selectSymbol", 1
        )[0]
        self.assertIn("preservedSelectedSymbol(select.value, payload.symbols)", load_symbols)
        self.assertIn("select.value = selectedSymbol;", load_symbols)
        self.assertIn("renderMonitorOverview();", load_symbols)
        render_overview = JAVASCRIPT.split("function renderMonitorOverview", 1)[1].split(
            "function updateSelectedChip", 1
        )[0]
        self.assertIn("updateSelectedChip(select.value);", render_overview)

    def test_heatmap_active_indicator_uses_authoritative_status_and_is_accessible(self) -> None:
        self.assertIn('return symbolState.mrz_status === "active";', HEATMAP_STATE)
        active_method = HEATMAP_STATE.split("function hasActiveMrz", 1)[1].split(
            "function safeActivityCount", 1
        )[0]
        self.assertNotIn("confirming_observation_count", active_method)
        self.assertNotIn("route_owner", active_method)
        heatmap_group = JAVASCRIPT.split("function createLocationGroup", 1)[1].split(
            "function renderLocationDistribution", 1
        )[0]
        self.assertIn("const active = hasActiveMrz(symbolState);", heatmap_group)
        self.assertIn('indicator.className = "active-mrz-dot";', heatmap_group)
        self.assertIn('indicator.setAttribute("aria-hidden", "true");', heatmap_group)
        self.assertIn("accessibleChipLabel(symbolState, locationLabel)", heatmap_group)
        self.assertNotIn("BTD", heatmap_group)
        self.assertNotIn("STR", heatmap_group)

    def test_heatmap_has_one_quiet_active_legend_without_animation(self) -> None:
        legends = HTML.split('class="heatmap-legends"', 1)[1].split("</div>", 1)[0]
        self.assertEqual(legends.count(">Active MRZ<"), 1)
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
        self.assertIn("concentrationCheckEligible(symbolState, minimumClusterObservations)", heatmap_group)

    def test_heatmap_ranking_reuses_backend_production_diagnostics(self) -> None:
        ranking_payload = REPOSITORY.split("def concentration_ranking_payload", 1)[1].split(
            "class EdgeRepository", 1
        )[0]
        self.assertIn("evaluate_concentration(route_windows[route], route).diagnostic", ranking_payload)
        self.assertIn("diagnostic.minimum_required_allowance_pct", ranking_payload)
        self.assertIn("-diagnostic.retained_observation_count", ranking_payload)
        self.assertIn('"concentration_ranking": concentration_ranking_payload(', REPOSITORY)
        self.assertNotIn("CONCENTRATION_SPAN_THRESHOLD", HEATMAP_STATE + JAVASCRIPT)
        self.assertNotIn("selected_lower", HEATMAP_STATE + JAVASCRIPT)

    def test_heatmap_click_preserves_detail_selection_when_group_tracking_is_off(self) -> None:
        self.assertIn(
            'button.addEventListener("click", () => handleHeatmapChipClick(symbol).catch(showError));',
            JAVASCRIPT,
        )
        chip_handler = JAVASCRIPT.split("async function handleHeatmapChipClick", 1)[1].split(
            "async function selectSymbol", 1
        )[0]
        self.assertIn("if (!isGroupSelectionMode(groupTrackingState))", chip_handler)
        self.assertIn("await selectSymbol(symbol);", chip_handler)
        self.assertIn("toggleGroupSymbol(groupTrackingState, symbol)", chip_handler)
        self.assertIn("renderMonitorOverview();", chip_handler)
        self.assertIn("select.value = symbol;", JAVASCRIPT)
        self.assertIn("await loadSymbol(symbol);", JAVASCRIPT)
        self.assertNotIn("window.location", JAVASCRIPT)

    def test_group_tracking_defaults_off_and_uses_semantic_controls(self) -> None:
        toggle = HTML.split('id="groupTrackingToggle"', 1)[0].rsplit("<input", 1)[1]
        self.assertIn('type="checkbox"', toggle)
        self.assertNotIn("checked", toggle)
        self.assertIn('id="groupTrackingStateLabel">Off<', HTML)
        self.assertIn('id="groupTrackingWorkspace"', HTML)
        self.assertIn('aria-labelledby="tracked-groups-title" aria-live="polite" hidden', HTML)
        self.assertIn('id="savedGroupSelect" disabled', HTML)
        self.assertIn('id="newSavedGroup" type="button"', HTML)
        self.assertIn('id="groupEditor" hidden', HTML)
        self.assertIn('type="checkbox" id="showSelectedOnly"', HTML)
        self.assertIn('id="clearSelectedGroup" type="button"', HTML)
        initial_state = HEATMAP_STATE.split("function createGroupTrackingState", 1)[1].split(
            "function setGroupTrackingEnabled", 1
        )[0]
        self.assertIn("enabled: false", initial_state)
        self.assertIn('mode: "browse"', initial_state)
        self.assertIn("activeGroupId: null", initial_state)
        self.assertIn("showSelectedOnly: false", initial_state)
        self.assertIn("selectedSymbols: new Set()", initial_state)

    def test_saved_group_view_contains_the_two_requested_views_and_metrics(self) -> None:
        self.assertIn('id="savedGroupHeading"', HTML)
        self.assertIn('id="selectedGroupSymbols"', HTML)
        self.assertIn('id="currentStateTab"', HTML)
        self.assertIn('aria-selected="true" aria-controls="currentStatePanel"', HTML)
        self.assertIn('id="migrationPathTab"', HTML)
        self.assertIn('id="migrationPathPanel"', HTML)
        for field_id in (
            "groupDeepDiscountCount",
            "groupShallowDiscountCount",
            "groupShallowPremiumCount",
            "groupDeepPremiumCount",
            "groupActiveMrzCount",
            "groupHigherCount",
            "groupLowerCount",
            "groupNoMigrationCount",
        ):
            with self.subTest(field_id=field_id):
                self.assertIn(f'id="{field_id}"', HTML)
        combined = HTML + JAVASCRIPT + HEATMAP_STATE
        for prohibited in (
            "group bias",
            "average formation",
            "median formation",
            "pressure score",
            "performance statistics",
        ):
            self.assertNotIn(prohibited, combined.lower())

    def test_group_selected_state_is_distinct_and_coexists_with_heatmap_encodings(self) -> None:
        heatmap_group = JAVASCRIPT.split("function createLocationGroup", 1)[1].split(
            "function renderLocationDistribution", 1
        )[0]
        self.assertIn('button.classList.toggle("active-mrz", active);', heatmap_group)
        self.assertIn('button.classList.toggle("group-selected", groupSelected);', heatmap_group)
        self.assertIn('"evidence-ready",', heatmap_group)
        self.assertIn('button.classList.add(`activity-${activity.tier}`);', heatmap_group)
        self.assertIn('check.textContent = "✓";', heatmap_group)
        self.assertIn('check.setAttribute("aria-hidden", "true");', heatmap_group)
        group_style = CSS.split(".symbol-chip.group-selected {", 1)[1].split("}", 1)[0]
        self.assertIn("border-color: #83aef0;", group_style)
        self.assertIn("box-shadow: 0 0 0 2px", group_style)
        self.assertNotIn("background-color", group_style)
        self.assertIn(".symbol-chip.evidence-ready.group-selected {", CSS)

    def test_group_filters_and_persistent_crud_use_the_saved_group_api(self) -> None:
        self.assertIn('showSelectedOnly.addEventListener("change",', JAVASCRIPT)
        self.assertIn("setShowSelectedOnly(", JAVASCRIPT)
        self.assertIn('clearSelectedGroup.addEventListener("click",', JAVASCRIPT)
        self.assertIn("clearGroupSelection(groupTrackingState)", JAVASCRIPT)
        self.assertIn('groupTrackingToggle.addEventListener("change",', JAVASCRIPT)
        self.assertIn("setGroupTrackingEnabled(", JAVASCRIPT)
        self.assertIn("if (!enabled) return createGroupTrackingState();", HEATMAP_STATE)
        self.assertIn("selectedSymbols: new Set()", HEATMAP_STATE)
        combined = HTML + JAVASCRIPT + HEATMAP_STATE
        for persistence_api in (
            "localStorage",
            "sessionStorage",
            "document.cookie",
            "history.pushState",
        ):
            self.assertNotIn(persistence_api, combined)
        self.assertNotIn("URLSearchParams", HEATMAP_STATE)
        self.assertIn("Save Group", HTML)
        self.assertIn("Group name", HTML)
        self.assertIn('requestJson("/api/groups")', JAVASCRIPT)
        self.assertIn('method: editing ? "PUT" : "POST"', JAVASCRIPT)
        self.assertIn('{ method: "DELETE" }', JAVASCRIPT)
        self.assertIn("CREATE TABLE IF NOT EXISTS saved_symbol_groups", SAVED_GROUP_MIGRATION)
        self.assertNotIn("mrz_events", SAVED_GROUP_MIGRATION)
        self.assertNotIn("active_mrz", SAVED_GROUP_MIGRATION)
        self.assertNotIn("observations", SAVED_GROUP_MIGRATION)

    def test_group_tracking_reads_canonical_current_and_migration_state(self) -> None:
        report = REPOSITORY.split("    def saved_group_report", 1)[1].split(
            "    def saved_group_migration_path", 1
        )[0]
        self.assertIn("LEFT JOIN active_mrz active", report)
        self.assertIn("ORDER BY observed_at DESC, received_at DESC, id DESC", report)
        self.assertIn("event_type = 'MRZ_MIGRATED'", report)
        self.assertIn("ORDER BY sequence DESC", report)
        self.assertIn('breadth[direction or "no_migration"] += 1', report)
        path = REPOSITORY.split("    def saved_group_migration_path", 1)[1].split(
            "    def symbols(self)", 1
        )[0]
        self.assertIn("events.event_type IN ('MRZ_ACTIVATED', 'MRZ_MIGRATED')", path)
        self.assertIn("events.occurred_at ASC", path)
        self.assertNotIn("events.created_at", path)
        self.assertIn('"location": location', path)
        self.assertNotIn("classify_ipda_location", path)
        self.assertNotIn("migration_pressure", report + path)
        self.assertNotIn("successor", report + path)

    def test_migration_path_tooltip_derives_eqm_from_adjacent_authorities_only(self) -> None:
        tooltip = JAVASCRIPT.split("function migrationStateTooltip", 1)[1].split(
            "function renderMigrationPath", 1
        )[0]
        renderer = JAVASCRIPT.split("function renderMigrationPath", 1)[1].split(
            "function renderLocationHeatmap", 1
        )[0]
        helper = HEATMAP_STATE.split("function authoritativeMrzEqmPair", 1)[1].split(
            "const heatmapState", 1
        )[0]
        self.assertIn("states[index - 1]?.midpoint", helper)
        self.assertIn("states[index]?.midpoint", helper)
        self.assertIn("(currentMidpoint + previousMidpoint) / 2", helper)
        self.assertNotIn("direction", helper)
        self.assertIn("authoritativeMrzEqmPair(path.states, index)", renderer)
        self.assertIn("Current midpoint:", tooltip)
        self.assertIn("Previous MRZ midpoint:", tooltip)
        self.assertIn("MRZ EQM:", tooltip)
        self.assertIn("if (eqmPair)", tooltip)
        self.assertNotIn("N/A", tooltip)
        self.assertIn("formatPrice(eqmPair.previousMidpoint)", tooltip)
        self.assertIn("formatPrice(eqmPair.eqm)", tooltip)

    def test_migration_path_eqm_adds_no_visual_timeline_elements(self) -> None:
        renderer = JAVASCRIPT.split("function renderMigrationPath", 1)[1].split(
            "function renderLocationHeatmap", 1
        )[0]
        self.assertIn('line.className = "migration-path-line"', renderer)
        self.assertIn('node.className = `migration-path-state', renderer)
        self.assertIn("node.title = migrationStateTooltip", renderer)
        self.assertIn('node.setAttribute("aria-label", node.title)', renderer)
        self.assertNotIn("migration-path-eqm", HTML + JAVASCRIPT + CSS)
        self.assertNotIn("eqm-marker", HTML + JAVASCRIPT + CSS)

    def test_group_tracking_mobile_layout_wraps_without_horizontal_overflow(self) -> None:
        self.assertIn("min-height: 44px;", CSS.split(".group-tracking-toggle", 1)[1])
        self.assertIn("flex-wrap: wrap;", CSS.split(".selected-group-symbols", 1)[1])
        self.assertIn("max-width: 100%;", CSS.split(".selected-group-symbols li", 1)[1])
        self.assertIn(".migration-path-scroller", CSS)
        self.assertIn("overflow-x: auto;", CSS.split(".migration-path-scroller", 1)[1])
        self.assertIn("max-width: 100%;", CSS.split(".migration-path-scroller", 1)[1])
        self.assertIn(".current-state-panel { grid-template-columns: 1fr; }", CSS)
        self.assertIn("position: sticky;", CSS.split(".migration-path-row-label", 1)[1])

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
        self.assertIn("timestampFormatter(state.formation_started_at)", MONITOR_PRESENTATION)
        self.assertIn("First ${type} · ${formationFirst}", MONITOR_PRESENTATION)
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
        self.assertIn("evaluation = evaluate_concentration(", STATE_ENGINE)
        self.assertIn("tuple(route_window)", STATE_ENGINE)
        self.assertIn("minimum_required_count=minimum_required_count", STATE_ENGINE)
        self.assertIn("concentration_threshold=concentration_threshold", STATE_ENGINE)
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
        heatmap_group = JAVASCRIPT.split("function createLocationGroup", 1)[1].split(
            "function renderLocationDistribution", 1
        )[0]
        self.assertNotIn("title =", heatmap_group)

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
