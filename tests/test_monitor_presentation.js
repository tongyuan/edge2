const assert = require("node:assert/strict");
const {
  formatFormationDuration,
  buildConcentrationCheck,
  buildActivationSourcePresentation,
  buildEvidencePresentation,
  buildMigrationPresentation,
  buildProductionConfirmationPresentation,
  formatActivatedAt,
  formatLatestObservationContext,
  operatorCardHref,
  percentageText,
} = require("../app/static/monitor-presentation.js");
const {
  formatOperatorTimestampUtcMinus4,
} = require("../app/static/operator-time.js");

const formatPrice = (value) => value == null ? "—" : new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 12,
}).format(value);
const formatLocation = (value) => ({
  deep_discount: "Deep Discount",
  shallow_discount: "Shallow Discount",
  shallow_premium: "Shallow Premium",
  deep_premium: "Deep Premium",
}[value] || "—");

assert.equal(formatFormationDuration(1080), "18m");
assert.equal(formatFormationDuration(19440), "5h 24m");
assert.equal(formatFormationDuration(280800), "3d 6h");
assert.equal(formatFormationDuration(30), "<1m");
assert.equal(formatFormationDuration(0), "0m");
assert.equal(formatFormationDuration(null), null);
assert.equal(percentageText("1.126789"), "1.13");
assert.equal(
  operatorCardHref({ mrz_status: "active", symbol: "BTCUSDT" }),
  "/diagnostics/mrz-robustness?symbol=BTCUSDT",
);
assert.equal(
  operatorCardHref({ mrz_status: "active", symbol: "NASDAQ:NDX" }),
  "/diagnostics/mrz-robustness?symbol=NASDAQ%3ANDX",
);
assert.equal(operatorCardHref({ mrz_status: "unestablished", symbol: "BTCUSDT" }), null);
assert.equal(operatorCardHref({ mrz_status: "active", symbol: "" }), null);
assert.deepEqual(
  buildActivationSourcePresentation({
    mrz_status: "active",
    activation_source: "OPERATOR_PROMOTED",
    operator_promotion: {
      minimum_required_allowance_pct: "1.02",
      production_threshold_pct: "1",
    },
  }),
  {
    primary: "OPERATOR PROMOTED",
    secondary: ["1.02% required / 1.00% threshold"],
  },
);
assert.deepEqual(
  buildActivationSourcePresentation({
    mrz_status: "active",
    activation_source: "PRODUCTION_QUALIFIED",
  }),
  { primary: "PRODUCTION QUALIFIED", secondary: [] },
);
assert.equal(buildActivationSourcePresentation({ mrz_status: "unestablished" }), null);
assert.deepEqual(
  buildProductionConfirmationPresentation({
    production_confirmation: {
      qualified_lower: "943.1",
      qualified_upper: "948.7",
      qualified_midpoint: "945.9",
      qualified_at: "2026-09-04T05:00:00Z",
      minimum_required_allowance_pct: "0.97",
      supporting_observation_count: 4,
    },
  }, () => "4 Sep 2026 · 01:00 UTC−4", formatPrice),
  {
    primary: "943.1–948.7",
    secondary: [
      "Midpoint · 945.9",
      "Qualified · 4 Sep 2026 · 01:00 UTC−4",
      "0.97% · 4 observations",
    ],
  },
);
assert.equal(buildProductionConfirmationPresentation({}), null);
assert.equal(
  buildMigrationPresentation(
    { mrz_status: "active", migration: { has_migrated: false } },
    formatOperatorTimestampUtcMinus4,
    formatPrice,
  ),
  null,
);
assert.deepEqual(
  buildMigrationPresentation({
    mrz_status: "active",
    migration: {
      has_migrated: true,
      direction: "UP",
      migrated_at: "2026-08-24T16:00:00Z",
      previous_lower: 0.3936,
      previous_upper: 0.3966,
      current_lower: 0.4034,
      current_upper: 0.4083,
    },
  }, formatOperatorTimestampUtcMinus4, formatPrice),
  {
    title: "↑ MIGRATED",
    timestamp: "24 Aug 2026 · 12:00 UTC−4",
    previousRange: "0.3936–0.3966",
    currentRange: "0.4034–0.4083",
  },
);
assert.equal(
  buildMigrationPresentation({
    mrz_status: "active",
    migration: {
      has_migrated: true,
      direction: "DOWN",
      previous_lower: 180,
      previous_upper: 180.6,
      current_lower: 170,
      current_upper: 170.6,
    },
  }, () => "24 Aug 2026 · 13:00 UTC−4", formatPrice).title,
  "↓ MIGRATED",
);
assert.equal(
  formatActivatedAt(
    { mrz_status: "active", activated_at: "2026-08-24T02:21:00Z" },
    formatOperatorTimestampUtcMinus4,
  ),
  "23 Aug 2026 · 22:21 UTC−4",
);
assert.equal(
  formatActivatedAt(
    { mrz_status: "unestablished", activated_at: "2026-08-24T02:21:00Z" },
    formatOperatorTimestampUtcMinus4,
  ),
  null,
);
assert.equal(
  formatActivatedAt(
    { mrz_status: "active", activated_at: null },
    formatOperatorTimestampUtcMinus4,
  ),
  null,
);

assert.deepEqual(
  buildEvidencePresentation({
    mrz_status: "unestablished",
    btd_window_observation_count: 3,
    btd_window_started_at: "2026-08-20T18:05:00Z",
    str_window_observation_count: 6,
    str_window_started_at: "2026-08-20T20:42:00Z",
  }, formatOperatorTimestampUtcMinus4),
  {
    primary: "No qualifying concentration",
    secondary: [
      "BTD · 3 reclaim observations",
      "BTD window since · 20 Aug 2026 · 14:05 UTC−4",
      "STR · 6 rejection observations",
      "STR window since · 20 Aug 2026 · 16:42 UTC−4",
    ],
    checks: [],
  },
);

assert.deepEqual(
  buildEvidencePresentation({
    mrz_status: "unestablished",
    btd_window_observation_count: 0,
    btd_window_started_at: null,
    str_window_observation_count: 1,
    str_window_started_at: "2026-08-20T20:42:00Z",
  }, formatOperatorTimestampUtcMinus4),
  {
    primary: "No qualifying concentration",
    secondary: [
      "BTD · 0 reclaim observations",
      "STR · 1 rejection observation",
      "STR window since · 20 Aug 2026 · 16:42 UTC−4",
    ],
    checks: [],
  },
);

assert.deepEqual(
  buildEvidencePresentation({
    mrz_status: "unestablished",
    btd_window_observation_count: 0,
    btd_window_started_at: "2026-08-20T18:05:00Z",
    str_window_observation_count: 0,
    str_window_started_at: "2026-08-20T20:42:00Z",
  }, formatOperatorTimestampUtcMinus4),
  { primary: "No qualifying concentration", secondary: [], checks: [] },
);

assert.deepEqual(
  buildEvidencePresentation({
    mrz_status: "active",
    route_owner: "BTD",
    supporting_observation_count: 4,
    formation_started_at: "2026-08-24T18:31:00Z",
    activated_at: "2026-08-28T19:31:00Z",
    formation_duration_seconds: 11700,
    btd_window_started_at: "2026-08-20T18:05:00Z",
  }, formatOperatorTimestampUtcMinus4),
  {
    primary: "4 qualifying reclaim observations",
    secondary: [
      "First reclaim · 24 Aug 2026 · 14:31 UTC−4",
      "Formation duration · 3h 15m",
    ],
    checks: [],
  },
);

assert.deepEqual(
  buildEvidencePresentation({
    mrz_status: "active",
    route_owner: "STR",
    supporting_observation_count: 6,
    formation_started_at: "2026-08-25T05:45:00Z",
    formation_duration_seconds: 280800,
  }, formatOperatorTimestampUtcMinus4),
  {
    primary: "6 qualifying rejection observations",
    secondary: [
      "First rejection · 25 Aug 2026 · 01:45 UTC−4",
      "Formation duration · 3d 6h",
    ],
    checks: [],
  },
);

assert.deepEqual(
  buildEvidencePresentation({
    mrz_status: "active",
    route_owner: "BTD",
    supporting_observation_count: 4,
    formation_duration_seconds: null,
  }),
  { primary: "4 qualifying reclaim observations", secondary: [], checks: [] },
);

const insufficientCheck = buildConcentrationCheck({
  route: "BTD",
  retained_observation_count: 3,
  minimum_required_count: 4,
  selected_observation_count: 0,
  result: "INSUFFICIENT_OBSERVATIONS",
}, formatPrice, formatLocation);
assert.deepEqual(insufficientCheck, {
  label: "CONCENTRATION CHECK · BTD",
  lines: [
    "Concentration check unavailable",
    "Minimum observations required · 4",
  ],
});
assert.equal(insufficientCheck.lines.some((line) => line.includes("Price range")), false);

assert.deepEqual(
  buildConcentrationCheck({
    route: "STR",
    retained_observation_count: 5,
    selected_observation_count: 4,
    selected_lower: "2326.95",
    selected_upper: "2444.13",
    observed_span: "117.18",
    ipda_width: "1042.73",
    allowance: "10.4273",
    minimum_required_allowance_pct: "11.237",
    configured_allowance_pct: "1",
    allowance_difference_pct_points: "10.237",
    allowance_comparison: "SHORTFALL",
    result: "TOO_DISPERSED",
  }, formatPrice, formatLocation),
  {
    label: "CONCENTRATION CHECK · STR",
    lines: [
      "Tightest eligible group · 4 of 5",
      "Price range · 2,326.95–2,444.13",
      "Minimum allowance required · 11.24%",
      "Current allowance · ≤1.00%",
      "Shortfall · 10.24 percentage points",
      "Price span · 117.18",
      "IPDA width · 1,042.73",
      "Result · Too dispersed",
    ],
  },
);

assert.deepEqual(
  buildConcentrationCheck({
    route: "STR",
    retained_observation_count: 4,
    selected_observation_count: 4,
    selected_lower: "120",
    selected_upper: "120.6",
    observed_span: "0.6",
    ipda_width: "100",
    allowance: "1",
    minimum_required_allowance_pct: "0.6",
    configured_allowance_pct: "1",
    allowance_difference_pct_points: "-0.4",
    allowance_comparison: "MARGIN",
    proposed_structural_location: "deep_discount",
    result: "STRUCTURALLY_INELIGIBLE",
  }, formatPrice, formatLocation),
  {
    label: "CONCENTRATION CHECK · STR",
    lines: [
      "Tightest eligible group · 4 of 4",
      "Price range · 120–120.6",
      "Minimum allowance required · 0.60%",
      "Current allowance · ≤1.00%",
      "Margin · 0.40 percentage points inside",
      "Price span · 0.6",
      "IPDA width · 100",
      "Proposed location · Deep Discount",
      "Result · Structurally ineligible",
    ],
  },
);

const atThreshold = buildConcentrationCheck({
  route: "BTD",
  retained_observation_count: 4,
  selected_observation_count: 4,
  selected_lower: "110",
  selected_upper: "111",
  observed_span: "1",
  ipda_width: "100",
  minimum_required_allowance_pct: "1.00",
  configured_allowance_pct: "1",
  allowance_difference_pct_points: "0.00",
  allowance_comparison: "AT_THRESHOLD",
  proposed_structural_location: "deep_premium",
  result: "STRUCTURALLY_INELIGIBLE",
}, formatPrice, formatLocation);
assert.match(atThreshold.lines.join("\n"), /Margin · At threshold/);
assert.doesNotMatch(atThreshold.lines.join("\n"), /Algorithm B/);

assert.deepEqual(
  buildConcentrationCheck({
    route: "STR",
    retained_observation_count: 5,
    selected_observation_count: 4,
    result: "QUALIFIES",
  }, formatPrice, formatLocation),
  {
    label: "CONCENTRATION CHECK · STR",
    lines: ["Concentration qualifies but no active MRZ is recorded"],
  },
);

const activeWithDiagnostic = buildEvidencePresentation({
  mrz_status: "active",
  route_owner: "STR",
  supporting_observation_count: 4,
  formation_duration_seconds: 60,
  concentration_checks: {
    STR: { route: "STR", retained_observation_count: 5, result: "TOO_DISPERSED" },
  },
}, formatOperatorTimestampUtcMinus4, formatPrice, formatLocation);
assert.deepEqual(activeWithDiagnostic.checks, []);

const unestablishedWithDiagnostic = buildEvidencePresentation({
  mrz_status: "unestablished",
  btd_window_observation_count: 3,
  btd_window_started_at: "2026-08-20T18:05:00Z",
  str_window_observation_count: 0,
  concentration_checks: {
    BTD: {
      route: "BTD",
      retained_observation_count: 3,
      minimum_required_count: 4,
      result: "INSUFFICIENT_OBSERVATIONS",
    },
    STR: {
      route: "STR",
      retained_observation_count: 0,
      minimum_required_count: 4,
      result: "INSUFFICIENT_OBSERVATIONS",
    },
  },
}, formatOperatorTimestampUtcMinus4, formatPrice, formatLocation);
assert.deepEqual(unestablishedWithDiagnostic.checks, [insufficientCheck]);

assert.equal(
  formatLatestObservationContext(
    {
      latest_observation_route: "BTD",
      latest_observation_type: "reclaim",
      latest_observed_at: "2026-08-21T01:30:00Z",
    },
    formatOperatorTimestampUtcMinus4,
  ),
  "BTD reclaim · 20 Aug 2026 · 21:30 UTC−4",
);

assert.equal(
  formatLatestObservationContext(
    {
      latest_observation_route: "STR",
      latest_observation_type: "rejection",
      latest_observed_at: "2026-08-21T01:30:00Z",
    },
    formatOperatorTimestampUtcMinus4,
  ),
  "STR rejection · 20 Aug 2026 · 21:30 UTC−4",
);

const stableActivatedAt = formatActivatedAt(
  { mrz_status: "active", activated_at: "2026-08-24T02:21:00Z", latest_observed_at: "2026-08-24T02:21:00Z" },
  formatOperatorTimestampUtcMinus4,
);
assert.equal(
  formatActivatedAt(
    { mrz_status: "active", activated_at: "2026-08-24T02:21:00Z", latest_observed_at: "2026-08-24T05:45:00Z" },
    formatOperatorTimestampUtcMinus4,
  ),
  stableActivatedAt,
);

console.log("monitor presentation tests passed");
