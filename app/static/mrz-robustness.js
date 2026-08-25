function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function priceText(value) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return number.toLocaleString("en-GB", { maximumFractionDigits: 8 });
}

function percentageText(value) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return `${number.toLocaleString("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function durationText(value) {
  if (value === null || value === undefined || value === "") return "—";
  const totalSeconds = Math.max(0, Math.floor(Number(value)));
  if (!Number.isFinite(totalSeconds)) return "—";
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  if (days) return `${days}d ${hours}h`;
  if (hours) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

function statusClass(status) {
  return String(status || "").toLowerCase().replaceAll("_", "-");
}

function directionText(direction, label = "Neutral") {
  if (direction === "UP") return `↑ ${label}`;
  if (direction === "DOWN") return `↓ ${label}`;
  return label || "Neutral";
}

function normalizedSpanText(value) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return percentageText(number * 100);
}

function titleWords(value) {
  return String(value || "—")
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (letter) => letter.toUpperCase());
}

function migrationProvenanceMarkup(migration, timestampFormatter = (value) => value) {
  if (!migration?.has_migrated) return "";
  const downward = migration.direction === "DOWN";
  const arrow = downward ? "↓" : "↑";
  const direction = downward ? "DOWNWARD" : "UPWARD";
  const previousRange = `${priceText(migration.previous_lower)} – ${priceText(migration.previous_upper)}`;
  const currentRange = `${priceText(migration.current_lower)} – ${priceText(migration.current_upper)}`;
  return `<aside class="migration-provenance" aria-label="Current MRZ migration provenance">
    <div class="migration-provenance-heading">
      <span class="section-label">CURRENT MRZ PROVENANCE</span>
      <strong>${arrow} MIGRATED ${direction}</strong>
      <span class="migration-provenance-time">${escapeHtml(timestampFormatter(migration.migrated_at) || "—")}</span>
    </div>
    <dl>
      <div><dt>Previous</dt><dd>${previousRange}</dd></div>
      <div><dt>Current</dt><dd>${currentRange}</dd></div>
    </dl>
  </aside>`;
}

function robustnessCardMarkup(report, timestampFormatter = (value) => value) {
  const authority = report.structural_authority;
  const active = report.active_mrz;
  const formation = report.formation_evidence;
  const robustness = report.robustness_evidence;
  const behavior = report.post_activation_robustness;
  const containment = report.containment;
  const boundary = report.boundary_pressure;
  const midpointDistance = report.distance_from_mrz_midpoint;
  const route = report.route_integrity;
  const pressure = report.migration_pressure;
  const successor = report.successor_watch;
  const age = report.mrz_age;
  const summary = report.structural_summary;
  const candidateRange = successor.candidate_lower !== null
    ? `${priceText(successor.candidate_lower)} – ${priceText(successor.candidate_upper)}`
    : "—";
  const successorIdentity = successor.symbol
    ? `${escapeHtml(successor.symbol)} · ${escapeHtml(successor.route)}`
    : "None";
  const successorDirection = successor.direction
    ? directionText(successor.direction, successor.direction_label)
    : "None";
  const relevantBoundary = pressure.relevant_boundary_label
    ? `<dt>${escapeHtml(pressure.relevant_boundary_label)}</dt><dd>${priceText(pressure.relevant_boundary)}</dd>`
    : "<dt>Relevant boundary</dt><dd>—</dd>";
  return `<section class="mrz-report" data-symbol="${escapeHtml(report.symbol)}">
    <section class="operation-section structural-authority" aria-label="Structural Authority">
      <div class="mrz-heading">
        <div>
          <span class="section-label">1 · STRUCTURAL AUTHORITY</span>
          <h2>${escapeHtml(report.symbol)} · ${escapeHtml(report.route_owner)}</h2>
          <p class="structural-location">${escapeHtml(authority.structural_location_label)}</p>
        </div>
        <strong class="status-pill authoritative">${escapeHtml(authority.label)}</strong>
      </div>
      <div class="authority-grid">
        <article class="authority-range"><span>ACTIVE MRZ</span><strong>${priceText(active.lower)} – ${priceText(active.upper)}</strong></article>
        <article><span>MIDPOINT</span><strong>${priceText(active.midpoint)}</strong></article>
        <article><span>AUTHORITY</span><strong>${escapeHtml(authority.label)}</strong></article>
        <article><span>STRUCTURAL ROLE</span><strong>${escapeHtml(authority.structural_role_label)}</strong></article>
        <article><span>ACTIVATED</span><strong>${escapeHtml(timestampFormatter(active.activated_at) || "—")}</strong></article>
        <article><span>MRZ AGE</span><strong>${durationText(age.active_duration_seconds)}</strong></article>
      </div>
      ${migrationProvenanceMarkup(report.migration, timestampFormatter)}
    </section>

    <section class="operation-section robustness-section" aria-label="Post-Activation Robustness">
      <div class="operation-section-heading"><span class="section-label">2 · POST-ACTIVATION ROBUSTNESS</span></div>
      <div class="robustness-panel ${statusClass(behavior.status)}">
        <strong class="robustness-state">${escapeHtml(behavior.label)}</strong>
        <span>${behavior.post_activation_observation_count} post-activation observations</span>
        <p>${escapeHtml(behavior.reason)}</p>
      </div>
    </section>

    <section class="operation-section evidence-section" aria-label="Evidence">
      <div class="operation-section-heading"><span class="section-label">3 · EVIDENCE</span></div>
      <div class="evidence-split">
        <article><span class="section-label">FORMATION</span><strong>${formation.confirming_observation_count} qualifying observations</strong><p>${escapeHtml(formation.meaning)}</p></article>
        <article><span class="section-label">POST-ACTIVATION SAMPLE</span><strong>${robustness.post_activation_observation_count} observations</strong><p>${escapeHtml(robustness.meaning)}</p></article>
      </div>
      <div class="evidence-grid">
      <article class="metric-card">
        <h3>Containment</h3>
        <strong class="metric-primary">${containment.inside_observation_count} / ${containment.total_observation_count}</strong>
        <span class="metric-secondary">inside active MRZ</span>
        <p class="metric-note">${percentageText(containment.percentage)} of the post-activation sample.</p>
      </article>
      <article class="metric-card">
        <h3>Boundary Behavior</h3>
        <dl><div><dt>Upper tests</dt><dd>${boundary.upper_boundary_test_count}</dd></div><div><dt>Lower tests</dt><dd>${boundary.lower_boundary_test_count}</dd></div></dl>
        <p class="metric-note">Tests are at or beyond the frozen core boundaries.</p>
      </article>
      <article class="metric-card">
        <h3>Envelope</h3>
        <strong class="metric-primary">${boundary.outside_envelope_observation_count}</strong>
        <span class="metric-secondary">outside envelope</span>
        <dl><div><dt>Above upper</dt><dd>${boundary.above_upper_envelope_observation_count}</dd></div><div><dt>Below lower</dt><dd>${boundary.below_lower_envelope_observation_count}</dd></div></dl>
      </article>
      <article class="metric-card">
        <h3>Route Integrity</h3>
        <strong class="metric-primary compact">${route.route_aligned_observation_count} / ${route.total_observation_count}</strong>
        <span class="metric-secondary">route aligned</span>
        <dl><div><dt>Structurally aligned</dt><dd>${route.structurally_aligned_observation_count}</dd></div></dl>
        <p class="metric-note">${escapeHtml(route.label)}</p>
      </article>
      <article class="metric-card">
        <h3>Distance From MRZ Midpoint</h3>
        <strong class="metric-primary">${percentageText(midpointDistance.median_distance_percentage_of_activation_ipda)}</strong>
        <span class="metric-secondary">Median distance</span>
        <p class="metric-note">${escapeHtml(midpointDistance.normalization)}</p>
      </article>
      </div>
    </section>

    <section class="operation-section pressure-section" aria-label="Migration Pressure">
      <div class="operation-section-heading"><span class="section-label">4 · MIGRATION PRESSURE</span></div>
      <div class="detail-card pressure ${statusClass(pressure.status)}">
        <div class="detail-status"><span>DIRECTION</span><strong class="direction-value">${escapeHtml(directionText(pressure.direction, pressure.direction_label))}</strong></div>
        <div class="detail-status"><span>STATUS</span><strong>${escapeHtml(pressure.label)}</strong></div>
        <dl class="detail-grid">
          <div>${relevantBoundary}</div>
          <div><dt>Observations beyond envelope</dt><dd>${pressure.observations_beyond_envelope}</dd></div>
          <div><dt>Above upper envelope</dt><dd>${pressure.above_upper_envelope_observation_count}</dd></div>
          <div><dt>Below lower envelope</dt><dd>${pressure.below_lower_envelope_observation_count}</dd></div>
          <div><dt>Current MRZ</dt><dd>Still authoritative</dd></div>
        </dl>
        <p>${escapeHtml(pressure.reason)}</p>
      </div>
    </section>

    <section class="operation-section successor-section" aria-label="Successor Watch">
      <div class="operation-section-heading"><span class="section-label">5 · SUCCESSOR WATCH</span></div>
      <div class="detail-card successor">
        <div class="detail-status"><span>STATUS</span><strong>${escapeHtml(successor.label)}</strong></div>
        <dl class="detail-grid">
          <div><dt>Direction</dt><dd>${escapeHtml(successorDirection)}</dd></div>
          <div><dt>Candidate</dt><dd>${successorIdentity}</dd></div>
          <div><dt>Candidate range</dt><dd>${candidateRange}</dd></div>
          <div><dt>Eligible observations</dt><dd>${successor.evidence_observation_count} / ${successor.required_observation_count}</dd></div>
          <div><dt>Normalized span</dt><dd>${normalizedSpanText(successor.normalized_span)}</dd></div>
          <div><dt>Production check</dt><dd>${escapeHtml(titleWords(successor.production_evaluation_result))}</dd></div>
        </dl>
        <p>Diagnostic only. Successor confirmation remains controlled by the production evaluator and MRZ engine.</p>
      </div>
    </section>

    <section class="operation-section structural-summary" aria-label="Structural Summary">
      <div class="operation-section-heading"><span class="section-label">6 · STRUCTURAL SUMMARY</span></div>
      <dl class="summary-grid">
        <div><dt>Current authority</dt><dd>${escapeHtml(summary.current_authority)}</dd></div>
        <div><dt>Robustness</dt><dd>${escapeHtml(summary.robustness_label)}</dd></div>
        <div><dt>Pressure</dt><dd>${escapeHtml(directionText(summary.pressure_direction, summary.pressure_direction_label))}</dd></div>
        <div><dt>Structural role</dt><dd>${escapeHtml(summary.structural_role_label)}</dd></div>
        <div><dt>Successor</dt><dd>${escapeHtml(summary.successor_label)}</dd></div>
      </dl>
      <p class="summary-authority">${escapeHtml(summary.authority_statement)}</p>
      <p>${escapeHtml(summary.detail_statement)}</p>
    </section>
  </section>`;
}

function reportMarkup(reports, timestampFormatter = (value) => value) {
  if (!reports.length) {
    return '<section class="empty-report">No active MRZ is available for an operation card.</section>';
  }
  return reports.map((report) => robustnessCardMarkup(report, timestampFormatter)).join("");
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    const refreshButton = document.getElementById("refreshReport");
    const status = document.getElementById("reportStatus");
    const content = document.getElementById("reportContent");

    async function loadReport() {
      refreshButton.disabled = true;
      status.hidden = false;
      status.classList.remove("error");
      status.textContent = "Calculating the latest report…";
      content.hidden = true;
      try {
        const response = await fetch("/api/diagnostics/mrz-robustness", { cache: "no-store" });
        if (!response.ok) throw new Error(`Report request failed (${response.status})`);
        const report = await response.json();
        document.getElementById("generatedAt").textContent = formatOperatorTimestampUtcMinus4(report.generated_at) || "—";
        document.getElementById("activeMrzCount").textContent = report.active_mrz_count;
        document.getElementById("activeReports").innerHTML = reportMarkup(report.active_mrzs, formatOperatorTimestampUtcMinus4);
        status.hidden = true;
        content.hidden = false;
      } catch (error) {
        status.classList.add("error");
        status.textContent = `Unable to generate the report. ${error.message}`;
      } finally {
        refreshButton.disabled = false;
      }
    }

    refreshButton.addEventListener("click", loadReport);
    loadReport();
  });
}

if (typeof module === "object" && module.exports) {
  module.exports = {
    durationText,
    directionText,
    migrationProvenanceMarkup,
    normalizedSpanText,
    percentageText,
    reportMarkup,
    robustnessCardMarkup,
  };
}
