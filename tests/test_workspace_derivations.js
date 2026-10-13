const assert = require("node:assert/strict");
const {
  allGroupsRows,
  currentAuthorityRow,
  deriveAttention,
  deriveBreadthLeadership,
  deriveResearchInterpretation,
  deriveLocationFlowDetails,
  derivePeerLocation,
  derivePeerLocationFlow,
  eventLabel,
  filterLocationSymbols,
  groupPressureSourcesByAssetClass,
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
} = require("../app/static/workspace-derivations.js");

const pressureSource = (symbol, direction, assetClass, sector = null, industry = null, location = "at_eqm") => ({
  symbol,
  direction,
  asset_class: assetClass,
  sector,
  industry,
  current_location: location,
  current_location_label: location,
  route_owner: "STR",
});
const nvdaPressure = pressureSource("NVDA", "higher", "EQUITY", "Technology", "Semiconductors", "deep_premium");
const msftPressure = pressureSource("MSFT", "neutral", "EQUITY", "Technology", "Software", "shallow_premium");
const d05Pressure = pressureSource("D05", "lower", "EQUITY", "Financials", "Banks", "shallow_discount");
const mstrPressure = pressureSource("MSTR", "lower", "EQUITY", "Financials", "Digital Asset Treasury", "deep_discount");
const btcPressure = pressureSource("BTCUSDT", "higher", "CRYPTO", null, null, "deep_discount");
const taxonomyPressure = {
  sources: { higher: [nvdaPressure, btcPressure], neutral: [msftPressure], lower: [d05Pressure, mstrPressure] },
  included_equity_count: 4,
  counts: { higher: 1, neutral: 1, lower: 2 },
  asset_classes: [
    { name: "EQUITY", members: { higher: [nvdaPressure], neutral: [msftPressure], lower: [d05Pressure, mstrPressure] } },
    { name: "CRYPTO", members: { higher: [btcPressure], neutral: [], lower: [] } },
  ],
  sectors: [
    { name: "Technology", members: { higher: [nvdaPressure], neutral: [msftPressure], lower: [] } },
    { name: "Financials", members: { higher: [], neutral: [], lower: [d05Pressure, mstrPressure] } },
  ],
  industries: [
    { name: "Semiconductors", sector: "Technology", members: { higher: [nvdaPressure], neutral: [], lower: [] } },
    { name: "Digital Asset Treasury", sector: "Financials", members: { higher: [], neutral: [], lower: [mstrPressure] } },
  ],
  concentration: {
    higher: { top_sector: "Technology", top_sector_share_pct: 100 },
    lower: { top_sector: "Financials", top_sector_share_pct: 100 },
  },
};
const pressureReport = {
  categories: {
    higher: [{ symbol: "NVDA", current_location: "deep_premium" }, { symbol: "BTCUSDT", current_location: "deep_discount" }],
    neutral: [{ symbol: "MSFT", current_location: "shallow_premium" }],
    lower: [{ symbol: "D05", current_location: "shallow_discount" }, { symbol: "MSTR", current_location: "deep_discount" }],
  },
};

assert.deepEqual(
  groupPressureSourcesByAssetClass(taxonomyPressure.sources.higher).map((group) => group.assetClass),
  ["EQUITY", "CRYPTO"],
  "pressure sources remain clearly separated by canonical asset class",
);
assert.deepEqual(
  pressureDrilldownMembers(taxonomyPressure, pressureReport, { type: "direction", direction: "higher" }).map((item) => item.symbol),
  ["BTCUSDT", "NVDA"],
  "direction drill-down reconciles to the current Higher list without duplicates",
);
assert.deepEqual(
  pressureDrilldownMembers(taxonomyPressure, pressureReport, { type: "asset_class", name: "CRYPTO" }).map((item) => item.symbol),
  ["BTCUSDT"],
  "asset-class drill-down reconciles to the clicked canonical class",
);
assert.deepEqual(
  pressureDrilldownMembers(taxonomyPressure, pressureReport, { type: "sector", name: "Technology" }).map((item) => item.symbol),
  ["NVDA", "MSFT"],
  "sector drill-down returns its canonical equity constituents grouped by direction",
);
assert.deepEqual(
  pressureDrilldownMembers(taxonomyPressure, pressureReport, { type: "industry", sector: "Financials", name: "Digital Asset Treasury" }).map((item) => item.symbol),
  ["MSTR"],
  "industry drill-down is scoped by canonical sector and industry",
);
assert.deepEqual(
  pressureDrilldownMembers(taxonomyPressure, pressureReport, { type: "map", location: "deep_discount", direction: "higher" }).map((item) => item.symbol),
  ["BTCUSDT"],
  "Pressure Map drill-down reuses the same canonical source records",
);
assert.equal(
  pressureConcentrationLabel(taxonomyPressure),
  "Balanced globally, sector-concentrated",
  "the restrained rotation read is deterministic and descriptive",
);

assert.deepEqual(filterLocationSymbols(["NVDA", "NVDL", "AAPL"], "nvd"), ["NVDA", "NVDL"], "location symbol search is case-insensitive and supports partial matches");
assert.deepEqual(filterLocationSymbols(["NVDA", "AAPL"], "  aapl  "), ["AAPL"], "location symbol search trims operator input");
assert.deepEqual(filterLocationSymbols(["NVDA", "AAPL"], ""), ["NVDA", "AAPL"], "empty location search preserves the existing order");
assert.deepEqual(filterLocationSymbols(["NVDA"], "MSFT"), [], "location symbol search reports an empty result without adding symbols");

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

const peerGroup = {
  id: 9,
  name: "Peers",
  member_count: 4,
  members: ["NVDA", "META", "MISSING", "CORE"],
  current_state: {
    members: [
      { symbol: "NVDA", current_location: "deep_discount", route_owner: "BTD", has_active_mrz: true },
      { symbol: "META", current_location: "shallow_premium", route_owner: "STR", has_active_mrz: true },
      { symbol: "MISSING", current_location: null, route_owner: null, has_active_mrz: false },
      { symbol: "CORE", current_location: "deep_premium_core_mrz", route_owner: "STR", has_active_mrz: true },
    ],
  },
};
const peerLocations = derivePeerLocation(peerGroup);
assert.equal(peerLocations.reduce((total, item) => total + item.members.length, 0), 4, "peer location reconciles to watchlist membership");
assert.deepEqual(peerLocations.find((item) => item.key === "deep_discount").members.map((item) => item.symbol), ["NVDA"], "clickable location groups expose exact members");
assert.deepEqual(peerLocations.find((item) => item.key === "deep_premium").members.map((item) => item.symbol), ["CORE"], "canonical core-location aliases map to their structural bucket");
assert.deepEqual(peerLocations.find((item) => item.key === "unavailable").members.map((item) => item.symbol), ["MISSING"], "missing location is explicit rather than dropped");
assert.equal(peerGroup.current_state.members[0].current_location, "deep_discount", "grouping does not mutate canonical structural location state");

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

const interpretationReport = (overrides = {}) => ({
  window: "5D",
  breadth: { movedHigher: 12, movedLower: 24, unchanged: 88, netHigher: -12, comparable: 124, participationPct: 36 / 124 * 100 },
  confirmationRates: { higher: { numerator: 3, denominator: 12 }, lower: { numerator: 4, denominator: 24 } },
  migrationBreadth: { up_only: 1, down_only: 7, mixed: 0, none: 116, uniqueSymbols: 8, eventCount: 8 },
  currentLocationPressure: { all: { counts: { higher: 14, neutral: 96, lower: 14 } } },
  divergences: { higherWithLower: [{}], lowerWithHigher: [{}, {}] },
  ...overrides,
});
const lowerInterpretation = deriveResearchInterpretation(interpretationReport());
assert.equal(lowerInterpretation.dimensions.direction, "Lower-skewed");
assert.equal(lowerInterpretation.dimensions.participation, "Limited");
assert.equal(lowerInterpretation.dimensions.confirmation, "Weak");
assert.equal(lowerInterpretation.dimensions.migration, "Downward-skewed · narrow");
assert.equal(lowerInterpretation.dimensions.pressure, "Mostly neutral");
assert.deepEqual(lowerInterpretation.evidence, [
  ["Structural flow", "12 higher · 24 lower · net -12"],
  ["Participation", "36 / 124 · 29.0%"],
  ["Matching pressure", "Higher 3 / 12 · 25.0% · Lower 4 / 24 · 16.7%"],
  ["MRZ migration breadth", "1 up-only · 7 down-only · 0 mixed · 8 / 124 symbols · 8 events"],
  ["Current pressure", "14 Higher · 96 Neutral · 14 Lower"],
  ["Non-confirmation cases", "1 higher movers with Lower pressure · 2 lower movers with Higher pressure"],
]);

const interpretationFor = ({ higher, lower, comparable = 100, confirmation = 0, up = 0, down = 0, mixed = 0, pressure = { higher: 20, neutral: 60, lower: 20 }, window = "5D" }) => deriveResearchInterpretation(interpretationReport({
  window,
  breadth: { movedHigher: higher, movedLower: lower, unchanged: Math.max(0, comparable - higher - lower), netHigher: higher - lower, comparable, participationPct: comparable ? ((higher + lower) / comparable) * 100 : 0 },
  confirmationRates: { higher: { numerator: confirmation, denominator: higher }, lower: { numerator: confirmation, denominator: lower } },
  migrationBreadth: { up_only: up, down_only: down, mixed, none: Math.max(0, comparable - up - down - mixed), uniqueSymbols: up + down + mixed, eventCount: up + down + mixed },
  currentLocationPressure: { all: { counts: pressure } },
  divergences: { higherWithLower: [], lowerWithHigher: [] },
}));

assert.equal(interpretationFor({ higher: 35, lower: 8, comparable: 72, confirmation: 25, up: 18, down: 3 }).dimensions.direction, "Higher-skewed");
assert.equal(interpretationFor({ higher: 30, lower: 28, comparable: 124 }).dimensions.direction, "Balanced / Mixed");
assert.equal(interpretationFor({ higher: 10, lower: 5, comparable: 100 }).dimensions.participation, "Narrow");
assert.equal(interpretationFor({ higher: 20, lower: 10, comparable: 100 }).dimensions.participation, "Limited");
assert.equal(interpretationFor({ higher: 30, lower: 20, comparable: 100 }).dimensions.participation, "Moderate");
assert.equal(interpretationFor({ higher: 50, lower: 20, comparable: 100 }).dimensions.participation, "Broad");
assert.equal(interpretationFor({ higher: 20, lower: 5, confirmation: 4 }).dimensions.confirmation, "Weak");
assert.equal(interpretationFor({ higher: 20, lower: 5, confirmation: 6 }).dimensions.confirmation, "Partial");
assert.equal(interpretationFor({ higher: 20, lower: 5, confirmation: 12 }).dimensions.confirmation, "Moderate");
assert.equal(interpretationFor({ higher: 20, lower: 5, confirmation: 15 }).dimensions.confirmation, "Strong");
assert.equal(interpretationFor({ higher: 20, lower: 5, up: 7, down: 1 }).dimensions.migration, "Upward-skewed · narrow");
assert.equal(interpretationFor({ higher: 20, lower: 5, up: 4, down: 4 }).dimensions.migration, "Balanced · narrow");
assert.equal(interpretationFor({ higher: 20, lower: 5 }).dimensions.migration, "No meaningful migration activity");
assert.equal(interpretationFor({ higher: 20, lower: 5, up: 1, down: 0 }).dimensions.migration, "Sparse / insufficient breadth");
assert.equal(interpretationFor({ higher: 20, lower: 5, pressure: { higher: 55, neutral: 25, lower: 20 } }).dimensions.pressure, "Higher pressure dominant");
assert.equal(interpretationFor({ higher: 20, lower: 5, pressure: { higher: 20, neutral: 25, lower: 55 } }).dimensions.pressure, "Lower pressure dominant");
assert.equal(interpretationFor({ higher: 20, lower: 5, pressure: { higher: 35, neutral: 30, lower: 35 } }).dimensions.pressure, "Directionally mixed");
assert.equal(interpretationFor({ higher: 1, lower: 1 }).dimensions.direction, "Insufficient breadth");
assert.equal(interpretationFor({ higher: 1, lower: 1 }).dimensions.confirmation, "Not applicable / insufficient");
assert.equal(interpretationFor({ higher: 1, lower: 0 }).narrative.includes("too narrow to establish"), true);
for (const window of ["24H", "5D", "20D"]) {
  const refreshed = interpretationFor({ higher: 20, lower: 5, window });
  assert.equal(refreshed.window, window);
  assert.equal(refreshed.narrative.includes(`last ${window}`), true, `${window} refreshes the interpretation narrative`);
}
const interpretationLanguage = JSON.stringify([
  lowerInterpretation,
  interpretationFor({ higher: 35, lower: 8, comparable: 72, confirmation: 25, up: 18, down: 3 }),
  interpretationFor({ higher: 30, lower: 28, comparable: 124 }),
]).toLowerCase();
for (const forbidden of ["bullish", "bearish", "probability", "expected return", "recommendation", "long bias", "short bias", "trade grade"]) {
  assert.equal(interpretationLanguage.includes(forbidden), false, `interpretation avoids ${forbidden}`);
}

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

const peerFlow = derivePeerLocationFlow(
  breadthHistory,
  ["UP_CONFIRMED", "DOWN_NEUTRAL", "UNCHANGED", "NOT_COMPARABLE"],
  breadthPressure,
);
assert.deepEqual(peerFlow.counts, { higher: 1, lower: 1, unchanged: 1 }, "peer flow filters the existing canonical flow without re-deriving locations");
assert.equal(peerFlow.comparable, 3, "peer flow counts reconcile to comparable watchlist members");
assert.equal(peerFlow.categories.higher[0].magnitude, 3, "peer flow preserves ordered start-to-current bucket distance");
assert.equal(peerFlow.categories.higher[0].pressure, "higher", "peer flow keeps current canonical pressure context");
assert.deepEqual(peerFlow.categories.higher[0].migrationEvents.map((event) => event.direction), ["higher"], "peer flow keeps canonical migration context only when present");
assert.equal(breadthHistory.symbol_movements.length, 7, "watchlist membership does not mutate global location history");

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
