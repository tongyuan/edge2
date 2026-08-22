const assert = require("node:assert/strict");
const {
  formatFormationDuration,
  buildConcentrationCheck,
  buildEvidencePresentation,
  formatLatestObservationContext,
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
    formation_duration_seconds: 11700,
    btd_window_started_at: "2026-08-20T18:05:00Z",
  }, formatOperatorTimestampUtcMinus4),
  {
    primary: "4 qualifying reclaim observations",
    secondary: ["Formation duration · 3h 15m"],
    checks: [],
  },
);

assert.deepEqual(
  buildEvidencePresentation({
    mrz_status: "active",
    route_owner: "STR",
    supporting_observation_count: 6,
    formation_duration_seconds: 280800,
  }),
  {
    primary: "6 qualifying rejection observations",
    secondary: ["Formation duration · 3d 6h"],
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
    result: "TOO_DISPERSED",
  }, formatPrice, formatLocation),
  {
    label: "CONCENTRATION CHECK · STR",
    lines: [
      "Tightest eligible group · 4 of 5",
      "Price range · 2,326.95–2,444.13",
      "Observed span · 117.18",
      "IPDA width · 1,042.73",
      "Allowance · ≤10.4273 (1% of IPDA width)",
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
    allowance: "1",
    proposed_structural_location: "deep_discount",
    result: "STRUCTURALLY_INELIGIBLE",
  }, formatPrice, formatLocation),
  {
    label: "CONCENTRATION CHECK · STR",
    lines: [
      "Tightest eligible group · 4 of 4",
      "Price range · 120–120.6",
      "Observed span · 0.6",
      "Allowance · ≤1 (1% of IPDA width)",
      "Proposed location · Deep Discount",
      "Result · Structurally ineligible",
    ],
  },
);

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

console.log("monitor presentation tests passed");
