const assert = require("node:assert/strict");
const {
  allGroupsRows,
  currentAuthorityRow,
  deriveAttention,
  deriveBreadthLeadership,
  deriveLocationFlowDetails,
  eventLabel,
  groupSymbolBoardRows,
  normalizeSymbolBoardSort,
  persistSymbolBoardSort,
  restoreSymbolBoardSort,
  sortSymbolBoardRows,
  symbolBoardGroup,
  symbolsForWatchlist,
  uniqueTrackedSymbols,
} = require("../app/static/workspace-derivations.js");

const groups = [
  { id: 1, name: "Large Cap", members: ["NVDA", "META"] },
  { id: 2, name: "Momentum", members: ["NVDA", "PLTR"] },
];
const symbols = [
  { symbol: "NVDA", mrz_status: "active", core_mrz_lower: 198.4, core_mrz_upper: 201.1, route_owner: "STR", activated_at: "2026-10-07T10:00:00Z", structural_location: "deep_premium_core_mrz" },
  { symbol: "META", mrz_status: "unestablished" },
  { symbol: "XAGUSD", mrz_status: "active" },
];
const events = [
  { id: 1, symbol: "NVDA", event_type: "MRZ_ACTIVATED", occurred_at: "2026-10-07T10:00:00Z" },
  { id: 2, symbol: "XAGUSD", event_type: "MRZ_NEAR_MISS", occurred_at: "2026-10-07T10:30:00Z" },
  { id: 3, symbol: "META", event_type: "MRZ_MIGRATED", occurred_at: "2026-10-07T09:00:00Z", previous_mrz_lower: "100", previous_mrz_upper: "102", mrz_lower: "105", mrz_upper: "107" },
];

assert.deepEqual([...uniqueTrackedSymbols(groups)].sort(), ["META", "NVDA", "PLTR"]);
assert.deepEqual(symbolsForWatchlist(symbols, groups, "all").map((item) => item.symbol), ["NVDA", "META"]);
assert.deepEqual(symbolsForWatchlist(symbols, groups, 1).map((item) => item.symbol), ["NVDA", "META"]);

const attention = deriveAttention(events, groups, { now: "2026-10-07T12:00:00Z" });
assert.deepEqual(attention.map((event) => event.symbol), ["NVDA", "META"]);
assert.equal(eventLabel(events[2]), "MIGRATED ↑");

const recentEvents = events.map((event) => ({
  ...event,
  occurred_at: new Date().toISOString(),
}));
const rows = allGroupsRows(recentEvents, groups);
assert.equal(rows.filter((row) => row.event.symbol === "NVDA").length, 2, "one canonical event may surface in both group contexts");
assert.equal(new Set(rows.filter((row) => row.event.symbol === "NVDA").map((row) => row.event.id)).size, 1, "group membership does not duplicate the canonical event identity");

assert.deepEqual(currentAuthorityRow(symbols[0], { direction: "higher" }, events[0]), {
  symbol: "NVDA",
  active: true,
  lower: 198.4,
  upper: 201.1,
  route: "STR",
  activatedAt: "2026-10-07T10:00:00Z",
  location: "deep_premium_core_mrz",
  pressure: "higher",
  latestEvent: events[0],
});

const boardNow = "2026-10-10T16:00:00Z";
const boardRow = ({
  symbol,
  eventType = null,
  eventAt = null,
  pressure = "neutral",
  activatedAt = null,
  location = "at_eqm",
  active = true,
}) => ({
  symbol,
  active,
  activatedAt,
  location,
  pressure,
  latestEvent: eventType ? { event_type: eventType, occurred_at: eventAt } : null,
});
const boardRows = [
  boardRow({ symbol: "ACT", eventType: "MRZ_ACTIVATED", eventAt: "2026-10-10T15:00:00Z", activatedAt: "2026-10-10T15:00:00Z", location: "shallow_premium" }),
  boardRow({ symbol: "MIG", eventType: "MRZ_MIGRATED", eventAt: "2026-10-10T12:00:00Z", activatedAt: "2026-10-01T10:00:00Z", location: "deep_discount" }),
  boardRow({ symbol: "PRESSURE_NEUTRAL", eventType: "POST_ACTIVATION_PRESSURE_CHANGED", eventAt: "2026-10-10T14:30:00Z", pressure: "neutral", activatedAt: "2026-10-02T10:00:00Z", location: "shallow_discount" }),
  boardRow({ symbol: "PRESSURE_NEW", eventType: "POST_ACTIVATION_PRESSURE_CHANGED", eventAt: "2026-10-10T14:00:00Z", pressure: "higher", activatedAt: "2026-10-03T10:00:00Z", location: "at_eqm" }),
  boardRow({ symbol: "PRESSURE_OLD", eventType: "POST_ACTIVATION_PRESSURE_CHANGED", eventAt: "2026-10-10T13:00:00Z", pressure: "lower", activatedAt: "2026-10-04T10:00:00Z", location: "deep_premium" }),
  boardRow({ symbol: "DIRECTIONAL", eventType: "MRZ_ACTIVATED", eventAt: "2026-10-09T12:00:00Z", pressure: "higher", activatedAt: "2026-10-09T12:00:00Z", location: "deep_premium_core_mrz" }),
  boardRow({ symbol: "STABLE_B", eventType: "MRZ_ACTIVATED", eventAt: "2026-10-08T12:00:00Z", activatedAt: "2026-10-08T12:00:00Z", location: "shallow_discount_core_mrz" }),
  boardRow({ symbol: "STABLE_A", eventType: "MRZ_ACTIVATED", eventAt: "2026-10-08T12:00:00Z", activatedAt: "2026-10-07T12:00:00Z", location: "shallow_premium_core_mrz" }),
];
const symbolsFrom = (rows) => rows.map((row) => row.symbol);

assert.equal(normalizeSymbolBoardSort("unknown"), "attention", "attention-first is the default");
assert.deepEqual(
  symbolsFrom(sortSymbolBoardRows(boardRows, "attention", { now: boardNow })),
  ["MIG", "PRESSURE_NEW", "PRESSURE_OLD", "PRESSURE_NEUTRAL", "ACT", "DIRECTIONAL", "STABLE_A", "STABLE_B"],
  "attention-first prioritizes event type, directional pressure, recency, then symbol",
);
assert.deepEqual(
  symbolsFrom(sortSymbolBoardRows(boardRows, "latest_event")),
  ["ACT", "PRESSURE_NEUTRAL", "PRESSURE_NEW", "PRESSURE_OLD", "MIG", "DIRECTIONAL", "STABLE_A", "STABLE_B"],
);
assert.deepEqual(
  symbolsFrom(sortSymbolBoardRows(boardRows, "activation_age")),
  ["ACT", "DIRECTIONAL", "STABLE_B", "STABLE_A", "PRESSURE_OLD", "PRESSURE_NEW", "PRESSURE_NEUTRAL", "MIG"],
);
assert.deepEqual(
  symbolsFrom(sortSymbolBoardRows(boardRows, "pressure")),
  ["DIRECTIONAL", "PRESSURE_NEW", "ACT", "MIG", "PRESSURE_NEUTRAL", "STABLE_A", "STABLE_B", "PRESSURE_OLD"],
);
assert.deepEqual(
  symbolsFrom(sortSymbolBoardRows(boardRows, "structural_location")),
  ["MIG", "PRESSURE_NEUTRAL", "STABLE_B", "PRESSURE_NEW", "ACT", "STABLE_A", "DIRECTIONAL", "PRESSURE_OLD"],
);
assert.deepEqual(
  symbolsFrom(sortSymbolBoardRows(boardRows, "symbol")),
  ["ACT", "DIRECTIONAL", "MIG", "PRESSURE_NEUTRAL", "PRESSURE_NEW", "PRESSURE_OLD", "STABLE_A", "STABLE_B"],
);

const attentionRows = sortSymbolBoardRows(boardRows, "attention", { now: boardNow });
const groupedRows = groupSymbolBoardRows(attentionRows, { now: boardNow });
assert.deepEqual(groupedRows.map((group) => group.label), [
  "Changed today",
  "Directional pressure",
  "Stable / no recent change",
]);
assert.deepEqual(
  symbolsFrom(groupedRows.flatMap((group) => group.rows)),
  symbolsFrom(attentionRows),
  "visual grouping preserves order without duplicating symbols",
);
assert.equal(new Set(groupedRows.flatMap((group) => group.rows).map((row) => row.symbol)).size, boardRows.length);
assert.equal(symbolBoardGroup(boardRows[0], { now: boardNow }), "changed_today");
assert.equal(symbolBoardGroup(boardRows[5], { now: boardNow }), "directional_pressure");
assert.equal(symbolBoardGroup(boardRows[6], { now: boardNow }), "stable");

const stored = new Map();
const storage = {
  getItem(key) { return stored.get(key) ?? null; },
  setItem(key, value) { stored.set(key, value); },
};
assert.equal(restoreSymbolBoardSort(storage), "attention");
assert.equal(persistSymbolBoardSort(storage, "pressure"), "pressure");
assert.equal(restoreSymbolBoardSort(storage), "pressure");
assert.deepEqual(
  symbolsFrom(sortSymbolBoardRows([...boardRows], restoreSymbolBoardSort(storage))),
  symbolsFrom(sortSymbolBoardRows(boardRows, "pressure")),
  "a data refresh preserves the operator's selected sort",
);

const breadthHistory = {
  window: "24H",
  universe: { now_eligible: 8, then_eligible: 8, common_eligible: 7, added_or_became_eligible: 1, removed_or_became_ineligible: 1 },
  flow: { moved_higher: 3, moved_lower: 3, unchanged: 1, net_higher: 0, comparable_symbols: 7 },
  symbol_movements: [
    { symbol: "UP_CONFIRMED", start_location: "deep_discount", start_location_label: "Deep Discount", current_location: "shallow_premium", current_location_label: "Shallow Premium", direction: "higher", magnitude: 3, current_observed_at: "2026-10-10T10:00:00Z" },
    { symbol: "UP_NEUTRAL", start_location: "deep_discount", start_location_label: "Deep Discount", current_location: "shallow_discount", current_location_label: "Shallow Discount", direction: "higher", magnitude: 1, current_observed_at: "2026-10-10T11:00:00Z" },
    { symbol: "UP_DIVERGENT", start_location: "shallow_discount", start_location_label: "Shallow Discount", current_location: "at_eqm", current_location_label: "At EQM", direction: "higher", magnitude: 1, current_observed_at: "2026-10-10T12:00:00Z" },
    { symbol: "DOWN_CONFIRMED", start_location: "deep_premium", start_location_label: "Deep Premium", current_location: "shallow_discount", current_location_label: "Shallow Discount", direction: "lower", magnitude: 3, current_observed_at: "2026-10-10T10:00:00Z" },
    { symbol: "DOWN_NEUTRAL", start_location: "deep_premium", start_location_label: "Deep Premium", current_location: "shallow_premium", current_location_label: "Shallow Premium", direction: "lower", magnitude: 1, current_observed_at: "2026-10-10T11:00:00Z" },
    { symbol: "DOWN_DIVERGENT", start_location: "shallow_premium", start_location_label: "Shallow Premium", current_location: "at_eqm", current_location_label: "At EQM", direction: "lower", magnitude: 1, current_observed_at: "2026-10-10T12:00:00Z" },
    { symbol: "UNCHANGED", start_location: "at_eqm", start_location_label: "At EQM", current_location: "at_eqm", current_location_label: "At EQM", direction: "unchanged", magnitude: 0, current_observed_at: "2026-10-10T12:00:00Z" },
  ],
  migration_events: [
    { event_key: "up-1", symbol: "UP_CONFIRMED", direction: "higher", occurred_at: "2026-10-10T09:00:00Z" },
    { event_key: "down-1", symbol: "DOWN_CONFIRMED", direction: "lower", occurred_at: "2026-10-10T08:00:00Z" },
    { event_key: "mixed-1", symbol: "MIXED", direction: "higher", occurred_at: "2026-10-10T07:00:00Z" },
    { event_key: "mixed-2", symbol: "MIXED", direction: "lower", occurred_at: "2026-10-10T06:00:00Z" },
  ],
};
const breadthPressure = {
  categories: {
    higher: [{ symbol: "UP_CONFIRMED" }, { symbol: "DOWN_DIVERGENT" }],
    neutral: [{ symbol: "UP_NEUTRAL" }, { symbol: "DOWN_NEUTRAL" }, { symbol: "UNCHANGED" }],
    lower: [{ symbol: "UP_DIVERGENT" }, { symbol: "DOWN_CONFIRMED" }],
  },
  pressure_map: { locations: { deep_discount: { counts: { higher: 1, neutral: 2, lower: 3 } } } },
};
const breadthReport = deriveBreadthLeadership(breadthHistory, breadthPressure);
assert.deepEqual(breadthReport.breadth, { movedHigher: 3, movedLower: 3, unchanged: 1, netHigher: 0, comparable: 7, participationPct: 6 / 7 * 100 });
assert.deepEqual(breadthReport.confirmation.higher, { higher: 1, neutral: 1, lower: 1 });
assert.deepEqual(breadthReport.confirmation.lower, { higher: 1, neutral: 1, lower: 1 });
assert.deepEqual(breadthReport.confirmationRates, { higher: { numerator: 1, denominator: 3 }, lower: { numerator: 1, denominator: 3 } });
assert.deepEqual(breadthReport.leaders.map((item) => item.symbol), ["UP_CONFIRMED"]);
assert.deepEqual(breadthReport.laggards.map((item) => item.symbol), ["DOWN_CONFIRMED"]);
assert.deepEqual(breadthReport.divergences.higherWithLower.map((item) => item.symbol), ["UP_DIVERGENT"]);
assert.deepEqual(breadthReport.divergences.lowerWithHigher.map((item) => item.symbol), ["DOWN_DIVERGENT"]);
assert.deepEqual(breadthReport.migrationBreadth, { up_only: 1, down_only: 1, mixed: 1, none: 5, uniqueSymbols: 3, eventCount: 4 });
assert.equal(breadthReport.currentLocationPressure.deep_discount.counts.lower, 3);
assert.equal(breadthReport.historicalPressureAvailable, false);

const flowDetails = deriveLocationFlowDetails(breadthHistory, breadthPressure);
assert.deepEqual(flowDetails.higher.map((item) => item.symbol), ["UP_CONFIRMED", "UP_DIVERGENT", "UP_NEUTRAL"]);
assert.deepEqual(flowDetails.lower.map((item) => item.symbol), ["DOWN_CONFIRMED", "DOWN_DIVERGENT", "DOWN_NEUTRAL"]);
assert.deepEqual(flowDetails.unchanged.map((item) => item.symbol), ["UNCHANGED"]);
assert.equal(flowDetails.higher[0].start_location_label, "Deep Discount");
assert.equal(flowDetails.higher[0].current_location_label, "Shallow Premium");
assert.equal(flowDetails.higher[0].magnitude, 3);
assert.equal(flowDetails.higher[0].pressure, "higher");
assert.deepEqual(flowDetails.higher[0].migrationEvents.map((event) => event.direction), ["higher"]);
assert.equal(flowDetails.higher.length, breadthHistory.flow.moved_higher, "aggregate higher count remains unchanged");
assert.equal(flowDetails.lower.length, breadthHistory.flow.moved_lower, "aggregate lower count remains unchanged");
assert.equal(flowDetails.unchanged.length, breadthHistory.flow.unchanged, "aggregate unchanged count remains unchanged");

const refreshedFlow = deriveLocationFlowDetails({
  symbol_movements: [{ symbol: "NEW_WINDOW", direction: "higher", magnitude: 1 }],
  migration_events: [],
}, { categories: { neutral: [{ symbol: "NEW_WINDOW" }] } });
assert.deepEqual(refreshedFlow.higher.map((item) => item.symbol), ["NEW_WINDOW"], "window refresh derives only the new response symbols");
assert.equal(refreshedFlow.higher.some((item) => item.symbol === "UP_CONFIRMED"), false, "window refresh retains no stale symbols");

const leaderSortReport = deriveBreadthLeadership({
  flow: { moved_higher: 3, moved_lower: 0, unchanged: 0, net_higher: 3, comparable_symbols: 3 },
  symbol_movements: [
    { symbol: "BETA", direction: "higher", magnitude: 2, current_observed_at: "2026-10-10T12:00:00Z" },
    { symbol: "ALPHA", direction: "higher", magnitude: 2, current_observed_at: "2026-10-10T12:00:00Z" },
    { symbol: "MIGRATION_FIRST", direction: "higher", magnitude: 1, current_observed_at: "2026-10-10T10:00:00Z" },
  ],
  migration_events: [
    { event_key: "confirm", symbol: "MIGRATION_FIRST", direction: "higher", occurred_at: "2026-10-10T09:00:00Z" },
  ],
}, {
  categories: { higher: [{ symbol: "ALPHA" }, { symbol: "BETA" }, { symbol: "MIGRATION_FIRST" }] },
});
assert.deepEqual(
  leaderSortReport.leaders.map((item) => item.symbol),
  ["MIGRATION_FIRST", "ALPHA", "BETA"],
  "leaders sort by confirming migration, magnitude, recency, then deterministic symbol",
);

const flowSortReport = deriveLocationFlowDetails({
  symbol_movements: [
    { symbol: "BETA", direction: "higher", magnitude: 2 },
    { symbol: "ALPHA", direction: "higher", magnitude: 2 },
    { symbol: "PRESSURE_FIRST", direction: "higher", magnitude: 1 },
    { symbol: "MIGRATION_SECOND", direction: "higher", magnitude: 1 },
  ],
  migration_events: [{ symbol: "MIGRATION_SECOND", direction: "higher", occurred_at: "2026-10-10T09:00:00Z" }],
}, {
  categories: {
    higher: [{ symbol: "PRESSURE_FIRST" }],
    neutral: [{ symbol: "ALPHA" }, { symbol: "BETA" }, { symbol: "MIGRATION_SECOND" }],
  },
});
assert.deepEqual(
  flowSortReport.higher.map((item) => item.symbol),
  ["ALPHA", "BETA", "PRESSURE_FIRST", "MIGRATION_SECOND"],
  "flow sorting is magnitude, confirming pressure, confirming migration, then symbol",
);
