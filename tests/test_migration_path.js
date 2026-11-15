"use strict";

const assert = require("node:assert/strict");
global.window = global;
const path = require("../app/static/migration-path.js");

assert.equal(path.countLabel(0), "0 migrations");
assert.equal(path.countLabel(1), "1 migration");
assert.equal(path.countLabel(13), "13 migrations");

const records = path.prepareMigrationRecords([
  { event_key: "m3", sequence: 3, route: "STR", activation_event_key: "a1", to_lower: "120", to_upper: "124", midpoint: null, observed_at: "2026-09-03T00:00:00Z" },
  { event_key: "m2", sequence: 2, route: "BTD", activation_event_key: "a1", to_lower: "110", to_upper: "114", midpoint: "112", observed_at: "2026-09-02T00:00:00Z" },
  { event_key: "m5", sequence: 5, route: "STR", activation_event_key: "a4", to_lower: "130", to_upper: "136", midpoint: "133", observed_at: "2026-09-04T00:00:00Z" },
]);
assert.deepEqual(records.map((item) => item.sequence), [2, 3, 5], "actual event time controls chronological ordering");
assert.equal(records[0].midpoint, 112);
assert.equal(records[0].segmentId, records[1].segmentId, "route changes inside one activation chain remain connected");
assert.notEqual(records[1].segmentId, records[2].segmentId, "activation boundaries break the progression line");

const chronological = path.prepareMigrationRecords([
  { event_key: "late-sequence", sequence: 20, activation_event_key: "a1", to_lower: "3.10", to_upper: "3.30", observed_at: "2026-09-01T00:00:00Z" },
  { event_key: "early-sequence", sequence: 2, activation_event_key: "a1", to_lower: "3.20", to_upper: "3.40", observed_at: "2026-09-02T00:00:00Z" },
]);
assert.deepEqual(chronological.map((item) => item.event_key), ["late-sequence", "early-sequence"], "event time is never replaced by an arbitrary sequence index");

const thirteen = Array.from({ length: 13 }, (_, index) => ({ sequence: index + 2 }));
assert.equal(path.latestWindowStart(thirteen.length), 7);
assert.deepEqual(path.recordsInWindow(thirteen, path.latestWindowStart(thirteen.length)).map((item) => item.sequence), [9, 10, 11, 12, 13, 14], "the default window contains the latest six states");
assert.deepEqual(path.recordsInWindow(thirteen, 2).map((item) => item.sequence), [4, 5, 6, 7, 8, 9], "earlier consecutive states remain navigable");
assert.equal(path.clampWindowStart(13, 99), 7);

const priceRecords = path.prepareMigrationRecords([
  { event_key: "p1", sequence: 1, activation_event_key: "p", to_lower: "2051.83", to_upper: "2059.33", observed_at: "2026-10-01T00:00:00Z" },
  { event_key: "p2", sequence: 2, activation_event_key: "p", to_lower: "2241.03", to_upper: "2252.96", observed_at: "2026-11-01T00:00:00Z" },
]);
const scale = path.linearPriceScale(priceRecords);
assert.equal(path.migrationPricePrecision(priceRecords), 2, "canonical bound precision controls chart labels");
assert.ok(scale.minimum > 0, "the linear price domain is not forced to zero");
assert.ok(scale.minimum < 2051.83 && scale.maximum > 2252.96, "the price domain pads actual displayed bounds");
assert.ok(scale.ticks.every((value, index) => index === 0 || value > scale.ticks[index - 1]), "price ticks are strictly monotonic");

assert.deepEqual(path.collisionAwareIndices([0, 12, 100, 112], 30, [3]), [1, 3], "dense optional labels are suppressed while the latest label remains visible");

console.log("Migration path tests passed");
