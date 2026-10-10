const assert = require("node:assert/strict");
const {
  allGroupsRows,
  currentAuthorityRow,
  deriveAttention,
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
