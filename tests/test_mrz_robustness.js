"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const {
  displacementText,
  durationText,
  filterReports,
  operatorViewCounts,
  normalizedSymbolQuery,
  operatorCardSectionFromHash,
  operatorCardSymbolFromSearch,
  percentageText,
} = require("../app/static/mrz-robustness.js");

const html = fs.readFileSync(require.resolve("../app/static/mrz-robustness.html"), "utf8");
const source = fs.readFileSync(require.resolve("../app/static/mrz-robustness.js"), "utf8");

assert.equal(durationText("219600"), "2d 13h");
assert.equal(percentageText("77.777"), "77.8%");
assert.equal(displacementText("6.210106", "ABOVE"), "↑ +6.2%");
assert.equal(normalizedSymbolQuery(" btcusdt "), "BTCUSDT");
assert.equal(operatorCardSymbolFromSearch("?symbol=NASDAQ%3ANDX"), "NASDAQ:NDX");
assert.equal(operatorCardSectionFromHash("#post-activation"), "post-activation");
assert.equal(operatorCardSectionFromHash("#other"), null);

const reports = [
  { symbol: "BTCUSDT", migration: { has_migrated: false } },
  { symbol: "ETHUSDT", migration: { has_migrated: true } },
];
assert.deepEqual(filterReports(reports, "all", "btc"), [reports[0]]);
assert.deepEqual(filterReports(reports, "all", ""), reports);
assert.deepEqual(operatorViewCounts(reports), { all: 2 });

assert.match(html, /Successor Evidence/);
assert.match(html, /id="activeReports"/);
assert.doesNotMatch(html, /filterPressure|pressureCount|>Pressure</);
assert.doesNotMatch(source, /filterMode\s*===\s*["']pressure["']/);
assert.doesNotMatch(source, /current-pressure-panel|CUMULATIVE SINCE ACTIVATION/);

console.log("MRZ operation card retirement tests passed");
