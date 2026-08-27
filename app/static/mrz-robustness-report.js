(function mrzRobustnessReportModule(globalScope) {
  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function numberText(value, digits = 1) {
    if (value === null || value === undefined || value === "") return "—";
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    return number.toLocaleString("en-GB", { maximumFractionDigits: digits });
  }

  function percentageText(value, digits = 1) {
    const number = numberText(value, digits);
    return number === "—" ? number : `${number}%`;
  }

  function durationText(value) {
    if (value === null || value === undefined || value === "") return "—";
    const seconds = Number(value);
    if (!Number.isFinite(seconds)) return "—";
    if (seconds < 60) return `${numberText(seconds, 1)}s`;
    if (seconds < 3600) return `${numberText(seconds / 60, 1)}m`;
    if (seconds < 86400) return `${numberText(seconds / 3600, 1)}h`;
    return `${numberText(seconds / 86400, 1)}d`;
  }

  function rateText(rate) {
    if (!rate || !rate.denominator) return `${rate?.numerator ?? 0} of ${rate?.denominator ?? 0} · —`;
    return `${rate.numerator} of ${rate.denominator} · ${percentageText(rate.percentage)}`;
  }

  function statusClass(status) {
    return `status-${String(status || "not-yet-assessable").toLowerCase().replaceAll("_", "-")}`;
  }

  function metricCard(label, value, note = "", extraClass = "") {
    return `<article class="metric-card ${extraClass}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong>${note ? `<p>${escapeHtml(note)}</p>` : ""}</article>`;
  }

  function sampleConfidenceMarkup(sample) {
    return `<div class="metric-grid">
      ${metricCard("Assessment", sample.label?.replace("Sample confidence · ", "") || "—", `${sample.eligible_symbol_route_histories} eligible histories`, "status-card")}
      ${metricCard("Eligible histories", sample.eligible_symbol_route_histories ?? 0, "Symbol-route histories with at least four observations")}
      ${metricCard("Production formations", sample.production_mrz_formations ?? 0, `of ${sample.production_formed_denominator ?? 0} eligible histories`)}
      ${metricCard("With post-activation evidence", sample.production_formations_with_post_activation_evidence ?? 0, "Strictly after production-policy activation")}
      ${metricCard("Completed lifecycles", sample.completed_migration_lifecycles ?? 0, "Deterministic migrations; other lifecycles are censored")}
    </div>`;
  }

  function productionSummaryMarkup(summary) {
    return `<div class="metric-grid">
      ${metricCard("Formation coverage", summary.formed_mrz_count ?? 0, rateText(summary.formation_coverage))}
      ${metricCard("With post-activation evidence", summary.formations_with_post_activation_evidence ?? 0, `of ${summary.formed_mrz_count ?? 0} formations`)}
      ${metricCard("Median containment", percentageText(summary.median_containment_percentage), `n=${summary.containment_sample_count ?? 0}`)}
      ${metricCard("Observed lifespan", durationText(summary.median_observed_lifespan_seconds), `n=${summary.observed_lifespan_sample_count ?? 0} · ${summary.completed_lifecycle_count ?? 0} completed · ${summary.censored_lifecycle_count ?? 0} censored`)}
      ${metricCard("Time to migration", durationText(summary.median_time_to_migration_seconds), `completed n=${summary.time_to_migration_sample_count ?? 0}`)}
      ${metricCard("Migration pressure", rateText(summary.migration_pressure_incidence), "Among formations with post-activation evidence")}
      ${metricCard("Successor pressure", rateText(summary.successor_pressure_incidence), "Among formations with post-activation evidence")}
      ${metricCard("Route integrity maintained", rateText(summary.route_integrity_maintained), "Among formations with post-activation evidence")}
    </div>`;
  }

  function crossSymbolTableMarkup(rows, timestampFormatter = (value) => value) {
    const body = (rows || []).map((row) => `<tr>
      <td><strong>${escapeHtml(row.symbol)}</strong><span class="secondary">${escapeHtml(row.route)}</span></td>
      <td>${escapeHtml(row.mrz.lower)}–${escapeHtml(row.mrz.upper)}<span class="secondary">${escapeHtml(row.mrz.structural_location).replaceAll("_", " ")}</span></td>
      <td>${escapeHtml(timestampFormatter(row.activated_at) || "—")}</td>
      <td>${escapeHtml(row.durability_label)}</td>
      <td>${row.post_activation_observation_count}</td>
      <td>${percentageText(row.containment.percentage)}</td>
      <td>${durationText(row.observed_lifespan_seconds)}${row.lifecycle.censored ? '<span class="secondary">censored</span>' : '<span class="secondary">completed</span>'}</td>
      <td>${escapeHtml(row.migration_pressure.status).replaceAll("_", " ")}</td>
      <td>${escapeHtml(row.successor_watch.status).replaceAll("_", " ")}</td>
      <td>${escapeHtml(row.route_integrity.status).replaceAll("_", " ")}</td>
    </tr>`).join("");
    const empty = '<tr><td colspan="10" class="neutral">No production-policy MRZ formed in the available sample.</td></tr>';
    return `<thead><tr><th>Symbol / Route</th><th>Frozen MRZ</th><th>Activated</th><th>Durability</th><th>Post observations</th><th>Containment</th><th>Observed lifespan</th><th>Migration pressure</th><th>Successor</th><th>Route integrity</th></tr></thead><tbody>${body || empty}</tbody>`;
  }

  function pressureSummaryMarkup(summary) {
    const successor = summary.successor_watch || {};
    return `<div class="pressure-layout">
      <article class="pressure-group"><h3>DURABILITY STATE · ${summary.formed_mrz_count ?? 0} FORMED MRZS</h3><div class="pressure-counts">
        <div><span>Stable</span><strong>${summary.stable ?? 0}</strong></div>
        <div><span>Under pressure</span><strong>${summary.under_pressure ?? 0}</strong></div>
        <div><span>Migration candidate</span><strong>${summary.migration_candidate ?? 0}</strong></div>
        <div><span>Not yet assessable</span><strong>${summary.not_yet_assessable ?? 0}</strong></div>
      </div></article>
      <article class="pressure-group"><h3>SUCCESSOR WATCH</h3><div class="pressure-counts">
        <div><span>No successor</span><strong>${successor.no_successor ?? 0}</strong></div>
        <div><span>Candidate forming</span><strong>${successor.candidate_forming ?? 0}</strong></div>
        <div><span>Awaiting confirmation</span><strong>${successor.awaiting_confirmation ?? 0}</strong></div>
        <div><span>Confirmed</span><strong>${successor.confirmed ?? 0}</strong></div>
      </div></article>
    </div>`;
  }

  function policyComparisonMarkup(rows) {
    const policies = rows || [];
    const cell = (row, value, note = "") => `<td class="${row === policies[0] ? "production-cell" : ""}">${value}${note ? `<span class="secondary">${note}</span>` : ""}</td>`;
    const metricRow = (label, render) => `<tr><th scope="row">${label}</th>${policies.map((row) => render(row)).join("")}</tr>`;
    const body = [
      metricRow("Formation coverage · context only", (row) => cell(row, `${row.formed_mrz_count} of ${row.eligible_symbol_route_histories}`, percentageText(row.formation_coverage.percentage))),
      metricRow("Median containment", (row) => cell(row, percentageText(row.median_containment_percentage), `n=${row.containment_sample_count}`)),
      metricRow("Median observed lifespan", (row) => cell(row, durationText(row.median_observed_lifespan_seconds), `n=${row.observed_lifespan_sample_count} · ${row.completed_lifecycle_count} completed · ${row.censored_lifecycle_count} censored`)),
      metricRow("Median time to migration", (row) => cell(row, durationText(row.median_time_to_migration_seconds), `n=${row.time_to_migration_sample_count}`)),
      metricRow("Migration confirmed", (row) => cell(row, rateText(row.migration_confirmation_incidence))),
      metricRow("Early migration", (row) => cell(row, rateText(row.early_migration_incidence))),
      metricRow("Migration pressure", (row) => cell(row, rateText(row.migration_pressure_incidence), `median first pressure ${durationText(row.median_time_to_first_pressure_seconds)} · n=${row.time_to_first_pressure_sample_count}`)),
      metricRow("Successor pressure", (row) => cell(row, rateText(row.successor_pressure_incidence))),
      metricRow("Route integrity maintained", (row) => cell(row, rateText(row.route_integrity_maintained))),
    ].join("");
    const headings = policies.map((row, index) => `<th>${escapeHtml(row.allowance_percent)}%${index === 0 ? '<span class="secondary">production</span>' : ""}</th>`).join("");
    return `<thead><tr><th>Metric</th>${headings}</tr></thead><tbody>${body}</tbody>`;
  }

  function cohortMarkup(cohort) {
    return `<article class="cohort-card">
      <h3>${escapeHtml(cohort.label)}</h3>
      <p class="cohort-definition">${escapeHtml(cohort.definition)}</p>
      <div class="cohort-count"><strong>${cohort.history_count}</strong><span>symbol-route histories</span></div>
      <dl class="compact-facts">
        <div><dt>Median containment</dt><dd>${percentageText(cohort.median_containment_percentage)} · n=${cohort.containment_sample_count}</dd></div>
        <div><dt>Observed lifespan</dt><dd>${durationText(cohort.median_observed_lifespan_seconds)} · n=${cohort.observed_lifespan_sample_count}</dd></div>
        <div><dt>Completed / censored</dt><dd>${cohort.completed_lifecycle_count} / ${cohort.censored_lifecycle_count}</dd></div>
        <div><dt>Migration confirmed</dt><dd>${rateText(cohort.migration_confirmation_incidence)}</dd></div>
        <div><dt>Time to migration</dt><dd>${durationText(cohort.median_time_to_migration_seconds)} · n=${cohort.time_to_migration_sample_count}</dd></div>
        <div><dt>Migration pressure</dt><dd>${rateText(cohort.migration_pressure_incidence)}</dd></div>
        <div><dt>Successor pressure</dt><dd>${rateText(cohort.successor_pressure_incidence)}</dd></div>
        <div><dt>Route integrity</dt><dd>${rateText(cohort.route_integrity_maintained)}</dd></div>
      </dl>
    </article>`;
  }

  function incrementalCohortsMarkup(cohorts) {
    return (cohorts || []).map(cohortMarkup).join("");
  }

  function policyDetailMarkup(policy, timestampFormatter) {
    const allowance = policy.formation_policy?.allowance_percent ?? "—";
    if (policy.formed === false) {
      return `<article class="policy-detail-card unformed"><h3>${escapeHtml(allowance)}% allowance</h3><p>No MRZ formed under this policy in the available symbol-route history.</p></article>`;
    }
    const activated = timestampFormatter(policy.activated_at) || "—";
    return `<article class="policy-detail-card">
      <h3>${escapeHtml(allowance)}% allowance</h3>
      <span class="status-badge ${statusClass(policy.durability_status)}">${escapeHtml(policy.durability_label)}</span>
      <dl class="compact-facts">
        <div><dt>Frozen MRZ</dt><dd>${escapeHtml(policy.mrz.lower)}–${escapeHtml(policy.mrz.upper)}</dd></div>
        <div><dt>Midpoint</dt><dd>${escapeHtml(policy.mrz.midpoint)}</dd></div>
        <div><dt>Activated</dt><dd>${escapeHtml(activated)}</dd></div>
        <div><dt>Post observations</dt><dd>${policy.post_activation_observation_count}</dd></div>
        <div><dt>Containment</dt><dd>${percentageText(policy.containment.percentage)}</dd></div>
        <div><dt>Observed lifespan</dt><dd>${durationText(policy.observed_lifespan_seconds)} · ${policy.lifecycle.censored ? "censored" : "completed"}</dd></div>
        <div><dt>Migration</dt><dd>${policy.lifecycle.completed ? durationText(policy.lifecycle.time_to_migration_seconds) : "Not observed"}</dd></div>
        <div><dt>Boundary pressure</dt><dd>${policy.boundary_pressure.outside_envelope_observation_count} beyond envelope</dd></div>
        <div><dt>Midpoint stability</dt><dd>${escapeHtml(policy.midpoint_stability.label)} · ${percentageText(policy.midpoint_stability.median_signed_displacement_percentage_of_activation_ipda)}</dd></div>
        <div><dt>Route integrity</dt><dd>${escapeHtml(policy.route_integrity.status).replaceAll("_", " ")}</dd></div>
        <div><dt>Successor watch</dt><dd>${escapeHtml(policy.successor_watch.status).replaceAll("_", " ")}</dd></div>
      </dl>
    </article>`;
  }

  function symbolDetailMarkup(detail, timestampFormatter = (value) => value) {
    if (!detail) return '<p class="neutral">No MRZ formed under the evaluated policies.</p>';
    return `<div class="symbol-detail-heading"><h3>${escapeHtml(detail.symbol)}</h3><span>${escapeHtml(detail.route)} history · policies replayed independently</span></div><div class="policy-detail-grid">${detail.policies.map((policy) => policyDetailMarkup(policy, timestampFormatter)).join("")}</div>`;
  }

  function interpretationMarkup(interpretation) {
    const facts = (interpretation.facts || []).map((fact) => `<li>${escapeHtml(fact)}</li>`).join("");
    return `<article class="interpretation-card"><h3>${escapeHtml(interpretation.heading)}</h3><p>${escapeHtml(interpretation.text)}</p><ul>${facts}</ul></article>`;
  }

  function setupPage(documentRef, fetchImpl, timestampFormatter) {
    const refresh = documentRef.getElementById("refreshReport");
    const status = documentRef.getElementById("reportStatus");
    const content = documentRef.getElementById("reportContent");
    const selector = documentRef.getElementById("historySelect");
    let report = null;

    function showSymbolDetail() {
      const detail = report?.symbol_level_detail?.find((item) => item.history_id === selector.value);
      documentRef.getElementById("symbolDetail").innerHTML = symbolDetailMarkup(detail, timestampFormatter);
    }

    function render(payload) {
      report = payload;
      documentRef.getElementById("dataAsOf").textContent = payload.data_as_of ? `Data through ${timestampFormatter(payload.data_as_of) || "—"}` : "No observations";
      documentRef.getElementById("sampleConfidence").innerHTML = sampleConfidenceMarkup(payload.sample_confidence);
      documentRef.getElementById("productionSummary").innerHTML = productionSummaryMarkup(payload.current_production_robustness);
      documentRef.getElementById("crossSymbolTable").innerHTML = crossSymbolTableMarkup(payload.cross_symbol_robustness, timestampFormatter);
      documentRef.getElementById("pressureSummary").innerHTML = pressureSummaryMarkup(payload.migration_pressure_summary);
      documentRef.getElementById("policyComparisonTable").innerHTML = policyComparisonMarkup(payload.policy_robustness_comparison);
      documentRef.getElementById("incrementalCohorts").innerHTML = incrementalCohortsMarkup(payload.incremental_cohorts);
      documentRef.getElementById("evidenceInterpretation").innerHTML = interpretationMarkup(payload.evidence_interpretation);
      selector.innerHTML = (payload.symbol_level_detail || []).map((item) => `<option value="${escapeHtml(item.history_id)}">${escapeHtml(item.symbol)} · ${escapeHtml(item.route)}</option>`).join("");
      selector.disabled = !payload.symbol_level_detail?.length;
      showSymbolDetail();
      status.hidden = true;
      content.hidden = false;
    }

    async function load() {
      refresh.disabled = true;
      status.hidden = false;
      status.classList.remove("error");
      status.textContent = "Replaying post-activation durability…";
      try {
        const response = await fetchImpl("/api/diagnostics/mrz-robustness-report", { cache: "no-store" });
        if (!response.ok) throw new Error(`Report request failed (${response.status})`);
        render(await response.json());
      } catch (error) {
        status.classList.add("error");
        status.textContent = error.message;
        content.hidden = true;
      } finally {
        refresh.disabled = false;
      }
    }

    selector.addEventListener("change", showSymbolDetail);
    refresh.addEventListener("click", load);
    load();
    return { load, render, showSymbolDetail };
  }

  const exported = {
    crossSymbolTableMarkup,
    durationText,
    incrementalCohortsMarkup,
    interpretationMarkup,
    policyComparisonMarkup,
    pressureSummaryMarkup,
    productionSummaryMarkup,
    rateText,
    sampleConfidenceMarkup,
    setupPage,
    symbolDetailMarkup,
  };
  if (typeof module === "object" && module.exports) module.exports = exported;
  if (globalScope?.document) {
    globalScope.document.addEventListener("DOMContentLoaded", () => setupPage(
      globalScope.document,
      globalScope.fetch.bind(globalScope),
      globalScope.formatOperatorTimestampUtcMinus4,
    ));
  }
}(typeof globalThis !== "undefined" ? globalThis : this));
