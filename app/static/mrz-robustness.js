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

function midpointValue(lower, upper) {
  if (lower === null || lower === undefined || lower === ""
    || upper === null || upper === undefined || upper === "") return null;
  const lowerNumber = Number(lower);
  const upperNumber = Number(upper);
  if (!Number.isFinite(lowerNumber) || !Number.isFinite(upperNumber)) return null;
  return (lowerNumber + upperNumber) / 2;
}

function migrationEqmValue(migration, currentMidpoint) {
  const previousMidpoint = midpointValue(
    migration?.previous_lower,
    migration?.previous_upper,
  );
  if (currentMidpoint === null || currentMidpoint === undefined || currentMidpoint === "") {
    return null;
  }
  const currentMidpointNumber = Number(currentMidpoint);
  if (previousMidpoint === null || !Number.isFinite(currentMidpointNumber)) return null;
  return (previousMidpoint + currentMidpointNumber) / 2;
}

function hasValidMigrationProvenance(report) {
  const migration = report?.migration;
  if (migration?.has_migrated !== true) return false;
  if ([
    migration.previous_lower,
    migration.previous_upper,
    migration.current_lower,
    migration.current_upper,
  ].some((value) => value === null || value === undefined || value === "")) return false;
  const previousLower = Number(migration.previous_lower);
  const previousUpper = Number(migration.previous_upper);
  const currentLower = Number(migration.current_lower);
  const currentUpper = Number(migration.current_upper);
  return [previousLower, previousUpper, currentLower, currentUpper].every(Number.isFinite)
    && previousLower <= previousUpper
    && currentLower <= currentUpper;
}

function filterReports(reports, filterMode = "all") {
  if (filterMode !== "migrated") return [...reports];
  return reports.filter((report) => hasValidMigrationProvenance(report));
}

function percentageText(value) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return `${number.toLocaleString("en-GB", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function displacementText(value, direction) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  if (direction === "ABOVE") return `↑ +${percentageText(Math.abs(number))}`;
  if (direction === "BELOW") return `↓ -${percentageText(Math.abs(number))}`;
  if (direction === "CENTERED") return percentageText(0);
  return percentageText(number);
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

function successorDetailsMarkup(successor) {
  const higherExternal = successor.higher_external_observation_count ?? 0;
  const lowerExternal = successor.lower_external_observation_count ?? 0;
  const externalCounts = `
    <div><dt>Higher external</dt><dd>${higherExternal}</dd></div>
    <div><dt>Lower external</dt><dd>${lowerExternal}</dd></div>`;

  if (successor.status === "SUCCESSOR_CANDIDATE") {
    const candidateRange = successor.candidate_lower !== null
      ? `${priceText(successor.candidate_lower)} – ${priceText(successor.candidate_upper)}`
      : "—";
    return `${externalCounts}
      <div><dt>Side</dt><dd>${escapeHtml(directionText(successor.direction, successor.direction_label))}</dd></div>
      <div><dt>Route</dt><dd>${escapeHtml(successor.route || "—")}</dd></div>
      <div><dt>Candidate range</dt><dd>${candidateRange}</dd></div>
      <div><dt>Evidence</dt><dd>${successor.evidence_observation_count} observations</dd></div>
      <div><dt>Normalized span</dt><dd>${normalizedSpanText(successor.normalized_span)}</dd></div>
      <div><dt>Production allowance</dt><dd>${normalizedSpanText(successor.production_allowance)}</dd></div>
      <div><dt>Concentration</dt><dd>${escapeHtml(titleWords(successor.production_evaluation_result))}</dd></div>
      <div><dt>Candidate rule eligibility</dt><dd>${escapeHtml(successor.operational_migration_eligibility_label)}</dd></div>`;
  }

  if (successor.status === "NO_QUALIFYING_SUCCESSOR") {
    return `${externalCounts}
      <div><dt>Observation count</dt><dd>${successor.evidence_observation_count}</dd></div>
      <div><dt>Concentration</dt><dd>${normalizedSpanText(successor.normalized_span)}</dd></div>
      <div><dt>Production allowance</dt><dd>${normalizedSpanText(successor.production_allowance)}</dd></div>
      <div><dt>Result</dt><dd>${escapeHtml(titleWords(successor.production_evaluation_result))}</dd></div>`;
  }

  return `${externalCounts}
    <div><dt>Minimum evidence</dt><dd>${successor.required_observation_count} observations</dd></div>
    <div><dt>Concentration</dt><dd>${escapeHtml(titleWords(successor.production_evaluation_result))}</dd></div>`;
}

function migrationProvenanceMarkup(
  migration,
  currentState = {},
  timestampFormatter = (value) => value,
) {
  if (!migration?.has_migrated) return "";
  const downward = migration.direction === "DOWN";
  const arrow = downward ? "↓" : "↑";
  const direction = downward ? "DOWNWARD" : "UPWARD";
  const previousRange = `${priceText(migration.previous_lower)} – ${priceText(migration.previous_upper)}`;
  const currentRange = `${priceText(migration.current_lower)} – ${priceText(migration.current_upper)}`;
  const previousMidpoint = midpointValue(migration.previous_lower, migration.previous_upper);
  const currentMidpoint = currentState.currentMidpoint;
  const migrationEqm = migrationEqmValue(migration, currentMidpoint);
  return `<aside class="migration-provenance" aria-label="Current MRZ migration provenance">
    <div class="migration-provenance-heading">
      <div>
        <span class="section-label">CURRENT MRZ PROVENANCE</span>
        <strong>${arrow} MIGRATED ${direction}</strong>
      </div>
      <span class="migration-provenance-time">${escapeHtml(timestampFormatter(migration.migrated_at) || "—")}</span>
    </div>
    <div class="migration-pair-grid">
      <section class="migration-zone previous-zone" aria-label="Previous MRZ">
        <span>PREVIOUS MRZ</span>
        <strong>${previousRange}</strong>
        <small>Midpoint ${priceText(previousMidpoint)}</small>
      </section>
      <div class="migration-eqm">
        <span>MIGRATION EQM</span>
        <strong>${priceText(migrationEqm)}</strong>
      </div>
      <section class="migration-zone current-zone" aria-label="Current MRZ">
        <span>CURRENT MRZ</span>
        <strong>${currentRange}</strong>
        <small>Midpoint ${priceText(currentMidpoint)}</small>
      </section>
    </div>
    <div class="post-migration-state" aria-label="Post-migration state">
      <span class="section-label">POST-MIGRATION</span>
      <dl>
        <div><dt>Pressure</dt><dd>${escapeHtml(currentState.pressureLabel || "—")}</dd></div>
        <div><dt>Successor</dt><dd>${escapeHtml(currentState.successorLabel || "—")}</dd></div>
      </dl>
    </div>
  </aside>`;
}

function disclosureMarkup(section, title, synopsis, content) {
  return `<details class="operator-disclosure ${escapeHtml(section)}-disclosure" data-section="${escapeHtml(section)}">
    <summary>
      <span class="disclosure-title">${escapeHtml(title)}</span>
      <span class="disclosure-synopsis">${escapeHtml(synopsis)}</span>
      <span class="disclosure-chevron" aria-hidden="true"></span>
    </summary>
    <div class="disclosure-content">${content}</div>
  </details>`;
}

function robustnessCardMarkup(report, timestampFormatter = (value) => value) {
  const authority = report.structural_authority;
  const active = report.active_mrz;
  const formation = report.formation_evidence;
  const robustness = report.robustness_evidence;
  const behavior = report.post_activation_robustness;
  const position = report.observation_position;
  const boundary = report.boundary_pressure;
  const displacement = report.mrz_displacement;
  const pressure = report.migration_pressure;
  const successor = report.successor_watch;
  const age = report.mrz_age;
  const structuralSummary = report.structural_summary;
  const qualifyingObservationName = report.route_owner === "BTD" ? "reclaim" : "rejection";
  const firstQualifyingLabel = `First qualifying ${qualifyingObservationName}`;
  const formationStartedAt = timestampFormatter(formation.started_at) || "Unavailable";
  const formationDuration = formation.duration_seconds === null
    || formation.duration_seconds === undefined
    || formation.duration_seconds === ""
    ? "Unavailable"
    : durationText(formation.duration_seconds);
  const activeTimestamp = timestampFormatter(active.activated_at) || "—";
  const activeDuration = durationText(age.active_duration_seconds);
  const pressureDirection = directionText(pressure.direction, pressure.direction_label);
  const pressureSummary = pressure.direction === "NEUTRAL"
    ? pressure.label
    : `${pressure.label} · ${pressureDirection}`;
  const migrationSummary = report.migration?.has_migrated
    ? `Migrated ${String(report.migration.direction || "").toLowerCase()} · ${pressureSummary}`
    : `No recorded migration · ${pressureSummary}`;
  const relevantBoundary = pressure.relevant_boundary_label
    ? `<dt>${escapeHtml(pressure.relevant_boundary_label)}</dt><dd>${priceText(pressure.relevant_boundary)}</dd>`
    : "<dt>Relevant boundary</dt><dd>—</dd>";

  const postActivationContent = `<div class="robustness-panel ${statusClass(behavior.status)}">
    <strong class="robustness-state">${escapeHtml(behavior.label)}</strong>
    <span>${behavior.post_activation_observation_count} post-activation observations</span>
    <p>${escapeHtml(behavior.reason)}</p>
  </div>
  <div class="evidence-grid">
    <article class="metric-card">
      <h3>Observation Position</h3>
      <dl>
        <div><dt>Above MRZ</dt><dd>${position.above_active_mrz_observation_count}</dd></div>
        <div><dt>Inside MRZ</dt><dd>${position.inside_active_mrz_observation_count}</dd></div>
        <div><dt>Below MRZ</dt><dd>${position.below_active_mrz_observation_count}</dd></div>
      </dl>
      <p class="metric-note">Relative to the frozen active MRZ bounds.</p>
    </article>
    <article class="metric-card">
      <h3>Migration Envelope</h3>
      <strong class="metric-primary">${boundary.outside_envelope_observation_count}</strong>
      <span class="metric-secondary">outside envelope</span>
      <dl><div><dt>Above envelope</dt><dd>${boundary.above_upper_envelope_observation_count}</dd></div><div><dt>Below envelope</dt><dd>${boundary.below_lower_envelope_observation_count}</dd></div></dl>
    </article>
    <article class="metric-card">
      <h3>MRZ Displacement</h3>
      <strong class="metric-primary">${escapeHtml(displacementText(displacement.median_signed_displacement_percentage_of_activation_ipda, displacement.direction))}</strong>
      <span class="metric-secondary">${escapeHtml(displacement.label)}</span>
      <p class="metric-note">${escapeHtml(displacement.normalization)}</p>
    </article>
  </div>`;

  const successorContent = `<div class="detail-card successor ${statusClass(successor.status)}">
    <div class="detail-status"><span>STATUS</span><strong>${escapeHtml(successor.label)}</strong></div>
    <dl class="detail-grid">
      ${successorDetailsMarkup(successor)}
    </dl>
    <p>${escapeHtml(successor.reason)}</p>
  </div>`;

  const migrationContent = `${migrationProvenanceMarkup(
    report.migration,
    {
      currentMidpoint: active.midpoint,
      pressureLabel: pressureSummary,
      successorLabel: successor.label,
    },
    timestampFormatter,
  )}
    <div class="detail-card pressure ${statusClass(pressure.status)}">
      <div class="detail-status"><span>DIRECTION</span><strong class="direction-value">${escapeHtml(pressureDirection)}</strong></div>
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
    <div class="structural-summary" aria-label="Structural Summary">
      <dl class="summary-grid">
        <div><dt>Current authority</dt><dd>${escapeHtml(structuralSummary.current_authority)}</dd></div>
        <div><dt>Robustness</dt><dd>${escapeHtml(structuralSummary.robustness_label)}</dd></div>
        <div><dt>Pressure</dt><dd>${escapeHtml(directionText(structuralSummary.pressure_direction, structuralSummary.pressure_direction_label))}</dd></div>
        <div><dt>Successor</dt><dd>${escapeHtml(structuralSummary.successor_label)}</dd></div>
      </dl>
      <p class="summary-authority">${escapeHtml(structuralSummary.authority_statement)}</p>
      <p>${escapeHtml(structuralSummary.displacement_statement)}</p>
      <p>${escapeHtml(structuralSummary.detail_statement)}</p>
    </div>`;

  return `<section class="mrz-report" data-symbol="${escapeHtml(report.symbol)}">
    <header class="compact-authority" aria-label="Current structural authority">
      <section class="compact-group structure-group" aria-label="Structure">
        <span class="section-label">STRUCTURE</span>
        <div class="mrz-heading">
          <div>
            <h2>${escapeHtml(report.symbol)} · ${escapeHtml(report.route_owner)}</h2>
            <p class="structural-location">${escapeHtml(authority.structural_location_label)}</p>
          </div>
          <strong class="status-pill authoritative">${escapeHtml(authority.label)}</strong>
        </div>
        <div class="current-mrz">
          <span>CURRENT AUTHORITATIVE MRZ</span>
          <strong>${priceText(active.lower)} – ${priceText(active.upper)}</strong>
        </div>
      </section>

      <section class="compact-group formation-group" aria-label="Formation">
        <span class="section-label">FORMATION</span>
        <dl class="compact-facts formation-facts">
          <div><dt>${escapeHtml(firstQualifyingLabel)}</dt><dd>${escapeHtml(formationStartedAt)}</dd></div>
          <div><dt>Activated</dt><dd>${escapeHtml(activeTimestamp)}</dd></div>
          <div class="formation-duration"><dt>Formation duration</dt><dd>${escapeHtml(formationDuration)}</dd></div>
          <div><dt>MRZ age</dt><dd>${escapeHtml(activeDuration)}</dd></div>
        </dl>
      </section>

      <section class="compact-group post-activation-group" aria-label="Post-activation state">
        <span class="section-label">POST-ACTIVATION STATE</span>
        <dl class="compact-facts post-activation-facts">
          <div class="${statusClass(pressure.status)}"><dt>Pressure</dt><dd>${escapeHtml(pressureSummary)}</dd></div>
          <div class="${statusClass(successor.status)}"><dt>Successor</dt><dd>${escapeHtml(successor.label)}</dd></div>
        </dl>
      </section>
    </header>

    <div class="operator-disclosures">
      ${disclosureMarkup(
    "post-activation",
    "Post-activation observations",
    `${behavior.label} · ${robustness.post_activation_observation_count} observations`,
    postActivationContent,
  )}
      ${disclosureMarkup(
    "successor-watch",
    "Successor Watch",
    successor.label,
    successorContent,
  )}
      ${disclosureMarkup(
    "migration-history",
    "Migration / history",
    migrationSummary,
    migrationContent,
  )}
    </div>
  </section>`;
}

function reportMarkup(reports, timestampFormatter = (value) => value, filterMode = "all") {
  const visibleReports = filterReports(reports, filterMode);
  if (filterMode === "migrated" && !visibleReports.length) {
    return '<section class="empty-report">No migrated MRZ pairs currently available.</section>';
  }
  if (!visibleReports.length) {
    return '<section class="empty-report">No active MRZ is available for an operation card.</section>';
  }
  return visibleReports
    .map((report) => robustnessCardMarkup(report, timestampFormatter))
    .join("");
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    const refreshButton = document.getElementById("refreshReport");
    const status = document.getElementById("reportStatus");
    const content = document.getElementById("reportContent");
    const activeReports = document.getElementById("activeReports");
    const allFilterButton = document.getElementById("filterAll");
    const migratedFilterButton = document.getElementById("filterMigrated");
    let reports = [];
    let filterMode = "all";

    function renderReports() {
      activeReports.innerHTML = reportMarkup(
        reports,
        formatOperatorTimestampUtcMinus4,
        filterMode,
      );
      allFilterButton.classList.toggle("active", filterMode === "all");
      migratedFilterButton.classList.toggle("active", filterMode === "migrated");
      allFilterButton.setAttribute("aria-pressed", String(filterMode === "all"));
      migratedFilterButton.setAttribute(
        "aria-pressed",
        String(filterMode === "migrated"),
      );
    }

    function selectFilter(nextFilterMode) {
      filterMode = nextFilterMode === "migrated" ? "migrated" : "all";
      renderReports();
    }

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
        reports = report.active_mrzs;
        renderReports();
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
    allFilterButton.addEventListener("click", () => selectFilter("all"));
    migratedFilterButton.addEventListener("click", () => selectFilter("migrated"));
    loadReport();
  });
}

if (typeof module === "object" && module.exports) {
  module.exports = {
    displacementText,
    durationText,
    directionText,
    filterReports,
    hasValidMigrationProvenance,
    midpointValue,
    migrationEqmValue,
    migrationProvenanceMarkup,
    normalizedSpanText,
    percentageText,
    reportMarkup,
    robustnessCardMarkup,
    successorDetailsMarkup,
  };
}
