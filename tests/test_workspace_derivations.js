const assert = require("node:assert/strict");
const {
  allGroupsRows,
  currentAuthorityRow,
  deriveAttention,
  eventLabel,
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
