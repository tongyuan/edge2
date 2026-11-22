"use strict";

const assert = require("node:assert/strict");
const viewport = require("../app/static/chart-viewport.js");

const cutoff = Date.parse("2026-11-18T08:00:00Z");
const sparseEarliest = Date.parse("2026-11-14T08:00:00Z");
const ninety = viewport.createTimeViewport({ earliest: sparseEarliest, cutoff, rangeDays: 90 });
assert.equal(ninety.maximum, cutoff);
assert.equal(ninety.maximum - ninety.minimum, 90 * viewport.DAY_MS, "sparse 90D views retain the exact selected duration");

const zoomed = viewport.zoomTimeViewport(ninety, 2, 0.75);
assert.ok(zoomed.maximum - zoomed.minimum < ninety.maximum - ninety.minimum, "zoom changes only the visible time domain");
assert.ok(zoomed.maximum <= cutoff, "zoom never reveals future-known evidence");

const pannedFuture = viewport.panTimeViewport(zoomed, 365 * viewport.DAY_MS);
assert.equal(pannedFuture.maximum, cutoff, "panning is bounded by the replay cutoff");
const pannedPast = viewport.panTimeViewport(zoomed, -365 * viewport.DAY_MS);
assert.ok(pannedPast.minimum >= ninety.extentMinimum, "panning is bounded by the selected evidence extent");

const restored = viewport.restoreTimeViewport(ninety, zoomed.minimum, zoomed.maximum);
assert.equal(restored.minimum, zoomed.minimum);
assert.equal(restored.maximum, zoomed.maximum);
assert.equal(viewport.restoreTimeViewport(ninety, 200, 100), ninety, "invalid docked state falls back safely");
assert.equal(viewport.clampWindowStart(13, 99, 6), 7);

console.log("Chart viewport tests passed");
