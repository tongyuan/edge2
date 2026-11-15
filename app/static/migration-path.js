(function initializeMigrationPath(globalObject) {
  "use strict";
  let model = { symbol: "", records: [], generated: false, selected: null, hits: [] };
  let resizeObserver = null;

  function prepareMigrationRecords(rows = []) {
    return rows.map((row) => {
      const lower = Number(row.to_lower); const upper = Number(row.to_upper);
      const sequence = Number(row.sequence); const activation = row.activation_event_key || `unlinked:${row.event_key}`; const route = row.route || "UNKNOWN";
      const storedMidpoint = row.midpoint == null ? Number.NaN : Number(row.midpoint);
      return { ...row, lower, upper, midpoint: Number.isFinite(storedMidpoint) ? storedMidpoint : (lower + upper) / 2, sequence, time: new Date(row.observed_at).getTime(), chainId: activation, segmentId: `${activation}:${route}` };
    }).filter((row) => Number.isFinite(row.lower) && Number.isFinite(row.upper) && Number.isFinite(row.time) && Number.isFinite(row.sequence))
      .sort((a, b) => a.sequence - b.sequence || a.time - b.time || String(a.event_key).localeCompare(String(b.event_key)));
  }

  function dateLabel(value) { return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }).format(new Date(value)); }
  function countLabel(count) { return `${count} migration${count === 1 ? "" : "s"}`; }
  function byId(id) { return document.querySelector(id); }

  function renderDetail(record) {
    const target = byId("#migrationRecordDetail"); if (!target || !record) return;
    const latest = record === model.records.at(-1); const range = `${model.formatPrice(record.lower)} – ${model.formatPrice(record.upper)}`; const previous = `${model.formatPrice(record.from_lower)} – ${model.formatPrice(record.from_upper)}`;
    target.replaceChildren(); const heading = document.createElement("strong"); heading.textContent = `#${record.sequence}${latest ? " (Latest)" : ""}`;
    const rows = [["MRZ Range", range], ["Midpoint", model.formatPrice(record.midpoint)], ["Observed At", model.exactTime(record.observed_at)]];
    if (model.records.length === 1) rows.splice(1, 0, ["Previous MRZ", previous]);
    const list = document.createElement("dl"); rows.forEach(([label, value]) => { const dt = document.createElement("dt"); dt.textContent = label; const dd = document.createElement("dd"); dd.textContent = value; list.append(dt, dd); }); target.append(heading, list);
  }

  function draw() {
    if (!model.generated || !model.records.length) return;
    const canvas = byId("#migrationPathCanvas"); const host = byId("#migrationChartScroll"); if (!canvas || !host) return;
    const cssWidth = Math.max(host.clientWidth - 2, model.records.length * 105, 680); const cssHeight = 310; const ratio = Math.max(1, globalObject.devicePixelRatio || 1);
    canvas.width = Math.round(cssWidth * ratio); canvas.height = Math.round(cssHeight * ratio); canvas.style.width = `${cssWidth}px`; canvas.style.height = `${cssHeight}px`;
    const context = canvas.getContext("2d"); context.setTransform(ratio, 0, 0, ratio, 0, 0); context.clearRect(0, 0, cssWidth, cssHeight);
    const pad = { left: 70, right: 24, top: 30, bottom: 42 }; const width = cssWidth - pad.left - pad.right; const height = cssHeight - pad.top - pad.bottom;
    const values = model.records.flatMap((item) => [item.lower, item.upper]); let minimum = Math.min(...values); let maximum = Math.max(...values); const pricePad = Math.max((maximum - minimum) * .08, Math.abs(maximum || 1) * .002); minimum -= pricePad; maximum += pricePad;
    const firstTime = model.records[0].time; const lastTime = model.records.at(-1).time; const span = Math.max(1, lastTime - firstTime);
    const x = (item, index) => lastTime === firstTime ? pad.left + (width * (index + 1) / (model.records.length + 1)) : pad.left + ((item.time - firstTime) / span) * width;
    const y = (price) => pad.top + (1 - ((price - minimum) / (maximum - minimum))) * height;
    context.font = "12px system-ui"; context.textBaseline = "middle";
    for (let index = 0; index <= 5; index += 1) { const yy = pad.top + (height * index / 5); const value = maximum - ((maximum - minimum) * index / 5); context.strokeStyle = "#233546"; context.lineWidth = 1; context.beginPath(); context.moveTo(pad.left, yy); context.lineTo(cssWidth - pad.right, yy); context.stroke(); context.fillStyle = "#a9b7c6"; context.textAlign = "right"; context.fillText(model.formatPrice(value), pad.left - 10, yy); }
    const positions = model.records.map((item, index) => ({ item, cx: x(item, index), cy: y(item.midpoint) }));
    context.setLineDash([7, 5]); context.strokeStyle = "#31e6b0"; context.lineWidth = 2; positions.forEach((point, index) => { const previous = positions[index - 1]; if (!previous || previous.item.segmentId !== point.item.segmentId) return; context.beginPath(); context.moveTo(previous.cx, previous.cy); context.lineTo(point.cx, point.cy); context.stroke(); }); context.setLineDash([]);
    model.hits = [];
    positions.forEach((point, index) => { const next = positions[index + 1]; const same = next && next.item.segmentId === point.item.segmentId; const bandEnd = same ? Math.max(point.cx + 24, next.cx - 8) : point.cx + 34; const top = y(point.item.upper); const bottom = y(point.item.lower); context.fillStyle = point.item === model.selected ? "rgba(123,104,238,.8)" : "rgba(105,91,207,.62)"; context.fillRect(Math.max(pad.left, point.cx - 8), top, Math.max(22, bandEnd - point.cx + 8), Math.max(4, bottom - top)); context.fillStyle = "#2be3aa"; context.beginPath(); context.arc(point.cx, point.cy, 6, 0, Math.PI * 2); context.fill(); context.fillStyle = "#e8eef4"; context.textAlign = "center"; context.fillText(`#${point.item.sequence}`, point.cx, Math.max(13, top - 12)); context.fillStyle = "#9aacbc"; context.fillText(dateLabel(point.item.observed_at).replace(/ \d{4}$/, ""), point.cx, cssHeight - 18); model.hits.push({ record: point.item, left: point.cx - 14, right: bandEnd, top: top - 18, bottom: bottom + 18 }); });
    context.strokeStyle = "#6f8293"; context.beginPath(); context.moveTo(pad.left, pad.top + height); context.lineTo(cssWidth - pad.right, pad.top + height); context.stroke();
  }

  function show() { if (!model.records.length) return; model.generated = true; model.selected = model.records.at(-1); byId("#migrationPathPanel").hidden = false; byId("#migrationGenerateButton").hidden = true; renderDetail(model.selected); draw(); byId("#migrationPathPanel").scrollIntoView?.({ behavior: "smooth", block: "nearest" }); }
  function hide() { model.generated = false; byId("#migrationPathPanel").hidden = true; if (model.records.length) byId("#migrationGenerateButton").hidden = false; }

  function setData({ symbol, migrations, formatPrice, exactTime }) {
    const records = prepareMigrationRecords(migrations); model = { symbol, records, generated: false, selected: records.at(-1) || null, hits: [], formatPrice, exactTime };
    const count = records.length; byId("#migrationCountBadge").textContent = countLabel(count); byId("#migrationEmptyState").hidden = count > 0; byId("#migrationGenerateButton").hidden = count === 0; byId("#migrationPathPanel").hidden = true; byId("#migrationLimitedNote").hidden = count !== 1;
    if (count) byId("#migrationPathSummary").textContent = `${countLabel(count)} · ${dateLabel(records[0].observed_at)} – ${dateLabel(records.at(-1).observed_at)}`;
    byId("#migrationGenerateButton").onclick = show; byId("#migrationHideButton").onclick = hide;
    const canvas = byId("#migrationPathCanvas"); canvas.onclick = (event) => { const rect = canvas.getBoundingClientRect(); const px = event.clientX - rect.left; const py = event.clientY - rect.top; const hit = model.hits.find((item) => px >= item.left && px <= item.right && py >= item.top && py <= item.bottom); if (hit) { model.selected = hit.record; renderDetail(hit.record); draw(); } };
    resizeObserver?.disconnect(); if (typeof globalObject.ResizeObserver === "function") { resizeObserver = new globalObject.ResizeObserver(draw); resizeObserver.observe(byId("#migrationChartScroll")); }
  }

  const exported = { countLabel, prepareMigrationRecords, setData };
  globalObject.edgeMigrationPath = exported;
  if (typeof module === "object" && module.exports) module.exports = exported;
}(globalThis));
