const assert = require("node:assert/strict");
const {
  primaryLocationKeys,
  secondaryLocationKeys,
  hasActiveMrz,
  activityTier,
  routeAlignedObservationCount,
  concentrationCheckEligible,
  concentrationRankingContext,
  routeAlignedActivity,
  activityTooltipText,
  accessibleChipLabel,
  compareSymbolsByActivity,
  compareSymbolsForHeatmap,
  preservedSelectedSymbol,
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

assert.equal(concentrationCheckEligible({
  btd_window_observation_count: 4,
  str_window_observation_count: 0,
}, 4), true, "BTD route independently meets the minimum");
assert.equal(concentrationCheckEligible({
  btd_window_observation_count: 0,
  str_window_observation_count: 4,
}, 4), true, "STR route independently meets the minimum");
assert.equal(concentrationCheckEligible({
  btd_window_observation_count: 4,
  str_window_observation_count: 4,
}, 4), true, "both routes may meet the minimum");
assert.equal(concentrationCheckEligible({
  btd_window_observation_count: 2,
  str_window_observation_count: 2,
}, 4), false, "opposite-route counts are never summed");
assert.equal(concentrationCheckEligible({
  btd_window_observation_count: 3,
  str_window_observation_count: 3,
}, 4), false, "both routes below minimum remain ineligible");
assert.equal(concentrationCheckEligible({
  mrz_status: "active",
  btd_window_observation_count: 4,
  str_window_observation_count: 1,
}, 4), true, "active status does not suppress independent evidence readiness");
assert.equal(concentrationCheckEligible({
  btd_window_observation_count: 20,
  str_window_observation_count: 20,
}, null), false, "a missing production threshold fails safely");

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
const groups = groupSymbolsByLocation([inactive, unavailable, secondary, active], 4);

assert.deepEqual(groups.deep_discount, [active, inactive], "equal-count bucket tie is alphabetical");
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

const deepPremiumSymbols = [
  {
    symbol: "HSI",
    mrz_status: "unestablished",
    current_price_location: "deep_premium",
    btd_window_observation_count: 20,
    str_window_observation_count: 0,
  },
  {
    symbol: "BMNR",
    mrz_status: "unestablished",
    current_price_location: "deep_premium",
    btd_window_observation_count: 20,
    str_window_observation_count: 1,
  },
  {
    symbol: "BTCUSDT",
    mrz_status: "unestablished",
    current_price_location: "deep_premium",
    btd_window_observation_count: 20,
    str_window_observation_count: 2,
  },
  {
    symbol: "ETHUSDT",
    mrz_status: "unestablished",
    current_price_location: "deep_premium",
    btd_window_observation_count: 0,
    str_window_observation_count: 4,
  },
];
const sortedPremium = groupSymbolsByLocation(deepPremiumSymbols, 4).deep_premium;
assert.deepEqual(
  sortedPremium.map(({ symbol }) => symbol),
  ["ETHUSDT", "BTCUSDT", "BMNR", "HSI"],
  "premium uses numeric descending STR counts and retains row-major DOM order",
);
assert.equal(routeAlignedObservationCount(deepPremiumSymbols[0]), 0);
assert.equal(routeAlignedObservationCount(deepPremiumSymbols[3]), 4);

const discountSymbols = [
  {
    symbol: "ALPHA",
    mrz_status: "unestablished",
    current_price_location: "shallow_discount",
    btd_window_observation_count: 2,
    str_window_observation_count: 20,
  },
  {
    symbol: "OMEGA",
    mrz_status: "unestablished",
    current_price_location: "shallow_discount",
    btd_window_observation_count: 10,
    str_window_observation_count: 0,
  },
];
assert.deepEqual(
  groupSymbolsByLocation(discountSymbols, 4).shallow_discount.map(({ symbol }) => symbol),
  ["OMEGA", "ALPHA"],
  "discount uses numeric BTD counts and ignores opposite-route STR counts",
);

const equalCounts = [
  { symbol: "ZETA", current_price_location: "deep_discount", btd_window_observation_count: 4 },
  { symbol: "ALPHA", current_price_location: "deep_discount", btd_window_observation_count: 4 },
];
assert.equal(compareSymbolsByActivity(equalCounts[0], equalCounts[1]) > 0, true);
assert.deepEqual(
  groupSymbolsByLocation(equalCounts, 4).deep_discount.map(({ symbol }) => symbol),
  ["ALPHA", "ZETA"],
  "equal counts use normalized symbol ascending",
);

const rankedCandidates = [
  {
    symbol: "NORMAL",
    mrz_status: "unestablished",
    current_price_location: "deep_premium",
    str_window_observation_count: 3,
  },
  {
    symbol: "PLTR",
    mrz_status: "unestablished",
    current_price_location: "deep_premium",
    str_window_observation_count: 5,
    concentration_ranking: {
      route: "STR",
      observation_count: 5,
      minimum_required_allowance_pct: "8.11",
    },
  },
  {
    symbol: "SE",
    mrz_status: "unestablished",
    current_price_location: "deep_premium",
    str_window_observation_count: 4,
    concentration_ranking: {
      route: "STR",
      observation_count: 4,
      minimum_required_allowance_pct: "3.32",
    },
  },
  {
    symbol: "ACTIVE",
    mrz_status: "active",
    route_owner: "STR",
    current_price_location: "deep_premium",
    str_window_observation_count: 4,
    concentration_ranking: {
      route: "STR",
      observation_count: 4,
      minimum_required_allowance_pct: "12.00",
    },
  },
];
assert.deepEqual(
  groupSymbolsByLocation(rankedCandidates, 4).deep_premium.map(({ symbol }) => symbol),
  ["ACTIVE", "SE", "PLTR", "NORMAL"],
  "active leads, then tighter eligible candidates, then non-eligible symbols",
);
assert.equal(compareSymbolsForHeatmap(rankedCandidates[2], rankedCandidates[1], 4) < 0, true);
assert.deepEqual(concentrationRankingContext(rankedCandidates[2], 4), {
  minimumAllowance: 3.32,
  observationCount: 4,
  route: "STR",
});

const equalAllowanceCandidates = [
  {
    symbol: "FOUR",
    mrz_status: "unestablished",
    current_price_location: "deep_discount",
    btd_window_observation_count: 4,
    concentration_ranking: {
      route: "BTD", observation_count: 4, minimum_required_allowance_pct: "2.00",
    },
  },
  {
    symbol: "FIVE",
    mrz_status: "unestablished",
    current_price_location: "deep_discount",
    btd_window_observation_count: 5,
    concentration_ranking: {
      route: "BTD", observation_count: 5, minimum_required_allowance_pct: "2.0",
    },
  },
];
assert.deepEqual(
  groupSymbolsByLocation(equalAllowanceCandidates, 4).deep_discount.map(({ symbol }) => symbol),
  ["FIVE", "FOUR"],
  "equal allowance uses eligible-route observation count descending",
);

const activePriority = [
  {
    symbol: "ACTIVE",
    mrz_status: "active",
    route_owner: "STR",
    current_price_location: "shallow_premium",
    str_window_observation_count: 1,
  },
  {
    symbol: "INACTIVE",
    mrz_status: "unestablished",
    current_price_location: "shallow_premium",
    str_window_observation_count: 9,
  },
];
assert.deepEqual(
  groupSymbolsByLocation(activePriority, 4).shallow_premium.map(({ symbol }) => symbol),
  ["ACTIVE", "INACTIVE"],
  "active MRZ authority overrides candidate observation count",
);
assert.equal(preservedSelectedSymbol("ETHUSDT", sortedPremium), "ETHUSDT");
assert.equal(preservedSelectedSymbol("MISSING", sortedPremium), "");

console.log("heatmap state tests passed");
