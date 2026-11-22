(function initializeChartViewport(globalObject) {
  "use strict";

  const DAY_MS = 86400000;

  function clamp(value, minimum, maximum) {
    return Math.max(minimum, Math.min(maximum, Number(value)));
  }

  function createTimeViewport({ earliest, cutoff, rangeDays = 0, minimumSpan = DAY_MS }) {
    const safeCutoff = Number.isFinite(Number(cutoff)) ? Number(cutoff) : Date.now();
    const safeEarliest = Number.isFinite(Number(earliest)) ? Math.min(Number(earliest), safeCutoff) : safeCutoff - minimumSpan;
    const requestedSpan = Number(rangeDays) > 0 ? Number(rangeDays) * DAY_MS : Math.max(minimumSpan, safeCutoff - safeEarliest);
    const baseMinimum = Number(rangeDays) > 0 ? safeCutoff - requestedSpan : safeEarliest;
    const baseSpan = Math.max(minimumSpan, safeCutoff - baseMinimum);
    return {
      minimum: baseMinimum,
      maximum: safeCutoff,
      extentMinimum: Math.min(safeEarliest, baseMinimum),
      extentMaximum: safeCutoff,
      baseSpan,
      minimumSpan: Math.min(minimumSpan, baseSpan),
    };
  }

  function constrainTimeViewport(viewport, minimum, maximum) {
    const span = clamp(
      Number(maximum) - Number(minimum),
      viewport.minimumSpan,
      viewport.baseSpan,
    );
    let nextMinimum = Number(minimum);
    let nextMaximum = nextMinimum + span;
    if (nextMaximum > viewport.extentMaximum) {
      nextMaximum = viewport.extentMaximum;
      nextMinimum = nextMaximum - span;
    }
    if (nextMinimum < viewport.extentMinimum) {
      nextMinimum = viewport.extentMinimum;
      nextMaximum = nextMinimum + span;
    }
    return { ...viewport, minimum: nextMinimum, maximum: nextMaximum };
  }

  function zoomTimeViewport(viewport, factor, anchorRatio = 0.5) {
    const ratio = clamp(anchorRatio, 0, 1);
    const currentSpan = viewport.maximum - viewport.minimum;
    const nextSpan = clamp(currentSpan / Math.max(0.01, Number(factor) || 1), viewport.minimumSpan, viewport.baseSpan);
    const anchor = viewport.minimum + currentSpan * ratio;
    return constrainTimeViewport(viewport, anchor - nextSpan * ratio, anchor + nextSpan * (1 - ratio));
  }

  function panTimeViewport(viewport, deltaMilliseconds) {
    const delta = Number(deltaMilliseconds) || 0;
    return constrainTimeViewport(viewport, viewport.minimum + delta, viewport.maximum + delta);
  }

  function restoreTimeViewport(baseViewport, minimum, maximum) {
    if (!Number.isFinite(Number(minimum)) || !Number.isFinite(Number(maximum)) || Number(maximum) <= Number(minimum)) return baseViewport;
    return constrainTimeViewport(baseViewport, Number(minimum), Number(maximum));
  }

  function clampWindowStart(recordCount, requestedStart, windowSize) {
    const count = Math.max(0, Number(recordCount) || 0);
    const size = Math.max(1, Number(windowSize) || 1);
    return clamp(Number(requestedStart) || 0, 0, Math.max(0, count - size));
  }

  const exported = {
    DAY_MS,
    clamp,
    clampWindowStart,
    constrainTimeViewport,
    createTimeViewport,
    panTimeViewport,
    restoreTimeViewport,
    zoomTimeViewport,
  };
  globalObject.edgeChartViewport = exported;
  if (typeof module === "object" && module.exports) module.exports = exported;
}(globalThis));
