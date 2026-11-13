"use strict";

const assert = require("node:assert/strict");

global.window = global;
require("../app/static/opportunity-map.js");

const map = global.edgeOpportunityMap;

assert.equal(map.proportionalPosition(15, 10, 20), 0.5);
assert.equal(map.proportionalPosition(10, 10, 20), 0);
assert.equal(map.proportionalPosition(20, 10, 20), 1);
assert.equal(map.proportionalPosition(99, 10, 20), 1);

const detail = {
  as_of: "2026-11-12T00:00:00Z",
  as_known_at: "2026-11-12T00:00:00Z",
  observations: [
    { effective_at: "2026-08-21T15:48:00Z", known_at: "2026-08-21T15:48:05Z" },
    { effective_at: "2026-10-02T19:57:00Z", known_at: "2026-10-02T19:57:03Z" },
  ],
  near_miss_events: [
    { known_at: "2026-09-18T13:51:07Z" },
  ],
  mrz_lifecycles: [
    { known_at: "2026-10-02T19:57:03Z" },
  ],
  pressure_observations: [
    { effective_at: "2026-10-13T14:11:00Z", known_at: "2026-10-13T14:11:04Z" },
  ],
};

const cursors = map.collectReplayCursors(detail);
assert.deepEqual(cursors, [
  "2026-08-21T15:48:05Z",
  "2026-09-18T13:51:07Z",
  "2026-10-02T19:57:03Z",
  "2026-10-13T14:11:04Z",
  "2026-11-12T00:00:00Z",
]);

const bounds = map.timeBounds(detail, 0);
const first = new Date("2026-08-21T15:48:00Z").getTime();
const activation = new Date("2026-10-02T19:57:00Z").getTime();
const last = new Date("2026-10-13T14:11:00Z").getTime();
const firstPosition = map.proportionalPosition(first, bounds.minimum, bounds.maximum);
const activationPosition = map.proportionalPosition(activation, bounds.minimum, bounds.maximum);
const lastPosition = map.proportionalPosition(last, bounds.minimum, bounds.maximum);
assert.ok(activationPosition - firstPosition > lastPosition - activationPosition,
  "time axis must use elapsed time rather than equal event spacing");

assert.equal(map.axisPrice(224.512345, "AAPL", 30), "224.51");
assert.equal(map.axisPrice(0.004321, "TOKENUSDT", 0.01), "0.004321");

const duplicateIdentityDetail = {
  observations: [{
    canonical_event_id: "shared-event", source_tracker: "IPDA_ROUTE", event_type: "BTD_OBSERVATION",
    route: "BTD", price: "100.25", effective_at: "2026-11-01T00:00:00Z", known_at: "2026-11-01T00:00:01Z",
  }],
  pressure_observations: [{
    canonical_event_id: "shared-event", source_tracker: "PRESSURE", event_type: "PRESSURE_HIGHER",
    direction: "HIGHER", price: "100.25", effective_at: "2026-11-01T00:00:00Z", known_at: "2026-11-01T00:00:01Z",
  }],
  near_miss_events: [], mrz_lifecycles: [],
};
const canonicalRows = map.timelineRows(duplicateIdentityDetail);
assert.equal(canonicalRows.length, 1, "one canonical observation must render as one timeline row");
assert.deepEqual(canonicalRows[0]._classifications, ["BTD", "Pressure"]);
assert.deepEqual(canonicalRows[0]._trackers, ["IPDA_ROUTE", "PRESSURE"]);

const comparisonBounds = map.comparisonTimeBounds([
  { ...detail, as_known_at: "2026-11-12T00:00:00Z" },
  {
    as_known_at: "2026-11-12T00:00:00Z",
    observations: [{ effective_at: "2026-09-01T00:00:00Z" }],
    near_miss_events: [], mrz_lifecycles: [], pressure_observations: [],
  },
], 0);
assert.equal(comparisonBounds.minimum, first, "comparison uses the earliest event from either symbol");
assert.equal(comparisonBounds.maximum, new Date("2026-11-12T00:00:00Z").getTime(), "comparison uses one shared latest timestamp");

require("../app/static/opportunity-comparison.js");
const comparison = global.edgeOpportunityComparison;
const checkpoints = comparison.unifiedCheckpoints([
  {
    symbol: "AMD", as_of: "2026-11-12T00:00:00Z",
    observations: [{ canonical_event_id: "amd-1", source_tracker: "IPDA_ROUTE", event_type: "BTD_OBSERVATION", effective_at: "2026-09-01T00:00:00Z", known_at: "2026-09-01T00:00:01Z" }],
    near_miss_events: [], mrz_lifecycles: [], pressure_observations: [],
  },
  {
    symbol: "NVDA", as_of: "2026-11-12T00:00:00Z",
    observations: [{ canonical_event_id: "nvda-1", source_tracker: "IPDA_ROUTE", event_type: "STR_OBSERVATION", effective_at: "2026-08-31T00:00:00Z", known_at: "2026-09-02T00:00:01Z" }],
    near_miss_events: [], mrz_lifecycles: [], pressure_observations: [],
  },
]);
assert.deepEqual(checkpoints.slice(0, 2).map((item) => item.symbol), ["AMD", "NVDA"], "replay checkpoints follow knowledge time across both symbols");
assert.equal(
  comparison.cursorIndexAtOrBefore(
    ["2026-11-09T11:14:05.375308Z", "2026-11-09T11:14:05.900000Z"],
    "2026-11-09T11:14:05.375308Z",
  ),
  0,
  "replay selection preserves an exact microsecond canonical checkpoint",
);

console.log("Opportunity Map tests passed");
