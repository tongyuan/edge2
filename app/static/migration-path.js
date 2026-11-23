(function initializeMigrationPath(globalObject) {
  "use strict";
  const DEFAULT_WINDOW_SIZE = 6;
  const chartViewport = globalObject.edgeChartViewport;
  let model = { symbol: "", records: [], developments: [], selectedDevelopment: null, migrationCount: 0, generated: false, selected: null, hits: [], windowStart: 0, windowSize: DEFAULT_WINDOW_SIZE, intelligence: null, pointers: new Map(), pinchDistance: 0, suppressClick: false, chartOnly: false, priceZoom: 0 };
  let resizeObserver = null;

  function prepareMigrationRecords(rows = []) {
    return rows.map((row) => {
      const lower = Number(row.to_lower ?? row.lower); const upper = Number(row.to_upper ?? row.upper);
      const sequence = Number(row.sequence); const activation = row.activation_event_key || `unlinked:${row.event_key}`;
      const midpoint = Number(row.midpoint);
      const calculated = { midpoint: (lower + upper) / 2 };
      return { ...row, lower, upper, midpoint: Number.isFinite(midpoint) ? midpoint : calculated.midpoint, sequence, time: new Date(row.observed_at).getTime(), chainId: activation, segmentId: activation };
    }).filter((row) => Number.isFinite(row.lower) && Number.isFinite(row.upper) && row.lower <= row.upper && Number.isFinite(row.time) && Number.isFinite(row.sequence))
      .sort((a, b) => a.time - b.time || a.sequence - b.sequence || String(a.event_key).localeCompare(String(b.event_key)));
  }

  function dateLabel(value) { return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(value)); }
  function countLabel(count) { return `${count} migration${count === 1 ? "" : "s"}`; }
  function byId(id) { return document.querySelector(id); }
  function canHidePath(chartOnly) { return !chartOnly; }
  function dismissDetail() { const detail = byId("#migrationRecordDetail"); if (detail) detail.hidden = true; }

  function decimalPlaces(value) {
    const text = String(value ?? "").trim().toLowerCase();
    if (!text || text.includes("e")) {
      const number = Number(value); if (!Number.isFinite(number)) return 0;
      const normalized = number.toFixed(8).replace(/0+$/, "");
      return normalized.includes(".") ? normalized.split(".")[1].length : 0;
    }
    return text.includes(".") ? text.split(".")[1].replace(/0+$/, "").length : 0;
  }

  function migrationPricePrecision(records = []) {
    return Math.min(8, Math.max(0, ...records.flatMap((record) => [
      decimalPlaces(record.to_lower ?? record.lower), decimalPlaces(record.to_upper ?? record.upper),
    ])));
  }

  function niceStep(span, targetTickCount = 5) {
    if (!Number.isFinite(span) || span <= 0) return 1;
    const rough = span / Math.max(1, targetTickCount); const power = 10 ** Math.floor(Math.log10(rough)); const fraction = rough / power;
    return (fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 5 ? 5 : 10) * power;
  }

  function linearPriceScale(records = [], targetTickCount = 5, paddingFactor = .08) {
    const values = records.flatMap((record) => [record.lower, record.upper]).filter(Number.isFinite);
    if (!values.length) return { minimum: 0, maximum: 1, ticks: [0, 1], step: 1 };
    const actualMinimum = Math.min(...values); const actualMaximum = Math.max(...values); const span = actualMaximum - actualMinimum;
    const normalizedPadding = Math.max(.005, Number(paddingFactor) || .08);
    const padding = Math.max(span * normalizedPadding, Math.abs((actualMinimum + actualMaximum) / 2 || 1) * .002);
    const paddedMinimum = actualMinimum - padding; const paddedMaximum = actualMaximum + padding; const step = niceStep(paddedMaximum - paddedMinimum, targetTickCount);
    let minimum = paddedMinimum; let maximum = paddedMaximum;
    if (actualMinimum > 0 && minimum <= 0) minimum = Math.max(Number.EPSILON, paddedMinimum);
    if (maximum <= minimum) maximum = minimum + step;
    const ticks = []; const firstTick = Math.ceil((minimum - (step * 1e-9)) / step) * step;
    for (let value = firstTick; value <= maximum + (step * 1e-9); value += step) { ticks.push(Number(value.toPrecision(12))); if (ticks.length > 12) break; }
    return { minimum, maximum, ticks, step };
  }

  function clampWindowStart(recordCount, requestedStart, windowSize = DEFAULT_WINDOW_SIZE) {
    return chartViewport.clampWindowStart(recordCount, requestedStart, windowSize);
  }
  function latestWindowStart(recordCount, windowSize = DEFAULT_WINDOW_SIZE) { return Math.max(0, recordCount - windowSize); }
  function recordsInWindow(records, windowStart, windowSize = DEFAULT_WINDOW_SIZE) {
    const start = clampWindowStart(records.length, windowStart, windowSize); return records.slice(start, start + windowSize);
  }
  function collisionAwareIndices(positions, minimumGap, required = []) {
    if (!positions.length) return [];
    const requiredSet = new Set(required.filter((index) => index >= 0 && index < positions.length));
    const selected = [...requiredSet].sort((left, right) => positions[left] - positions[right]);
    for (let index = positions.length - 1; index >= 0; index -= 1) {
      if (!requiredSet.has(index) && selected.every((other) => Math.abs(positions[index] - positions[other]) >= minimumGap)) selected.push(index);
    }
    return selected.sort((left, right) => left - right);
  }
  function visibleRecords() { return recordsInWindow(model.records, model.windowStart, model.windowSize); }
  function formatMigrationPrice(value) { return model.priceFormatter?.format(Number(value)) || model.formatPrice?.(value) || String(value); }

  function renderDetail(record) {
    const target = byId("#migrationRecordDetail"); if (!target || !record) return;
    const latest = record === model.records.at(-1); const range = `${formatMigrationPrice(record.lower)} – ${formatMigrationPrice(record.upper)}`; const hasPrevious = Number.isFinite(Number(record.from_lower)) && Number.isFinite(Number(record.from_upper)); const previous = hasPrevious ? `${formatMigrationPrice(record.from_lower)} – ${formatMigrationPrice(record.from_upper)}` : "—";
    target.replaceChildren(); const heading = document.createElement("strong"); heading.textContent = `#${record.sequence}${latest ? " (Latest)" : ""}`;
    const pivot = structuralPivot(record);
    const rows = [["State", record.event_type === "MRZ_ACTIVATED" ? "Activation" : "Migration"], ["MRZ Range", range], ["Midpoint", formatMigrationPrice(record.midpoint)], ["Route", record.route || "—"], ["Observed At", model.exactTime(record.observed_at)], ["First Known", record.first_known_at ? model.exactTime(record.first_known_at) : "Unavailable"], ["Canonical Reference", record.canonical_evidence_ref || record.event_key || "Unavailable"]];
    if (pivot) rows.splice(2, 0, ["Structural Pivot", `${pivot.type} · ${pivot.maturity}`]);
    if (model.selectedDevelopment?.pivot_event_key === record.event_key) {
      const evidence = model.selectedDevelopment.supporting_event_keys || [];
      rows.splice(3, 0, ["Supporting Migrations", evidence.join(", ") || "Unavailable"]);
    }
    if (hasPrevious) rows.splice(2, 0, ["Previous MRZ", previous]);
    const list = document.createElement("dl"); rows.forEach(([label, value]) => { const dt = document.createElement("dt"); dt.textContent = label; const dd = document.createElement("dd"); dd.textContent = value; list.append(dt, dd); }); target.append(heading, list);
  }

  function structuralPivot(record) {
    const candidates = [...(model.intelligence?.pivots || [])];
    if (model.intelligence?.latest_development) candidates.push(model.intelligence.latest_development);
    if (model.selectedDevelopment) candidates.push(model.selectedDevelopment);
    return candidates.find((item) => item.pivot_event_key === record.event_key || Number(item.migration_sequence) === Number(record.sequence)) || null;
  }

  function renderWindowControls() {
    const records = visibleRecords(); const older = byId("#migrationOlderButton"); const newer = byId("#migrationNewerButton"); const summary = byId("#migrationWindowSummary");
    if (older) older.disabled = model.windowStart === 0;
    if (newer) newer.disabled = model.windowStart >= latestWindowStart(model.records.length, model.windowSize);
    if (summary) summary.textContent = records.length ? `States #${records[0].sequence}–#${records.at(-1).sequence} · ${records.length} of ${model.records.length}` : "No verified migration states";
  }

  function hitAt(x, y) { return model.hits.find((item) => x >= item.left && x <= item.right && y >= item.top && y <= item.bottom) || null; }

  function draw() {
    const records = visibleRecords();
    if (!model.generated || !records.length) return;
    const canvas = byId("#migrationPathCanvas"); const host = byId("#migrationChartScroll"); if (!canvas || !host) return;
    renderWindowControls();
    canvas.dataset.priceZoom = String(model.priceZoom);
    canvas.dataset.windowStart = String(model.windowStart);
    canvas.dataset.windowSize = String(model.windowSize);
    const panel = byId("#migrationPathPanel"); const expanded = panel?.classList.contains("chart-maximized") || globalObject.document.body?.dataset.chartOnly === "migration-path";
    const cssWidth = Math.max(host.clientWidth - 2, 320); const cssHeight = expanded ? Math.max(300, host.clientHeight - 2) : cssWidth < 680 ? 286 : 300; const ratio = Math.max(1, globalObject.devicePixelRatio || 1);
    canvas.width = Math.round(cssWidth * ratio); canvas.height = Math.round(cssHeight * ratio); canvas.style.width = `${cssWidth}px`; canvas.style.height = `${cssHeight}px`;
    const context = canvas.getContext("2d"); context.setTransform(ratio, 0, 0, ratio, 0, 0); context.clearRect(0, 0, cssWidth, cssHeight);
    context.font = "12px system-ui"; context.textBaseline = "middle";

    const priceScale = linearPriceScale(records, 5, .08 * (2 ** (-model.priceZoom))); const formattedTicks = priceScale.ticks.map((value) => formatMigrationPrice(value));
    const widestTick = Math.max(0, ...formattedTicks.map((label) => context.measureText(label).width));
    const pad = { left: Math.ceil(widestTick) + 18, right: 26, top: 38, bottom: 48 }; const width = cssWidth - pad.left - pad.right; const height = cssHeight - pad.top - pad.bottom;
    const firstTime = records[0].time; const lastTime = records.at(-1).time; const span = Math.max(1, lastTime - firstTime);
    const x = (item) => lastTime === firstTime ? pad.left + (width / 2) : pad.left + ((item.time - firstTime) / span) * width;
    const y = (price) => pad.top + (1 - ((price - priceScale.minimum) / (priceScale.maximum - priceScale.minimum))) * height;
    priceScale.ticks.forEach((value, index) => { const yy = y(value); if (yy < pad.top - 1 || yy > pad.top + height + 1) return; context.strokeStyle = "rgba(35,53,70,.72)"; context.lineWidth = 1; context.beginPath(); context.moveTo(pad.left, yy); context.lineTo(cssWidth - pad.right, yy); context.stroke(); context.fillStyle = "#a9b7c6"; context.textAlign = "right"; context.fillText(formattedTicks[index], pad.left - 10, yy); });
    const positions = records.map((item) => ({ item, cx: x(item), cy: y(item.midpoint) }));

    model.hits = [];
    positions.forEach((point, index) => {
      const next = positions[index + 1]; const validityKnown = next && next.item.chainId === point.item.chainId; const bandEnd = validityKnown ? next.cx : point.cx; const top = y(point.item.upper); const bottom = y(point.item.lower); const bandHeight = Math.max(.75, bottom - top);
      context.fillStyle = point.item === model.selected ? "rgba(123,104,238,.82)" : "rgba(105,91,207,.66)"; context.strokeStyle = point.item === model.selected ? "#a99cff" : "#7c70dc"; context.lineWidth = 1;
      if (validityKnown && bandEnd > point.cx) { context.fillRect(point.cx, top, bandEnd - point.cx, bandHeight); context.strokeRect(point.cx, top, bandEnd - point.cx, bandHeight); }
      else { context.beginPath(); context.moveTo(point.cx - 7, top); context.lineTo(point.cx + 7, top); context.stroke(); context.beginPath(); context.moveTo(point.cx - 7, bottom); context.lineTo(point.cx + 7, bottom); context.stroke(); }
      model.hits.push({ record: point.item, left: Math.min(point.cx - 10, bandEnd), right: Math.max(point.cx + 10, bandEnd), top: Math.min(top, bottom) - 18, bottom: Math.max(top, bottom) + 18 });
    });

    context.setLineDash([7, 5]); context.strokeStyle = "#31e6b0"; context.lineWidth = 2;
    positions.forEach((point, index) => { const previous = positions[index - 1]; if (!previous || previous.item.chainId !== point.item.chainId) return; context.beginPath(); context.moveTo(previous.cx, previous.cy); context.lineTo(point.cx, point.cy); context.stroke(); });
    context.setLineDash([]);
    positions.forEach((point) => { context.fillStyle = "#2be3aa"; context.beginPath(); context.arc(point.cx, point.cy, 6, 0, Math.PI * 2); context.fill(); if (point.item === model.selected) { context.strokeStyle = "#fff"; context.lineWidth = 2; context.beginPath(); context.arc(point.cx, point.cy, 9, 0, Math.PI * 2); context.stroke(); } });

    const xPositions = positions.map((point) => point.cx); const selectedIndex = positions.findIndex((point) => point.item === model.selected);
    collisionAwareIndices(xPositions, 42, [positions.length - 1, selectedIndex]).forEach((index) => {
      const point = positions[index]; const pivot = structuralPivot(point.item);
      context.fillStyle = point.item === model.selected || index === positions.length - 1 ? "#f4f8fb" : "#d3dde6"; context.textAlign = "center";
      context.fillText(pivot ? `${pivot.type}${pivot.maturity === "developing" ? "…" : ""} · #${point.item.sequence}` : `#${point.item.sequence}`, point.cx, Math.max(15, y(point.item.upper) - 13));
    });
    collisionAwareIndices(xPositions, 88, [0, positions.length - 1]).forEach((index) => { const point = positions[index]; context.fillStyle = "#9aacbc"; context.textAlign = index === 0 ? "left" : index === positions.length - 1 ? "right" : "center"; context.fillText(dateLabel(point.item.observed_at).replace(/ \d{4}$/, ""), point.cx, cssHeight - 19); });
    context.strokeStyle = "#6f8293"; context.beginPath(); context.moveTo(pad.left, pad.top + height); context.lineTo(cssWidth - pad.right, pad.top + height); context.stroke();
  }

  function selectRecord(record, { reveal = true } = {}) { if (!record) return; model.selected = record; renderDetail(record); const detail = byId("#migrationRecordDetail"); if (detail) detail.hidden = !reveal; draw(); }
  function shiftWindow(direction) {
    const previousStart = model.windowStart; const step = Math.max(1, model.windowSize - 1);
    model.windowStart = clampWindowStart(model.records.length, model.windowStart + (direction * step), model.windowSize);
    if (model.windowStart === previousStart) return;
    const records = visibleRecords(); selectRecord(direction < 0 ? records[0] : records.at(-1));
  }
  function zoom(direction) {
    if (!model.records.length) return;
    if (model.records.length <= 3) {
      const nextPriceZoom = Math.max(-3, Math.min(3, model.priceZoom + (direction < 0 ? 1 : -1)));
      if (nextPriceZoom === model.priceZoom) return;
      model.priceZoom = nextPriceZoom;
      draw();
      return;
    }
    const previousSize = model.windowSize;
    model.windowSize = Math.max(3, Math.min(model.records.length, previousSize + direction));
    if (model.windowSize === previousSize) return;
    model.windowStart = clampWindowStart(model.records.length, model.windowStart, model.windowSize);
    draw();
  }
  function resetView() {
    model.windowSize = Math.min(DEFAULT_WINDOW_SIZE, Math.max(1, model.records.length));
    model.windowStart = latestWindowStart(model.records.length, model.windowSize);
    model.priceZoom = 0;
    model.selected = model.records.at(-1) || null;
    if (model.selected) renderDetail(model.selected);
    const detail = byId("#migrationRecordDetail"); if (detail) detail.hidden = true;
    draw();
  }
  function toggleMaximize() {
    const panel = byId("#migrationPathPanel"); const button = byId("#migrationMaximize");
    const active = panel?.classList.toggle("chart-maximized");
    if (button) { button.textContent = active ? "↙" : "⛶"; button.title = active ? "Restore chart" : "Maximize chart"; button.setAttribute("aria-label", button.title); button.setAttribute("aria-pressed", String(Boolean(active))); }
    globalObject.setTimeout(draw, 0);
  }
  function show({ preserveViewport = false } = {}) { if (!model.migrationCount || !model.records.length) return; model.generated = true; if (!preserveViewport) model.windowStart = latestWindowStart(model.records.length, model.windowSize); model.selected ||= model.records.at(-1); byId("#migrationPathPanel").hidden = false; byId("#migrationGenerateButton").hidden = true; renderDetail(model.selected); const detail = byId("#migrationRecordDetail"); if (detail) detail.hidden = true; renderWindowControls(); draw(); byId("#migrationPathPanel").scrollIntoView?.({ behavior: "smooth", block: "nearest" }); }
  function hide() { if (!canHidePath(model.chartOnly)) return; model.generated = false; byId("#migrationPathPanel").hidden = true; if (model.records.length) byId("#migrationGenerateButton").hidden = false; }

  function setData({ symbol, migrations = [], states = [], developments = [], formatPrice, exactTime }) {
    const source = states.length ? states : migrations; const records = prepareMigrationRecords(source); const precision = migrationPricePrecision(records); const migrationCount = migrations.length;
    const params = new URLSearchParams(globalObject.location.search); const requestedSize = Number(params.get("migration_size")); const requestedStart = Number(params.get("migration_start"));
    const chartOnly = params.get("chart_only") === "1";
    const windowSize = Number.isFinite(requestedSize) && requestedSize > 0 ? Math.min(records.length || 1, Math.max(1, requestedSize)) : Math.min(DEFAULT_WINDOW_SIZE, Math.max(1, records.length));
    let windowStart = Number.isFinite(requestedStart) ? clampWindowStart(records.length, requestedStart, windowSize) : (Number.isFinite(requestedSize) && requestedSize > 0 ? latestWindowStart(records.length, windowSize) : latestWindowStart(records.length));
    const requestedDevelopmentId = params.get("development");
    const selectedDevelopment = developments.find((item) => String(item.id) === requestedDevelopmentId) || null;
    const requestedEvent = params.get("migration_event") || selectedDevelopment?.pivot_event_key;
    const selected = records.find((record) => record.event_key === requestedEvent) || records.at(-1) || null;
    const selectedIndex = records.findIndex((record) => record === selected);
    if (!Number.isFinite(requestedStart) && selectedIndex >= 0) windowStart = clampWindowStart(records.length, selectedIndex - Math.floor(windowSize / 2), windowSize);
    model = { ...model, symbol, records, developments, selectedDevelopment, migrationCount, generated: false, selected, hits: [], windowStart, windowSize, formatPrice, exactTime, priceFormatter: new Intl.NumberFormat("en-US", { minimumFractionDigits: precision, maximumFractionDigits: precision }), pointers: new Map(), pinchDistance: 0, suppressClick: false, chartOnly, priceZoom: 0 };
    const count = migrationCount; byId("#migrationCountBadge").textContent = countLabel(count); byId("#migrationEmptyState").hidden = count > 0; byId("#migrationGenerateButton").hidden = count === 0; byId("#migrationPathPanel").hidden = true; byId("#migrationLimitedNote").hidden = count === 0 || count > 3;
    const detail = byId("#migrationRecordDetail"); if (detail) detail.hidden = true;
    if (count) byId("#migrationPathSummary").textContent = `${countLabel(count)} · ${records.length} canonical states · ${dateLabel(records[0].observed_at)} – ${dateLabel(records.at(-1).observed_at)}`;
    byId("#migrationGenerateButton").onclick = show;
    const hideButton = byId("#migrationHideButton"); hideButton.hidden = !canHidePath(chartOnly); hideButton.onclick = hide;
    byId("#migrationOlderButton").onclick = () => shiftWindow(-1); byId("#migrationNewerButton").onclick = () => shiftWindow(1);
    byId("#migrationZoomIn").onclick = () => zoom(-1); byId("#migrationZoomOut").onclick = () => zoom(1); byId("#migrationResetView").onclick = resetView; byId("#migrationMaximize").onclick = toggleMaximize;
    const dock = byId("#migrationDock");
    globalObject.edgeDocking?.decorateDockButton?.(dock, chartOnly ? "Undock MRZ Migration Path" : "Dock MRZ Migration Path");
    dock.hidden = !chartOnly && !globalObject.edgeDocking?.canDock?.();
    dock.onclick = () => {
      const viewport = { windowStart: model.windowStart, windowSize: model.windowSize, selectedEventId: model.selected?.event_key };
      if (chartOnly) { const target = new URLSearchParams({ symbol, focus: "migration-path", migration_start: String(viewport.windowStart), migration_size: String(viewport.windowSize) }); if (viewport.selectedEventId) target.set("migration_event", viewport.selectedEventId); globalObject.edgeDocking?.openInMain?.(`/mrz/symbols?${target}`); return; }
      const opened = globalObject.edgeDocking?.openMigrationPath?.(symbol, { returnUrl: `${globalObject.location.pathname}${globalObject.location.search}`, ...viewport });
      if (!opened) globalObject.alert?.("The dock window was blocked. Allow pop-ups for EDGE and try again.");
    };
    const canvas = byId("#migrationPathCanvas"); canvas.onclick = (event) => { if (model.suppressClick) { model.suppressClick = false; return; } const rect = canvas.getBoundingClientRect(); const hit = hitAt(event.clientX - rect.left, event.clientY - rect.top); if (hit) selectRecord(hit.record); else dismissDetail(); };
    canvas.onwheel = (event) => { event.preventDefault(); if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) zoom(event.deltaY > 0 ? 1 : -1); else shiftWindow(event.deltaX > 0 ? 1 : -1); };
    canvas.onpointerdown = (event) => { model.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY }); model.pinchDistance = 0; model.suppressClick = false; canvas.setPointerCapture?.(event.pointerId); };
    canvas.onpointermove = (event) => { if (!model.pointers.has(event.pointerId)) return; const previous = model.pointers.get(event.pointerId); model.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY }); if (model.pointers.size > 1) { const points = [...model.pointers.values()]; const distance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y); if (model.pinchDistance && Math.abs(distance - model.pinchDistance) >= 24) { zoom(distance > model.pinchDistance ? -1 : 1); model.pinchDistance = distance; model.suppressClick = true; } else if (!model.pinchDistance) model.pinchDistance = distance; return; } const delta = event.clientX - previous.x; if (Math.abs(delta) < 28) return; shiftWindow(delta < 0 ? 1 : -1); model.suppressClick = true; };
    const releasePointer = (event) => { model.pointers.delete(event.pointerId); model.pinchDistance = 0; };
    canvas.onpointerup = releasePointer;
    canvas.onpointercancel = releasePointer;
    canvas.onmousemove = (event) => { const rect = canvas.getBoundingClientRect(); const hit = hitAt(event.clientX - rect.left, event.clientY - rect.top); canvas.title = hit ? `MRZ #${hit.record.sequence} · ${dateLabel(hit.record.observed_at)}` : ""; };
    canvas.onkeydown = (event) => { if (event.key === "Escape") { dismissDetail(); return; } if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return; event.preventDefault(); const recordsNow = visibleRecords(); const selectedIndex = recordsNow.findIndex((record) => record === model.selected); const nextIndex = event.key === "ArrowLeft" ? selectedIndex - 1 : selectedIndex + 1; if (nextIndex >= 0 && nextIndex < recordsNow.length) selectRecord(recordsNow[nextIndex]); else shiftWindow(event.key === "ArrowLeft" ? -1 : 1); };
    resizeObserver?.disconnect(); if (typeof globalObject.ResizeObserver === "function") { resizeObserver = new globalObject.ResizeObserver(draw); resizeObserver.observe(byId("#migrationChartScroll")); }
    renderWindowControls();
    if (params.get("focus") === "migration-path" && count) globalObject.requestAnimationFrame(() => show({ preserveViewport: true }));
    if (chartOnly) globalObject.edgeDocking?.trackDockedWindow?.("migration-path");
  }

  function setStructuralIntelligence(intelligence) {
    model.intelligence = intelligence || null;
    if (model.selected) renderDetail(model.selected);
    if (model.generated) draw();
  }

  const exported = { canHidePath, clampWindowStart, collisionAwareIndices, countLabel, dismissDetail, latestWindowStart, linearPriceScale, migrationPricePrecision, prepareMigrationRecords, recordsInWindow, setData, setStructuralIntelligence };
  globalObject.edgeMigrationPath = exported;
  if (typeof module === "object" && module.exports) module.exports = exported;
}(globalThis));
