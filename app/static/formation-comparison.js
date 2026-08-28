const formationEscapeHtml = (value) => String(value ?? "—")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

const formationNumber = (value, digits = 2) => value == null ? "—" : new Intl.NumberFormat("en-US", {
  maximumFractionDigits: digits,
}).format(value);

const formationPercent = (value) => value == null ? "—" : `${formationNumber(value, 1)}%`;

const outcomeRatio = (metric) => `${metric.numerator} of ${metric.denominator} · ${formationPercent(metric.percentage)}`;

const ordinalTiming = (index, hours) => index == null ? "—" : `+${index} · ${formationNumber(hours, 2)}h`;

function comparisonTableMarkup(summaries) {
  const row = (label, render) => `<tr><th scope="row">${formationEscapeHtml(label)}</th>${summaries.map((item) => `<td>${render(item)}</td>`).join("")}</tr>`;
  return `<div class="table-wrap formation-summary-table"><table>
    <thead><tr><th>Metric</th>${summaries.map((item) => `<th>${formationEscapeHtml(item.label)}</th>`).join("")}</tr></thead>
    <tbody>
      ${row("Candidates", (item) => item.candidates)}
      ${row("With follow-through", (item) => `${item.with_follow_through} of ${item.candidates}`)}
      ${row("Resolved", (item) => `${item.resolved} of ${item.candidates}`)}
      ${row("Pending", (item) => item.pending)}
      ${row("Supportive first", (item) => outcomeRatio(item.supportive_first))}
      ${row("Adverse first", (item) => outcomeRatio(item.adverse_first))}
      ${row("Unresolved", (item) => item.unresolved)}
      ${row("Median supportive lag", (item) => item.median_supportive_lag_hours == null ? "—" : `${formationNumber(item.median_supportive_lag_hours, 2)}h`)}
      ${row("Median adverse lag", (item) => item.median_adverse_lag_hours == null ? "—" : `${formationNumber(item.median_adverse_lag_hours, 2)}h`)}
      ${row("Supportive-first windows", (item) => `${item.supportive_first_windows.numerator} of ${item.supportive_first_windows.denominator}`)}
      ${row("Sample", (item) => `<span class="comparison-sample">${formationEscapeHtml(item.sample_state)}</span>`)}
    </tbody>
  </table></div>`;
}

function primaryArrivalMarkup(summaries) {
  return `<div class="arrival-grid">${summaries.map((item) => `
    <article class="arrival-card">
      <p class="section-kicker">${formationEscapeHtml(item.label)}</p>
      <div><span>SUPPORTIVE-FIRST</span><strong>${item.supportive_first.numerator} of ${item.supportive_first.denominator}</strong></div>
      <div><span>ADVERSE-FIRST</span><strong>${item.adverse_first.numerator} of ${item.adverse_first.denominator}</strong></div>
      <div><span>UNRESOLVED</span><strong>${item.unresolved}</strong></div>
    </article>`).join("")}</div>`;
}

function nearMissCardMarkup(item, timestampFormatter = formatOperatorTimestampUtcMinus4) {
  const timestamp = timestampFormatter(item.anchor_at) || "—";
  const scope = {
    CURRENT: "Current candidate",
    HISTORICAL_CLOSEST: "Closest historical candidate",
    CURRENT_AND_HISTORICAL_CLOSEST: "Current and closest historical candidate",
  }[item.source] || item.source;
  return `<article class="near-miss-window-card ${item.outcome === "PENDING_FOLLOW_THROUGH" ? "pending" : ""}">
    <header><div><p class="section-kicker">${formationEscapeHtml(item.candidate_class)}</p><h3>${formationEscapeHtml(item.symbol)} · ${formationEscapeHtml(item.route)}</h3></div><span>${formationEscapeHtml(scope)}</span></header>
    <dl>
      <div><dt>Minimum allowance required</dt><dd>${formationNumber(item.minimum_required_allowance_pct, 2)}%</dd></div>
      <div><dt>Production allowance</dt><dd>${formationNumber(item.production_allowance_pct, 2)}%</dd></div>
      <div><dt>Candidate range</dt><dd>${formationNumber(item.candidate_lower, 6)}–${formationNumber(item.candidate_upper, 6)}</dd></div>
      <div><dt>Candidate observed</dt><dd>${formationEscapeHtml(timestamp)}</dd></div>
      <div><dt>Post-candidate observations</dt><dd>${item.post_anchor_observations}</dd></div>
      <div><dt>First supportive</dt><dd>${ordinalTiming(item.first_supportive_observation, item.first_supportive_hours)}</dd></div>
      <div><dt>First adverse</dt><dd>${ordinalTiming(item.first_adverse_observation, item.first_adverse_hours)}</dd></div>
      <div><dt>Outcome</dt><dd>${formationEscapeHtml(item.outcome_label)}</dd></div>
    </dl>
  </article>`;
}

function routeBreakdownMarkup(byRoute) {
  return `<details class="route-comparison"><summary>BTD / STR cohort denominators and timing</summary>
    ${Object.entries(byRoute).map(([route, summaries]) => `<section><h3>${formationEscapeHtml(route)}</h3>${comparisonTableMarkup(summaries)}</section>`).join("")}
  </details>`;
}

function renderFormationComparison(comparison, timestampFormatter = formatOperatorTimestampUtcMinus4) {
  const details = comparison.near_miss_details.length
    ? `<div class="near-miss-window-grid">${comparison.near_miss_details.map((item) => nearMissCardMarkup(item, timestampFormatter)).join("")}</div>`
    : '<p class="muted">No structurally eligible near-miss candidate at or below 2.00% is available in the current sample.</p>';
  return `<section class="report-section formation-comparison" id="production-vs-near-miss-windows">
    <p class="section-kicker">FORMATION STRICTNESS VS WINDOW QUALITY</p>
    <h2>${formationEscapeHtml(comparison.title)}</h2>
    <p class="research-question">${formationEscapeHtml(comparison.research_question)}</p>
    <p class="definition">${formationEscapeHtml(comparison.outcome_denominator)}</p>
    <section class="comparison-primary"><h3>What arrived first?</h3>${primaryArrivalMarkup(comparison.summaries)}</section>
    ${comparisonTableMarkup(comparison.summaries)}
    ${routeBreakdownMarkup(comparison.by_route)}
    <section class="near-miss-details"><p class="section-kicker">NEAR-MISS DETAIL</p><h3>Exact rejected candidate windows</h3><p class="definition">Candidate bounds are frozen exactly as selected by the production evaluator. These are analytical counterfactuals, not Active MRZs.</p>${details}</section>
    <aside class="comparison-interpretation"><span>${formationEscapeHtml(comparison.evidence_interpretation.status)}</span><p>${formationEscapeHtml(comparison.evidence_interpretation.text)}</p></aside>
  </section>`;
}

if (typeof module === "object" && module.exports) {
  module.exports = {
    comparisonTableMarkup,
    nearMissCardMarkup,
    outcomeRatio,
    primaryArrivalMarkup,
    renderFormationComparison,
  };
}
