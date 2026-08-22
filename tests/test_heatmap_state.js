const assert = require("node:assert/strict");
const {
  primaryLocationKeys,
  secondaryLocationKeys,
  hasActiveMrz,
  activityTier,
  routeAlignedActivity,
  activityTooltipText,
  accessibleChipLabel,
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

const premiumActivity = routeAlignedActivity({
  symbol: "ETHUSDT",
  mrz_status: "unestablished",
  current_price_location: "deep_premium",
  btd_window_observation_count: 20,
  str_window_observation_count: 4,
});
assert.deepEqual(premiumActivity, {
  count: 4,
  route: "STR",
  observationType: "rejection",
  tier: "medium",
}, "premium activity uses only retained STR rejections");

assert.deepEqual(routeAlignedActivity({
  symbol: "SPXUSDT",
  mrz_status: "unestablished",
  current_price_location: "shallow_discount",
  btd_window_observation_count: 9,
  str_window_observation_count: 20,
}), {
  count: 9,
  route: "BTD",
  observationType: "reclaim",
  tier: "medium-high",
}, "discount activity uses only retained BTD reclaims");

assert.equal(routeAlignedActivity({
  mrz_status: "unestablished",
  current_price_location: null,
  btd_window_observation_count: 4,
}), null, "missing location falls back safely");
assert.equal(routeAlignedActivity({
  mrz_status: "unestablished",
  current_price_location: "deep_discount",
}), null, "missing aligned count falls back safely");
assert.equal(routeAlignedActivity({
  mrz_status: "active",
  current_price_location: "deep_discount",
  btd_window_observation_count: 20,
}), null, "active MRZ remains the higher-priority authoritative state");
assert.equal(routeAlignedActivity({
  mrz_status: "unestablished",
  current_price_location: "deep_discount",
  btd_window_observation_count: 27,
}).count, 20, "activity display count is capped at the retained-window maximum");

[
  [0, "none"],
  [1, "low"],
  [3, "low"],
  [4, "medium"],
  [7, "medium"],
  [8, "medium-high"],
  [11, "medium-high"],
  [12, "high"],
  [15, "high"],
  [16, "strongest"],
  [20, "strongest"],
  [21, "strongest"],
].forEach(([count, tier]) => assert.equal(activityTier(count), tier, `${count} maps to ${tier}`));

assert.equal(activityTooltipText(0), "0 observations");
assert.equal(activityTooltipText(1), "1 observation");
assert.equal(activityTooltipText(2), "2 observations");
assert.equal(activityTooltipText(null), null);
assert.equal(
  accessibleChipLabel({
    symbol: "ETHUSDT",
    mrz_status: "unestablished",
    current_price_location: "deep_premium",
    btd_window_observation_count: 9,
    str_window_observation_count: 4,
  }, "Deep Premium"),
  "ETHUSDT, Deep Premium, 4 STR rejection observations, no qualifying concentration, MRZ unestablished",
);

console.log("heatmap state tests passed");
