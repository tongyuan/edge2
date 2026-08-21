const assert = require("node:assert/strict");
const {
  primaryLocationKeys,
  secondaryLocationKeys,
  hasActiveMrz,
  groupSymbolsByLocation,
} = require("../app/static/heatmap-state.js");

assert.deepEqual(primaryLocationKeys, [
  "deep_discount",
  "shallow_discount",
  "shallow_premium",
  "deep_premium",
]);
assert.deepEqual(secondaryLocationKeys, [
  "below_ipda_range",
  "above_ipda_range",
  "unavailable",
]);

assert.equal(hasActiveMrz({ mrz_status: "active" }), true, "authoritative active state");
assert.equal(hasActiveMrz({ mrz_status: "unestablished" }), false, "unestablished state");
assert.equal(hasActiveMrz({ confirming_observation_count: 4 }), false, "candidate concentration");
assert.equal(hasActiveMrz({ route_owner: "BTD" }), false, "route owner alone");
assert.equal(hasActiveMrz({ mrz_events: [{ event_type: "activated" }] }), false, "historical MRZ");

const active = {
  symbol: "GRAB",
  mrz_status: "active",
  current_price_location: "deep_discount",
  structural_location: "deep_premium_core_mrz",
};
const inactive = {
  symbol: "NIO",
  mrz_status: "unestablished",
  current_price_location: "deep_discount",
  structural_location: "shallow_premium_core_mrz",
};
const secondary = {
  symbol: "MU",
  mrz_status: "active",
  current_price_location: "above_ipda_range",
};
const unavailable = {
  symbol: "QQQ",
  mrz_status: "active",
  current_price_location: null,
};
const groups = groupSymbolsByLocation([inactive, unavailable, secondary, active]);

assert.deepEqual(groups.deep_discount, [active, inactive], "bucket and alphabetical order");
assert.deepEqual(groups.deep_premium, [], "MRZ location must not determine bucket");
assert.deepEqual(groups.above_ipda_range, [secondary], "secondary bucket");
assert.deepEqual(groups.unavailable, [unavailable], "unavailable bucket");

console.log("heatmap state tests passed");
