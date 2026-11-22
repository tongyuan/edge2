"use strict";

const assert = require("node:assert/strict");
global.window = global;
require("../app/static/chart-viewport.js");
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

const canonicalStates = path.prepareMigrationRecords([
  { event_key: "a1", event_type: "MRZ_ACTIVATED", sequence: 1, route: "STR", activation_event_key: "a1", lower: "130.0", upper: "132.0", midpoint: "131.0", observed_at: "2026-09-01T00:00:00Z", first_known_at: "2026-09-01T00:01:00Z" },
  { event_key: "m2", event_type: "MRZ_MIGRATED", sequence: 2, route: "STR", activation_event_key: "a1", lower: "125.0", upper: "127.0", midpoint: "126.0", observed_at: "2026-09-02T00:00:00Z", first_known_at: "2026-09-02T00:01:00Z" },
]);
assert.deepEqual(canonicalStates.map((item) => item.event_type), ["MRZ_ACTIVATED", "MRZ_MIGRATED"], "the initial canonical activation is retained with migration successors");
assert.equal(canonicalStates[0].midpoint, 131);

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
const zoomedScale = path.linearPriceScale(priceRecords, 5, .02);
const expandedScale = path.linearPriceScale(priceRecords, 5, .32);
assert.equal(path.migrationPricePrecision(priceRecords), 2, "canonical bound precision controls chart labels");
assert.ok(scale.minimum > 0, "the linear price domain is not forced to zero");
assert.ok(scale.minimum < 2051.83 && scale.maximum > 2252.96, "the price domain pads actual displayed bounds");
assert.ok(scale.ticks.every((value, index) => index === 0 || value > scale.ticks[index - 1]), "price ticks are strictly monotonic");
assert.ok((zoomedScale.maximum - zoomedScale.minimum) < (scale.maximum - scale.minimum), "short histories visibly zoom into the price domain");
assert.ok((expandedScale.maximum - expandedScale.minimum) > (scale.maximum - scale.minimum), "short histories visibly zoom out from the price domain");

assert.deepEqual(path.collisionAwareIndices([0, 12, 100, 112], 30, [3]), [1, 3], "dense optional labels are suppressed while the latest label remains visible");

assert.equal(path.canHidePath(false), true, "the embedded symbol workspace can hide its generated path");
assert.equal(path.canHidePath(true), false, "the docked chart never reveals unrelated symbol-workspace content");
const detail = { hidden: false };
global.document = { querySelector: (selector) => selector === "#migrationRecordDetail" ? detail : null };
path.dismissDetail();
assert.equal(detail.hidden, true, "tapping blank chart space can dismiss the selected-state evidence dialog");

console.log("Migration path tests passed");
