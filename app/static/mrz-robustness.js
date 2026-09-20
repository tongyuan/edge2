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
  if (filterMode === "pressure") {
    return reports.filter((report) => {
      const pressure = report.current_pressure || report.migration_pressure;
      return report.structural_authority?.status === "AUTHORITATIVE"
        && pressure?.status === "UNDER_PRESSURE"
        && ["UP", "DOWN"].includes(pressure.direction);
    });
  }
  if (filterMode !== "migrated") return [...reports];
  return reports.filter((report) => hasValidMigrationProvenance(report));
}

function operatorViewCounts(reports) {
  return { all: reports.length, pressure: filterReports(reports, "pressure").length };
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
  if (!migration?.has_migrated) {
    return '<div class="history-empty">No recorded migration. Current MRZ is the first recorded authority.</div>';
  }
  const downward = migration.direction === "DOWN";
  const arrow = downward ? "↓" : "↑";
  const direction = downward ? "DOWNWARD" : "UPWARD";
  const previousRange = `${priceText(migration.previous_lower)} – ${priceText(migration.previous_upper)}`;
  const currentRange = `${priceText(migration.current_lower)} – ${priceText(migration.current_upper)}`;
  const previousMidpoint = midpointValue(migration.previous_lower, migration.previous_upper);
  const currentMidpoint = currentState.currentMidpoint;
  const migrationEqm = migrationEqmValue(migration, currentMidpoint);
  const previousActivatedAt = migration.previous_activated_at
    ? timestampFormatter(migration.previous_activated_at)
    : null;
  const migratedAt = timestampFormatter(migration.migrated_at) || "—";
  const currentActivatedAt = currentState.currentActivatedAt
    ? timestampFormatter(currentState.currentActivatedAt)
    : null;
  return `<aside class="migration-chronology" aria-label="MRZ migration chronology">
    <div class="migration-chronology-heading">
      <span class="section-label">MIGRATION CHRONOLOGY</span>
      <strong>${arrow} MIGRATED ${direction}</strong>
    </div>
    <ol class="migration-timeline">
      <li class="previous-authority-event">
        <span class="timeline-marker" aria-hidden="true"></span>
        <div>
          <span>PREVIOUS AUTHORITY</span>
          <strong>${previousRange}</strong>
          <small>Midpoint ${priceText(previousMidpoint)}</small>
          <small>Activated ${escapeHtml(previousActivatedAt || "Unavailable")}</small>
        </div>
      </li>
      <li class="migration-event">
        <span class="timeline-marker" aria-hidden="true"></span>
        <div>
          <span>${arrow} MIGRATED ${direction}</span>
          <small>${escapeHtml(migratedAt)}</small>
        </div>
      </li>
      <li class="current-authority-event">
        <span class="timeline-marker" aria-hidden="true"></span>
        <div>
          <span>CURRENT AUTHORITY</span>
          <strong>${currentRange}</strong>
          <small>Midpoint ${priceText(currentMidpoint)}</small>
          ${currentActivatedAt ? `<small>Activated ${escapeHtml(currentActivatedAt)}</small>` : ""}
        </div>
      </li>
    </ol>
    <div class="history-eqm"><span>MIGRATION EQM</span><strong>${priceText(migrationEqm)}</strong></div>
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

function robustnessCardMarkup(
  report,
  timestampFormatter = (value) => value,
  focusedSymbol = null,
) {
  const authority = report.structural_authority;
  const active = report.active_mrz;
  const formation = report.formation_evidence;
  const behavior = report.post_activation_robustness;
  const position = report.observation_position;
  const boundary = report.boundary_pressure;
  const displacement = report.mrz_displacement;
  const pressure = report.current_pressure || report.migration_pressure;
  const cumulativePressure = report.cumulative_pressure || report.migration_pressure;
  const successor = report.successor_watch;
  const age = report.mrz_age;
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
  const postActivationObservationText = `${behavior.post_activation_observation_count} observation${behavior.post_activation_observation_count === 1 ? "" : "s"}`;
  const pressureDirection = directionText(pressure.direction, pressure.direction_label);
  const stateSummary = pressure.direction !== "NEUTRAL"
    ? `${pressure.direction === "UP" ? "↑" : "↓"} ${pressure.label}`
    : pressure.label || pressureDirection;
  const recentPressureSequence = (pressure.recent_sequence || [])
    .map((entry) => (entry.direction === "UP" ? "↑" : "↓"))
    .join(" ") || "—";
  const currentPressureSince = pressure.current_pressure_since
    ? `Since ${timestampFormatter(pressure.current_pressure_since)}`
    : "Regime not established";
  const latestPressureObservation = pressure.latest_pressure_observed_at
    ? `Latest pressure ${timestampFormatter(pressure.latest_pressure_observed_at)}`
    : "No qualifying pressure observations";
  const migrationSummary = report.migration?.has_migrated
    ? `Migrated ${String(report.migration.direction || "").toLowerCase()}`
    : "No recorded migration";
  const hasPreviousMrz = hasValidMigrationProvenance(report);
  const previousMidpoint = hasPreviousMrz
    ? midpointValue(report.migration.previous_lower, report.migration.previous_upper)
    : null;
  const migrationEqm = hasPreviousMrz
    ? migrationEqmValue(report.migration, active.midpoint)
    : null;
  const previousActivatedAt = hasPreviousMrz
    ? (report.migration.previous_activated_at
      ? timestampFormatter(report.migration.previous_activated_at)
      : null) || "Unavailable"
    : null;
  const previousMrzMarkup = hasPreviousMrz
    ? `<strong class="authority-range">${priceText(report.migration.previous_lower)} – ${priceText(report.migration.previous_upper)}</strong>
      <dl class="authority-facts">
        <div><dt>Midpoint</dt><dd>${priceText(previousMidpoint)}</dd></div>
        <div><dt>Activated</dt><dd>${escapeHtml(previousActivatedAt)}</dd></div>
      </dl>`
    : '<strong class="authority-empty">No previous MRZ</strong>';
  const migrationEqmMarkup = hasPreviousMrz
    ? `<div class="authority-eqm" aria-label="Migration EQM">
        <span>MIGRATION EQM</span>
        <strong>${priceText(migrationEqm)}</strong>
      </div>`
    : "";
  const migrationDirection = report.migration?.direction;
  const migrationDirectionMarkup = hasPreviousMrz
    && (migrationDirection === "UP" || migrationDirection === "DOWN")
    ? `<strong class="authority-migration-direction">${migrationDirection === "UP" ? "↑ MIGRATED UP" : "↓ MIGRATED DOWN"}</strong>`
    : "";

  const postActivationContent = `<p class="detail-explanation">${escapeHtml(cumulativePressure.reason)}</p>
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
      currentActivatedAt: active.activated_at,
    },
    timestampFormatter,
  )}`;

  const formationContent = `<div class="detail-card formation-detail">
    <dl class="detail-grid formation-detail-grid">
      <div><dt>${escapeHtml(firstQualifyingLabel)}</dt><dd>${escapeHtml(formationStartedAt)}</dd></div>
      <div><dt>Formation duration</dt><dd>${escapeHtml(formationDuration)}</dd></div>
      <div><dt>Qualifying observations</dt><dd>${formation.confirming_observation_count}</dd></div>
    </dl>
    <p>${escapeHtml(formation.meaning || "Formation evidence retained for research context.")}</p>
  </div>`;

  const focusedClass = report.symbol === focusedSymbol ? " focused-operator-card" : "";
  const focusAttribute = report.symbol === focusedSymbol ? ' tabindex="-1"' : "";
  return `<section class="mrz-report${focusedClass}" data-symbol="${escapeHtml(report.symbol)}"${focusAttribute}>
    <header class="compact-authority" aria-label="Current structural authority" data-section="active-mrz">
      <div class="mrz-heading">
        <div>
          <h2>${escapeHtml(report.symbol)} · ${escapeHtml(report.route_owner)}</h2>
          <p class="structural-location">${escapeHtml(authority.structural_location_label)}</p>
        </div>
        <strong class="status-pill authoritative">${escapeHtml(authority.label)}</strong>
      </div>

      <section class="mrz-authority-context" aria-label="MRZ Authority">
        <div class="mrz-authority-heading">
          <span class="section-label">MRZ AUTHORITY</span>
          ${migrationDirectionMarkup}
        </div>
        <div class="mrz-authority-grid">
          <section class="authority-zone current-authority-zone" aria-label="Current MRZ">
            <span class="authority-zone-label">CURRENT MRZ</span>
            <strong class="authority-range">${priceText(active.lower)} – ${priceText(active.upper)}</strong>
            <dl class="authority-facts">
              <div><dt>Midpoint</dt><dd>${priceText(active.midpoint)}</dd></div>
              <div><dt>Activated</dt><dd>${escapeHtml(activeTimestamp)}</dd></div>
            </dl>
            <small class="mrz-age">${escapeHtml(activeDuration)} old</small>
          </section>
          <section class="authority-zone previous-authority-zone" aria-label="Previous MRZ">
            <span class="authority-zone-label">PREVIOUS MRZ</span>
            ${previousMrzMarkup}
          </section>
        </div>
        ${migrationEqmMarkup}
      </section>

      <section class="current-pressure-panel ${statusClass(pressure.status)}" aria-label="Current Pressure">
        <div class="current-pressure-heading">
          <div>
            <span class="section-label">CURRENT PRESSURE</span>
            <strong>${escapeHtml(stateSummary)}</strong>
          </div>
          <span class="pressure-observation-count">${escapeHtml(currentPressureSince)}</span>
        </div>
        <div class="current-pressure-evidence">
          <div>
            <span>RECENT PRESSURE</span>
            <strong aria-label="Recent pressure sequence">${escapeHtml(recentPressureSequence)}</strong>
          </div>
          <div>
            <span>LATEST PRESSURE OBSERVATION</span>
            <strong>${escapeHtml(latestPressureObservation)}</strong>
          </div>
        </div>
        <p class="cumulative-pressure-summary">
          <span>CUMULATIVE SINCE ACTIVATION</span>
          <strong>↑ ${cumulativePressure.above_upper_envelope_observation_count} · ↓ ${cumulativePressure.below_lower_envelope_observation_count} · ${cumulativePressure.observations_beyond_envelope} outside</strong>
        </p>
      </section>
    </header>

    <div class="operator-disclosures">
      ${disclosureMarkup(
    "post-activation",
    "Cumulative since activation",
    `${cumulativePressure.label} · ${postActivationObservationText}`,
    postActivationContent,
  )}
      ${disclosureMarkup(
    "migration-history",
    "Migration / history",
    migrationSummary,
    migrationContent,
  )}
      ${disclosureMarkup(
    "successor-watch",
    "Successor Watch",
    successor.label,
    successorContent,
  )}
      ${disclosureMarkup(
    "formation-details",
    "Formation details",
    `${formation.confirming_observation_count} qualifying observations`,
    formationContent,
  )}
    </div>
  </section>`;
}

function reportMarkup(
  reports,
  timestampFormatter = (value) => value,
  filterMode = "all",
  focusedSymbol = null,
) {
  const visibleReports = filterReports(reports, filterMode);
  if (filterMode === "pressure" && !visibleReports.length) {
    return '<section class="empty-report">No directional pressure currently detected.</section>';
  }
  if (filterMode === "migrated" && !visibleReports.length) {
    return '<section class="empty-report">No migrated MRZ pairs currently available.</section>';
  }
  if (!visibleReports.length) {
    return '<section class="empty-report">No active MRZ is available for an operation card.</section>';
  }
  return visibleReports
    .map((report) => robustnessCardMarkup(report, timestampFormatter, focusedSymbol))
    .join("");
}

function operatorCardSymbolFromSearch(search = "") {
  return new URLSearchParams(search).get("symbol") || null;
}

function operatorCardSectionFromHash(hash = "") {
  const section = hash.startsWith("#") ? hash.slice(1) : "";
  return ["active-mrz", "migration-history", "post-activation"].includes(section)
    ? section
    : null;
}

function focusOperatorCard(container, symbol, section = null) {
  if (!container || !symbol) return false;
  const card = Array.from(container.querySelectorAll(".mrz-report"))
    .find((item) => item.dataset.symbol === symbol);
  if (!card) return false;
  let target = card;
  if (section) {
    const sectionTarget = card.querySelector(`[data-section="${section}"]`);
    if (sectionTarget) {
      target = sectionTarget;
      if (sectionTarget.tagName === "DETAILS") sectionTarget.open = true;
    }
  }
  target.tabIndex = -1;
  target.scrollIntoView({ block: "start" });
  target.focus({ preventScroll: true });
  return true;
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    const refreshButton = document.getElementById("refreshReport");
    const status = document.getElementById("reportStatus");
    const content = document.getElementById("reportContent");
    const activeReports = document.getElementById("activeReports");
    const allFilterButton = document.getElementById("filterAll");
    const pressureFilterButton = document.getElementById("filterPressure");
    const allCount = document.getElementById("allCount");
    const pressureCount = document.getElementById("pressureCount");
    const viewButtons = [allFilterButton, pressureFilterButton];
    const requestedSymbol = operatorCardSymbolFromSearch(window.location.search);
    const requestedSection = operatorCardSectionFromHash(window.location.hash);
    let reports = [];
    let filterMode = "all";
    let requestedCardFocused = false;

    function renderReports() {
      activeReports.innerHTML = reportMarkup(
        reports,
        formatOperatorTimestampUtcMinus4,
        filterMode,
        requestedSymbol,
      );
      const counts = operatorViewCounts(reports);
      allCount.textContent = counts.all;
      pressureCount.textContent = counts.pressure;
      viewButtons.forEach((button) => {
        const selected = button === (filterMode === "pressure" ? pressureFilterButton : allFilterButton);
        button.classList.toggle("active", selected);
        button.setAttribute("aria-selected", String(selected));
        button.tabIndex = selected ? 0 : -1;
      });
      activeReports.setAttribute("aria-labelledby", filterMode === "pressure" ? "filterPressure" : "filterAll");
    }

    function selectFilter(nextFilterMode) {
      filterMode = nextFilterMode === "pressure" ? "pressure" : "all";
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
        // Reveal a push-targeted card before its initial focus, even after a tab switch
        // during loading. Explicit operator tab choices after focus remain respected.
        if (!requestedCardFocused && requestedSymbol
          && reports.some((item) => item.symbol === requestedSymbol)) {
          filterMode = "all";
        }
        renderReports();
        status.hidden = true;
        content.hidden = false;
        if (!requestedCardFocused) {
          requestedCardFocused = focusOperatorCard(
            activeReports,
            requestedSymbol,
            requestedSection,
          );
        }
      } catch (error) {
        status.classList.add("error");
        status.textContent = `Unable to generate the report. ${error.message}`;
      } finally {
        refreshButton.disabled = false;
      }
    }

    refreshButton.addEventListener("click", loadReport);
    allFilterButton.addEventListener("click", () => selectFilter("all"));
    pressureFilterButton.addEventListener("click", () => selectFilter("pressure"));
    viewButtons.forEach((button, index) => {
      button.addEventListener("keydown", (event) => {
        let nextIndex;
        if (event.key === "ArrowRight") nextIndex = (index + 1) % viewButtons.length;
        else if (event.key === "ArrowLeft") nextIndex = (index + viewButtons.length - 1) % viewButtons.length;
        else if (event.key === "Home") nextIndex = 0;
        else if (event.key === "End") nextIndex = viewButtons.length - 1;
        else return;
        event.preventDefault();
        selectFilter(nextIndex === 1 ? "pressure" : "all");
        viewButtons[nextIndex].focus({ preventScroll: true });
      });
    });
    loadReport();
  });
}

if (typeof module === "object" && module.exports) {
  module.exports = {
    displacementText,
    durationText,
    directionText,
    filterReports,
    operatorViewCounts,
    hasValidMigrationProvenance,
    midpointValue,
    migrationEqmValue,
    migrationProvenanceMarkup,
    normalizedSpanText,
    operatorCardSectionFromHash,
    operatorCardSymbolFromSearch,
    focusOperatorCard,
    percentageText,
    reportMarkup,
    robustnessCardMarkup,
    successorDetailsMarkup,
  };
}
