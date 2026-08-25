const assert = require("node:assert/strict");
const {
  durationText,
  migrationProvenanceMarkup,
  percentageText,
  reportMarkup,
  robustnessCardMarkup,
} = require("../app/static/mrz-robustness.js");

assert.equal(durationText("219600"), "2d 13h");
assert.equal(durationText("5400"), "1h 30m");
assert.equal(percentageText("77.777"), "77.8%");
assert.equal(percentageText(null), "—");

const activeReport = {
  symbol: "BTCUSDT",
  route_owner: "STR",
  migration: { has_migrated: false },
  active_mrz: {
    lower: "77309.19",
    upper: "77436.91",
    midpoint: "77373.05",
    activated_at: "2026-08-24T02:21:00Z",
  },
  formation_evidence: {
    confirming_observation_count: 4,
    meaning: "Why the active MRZ was formed.",
  },
  robustness_evidence: {
    post_activation_observation_count: 18,
    meaning: "What occurred after the active MRZ was formed.",
  },
  containment: {
    inside_observation_count: 14,
    total_observation_count: 18,
    percentage: "77.777777",
  },
  boundary_pressure: {
    upper_boundary_test_count: 3,
    lower_boundary_test_count: 1,
    outside_envelope_observation_count: 3,
    definition: "Deterministic boundary definition.",
  },
  midpoint_stability: {
    median_distance_percentage_of_activation_ipda: "0.18",
    normalization: "Full IPDA 20W width stored at activation.",
  },
  route_integrity: {
    label: "Premium structure maintained",
    route_aligned_observation_count: 18,
    structurally_aligned_observation_count: 18,
    total_observation_count: 18,
  },
  migration_pressure: {
    status: "UNDER_PRESSURE",
    label: "Under Pressure",
    reason: "External observations were detected outside the active MRZ envelope.",
  },
  successor_watch: {
    status: "AWAITING_CONFIRMATION",
    label: "Awaiting confirmation",
    symbol: "BTCUSDT",
    route: "STR",
    candidate_lower: "78100",
    candidate_upper: "78250",
    evidence_observation_count: 3,
    required_observation_count: 4,
    production_evaluation_result: "INSUFFICIENT_OBSERVATIONS",
  },
  mrz_age: {
    active_duration_seconds: "219600",
  },
  robustness_classification: {
    status: "UNDER_PRESSURE",
    label: "Under Pressure",
    reasons: [
      "A majority of post-activation observations remain inside the frozen MRZ.",
      "Premium structure maintained.",
      "No confirmed successor is detected.",
    ],
  },
};

const markup = robustnessCardMarkup(
  activeReport,
  () => "23 Aug 2026 · 22:21 UTC−4",
);
assert.match(markup, /BTCUSDT · STR/);
assert.match(markup, /77,309\.19 – 77,436\.91/);
assert.match(markup, /23 Aug 2026 · 22:21 UTC−4/);
assert.match(markup, /4 qualifying observations/);
assert.match(markup, /18 post-activation observations/);
assert.match(markup, /14 \/ 18/);
assert.match(markup, /77\.8%/);
assert.match(markup, /Upper boundary tests/);
assert.match(markup, />3</);
assert.match(markup, /Median distance/);
assert.match(markup, /0\.2%/);
assert.match(markup, /Premium structure maintained/);
assert.match(markup, /MIGRATION PRESSURE/);
assert.match(markup, /Under Pressure/);
assert.match(markup, /SUCCESSOR WATCH/);
assert.match(markup, /Awaiting confirmation/);
assert.match(markup, /78,100 – 78,250/);
assert.match(markup, /3 \/ 4 observations/);
assert.match(markup, /Current MRZ remains authoritative/);
assert.match(markup, /Diagnostic only\. Migration remains controlled by the MRZ engine/);
assert.match(markup, /2d 13h/);
assert.doesNotMatch(markup, /Healthy|Weak|Good|Bad/);
assert.doesNotMatch(markup, /MIGRATED UPWARD|MIGRATED DOWNWARD/);

const wldMigration = {
  has_migrated: true,
  direction: "UP",
  migrated_at: "2026-08-24T16:00:00Z",
  previous_lower: 0.3936,
  previous_upper: 0.3966,
  current_lower: 0.4034,
  current_upper: 0.4083,
};
const migrationMarkup = migrationProvenanceMarkup(
  wldMigration,
  () => "24 Aug 2026 · 12:00 UTC−4",
);
assert.match(migrationMarkup, /↑ MIGRATED UPWARD/);
assert.match(migrationMarkup, /24 Aug 2026 · 12:00 UTC−4/);
assert.match(migrationMarkup, /0\.3936 – 0\.3966/);
assert.match(migrationMarkup, /0\.4034 – 0\.4083/);

const migratedStableReport = {
  ...activeReport,
  symbol: "WLDUSDT",
  route_owner: "BTD",
  migration: wldMigration,
  active_mrz: {
    ...activeReport.active_mrz,
    lower: "0.4034",
    upper: "0.4083",
    midpoint: "0.40585",
  },
  migration_pressure: {
    status: "STABLE",
    label: "Stable",
    reason: "No post-activation observation has moved outside the active MRZ envelope.",
  },
  successor_watch: {
    ...activeReport.successor_watch,
    status: "NO_SUCCESSOR_CANDIDATE",
    label: "No successor candidate",
    symbol: null,
    route: null,
    candidate_lower: null,
    candidate_upper: null,
    evidence_observation_count: 0,
  },
  robustness_classification: {
    status: "STABLE",
    label: "Stable",
    reasons: ["No confirmed successor is detected."],
  },
};
const migratedStableMarkup = robustnessCardMarkup(
  migratedStableReport,
  () => "24 Aug 2026 · 12:00 UTC−4",
);
assert.match(migratedStableMarkup, /↑ MIGRATED UPWARD/);
assert.match(migratedStableMarkup, /Stable/);
assert.match(migratedStableMarkup, /No successor candidate/);

assert.match(
  migrationProvenanceMarkup({ ...wldMigration, direction: "DOWN" }, () => "timestamp"),
  /↓ MIGRATED DOWNWARD/,
);

const empty = reportMarkup([]);
assert.match(empty, /No active MRZ is available/);

console.log("MRZ robustness presentation tests passed");
