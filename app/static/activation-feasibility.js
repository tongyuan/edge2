function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
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

function percentagePointText(value) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return `${number.toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} percentage points`;
}

function historyLabel(count) {
  return Number(count) === 1 ? "history" : "histories";
}

function productionMarkup(rule) {
  const frequency = rule?.result?.activation_frequency || {};
  const formed = frequency.numerator ?? 0;
  const eligible = frequency.denominator ?? 0;
  return `
    <strong class="production-rule">Algorithm ${escapeHtml(rule?.algorithm || "—")} · ${rule?.minimum_observations ?? "—"} observations · ${percentageText(rule?.allowance_percent)}</strong>
    <div class="production-summary">
      <div>
        <span>OBSERVED FORMATION</span>
        <p class="production-outcome">${formed} of ${eligible} eligible symbol-route ${historyLabel(eligible)} formed an MRZ</p>
      </div>
      <strong class="production-rate">${frequencyPercentageText(frequency.percentage)}</strong>
    </div>`;
}

function currentNearMissMarkup(items, timestampFormatter = (value) => value) {
  if (!items?.length) {
    return '<p class="neutral empty-state">No current production near misses in the stored sample.</p>';
  }
  return `<div class="diagnostic-card-grid">${items.map((item) => {
    const timestamp = timestampFormatter(item.candidate_timestamp) || "—";
    const candidateRange = `${decimalText(item.candidate_lower_boundary, 12)}–${decimalText(item.candidate_upper_boundary, 12)}`;
    return `<article class="diagnostic-card near-miss-card">
      <h3>${escapeHtml(item.symbol)} · ${escapeHtml(item.route)}</h3>
      <dl>
        <div><dt>Current minimum allowance required</dt><dd>${percentageText(item.minimum_required_allowance_pct)}</dd></div>
        <div><dt>Current production allowance</dt><dd>${percentageText(item.configured_allowance_pct)}</dd></div>
        <div><dt>Shortfall</dt><dd>${percentagePointText(item.shortfall_percentage_points)}</dd></div>
        <div><dt>Candidate range</dt><dd>${candidateRange}</dd></div>
        <div><dt>Observation count</dt><dd>${item.candidate_observation_count} of ${item.total_stored_route_observations}</dd></div>
        <div><dt>Current candidate time</dt><dd>${escapeHtml(timestamp)}</dd></div>
      </dl>
    </article>`;
  }).join("")}</div>`;
}

function qualificationMarkup(activations, timestampFormatter = (value) => value) {
  if (!activations?.length) {
    return '<p class="neutral empty-state">No symbol-route history formed an MRZ under the current production rule in this sample.</p>';
  }
  return `<div class="diagnostic-card-grid">${activations.map((activation) => `
    <article class="diagnostic-card qualification-card">
      <h3>${escapeHtml(activation.symbol)} · ${escapeHtml(activation.route)}</h3>
      <dl>
        <div><dt>First qualifying MRZ</dt><dd>${decimalText(activation.core_mrz_lower, 12)}–${decimalText(activation.core_mrz_upper, 12)}</dd></div>
        <div><dt>First qualified</dt><dd>${escapeHtml(timestampFormatter(activation.activated_at) || "—")}</dd></div>
        <div><dt>Rule</dt><dd>${activation.minimum_observations} observations · ${percentageText(activation.allowance_percent)}</dd></div>
      </dl>
    </article>`).join("")}</div>`;
}

function productionSampleMarkup(report) {
  const rule = report?.current_production_rule || {};
  const frequency = rule.result?.activation_frequency || {};
  const formed = frequency.numerator ?? 0;
  const eligible = frequency.denominator ?? 0;
  const nearMissCount = report?.diagnosis?.current_production_near_misses?.length ?? 0;
  return `
    <dl class="sample-summary">
      <div><dt>Production rule</dt><dd>Algorithm ${escapeHtml(rule.algorithm || "—")} · ${rule.minimum_observations ?? "—"} observations · ${percentageText(rule.allowance_percent)}</dd></div>
      <div><dt>Eligible histories</dt><dd>${eligible}</dd></div>
      <div><dt>MRZ formations</dt><dd>${formed}</dd></div>
      <div><dt>Observed formation frequency</dt><dd>${frequencyPercentageText(frequency.percentage)}</dd></div>
      <div><dt>Current near misses</dt><dd>${nearMissCount}</dd></div>
    </dl>
    <p class="sample-interpretation">The current production rule formed an MRZ in ${formed} of ${eligible} eligible symbol-route ${historyLabel(eligible)} in the stored sample.</p>`;
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    const refreshButton = document.getElementById("refreshReport");
    const status = document.getElementById("reportStatus");
    const content = document.getElementById("reportContent");
    const sampleWarning = document.getElementById("sampleWarning");

    function renderReport(value) {
      document.getElementById("generatedAt").textContent = formatOperatorTimestampUtcMinus4(value.generated_at) || "—";
      const earliest = formatOperatorTimestampUtcMinus4(value.earliest_observation_at);
      const latest = formatOperatorTimestampUtcMinus4(value.latest_observation_at);
      document.getElementById("observationRange").textContent = earliest && latest ? `${earliest} → ${latest}` : "—";
      document.getElementById("totalObservations").textContent = value.total_observations_evaluated;
      document.getElementById("totalSymbols").textContent = value.total_normalized_symbols;
      document.getElementById("totalSequences").textContent = value.total_symbol_route_sequences;
      sampleWarning.hidden = !value.diagnosis?.sample_assessment?.small_sample;

      document.getElementById("productionContent").innerHTML = productionMarkup(value.current_production_rule);
      document.getElementById("currentNearMissContent").innerHTML = currentNearMissMarkup(
        value.diagnosis?.current_production_near_misses,
        formatOperatorTimestampUtcMinus4,
      );
      document.getElementById("qualificationContent").innerHTML = qualificationMarkup(
        value.current_production_rule?.activations,
        formatOperatorTimestampUtcMinus4,
      );
      document.getElementById("productionSampleContent").innerHTML = productionSampleMarkup(value);
    }

    async function loadReport() {
      refreshButton.disabled = true;
      status.hidden = false;
      status.classList.remove("error");
      status.textContent = "Calculating the latest diagnostics…";
      content.hidden = true;
      try {
        const response = await fetch("/api/diagnostics/activation-feasibility", { cache: "no-store" });
        if (!response.ok) throw new Error(`Report request failed (${response.status})`);
        renderReport(await response.json());
        status.hidden = true;
        content.hidden = false;
      } catch (error) {
        status.classList.add("error");
        status.textContent = `Unable to generate the diagnostics. ${error.message}`;
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
    currentNearMissMarkup,
    frequencyPercentageText,
    percentageText,
    productionMarkup,
    productionSampleMarkup,
    qualificationMarkup,
  };
}
