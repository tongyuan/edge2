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

  function buildEvidencePresentation(state) {
    if (state.mrz_status === "active") {
      const count = countValue(state.supporting_observation_count);
      const type = state.route_owner === "STR" ? "rejection" : "reclaim";
      const duration = formatFormationDuration(state.formation_duration_seconds);
      return {
        primary: `${count} qualifying ${type} observation${count === 1 ? "" : "s"}`,
        secondary: duration ? [`Formation duration · ${duration}`] : [],
      };
    }

    const btdCount = countValue(state.btd_window_observation_count);
    const strCount = countValue(state.str_window_observation_count);
    const secondary = btdCount + strCount === 0 ? [] : [
      `BTD · ${observationCount(btdCount, "reclaim")}`,
      `STR · ${observationCount(strCount, "rejection")}`,
    ];
    return {
      primary: "No qualifying concentration",
      secondary,
    };
  }

  function formatLatestObservationContext(state, timestampFormatter) {
    const timestamp = timestampFormatter(state.latest_observed_at);
    if (!timestamp || !state.latest_observation_route || !state.latest_observation_type) return null;
    return `${state.latest_observation_route} ${state.latest_observation_type} · ${timestamp}`;
  }

  const monitorPresentation = {
    formatFormationDuration,
    buildEvidencePresentation,
    formatLatestObservationContext,
  };

  root.edgeMonitorPresentation = monitorPresentation;
  if (typeof module === "object" && module.exports) {
    module.exports = monitorPresentation;
  }
}(typeof globalThis === "object" ? globalThis : this));
