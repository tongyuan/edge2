const assert = require("node:assert/strict");
const fs = require("node:fs");
const {
  displacementText,
  durationText,
  directionText,
  filterReports,
  focusOperatorCard,
  hasValidMigrationProvenance,
  midpointValue,
  migrationEqmValue,
  migrationProvenanceMarkup,
  normalizedSpanText,
  operatorCardSectionFromHash,
  operatorCardSymbolFromSearch,
  percentageText,
  reportMarkup,
  robustnessCardMarkup,
  successorDetailsMarkup,
} = require("../app/static/mrz-robustness.js");

assert.equal(durationText("219600"), "2d 13h");
assert.equal(durationText("5400"), "1h 30m");
assert.equal(percentageText("77.777"), "77.8%");
assert.equal(percentageText(null), "—");
assert.equal(displacementText("6.210106", "ABOVE"), "↑ +6.2%");
assert.equal(displacementText("-3.44", "BELOW"), "↓ -3.4%");
assert.equal(displacementText("0.04", "CENTERED"), "0.0%");
assert.equal(displacementText(null, null), "—");
assert.equal(directionText("UP", "Upward"), "↑ Upward");
assert.equal(directionText("DOWN", "Downward"), "↓ Downward");
assert.equal(directionText("NEUTRAL", "Neutral"), "Neutral");
assert.equal(normalizedSpanText("0.0012"), "0.1%");
assert.equal(midpointValue("0.3936", "0.3966"), 0.3951);
assert.equal(midpointValue(null, "0.3966"), null);
assert.equal(operatorCardSymbolFromSearch("?symbol=BTCUSDT"), "BTCUSDT");
assert.equal(operatorCardSymbolFromSearch("?symbol=NASDAQ%3ANDX"), "NASDAQ:NDX");
assert.equal(operatorCardSymbolFromSearch(""), null);
assert.equal(operatorCardSectionFromHash("#post-activation"), "post-activation");
assert.equal(operatorCardSectionFromHash("#active-mrz"), "active-mrz");
assert.equal(operatorCardSectionFromHash("#migration-history"), "migration-history");
assert.equal(operatorCardSectionFromHash("#other"), null);

function fakeSection(tagName) {
  return {
    tagName,
    open: false,
    scrollOptions: null,
    focusOptions: null,
    tabIndex: null,
    scrollIntoView(options) { this.scrollOptions = options; },
    focus(options) { this.focusOptions = options; },
  };
}

function fakeOperatorCard(symbol) {
  return {
    dataset: { symbol },
    scrollOptions: null,
    focusOptions: null,
    sections: {
      "active-mrz": fakeSection("HEADER"),
      "migration-history": fakeSection("DETAILS"),
      "post-activation": fakeSection("DETAILS"),
    },
    querySelector(selector) {
      const match = selector.match(/^\[data-section="([a-z-]+)"\]$/);
      return match ? this.sections[match[1]] || null : null;
    },
    scrollIntoView(options) { this.scrollOptions = options; },
    focus(options) { this.focusOptions = options; },
  };
}

const btcCard = fakeOperatorCard("BTCUSDT");
const btcDerivativeCard = fakeOperatorCard("BTCUSDT.P");
const ethCard = fakeOperatorCard("ETHUSDT");
const operatorCardContainer = {
  querySelectorAll(selector) {
    assert.equal(selector, ".mrz-report");
    return [btcDerivativeCard, ethCard, btcCard];
  },
};
assert.equal(focusOperatorCard(operatorCardContainer, "BTCUSDT"), true);
assert.deepEqual(btcCard.scrollOptions, { block: "start" });
assert.deepEqual(btcCard.focusOptions, { preventScroll: true });
assert.equal(btcDerivativeCard.scrollOptions, null, "similar symbols must not match");
assert.equal(ethCard.scrollOptions, null);

assert.equal(focusOperatorCard(operatorCardContainer, "ETHUSDT"), true);
assert.deepEqual(ethCard.scrollOptions, { block: "start" });
assert.deepEqual(ethCard.focusOptions, { preventScroll: true });
assert.equal(focusOperatorCard(operatorCardContainer, "MISSING"), false);
assert.equal(focusOperatorCard(operatorCardContainer, null), false);
assert.equal(
  focusOperatorCard(operatorCardContainer, "BTCUSDT", "post-activation"),
  true,
);
assert.equal(btcCard.sections["post-activation"].open, true);
assert.deepEqual(
  btcCard.sections["post-activation"].scrollOptions,
  { block: "start" },
);
assert.equal(
  focusOperatorCard(operatorCardContainer, "BTCUSDT", "migration-history"),
  true,
);
assert.equal(btcCard.sections["migration-history"].open, true);
assert.equal(
  focusOperatorCard(operatorCardContainer, "BTCUSDT", "active-mrz"),
  true,
);
assert.equal(btcCard.sections["active-mrz"].open, false);
assert.deepEqual(btcCard.sections["active-mrz"].focusOptions, { preventScroll: true });

const operationCardSource = fs.readFileSync(
  require.resolve("../app/static/mrz-robustness.js"),
  "utf8",
);
const operationCardCss = fs.readFileSync(
  require.resolve("../app/static/mrz-robustness.css"),
  "utf8",
);
const operationCardHtml = fs.readFileSync(
  require.resolve("../app/static/mrz-robustness.html"),
  "utf8",
);
assert.doesNotMatch(operationCardSource, /bb_mrz_(?:discount|premium)/);
assert.doesNotMatch(operationCardSource, /trade recommendation/i);
assert.doesNotMatch(operationCardSource, /Candidate forming|Awaiting confirmation/i);
assert.doesNotMatch(
  operationCardSource,
  /Fast formation|Slow formation|Strong intent|Weak intent|Bullish intent|Bearish intent|High conviction|Preferred|Better setup/i,
);
assert.doesNotMatch(
  `${operationCardSource}\n${operationCardHtml}`,
  /<select|type=["']search["']|data-sort|data-filter/i,
);
assert.match(operationCardHtml, /id="filterAll"[^>]*aria-pressed="false"[^>]*>All</);
assert.match(
  operationCardHtml,
  /id="filterMigrated"[^>]*aria-pressed="true"[^>]*>Migrated only</,
);
assert.match(
  operationCardSource,
  /let filterMode = "migrated";/,
  "Migrated only must be the initial Operator Card filter",
);
assert.match(
  operationCardSource,
  /reports = report\.active_mrzs;\s*renderReports\(\);/,
  "the async response must populate report state before rendering",
);
const reportLoadSource = operationCardSource.split("async function loadReport()", 2)[1];
const renderAfterLoadIndex = reportLoadSource.indexOf("renderReports();");
const revealAfterRenderIndex = reportLoadSource.indexOf("content.hidden = false;");
const focusAfterRevealIndex = reportLoadSource.indexOf(
  "focusOperatorCard(",
);
assert.ok(
  renderAfterLoadIndex >= 0
    && renderAfterLoadIndex < revealAfterRenderIndex
    && revealAfterRenderIndex < focusAfterRevealIndex,
  "target scrolling must run after asynchronous render and after the report becomes visible",
);
assert.doesNotMatch(operationCardSource, /setTimeout\(/);

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
    activated_at: "2026-08-26T05:37:00Z",
  },
  formation_evidence: {
    confirming_observation_count: 4,
    started_at: "2026-08-24T14:25:00Z",
    completed_at: "2026-08-26T05:37:00Z",
    duration_seconds: "141120",
    meaning: "Why the active MRZ was formed.",
  },
  robustness_evidence: {
    post_activation_observation_count: 4,
    meaning: "What occurred after the active MRZ was formed.",
  },
  post_activation_robustness: {
    status: "UNDER_PRESSURE",
    label: "Upward Pressure",
    reason: "Above-envelope activity materially dominates below-envelope activity.",
    post_activation_observation_count: 4,
  },
  observation_position: {
    above_active_mrz_observation_count: 3,
    inside_active_mrz_observation_count: 1,
    below_active_mrz_observation_count: 0,
    total_observation_count: 4,
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
  mrz_displacement: {
    median_signed_displacement_percentage_of_activation_ipda: "6.210106982847374890268628785",
    direction: "ABOVE",
    label: "Median displacement above midpoint",
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
    label: "Upward Pressure",
    reason: "Above-envelope activity materially dominates below-envelope activity.",
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
    status: "EXTERNAL_OBSERVATIONS",
    label: "External observations detected",
    reason: "External observations exist, but no side-and-route pool has enough evidence for a qualifying concentration.",
    direction: null,
    direction_label: null,
    symbol: null,
    route: null,
    candidate_lower: null,
    candidate_upper: null,
    evidence_observation_count: 0,
    required_observation_count: 4,
    normalized_span: null,
    production_allowance: "0.01",
    production_evaluation_result: "INSUFFICIENT_OBSERVATIONS",
    external_observation_count: 3,
    higher_external_observation_count: 3,
    lower_external_observation_count: 0,
    operational_migration_eligible: null,
    operational_migration_eligibility_label: "Not assessed",
    current_mrz_remains_authoritative: true,
    diagnostic_only: true,
  },
  mrz_age: {
    active_duration_seconds: "219600",
  },
  structural_summary: {
    current_authority: "STR · Deep Premium",
    robustness_status: "UNDER_PRESSURE",
    robustness_label: "Upward Pressure",
    pressure_direction: "UP",
    pressure_direction_label: "Upward",
    structural_role: "RESISTIVE",
    structural_role_label: "Resistive",
    successor_status: "NOT_DETECTED",
    successor_label: "Not detected",
    authority_statement: "The current MRZ remains authoritative.",
    displacement_statement: "Post-activation observations are centered above the active MRZ midpoint.",
    detail_statement: "Above-envelope activity materially dominates.",
  },
};

const btcMarkup = robustnessCardMarkup(
  btcReport,
  (value) => value === "2026-08-24T14:25:00Z"
    ? "24 Aug 2026 · 10:25 UTC−4"
    : "26 Aug 2026 · 01:37 UTC−4",
);
const btcCompactSummary = btcMarkup.slice(0, btcMarkup.indexOf("</header>") + 9);
const authorityIndex = btcCompactSummary.indexOf('class="mrz-authority-context"');
const currentPressureIndex = btcCompactSummary.indexOf('class="current-pressure-panel');
assert.ok(authorityIndex >= 0, "MRZ Authority renders on the default surface");
assert.ok(currentPressureIndex > authorityIndex, "Current Pressure follows MRZ Authority");
const orderedDisclosures = [
  'data-section="post-activation"',
  'data-section="migration-history"',
  'data-section="successor-watch"',
  'data-section="formation-details"',
];
assert.match(btcMarkup, /data-section="active-mrz"/);
let previousIndex = -1;
for (const section of orderedDisclosures) {
  const currentIndex = btcMarkup.indexOf(section);
  assert.ok(currentIndex > previousIndex, `${section} is rendered in sequence`);
  previousIndex = currentIndex;
}
const firstDisclosureIndex = btcMarkup.indexOf("<details");
for (const summaryValue of [
  "BTCUSDT · STR",
  "Deep Premium",
  "MRZ AUTHORITY",
  "CURRENT MRZ",
  "PREVIOUS MRZ",
  "77,309.19 – 77,436.91",
  "Midpoint",
  "Activated",
  "CURRENT PRESSURE",
  "Upward Pressure",
  "4 observations",
  "Above upper envelope",
  "Below lower envelope",
]) {
  const summaryValueIndex = btcMarkup.indexOf(summaryValue);
  assert.ok(summaryValueIndex >= 0, `${summaryValue} renders in the compact summary`);
  assert.ok(
    summaryValueIndex < firstDisclosureIndex,
    `${summaryValue} remains visible before collapsed details`,
  );
}
assert.match(btcMarkup, /<header class="compact-authority"/);
assert.match(btcMarkup, /<summary>/);
assert.equal((btcMarkup.match(/<details/g) || []).length, 4);
assert.doesNotMatch(btcMarkup, /<details[^>]*\sopen(?:\s|>)/);
assert.doesNotMatch(btcMarkup, /data-section="evidence"/);
assert.doesNotMatch(btcMarkup, /evidence-disclosure/);
assert.match(
  btcMarkup,
  /data-section="post-activation"[\s\S]*Observation Position[\s\S]*<\/details>/,
);
assert.match(
  btcMarkup,
  /data-section="successor-watch"[\s\S]*Minimum evidence[\s\S]*<\/details>/,
);
assert.match(
  btcMarkup,
  /data-section="formation-details"[\s\S]*First qualifying rejection[\s\S]*Formation duration[\s\S]*<\/details>/,
);
assert.match(btcMarkup, /BTCUSDT · STR/);
assert.match(btcMarkup, /Deep Premium/);
assert.match(btcMarkup, /Authoritative/);
assert.match(btcMarkup, /77,309\.19 – 77,436\.91/);
assert.match(btcMarkup, /Midpoint<\/dt><dd>77,373\.05/);
assert.match(btcMarkup, /26 Aug 2026 · 01:37 UTC−4/);
assert.match(btcMarkup, /Formation duration<\/dt><dd>1d 15h/);
assert.doesNotMatch(btcMarkup, /4 qualifying rejection observations/);
assert.match(btcMarkup, /First qualifying rejection/);
assert.match(btcMarkup, /24 Aug 2026 · 10:25 UTC−4/);
assert.match(btcMarkup, /Formation duration<\/dt><dd>1d 15h/);
assert.match(btcCompactSummary, /No previous MRZ/);
assert.match(btcCompactSummary, /2d 13h old/);
assert.doesNotMatch(btcCompactSummary, /First qualifying rejection/);
assert.doesNotMatch(btcCompactSummary, /Formation duration/);
assert.doesNotMatch(btcCompactSummary, /Successor/);
assert.doesNotMatch(btcCompactSummary, /MIGRATION EQM/);
assert.match(
  btcMarkup,
  /data-section="post-activation"[\s\S]*Upward Pressure[\s\S]*<\/details>/,
);
assert.equal(
  btcReport.active_mrz.activated_at,
  btcReport.formation_evidence.completed_at,
);
assert.equal(
  (Date.parse(btcReport.active_mrz.activated_at)
    - Date.parse(btcReport.formation_evidence.started_at)) / 1000,
  Number(btcReport.formation_evidence.duration_seconds),
);
assert.match(btcMarkup, /Upward Pressure/);
assert.match(btcCompactSummary, /Above upper envelope<\/dt><dd>3/);
assert.match(btcCompactSummary, /Below lower envelope<\/dt><dd>0/);
assert.match(btcMarkup, /Observation Position/);
assert.match(btcMarkup, /Above MRZ<\/dt><dd>3/);
assert.match(btcMarkup, /Inside MRZ<\/dt><dd>1/);
assert.match(btcMarkup, /Below MRZ<\/dt><dd>0/);
assert.match(btcMarkup, /Migration Envelope/);
assert.match(btcMarkup, /Above envelope<\/dt><dd>3/);
assert.match(btcMarkup, /Below envelope<\/dt><dd>0/);
assert.match(btcMarkup, /MRZ Displacement/);
assert.match(btcMarkup, /↑ \+6\.2%/);
assert.match(btcMarkup, /Median displacement above midpoint/);
assert.match(btcMarkup, /Normalized by full IPDA 20W width stored at activation/);
assert.match(btcMarkup, /External observations detected/);
assert.match(btcMarkup, /Higher external<\/dt><dd>3/);
assert.match(btcMarkup, /Lower external<\/dt><dd>0/);
assert.match(btcMarkup, /Minimum evidence<\/dt><dd>4 observations/);
assert.match(btcMarkup, /Insufficient observations/);
assert.match(btcMarkup, /no side-and-route pool has enough evidence/i);
assert.doesNotMatch(btcMarkup, /Midpoint Stability/);
assert.doesNotMatch(btcMarkup, /Distance From MRZ Midpoint/);
assert.doesNotMatch(btcMarkup, /bb_mrz/);
assert.doesNotMatch(btcMarkup, /\b(?:buy|sell|long|short)\b/i);
assert.doesNotMatch(btcMarkup, /Healthy|Weak|Good|Bad/);
assert.doesNotMatch(btcMarkup, /MIGRATED UPWARD|MIGRATED DOWNWARD/);
assert.doesNotMatch(btcMarkup, /Structural Role|Route Integrity|Containment/i);
assert.doesNotMatch(btcMarkup, /Boundary Behavior|Upper tests|Lower tests/i);
assert.doesNotMatch(btcMarkup, /Resistive|Supportive/i);
assert.doesNotMatch(btcMarkup, /<dt>First rejection<\/dt>/);

const ethBalancedReport = {
  ...btcReport,
  symbol: "ETHUSDT",
  active_mrz: {
    ...btcReport.active_mrz,
    lower: "2452.46",
    upper: "2461.11",
    midpoint: "2456.785",
  },
  robustness_evidence: {
    ...btcReport.robustness_evidence,
    post_activation_observation_count: 22,
  },
  post_activation_robustness: {
    status: "STABLE",
    label: "Two-sided / Consolidating",
    reason: "Post-activation observations are distributed on both sides of the active MRZ with no meaningful directional dominance.",
    post_activation_observation_count: 22,
  },
  observation_position: {
    above_active_mrz_observation_count: 10,
    inside_active_mrz_observation_count: 2,
    below_active_mrz_observation_count: 10,
    total_observation_count: 22,
  },
  boundary_pressure: {
    ...btcReport.boundary_pressure,
    outside_envelope_observation_count: 11,
    above_upper_envelope_observation_count: 5,
    below_lower_envelope_observation_count: 6,
  },
  mrz_displacement: {
    ...btcReport.mrz_displacement,
    median_signed_displacement_percentage_of_activation_ipda: "-0.1",
    direction: "BELOW",
    label: "Median displacement below midpoint",
  },
  migration_pressure: {
    ...btcReport.migration_pressure,
    status: "STABLE",
    label: "Two-sided / Consolidating",
    reason: "Post-activation observations are distributed on both sides of the active MRZ with no meaningful directional dominance.",
    direction: "NEUTRAL",
    direction_label: "Neutral",
    relevant_boundary_label: null,
    relevant_boundary: null,
    observations_beyond_envelope: 11,
    above_upper_envelope_observation_count: 5,
    below_lower_envelope_observation_count: 6,
  },
  successor_watch: {
    ...btcReport.successor_watch,
    status: "NO_QUALIFYING_SUCCESSOR",
    label: "No qualifying successor",
    evidence_observation_count: 6,
    higher_external_observation_count: 5,
    lower_external_observation_count: 6,
    production_evaluation_result: "TOO_DISPERSED",
  },
  structural_summary: {
    ...btcReport.structural_summary,
    robustness_status: "STABLE",
    robustness_label: "Two-sided / Consolidating",
    pressure_direction: "NEUTRAL",
    pressure_direction_label: "Neutral",
    displacement_statement: "Post-activation observations are centered below the active MRZ midpoint.",
    detail_statement: "Post-activation observations are distributed on both sides of the active MRZ with no meaningful directional dominance. No qualifying successor candidate is detected.",
  },
};
const ethBalancedMarkup = robustnessCardMarkup(ethBalancedReport);
const ethBalancedSummary = ethBalancedMarkup.slice(
  0,
  ethBalancedMarkup.indexOf("</header>") + 9,
);
assert.match(ethBalancedSummary, /CURRENT PRESSURE/);
assert.match(ethBalancedSummary, /Two-sided \/ Consolidating/);
assert.match(ethBalancedSummary, /22 observations/);
assert.doesNotMatch(ethBalancedSummary, /No qualifying successor/);
assert.match(ethBalancedMarkup, /Two-sided \/ Consolidating · 22 observations/);
assert.match(ethBalancedMarkup, /Above MRZ<\/dt><dd>10/);
assert.match(ethBalancedMarkup, /Inside MRZ<\/dt><dd>2/);
assert.match(ethBalancedMarkup, /Below MRZ<\/dt><dd>10/);
assert.match(ethBalancedMarkup, /11<\/strong>\s*<span class="metric-secondary">outside envelope/);
assert.match(ethBalancedMarkup, /Above envelope<\/dt><dd>5/);
assert.match(ethBalancedMarkup, /Below envelope<\/dt><dd>6/);
assert.match(ethBalancedMarkup, /↓ -0\.1%/);
assert.match(ethBalancedMarkup, /Median displacement below midpoint/);
assert.match(ethBalancedMarkup, /no meaningful directional dominance/i);
assert.doesNotMatch(ethBalancedMarkup, /Under Pressure|↓ Downward/);

const downwardPressureMarkup = robustnessCardMarkup({
  ...btcReport,
  post_activation_robustness: {
    ...btcReport.post_activation_robustness,
    label: "Downward Pressure",
  },
  boundary_pressure: {
    ...btcReport.boundary_pressure,
    above_upper_envelope_observation_count: 0,
    below_lower_envelope_observation_count: 4,
  },
  migration_pressure: {
    ...btcReport.migration_pressure,
    label: "Downward Pressure",
    direction: "DOWN",
    direction_label: "Downward",
    above_upper_envelope_observation_count: 0,
    below_lower_envelope_observation_count: 4,
  },
});
const downwardPressureSummary = downwardPressureMarkup.slice(
  0,
  downwardPressureMarkup.indexOf("</header>") + 9,
);
assert.match(downwardPressureSummary, /CURRENT PRESSURE[\s\S]*Downward Pressure/);
assert.match(downwardPressureSummary, /Above upper envelope<\/dt><dd>0/);
assert.match(downwardPressureSummary, /Below lower envelope<\/dt><dd>4/);

assert.match(operationCardCss, /\.operator-disclosure\[open\] > summary/);
assert.match(operationCardCss, /\.operator-disclosure > summary:focus-visible/);
assert.match(operationCardCss, /min-height:\s*64px/);
assert.match(operationCardCss, /@media \(max-width: 460px\)/);
assert.match(
  operationCardCss,
  /\.mrz-authority-grid\s*\{[^}]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/,
);
assert.match(
  operationCardCss,
  /\.current-pressure-counts\s*\{[^}]*grid-template-columns:\s*repeat\(2, minmax\(0, 1fr\)\)/,
);
assert.match(
  operationCardCss,
  /@media \(max-width: 720px\)[\s\S]*\.report-meta, \.mrz-authority-grid[^{]*\{\s*grid-template-columns:\s*minmax\(0, 1fr\)/,
);
assert.match(
  operationCardCss,
  /@media \(max-width: 460px\)[\s\S]*\.current-pressure-counts\s*\{\s*grid-template-columns:\s*minmax\(0, 1fr\)/,
);
assert.match(
  operationCardCss,
  /\.authority-range\s*\{[^}]*overflow-wrap:\s*anywhere/,
);
assert.match(
  operationCardCss,
  /@media \(max-width: 720px\)[\s\S]*\.filter-option\s*\{[^}]*min-height:\s*44px/,
);
assert.match(operationCardCss, /\.migration-timeline li > div > strong[^}]*overflow-wrap:\s*anywhere/);
assert.doesNotMatch(operationCardCss, /overflow-x:\s*(?:auto|scroll)/);
assert.doesNotMatch(operationCardCss, /\border\s*:/);

const wldMigration = {
  has_migrated: true,
  direction: "UP",
  migrated_at: "2026-08-24T16:00:00Z",
  previous_activated_at: "2026-08-23T08:15:00Z",
  previous_lower: 0.3936,
  previous_upper: 0.3966,
  current_lower: 0.4034,
  current_upper: 0.4083,
};
const migrationMarkup = migrationProvenanceMarkup(
  wldMigration,
  {
    currentMidpoint: "0.40585",
    pressureLabel: "Stable",
    successorLabel: "No successor candidate",
  },
  (value) => value === "2026-08-23T08:15:00Z"
    ? "23 Aug 2026 · 04:15 UTC−4"
    : "24 Aug 2026 · 12:00 UTC−4",
);
assert.match(migrationMarkup, /↑ MIGRATED UPWARD/);
assert.match(migrationMarkup, /24 Aug 2026 · 12:00 UTC−4/);
assert.match(migrationMarkup, /0\.3936 – 0\.3966/);
assert.match(migrationMarkup, /0\.4034 – 0\.4083/);
assert.match(migrationMarkup, /PREVIOUS AUTHORITY/);
assert.match(migrationMarkup, /Midpoint 0\.3951/);
assert.match(migrationMarkup, /Activated 23 Aug 2026 · 04:15 UTC−4/);
assert.ok(
  migrationMarkup.indexOf("Midpoint 0.3951")
    < migrationMarkup.indexOf("Activated 23 Aug 2026 · 04:15 UTC−4"),
  "previous activation is rendered beneath the previous midpoint",
);
assert.notEqual(
  migrationMarkup.indexOf("23 Aug 2026 · 04:15 UTC−4"),
  migrationMarkup.indexOf("24 Aug 2026 · 12:00 UTC−4"),
  "previous activation and current migration timestamps remain distinct",
);
assert.match(migrationMarkup, /MIGRATION EQM/);
assert.match(migrationMarkup, /0\.400475/);
assert.match(migrationMarkup, /CURRENT AUTHORITY/);
assert.match(migrationMarkup, /Midpoint 0\.40585/);
assert.doesNotMatch(migrationMarkup, /POST-MIGRATION|State<\/dt>|Successor<\/dt>/);
assert.equal(migrationEqmValue(wldMigration, "0.40585"), 0.400475);
assert.match(
  migrationProvenanceMarkup(
    { ...wldMigration, direction: "DOWN" },
    { currentMidpoint: "0.40585" },
    () => "timestamp",
  ),
  /↓ MIGRATED DOWNWARD/,
);
assert.match(
  migrationProvenanceMarkup(
    { ...wldMigration, previous_activated_at: null },
    { currentMidpoint: "0.40585" },
    () => null,
  ),
  /Activated Unavailable/,
);

const btcMigrationChainMarkup = migrationProvenanceMarkup(
  {
    has_migrated: true,
    direction: "UP",
    migrated_at: "2026-08-31T17:50:00Z",
    previous_activated_at: "2026-08-31T08:15:00Z",
    previous_lower: 78040.41,
    previous_upper: 78226.01,
    current_lower: 78850.69,
    current_upper: 79030,
  },
  {
    currentMidpoint: "78940.345",
    pressureLabel: "Stable",
    successorLabel: "No successor candidate",
  },
  (value) => value === "2026-08-31T08:15:00Z"
    ? "31 Aug 2026 · 04:15 UTC−4"
    : "31 Aug 2026 · 13:50 UTC−4",
);
assert.match(btcMigrationChainMarkup, /78,040\.41 – 78,226\.01/);
assert.match(btcMigrationChainMarkup, /Midpoint 78,133\.21/);
assert.match(btcMigrationChainMarkup, /Activated 31 Aug 2026 · 04:15 UTC−4/);
assert.match(btcMigrationChainMarkup, /31 Aug 2026 · 13:50 UTC−4/);

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
    activated_at: "2026-08-29T17:50:00Z",
  },
  formation_evidence: {
    ...btcReport.formation_evidence,
    started_at: "2026-08-29T01:13:00Z",
    completed_at: "2026-08-29T17:50:00Z",
    duration_seconds: "59820",
  },
  robustness_evidence: {
    ...btcReport.robustness_evidence,
    post_activation_observation_count: 1,
  },
  post_activation_robustness: {
    status: "STABLE",
    label: "Contained / Quiet",
    reason: "The observed post-activation sample remains within the frozen migration envelope.",
    post_activation_observation_count: 1,
  },
  observation_position: {
    above_active_mrz_observation_count: 0,
    inside_active_mrz_observation_count: 1,
    below_active_mrz_observation_count: 0,
    total_observation_count: 1,
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
  mrz_displacement: {
    ...btcReport.mrz_displacement,
    median_signed_displacement_percentage_of_activation_ipda: "-0.977428456267634",
    direction: "BELOW",
    label: "Median displacement below midpoint",
  },
  migration_pressure: {
    ...btcReport.migration_pressure,
    status: "STABLE",
    label: "Contained / Quiet",
    reason: "No post-activation observation is outside the frozen migration envelope.",
    direction: "NEUTRAL",
    direction_label: "Neutral",
    relevant_boundary_label: null,
    relevant_boundary: null,
    observations_beyond_envelope: 0,
    above_upper_envelope_observation_count: 0,
  },
  successor_watch: {
    ...btcReport.successor_watch,
    status: "NO_SUCCESSOR_CANDIDATE",
    label: "No successor candidate",
    reason: "No qualifying external concentration exists.",
    external_observation_count: 0,
    higher_external_observation_count: 0,
    lower_external_observation_count: 0,
  },
  structural_summary: {
    ...btcReport.structural_summary,
    current_authority: "BTD · Shallow Discount",
    robustness_status: "STABLE",
    robustness_label: "Contained / Quiet",
    pressure_direction: "NEUTRAL",
    pressure_direction_label: "Neutral",
    structural_role: "SUPPORTIVE",
    structural_role_label: "Supportive",
    displacement_statement: "Post-activation observations are centered below the active MRZ midpoint.",
    detail_statement: "No post-activation observation is outside the frozen migration envelope.",
  },
};
const wldMarkup = robustnessCardMarkup(
  wldReport,
  (value) => value === "2026-08-29T01:13:00Z"
    ? "28 Aug 2026 · 21:13 UTC−4"
    : value === "2026-08-29T17:50:00Z"
      ? "29 Aug 2026 · 13:50 UTC−4"
      : "24 Aug 2026 · 12:00 UTC−4",
);
const wldCompactSummary = wldMarkup.slice(0, wldMarkup.indexOf("</header>") + 9);
assert.match(wldMarkup, /WLDUSDT · BTD/);
assert.match(wldMarkup, /Shallow Discount/);
assert.match(wldMarkup, /↑ MIGRATED UPWARD/);
assert.match(wldMarkup, /Contained \/ Quiet/);
assert.match(wldMarkup, /↓ -1\.0%/);
assert.match(wldMarkup, /Median displacement below midpoint/);
assert.match(wldMarkup, /No successor candidate/);
assert.match(wldMarkup, /Previous MRZ/);
assert.match(wldMarkup, /Midpoint 0\.3951/);
assert.match(wldMarkup, /MIGRATION EQM/);
assert.match(wldMarkup, /0\.400475/);
assert.match(wldMarkup, /Midpoint 0\.40585/);
assert.doesNotMatch(
  wldMarkup,
  /Previous MRZ is (?:support|resistance)|Migration confirmed (?:bullish|bearish)|Long setup|Short setup/i,
);
assert.doesNotMatch(wldMarkup, /4 qualifying reclaim observations/);
assert.match(wldMarkup, /First qualifying reclaim/);
assert.match(wldCompactSummary, /CURRENT MRZ/);
assert.match(wldCompactSummary, /0\.4034 – 0\.4083/);
assert.match(wldCompactSummary, /Midpoint<\/dt><dd>0\.40585/);
assert.match(wldCompactSummary, /Activated<\/dt><dd>29 Aug 2026 · 13:50 UTC−4/);
assert.match(wldCompactSummary, /PREVIOUS MRZ/);
assert.match(wldCompactSummary, /0\.3936 – 0\.3966/);
assert.match(wldCompactSummary, /Midpoint<\/dt><dd>0\.3951/);
assert.match(wldCompactSummary, /Activated<\/dt><dd>24 Aug 2026 · 12:00 UTC−4/);
assert.match(wldCompactSummary, /MIGRATION EQM/);
assert.match(wldCompactSummary, /0\.400475/);
assert.ok(
  wldCompactSummary.indexOf("current-authority-zone")
    < wldCompactSummary.indexOf("previous-authority-zone"),
  "Current MRZ precedes Previous MRZ in the responsive DOM order",
);
assert.doesNotMatch(wldCompactSummary, /First qualifying reclaim|Formation duration|No successor candidate/);
assert.doesNotMatch(wldMarkup, /<dt>First reclaim<\/dt>/);

const secondMigratedReport = {
  ...wldReport,
  symbol: "XAGUSD",
  migration: {
    ...wldMigration,
    direction: "DOWN",
    previous_lower: "69.5",
    previous_upper: "70",
    current_lower: "68.995",
    current_upper: "69.233",
  },
  active_mrz: {
    ...wldReport.active_mrz,
    lower: "68.995",
    upper: "69.233",
    midpoint: "69.114",
  },
};
const migrationProxyReport = {
  ...btcReport,
  symbol: "PRESSUREONLY",
  migration: { has_migrated: false },
  migration_pressure: {
    ...btcReport.migration_pressure,
    status: "UNDER_PRESSURE",
  },
  successor_watch: {
    ...btcReport.successor_watch,
    status: "SUCCESSOR_CANDIDATE",
  },
};
assert.equal(hasValidMigrationProvenance(wldReport), true);
assert.equal(hasValidMigrationProvenance(btcReport), false);
assert.equal(hasValidMigrationProvenance(migrationProxyReport), false);
assert.equal(
  hasValidMigrationProvenance({
    ...wldReport,
    migration: { ...wldMigration, previous_lower: null },
  }),
  false,
);
const backendOrderedReports = [btcReport, wldReport, migrationProxyReport, secondMigratedReport];
assert.deepEqual(
  filterReports(backendOrderedReports, "all").map((report) => report.symbol),
  ["BTCUSDT", "WLDUSDT", "PRESSUREONLY", "XAGUSD"],
);
assert.deepEqual(
  filterReports(backendOrderedReports, "migrated").map((report) => report.symbol),
  ["WLDUSDT", "XAGUSD"],
  "migrated filtering preserves the backend formation-duration order",
);
const allReportsMarkup = reportMarkup(backendOrderedReports);
assert.match(allReportsMarkup, /BTCUSDT/);
assert.match(allReportsMarkup, /WLDUSDT/);
assert.match(allReportsMarkup, /PRESSUREONLY/);
assert.match(allReportsMarkup, /XAGUSD/);
assert.doesNotMatch(allReportsMarkup, /focused-operator-card/);
const focusedReportsMarkup = reportMarkup(
  backendOrderedReports,
  (value) => value,
  "all",
  "BTCUSDT",
);
assert.match(
  focusedReportsMarkup,
  /class="mrz-report focused-operator-card" data-symbol="BTCUSDT" tabindex="-1"/,
);
assert.doesNotMatch(
  focusedReportsMarkup,
  /class="mrz-report focused-operator-card" data-symbol="(?:WLDUSDT|PRESSUREONLY|XAGUSD)"/,
  "a symbol-level link cannot focus another symbol's card",
);
const migratedReportsMarkup = reportMarkup(
  backendOrderedReports,
  (value) => value,
  "migrated",
);
assert.doesNotMatch(migratedReportsMarkup, /BTCUSDT|PRESSUREONLY/);
assert.ok(
  migratedReportsMarkup.indexOf("WLDUSDT") < migratedReportsMarkup.indexOf("XAGUSD"),
  "the filtered list keeps the existing relative order",
);
assert.match(
  reportMarkup([btcReport, migrationProxyReport], (value) => value, "migrated"),
  /No migrated MRZ pairs currently available/,
);
assert.match(
  reportMarkup([], (value) => value, "migrated"),
  /No migrated MRZ pairs currently available/,
);

const unavailableFormationMarkup = robustnessCardMarkup({
  ...btcReport,
  formation_evidence: {
    ...btcReport.formation_evidence,
    started_at: null,
    completed_at: null,
    duration_seconds: null,
  },
});
assert.match(
  unavailableFormationMarkup,
  /Formation duration<\/dt><dd>Unavailable<\/dd>/,
);
assert.match(
  unavailableFormationMarkup,
  /First qualifying rejection<\/dt><dd>Unavailable<\/dd>/,
);
const unavailableCompactSummary = unavailableFormationMarkup.slice(
  0,
  unavailableFormationMarkup.indexOf("</header>") + 9,
);
assert.match(
  unavailableCompactSummary,
  /No previous MRZ/,
);
assert.doesNotMatch(unavailableCompactSummary, /First qualifying rejection|Formation duration/);

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
  observation_position: {
    above_active_mrz_observation_count: 0,
    inside_active_mrz_observation_count: 0,
    below_active_mrz_observation_count: 0,
    total_observation_count: 0,
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
  mrz_displacement: {
    ...wldReport.mrz_displacement,
    median_signed_displacement_percentage_of_activation_ipda: null,
    direction: null,
    label: "No post-activation evidence",
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
    displacement_statement: "No post-activation displacement evidence is available yet.",
    detail_statement: "No post-activation evidence is available yet.",
  },
};
const zeroMarkup = robustnessCardMarkup(zeroEvidenceReport);
assert.match(zeroMarkup, /Not yet assessable/);
assert.match(zeroMarkup, /0 observations/);
assert.match(zeroMarkup, /No evidence/);
assert.match(zeroMarkup, /MRZ Displacement<\/h3>\s*<strong class="metric-primary">—<\/strong>/);
assert.match(zeroMarkup, /No post-activation evidence/);

const successorReport = {
  ...btcReport,
  successor_watch: {
    ...btcReport.successor_watch,
    status: "SUCCESSOR_CANDIDATE",
    label: "Qualifying successor candidate",
    reason: "A canonical external concentration qualifies. The current MRZ remains authoritative until the production migration engine changes it.",
    direction: "UP",
    direction_label: "Higher",
    symbol: "BTCUSDT",
    route: "STR",
    candidate_lower: "78100",
    candidate_upper: "78250",
    evidence_observation_count: 4,
    normalized_span: "0.0012",
    production_evaluation_result: "QUALIFIES",
    operational_migration_eligible: true,
    operational_migration_eligibility_label: "Satisfied",
  },
};
const successorMarkup = robustnessCardMarkup(successorReport);
assert.match(successorMarkup, /↑ Higher/);
assert.match(successorMarkup, /78,100 – 78,250/);
assert.match(successorMarkup, /Evidence<\/dt><dd>4 observations/);
assert.match(successorMarkup, /0\.1%/);
assert.match(successorMarkup, /Production allowance<\/dt><dd>1\.0%/);
assert.match(successorMarkup, /Qualifies/);
assert.match(successorMarkup, /Candidate rule eligibility<\/dt><dd>Satisfied/);
assert.doesNotMatch(successorMarkup, /Operational migration eligibility/);
assert.match(successorMarkup, /current MRZ remains authoritative until the production migration engine changes it/i);

const tooDispersedMarkup = successorDetailsMarkup({
  ...btcReport.successor_watch,
  status: "NO_QUALIFYING_SUCCESSOR",
  evidence_observation_count: 5,
  normalized_span: "0.023",
  production_evaluation_result: "TOO_DISPERSED",
  higher_external_observation_count: 5,
});
assert.match(tooDispersedMarkup, /Observation count<\/dt><dd>5/);
assert.match(tooDispersedMarkup, /Concentration<\/dt><dd>2\.3%/);
assert.match(tooDispersedMarkup, /Production allowance<\/dt><dd>1\.0%/);
assert.match(tooDispersedMarkup, /Result<\/dt><dd>Too dispersed/);
assert.doesNotMatch(tooDispersedMarkup, /Candidate range|Awaiting confirmation/);

const isolatedExternalMarkup = successorDetailsMarkup({
  ...btcReport.successor_watch,
  higher_external_observation_count: 1,
  lower_external_observation_count: 0,
});
assert.match(isolatedExternalMarkup, /Higher external<\/dt><dd>1/);
assert.match(isolatedExternalMarkup, /Minimum evidence<\/dt><dd>4 observations/);
assert.doesNotMatch(isolatedExternalMarkup, /Candidate|Direction|Eligible observations/);

const empty = reportMarkup([]);
assert.match(empty, /No active MRZ is available for an operation card/);

console.log("MRZ operation card presentation tests passed");
