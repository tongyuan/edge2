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
assert.deepEqual(records.map((item) => item.sequence), [2, 3, 5], "canonical sequence controls stable ordering");
assert.equal(records[0].midpoint, 112);
assert.notEqual(records[0].segmentId, records[1].segmentId, "route boundaries break the progression line");
assert.notEqual(records[1].segmentId, records[2].segmentId, "activation boundaries break the progression line");

console.log("Migration path tests passed");
