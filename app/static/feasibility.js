const reportRoot = document.querySelector("#report");
const loading = document.querySelector("#reportLoading");
const refreshButton = document.querySelector("#refreshReport");

const escapeHtml = (value) => String(value ?? "—")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");

const formatNumber = (value, digits = 4) => value == null ? "—" : new Intl.NumberFormat("en-US", {
  maximumFractionDigits: digits,
}).format(value);

const formatPercent = (value) => value == null ? "—" : `${formatNumber(value, 1)}%`;

const metric = (label, value) => `
  <div><dt>${escapeHtml(label)}</dt><dd class="metric-value">${escapeHtml(value)}</dd></div>`;

const evidenceList = (items) => `<ul class="evidence-list">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;

const titleCase = (value) => value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());

const timingLabels = {
  first_adverse_migration_pressure: "First adverse pressure",
  first_route_supportive_displacement: "First route-supportive displacement",
  first_route_supportive_median: "First route-supportive median",
  first_successor_candidate: "First successor candidate",
  first_two_observation_supportive_sequence: "First two-observation supportive sequence",
  first_three_observation_supportive_sequence: "First three-observation supportive sequence",
  first_core_containment: "First core containment",
  first_no_adverse_envelope_breach: "First observation without adverse envelope breach",
};

function checkpointTable(checkpoints) {
  return `
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Checkpoint</th><th>Episodes</th><th>Signed median</th><th>Supportive</th><th>Adverse</th>
          <th>Inside core</th><th>Above / below core</th><th>Upper / lower tests</th>
          <th>Above / below envelope</th><th>Eligible / minimum</th><th>Successor candidate</th><th>Candidate range / span</th>
        </tr></thead>
        <tbody>${checkpoints.map((row) => `
          <tr>
            <td>${escapeHtml(row.checkpoint)}</td>
            <td>${row.episodes_available}</td>
            <td>${formatNumber(row.signed_median_displacement, 8)}</td>
            <td>${row.route_supportive} / ${row.episodes_available}</td>
            <td>${row.route_adverse} / ${row.episodes_available}</td>
            <td>${row.inside_mrz} / ${row.episodes_available}</td>
            <td>${row.above_core} / ${row.below_core}</td>
            <td>${row.upper_boundary_tests} / ${row.lower_boundary_tests}</td>
            <td>${row.observations_above_upper_envelope} / ${row.observations_below_lower_envelope}</td>
            <td>${row.successor_eligible_observation_count} / ${row.successor_minimum_required}</td>
            <td>${row.episodes_with_successor_candidate} / ${row.episodes_available}</td>
            <td>${row.successor_candidates.length ? row.successor_candidates.map((candidate) => `${formatNumber(candidate.lower)}–${formatNumber(candidate.upper)} / ${formatNumber(candidate.normalized_span, 6)}`).join("; ") : "—"}</td>
          </tr>`).join("")}</tbody>
      </table>
    </div>`;
}

function timingTable(timings) {
  const entries = Object.entries(timings);
  if (!entries.length) return "<p class=\"muted\">No post-activation confirmation timing is available.</p>";
  return `
    <div class="table-wrap">
      <table>
        <thead><tr><th>Candidate event</th><th>Episodes observed</th><th>Median observation</th><th>Median hours</th><th>Index distribution</th></tr></thead>
        <tbody>${entries.map(([name, timing]) => `<tr>
          <td>${escapeHtml(timingLabels[name] || titleCase(name))}</td>
          <td>${timing.episodes}</td>
          <td>${timing.median_observation_index == null ? "—" : `+${formatNumber(timing.median_observation_index, 1)}`}</td>
          <td>${formatNumber(timing.median_hours, 2)}</td>
          <td>${escapeHtml(Object.entries(timing.by_observation_index).map(([index, count]) => `+${index}: ${count}`).join(", "))}</td>
        </tr>`).join("")}</tbody>
      </table>
    </div>`;
}

function episodeTable(episodes) {
  if (!episodes.length) return "<p class=\"muted\">No reconstructable episodes in this cohort.</p>";
  return `
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Episode</th><th>Route / location</th><th>MRZ</th><th>Activated</th><th>Activation IPDA</th><th>Post observations</th>
          <th>First supportive</th><th>First adverse pressure</th><th>Terminal event</th><th>Actual direction</th>
          <th>Route-relative outcome</th><th>Status</th>
        </tr></thead>
        <tbody>${episodes.map((row) => `
          <tr>
            <td>${escapeHtml(row.symbol)} · G${row.generation}</td>
            <td>${escapeHtml(row.route)} · ${escapeHtml(titleCase(row.structural_location_at_activation))}</td>
            <td>${formatNumber(row.mrz_lower)}–${formatNumber(row.mrz_upper)}</td>
            <td>${escapeHtml(row.activated_at)}</td>
            <td>${formatNumber(row.ipda_20w_low_at_activation)}–${formatNumber(row.ipda_20w_high_at_activation)}</td>
            <td>${row.post_activation_observations}</td>
            <td>${row.first_supportive_observation == null ? "—" : `+${row.first_supportive_observation} / ${formatNumber(row.first_supportive_hours, 2)}h`}</td>
            <td>${row.first_adverse_pressure_observation == null ? "—" : `+${row.first_adverse_pressure_observation} / ${formatNumber(row.first_adverse_pressure_hours, 2)}h`}</td>
            <td>${escapeHtml(row.terminal_event)}</td>
            <td>${escapeHtml(row.migration_direction)}</td>
            <td><strong>${escapeHtml(row.route_relative_migration)}</strong><span class="table-subline">${escapeHtml(row.route_relative_meaning)}</span></td>
            <td><span class="episode-status ${row.status === "ONGOING" ? "ongoing" : "completed"}">${escapeHtml(row.status)}</span></td>
          </tr>`).join("")}</tbody>
      </table>
    </div>`;
}

function diagnosisPanel(diagnosis) {
  const insufficient = diagnosis.status === "Insufficient sample" ? " insufficient" : "";
  return `
    <div class="diagnosis-panel">
      <h4>Cohort Diagnosis</h4>
      <p class="status${insufficient}">${escapeHtml(diagnosis.status)}</p>
      <div class="diagnosis-grid">
        <div><p class="label">Activation alone</p><p>${escapeHtml(diagnosis.activation_alone)}</p></div>
        <div><p class="label">Confirmation effect</p><p>${escapeHtml(diagnosis.confirmation_effect)}</p></div>
        <div><p class="label">Candidate confirmation point</p><p>${escapeHtml(diagnosis.candidate_confirmation_point)}</p></div>
        <div><p class="label">Sample</p><p>${escapeHtml(diagnosis.sample_assessment)}</p></div>
      </div>
      <p class="label">Supporting evidence</p>${evidenceList(diagnosis.supportive_evidence)}
      <p class="label">Contradictory evidence</p>${evidenceList(diagnosis.contradictory_evidence)}
      <p class="label">Interpretation</p><p>${escapeHtml(diagnosis.interpretation)}</p>
      <p class="label">Limitations</p>${evidenceList(diagnosis.limitations)}
    </div>`;
}

function primaryOutcomePanel(primary) {
  return `
    <section class="subsection primary-outcome-card">
      <p class="section-kicker">PRIMARY OUTCOME</p>
      <h3>Continuation vs Reversal After Activation</h3>
      <p class="denominator-line">Observed completed outcome rate · <strong>${primary.completed_denominator} completed</strong></p>
      <div class="outcome-comparison">
        <article class="outcome-row continuation">
          <div><span>CONTINUATION</span><strong>${escapeHtml(primary.continuation_label)}</strong></div>
          <p><strong>${primary.continuation_count} / ${primary.completed_denominator}</strong><em>${formatPercent(primary.continuation_percentage)}</em></p>
        </article>
        <article class="outcome-row reversal">
          <div><span>REVERSAL</span><strong>${escapeHtml(primary.reversal_label)}</strong></div>
          <p><strong>${primary.reversal_count} / ${primary.completed_denominator}</strong><em>${formatPercent(primary.reversal_percentage)}</em></p>
        </article>
        <article class="outcome-row unresolved">
          <div><span>UNRESOLVED</span><strong>Ongoing MRZ generations</strong></div>
          <p><strong>${primary.unresolved_count}</strong><em>excluded</em></p>
        </article>
      </div>
      ${primary.other_terminal_count ? `<p class="definition">Other completed terminal outcomes: ${primary.other_terminal_count}. They remain in the completed denominator but are not forced into continuation or reversal.</p>` : ""}
      <p class="sample-qualification">${escapeHtml(primary.qualification)}</p>
      <p class="definition">${escapeHtml(primary.denominator_definition)}</p>
    </section>`;
}

function operatorInterpretationPanel(cohort) {
  const interpretation = cohort.operator_interpretation;
  return `
    <section class="subsection interpretation-card">
      <p class="section-kicker">OPERATOR INTERPRETATION</p>
      <div class="interpretation-grid">
        ${metric("Structural location", interpretation.structural_location)}
        ${metric("Strategy context", interpretation.strategy_context)}
        ${metric("Activation outcome bias", interpretation.activation_outcome_bias)}
        ${metric("Current evidence", interpretation.current_evidence)}
        ${metric("Confirmation effect", interpretation.confirmation_effect)}
        ${metric("Research status", interpretation.research_status)}
      </div>
      <p class="interpretation-summary">${escapeHtml(interpretation.summary)}</p>
      <p class="operator-guardrail">${escapeHtml(interpretation.guardrail)}</p>
      <details><summary>Supporting, contradictory, and limiting evidence</summary>${diagnosisPanel(cohort.diagnosis)}</details>
    </section>`;
}

function methodologyPanel(cohort, methodology) {
  return `
    <section class="subsection methodology-section">
      <p class="section-kicker">METHODOLOGY / DEFINITIONS</p>
      <details>
        <summary>Definitions, research assumptions, and production safeguards</summary>
        <dl class="methodology">${Object.entries(methodology).map(([key, value]) => `<dt>${escapeHtml(key.replaceAll("_", " "))}</dt><dd>${escapeHtml(value)}</dd>`).join("")}</dl>
        <dl class="identity-grid research-assumptions">
          ${metric("Initial prior", cohort.prior)}
          ${metric("Existing hypothesis", cohort.hypothesis)}
          ${metric("Research-only candidate", cohort.candidate)}
          ${metric("Production status", cohort.candidate_policy.production_status)}
        </dl>
      </details>
    </section>`;
}

function renderCohort(cohort, methodology) {
  const outcomes = cohort.completed_episode_outcomes;
  const candidate = cohort.candidate_confirmation_point;
  return `
    <section class="cohort-card">
      <header class="cohort-header">
        <p class="eyebrow">${escapeHtml(cohort.cohort)}</p>
        <h2>${escapeHtml(cohort.label)}</h2>
        <p class="strategy-context">${escapeHtml(cohort.strategy_context)}</p>
        <p class="research-question"><span>Research question</span>${escapeHtml(cohort.research_question)}</p>
        <dl class="summary-grid cohort-counts">
          ${metric("Episodes", cohort.episode_counts.total)}
          ${metric("Completed", cohort.episode_counts.completed)}
          ${metric("Ongoing", cohort.episode_counts.ongoing)}
          ${metric("Unique symbols", cohort.episode_counts.unique_symbols)}
        </dl>
        <span class="sample-state ${cohort.primary_outcome.sample_sufficient ? "sufficient" : "insufficient"}">${escapeHtml(cohort.primary_outcome.sample_state)}</span>
      </header>
      <div class="cohort-body">
        ${primaryOutcomePanel(cohort.primary_outcome)}
        ${operatorInterpretationPanel(cohort)}
        <section class="subsection">
          <p class="section-kicker">CONFIRMATION EFFECT</p>
          <h3>Does waiting after activation improve reversal clarity?</h3>
          <p class="definition">If activation alone does not establish a useful reversal bias, do later route-supportive observations materially clarify the eventual outcome?</p>
          <p class="checkpoint-definition"><strong>+N means the Nth authoritative post-activation observation — never bars.</strong> Intermediate behavior remains separate from final outcomes.</p>
          ${checkpointTable(cohort.checkpoints)}
        </section>
        <section class="subsection candidate-card">
          <p class="section-kicker">CANDIDATE CONFIRMATION POINT</p>
          <p class="candidate-value">${escapeHtml(candidate.status).toUpperCase()}</p>
          <p>${escapeHtml(candidate.confirmation_effect)}</p>
          <dl class="candidate-facts">
            ${metric("Evidence status", candidate.evidence_status)}
            ${metric("Production status", candidate.production_status)}
          </dl>
        </section>
        <section class="subsection">
          <p class="section-kicker">WHAT TENDS TO HAPPEN FIRST?</p>
          <h3>Post-activation event timing</h3>
          <p class="definition">Lifecycle timing only. These events describe intermediate behavior and do not resolve an ongoing episode.</p>
          ${timingTable(cohort.first_confirmation_timing)}
        </section>
        <section class="subsection final-outcomes">
          <p class="section-kicker">FINAL OUTCOMES</p>
          <h3>Completed MRZ generations only</h3>
          <p class="denominator-line"><strong>Completed episodes: ${outcomes.completed}</strong> · Ongoing / unresolved: ${outcomes.ongoing}</p>
          <dl class="outcome-grid">
            ${metric("Upward migrations", outcomes.migrated_upward)}
            ${metric("Downward migrations", outcomes.migrated_downward)}
            ${metric("Route changes / replacements", outcomes.route_changed_or_replaced)}
            ${metric("Route-supportive migrations", `${outcomes.route_supportive_migrations} / ${outcomes.completed}`)}
            ${metric("Route-adverse migrations", `${outcomes.route_adverse_migrations} / ${outcomes.completed}`)}
            ${metric("Median observations to migration", formatNumber(outcomes.median_observations_to_migration, 1))}
            ${metric("Median hours to termination", formatNumber(outcomes.median_hours_to_termination, 2))}
            ${metric("Median authoritative observations", formatNumber(outcomes.median_authoritative_observation_count, 1))}
          </dl>
          ${cohort.primary_outcome.sample_sufficient ? "" : `<p class="sample-qualification">Descriptive only — insufficient completed sample.</p>`}
        </section>
        <section class="subsection raw-episodes">
          <p class="section-kicker">RAW RECONSTRUCTED EPISODES</p>
          <h3>Generation-level audit layer</h3>
          <p class="definition">Each row is one MRZ generation. Intermediate pressure is shown independently from canonical terminal status.</p>
          ${episodeTable(cohort.episodes)}
        </section>
        ${methodologyPanel(cohort, methodology)}
      </div>
    </section>`;
}

function renderReport(report) {
  const reconstruction = report.reconstruction;
  const cross = report.cross_cohort_diagnosis;
  reportRoot.innerHTML = `
    <section class="report-section">
      <p class="flow">SAMPLE → DIAGNOSE → CANDIDATE POLICY</p>
      <h2>Episode reconstruction</h2>
      <dl class="summary-grid">
        ${metric("Total episodes", reconstruction.total_episodes)}
        ${metric("Completed", reconstruction.completed_episodes)}
        ${metric("Ongoing", reconstruction.ongoing_episodes)}
        ${metric("Excluded", reconstruction.excluded_episodes)}
      </dl>
      <p class="definition">Data as of ${escapeHtml(report.data_as_of)}. Audit match: ${reconstruction.event_history_matches_replay ? "yes" : "no"}. Active-state match: ${reconstruction.active_state_matches_replay ? "yes" : "no"}.</p>
    </section>
    ${report.cohorts.map((cohort) => renderCohort(cohort, report.methodology)).join("")}
    <section class="report-section">
      <h2>Cross-Cohort Diagnosis</h2>
      <p class="status${cross.status === "Insufficient sample" ? " insufficient" : ""}">${escapeHtml(cross.status)}</p>
      <div class="diagnosis-grid">
        <div><p class="label">BTD · Deep vs Shallow</p><p>${escapeHtml(cross.BTD.interpretation)}</p><p class="muted">Comparable checkpoint: ${escapeHtml(cross.BTD.shallow_comparable_checkpoint)}</p></div>
        <div><p class="label">STR · Deep vs Shallow</p><p>${escapeHtml(cross.STR.interpretation)}</p><p class="muted">Comparable checkpoint: ${escapeHtml(cross.STR.shallow_comparable_checkpoint)}</p></div>
      </div>
      <p class="label">Overall interpretation</p><p>${escapeHtml(cross.overall_interpretation)}</p>
    </section>
    <section class="report-section">
      <h2>Trading Window Research Diagnosis</h2>
      <div class="table-wrap"><table><thead><tr><th>Cohort</th><th>Hypothesis</th><th>Status</th><th>Candidate checkpoint</th></tr></thead>
      <tbody>${report.overall_diagnosis.cohorts.map((item) => `<tr><td>${escapeHtml(item.cohort)}</td><td>${escapeHtml(item.hypothesis)}</td><td>${escapeHtml(item.status)}</td><td>${escapeHtml(item.candidate_checkpoint)}</td></tr>`).join("")}</tbody></table></div>
      <p class="notice">Production recommendation: ${escapeHtml(report.overall_diagnosis.production_recommendation)}</p>
    </section>
    <section class="report-section">
      <h2>Data limitations and invariants</h2>
      <ul class="limitations">${report.data_limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      <p class="production-badge">${escapeHtml(report.invariants.production_status)}</p>
      <p class="definition">Schema ${escapeHtml(report.invariants.schema_version)} · Payload ${escapeHtml(report.invariants.payload_structure)} · MRZ engine ${escapeHtml(report.invariants.mrz_engine_behavior)} · Operation Card state ${escapeHtml(report.invariants.operation_card_trading_window_state)}</p>
    </section>`;
  loading.hidden = true;
  reportRoot.hidden = false;
}

async function loadReport() {
  refreshButton.disabled = true;
  loading.hidden = false;
  loading.querySelector("p").textContent = "Reconstructing MRZ activation episodes…";
  try {
    const response = await fetch("/api/diagnostics/trading-window-feasibility", { cache: "no-store" });
    if (!response.ok) throw new Error("Unable to build the feasibility report");
    renderReport(await response.json());
  } finally {
    refreshButton.disabled = false;
  }
}

refreshButton.addEventListener("click", () => {
  loadReport().catch((error) => {
    loading.querySelector("p").textContent = error.message;
  });
});

loadReport().catch((error) => {
  loading.querySelector("p").textContent = error.message;
});
