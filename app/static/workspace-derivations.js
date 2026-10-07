(function edgeWorkspaceDerivations(globalObject) {
  "use strict";

  const EVENT_PRIORITY = {
    MRZ_ACTIVATED: 4,
    MRZ_MIGRATED: 3,
    POST_ACTIVATION_PRESSURE_CHANGED: 2,
    MRZ_NEAR_MISS: 1,
  };

  function groupMembership(groups) {
    const membership = new Map();
    (groups || []).forEach((group) => {
      (group.members || []).forEach((symbol) => {
        if (!membership.has(symbol)) membership.set(symbol, []);
        membership.get(symbol).push(group);
      });
    });
    return membership;
  }

  function uniqueTrackedSymbols(groups) {
    return new Set((groups || []).flatMap((group) => group.members || []));
  }

  function symbolsForWatchlist(symbols, groups, selectedGroupId = "all") {
    const wanted = selectedGroupId === "all"
      ? uniqueTrackedSymbols(groups)
      : new Set(
        ((groups || []).find((group) => String(group.id) === String(selectedGroupId)) || {})
          .members || [],
      );
    return (symbols || []).filter((state) => wanted.has(state.symbol));
  }

  function eventDirection(event) {
    if (event.event_type === "POST_ACTIVATION_PRESSURE_CHANGED") {
      return event.current_state === "UP" ? "UP" : event.current_state === "DOWN" ? "DOWN" : null;
    }
    if (event.event_type !== "MRZ_MIGRATED") return null;
    const oldMidpoint = (Number(event.previous_mrz_lower) + Number(event.previous_mrz_upper)) / 2;
    const newMidpoint = (Number(event.mrz_lower) + Number(event.mrz_upper)) / 2;
    if (!Number.isFinite(oldMidpoint) || !Number.isFinite(newMidpoint)) return null;
    return newMidpoint > oldMidpoint ? "UP" : newMidpoint < oldMidpoint ? "DOWN" : null;
  }

  function eventLabel(event) {
    const direction = eventDirection(event);
    if (event.event_type === "MRZ_ACTIVATED") return "MRZ ACTIVATED";
    if (event.event_type === "MRZ_MIGRATED") return `MIGRATED ${direction === "UP" ? "↑" : direction === "DOWN" ? "↓" : ""}`.trim();
    if (event.event_type === "POST_ACTIVATION_PRESSURE_CHANGED") {
      return `PRESSURE ${direction === "UP" ? "↑" : direction === "DOWN" ? "↓" : "↔"}`;
    }
    if (event.event_type === "MRZ_NEAR_MISS") return "NEAR-MISS";
    return event.event_name || event.event_type || "EVENT";
  }

  function latestEventsBySymbol(events) {
    const result = new Map();
    [...(events || [])]
      .sort((left, right) => new Date(right.occurred_at) - new Date(left.occurred_at))
      .forEach((event) => {
        if (!result.has(event.symbol)) result.set(event.symbol, event);
      });
    return result;
  }

  function deriveAttention(events, groups, options = {}) {
    const tracked = uniqueTrackedSymbols(groups);
    const now = options.now ? new Date(options.now) : new Date();
    const maximumAgeMs = options.maximumAgeMs ?? 24 * 60 * 60 * 1000;
    return [...(events || [])]
      .filter((event) => tracked.has(event.symbol))
      .filter((event) => {
        const occurred = new Date(event.occurred_at);
        return Number.isFinite(occurred.getTime()) && now - occurred <= maximumAgeMs;
      })
      .sort((left, right) => {
        const time = new Date(right.occurred_at) - new Date(left.occurred_at);
        return time || (EVENT_PRIORITY[right.event_type] || 0) - (EVENT_PRIORITY[left.event_type] || 0);
      });
  }

  function allGroupsRows(events, groups) {
    const membership = groupMembership(groups);
    return deriveAttention(events, groups).flatMap((event) => (
      (membership.get(event.symbol) || []).map((group) => ({ event, group }))
    ));
  }

  function currentAuthorityRow(symbolState, pressure, latestEvent) {
    return {
      symbol: symbolState.symbol,
      active: symbolState.mrz_status === "active",
      lower: symbolState.core_mrz_lower,
      upper: symbolState.core_mrz_upper,
      route: symbolState.route_owner,
      activatedAt: symbolState.activated_at,
      location: symbolState.structural_location,
      pressure: pressure?.direction || "neutral",
      latestEvent: latestEvent || null,
    };
  }

  const exported = {
    allGroupsRows,
    currentAuthorityRow,
    deriveAttention,
    eventDirection,
    eventLabel,
    groupMembership,
    latestEventsBySymbol,
    symbolsForWatchlist,
    uniqueTrackedSymbols,
  };
  globalObject.edgeWorkspaceDerivations = exported;
  if (typeof module === "object" && module.exports) module.exports = exported;
}(globalThis));
