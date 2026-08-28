const assert = require("node:assert/strict");
const {
  comparisonTableMarkup,
  nearMissCardMarkup,
  renderFormationComparison,
} = require("../app/static/formation-comparison.js");

const summary = (cohort, label, overrides = {}) => ({
  cohort,
  label,
  candidates: 4,
  with_follow_through: 3,
  resolved: 2,
  pending: 1,
  unresolved: 2,
  supportive_first: { numerator: 1, denominator: 2, percentage: 50 },
  adverse_first: { numerator: 1, denominator: 2, percentage: 50 },
  median_supportive_lag_hours: 2,
  median_adverse_lag_hours: 1,
  supportive_first_windows: { numerator: 1, denominator: 2 },
  sample_state: "PRELIMINARY",
  ...overrides,
});

const summaries = [
  summary("PRODUCTION", "≤1.00% Production"),
  summary("TIGHT_NEAR_MISS", "1.00–1.50% Near Miss"),
  summary("WIDER_NEAR_MISS", "1.50–2.00% Near Miss"),
];

const detail = (candidateClass, minimum, outcome, overrides = {}) => ({
  symbol: "SOXS",
  route: "BTD",
  candidate_class: candidateClass,
  source: "HISTORICAL_CLOSEST",
  minimum_required_allowance_pct: minimum,
  production_allowance_pct: 1,
  candidate_lower: 46.03,
  candidate_upper: 48.69,
  anchor_at: "2026-08-27T16:06:00Z",
  post_anchor_observations: 3,
  first_supportive_observation: 1,
  first_supportive_hours: 2,
  first_adverse_observation: 3,
  first_adverse_hours: 6,
  outcome,
  outcome_label: outcome === "PENDING_FOLLOW_THROUGH"
    ? "Pending follow-through"
    : "Supportive behavior arrived first",
  ...overrides,
});

const table = comparisonTableMarkup(summaries);
assert.match(table, /≤1\.00% Production/);
assert.match(table, /1\.00–1\.50% Near Miss/);
assert.match(table, /1\.50–2\.00% Near Miss/);
assert.match(table, /Supportive first/);
assert.match(table, /1 of 2 · 50%/);
assert.match(table, /With follow-through/);
assert.match(table, /Pending/);

const formatter = () => "27 Aug 2026 · 12:06 UTC−4";
const card = nearMissCardMarkup(detail("Tight near miss", 1.29, "SUPPORTIVE_FIRST"), formatter);
assert.match(card, /SOXS · BTD/);
assert.match(card, /Tight near miss/);
assert.match(card, /Minimum allowance required/);
assert.match(card, /1\.29%/);
assert.match(card, /Production allowance/);
assert.match(card, /1%/);
assert.match(card, /46\.03–48\.69/);
assert.match(card, /Candidate observed/);
assert.match(card, /27 Aug 2026 · 12:06 UTC−4/);
assert.match(card, /\+1 · 2h/);
assert.doesNotMatch(card, /Activated/);

const comparison = {
  title: "Production vs Near-Miss Windows",
  research_question: "After the structural candidate appears, does supportive behavior tend to arrive before adverse behavior?",
  outcome_denominator: "Resolved cases only; pending remains visible.",
  summaries,
  by_route: { BTD: summaries, STR: summaries },
  near_miss_details: [
    detail("Tight near miss", 1.29, "SUPPORTIVE_FIRST"),
    detail("Wider near miss", 1.57, "SUPPORTIVE_FIRST", { symbol: "GOOG" }),
    detail("Tight near miss", 1.31, "PENDING_FOLLOW_THROUGH", {
      symbol: "PENDING",
      post_anchor_observations: 0,
      first_supportive_observation: null,
      first_supportive_hours: null,
      first_adverse_observation: null,
      first_adverse_hours: null,
    }),
  ],
  evidence_interpretation: {
    status: "Preliminary",
    text: "The current sample is insufficient to determine whether near-miss candidates provide comparable windows.",
  },
};
const report = renderFormationComparison(comparison, formatter);
assert.match(report, /Production vs Near-Miss Windows/);
assert.match(report, /What arrived first\?/);
assert.match(report, /Tight near miss/);
assert.match(report, /Wider near miss/);
assert.match(report, /Pending follow-through/);
assert.match(report, /Evidence|Preliminary/);
assert.match(report, /insufficient to determine/);
assert.match(report, /analytical counterfactuals/);
assert.doesNotMatch(report, /recommended allowance/i);
assert.doesNotMatch(report, /optimal threshold/i);

console.log("formation strictness comparison presentation tests passed");
