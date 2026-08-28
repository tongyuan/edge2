const assert = require("node:assert/strict");
const fs = require("node:fs");
const {
  crossSymbolTableMarkup,
  incrementalCohortsMarkup,
  interpretationMarkup,
  lifecycleComparisonMarkup,
  policyComparisonMarkup,
  productionSummaryMarkup,
  routeBreakdownMarkup,
  sampleConfidenceMarkup,
  symbolDetailMarkup,
} = require("../app/dormant/mrz-robustness-report.js");

const rate = (numerator, denominator, percentage) => ({ numerator, denominator, percentage });
const metric = {
  formed_mrz_count: 2,
  eligible_symbol_route_histories: 3,
  formation_coverage: rate(2, 3, "66.7"),
  formations_with_post_activation_evidence: 2,
  resolved_case_count: 2,
  unresolved_case_count: 0,
  supportive_outcome_count: 8,
  adverse_outcome_count: 2,
  neutral_unresolved_outcome_count: 1,
  resolved_outcome_count: 10,
  supportive_rate: rate(8, 10, "80"),
  adverse_rate: rate(2, 10, "20"),
  supportive_to_adverse_balance: "8 : 2",
  median_time_to_first_supportive_seconds: "900",
  time_to_first_supportive_sample_count: 2,
  median_time_to_first_adverse_seconds: "1800",
  time_to_first_adverse_sample_count: 1,
  early_adverse_incidence: rate(1, 2, "50"),
  early_adverse_window_observations: 4,
  median_containment_percentage: "75",
  containment_sample_count: 2,
  median_observed_lifespan_seconds: "7200",
  observed_lifespan_sample_count: 2,
  completed_lifecycle_count: 1,
  censored_lifecycle_count: 1,
  median_time_to_migration_seconds: "3600",
  time_to_migration_sample_count: 1,
  migration_confirmation_incidence: rate(1, 2, "50"),
  early_migration_incidence: rate(0, 2, "0"),
  migration_pressure_incidence: rate(1, 2, "50"),
  median_time_to_first_pressure_seconds: "1800",
  time_to_first_pressure_sample_count: 1,
  successor_pressure_incidence: rate(1, 2, "50"),
  route_integrity_maintained: rate(2, 2, "100"),
  route_breakdown: [
    { route: "BTD", resolved_case_count: 1, unresolved_case_count: 0, supportive_rate: rate(4, 5, "80"), adverse_rate: rate(1, 5, "20") },
    { route: "STR", resolved_case_count: 1, unresolved_case_count: 0, supportive_rate: rate(4, 5, "80"), adverse_rate: rate(1, 5, "20") },
  ],
};

const sample = sampleConfidenceMarkup({
  label: "Sample confidence · Preliminary",
  eligible_symbol_route_histories: 3,
  production_mrz_formations: 2,
  production_formed_denominator: 3,
  production_formations_with_post_activation_evidence: 2,
  production_resolved_case_count: 2,
  production_unresolved_case_count: 0,
  completed_migration_lifecycles: 1,
});
assert.match(sample, /Preliminary/);
assert.match(sample, /3 eligible histories/);
assert.match(sample, /of 3 eligible histories/);

const production = productionSummaryMarkup(metric);
assert.match(production, /Formation/);
assert.match(production, /Supportive outcomes/);
assert.match(production, /Adverse outcomes/);
assert.match(production, /8 : 2/);
assert.match(production, /First supportive/);
assert.match(production, /research-only/);
assert.doesNotMatch(production, /performance/i);

const policies = [
  { ...metric, allowance_percent: "1.00" },
  { ...metric, allowance_percent: "1.50" },
  { ...metric, allowance_percent: "2.00" },
];
const comparison = policyComparisonMarkup(policies);
assert.match(comparison, /1\.00%/);
assert.match(comparison, /1\.50%/);
assert.match(comparison, /2\.00%/);
assert.match(comparison, /Formation coverage · context only/);
assert.match(comparison, /Resolved MRZ cases/);
assert.match(comparison, /Supportive outcomes/);
assert.match(comparison, /Median time to first adverse/);
assert.doesNotMatch(comparison, /best|optimal|recommended/i);

const routeBreakdown = routeBreakdownMarkup(policies);
assert.match(routeBreakdown, /BTD/);
assert.match(routeBreakdown, /STR/);
assert.match(routeBreakdown, /Supportive \/ adverse/);

const lifecycle = lifecycleComparisonMarkup(policies);
assert.match(lifecycle, /Mechanical persistence \/ lifecycle/);
assert.match(lifecycle, /Median containment/);
assert.match(lifecycle, /Migration pressure/);
assert.match(lifecycle, /Structural-location alignment/);

const cohort = incrementalCohortsMarkup([{
  ...metric,
  label: "Incremental 1.50% cohort",
  definition: "Fails at 1.00% and forms at 1.50%",
  history_count: 1,
}]);
assert.match(cohort, /Fails at 1\.00% and forms at 1\.50%/);
assert.match(cohort, /Resolved \/ unresolved cases/);
assert.match(cohort, /Supportive outcomes/);
assert.match(cohort, /First adverse/);
assert.match(cohort, /Mechanical persistence \/ lifecycle/);

const record = {
  formed: true,
  symbol: "BTCUSDT",
  route: "BTD",
  mechanical_lifecycle_label: "Stable",
  mechanical_lifecycle_status: "STABLE",
  mrz: { lower: "110", upper: "110.6", midpoint: "110.3", structural_location: "deep_discount_core_mrz" },
  activated_at: "2026-08-20T12:00:04Z",
  formation_policy: { allowance_percent: "1.00" },
  post_activation_observation_count: 1,
  structural_response: {
    supportive_outcome_count: 1,
    adverse_outcome_count: 0,
    neutral_unresolved_outcome_count: 0,
    resolved_outcome_count: 1,
    supportive_rate: rate(1, 1, "100"),
    adverse_rate: rate(0, 1, "0"),
    supportive_to_adverse_balance: "1 : 0",
    first_supportive: { observation_number: 1, seconds_from_activation: "1" },
    first_adverse: { observation_number: null, seconds_from_activation: null },
  },
  containment: { percentage: "100" },
  observed_lifespan_seconds: "1",
  lifecycle: { completed: false, censored: true, time_to_migration_seconds: null },
  boundary_pressure: { outside_envelope_observation_count: 0 },
  midpoint_stability: { label: "Centered around midpoint", median_signed_displacement_percentage_of_activation_ipda: "0" },
  route_integrity: { status: "MAINTAINED" },
  migration_pressure: { status: "STABLE" },
  successor_watch: { status: "NO_SUCCESSOR_CANDIDATE" },
};
const timestamp = () => "20 Aug 2026 · 08:00 UTC−4";
const crossSymbol = crossSymbolTableMarkup([record], timestamp);
assert.match(crossSymbol, /20 Aug 2026 · 08:00 UTC−4/);
assert.match(crossSymbol, /First supportive/);
assert.match(crossSymbol, /1 : 0/);
const detail = symbolDetailMarkup({ symbol: "BTCUSDT", route: "BTD", policies: [record, { formed: false, formation_policy: { allowance_percent: "1.50" } }] }, timestamp);
assert.match(detail, /Post observations/);
assert.match(detail, /Boundary pressure/);
assert.match(detail, /Midpoint stability/);
assert.match(detail, /Supportive rate/);
assert.match(detail, /Mechanical persistence \/ lifecycle/);
assert.match(detail, /No MRZ formed under this policy/);

const interpretation = interpretationMarkup({
  heading: "Evidence remains preliminary",
  text: "The incremental cohorts are worthy of further monitoring.",
  facts: ["1.00% formed 2 of 3 eligible histories."],
});
assert.match(interpretation, /worthy of further monitoring/);

const html = fs.readFileSync(require.resolve("../app/dormant/mrz-robustness-report.html"), "utf8");
const css = fs.readFileSync(require.resolve("../app/dormant/mrz-robustness-report.css"), "utf8");
const source = fs.readFileSync(require.resolve("../app/dormant/mrz-robustness-report.js"), "utf8");
assert.match(html, /SAMPLE CONFIDENCE \/ SCOPE/);
assert.match(html, /PURPOSE/);
assert.match(html, /PRIMARY DURABILITY COMPARISON/);
assert.match(html, /BTD \/ STR BREAKDOWN/);
assert.match(html, /INCREMENTAL COHORT ANALYSIS/);
assert.match(html, /Geometry note/);
assert.match(html, /partly influenced by MRZ geometry/);
assert.match(html, /SECONDARY LIFECYCLE DIAGNOSTICS/);
assert.match(css, /body \{ overflow-x: hidden; \}/);
assert.match(css, /@media \(max-width: 700px\)/);
assert.match(css, /\.policy-detail-grid \{ grid-template-columns: 1fr; \}/);
assert.doesNotMatch(source, /recommended|optimal|best/i);
assert.doesNotMatch(source, /fetch\([^)]*observations/i);

console.log("MRZ robustness report presentation tests passed");
