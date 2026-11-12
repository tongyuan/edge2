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

console.log("Opportunity Map tests passed");
