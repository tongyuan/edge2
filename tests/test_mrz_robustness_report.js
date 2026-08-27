const assert = require("node:assert/strict");
const fs = require("node:fs");
const {
  crossSymbolTableMarkup,
  incrementalCohortsMarkup,
  interpretationMarkup,
  policyComparisonMarkup,
  productionSummaryMarkup,
  sampleConfidenceMarkup,
  symbolDetailMarkup,
} = require("../app/static/mrz-robustness-report.js");

const rate = (numerator, denominator, percentage) => ({ numerator, denominator, percentage });
const metric = {
  formed_mrz_count: 2,
  eligible_symbol_route_histories: 3,
  formation_coverage: rate(2, 3, "66.7"),
  formations_with_post_activation_evidence: 2,
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
};

const sample = sampleConfidenceMarkup({
  label: "Sample confidence · Preliminary",
  eligible_symbol_route_histories: 3,
  production_mrz_formations: 2,
  production_formed_denominator: 3,
  production_formations_with_post_activation_evidence: 2,
  completed_migration_lifecycles: 1,
});
assert.match(sample, /Preliminary/);
assert.match(sample, /3 eligible histories/);
assert.match(sample, /of 3 eligible histories/);

const production = productionSummaryMarkup(metric);
assert.match(production, /Formation/);
assert.match(production, /Successor pressure/);
assert.match(production, /Route integrity maintained/);
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
assert.match(comparison, /Migration confirmed/);
assert.doesNotMatch(comparison, /best|optimal|recommended/i);

const cohort = incrementalCohortsMarkup([{
  ...metric,
  label: "Incremental 1.50% cohort",
  definition: "Fails at 1.00% and forms at 1.50%",
  history_count: 1,
}]);
assert.match(cohort, /Fails at 1\.00% and forms at 1\.50%/);
assert.match(cohort, /Completed \/ censored/);
assert.match(cohort, /Time to migration/);

const record = {
  formed: true,
  symbol: "BTCUSDT",
  route: "BTD",
  durability_label: "Stable",
  durability_status: "STABLE",
  mrz: { lower: "110", upper: "110.6", midpoint: "110.3", structural_location: "deep_discount_core_mrz" },
  activated_at: "2026-08-20T12:00:04Z",
  formation_policy: { allowance_percent: "1.00" },
  post_activation_observation_count: 1,
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
assert.match(crossSymbol, /censored/);
const detail = symbolDetailMarkup({ symbol: "BTCUSDT", route: "BTD", policies: [record, { formed: false, formation_policy: { allowance_percent: "1.50" } }] }, timestamp);
assert.match(detail, /Post observations/);
assert.match(detail, /Boundary pressure/);
assert.match(detail, /Midpoint stability/);
assert.match(detail, /No MRZ formed under this policy/);

const interpretation = interpretationMarkup({
  heading: "Evidence remains preliminary",
  text: "The incremental cohorts are worthy of further monitoring.",
  facts: ["1.00% formed 2 of 3 eligible histories."],
});
assert.match(interpretation, /worthy of further monitoring/);

const html = fs.readFileSync(require.resolve("../app/static/mrz-robustness-report.html"), "utf8");
const css = fs.readFileSync(require.resolve("../app/static/mrz-robustness-report.css"), "utf8");
const source = fs.readFileSync(require.resolve("../app/static/mrz-robustness-report.js"), "utf8");
assert.match(html, /SAMPLE CONFIDENCE \/ SCOPE/);
assert.match(html, /POLICY ROBUSTNESS COMPARISON/);
assert.match(html, /INCREMENTAL COHORT ANALYSIS/);
assert.match(css, /body \{ overflow-x: hidden; \}/);
assert.match(css, /@media \(max-width: 700px\)/);
assert.match(css, /\.policy-detail-grid \{ grid-template-columns: 1fr; \}/);
assert.doesNotMatch(source, /recommended|optimal|best/i);
assert.doesNotMatch(source, /fetch\([^)]*observations/i);

console.log("MRZ robustness report presentation tests passed");
