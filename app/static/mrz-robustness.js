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
  const active = report.active_mrz;
  const formation = report.formation_evidence;
  const robustness = report.robustness_evidence;
  const containment = report.containment;
  const boundary = report.boundary_pressure;
  const midpoint = report.midpoint_stability;
  const route = report.route_integrity;
  const pressure = report.migration_pressure;
  const successor = report.successor_watch;
  const age = report.mrz_age;
  const classification = report.robustness_classification;
  const candidateRange = successor.candidate_lower !== null
    ? `${priceText(successor.candidate_lower)} – ${priceText(successor.candidate_upper)}`
    : "—";
  const successorIdentity = successor.symbol
    ? `${escapeHtml(successor.symbol)} · ${escapeHtml(successor.route)}`
    : "—";
  const reasons = (classification.reasons || []).map((reason) => `<li>${escapeHtml(reason)}</li>`).join("");
  return `<section class="mrz-report" data-symbol="${escapeHtml(report.symbol)}">
    <div class="mrz-heading">
      <div><span class="section-label">ACTIVE STRUCTURAL AUTHORITY</span><h2>${escapeHtml(report.symbol)} · ${escapeHtml(report.route_owner)}</h2></div>
      <strong class="status-pill ${statusClass(classification.status)}">${escapeHtml(classification.label)}</strong>
    </div>
    <div class="active-hero">
      <article><span>ACTIVE MRZ</span><strong class="active-range">${priceText(active.lower)} – ${priceText(active.upper)}</strong></article>
      <article><span>MIDPOINT</span><strong>${priceText(active.midpoint)}</strong></article>
      <article><span>ACTIVATED</span><strong>${escapeHtml(timestampFormatter(active.activated_at) || "—")}</strong></article>
      <article><span>MRZ AGE</span><strong>${durationText(age.active_duration_seconds)}</strong></article>
    </div>
    ${migrationProvenanceMarkup(report.migration, timestampFormatter)}
    <div class="evidence-split">
      <article><span class="section-label">FORMATION EVIDENCE</span><strong>${formation.confirming_observation_count} qualifying observations</strong><p>${escapeHtml(formation.meaning)}</p></article>
      <article><span class="section-label">ROBUSTNESS EVIDENCE</span><strong>${robustness.post_activation_observation_count} post-activation observations</strong><p>${escapeHtml(robustness.meaning)}</p></article>
    </div>
    <div class="metric-grid">
      <article class="metric-card">
        <h3>MRZ Containment</h3>
        <strong class="metric-primary">${containment.inside_observation_count} / ${containment.total_observation_count}</strong>
        <span class="metric-secondary">${percentageText(containment.percentage)}</span>
        <p class="metric-note">Post-activation observations inside the frozen MRZ bounds.</p>
      </article>
      <article class="metric-card">
        <h3>Boundary Pressure</h3>
        <dl><div><dt>Upper boundary tests</dt><dd>${boundary.upper_boundary_test_count}</dd></div><div><dt>Lower boundary tests</dt><dd>${boundary.lower_boundary_test_count}</dd></div><div><dt>Outside envelope</dt><dd>${boundary.outside_envelope_observation_count}</dd></div></dl>
        <p class="metric-note">${escapeHtml(boundary.definition)}</p>
      </article>
      <article class="metric-card">
        <h3>Midpoint Stability</h3>
        <strong class="metric-primary">${percentageText(midpoint.median_distance_percentage_of_activation_ipda)}</strong>
        <span class="metric-secondary">Median distance</span>
        <p class="metric-note">${escapeHtml(midpoint.normalization)}</p>
      </article>
      <article class="metric-card">
        <h3>Route Integrity</h3>
        <strong class="metric-primary">${escapeHtml(route.label)}</strong>
        <dl><div><dt>Route aligned</dt><dd>${route.route_aligned_observation_count} / ${route.total_observation_count}</dd></div><div><dt>Structurally aligned</dt><dd>${route.structurally_aligned_observation_count}</dd></div></dl>
      </article>
    </div>
    <div class="monitoring-grid">
      <article class="monitoring-card pressure">
        <span class="section-label">MIGRATION PRESSURE</span>
        <strong class="monitoring-status">${escapeHtml(pressure.label)}</strong>
        <p>${escapeHtml(pressure.reason)}</p>
        <p class="authority-note">Current MRZ remains authoritative.</p>
      </article>
      <article class="monitoring-card successor">
        <span class="section-label">SUCCESSOR WATCH</span>
        <strong class="monitoring-status">${escapeHtml(successor.label)}</strong>
        <dl><div><dt>Candidate</dt><dd>${successorIdentity}</dd></div><div><dt>Candidate range</dt><dd>${candidateRange}</dd></div><div><dt>Evidence</dt><dd>${successor.evidence_observation_count} / ${successor.required_observation_count} observations</dd></div><div><dt>Production check</dt><dd>${escapeHtml(successor.production_evaluation_result.replaceAll("_", " "))}</dd></div></dl>
        <p class="authority-note">Diagnostic only. Migration remains controlled by the MRZ engine.</p>
      </article>
    </div>
    <article class="classification">
      <span class="section-label">MRZ STATUS</span>
      <h3>Post-activation structural summary</h3>
      <strong>${escapeHtml(classification.label)}</strong>
      <ul>${reasons}</ul>
    </article>
  </section>`;
}

function reportMarkup(reports, timestampFormatter = (value) => value) {
  if (!reports.length) {
    return '<section class="empty-report">No active MRZ is available for post-activation robustness monitoring.</section>';
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
    migrationProvenanceMarkup,
    percentageText,
    reportMarkup,
    robustnessCardMarkup,
  };
}
