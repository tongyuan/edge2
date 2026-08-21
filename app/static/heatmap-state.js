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

  function hasActiveMrz(symbolState) {
    return symbolState.mrz_status === "active";
  }

  function groupSymbolsByLocation(symbols) {
    const groups = Object.fromEntries([...allLocationKeys].map((key) => [key, []]));
    symbols.forEach((symbolState) => {
      const currentLocation = symbolState.current_price_location;
      const key = allLocationKeys.has(currentLocation) ? currentLocation : "unavailable";
      groups[key].push(symbolState);
    });
    Object.values(groups).forEach((symbolsInGroup) => symbolsInGroup.sort(
      (left, right) => left.symbol.localeCompare(right.symbol),
    ));
    return groups;
  }

  const heatmapState = {
    primaryLocationKeys,
    secondaryLocationKeys,
    hasActiveMrz,
    groupSymbolsByLocation,
  };

  root.edgeHeatmapState = heatmapState;
  if (typeof module === "object" && module.exports) {
    module.exports = heatmapState;
  }
}(typeof globalThis === "object" ? globalThis : this));
