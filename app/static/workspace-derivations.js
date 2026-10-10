(function edgeWorkspaceDerivations(globalObject) {
  "use strict";

  const EVENT_PRIORITY = {
    MRZ_ACTIVATED: 4,
    MRZ_MIGRATED: 3,
    POST_ACTIVATION_PRESSURE_CHANGED: 2,
    MRZ_NEAR_MISS: 1,
  };
  const SYMBOL_BOARD_SORTS = new Set([
    "attention",
    "latest_event",
    "activation_age",
    "pressure",
    "structural_location",
    "symbol",
  ]);
  const SYMBOL_BOARD_SORT_STORAGE_KEY = "edge2.mrz.symbol-board.sort";
  const SYMBOL_BOARD_GROUPS = [
    { key: "changed_today", label: "Changed today" },
    { key: "directional_pressure", label: "Directional pressure" },
    { key: "stable", label: "Stable / no recent change" },
  ];
  const STRUCTURAL_LOCATION_PRIORITY = {
    deep_discount: 0,
    deep_discount_core_mrz: 0,
    shallow_discount: 1,
    shallow_discount_core_mrz: 1,
    at_eqm: 2,
    shallow_premium: 3,
    shallow_premium_core_mrz: 3,
    deep_premium: 4,
    deep_premium_core_mrz: 4,
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

  function normalizeSymbolBoardSort(value) {
    return SYMBOL_BOARD_SORTS.has(value) ? value : "attention";
  }

  function restoreSymbolBoardSort(storage) {
    try {
      return normalizeSymbolBoardSort(storage?.getItem(SYMBOL_BOARD_SORT_STORAGE_KEY));
    } catch {
      return "attention";
    }
  }

  function persistSymbolBoardSort(storage, value) {
    const normalized = normalizeSymbolBoardSort(value);
    try {
      storage?.setItem(SYMBOL_BOARD_SORT_STORAGE_KEY, normalized);
    } catch {
      // Sorting remains available for this page load when storage is blocked.
    }
    return normalized;
  }

  function timestamp(value) {
    const resolved = new Date(value).getTime();
    return Number.isFinite(resolved) ? resolved : Number.NEGATIVE_INFINITY;
  }

  function operatorDay(value, utcOffsetMinutes = -240) {
    const resolved = timestamp(value);
    if (!Number.isFinite(resolved)) return null;
    return new Date(resolved + (utcOffsetMinutes * 60 * 1000))
      .toISOString()
      .slice(0, 10);
  }

  function isMeaningfulBoardEvent(event) {
    return [
      "MRZ_MIGRATED",
      "POST_ACTIVATION_PRESSURE_CHANGED",
      "MRZ_ACTIVATED",
    ].includes(event?.event_type);
  }

  function symbolBoardGroup(row, options = {}) {
    const now = options.now || new Date();
    const utcOffsetMinutes = options.utcOffsetMinutes ?? -240;
    if (
      isMeaningfulBoardEvent(row.latestEvent)
      && operatorDay(row.latestEvent.occurred_at, utcOffsetMinutes)
        === operatorDay(now, utcOffsetMinutes)
    ) return "changed_today";
    if (row.pressure === "higher" || row.pressure === "lower") {
      return "directional_pressure";
    }
    return "stable";
  }

  function compareSymbol(left, right) {
    return String(left.symbol || "").localeCompare(String(right.symbol || ""));
  }

  function compareNewest(leftValue, rightValue) {
    return timestamp(rightValue) - timestamp(leftValue);
  }

  function attentionEventPriority(event) {
    return {
      MRZ_MIGRATED: 0,
      POST_ACTIVATION_PRESSURE_CHANGED: 1,
      MRZ_ACTIVATED: 2,
    }[event?.event_type] ?? 3;
  }

  function pressurePriority(direction) {
    return { higher: 0, neutral: 1, lower: 2 }[direction] ?? 3;
  }

  function directionalPriority(direction) {
    return direction === "higher" || direction === "lower" ? 0 : 1;
  }

  function attentionComparator(left, right, options) {
    const groupPriority = {
      changed_today: 0,
      directional_pressure: 1,
      stable: 2,
    };
    const leftGroup = symbolBoardGroup(left, options);
    const rightGroup = symbolBoardGroup(right, options);
    const groupOrder = groupPriority[leftGroup] - groupPriority[rightGroup];
    if (groupOrder) return groupOrder;
    if (leftGroup === "changed_today") {
      const eventOrder = attentionEventPriority(left.latestEvent)
        - attentionEventPriority(right.latestEvent);
      if (eventOrder) return eventOrder;
      if (
        left.latestEvent?.event_type === "POST_ACTIVATION_PRESSURE_CHANGED"
        && right.latestEvent?.event_type === "POST_ACTIVATION_PRESSURE_CHANGED"
      ) {
        const directionOrder = directionalPriority(left.pressure)
          - directionalPriority(right.pressure);
        if (directionOrder) return directionOrder;
      }
    }
    if (leftGroup === "stable") {
      const activeOrder = Number(right.active) - Number(left.active);
      if (activeOrder) return activeOrder;
    }
    return compareNewest(
      left.latestEvent?.occurred_at,
      right.latestEvent?.occurred_at,
    ) || compareSymbol(left, right);
  }

  function sortSymbolBoardRows(rows, sort = "attention", options = {}) {
    const normalized = normalizeSymbolBoardSort(sort);
    const comparators = {
      attention: (left, right) => attentionComparator(left, right, options),
      latest_event: (left, right) => compareNewest(
        left.latestEvent?.occurred_at,
        right.latestEvent?.occurred_at,
      ) || compareSymbol(left, right),
      activation_age: (left, right) => compareNewest(
        left.activatedAt,
        right.activatedAt,
      ) || compareSymbol(left, right),
      pressure: (left, right) => pressurePriority(left.pressure)
        - pressurePriority(right.pressure)
        || compareSymbol(left, right),
      structural_location: (left, right) => (
        (STRUCTURAL_LOCATION_PRIORITY[left.location] ?? 99)
        - (STRUCTURAL_LOCATION_PRIORITY[right.location] ?? 99)
        || compareSymbol(left, right)
      ),
      symbol: compareSymbol,
    };
    return [...(rows || [])].sort(comparators[normalized]);
  }

  function groupSymbolBoardRows(rows, options = {}) {
    const grouped = new Map(SYMBOL_BOARD_GROUPS.map(({ key }) => [key, []]));
    (rows || []).forEach((row) => grouped.get(symbolBoardGroup(row, options)).push(row));
    return SYMBOL_BOARD_GROUPS
      .map(({ key, label }) => ({ key, label, rows: grouped.get(key) }))
      .filter((group) => group.rows.length > 0);
  }

  function deriveBreadthLeadership(history = {}, pressureReport = {}) {
    const pressureBySymbol = new Map();
    Object.entries(pressureReport.categories || {}).forEach(([direction, members]) => {
      (members || []).forEach((member) => pressureBySymbol.set(member.symbol, direction));
    });
    const migrationBySymbol = new Map();
    (history.migration_events || []).forEach((event) => {
      if (event.direction !== "higher" && event.direction !== "lower") return;
      if (!migrationBySymbol.has(event.symbol)) migrationBySymbol.set(event.symbol, []);
      migrationBySymbol.get(event.symbol).push(event);
    });
    function migrationState(symbol) {
      const events = migrationBySymbol.get(symbol) || [];
      const directions = new Set(events.map((event) => event.direction));
      const state = directions.size > 1
        ? "mixed"
        : directions.has("higher") ? "up_only"
          : directions.has("lower") ? "down_only" : "none";
      return {
        state,
        events,
        latestAt: events.reduce((latest, event) => (
          timestamp(event.occurred_at) > timestamp(latest) ? event.occurred_at : latest
        ), null),
      };
    }
    const movements = (history.symbol_movements || []).map((movement) => {
      const migration = migrationState(movement.symbol);
      return {
        ...movement,
        pressure: pressureBySymbol.get(movement.symbol) || "neutral",
        migrationState: migration.state,
        migrationEvents: migration.events,
        latestRelevantAt: migration.latestAt || movement.current_observed_at || null,
      };
    });
    const confirmation = {
      higher: { higher: 0, neutral: 0, lower: 0 },
      lower: { higher: 0, neutral: 0, lower: 0 },
    };
    movements.forEach((movement) => {
      if (confirmation[movement.direction]) {
        confirmation[movement.direction][movement.pressure] += 1;
      }
    });
    function leadershipRows(direction, pressure, migrationDirection) {
      return movements
        .filter((movement) => movement.direction === direction && movement.pressure === pressure)
        .sort((left, right) => {
          const leftConfirmed = left.migrationEvents.some((event) => event.direction === migrationDirection);
          const rightConfirmed = right.migrationEvents.some((event) => event.direction === migrationDirection);
          return Number(rightConfirmed) - Number(leftConfirmed)
            || Number(right.magnitude || 0) - Number(left.magnitude || 0)
            || compareNewest(left.latestRelevantAt, right.latestRelevantAt)
            || compareSymbol(left, right);
        });
    }
    const migrationSymbols = { up_only: 0, down_only: 0, mixed: 0, none: 0 };
    migrationBySymbol.forEach((_events, symbol) => {
      migrationSymbols[migrationState(symbol).state] += 1;
    });
    migrationSymbols.none = Math.max(0, movements.length - movements.filter((movement) => migrationBySymbol.has(movement.symbol)).length);
    const flow = history.flow || {};
    const comparable = Number(flow.comparable_symbols || movements.length || 0);
    const moved = Number(flow.moved_higher || 0) + Number(flow.moved_lower || 0);
    return {
      window: history.window || "24H",
      universe: history.universe || {},
      breadth: {
        movedHigher: Number(flow.moved_higher || 0),
        movedLower: Number(flow.moved_lower || 0),
        unchanged: Number(flow.unchanged || 0),
        netHigher: Number(flow.net_higher || 0),
        comparable,
        participationPct: comparable ? (moved / comparable) * 100 : 0,
      },
      confirmation,
      confirmationRates: {
        higher: {
          numerator: confirmation.higher.higher,
          denominator: Number(flow.moved_higher || 0),
        },
        lower: {
          numerator: confirmation.lower.lower,
          denominator: Number(flow.moved_lower || 0),
        },
      },
      leaders: leadershipRows("higher", "higher", "higher"),
      laggards: leadershipRows("lower", "lower", "lower"),
      divergences: {
        higherWithLower: movements.filter((item) => item.direction === "higher" && item.pressure === "lower").sort(compareSymbol),
        lowerWithHigher: movements.filter((item) => item.direction === "lower" && item.pressure === "higher").sort(compareSymbol),
      },
      migrationBreadth: {
        ...migrationSymbols,
        uniqueSymbols: migrationBySymbol.size,
        eventCount: [...migrationBySymbol.values()].reduce((total, events) => total + events.length, 0),
      },
      currentLocationPressure: pressureReport.pressure_map?.locations || {},
      historicalPressureAvailable: false,
    };
  }

  const exported = {
    SYMBOL_BOARD_GROUPS,
    SYMBOL_BOARD_SORT_STORAGE_KEY,
    allGroupsRows,
    currentAuthorityRow,
    deriveAttention,
    deriveBreadthLeadership,
    eventDirection,
    eventLabel,
    groupMembership,
    latestEventsBySymbol,
    groupSymbolBoardRows,
    normalizeSymbolBoardSort,
    persistSymbolBoardSort,
    restoreSymbolBoardSort,
    sortSymbolBoardRows,
    symbolBoardGroup,
    symbolsForWatchlist,
    uniqueTrackedSymbols,
  };
  globalObject.edgeWorkspaceDerivations = exported;
  if (typeof module === "object" && module.exports) module.exports = exported;
}(globalThis));
