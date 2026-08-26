(function registerHeatmapState(root) {
  const primaryLocationKeys = [
    "deep_discount",
    "shallow_discount",
    "shallow_premium",
    "deep_premium",
  ];

  const secondaryLocationKeys = [
    "below_ipda_range",
    "above_ipda_range",
    "unavailable",
  ];

  const allLocationKeys = new Set([...primaryLocationKeys, ...secondaryLocationKeys]);
  const premiumLocationKeys = new Set(["shallow_premium", "deep_premium"]);
  const discountLocationKeys = new Set(["shallow_discount", "deep_discount"]);
  const activityMaximum = 20;

  function hasActiveMrz(symbolState) {
    return symbolState.mrz_status === "active";
  }

  function safeActivityCount(value) {
    if (value == null || value === "") return null;
    const count = Number(value);
    if (!Number.isFinite(count) || count < 0) return null;
    return Math.min(Math.trunc(count), activityMaximum);
  }

  function activityTier(value) {
    const count = safeActivityCount(value);
    if (count == null || count === 0) return "none";
    if (count <= 3) return "low";
    if (count <= 7) return "medium";
    if (count <= 11) return "medium-high";
    if (count <= 15) return "high";
    return "strongest";
  }

  function routeAlignedObservationContext(symbolState) {
    const location = symbolState.current_price_location;
    let route;
    let observationType;
    let countField;
    if (premiumLocationKeys.has(location)) {
      route = "STR";
      observationType = "rejection";
      countField = "str_window_observation_count";
    } else if (discountLocationKeys.has(location)) {
      route = "BTD";
      observationType = "reclaim";
      countField = "btd_window_observation_count";
    } else {
      return null;
    }
    const count = safeActivityCount(symbolState[countField]);
    if (count == null) return null;
    return { count, route, observationType };
  }

  function routeAlignedObservationCount(symbolState) {
    return routeAlignedObservationContext(symbolState)?.count ?? null;
  }

  function concentrationCheckEligible(symbolState, minimumObservations) {
    // Count readiness only: this does not imply concentration, ownership, or an active MRZ.
    const minimum = Number(minimumObservations);
    if (!Number.isInteger(minimum) || minimum <= 0) return false;
    const btdCount = safeActivityCount(symbolState.btd_window_observation_count);
    const strCount = safeActivityCount(symbolState.str_window_observation_count);
    return (
      (btdCount != null && btdCount >= minimum)
      || (strCount != null && strCount >= minimum)
    );
  }

  function routeAlignedActivity(symbolState) {
    if (hasActiveMrz(symbolState)) return null;
    const context = routeAlignedObservationContext(symbolState);
    if (!context) return null;
    return { ...context, tier: activityTier(context.count) };
  }

  function activityTooltipText(countValue) {
    const count = safeActivityCount(countValue);
    if (count == null) return null;
    return `${count} observation${count === 1 ? "" : "s"}`;
  }

  function accessibleChipLabel(symbolState, locationLabel) {
    const symbol = symbolState.symbol;
    if (hasActiveMrz(symbolState)) {
      const owner = symbolState.route_owner ? `, route owner ${symbolState.route_owner}` : "";
      return `${symbol}, ${locationLabel}, MRZ active${owner}`;
    }
    const activity = routeAlignedActivity(symbolState);
    if (!activity) {
      return `${symbol}, ${locationLabel}, no qualifying concentration, MRZ unestablished`;
    }
    const observationNoun = activity.count === 1 ? "observation" : "observations";
    return `${symbol}, ${locationLabel}, ${activity.count} ${activity.route} ${activity.observationType} ${observationNoun}, no qualifying concentration, MRZ unestablished`;
  }

  function compareSymbolsByActivity(left, right) {
    const countDifference = (
      (routeAlignedObservationCount(right) ?? 0)
      - (routeAlignedObservationCount(left) ?? 0)
    );
    if (countDifference !== 0) return countDifference;
    return String(left.symbol).localeCompare(String(right.symbol));
  }

  function preservedSelectedSymbol(currentSymbol, symbols) {
    if (!currentSymbol) return "";
    return symbols.some((symbolState) => symbolState.symbol === currentSymbol) ? currentSymbol : "";
  }

  function groupSymbolsByLocation(symbols) {
    const groups = Object.fromEntries([...allLocationKeys].map((key) => [key, []]));
    symbols.forEach((symbolState) => {
      const currentLocation = symbolState.current_price_location;
      const key = allLocationKeys.has(currentLocation) ? currentLocation : "unavailable";
      groups[key].push(symbolState);
    });
    Object.values(groups).forEach((symbolsInGroup) => symbolsInGroup.sort(compareSymbolsByActivity));
    return groups;
  }

  const heatmapState = {
    primaryLocationKeys,
    secondaryLocationKeys,
    hasActiveMrz,
    activityTier,
    routeAlignedObservationCount,
    concentrationCheckEligible,
    routeAlignedActivity,
    activityTooltipText,
    accessibleChipLabel,
    compareSymbolsByActivity,
    preservedSelectedSymbol,
    groupSymbolsByLocation,
  };

  root.edgeHeatmapState = heatmapState;
  if (typeof module === "object" && module.exports) {
    module.exports = heatmapState;
  }
}(typeof globalThis === "object" ? globalThis : this));
