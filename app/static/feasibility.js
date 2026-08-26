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

const metric = (label, value) => `
  <div><dt>${escapeHtml(label)}</dt><dd class="metric-value">${escapeHtml(value)}</dd></div>`;

const evidenceList = (items) => `<ul class="evidence-list">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;

const titleCase = (value) => value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());

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
          <td>${escapeHtml(titleCase(name))}</td>
          <td>${timing.episodes}</td>
          <td>${formatNumber(timing.median_observation_index, 1)}</td>
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
          <th>Episode</th><th>Activated</th><th>MRZ</th><th>Activation IPDA</th><th>Post observations</th>
          <th>Outcome</th><th>Actual direction</th><th>Route-relative</th><th>First adverse pressure</th>
        </tr></thead>
        <tbody>${episodes.map((row) => `
          <tr>
            <td>${escapeHtml(row.symbol)} · G${row.generation}</td>
            <td>${escapeHtml(row.activated_at)}</td>
            <td>${formatNumber(row.mrz_lower)}–${formatNumber(row.mrz_upper)}</td>
            <td>${formatNumber(row.ipda_20w_low_at_activation)}–${formatNumber(row.ipda_20w_high_at_activation)}</td>
            <td>${row.post_activation_observations}</td>
            <td>${escapeHtml(row.outcome)}</td>
            <td>${escapeHtml(row.migration_direction)}</td>
            <td>${escapeHtml(row.route_relative_migration)}</td>
            <td>${row.first_adverse_pressure_observation == null ? "—" : `+${row.first_adverse_pressure_observation} / ${formatNumber(row.first_adverse_pressure_hours, 2)}h`}</td>
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

function policyPanel(policy) {
  return `
    <div class="policy-panel">
      <h4>Candidate Trading Window Policy</h4>
      <dl class="policy-grid">
        ${metric("Strategy context", policy.strategy_context)}
        ${metric("Candidate", policy.candidate)}
        ${metric("Candidate checkpoint", policy.candidate_checkpoint)}
        ${metric("Evidence status", policy.evidence_status)}
        ${metric("Production status", policy.production_status)}
      </dl>
    </div>`;
}

function renderCohort(cohort) {
  const outcomes = cohort.completed_episode_outcomes;
  return `
    <section class="cohort-card">
      <header class="cohort-header">
        <p class="eyebrow">${escapeHtml(cohort.cohort)}</p>
        <h2>${escapeHtml(cohort.label)}</h2>
        <p class="muted">${escapeHtml(cohort.hypothesis)}</p>
      </header>
      <div class="cohort-body">
        <section class="subsection">
          <h3>1. Cohort identity and hypothesis</h3>
          <dl class="identity-grid">
            ${metric("Route", cohort.route)}
            ${metric("Structural location", cohort.location)}
            ${metric("Initial prior", cohort.prior)}
            ${metric("Strategy context", cohort.strategy_context)}
            ${metric("Candidate hypothesis", cohort.candidate)}
          </dl>
        </section>
        <section class="subsection">
          <h3>2. Episode counts</h3>
          <dl class="summary-grid">
            ${metric("Total", cohort.episode_counts.total)}
            ${metric("Completed", cohort.episode_counts.completed)}
            ${metric("Ongoing", cohort.episode_counts.ongoing)}
            ${metric("Sampling unit", "MRZ generation")}
          </dl>
        </section>
        <section class="subsection">
          <h3>3–5. Checkpoint sampling and structural measurements</h3>
          <p class="definition">Signed displacement preserves raw above/below-midpoint direction and mirrors route-relative support for STR. Every fraction retains its episode denominator.</p>
          ${checkpointTable(cohort.checkpoints)}
          <details><summary>First-confirmation timing</summary>${timingTable(cohort.first_confirmation_timing)}</details>
        </section>
        <section class="subsection">
          <h3>6. Completed episode outcomes</h3>
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
          <details><summary>Raw reconstructed episodes</summary>${episodeTable(cohort.episodes)}</details>
        </section>
        <section class="subsection">${diagnosisPanel(cohort.diagnosis)}</section>
        <section class="subsection">${policyPanel(cohort.candidate_policy)}</section>
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
      <details><summary>Measurement and diagnosis methodology</summary>
        <dl class="methodology">${Object.entries(report.methodology).map(([key, value]) => `<dt>${escapeHtml(key.replaceAll("_", " "))}</dt><dd>${escapeHtml(value)}</dd>`).join("")}</dl>
      </details>
    </section>
    ${report.cohorts.map(renderCohort).join("")}
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
