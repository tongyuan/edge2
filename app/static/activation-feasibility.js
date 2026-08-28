function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function frequencyText(frequency) {
  if (!frequency || !frequency.denominator) return "0 of 0 · —";
  return `${frequency.numerator} of ${frequency.denominator} · ${frequency.percentage}%`;
}

function decimalText(value, digits = 4) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return number.toLocaleString("en-GB", { maximumFractionDigits: digits });
}

function percentageText(value) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return `${number.toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}%`;
}

function frequencyPercentageText(value) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return `${number.toLocaleString("en-GB", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`;
}

function productionMarkup(rule, timestampFormatter = (value) => value) {
  const result = rule?.result || {};
  const frequency = result.activation_frequency || {};
  const activations = rule?.activations || [];
  const cards = activations.map((activation) => `
    <article class="production-activation-card">
      <h4>${escapeHtml(activation.symbol)} · ${escapeHtml(activation.route)}</h4>
      <dl>
        <div><dt>MRZ</dt><dd>${decimalText(activation.core_mrz_lower, 12)}–${decimalText(activation.core_mrz_upper, 12)}</dd></div>
        <div><dt>Activated</dt><dd>${escapeHtml(timestampFormatter(activation.activated_at) || "—")}</dd></div>
        <div><dt>Rule</dt><dd>${activation.minimum_observations} observations · ${percentageText(activation.allowance_percent)} allowance</dd></div>
      </dl>
    </article>`).join("");
  const activationDetail = cards
    ? `<div class="production-activation-grid">${cards}</div>`
    : '<p class="production-empty">No MRZ formed under the current production rule in this sample.</p>';
  return `
    <strong>Algorithm ${escapeHtml(rule?.algorithm || "—")} · ${rule?.minimum_observations ?? "—"} observations · ${percentageText(rule?.allowance_percent)}</strong>
    <div class="production-summary">
      <p class="production-outcome">${frequency.numerator ?? 0} of ${frequency.denominator ?? 0} eligible symbol-route histories formed an MRZ</p>
      <strong class="production-rate">${frequencyPercentageText(frequency.percentage)}</strong>
    </div>
    <div class="production-activations">
      <h3>ACTIVATED MRZ</h3>
      ${activationDetail}
    </div>`;
}

function durationText(value) {
  if (value === null || value === undefined) return "—";
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) return "—";
  if (seconds < 60) return `${decimalText(seconds, 1)}s`;
  if (seconds < 3600) return `${decimalText(seconds / 60, 1)}m`;
  if (seconds < 86400) return `${decimalText(seconds / 3600, 1)}h`;
  return `${decimalText(seconds / 86400, 1)}d`;
}

function summaryTableMarkup(rows) {
  const body = rows.map((row) => `
    <tr class="${row.is_current_production_rule ? "production-row" : ""}">
      <td>${row.minimum_observations}</td>
      <td>${row.allowance_percent}%${row.small_sample ? '<span class="low-sample">LOW SAMPLE</span>' : ""}</td>
      <td>${row.eligible_symbol_route_sequences}</td>
      <td>${row.hypothetical_activations}</td>
      <td>${frequencyText(row.activation_frequency)}</td>
      <td>${row.near_miss_sequences}</td>
      <td>${row.dispersed_sequences}</td>
      <td>${decimalText(row.median_ordinal_observation_at_qualification, 1)}</td>
      <td>${durationText(row.median_formation_duration_seconds)}</td>
      <td>${percentageText(row.median_minimum_required_allowance_pct_at_qualification)}</td>
    </tr>`).join("");
  return `<thead><tr>
    <th>Minimum</th><th>Allowance</th><th>Eligible</th><th>MRZ formations</th>
    <th>Formation frequency</th><th>Near misses</th><th>Dispersed</th>
    <th>Median ordinal</th><th>Median duration</th><th>Median minimum allowance required</th>
  </tr></thead><tbody>${body}</tbody>`;
}

function matrixMarkup(rows) {
  const allowances = [1, 2, 3, 4, 5];
  const minimums = [2, 3, 4];
  const cells = new Map(rows.map((row) => [`${row.minimum_observations}-${row.allowance_percent}`, row]));
  const body = minimums.map((minimum) => `<tr><th scope="row">${minimum}</th>${allowances.map((allowance) => {
    const row = cells.get(`${minimum}-${allowance}`);
    return `<td>${frequencyText(row?.activation_frequency)}${row?.small_sample ? '<br><span class="low-sample">LOW SAMPLE</span>' : ""}</td>`;
  }).join("")}</tr>`).join("");
  return `<thead><tr><th>Minimum / Allowance</th>${allowances.map((value) => `<th>${value}%</th>`).join("")}</tr></thead><tbody>${body}</tbody>`;
}

function auditTableMarkup(rows, timestampFormatter) {
  const body = rows.map((row) => {
    const activated = row.activated ? "First activated" : (row.eligible ? "Never qualified" : "Insufficient observations");
    const timestamp = row.first_qualifying_timestamp
      ? timestampFormatter(row.first_qualifying_timestamp) || "—"
      : "—";
    const proposedRange = row.proposed_lower_boundary !== null
      ? `${decimalText(row.proposed_lower_boundary, 6)}–${decimalText(row.proposed_upper_boundary, 6)}`
      : "—";
    const requiredAllowance = row.activated
      ? row.minimum_required_allowance_pct
      : row.closest_minimum_required_allowance_pct;
    const requiredAllowanceLabel = row.eligible
      ? `${row.activated ? "First" : "Closest"} · ${percentageText(requiredAllowance)}`
      : "—";
    const resultClass = `result-${row.classification.toLowerCase().replaceAll("_", "-")}`;
    return `<tr>
      <td>${escapeHtml(row.symbol)}</td><td>${row.route}</td><td>${row.total_stored_route_observations}</td>
      <td>${row.algorithm} · ${row.minimum_observations} · ${row.allowance_percent}%</td>
      <td class="${resultClass}">${row.classification.replaceAll("_", " ")}</td>
      <td>${activated}</td><td>${timestamp}</td>
      <td>${row.ordinal_route_observation_number ?? "—"}</td><td>${durationText(row.formation_duration_seconds)}</td>
      <td>${proposedRange}</td><td>${requiredAllowanceLabel}</td><td>${decimalText(row.normalized_span, 5)}</td>
      <td>${decimalText(row.closest_qualification_ratio, 3)}</td>
      <td>${escapeHtml(row.structural_location?.replaceAll("_", " ") || "—")}</td>
    </tr>`;
  }).join("");
  return `<thead><tr>
    <th>Symbol</th><th>Route</th><th>Stored observations</th><th>Scenario</th><th>Classification</th>
    <th>Outcome</th><th>First qualifying time</th><th>Observation no.</th><th>Formation</th>
    <th>Proposed range</th><th>Minimum allowance required</th><th>Normalized span</th><th>Closest ratio</th><th>Location</th>
  </tr></thead><tbody>${body}</tbody>`;
}

function candidatePolicyMarkup(evaluation) {
  if (!evaluation) return "";
  const current = evaluation.current || {};
  const candidate = evaluation.candidate;
  const resultMarkup = (label, policy) => {
    const frequency = policy?.activation_frequency || {};
    const denominator = frequency.denominator ?? 0;
    return `<article class="candidate-policy-result">
      <span>${label}</span>
      <strong>Algorithm ${escapeHtml(policy?.algorithm || "—")} · ${policy?.minimum_observations ?? "—"} observations · ${percentageText(policy?.allowance_percent)}</strong>
      <p>${frequency.numerator ?? 0} of ${denominator} ${denominator === 1 ? "history" : "histories"} formed an MRZ</p>
    </article>`;
  };
  const basis = (evaluation.selection_basis || []).map((item) =>
    `<li><span aria-hidden="true">✓</span>${escapeHtml(item)}</li>`
  ).join("");
  const candidateDetails = candidate
    ? `<div class="candidate-policy-identity">
        <span>CANDIDATE</span>
        <strong>Algorithm ${escapeHtml(candidate.algorithm)}</strong>
        <dl>
          <div><dt>Minimum observations</dt><dd>${candidate.minimum_observations}</dd></div>
          <div><dt>Allowance</dt><dd>${percentageText(candidate.allowance_percent)}</dd></div>
        </dl>
      </div>
      <div class="candidate-policy-comparison">
        <span>OBSERVED IMPACT</span>
        <div>${resultMarkup("CURRENT", current)}${resultMarkup("CANDIDATE", candidate)}</div>
      </div>`
    : `<div class="candidate-policy-empty"><p>${escapeHtml(evaluation.text)}</p></div>`;
  return `<article class="candidate-policy-card">
    <div class="candidate-policy-heading">
      <div><span>DECISION SUPPORT</span><h3>${escapeHtml(evaluation.heading)}</h3></div>
      ${evaluation.small_sample ? '<strong class="candidate-policy-status">PRELIMINARY</strong>' : ""}
    </div>
    <div class="candidate-policy-layout">${candidateDetails}</div>
    <div class="candidate-policy-basis"><span>SELECTION BASIS</span><ul>${basis}</ul></div>
  </article>`;
}

function diagnosisSummaryMarkup(diagnosis) {
  if (!diagnosis) return "";
  const sections = [
    diagnosis.sample_assessment,
    diagnosis.production_feasibility,
    diagnosis.count_sensitivity,
    diagnosis.allowance_sensitivity,
  ].filter(Boolean);
  const cards = sections.map((item) => `
    <article class="diagnosis-card">
      <h3>${escapeHtml(item.heading)}</h3>
      <p>${escapeHtml(item.text)}</p>
    </article>`).join("");
  return `<div class="diagnosis-grid">${cards}</div>`;
}

function nearMissSectionMarkup(items, heading, timeLabel, emptyText, timestampFormatter) {
  const uniqueItems = (items || []).filter((item) => !item.matches_current_candidate);
  const sharedItems = (items || []).filter((item) => item.matches_current_candidate);
  const cards = uniqueItems.map((item) => {
    const timestamp = timestampFormatter(item.candidate_timestamp || item.closest_timestamp) || "—";
    return `<article class="near-miss-card">
      <h3>${escapeHtml(item.heading)}</h3>
      <p>${escapeHtml(item.text)}</p>
      <dl>
        <div><dt>Candidate range</dt><dd>${decimalText(item.candidate_lower_boundary, 6)}–${decimalText(item.candidate_upper_boundary, 6)}</dd></div>
        <div><dt>Observations</dt><dd>${item.candidate_observation_count} of ${item.total_stored_route_observations}</dd></div>
        <div><dt>${timeLabel}</dt><dd>${escapeHtml(timestamp)}</dd></div>
      </dl>
    </article>`;
  }).join("");
  const shared = sharedItems.map((item) =>
    `<p class="near-miss-shared"><strong>${escapeHtml(item.heading)}</strong> · Current candidate is also the closest historical near miss.</p>`
  ).join("");
  return cards || shared
    ? `<div class="diagnosis-subsection"><h3>${heading}</h3>${cards ? `<div class="near-miss-grid">${cards}</div>` : ""}${shared}</div>`
    : `<div class="diagnosis-subsection"><h3>${heading}</h3><p class="neutral">${emptyText}</p></div>`;
}

function decisionSupportMarkup(diagnosis, timestampFormatter = (value) => value) {
  if (!diagnosis) return "";
  const currentNearMissSection = nearMissSectionMarkup(
    diagnosis.current_production_near_misses,
    "Current production near misses",
    "Current candidate time",
    "No current structurally eligible production near miss falls above 1% and at or below 2%.",
    timestampFormatter,
  );
  const historicalNearMissSection = nearMissSectionMarkup(
    diagnosis.closest_production_near_misses,
    "Closest historical production near misses",
    "Closest historical time",
    "No historical structurally eligible production near miss fell above 1% and at or below 2%.",
    timestampFormatter,
  );
  const interpretation = diagnosis.evidence_interpretation
    ? `<article class="diagnosis-card interpretation-card"><h3>${escapeHtml(diagnosis.evidence_interpretation.heading)}</h3><p>${escapeHtml(diagnosis.evidence_interpretation.text)}</p></article>`
    : "";
  const candidatePolicy = candidatePolicyMarkup(diagnosis.candidate_policy_evaluation);
  return `${candidatePolicy}${currentNearMissSection}${historicalNearMissSection}${interpretation}`;
}

function filterAuditRows(rows, filters) {
  return rows.filter((row) => (
    row.algorithm === "A"
    && (!filters.symbol || row.symbol === filters.symbol)
    && (!filters.route || row.route === filters.route)
    && (!filters.minimum || String(row.minimum_observations) === filters.minimum)
    && (!filters.allowance || String(row.allowance_percent) === filters.allowance)
    && (!filters.classification || row.classification === filters.classification)
  ));
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    const refreshButton = document.getElementById("refreshReport");
    const status = document.getElementById("reportStatus");
    const content = document.getElementById("reportContent");
    const sampleWarning = document.getElementById("sampleWarning");
    const filterIds = ["symbolFilter", "routeFilter", "minimumFilter", "allowanceFilter", "classificationFilter"];
    let report = null;

    function renderAudit() {
      if (!report) return;
      const filters = {
        symbol: document.getElementById("symbolFilter").value,
        route: document.getElementById("routeFilter").value,
        minimum: document.getElementById("minimumFilter").value,
        allowance: document.getElementById("allowanceFilter").value,
        classification: document.getElementById("classificationFilter").value,
      };
      const rows = filterAuditRows(report.sequence_details, filters);
      document.getElementById("auditCount").textContent = `${rows.length} row${rows.length === 1 ? "" : "s"}`;
      document.getElementById("auditTable").innerHTML = auditTableMarkup(rows, formatOperatorTimestampUtcMinus4);
    }

    function renderReport(value) {
      report = value;
      document.getElementById("generatedAt").textContent = formatOperatorTimestampUtcMinus4(value.generated_at) || "—";
      const earliest = formatOperatorTimestampUtcMinus4(value.earliest_observation_at);
      const latest = formatOperatorTimestampUtcMinus4(value.latest_observation_at);
      document.getElementById("observationRange").textContent = earliest && latest ? `${earliest} → ${latest}` : "—";
      document.getElementById("totalObservations").textContent = value.total_observations_evaluated;
      document.getElementById("totalSymbols").textContent = value.total_normalized_symbols;
      document.getElementById("totalSequences").textContent = value.total_symbol_route_sequences;
      sampleWarning.hidden = !value.diagnosis?.sample_assessment?.small_sample;
      document.getElementById("diagnosisSummaryContent").innerHTML = diagnosisSummaryMarkup(value.diagnosis);
      document.getElementById("decisionSupportContent").innerHTML = decisionSupportMarkup(
        value.diagnosis,
        formatOperatorTimestampUtcMinus4,
      );

      document.getElementById("productionContent").innerHTML = productionMarkup(
        value.current_production_rule,
        formatOperatorTimestampUtcMinus4,
      );
      const rowsA = value.scenarios.filter((row) => row.algorithm === "A");
      document.getElementById("summaryA").innerHTML = summaryTableMarkup(rowsA);
      document.getElementById("matrixA").innerHTML = matrixMarkup(rowsA);

      const symbolFilter = document.getElementById("symbolFilter");
      const selectedSymbol = symbolFilter.value;
      const symbols = [...new Set(
        value.sequence_details.filter((row) => row.algorithm === "A").map((row) => row.symbol),
      )].sort();
      symbolFilter.innerHTML = `<option value="">All</option>${symbols.map((symbol) => `<option value="${escapeHtml(symbol)}">${escapeHtml(symbol)}</option>`).join("")}`;
      if (symbols.includes(selectedSymbol)) symbolFilter.value = selectedSymbol;
      renderAudit();
    }

    async function loadReport() {
      refreshButton.disabled = true;
      status.hidden = false;
      status.classList.remove("error");
      status.textContent = "Calculating the latest report…";
      content.hidden = true;
      try {
        const response = await fetch("/api/diagnostics/activation-feasibility", { cache: "no-store" });
        if (!response.ok) throw new Error(`Report request failed (${response.status})`);
        const value = await response.json();
        renderReport(value);
        status.hidden = true;
        content.hidden = false;
      } catch (error) {
        status.classList.add("error");
        status.textContent = `Unable to generate the report. ${error.message}`;
      } finally {
        refreshButton.disabled = false;
      }
    }

    filterIds.forEach((id) => document.getElementById(id).addEventListener("change", renderAudit));
    refreshButton.addEventListener("click", loadReport);
    loadReport();
  });
}

if (typeof module === "object" && module.exports) {
  module.exports = {
    auditTableMarkup,
    candidatePolicyMarkup,
    decisionSupportMarkup,
    diagnosisSummaryMarkup,
    filterAuditRows,
    frequencyText,
    frequencyPercentageText,
    matrixMarkup,
    percentageText,
    productionMarkup,
    summaryTableMarkup,
  };
}
