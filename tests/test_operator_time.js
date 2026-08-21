const assert = require("node:assert/strict");
const {
  formatOperatorTimestampUtcMinus4,
} = require("../app/static/operator-time.js");

const cases = [
  ["ordinary same-day conversion", "2026-08-21T12:30:00Z", "21 Aug 2026 · 08:30 UTC−4"],
  ["previous-day conversion", "2026-08-21T01:30:00Z", "20 Aug 2026 · 21:30 UTC−4"],
  ["month boundary", "2026-09-01T02:15:00Z", "31 Aug 2026 · 22:15 UTC−4"],
  ["year boundary", "2027-01-01T01:05:00Z", "31 Dec 2026 · 21:05 UTC−4"],
  ["fixed winter offset", "2026-01-15T12:00:00Z", "15 Jan 2026 · 08:00 UTC−4"],
];

for (const [name, input, expected] of cases) {
  assert.equal(formatOperatorTimestampUtcMinus4(input), expected, name);
}

const input = "2026-08-21T01:30:00Z";
const expected = "20 Aug 2026 · 21:30 UTC−4";
for (const timezone of ["UTC", "Asia/Singapore", "America/Los_Angeles"]) {
  process.env.TZ = timezone;
  assert.equal(
    formatOperatorTimestampUtcMinus4(input),
    expected,
    `formatter must ignore system timezone ${timezone}`,
  );
}

assert.equal(formatOperatorTimestampUtcMinus4(null), null, "missing timestamp");
assert.equal(formatOperatorTimestampUtcMinus4("not-a-timestamp"), null, "invalid timestamp");

console.log("operator timestamp tests passed");
