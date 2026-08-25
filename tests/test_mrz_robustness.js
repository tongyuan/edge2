const assert = require("node:assert/strict");
const fs = require("node:fs");
const {
  durationText,
  directionText,
  migrationProvenanceMarkup,
  normalizedSpanText,
  percentageText,
  reportMarkup,
  robustnessCardMarkup,
} = require("../app/static/mrz-robustness.js");

assert.equal(durationText("219600"), "2d 13h");
assert.equal(durationText("5400"), "1h 30m");
assert.equal(percentageText("77.777"), "77.8%");
assert.equal(percentageText(null), "—");
assert.equal(directionText("UP", "Upward"), "↑ Upward");
assert.equal(directionText("DOWN", "Downward"), "↓ Downward");
assert.equal(directionText("NEUTRAL", "Neutral"), "Neutral");
assert.equal(normalizedSpanText("0.0012"), "0.1%");

const operationCardSource = fs.readFileSync(
  require.resolve("../app/static/mrz-robustness.js"),
  "utf8",
);
assert.doesNotMatch(operationCardSource, /bb_mrz_(?:discount|premium)/);
assert.doesNotMatch(operationCardSource, /trade recommendation/i);

const btcReport = {
  symbol: "BTCUSDT",
  route_owner: "STR",
  migration: { has_migrated: false },
  structural_authority: {
    status: "AUTHORITATIVE",
    label: "Authoritative",
    structural_location: "deep_premium_core_mrz",
    structural_location_label: "Deep Premium",
    structural_role: "RESISTIVE",
    structural_role_label: "Resistive",
  },
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
    post_activation_observation_count: 4,
    meaning: "What occurred after the active MRZ was formed.",
  },
  post_activation_robustness: {
    status: "UNDER_PRESSURE",
    label: "Under Pressure",
    reason: "Post-activation observations have moved outside the frozen migration envelope.",
    post_activation_observation_count: 4,
  },
  containment: {
    inside_observation_count: 1,
    total_observation_count: 4,
    percentage: "25",
  },
  boundary_pressure: {
    upper_boundary_test_count: 3,
    lower_boundary_test_count: 1,
    outside_envelope_observation_count: 3,
    above_upper_envelope_observation_count: 3,
    below_lower_envelope_observation_count: 0,
    definition: "Deterministic boundary definition.",
  },
  distance_from_mrz_midpoint: {
    median_distance_percentage_of_activation_ipda: "0.18",
    normalization: "Normalized by full IPDA 20W width stored at activation.",
  },
  route_integrity: {
    label: "Premium structure maintained",
    route_aligned_observation_count: 4,
    structurally_aligned_observation_count: 4,
    total_observation_count: 4,
  },
  migration_pressure: {
    status: "UNDER_PRESSURE",
    label: "Under Pressure",
    reason: "Three post-activation observations are above the upper migration envelope.",
    direction: "UP",
    direction_label: "Upward",
    relevant_boundary_label: "Upper migration boundary",
    relevant_boundary: "77692.35",
    observations_beyond_envelope: 3,
    above_upper_envelope_observation_count: 3,
    below_lower_envelope_observation_count: 0,
    current_mrz_remains_authoritative: true,
  },
  successor_watch: {
    status: "NO_SUCCESSOR_CANDIDATE",
    label: "No successor candidate",
    direction: null,
    direction_label: null,
    symbol: null,
    route: null,
    candidate_lower: null,
    candidate_upper: null,
    evidence_observation_count: 0,
    required_observation_count: 4,
    normalized_span: null,
    production_evaluation_result: "INSUFFICIENT_OBSERVATIONS",
  },
  mrz_age: {
    active_duration_seconds: "219600",
  },
  structural_summary: {
    current_authority: "STR · Deep Premium",
    robustness_status: "UNDER_PRESSURE",
    robustness_label: "Under Pressure",
    pressure_direction: "UP",
    pressure_direction_label: "Upward",
    structural_role: "RESISTIVE",
    structural_role_label: "Resistive",
    successor_status: "NOT_CONFIRMED",
    successor_label: "Not confirmed",
    authority_statement: "The current MRZ remains authoritative.",
    detail_statement: "Observed post-activation evidence is exerting upward pressure.",
  },
};

const btcMarkup = robustnessCardMarkup(
  btcReport,
  () => "23 Aug 2026 · 22:21 UTC−4",
);
const orderedSections = [
  "1 · STRUCTURAL AUTHORITY",
  "2 · POST-ACTIVATION ROBUSTNESS",
  "3 · EVIDENCE",
  "4 · MIGRATION PRESSURE",
  "5 · SUCCESSOR WATCH",
  "6 · STRUCTURAL SUMMARY",
];
let previousIndex = -1;
for (const section of orderedSections) {
  const currentIndex = btcMarkup.indexOf(section);
  assert.ok(currentIndex > previousIndex, `${section} is rendered in sequence`);
  previousIndex = currentIndex;
}
assert.match(btcMarkup, /BTCUSDT · STR/);
assert.match(btcMarkup, /Deep Premium/);
assert.match(btcMarkup, /Authoritative/);
assert.match(btcMarkup, /Resistive/);
assert.match(btcMarkup, /77,309\.19 – 77,436\.91/);
assert.match(btcMarkup, /23 Aug 2026 · 22:21 UTC−4/);
assert.match(btcMarkup, /Under Pressure/);
assert.match(btcMarkup, /↑ Upward/);
assert.match(btcMarkup, /Upper migration boundary/);
assert.match(btcMarkup, /Still authoritative/);
assert.match(btcMarkup, /Distance From MRZ Midpoint/);
assert.match(btcMarkup, /Normalized by full IPDA 20W width stored at activation/);
assert.match(btcMarkup, /No successor candidate/);
assert.match(btcMarkup, /0 \/ 4/);
assert.match(btcMarkup, /Insufficient observations/);
assert.match(btcMarkup, /2d 13h/);
assert.doesNotMatch(btcMarkup, /Midpoint Stability/);
assert.doesNotMatch(btcMarkup, /bb_mrz/);
assert.doesNotMatch(btcMarkup, /\b(?:buy|sell|long|short)\b/i);
assert.doesNotMatch(btcMarkup, /Healthy|Weak|Good|Bad/);
assert.doesNotMatch(btcMarkup, /MIGRATED UPWARD|MIGRATED DOWNWARD/);

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
assert.match(
  migrationProvenanceMarkup({ ...wldMigration, direction: "DOWN" }, () => "timestamp"),
  /↓ MIGRATED DOWNWARD/,
);

const wldReport = {
  ...btcReport,
  symbol: "WLDUSDT",
  route_owner: "BTD",
  migration: wldMigration,
  structural_authority: {
    ...btcReport.structural_authority,
    structural_location: "shallow_discount_core_mrz",
    structural_location_label: "Shallow Discount",
    structural_role: "SUPPORTIVE",
    structural_role_label: "Supportive",
  },
  active_mrz: {
    ...btcReport.active_mrz,
    lower: "0.4034",
    upper: "0.4083",
    midpoint: "0.40585",
  },
  robustness_evidence: {
    ...btcReport.robustness_evidence,
    post_activation_observation_count: 1,
  },
  post_activation_robustness: {
    status: "STABLE",
    label: "Stable",
    reason: "The observed post-activation sample remains within the frozen migration envelope.",
    post_activation_observation_count: 1,
  },
  containment: {
    inside_observation_count: 1,
    total_observation_count: 1,
    percentage: "100",
  },
  boundary_pressure: {
    ...btcReport.boundary_pressure,
    upper_boundary_test_count: 0,
    lower_boundary_test_count: 0,
    outside_envelope_observation_count: 0,
    above_upper_envelope_observation_count: 0,
  },
  route_integrity: {
    ...btcReport.route_integrity,
    label: "Discount structure maintained",
    route_aligned_observation_count: 1,
    structurally_aligned_observation_count: 1,
    total_observation_count: 1,
  },
  migration_pressure: {
    ...btcReport.migration_pressure,
    status: "STABLE",
    label: "Stable",
    reason: "No post-activation observation is outside the frozen migration envelope.",
    direction: "NEUTRAL",
    direction_label: "Neutral",
    relevant_boundary_label: null,
    relevant_boundary: null,
    observations_beyond_envelope: 0,
    above_upper_envelope_observation_count: 0,
  },
  structural_summary: {
    ...btcReport.structural_summary,
    current_authority: "BTD · Shallow Discount",
    robustness_status: "STABLE",
    robustness_label: "Stable",
    pressure_direction: "NEUTRAL",
    pressure_direction_label: "Neutral",
    structural_role: "SUPPORTIVE",
    structural_role_label: "Supportive",
    detail_statement: "No post-activation observation is outside the frozen migration envelope.",
  },
};
const wldMarkup = robustnessCardMarkup(
  wldReport,
  () => "24 Aug 2026 · 12:00 UTC−4",
);
assert.match(wldMarkup, /WLDUSDT · BTD/);
assert.match(wldMarkup, /Shallow Discount/);
assert.match(wldMarkup, /Supportive/);
assert.match(wldMarkup, /↑ MIGRATED UPWARD/);
assert.match(wldMarkup, /Stable/);
assert.match(wldMarkup, /Neutral/);
assert.match(wldMarkup, /No successor candidate/);

const zeroEvidenceReport = {
  ...wldReport,
  migration: { has_migrated: false },
  robustness_evidence: {
    ...wldReport.robustness_evidence,
    post_activation_observation_count: 0,
  },
  post_activation_robustness: {
    status: "NOT_YET_ASSESSABLE",
    label: "Not yet assessable",
    reason: "No post-activation observations are available.",
    post_activation_observation_count: 0,
  },
  containment: {
    inside_observation_count: 0,
    total_observation_count: 0,
    percentage: null,
  },
  boundary_pressure: {
    ...wldReport.boundary_pressure,
    upper_boundary_test_count: 0,
    lower_boundary_test_count: 0,
    outside_envelope_observation_count: 0,
    above_upper_envelope_observation_count: 0,
    below_lower_envelope_observation_count: 0,
  },
  distance_from_mrz_midpoint: {
    ...wldReport.distance_from_mrz_midpoint,
    median_distance_percentage_of_activation_ipda: null,
  },
  route_integrity: {
    ...wldReport.route_integrity,
    label: "No post-activation evidence",
    route_aligned_observation_count: 0,
    structurally_aligned_observation_count: 0,
    total_observation_count: 0,
  },
  migration_pressure: {
    ...wldReport.migration_pressure,
    status: "NO_EVIDENCE",
    label: "No evidence",
    reason: "No post-activation observations are available for directional pressure.",
  },
  structural_summary: {
    ...wldReport.structural_summary,
    robustness_status: "NOT_YET_ASSESSABLE",
    robustness_label: "Not yet assessable",
    detail_statement: "No post-activation evidence is available yet.",
  },
};
const zeroMarkup = robustnessCardMarkup(zeroEvidenceReport);
assert.match(zeroMarkup, /Not yet assessable/);
assert.match(zeroMarkup, /0 post-activation observations/);
assert.match(zeroMarkup, /No evidence/);
assert.match(zeroMarkup, /Neutral/);

const successorReport = {
  ...btcReport,
  successor_watch: {
    ...btcReport.successor_watch,
    status: "CANDIDATE_FORMING",
    label: "Candidate forming",
    direction: "UP",
    direction_label: "Higher MRZ",
    symbol: "BTCUSDT",
    route: "STR",
    candidate_lower: "78100",
    candidate_upper: "78250",
    evidence_observation_count: 2,
    normalized_span: "0.0012",
    production_evaluation_result: "TOO_DISPERSED",
  },
};
const successorMarkup = robustnessCardMarkup(successorReport);
assert.match(successorMarkup, /↑ Higher MRZ/);
assert.match(successorMarkup, /78,100 – 78,250/);
assert.match(successorMarkup, /2 \/ 4/);
assert.match(successorMarkup, /0\.1%/);
assert.match(successorMarkup, /Too dispersed/);
assert.match(successorMarkup, /production evaluator and MRZ engine/);

const empty = reportMarkup([]);
assert.match(empty, /No active MRZ is available for an operation card/);

console.log("MRZ operation card presentation tests passed");
