const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {
  currentNearMissMarkup,
  productionMarkup,
  productionSampleMarkup,
  qualificationMarkup,
} = require("../app/static/activation-feasibility.js");

const productionRule = {
  algorithm: "A",
  minimum_observations: 4,
  allowance_percent: 1,
  result: {
    activation_frequency: { numerator: 12, denominator: 66, percentage: "18.2" },
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
};

const nearMisses = [{
  symbol: "WLDUSDT",
  route: "BTD",
  minimum_required_allowance_pct: "1.5900",
  configured_allowance_pct: "1",
  shortfall_percentage_points: "0.5900",
  candidate_lower_boundary: "2.7",
  candidate_upper_boundary: "2.8",
  candidate_observation_count: 4,
  total_stored_route_observations: 5,
  candidate_timestamp: "2026-08-22T00:30:00Z",
}];

const production = productionMarkup(productionRule);
assert.match(production, /Algorithm A · 4 observations · 1\.00%/);
assert.match(production, /12 of 66 eligible symbol-route histories formed an MRZ/);
assert.match(production, />18\.2%</);

const nearMiss = currentNearMissMarkup(
  nearMisses,
  () => "21 Aug 2026 · 20:30 UTC−4",
);
assert.match(nearMiss, /WLDUSDT · BTD/);
assert.match(nearMiss, /Current minimum allowance required/);
assert.match(nearMiss, /1\.59%/);
assert.match(nearMiss, /Current production allowance/);
assert.match(nearMiss, /1\.00%/);
assert.match(nearMiss, /Shortfall/);
assert.match(nearMiss, /0\.59 percentage points/);
assert.match(nearMiss, /2\.7–2\.8/);
assert.match(nearMiss, /4 of 5/);
assert.match(nearMiss, /21 Aug 2026 · 20:30 UTC−4/);
assert.match(currentNearMissMarkup([]), /No current production near misses/);

const qualifications = qualificationMarkup(
  productionRule.activations,
  () => "23 Aug 2026 · 22:21 UTC−4",
);
assert.match(qualifications, /BTCUSDT · STR/);
assert.match(qualifications, /First qualifying MRZ/);
assert.match(qualifications, /77,309\.19–77,436\.91/);
assert.match(qualifications, /First qualified/);
assert.match(qualifications, /23 Aug 2026 · 22:21 UTC−4/);
assert.match(qualifications, /4 observations · 1\.00%/);
assert.doesNotMatch(qualifications, />Activated</);
assert.match(qualificationMarkup([]), /No symbol-route history formed an MRZ/);

const sample = productionSampleMarkup({
  current_production_rule: productionRule,
  diagnosis: { current_production_near_misses: nearMisses },
});
assert.match(sample, /Production rule/);
assert.match(sample, /Algorithm A · 4 observations · 1\.00%/);
assert.match(sample, /Eligible histories<\/dt><dd>66/);
assert.match(sample, /MRZ formations<\/dt><dd>12/);
assert.match(sample, /Observed formation frequency<\/dt><dd>18\.2%/);
assert.match(sample, /Current near misses<\/dt><dd>1/);
assert.match(sample, /formed an MRZ in 12 of 66 eligible symbol-route histories in the stored sample/);
assert.doesNotMatch(sample, /predictive probability|recommended/i);

const pageHtml = fs.readFileSync(
  path.join(__dirname, "../app/static/activation-feasibility.html"),
  "utf8",
);
assert.match(pageHtml, /<h1>MRZ Formation Diagnostics<\/h1>/);
assert.match(pageHtml, /Observed MRZ formation frequency is descriptive, not a predictive probability/);
for (const contextId of [
  "generatedAt",
  "observationRange",
  "totalObservations",
  "totalSymbols",
  "totalSequences",
]) {
  assert.match(pageHtml, new RegExp(`id="${contextId}"`));
}
assert.match(pageHtml, /SYMBOL-ROUTE HISTORIES/);
assert.match(pageHtml, /id="productionContent"/);
assert.match(pageHtml, /id="currentNearMissContent"/);
assert.match(pageHtml, /id="qualificationContent"/);
assert.match(pageHtml, /id="productionSampleContent"/);
assert.match(pageHtml, /Qualified under production rule/);
assert.match(pageHtml, /do not assert current active-MRZ authority/);

for (const removed of [
  "summaryA",
  "matrixA",
  "auditFilters",
  "auditTable",
  "Candidate Policy Evaluation",
  "Algorithm A scenario results",
  "Activation matrices",
  "15 SCENARIOS",
]) {
  assert.doesNotMatch(pageHtml, new RegExp(removed));
}

const presentationSource = fs.readFileSync(
  path.join(__dirname, "../app/static/activation-feasibility.js"),
  "utf8",
);
for (const retiredData of [
  "value.scenarios",
  "value.sequence_details",
  "closest_production_near_misses",
  "candidate_policy_evaluation",
]) {
  assert.doesNotMatch(presentationSource, new RegExp(retiredData.replace(".", "\\.")));
}

console.log("MRZ formation diagnostics presentation tests passed");
