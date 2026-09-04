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
    return `<article class="diagnostic-card near-miss-card" data-near-miss-symbol="${escapeHtml(item.symbol)}" data-near-miss-route="${escapeHtml(item.route)}" data-candidate-identity="${escapeHtml(item.candidate_identity)}">
      <h3>${escapeHtml(item.symbol)} · ${escapeHtml(item.route)}</h3>
      <dl>
        <div><dt>Current minimum allowance required</dt><dd>${percentageText(item.minimum_required_allowance_pct)}</dd></div>
        <div><dt>Current production allowance</dt><dd>${percentageText(item.configured_allowance_pct)}</dd></div>
        <div><dt>Shortfall</dt><dd>${percentagePointText(item.shortfall_percentage_points)}</dd></div>
        <div><dt>Candidate range</dt><dd>${candidateRange}</dd></div>
        <div><dt>Midpoint</dt><dd>${decimalText(item.candidate_midpoint, 12)}</dd></div>
        <div><dt>Observation count</dt><dd>${item.candidate_observation_count} of ${item.total_stored_route_observations}</dd></div>
        <div><dt>Current candidate time</dt><dd>${escapeHtml(timestamp)}</dd></div>
      </dl>
      <button type="button" class="promote-near-miss" data-symbol="${escapeHtml(item.symbol)}" data-route="${escapeHtml(item.route)}" data-candidate-identity="${escapeHtml(item.candidate_identity)}">Promote to Active MRZ</button>
    </article>`;
  }).join("")}</div>`;
}

function promotionConfirmationMarkup(item, timestampFormatter = (value) => value) {
  return `<div class="promotion-confirmation-copy">
    <p>This exact candidate will become authoritative through an operator override.</p>
    <dl>
      <div><dt>Route</dt><dd>${escapeHtml(item.route)}</dd></div>
      <div><dt>Candidate</dt><dd>${decimalText(item.candidate_lower_boundary, 12)}–${decimalText(item.candidate_upper_boundary, 12)}</dd></div>
      <div><dt>Midpoint</dt><dd>${decimalText(item.candidate_midpoint, 12)}</dd></div>
      <div><dt>Minimum allowance required</dt><dd>${percentageText(item.minimum_required_allowance_pct)}</dd></div>
      <div><dt>Production threshold</dt><dd>${percentageText(item.configured_allowance_pct)}</dd></div>
      <div><dt>Shortfall</dt><dd>${percentagePointText(item.shortfall_percentage_points)}</dd></div>
      <div><dt>Supporting observations</dt><dd>${item.candidate_observation_count}</dd></div>
      <div><dt>Production status</dt><dd>Near miss</dd></div>
      <div><dt>Candidate time</dt><dd>${escapeHtml(timestampFormatter(item.candidate_timestamp) || "—")}</dd></div>
    </dl>
  </div>`;
}

function nearMissTargetFromSearch(search = "") {
  const parameters = new URLSearchParams(search);
  const symbol = parameters.get("symbol");
  const candidateIdentity = parameters.get("candidate");
  if (!/^[A-Z0-9][A-Z0-9:._-]{0,39}$/.test(symbol || "")) return null;
  if (!/^[a-f0-9]{64}$/.test(candidateIdentity || "")) return null;
  return { symbol, candidateIdentity };
}

async function submitPromotion(item, fetchImpl = fetch) {
  const response = await fetchImpl(
    `/api/diagnostics/activation-feasibility/near-misses/${encodeURIComponent(item.symbol)}/promote`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        route: item.route,
        candidate_identity: item.candidate_identity,
      }),
    },
  );
  const payload = await response.json();
  if (!response.ok) {
    const detail = payload.detail;
    const message = typeof detail === "object" ? detail?.message : detail;
    throw new Error(message || "EDGE could not promote this candidate.");
  }
  return payload;
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
    const currentNearMissContent = document.getElementById("currentNearMissContent");
    const promotionDialog = document.getElementById("promotionDialog");
    const promotionTitle = document.getElementById("promotionTitle");
    const promotionDetails = document.getElementById("promotionDetails");
    const promotionError = document.getElementById("promotionError");
    const confirmPromotion = document.getElementById("confirmPromotion");
    const promotionOutcome = document.getElementById("promotionOutcome");
    let report = null;
    let pendingPromotion = null;

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

    function showPromotionOutcome(message, symbol) {
      promotionOutcome.hidden = false;
      promotionOutcome.innerHTML = `<strong>${escapeHtml(message)}</strong> <a href="/?symbol=${encodeURIComponent(symbol)}">Open current ${escapeHtml(symbol)} state</a>`;
    }

    function focusNearMissDeepLink() {
      const target = nearMissTargetFromSearch(globalThis.location?.search || "");
      if (!target) return;
      const current = report?.diagnosis?.current_production_near_misses || [];
      const latest = current.find((item) => item.symbol === target.symbol);
      if (!latest) {
        showPromotionOutcome(
          `${target.symbol} is no longer a current production near miss. The episode changed or resolved.`,
          target.symbol,
        );
        document.getElementById("current-production-near-misses")?.scrollIntoView({ block: "center" });
        return;
      }
      const card = [...document.querySelectorAll("#current-production-near-misses .near-miss-card")]
        .find((item) => item.dataset.nearMissSymbol === target.symbol);
      if (!card) return;
      card.classList.add("focused-near-miss");
      card.tabIndex = -1;
      card.scrollIntoView({ block: "center" });
      card.focus({ preventScroll: true });
      if (latest.candidate_identity !== target.candidateIdentity) {
        showPromotionOutcome(
          `${target.symbol}'s near-miss candidate changed. Showing the latest candidate.`,
          target.symbol,
        );
      }
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
        focusNearMissDeepLink();
      } catch (error) {
        status.classList.add("error");
        status.textContent = `Unable to generate the diagnostics. ${error.message}`;
      } finally {
        refreshButton.disabled = false;
      }
    }

    currentNearMissContent.addEventListener("click", (event) => {
      const button = event.target.closest(".promote-near-miss");
      if (!button || !report) return;
      pendingPromotion = (report.diagnosis?.current_production_near_misses || []).find(
        (item) => item.symbol === button.dataset.symbol
          && item.route === button.dataset.route
          && item.candidate_identity === button.dataset.candidateIdentity,
      ) || null;
      if (!pendingPromotion) return;
      promotionTitle.textContent = `PROMOTE ${pendingPromotion.symbol} TO ACTIVE MRZ?`;
      promotionDetails.innerHTML = promotionConfirmationMarkup(
        pendingPromotion,
        formatOperatorTimestampUtcMinus4,
      );
      promotionError.hidden = true;
      confirmPromotion.disabled = false;
      if (typeof promotionDialog.showModal === "function") promotionDialog.showModal();
      else promotionDialog.setAttribute("open", "");
    });
    confirmPromotion.addEventListener("click", async () => {
      if (!pendingPromotion) return;
      confirmPromotion.disabled = true;
      promotionError.hidden = true;
      try {
        const result = await submitPromotion(pendingPromotion, fetch.bind(globalThis));
        const symbol = pendingPromotion.symbol;
        if (typeof promotionDialog.close === "function") promotionDialog.close();
        else promotionDialog.removeAttribute("open");
        pendingPromotion = null;
        await loadReport();
        showPromotionOutcome(
          result.duplicate
            ? `${symbol} was already promoted to authoritative MRZ.`
            : `${symbol} promoted to authoritative MRZ.`,
          symbol,
        );
      } catch (error) {
        promotionError.textContent = error.message;
        promotionError.hidden = false;
        confirmPromotion.disabled = false;
        await loadReport();
      }
    });
    refreshButton.addEventListener("click", loadReport);
    loadReport();
  });
}

if (typeof module === "object" && module.exports) {
  module.exports = {
    currentNearMissMarkup,
    frequencyPercentageText,
    nearMissTargetFromSearch,
    percentageText,
    productionMarkup,
    productionSampleMarkup,
    promotionConfirmationMarkup,
    qualificationMarkup,
    submitPromotion,
  };
}
