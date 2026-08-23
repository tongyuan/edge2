(function registerMonitorPresentation(root) {
  function countValue(value) {
    const count = Number(value);
    return Number.isFinite(count) && count >= 0 ? Math.trunc(count) : 0;
  }

  function observationCount(count, type) {
    return `${count} ${type} observation${count === 1 ? "" : "s"}`;
  }

  function formatFormationDuration(secondsValue) {
    if (secondsValue == null) return null;
    const seconds = Number(secondsValue);
    if (!Number.isFinite(seconds) || seconds < 0) return null;
    if (seconds === 0) return "0m";
    const totalMinutes = Math.floor(seconds / 60);
    if (totalMinutes === 0) return "<1m";
    const days = Math.floor(totalMinutes / 1440);
    const hours = Math.floor((totalMinutes % 1440) / 60);
    const minutes = totalMinutes % 60;
    if (days > 0) {
      if (hours > 0) return `${days}d ${hours}h`;
      if (minutes > 0) return `${days}d ${minutes}m`;
      return `${days}d`;
    }
    if (hours > 0) return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
    return `${minutes}m`;
  }

  function percentageText(value) {
    if (value === null || value === undefined || value === "") return "—";
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    return number.toLocaleString("en-GB", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  function buildConcentrationCheck(check, priceFormatter, locationFormatter) {
    const retainedCount = countValue(check.retained_observation_count);
    const selectedCount = countValue(check.selected_observation_count);
    const label = `CONCENTRATION CHECK · ${check.route}`;
    if (check.result === "INSUFFICIENT_OBSERVATIONS") {
      return {
        label,
        lines: [
          "Concentration check unavailable",
          `Minimum observations required · ${countValue(check.minimum_required_count)}`,
        ],
      };
    }
    if (check.result === "QUALIFIES") {
      return {
        label,
        lines: ["Concentration qualifies but no active MRZ is recorded"],
      };
    }

    const lines = [
      `Tightest eligible group · ${selectedCount} of ${retainedCount}`,
      `Price range · ${priceFormatter(check.selected_lower)}–${priceFormatter(check.selected_upper)}`,
      `Minimum allowance required · ${percentageText(check.minimum_required_allowance_pct)}%`,
      `Current allowance · ≤${percentageText(check.configured_allowance_pct)}%`,
    ];
    const difference = percentageText(Math.abs(Number(check.allowance_difference_pct_points)));
    if (check.allowance_comparison === "SHORTFALL") {
      lines.push(`Shortfall · ${difference} percentage points`);
    } else if (check.allowance_comparison === "MARGIN") {
      lines.push(`Margin · ${difference} percentage points inside`);
    } else if (check.allowance_comparison === "AT_THRESHOLD") {
      lines.push("Margin · At threshold");
    }
    lines.push(`Price span · ${priceFormatter(check.observed_span)}`);
    lines.push(`IPDA width · ${priceFormatter(check.ipda_width)}`);
    if (check.result === "STRUCTURALLY_INELIGIBLE") {
      lines.push(`Proposed location · ${locationFormatter(check.proposed_structural_location)}`);
      lines.push("Result · Structurally ineligible");
    } else {
      lines.push("Result · Too dispersed");
    }
    return { label, lines };
  }

  function buildEvidencePresentation(
    state,
    timestampFormatter = () => null,
    priceFormatter = (value) => String(value),
    locationFormatter = (value) => String(value),
  ) {
    if (state.mrz_status === "active") {
      const count = countValue(state.supporting_observation_count);
      const type = state.route_owner === "STR" ? "rejection" : "reclaim";
      const duration = formatFormationDuration(state.formation_duration_seconds);
      return {
        primary: `${count} qualifying ${type} observation${count === 1 ? "" : "s"}`,
        secondary: duration ? [`Formation duration · ${duration}`] : [],
        checks: [],
      };
    }

    const btdCount = countValue(state.btd_window_observation_count);
    const strCount = countValue(state.str_window_observation_count);
    const secondary = [];
    if (btdCount + strCount > 0) {
      secondary.push(`BTD · ${observationCount(btdCount, "reclaim")}`);
      const btdWindowStartedAt = timestampFormatter(state.btd_window_started_at);
      if (btdCount > 0 && btdWindowStartedAt) {
        secondary.push(`BTD window since · ${btdWindowStartedAt}`);
      }
      secondary.push(`STR · ${observationCount(strCount, "rejection")}`);
      const strWindowStartedAt = timestampFormatter(state.str_window_started_at);
      if (strCount > 0 && strWindowStartedAt) {
        secondary.push(`STR window since · ${strWindowStartedAt}`);
      }
    }
    const checkPayload = state.concentration_checks || {};
    const checks = ["BTD", "STR"]
      .map((route) => checkPayload[route])
      .filter((check) => check && countValue(check.retained_observation_count) > 0)
      .map((check) => buildConcentrationCheck(check, priceFormatter, locationFormatter));
    return {
      primary: "No qualifying concentration",
      secondary,
      checks,
    };
  }

  function formatLatestObservationContext(state, timestampFormatter) {
    const timestamp = timestampFormatter(state.latest_observed_at);
    if (!timestamp || !state.latest_observation_route || !state.latest_observation_type) return null;
    return `${state.latest_observation_route} ${state.latest_observation_type} · ${timestamp}`;
  }

  const monitorPresentation = {
    formatFormationDuration,
    percentageText,
    buildConcentrationCheck,
    buildEvidencePresentation,
    formatLatestObservationContext,
  };

  root.edgeMonitorPresentation = monitorPresentation;
  if (typeof module === "object" && module.exports) {
    module.exports = monitorPresentation;
  }
}(typeof globalThis === "object" ? globalThis : this));
