const assert = require("node:assert/strict");
const {
  auditTableMarkup,
  candidatePolicyMarkup,
  comparisonTableMarkup,
  diagnosisMarkup,
  filterAuditRows,
  frequencyText,
  matrixMarkup,
  percentageText,
  productionMarkup,
  summaryTableMarkup,
} = require("../app/static/activation-feasibility.js");

const scenarios = [2, 3, 4].flatMap((minimum) => [1, 2, 3, 4, 5].map((allowance) => ({
  algorithm: "A",
  minimum_observations: minimum,
  allowance_percent: allowance,
  eligible_symbol_route_sequences: 8,
  hypothetical_activations: 3,
  activation_frequency: { numerator: 3, denominator: 8, percentage: "37.5" },
  near_miss_sequences: 2,
  dispersed_sequences: 3,
  median_ordinal_observation_at_qualification: "4",
  median_formation_duration_seconds: "3600",
  median_normalized_span_at_qualification: "0.008",
  median_minimum_required_allowance_pct_at_qualification: "0.812345",
  small_sample: true,
  is_current_production_rule: minimum === 4 && allowance === 1,
})));

assert.equal(frequencyText({ numerator: 3, denominator: 8, percentage: "37.5" }), "3 of 8 · 37.5%");
assert.equal(frequencyText({ numerator: 0, denominator: 0, percentage: null }), "0 of 0 · —");
assert.equal(percentageText("1.126789"), "1.13%");

const summary = summaryTableMarkup(scenarios);
assert.match(summary, /Formation frequency/);
assert.match(summary, /MRZ formations/);
assert.match(summary, /Near misses/);
assert.match(summary, /Median duration/);
assert.match(summary, /Median minimum allowance required/);
assert.match(summary, /0\.81%/);
assert.match(summary, /production-row/);
assert.match(summary, /LOW SAMPLE/);

const matrix = matrixMarkup(scenarios);
assert.match(matrix, /Minimum \/ Allowance/);
assert.equal((matrix.match(/3 of 8 · 37\.5%/g) || []).length, 15);

const comparison = comparisonTableMarkup([{
  minimum_observations: 4,
  allowance_percent: 1,
  small_sample: true,
  algorithm_a_frequency: { numerator: 3, denominator: 8, percentage: "37.5" },
  algorithm_b_frequency: { numerator: 2, denominator: 8, percentage: "25.0" },
  activation_frequency_difference_percentage_points_b_minus_a: "-12.5",
  both_activated: 2,
  algorithm_a_only: 1,
  algorithm_b_only: 0,
  neither_activated: 5,
  median_activation_timestamp_difference_seconds_b_minus_a: "60",
  median_ordinal_observation_difference_b_minus_a: "1",
  median_proposed_span_difference_b_minus_a: "0.2",
  median_algorithm_a_qualification_ratio: "0.8",
  median_algorithm_b_qualification_ratio: "0.9",
  median_algorithm_a_minimum_required_allowance_pct: "0.8",
  median_algorithm_b_minimum_required_allowance_pct: "0.9",
}]);
assert.match(comparison, /B − A/);
assert.match(comparison, /A only/);
assert.match(comparison, /Neither/);
assert.match(comparison, /Median A required/);
assert.match(comparison, /0\.80%/);

const production = productionMarkup({
  algorithm: "A",
  minimum_observations: 4,
  allowance_percent: 1,
  result: {
    activation_frequency: { numerator: 1, denominator: 5, percentage: "20.0" },
  },
  activations: [{
    symbol: "BTCUSDT",
    route: "STR",
    core_mrz_lower: "77309.19",
    core_mrz_upper: "77436.91",
    activated_at: "2026-08-24T02:21:00Z",
    minimum_observations: 4,
    allowance_percent: 1,
  }],
}, () => "23 Aug 2026 · 22:21 UTC−4");
assert.match(production, /Algorithm A · 4 observations · 1\.00%/);
assert.match(production, /1 of 5 eligible symbol-route histories formed an MRZ/);
assert.match(production, />20\.0%</);
assert.match(production, /BTCUSDT · STR/);
assert.match(production, /77,309\.19–77,436\.91/);
assert.match(production, /23 Aug 2026 · 22:21 UTC−4/);
assert.match(production, /4 observations · 1\.00% allowance/);

const zeroProduction = productionMarkup({
  algorithm: "A",
  minimum_observations: 4,
  allowance_percent: 1,
  result: {
    activation_frequency: { numerator: 0, denominator: 5, percentage: "0.0" },
  },
  activations: [],
});
assert.match(zeroProduction, /No MRZ formed under the current production rule in this sample\./);

const details = [
  {
    symbol: "ETHUSDT", route: "STR", algorithm: "A", minimum_observations: 4,
    allowance_percent: 1, classification: "NEAR_MISS", activated: false, eligible: true,
    total_stored_route_observations: 5, first_qualifying_timestamp: null,
    ordinal_route_observation_number: null, formation_duration_seconds: null,
    proposed_lower_boundary: null, proposed_upper_boundary: null, normalized_span: null,
    minimum_required_allowance_pct: null, closest_minimum_required_allowance_pct: "1.5",
    closest_qualification_ratio: "1.5", structural_location: "deep_premium",
  },
  {
    symbol: "BTCUSDT", route: "BTD", algorithm: "B", minimum_observations: 2,
    allowance_percent: 3, classification: "QUALIFIED", activated: true, eligible: true,
    total_stored_route_observations: 4, first_qualifying_timestamp: "2026-08-21T01:30:00Z",
    ordinal_route_observation_number: 2, formation_duration_seconds: "60",
    proposed_lower_boundary: "110", proposed_upper_boundary: "110.2", normalized_span: "0.002",
    minimum_required_allowance_pct: "0.2", closest_minimum_required_allowance_pct: "0.2",
    closest_qualification_ratio: "0.1", structural_location: "deep_discount",
  },
];
assert.deepEqual(filterAuditRows(details, {
  symbol: "ETHUSDT", route: "STR", algorithm: "A", minimum: "4", allowance: "1", classification: "NEAR_MISS",
}), [details[0]]);
const audit = auditTableMarkup(details, () => "20 Aug 2026 · 21:30 UTC−4");
assert.match(audit, /First activated/);
assert.match(audit, /Never qualified/);
assert.match(audit, /20 Aug 2026 · 21:30 UTC−4/);
assert.match(audit, /Closest ratio/);
assert.match(audit, /Minimum allowance required/);
assert.match(audit, /Closest · 1\.50%/);
assert.match(audit, /First · 0\.20%/);

const suppliedDiagnosis = {
  sample_assessment: { heading: "Sample confidence · Preliminary", text: "Backend sample text 7." },
  production_feasibility: { heading: "Production feasibility · No MRZ formed", text: "Backend production text 11." },
  count_sensitivity: { heading: "Count sensitivity", text: "Backend count text." },
  allowance_sensitivity: { heading: "Allowance sensitivity", text: "Backend allowance text." },
  algorithm_comparison: { heading: "Algorithm comparison", text: "Backend comparison text." },
  candidate_policy_evaluation: {
    heading: "Candidate Policy Evaluation",
    small_sample: true,
    current: {
      algorithm: "A",
      minimum_observations: 4,
      allowance_percent: 1,
      activation_frequency: { numerator: 1, denominator: 5, percentage: "20.0" },
    },
    candidate: {
      algorithm: "A",
      minimum_observations: 4,
      allowance_percent: 2,
      activation_frequency: { numerator: 4, denominator: 5, percentage: "80.0" },
    },
    selection_basis: [
      "Maintains the current 4-observation evidence requirement.",
      "First tested allowance increase with a material improvement in MRZ formation coverage.",
      "Wider tested allowances from 3.00%–5.00% produced no additional MRZ formations in the current sample.",
      "Sample remains preliminary.",
    ],
  },
  current_production_near_misses: [{
    heading: "WLDUSDT · BTD",
    text: "Current minimum allowance required · 1.59%. Current allowance · 1.00%. Shortfall · 0.59 percentage points.",
    candidate_lower_boundary: "2.7",
    candidate_upper_boundary: "2.8",
    candidate_observation_count: 4,
    total_stored_route_observations: 5,
    candidate_timestamp: "2026-08-22T00:30:00Z",
  }],
  closest_production_near_misses: [{
    heading: "WLDUSDT · BTD",
    text: "Closest historical minimum allowance required · 1.59%. Current allowance · 1.00%. Shortfall · 0.59 percentage points.",
    candidate_lower_boundary: "2.7",
    candidate_upper_boundary: "2.8",
    candidate_observation_count: 4,
    total_stored_route_observations: 5,
    candidate_timestamp: "2026-08-22T00:30:00Z",
    matches_current_candidate: true,
  }],
  evidence_interpretation: { heading: "Evidence interpretation", text: "Backend interpretation only." },
};
const diagnosis = diagnosisMarkup(suppliedDiagnosis, () => "20 Aug 2026 · 21:30 UTC−4");
assert.match(diagnosis, /Backend sample text 7\./);
assert.match(diagnosis, /Backend interpretation only\./);
assert.match(diagnosis, /Candidate Policy Evaluation/);
assert.match(diagnosis, /Algorithm A/);
assert.match(diagnosis, /Minimum observations/);
assert.match(diagnosis, /4 observations · 1\.00%/);
assert.match(diagnosis, /4 observations · 2\.00%/);
assert.match(diagnosis, /1 of 5 histories formed an MRZ/);
assert.match(diagnosis, /4 of 5 histories formed an MRZ/);
assert.match(diagnosis, /SELECTION BASIS/);
assert.match(diagnosis, /WLDUSDT · BTD/);
assert.match(diagnosis, /20 Aug 2026 · 21:30 UTC−4/);
assert.match(diagnosis, /Current production near misses/);
assert.match(diagnosis, /Closest historical production near misses/);
assert.match(diagnosis, /Current minimum allowance required · 1\.59%/);
assert.match(diagnosis, /Current candidate is also the closest historical near miss\./);
assert.equal((diagnosis.match(/2\.7–2\.8/g) || []).length, 1);
assert.doesNotMatch(diagnosis, />Activated</);
assert.doesNotMatch(diagnosis, /7 of 11/);
assert.doesNotMatch(diagnosis, /recommended/i);
assert.ok(
  diagnosis.indexOf("Algorithm comparison") < diagnosis.indexOf("Candidate Policy Evaluation"),
  "candidate policy follows algorithm comparison",
);
assert.ok(
  diagnosis.indexOf("Candidate Policy Evaluation") < diagnosis.indexOf("Current production near misses"),
  "candidate policy precedes current production near misses",
);

const standaloneCandidate = candidatePolicyMarkup(suppliedDiagnosis.candidate_policy_evaluation);
assert.match(standaloneCandidate, /CURRENT/);
assert.match(standaloneCandidate, /CANDIDATE/);
assert.match(standaloneCandidate, /PRELIMINARY/);

const operatorFacingMarkup = [summary, matrix, comparison, audit, production, zeroProduction, diagnosis].join("\n");
assert.doesNotMatch(operatorFacingMarkup, /\bsequences?\b/i);

console.log("activation feasibility presentation tests passed");
