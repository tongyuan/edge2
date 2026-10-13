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
  const PEER_LOCATION_ORDER = [
    "deep_discount",
    "shallow_discount",
    "at_eqm",
    "shallow_premium",
    "deep_premium",
    "unavailable",
  ];

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

  function filterLocationSymbols(symbols, query) {
    const normalized = String(query || "").trim().toUpperCase();
    if (!normalized) return [...(symbols || [])];
    return (symbols || []).filter((symbol) => String(symbol || "").toUpperCase().includes(normalized));
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

  function groupPressureSourcesByAssetClass(sources) {
    const order = ["EQUITY", "ETF", "INDEX", "CRYPTO", "COMMODITY", "FX", "UNCLASSIFIED"];
    const grouped = new Map();
    (sources || []).forEach((source) => {
      const assetClass = source.asset_class || "UNCLASSIFIED";
      if (!grouped.has(assetClass)) grouped.set(assetClass, []);
      grouped.get(assetClass).push(source);
    });
    grouped.forEach((members) => members.sort(compareSymbol));
    return [...grouped.entries()]
      .sort(([left], [right]) => (
        (order.indexOf(left) < 0 ? order.length : order.indexOf(left))
        - (order.indexOf(right) < 0 ? order.length : order.indexOf(right))
        || left.localeCompare(right)
      ))
      .map(([assetClass, members]) => ({ assetClass, members }));
  }

  function derivePeerLocation(group = {}) {
    const currentBySymbol = new Map(
      (group.current_state?.members || []).map((item) => [item.symbol, item]),
    );
    const groups = new Map(PEER_LOCATION_ORDER.map((key) => [key, []]));
    (group.members || []).forEach((symbol) => {
      const current = currentBySymbol.get(symbol) || { symbol };
      const location = {
        deep_discount_core_mrz: "deep_discount",
        shallow_discount_core_mrz: "shallow_discount",
        shallow_premium_core_mrz: "shallow_premium",
        deep_premium_core_mrz: "deep_premium",
      }[current.current_location] || (
        PEER_LOCATION_ORDER.includes(current.current_location)
          ? current.current_location
          : "unavailable"
      );
      groups.get(location).push({
        symbol,
        current_location: location === "unavailable" ? null : location,
        route_owner: current.route_owner || null,
        has_active_mrz: Boolean(current.has_active_mrz),
      });
    });
    groups.forEach((members) => members.sort(compareSymbol));
    return PEER_LOCATION_ORDER.map((key) => ({ key, members: groups.get(key) }));
  }

  function derivePeerLocationFlow(history = {}, members = [], pressureReport = {}) {
    const wanted = new Set(members || []);
    const filtered = {
      ...history,
      symbol_movements: (history.symbol_movements || []).filter((item) => wanted.has(item.symbol)),
      migration_events: (history.migration_events || []).filter((item) => wanted.has(item.symbol)),
    };
    const details = deriveLocationFlowDetails(filtered, pressureReport);
    return {
      window: history.window || "24H",
      counts: {
        higher: details.higher.length,
        lower: details.lower.length,
        unchanged: details.unchanged.length,
      },
      comparable: details.higher.length + details.lower.length + details.unchanged.length,
      categories: details,
    };
  }

  function pressureDrilldownMembers(taxonomy = {}, pressure = {}, selection = {}) {
    const sourceIndex = new Map();
    Object.values(taxonomy.sources || {}).flat().forEach((item) => {
      sourceIndex.set(item.symbol, item);
    });
    let members = [];
    if (selection.type === "direction") {
      members = taxonomy.sources?.[selection.direction] || [];
    } else if (selection.type === "asset_class") {
      const group = (taxonomy.asset_classes || []).find((item) => item.name === selection.name);
      members = Object.values(group?.members || {}).flat();
    } else if (selection.type === "sector") {
      const group = (taxonomy.sectors || []).find((item) => item.name === selection.name);
      members = Object.values(group?.members || {}).flat();
    } else if (selection.type === "industry") {
      const group = (taxonomy.industries || []).find((item) => (
        item.name === selection.name && item.sector === selection.sector
      ));
      members = Object.values(group?.members || {}).flat();
    } else if (selection.type === "map") {
      members = (pressure.categories?.[selection.direction] || [])
        .filter((item) => item.current_location === selection.location)
        .map((item) => sourceIndex.get(item.symbol) || {
          symbol: item.symbol,
          direction: selection.direction,
          asset_class: null,
          sector: null,
          industry: null,
          current_location: item.current_location,
          current_location_label: item.current_location_label,
          route_owner: item.active_mrz?.route_owner || null,
          latest_pressure_observed_at: item.evidence?.latest_pressure_observed_at || null,
        });
    }
    const unique = new Map();
    members.forEach((member) => unique.set(member.symbol, member));
    const directionOrder = { higher: 0, neutral: 1, lower: 2 };
    return [...unique.values()].sort((left, right) => (
      (directionOrder[left.direction] ?? 3) - (directionOrder[right.direction] ?? 3)
      || compareSymbol(left, right)
    ));
  }

  function pressureConcentrationLabel(taxonomy = {}) {
    const counts = taxonomy.counts || {};
    const higher = taxonomy.concentration?.higher || {};
    const lower = taxonomy.concentration?.lower || {};
    const directional = Number(counts.higher || 0) + Number(counts.lower || 0);
    if (directional === 0 || directional <= Math.max(2, Number(taxonomy.included_equity_count || 0) * 0.15)) {
      return "Mostly neutral";
    }
    const balanced = Math.abs(Number(counts.higher || 0) - Number(counts.lower || 0)) <= 1;
    const higherConcentrated = Number(higher.top_sector_share_pct || 0) >= 50;
    const lowerConcentrated = Number(lower.top_sector_share_pct || 0) >= 50;
    if (balanced && higherConcentrated && lowerConcentrated && higher.top_sector !== lower.top_sector) {
      return "Balanced globally, sector-concentrated";
    }
    if (Number(counts.higher || 0) > Number(counts.lower || 0) && higherConcentrated) {
      return `Higher pressure concentrated in ${higher.top_sector}`;
    }
    if (Number(counts.lower || 0) > Number(counts.higher || 0) && lowerConcentrated) {
      return `Lower pressure concentrated in ${lower.top_sector}`;
    }
    return "Directional pressure broadly dispersed";
  }

  function contextualizeLocationMovements(history = {}, pressureReport = {}) {
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
    return { movements, migrationBySymbol, migrationState };
  }

  function deriveLocationFlowDetails(history = {}, pressureReport = {}) {
    const { movements } = contextualizeLocationMovements(history, pressureReport);
    function sorted(direction) {
      const confirmingPressure = direction === "higher" ? "higher" : direction === "lower" ? "lower" : null;
      return movements
        .filter((movement) => movement.direction === direction)
        .sort((left, right) => (
          Number(right.magnitude || 0) - Number(left.magnitude || 0)
          || (confirmingPressure
            ? Number(right.pressure === confirmingPressure) - Number(left.pressure === confirmingPressure)
            : 0)
          || (confirmingPressure
            ? Number(right.migrationEvents.some((event) => event.direction === direction))
              - Number(left.migrationEvents.some((event) => event.direction === direction))
            : 0)
          || compareSymbol(left, right)
        ));
    }
    return {
      higher: sorted("higher"),
      lower: sorted("lower"),
      unchanged: sorted("unchanged"),
    };
  }

  // Operator heuristics for descriptive research only. These deliberately avoid
  // confidence, probability, or trading implications.
  function participationLabel(value) {
    const percentage = Number(value || 0);
    if (percentage < 20) return "Narrow";
    if (percentage < 40) return "Limited";
    if (percentage <= 60) return "Moderate";
    return "Broad";
  }

  function confirmationLabel(numerator, denominator) {
    const sample = Number(denominator || 0);
    if (!sample || sample <= 2) return "Not applicable / insufficient";
    const percentage = (Number(numerator || 0) / sample) * 100;
    if (percentage < 25) return "Weak";
    if (percentage < 50) return "Partial";
    if (percentage <= 70) return "Moderate";
    return "Strong";
  }

  function structuralDirection(breadth) {
    const higher = Number(breadth?.movedHigher || 0);
    const lower = Number(breadth?.movedLower || 0);
    const movers = higher + lower;
    if (movers <= 2) return { key: "insufficient", label: "Insufficient breadth", imbalance: movers ? Math.abs(higher - lower) / movers : 0 };
    const imbalance = Math.abs(higher - lower) / movers;
    if (imbalance < 0.2) return { key: "balanced", label: "Balanced / Mixed", imbalance };
    return higher > lower
      ? { key: "higher", label: "Higher-skewed", imbalance }
      : { key: "lower", label: "Lower-skewed", imbalance };
  }

  function currentPressureCounts(report) {
    const totals = { higher: 0, neutral: 0, lower: 0 };
    Object.values(report.currentLocationPressure || {}).forEach((location) => {
      Object.keys(totals).forEach((key) => { totals[key] += Number(location?.counts?.[key] || 0); });
    });
    return totals;
  }

  function pressureRegime(counts) {
    const total = counts.higher + counts.neutral + counts.lower;
    if (!total) return { key: "insufficient", label: "Insufficient data" };
    if ((counts.neutral / total) >= 0.6) return { key: "neutral", label: "Mostly neutral" };
    if ((counts.higher / total) >= 0.4 && counts.higher >= counts.lower * 1.5) return { key: "higher", label: "Higher pressure dominant" };
    if ((counts.lower / total) >= 0.4 && counts.lower >= counts.higher * 1.5) return { key: "lower", label: "Lower pressure dominant" };
    return { key: "mixed", label: "Directionally mixed" };
  }

  function migrationSkew(migration, comparable) {
    const up = Number(migration?.up_only || 0);
    const down = Number(migration?.down_only || 0);
    const unique = Number(migration?.uniqueSymbols || 0);
    if (!unique) return { key: "none", label: "No meaningful migration activity", narrow: true };
    if (unique <= 2) return { key: "insufficient", label: "Sparse / insufficient breadth", narrow: true };
    const directional = up + down;
    const imbalance = directional ? Math.abs(up - down) / directional : 0;
    const narrow = !comparable || (unique / comparable) < 0.2;
    const key = !directional || imbalance < 0.2 ? "balanced" : up > down ? "upward" : "downward";
    const base = { balanced: "Balanced", upward: "Upward-skewed", downward: "Downward-skewed" }[key];
    return { key, label: `${base}${narrow ? " · narrow" : ""}`, narrow };
  }

  function researchNarrative({ report, direction, participation, confirmation, migration, pressure }) {
    const breadth = report.breadth;
    const movers = breadth.movedHigher + breadth.movedLower;
    let first;
    if (direction.key === "insufficient") {
      first = `Only ${movers} symbol${movers === 1 ? "" : "s"} changed structural bucket over the last ${report.window}, so the evidence is too narrow to establish a directional structural read.`;
    } else if (direction.key === "balanced") {
      first = `Structural movement over the last ${report.window} is directionally mixed, with ${participation.toLowerCase()} participation.`;
    } else {
      first = `Structural movement over the last ${report.window} favored ${direction.key} locations, with ${participation.toLowerCase()} participation and ${confirmation.toLowerCase()} matching current pressure confirmation.`;
    }
    let migrationText;
    if (migration.key === "none") migrationText = "No meaningful canonical MRZ migration activity occurred in the window";
    else if (migration.key === "insufficient") migrationText = "Canonical MRZ migration activity is too sparse for a directional breadth read";
    else if (migration.key === "balanced") migrationText = `Canonical MRZ migrations are balanced${migration.narrow ? " across a narrow share of comparable symbols" : ""}`;
    else migrationText = `Canonical MRZ migrations are skewed ${migration.key}${migration.narrow ? ", but cover only a narrow share of comparable symbols" : ""}`;
    const pressureText = {
      neutral: "current pressure is mostly neutral",
      higher: "Higher pressure is currently dominant",
      lower: "Lower pressure is currently dominant",
      mixed: "current directional pressure is mixed",
      insufficient: "current pressure coverage is insufficient",
    }[pressure.key];
    return `${first} ${migrationText}; ${pressureText}.`;
  }

  function deriveResearchInterpretation(report = {}) {
    const breadth = report.breadth || { movedHigher: 0, movedLower: 0, comparable: 0, participationPct: 0 };
    const direction = structuralDirection(breadth);
    const participation = participationLabel(breadth.participationPct);
    const dominantRate = direction.key === "higher" ? report.confirmationRates?.higher
      : direction.key === "lower" ? report.confirmationRates?.lower : null;
    const confirmation = dominantRate
      ? confirmationLabel(dominantRate.numerator, dominantRate.denominator)
      : direction.key === "balanced" ? "Mixed" : "Not applicable / insufficient";
    const migration = migrationSkew(report.migrationBreadth || {}, Number(breadth.comparable || 0));
    const pressureCounts = currentPressureCounts(report);
    const pressure = pressureRegime(pressureCounts);
    const higherRate = report.confirmationRates?.higher || { numerator: 0, denominator: 0 };
    const lowerRate = report.confirmationRates?.lower || { numerator: 0, denominator: 0 };
    const moved = Number(breadth.movedHigher || 0) + Number(breadth.movedLower || 0);
    const formatRate = (rate) => rate.denominator ? `${((rate.numerator / rate.denominator) * 100).toFixed(1)}%` : "n/a";
    const migrationBreadth = report.migrationBreadth || {};
    const divergences = report.divergences || { higherWithLower: [], lowerWithHigher: [] };
    const result = {
      window: report.window || "24H",
      dimensions: {
        direction: direction.label,
        participation,
        confirmation,
        migration: migration.label,
        pressure: pressure.label,
      },
      evidence: [
        ["Structural flow", `${breadth.movedHigher || 0} higher · ${breadth.movedLower || 0} lower · net ${Number(breadth.netHigher || 0) > 0 ? "+" : ""}${Number(breadth.netHigher || 0)}`],
        ["Participation", `${moved} / ${breadth.comparable || 0} · ${Number(breadth.participationPct || 0).toFixed(1)}%`],
        ["Matching pressure", `Higher ${higherRate.numerator} / ${higherRate.denominator} · ${formatRate(higherRate)} · Lower ${lowerRate.numerator} / ${lowerRate.denominator} · ${formatRate(lowerRate)}`],
        ["MRZ migration breadth", `${migrationBreadth.up_only || 0} up-only · ${migrationBreadth.down_only || 0} down-only · ${migrationBreadth.mixed || 0} mixed · ${migrationBreadth.uniqueSymbols || 0} / ${breadth.comparable || 0} symbols · ${migrationBreadth.eventCount || 0} events`],
        ["Current pressure", `${pressureCounts.higher} Higher · ${pressureCounts.neutral} Neutral · ${pressureCounts.lower} Lower`],
        ["Non-confirmation cases", `${divergences.higherWithLower?.length || 0} higher movers with Lower pressure · ${divergences.lowerWithHigher?.length || 0} lower movers with Higher pressure`],
      ],
    };
    result.narrative = researchNarrative({ report, direction, participation, confirmation, migration, pressure });
    return result;
  }

  function deriveBreadthLeadership(history = {}, pressureReport = {}) {
    const { movements, migrationBySymbol, migrationState } = contextualizeLocationMovements(history, pressureReport);
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
    derivePeerLocation,
    derivePeerLocationFlow,
    deriveLocationFlowDetails,
    deriveAttention,
    deriveBreadthLeadership,
    deriveResearchInterpretation,
    eventDirection,
    eventLabel,
    filterLocationSymbols,
    groupPressureSourcesByAssetClass,
    groupMembership,
    latestEventsBySymbol,
    groupSymbolBoardRows,
    normalizeSymbolBoardSort,
    persistSymbolBoardSort,
    pressureConcentrationLabel,
    pressureDrilldownMembers,
    restoreSymbolBoardSort,
    sortSymbolBoardRows,
    symbolBoardGroup,
    symbolsForWatchlist,
    uniqueTrackedSymbols,
  };
  globalObject.edgeWorkspaceDerivations = exported;
  if (typeof module === "object" && module.exports) module.exports = exported;
}(globalThis));
