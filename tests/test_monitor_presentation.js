const assert = require("node:assert/strict");
const {
  formatFormationDuration,
  buildEvidencePresentation,
  formatLatestObservationContext,
} = require("../app/static/monitor-presentation.js");
const {
  formatOperatorTimestampUtcMinus4,
} = require("../app/static/operator-time.js");

assert.equal(formatFormationDuration(1080), "18m");
assert.equal(formatFormationDuration(19440), "5h 24m");
assert.equal(formatFormationDuration(280800), "3d 6h");
assert.equal(formatFormationDuration(30), "<1m");
assert.equal(formatFormationDuration(0), "0m");
assert.equal(formatFormationDuration(null), null);

assert.deepEqual(
  buildEvidencePresentation({
    mrz_status: "unestablished",
    btd_window_observation_count: 3,
    btd_window_started_at: "2026-08-20T18:05:00Z",
    str_window_observation_count: 6,
    str_window_started_at: "2026-08-20T20:42:00Z",
  }, formatOperatorTimestampUtcMinus4),
  {
    primary: "No qualifying concentration",
    secondary: [
      "BTD · 3 reclaim observations",
      "BTD window since · 20 Aug 2026 · 14:05 UTC−4",
      "STR · 6 rejection observations",
      "STR window since · 20 Aug 2026 · 16:42 UTC−4",
    ],
  },
);

assert.deepEqual(
  buildEvidencePresentation({
    mrz_status: "unestablished",
    btd_window_observation_count: 0,
    btd_window_started_at: null,
    str_window_observation_count: 1,
    str_window_started_at: "2026-08-20T20:42:00Z",
  }, formatOperatorTimestampUtcMinus4),
  {
    primary: "No qualifying concentration",
    secondary: [
      "BTD · 0 reclaim observations",
      "STR · 1 rejection observation",
      "STR window since · 20 Aug 2026 · 16:42 UTC−4",
    ],
  },
);

assert.deepEqual(
  buildEvidencePresentation({
    mrz_status: "unestablished",
    btd_window_observation_count: 0,
    btd_window_started_at: "2026-08-20T18:05:00Z",
    str_window_observation_count: 0,
    str_window_started_at: "2026-08-20T20:42:00Z",
  }, formatOperatorTimestampUtcMinus4),
  { primary: "No qualifying concentration", secondary: [] },
);

assert.deepEqual(
  buildEvidencePresentation({
    mrz_status: "active",
    route_owner: "BTD",
    supporting_observation_count: 4,
    formation_duration_seconds: 11700,
    btd_window_started_at: "2026-08-20T18:05:00Z",
  }, formatOperatorTimestampUtcMinus4),
  {
    primary: "4 qualifying reclaim observations",
    secondary: ["Formation duration · 3h 15m"],
  },
);

assert.deepEqual(
  buildEvidencePresentation({
    mrz_status: "active",
    route_owner: "STR",
    supporting_observation_count: 6,
    formation_duration_seconds: 280800,
  }),
  {
    primary: "6 qualifying rejection observations",
    secondary: ["Formation duration · 3d 6h"],
  },
);

assert.deepEqual(
  buildEvidencePresentation({
    mrz_status: "active",
    route_owner: "BTD",
    supporting_observation_count: 4,
    formation_duration_seconds: null,
  }),
  { primary: "4 qualifying reclaim observations", secondary: [] },
);

assert.equal(
  formatLatestObservationContext(
    {
      latest_observation_route: "BTD",
      latest_observation_type: "reclaim",
      latest_observed_at: "2026-08-21T01:30:00Z",
    },
    formatOperatorTimestampUtcMinus4,
  ),
  "BTD reclaim · 20 Aug 2026 · 21:30 UTC−4",
);

assert.equal(
  formatLatestObservationContext(
    {
      latest_observation_route: "STR",
      latest_observation_type: "rejection",
      latest_observed_at: "2026-08-21T01:30:00Z",
    },
    formatOperatorTimestampUtcMinus4,
  ),
  "STR rejection · 20 Aug 2026 · 21:30 UTC−4",
);

console.log("monitor presentation tests passed");
