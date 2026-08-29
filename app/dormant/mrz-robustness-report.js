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

  function metricCard(label, value, note = "", extraClass = "") {
    return `<article class="metric-card ${extraClass}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong>${note ? `<p>${escapeHtml(note)}</p>` : ""}</article>`;
  }

  function sampleConfidenceMarkup(sample) {
    return `<div class="metric-grid">
      ${metricCard("Assessment", sample.label?.replace("Sample confidence · ", "") || "—", `${sample.eligible_symbol_route_histories} eligible histories`, "status-card")}
      ${metricCard("Eligible histories", sample.eligible_symbol_route_histories ?? 0, "Symbol-route histories with at least four observations")}
      ${metricCard("Production formations", sample.production_mrz_formations ?? 0, `of ${sample.production_formed_denominator ?? 0} eligible histories`)}
      ${metricCard("With post-activation evidence", sample.production_formations_with_post_activation_evidence ?? 0, "Strictly after production-policy activation")}
      ${metricCard("Resolved cases", sample.production_resolved_case_count ?? 0, "At least one supportive or adverse outcome")}
      ${metricCard("Unresolved cases", sample.production_unresolved_case_count ?? 0, "No resolved post-activation outcome")}
    </div>`;
  }

  function productionSummaryMarkup(summary) {
    return `<div class="metric-grid durability-grid">
      ${metricCard("Supportive outcomes", summary.supportive_outcome_count ?? 0, rateText(summary.supportive_rate), "supportive-card")}
      ${metricCard("Adverse outcomes", summary.adverse_outcome_count ?? 0, rateText(summary.adverse_rate), "adverse-card")}
      ${metricCard("Supportive : Adverse", summary.supportive_to_adverse_balance ?? "0 : 0", `${summary.resolved_outcome_count ?? 0} resolved outcomes`)}
      ${metricCard("Resolved cases", summary.resolved_case_count ?? 0, `${summary.unresolved_case_count ?? 0} unresolved · ${summary.formed_mrz_count ?? 0} formed`)}
      ${metricCard("First supportive", durationText(summary.median_time_to_first_supportive_seconds), `median · n=${summary.time_to_first_supportive_sample_count ?? 0}`)}
      ${metricCard("First adverse", durationText(summary.median_time_to_first_adverse_seconds), `median · n=${summary.time_to_first_adverse_sample_count ?? 0}`)}
      ${metricCard("Early adverse", rateText(summary.early_adverse_incidence), `research-only · first ${summary.early_adverse_window_observations ?? 4} observations`)}
      ${metricCard("Formation coverage", `${summary.formed_mrz_count ?? 0} of ${summary.eligible_symbol_route_histories ?? 0}`, `${percentageText(summary.formation_coverage?.percentage)} · selectivity context`, "context-card")}
    </div>`;
  }

  function crossSymbolTableMarkup(rows, timestampFormatter = (value) => value) {
    const body = (rows || []).map((row) => {
      const response = row.structural_response || {};
      return `<tr>
      <td><strong>${escapeHtml(row.symbol)}</strong><span class="secondary">${escapeHtml(row.route)}</span></td>
      <td>${escapeHtml(row.mrz.lower)}–${escapeHtml(row.mrz.upper)}<span class="secondary">${escapeHtml(row.mrz.structural_location).replaceAll("_", " ")}</span></td>
      <td>${escapeHtml(timestampFormatter(row.activated_at) || "—")}</td>
      <td>${row.post_activation_observation_count}</td>
      <td>${response.resolved_outcome_count ?? 0}</td>
      <td class="supportive-value">${response.supportive_outcome_count ?? 0}</td>
      <td class="adverse-value">${response.adverse_outcome_count ?? 0}</td>
      <td>${response.neutral_unresolved_outcome_count ?? 0}</td>
      <td>${escapeHtml(response.supportive_to_adverse_balance ?? "0 : 0")}</td>
      <td>${durationText(response.first_supportive?.seconds_from_activation)}<span class="secondary">${response.first_supportive?.observation_number ? `observation +${response.first_supportive.observation_number}` : "not observed"}</span></td>
      <td>${durationText(response.first_adverse?.seconds_from_activation)}<span class="secondary">${response.first_adverse?.observation_number ? `observation +${response.first_adverse.observation_number}` : "not observed"}</span></td>
    </tr>`;
    }).join("");
    const empty = '<tr><td colspan="11" class="neutral">No production-policy MRZ formed in the available sample.</td></tr>';
    return `<thead><tr><th>Symbol / Route</th><th>Frozen MRZ</th><th>Activated</th><th>Post observations</th><th>Resolved</th><th>Supportive</th><th>Adverse</th><th>Neutral</th><th>Balance</th><th>First supportive</th><th>First adverse</th></tr></thead><tbody>${body || empty}</tbody>`;
  }

  function pressureSummaryMarkup(summary) {
    const successor = summary.successor_watch || {};
    return `<div class="pressure-layout">
      <article class="pressure-group"><h3>MECHANICAL LIFECYCLE STATE · ${summary.formed_mrz_count ?? 0} FORMED MRZS</h3><div class="pressure-counts">
        <div><span>Stable</span><strong>${summary.stable ?? 0}</strong></div>
        <div><span>Under pressure</span><strong>${summary.under_pressure ?? 0}</strong></div>
        <div><span>Migration candidate</span><strong>${summary.migration_candidate ?? 0}</strong></div>
        <div><span>Not yet assessable</span><strong>${summary.not_yet_assessable ?? 0}</strong></div>
      </div></article>
      <article class="pressure-group"><h3>SUCCESSOR WATCH</h3><div class="pressure-counts">
        <div><span>No successor</span><strong>${successor.no_successor ?? 0}</strong></div>
        <div><span>External observations</span><strong>${successor.external_observations ?? 0}</strong></div>
        <div><span>No qualifying successor</span><strong>${successor.no_qualifying_successor ?? 0}</strong></div>
        <div><span>Candidate detected</span><strong>${successor.candidate_detected ?? 0}</strong></div>
      </div></article>
    </div>`;
  }

  function policyComparisonMarkup(rows) {
    const policies = rows || [];
    const cell = (row, value, note = "") => `<td class="${row === policies[0] ? "production-cell" : ""}">${value}${note ? `<span class="secondary">${note}</span>` : ""}</td>`;
    const metricRow = (label, render) => `<tr><th scope="row">${label}</th>${policies.map((row) => render(row)).join("")}</tr>`;
    const body = [
      metricRow("Formation coverage · context only", (row) => cell(row, `${row.formed_mrz_count} of ${row.eligible_symbol_route_histories}`, percentageText(row.formation_coverage.percentage))),
      metricRow("With post-activation evidence", (row) => cell(row, `${row.formations_with_post_activation_evidence} of ${row.formed_mrz_count}`)),
      metricRow("Resolved MRZ cases", (row) => cell(row, `${row.resolved_case_count} of ${row.formed_mrz_count}`, `${row.unresolved_case_count} unresolved`)),
      metricRow("Supportive outcomes", (row) => cell(row, row.supportive_outcome_count, rateText(row.supportive_rate))),
      metricRow("Adverse outcomes", (row) => cell(row, row.adverse_outcome_count, rateText(row.adverse_rate))),
      metricRow("Supportive : Adverse", (row) => cell(row, escapeHtml(row.supportive_to_adverse_balance), `${row.resolved_outcome_count} resolved outcomes`)),
      metricRow("Median time to first supportive", (row) => cell(row, durationText(row.median_time_to_first_supportive_seconds), `n=${row.time_to_first_supportive_sample_count}`)),
      metricRow("Median time to first adverse", (row) => cell(row, durationText(row.median_time_to_first_adverse_seconds), `n=${row.time_to_first_adverse_sample_count}`)),
      metricRow("Early adverse · research only", (row) => cell(row, rateText(row.early_adverse_incidence), `first ${row.early_adverse_window_observations} post-activation observations`)),
    ].join("");
    const headings = policies.map((row, index) => `<th>${escapeHtml(row.allowance_percent)}%${index === 0 ? '<span class="secondary">production</span>' : ""}</th>`).join("");
    return `<thead><tr><th>Route-role durability</th>${headings}</tr></thead><tbody>${body}</tbody>`;
  }

  function lifecycleComparisonMarkup(rows) {
    const policies = rows || [];
    const cell = (row, value, note = "") => `<td class="${row === policies[0] ? "production-cell" : ""}">${value}${note ? `<span class="secondary">${note}</span>` : ""}</td>`;
    const metricRow = (label, render) => `<tr><th scope="row">${label}</th>${policies.map((row) => render(row)).join("")}</tr>`;
    const body = [
      metricRow("Median containment", (row) => cell(row, percentageText(row.median_containment_percentage), `n=${row.containment_sample_count}`)),
      metricRow("Median observed lifespan", (row) => cell(row, durationText(row.median_observed_lifespan_seconds), `n=${row.observed_lifespan_sample_count} · ${row.completed_lifecycle_count} completed · ${row.censored_lifecycle_count} censored`)),
      metricRow("Median time to migration", (row) => cell(row, durationText(row.median_time_to_migration_seconds), `n=${row.time_to_migration_sample_count}`)),
      metricRow("Migration confirmed", (row) => cell(row, rateText(row.migration_confirmation_incidence))),
      metricRow("Early migration", (row) => cell(row, rateText(row.early_migration_incidence))),
      metricRow("Migration pressure", (row) => cell(row, rateText(row.migration_pressure_incidence), `median first pressure ${durationText(row.median_time_to_first_pressure_seconds)} · n=${row.time_to_first_pressure_sample_count}`)),
      metricRow("Successor pressure", (row) => cell(row, rateText(row.successor_pressure_incidence))),
      metricRow("Structural-location alignment", (row) => cell(row, rateText(row.route_integrity_maintained), "legacy route-integrity context")),
    ].join("");
    const headings = policies.map((row, index) => `<th>${escapeHtml(row.allowance_percent)}%${index === 0 ? '<span class="secondary">production</span>' : ""}</th>`).join("");
    return `<thead><tr><th>Mechanical persistence / lifecycle</th>${headings}</tr></thead><tbody>${body}</tbody>`;
  }

  function routeBreakdownMarkup(rows) {
    const policies = rows || [];
    const headings = policies.map((row) => `<th>${escapeHtml(row.allowance_percent)}%</th>`).join("");
    const metricRow = (route, label, render) => `<tr><th scope="row"><strong>${route}</strong><span class="secondary">${label}</span></th>${policies.map((policy) => {
      const routeData = (policy.route_breakdown || []).find((item) => item.route === route) || {};
      return `<td>${render(routeData)}</td>`;
    }).join("")}</tr>`;
    const body = [
      metricRow("BTD", "Resolved cases", (row) => `${row.resolved_case_count ?? 0} resolved · ${row.unresolved_case_count ?? 0} unresolved`),
      metricRow("BTD", "Supportive / adverse", (row) => `${rateText(row.supportive_rate)}<span class="secondary">adverse ${rateText(row.adverse_rate)}</span>`),
      metricRow("STR", "Resolved cases", (row) => `${row.resolved_case_count ?? 0} resolved · ${row.unresolved_case_count ?? 0} unresolved`),
      metricRow("STR", "Supportive / adverse", (row) => `${rateText(row.supportive_rate)}<span class="secondary">adverse ${rateText(row.adverse_rate)}</span>`),
    ].join("");
    return `<thead><tr><th>Route / evidence</th>${headings}</tr></thead><tbody>${body}</tbody>`;
  }

  function cohortMarkup(cohort) {
    return `<article class="cohort-card">
      <h3>${escapeHtml(cohort.label)}</h3>
      <p class="cohort-definition">${escapeHtml(cohort.definition)}</p>
      <div class="cohort-count"><strong>${cohort.history_count}</strong><span>symbol-route histories</span></div>
      <dl class="compact-facts">
        <div><dt>With post-activation evidence</dt><dd>${cohort.formations_with_post_activation_evidence} / ${cohort.history_count}</dd></div>
        <div><dt>Resolved / unresolved cases</dt><dd>${cohort.resolved_case_count} / ${cohort.unresolved_case_count}</dd></div>
        <div><dt>Supportive outcomes</dt><dd>${cohort.supportive_outcome_count} · ${rateText(cohort.supportive_rate)}</dd></div>
        <div><dt>Adverse outcomes</dt><dd>${cohort.adverse_outcome_count} · ${rateText(cohort.adverse_rate)}</dd></div>
        <div><dt>Supportive : Adverse</dt><dd>${escapeHtml(cohort.supportive_to_adverse_balance)}</dd></div>
        <div><dt>First supportive</dt><dd>${durationText(cohort.median_time_to_first_supportive_seconds)} · n=${cohort.time_to_first_supportive_sample_count}</dd></div>
        <div><dt>First adverse</dt><dd>${durationText(cohort.median_time_to_first_adverse_seconds)} · n=${cohort.time_to_first_adverse_sample_count}</dd></div>
        <div><dt>Early adverse</dt><dd>${rateText(cohort.early_adverse_incidence)}</dd></div>
      </dl>
      <details class="lifecycle-details"><summary>Mechanical persistence / lifecycle</summary><dl class="compact-facts">
        <div><dt>Median containment</dt><dd>${percentageText(cohort.median_containment_percentage)} · n=${cohort.containment_sample_count}</dd></div>
        <div><dt>Observed lifespan</dt><dd>${durationText(cohort.median_observed_lifespan_seconds)} · n=${cohort.observed_lifespan_sample_count}</dd></div>
        <div><dt>Completed / censored</dt><dd>${cohort.completed_lifecycle_count} / ${cohort.censored_lifecycle_count}</dd></div>
        <div><dt>Migration pressure</dt><dd>${rateText(cohort.migration_pressure_incidence)}</dd></div>
        <div><dt>Successor pressure</dt><dd>${rateText(cohort.successor_pressure_incidence)}</dd></div>
      </dl></details>
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
    const response = policy.structural_response || {};
    return `<article class="policy-detail-card">
      <h3>${escapeHtml(allowance)}% allowance</h3>
      <div class="response-balance"><span>Supportive</span><strong>${response.supportive_outcome_count ?? 0}</strong><span>Adverse</span><strong>${response.adverse_outcome_count ?? 0}</strong></div>
      <dl class="compact-facts">
        <div><dt>Frozen MRZ</dt><dd>${escapeHtml(policy.mrz.lower)}–${escapeHtml(policy.mrz.upper)}</dd></div>
        <div><dt>Midpoint</dt><dd>${escapeHtml(policy.mrz.midpoint)}</dd></div>
        <div><dt>Activated</dt><dd>${escapeHtml(activated)}</dd></div>
        <div><dt>Post observations</dt><dd>${policy.post_activation_observation_count}</dd></div>
        <div><dt>Resolved / neutral outcomes</dt><dd>${response.resolved_outcome_count ?? 0} / ${response.neutral_unresolved_outcome_count ?? 0}</dd></div>
        <div><dt>Supportive rate</dt><dd>${rateText(response.supportive_rate)}</dd></div>
        <div><dt>Adverse rate</dt><dd>${rateText(response.adverse_rate)}</dd></div>
        <div><dt>Supportive : Adverse</dt><dd>${escapeHtml(response.supportive_to_adverse_balance ?? "0 : 0")}</dd></div>
        <div><dt>First supportive</dt><dd>${durationText(response.first_supportive?.seconds_from_activation)}</dd></div>
        <div><dt>First adverse</dt><dd>${durationText(response.first_adverse?.seconds_from_activation)}</dd></div>
      </dl>
      <p class="detail-label lifecycle-label">Mechanical persistence / lifecycle</p>
      <dl class="compact-facts">
        <div><dt>Containment</dt><dd>${percentageText(policy.containment.percentage)}</dd></div>
        <div><dt>Observed lifespan</dt><dd>${durationText(policy.observed_lifespan_seconds)} · ${policy.lifecycle.censored ? "censored" : "completed"}</dd></div>
        <div><dt>Migration</dt><dd>${policy.lifecycle.completed ? durationText(policy.lifecycle.time_to_migration_seconds) : "Not observed"}</dd></div>
        <div><dt>Boundary pressure</dt><dd>${policy.boundary_pressure.outside_envelope_observation_count} beyond envelope</dd></div>
        <div><dt>Midpoint stability</dt><dd>${escapeHtml(policy.midpoint_stability.label)} · ${percentageText(policy.midpoint_stability.median_signed_displacement_percentage_of_activation_ipda)}</dd></div>
        <div><dt>Structural-location alignment</dt><dd>${escapeHtml(policy.route_integrity.status).replaceAll("_", " ")}</dd></div>
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
      documentRef.getElementById("routeBreakdownTable").innerHTML = routeBreakdownMarkup(payload.policy_robustness_comparison);
      documentRef.getElementById("lifecycleComparisonTable").innerHTML = lifecycleComparisonMarkup(payload.policy_robustness_comparison);
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
    lifecycleComparisonMarkup,
    policyComparisonMarkup,
    pressureSummaryMarkup,
    productionSummaryMarkup,
    rateText,
    routeBreakdownMarkup,
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
