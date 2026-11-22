(function initializeOpportunityMap(globalObject) {
  "use strict";

  const STAGE_ORDER = {
    STRUCTURE_ESTABLISHED: 5,
    NEAR_MISS: 4,
    DEVELOPING: 3,
    CONTEXT_OBSERVED: 2,
    HISTORICAL_UNRESOLVED: 1,
  };
  const COLORS = {
    grid: "#223242",
    text: "#91a1b3",
    btd: "#3B82F6",
    str: "#A78BFA",
    mrz: "#14B8A6",
    near: "#C084FC",
  };
  const chartViewport = globalObject.edgeChartViewport;

  function node(tag, className, content) {
    const element = globalObject.document.createElement(tag);
    if (className) element.className = className;
    if (content !== undefined) element.textContent = content;
    return element;
  }

  function parseTime(value) {
    return value ? new Date(value).getTime() : Number.NaN;
  }

  function exactTime(value) {
    if (!value) return "Unavailable";
    return globalObject.formatOperatorTimestampUtcMinus4?.(value)
      || new Date(value).toLocaleString();
  }

  function renderCanonicalEvidenceLink(detail, options = {}) {
    const params = new URLSearchParams({
      symbol: detail.symbol,
      from: "watchlists",
      as_known_at: detail.as_known_at,
    });
    if (options.groupId !== undefined && options.groupId !== null) params.set("group", String(options.groupId));
    if (options.window) params.set("window", String(options.window));
    if (options.returnUrl) params.set("return", String(options.returnUrl));
    const link = node("a", "opportunity-canonical-link");
    link.href = `/mrz/symbols?${params}`;
    link.setAttribute("aria-label", "Open Canonical Evidence");
    link.title = "Open Canonical Evidence";
    const icon = node("span", "opportunity-evidence-icon", "◎");
    icon.setAttribute("aria-hidden", "true");
    link.append(icon, node("span", "", options.label || "Evidence"));
    return link;
  }

  function shortTime(value) {
    if (!value) return "—";
    return new Date(value).toLocaleDateString(undefined, {
      day: "numeric", month: "short", year: "2-digit",
    });
  }

  function price(value) {
    if (value === null || value === undefined || value === "") return "—";
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return String(value);
    return numeric.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 6,
    });
  }

  function axisPrice(value, symbol, span) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return String(value);
    const upperSymbol = String(symbol || "").toUpperCase();
    const isCrypto = upperSymbol.endsWith("USDT") || upperSymbol.endsWith("USDC");
    let digits = 2;
    if (isCrypto && Math.abs(numeric) < 1) digits = Math.abs(numeric) < 0.01 ? 6 : 4;
    else if (isCrypto && Math.abs(numeric) < 100) digits = 4;
    else if (Number(span) > 0 && Number(span) < 0.01) digits = 4;
    return numeric.toLocaleString(undefined, {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  }

  function rangeText(item) {
    if (!item?.lower_bound || !item?.upper_bound) return "—";
    return `${price(item.lower_bound)}–${price(item.upper_bound)}`;
  }

  function stageClass(value) {
    return String(value || "context").toLowerCase().replaceAll("_", "-");
  }

  function eventIdentity(item) {
    return item?.canonical_event_id
      || item?.event_id
      || item?.mrz_lifecycle_event_id
      || [item?.source_tracker, item?.event_type, item?.effective_at, item?.known_at].join(":");
  }

  function collectReplayCursors(detail) {
    const values = new Set([detail.as_of]);
    [
      ...(detail.observations || []),
      ...(detail.near_miss_events || []),
      ...(detail.mrz_lifecycles || []),
    ].forEach((item) => { if (item.known_at) values.add(item.known_at); });
    return [...values].sort((left, right) => parseTime(left) - parseTime(right));
  }

  function cursorIndexAtOrBefore(cursors, target) {
    const exact = cursors.indexOf(target);
    if (exact >= 0) return exact;
    const targetTime = parseTime(target);
    return cursors.reduce(
      (current, cursor, index) => (parseTime(cursor) <= targetTime ? index : current),
      0,
    );
  }

  function proportionalPosition(value, minimum, maximum) {
    if (!(maximum > minimum)) return 0.5;
    return Math.max(0, Math.min(1, (Number(value) - minimum) / (maximum - minimum)));
  }

  function timeBounds(detail, rangeDays) {
    const times = [];
    (detail.observations || []).forEach((item) => times.push(parseTime(item.effective_at)));
    (detail.near_miss_events || []).forEach((item) => times.push(parseTime(item.effective_at || item.known_at)));
    (detail.mrz_lifecycles || []).forEach((item) => times.push(parseTime(item.known_at)));
    const finite = times.filter(Number.isFinite);
    const replayCutoff = parseTime(detail.as_known_at || detail.as_of);
    const latest = Number.isFinite(replayCutoff) ? replayCutoff : finite.length ? Math.max(...finite) : Date.now();
    const eligible = finite.filter((value) => value <= latest);
    const earliest = eligible.length ? Math.min(...eligible) : latest - 86400000;
    if (!rangeDays) return { minimum: earliest, maximum: latest };
    return { minimum: latest - rangeDays * 86400000, maximum: latest };
  }

  function chartViewportBounds(detail, componentState) {
    if (!componentState.viewport) componentState.viewport = createOpportunityViewport(detail, componentState.rangeDays);
    return { minimum: componentState.viewport.minimum, maximum: componentState.viewport.maximum };
  }

  function createOpportunityViewport(detail, rangeDays, restored = null) {
    const full = timeBounds(detail, 0);
    const base = chartViewport.createTimeViewport({
      earliest: full.minimum,
      cutoff: full.maximum,
      rangeDays,
    });
    return restored
      ? chartViewport.restoreTimeViewport(base, restored.minimum, restored.maximum)
      : base;
  }

  function comparisonTimeBounds(details, rangeDays) {
    const all = (details || []).flatMap((detail) => {
      const values = [];
      (detail.observations || []).forEach((item) => values.push(parseTime(item.effective_at)));
      (detail.near_miss_events || []).forEach((item) => values.push(parseTime(item.effective_at || item.known_at)));
      (detail.mrz_lifecycles || []).forEach((item) => values.push(parseTime(item.known_at), parseTime(item.ended_known_at)));
      values.push(parseTime(detail.as_known_at || detail.as_of));
      return values.filter(Number.isFinite);
    });
    const maximum = all.length ? Math.max(...all) : Date.now();
    const minimum = all.length ? Math.min(...all) : maximum - 86400000;
    return rangeDays
      ? { minimum: Math.max(minimum, maximum - rangeDays * 86400000), maximum }
      : { minimum, maximum };
  }

  function visibleChartItems(detail, bounds) {
    const within = (value) => {
      const time = parseTime(value);
      return Number.isFinite(time) && time >= bounds.minimum && time <= bounds.maximum;
    };
    return {
      observations: (detail.observations || []).filter((item) => within(item.effective_at)),
      near: (detail.near_miss_events || []).filter((item) => within(item.effective_at || item.known_at)),
      mrz: (detail.mrz_lifecycles || []).filter((item) => {
        const start = parseTime(item.known_at);
        const end = parseTime(item.ended_known_at || detail.as_known_at);
        return start <= bounds.maximum && end >= bounds.minimum;
      }),
    };
  }

  function priceBounds(items) {
    const values = [];
    const add = (value) => {
      const numeric = Number(value);
      if (Number.isFinite(numeric)) values.push(numeric);
    };
    items.observations.forEach((item) => add(item.price));
    items.near.forEach((item) => { add(item.lower_bound); add(item.upper_bound); });
    items.mrz.forEach((item) => {
      add(item.lower_bound); add(item.upper_bound);
      add(item.lower_migration_boundary); add(item.upper_migration_boundary);
    });
    if (!values.length) return { minimum: 0, maximum: 1 };
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const padding = Math.max((maximum - minimum) * 0.08, Math.abs(maximum) * 0.01, 0.01);
    return { minimum: minimum - padding, maximum: maximum + padding };
  }

  function drawTriangle(context, xPosition, yPosition, direction, size, fill, stroke = "#0b1119", strokeWidth = 2) {
    const upward = direction === "HIGHER";
    context.beginPath();
    context.moveTo(xPosition, yPosition + (upward ? -size : size));
    context.lineTo(xPosition - size, yPosition + (upward ? size : -size));
    context.lineTo(xPosition + size, yPosition + (upward ? size : -size));
    context.closePath();
    context.fillStyle = fill;
    context.fill();
    context.strokeStyle = stroke;
    context.lineWidth = strokeWidth;
    context.stroke();
  }

  function nearMissDisplayGeometry(anchorX, plotLeft, plotRight, canvasScale = 1, extensionCssPixels = 48) {
    const start = Math.max(plotLeft, Math.min(plotRight, Number(anchorX)));
    const cssPixels = Math.max(40, Math.min(60, Number(extensionCssPixels) || 48));
    const end = Math.min(plotRight, start + cssPixels * Math.max(Number(canvasScale) || 1, 0.01));
    return { start, end, width: Math.max(0, end - start), cssPixels };
  }

  function drawChart(canvas, detail, rangeDays, selectedEventId, onSelect, options = {}) {
    const context = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    const margin = { left: 68, right: 26, top: 30, bottom: 48 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const times = options.timeBounds || timeBounds(detail, rangeDays);
    const items = visibleChartItems(detail, times);
    const prices = priceBounds(items);
    const x = (value) => margin.left + proportionalPosition(parseTime(value), times.minimum, times.maximum) * plotWidth;
    const y = (value) => margin.top + (1 - proportionalPosition(Number(value), prices.minimum, prices.maximum)) * plotHeight;
    context.clearRect(0, 0, width, height);
    context.fillStyle = "#0b1119";
    context.fillRect(0, 0, width, height);
    context.font = "12px Inter, system-ui, sans-serif";
    context.lineWidth = 1;
    for (let index = 0; index <= 5; index += 1) {
      const ratio = index / 5;
      const yPosition = margin.top + ratio * plotHeight;
      const priceValue = prices.maximum - ratio * (prices.maximum - prices.minimum);
      context.strokeStyle = COLORS.grid;
      context.beginPath(); context.moveTo(margin.left, yPosition); context.lineTo(width - margin.right, yPosition); context.stroke();
      context.fillStyle = COLORS.text;
      context.textAlign = "right";
      context.fillText(axisPrice(priceValue, detail.symbol, prices.maximum - prices.minimum), margin.left - 10, yPosition + 4);
    }
    const timeTickCount = width < 520 ? 3 : width < 800 ? 4 : 6;
    for (let index = 0; index <= timeTickCount; index += 1) {
      const ratio = index / timeTickCount;
      const xPosition = margin.left + ratio * plotWidth;
      const time = new Date(times.minimum + ratio * (times.maximum - times.minimum));
      context.strokeStyle = "rgba(34,50,66,.48)";
      context.beginPath(); context.moveTo(xPosition, margin.top); context.lineTo(xPosition, height - margin.bottom); context.stroke();
      context.fillStyle = COLORS.text;
      context.textAlign = index === 0 ? "left" : index === timeTickCount ? "right" : "center";
      context.fillText(time.toLocaleDateString(undefined, { month: "short", day: "numeric" }), xPosition, height - 20);
    }
    context.textAlign = "left";
    context.fillStyle = "#c5d1dd";
    context.fillText("Price", 12, 18);
    context.textAlign = "right";
    context.fillText("Actual event time →", width - margin.right, height - 5);

    if (options.timeCursor && Number.isFinite(parseTime(options.timeCursor))) {
      const cursorX = x(options.timeCursor);
      context.save();
      context.setLineDash([4, 4]);
      context.strokeStyle = "rgba(226,232,240,.7)";
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(cursorX, margin.top);
      context.lineTo(cursorX, height - margin.bottom);
      context.stroke();
      context.restore();
    }

    const zoneHits = [];
    const selectedNearZones = [];
    const canvasScale = width / Math.max(1, canvas.getBoundingClientRect().width || width);
    items.near.forEach((item) => {
      const geometry = nearMissDisplayGeometry(
        x(item.effective_at || item.known_at),
        margin.left,
        width - margin.right,
        canvasScale,
      );
      const start = geometry.start;
      const end = geometry.end;
      const top = y(item.upper_bound);
      const bottom = y(item.lower_bound);
      const selected = eventIdentity(item) === selectedEventId;
      context.save();
      context.strokeStyle = selected ? "rgba(192,132,252,.72)" : COLORS.near;
      context.lineWidth = selected ? 2 : 1.5;
      context.setLineDash([6, 4]);
      context.strokeRect(start, top, Math.max(2, geometry.width), Math.max(2, bottom - top));
      context.restore();
      const hit = { left: start, right: Math.max(start + 14 * canvasScale, end), top: Math.min(top, bottom) - 5 * canvasScale, bottom: Math.max(top + 10 * canvasScale, bottom + 5 * canvasScale), item, kind: "near" };
      zoneHits.push(hit);
      if (selected) selectedNearZones.push({ start, end, top, bottom, item });
    });
    items.mrz.forEach((item) => {
      const start = Math.max(margin.left, x(item.known_at));
      const end = Math.min(width - margin.right, x(item.ended_known_at || detail.as_known_at));
      const top = y(item.upper_bound);
      const bottom = y(item.lower_bound);
      context.fillStyle = "rgba(20,184,166,.16)";
      context.fillRect(start, top, Math.max(2, end - start), Math.max(3, bottom - top));
      context.strokeStyle = eventIdentity(item) === selectedEventId ? "#d8fff4" : COLORS.mrz;
      context.lineWidth = eventIdentity(item) === selectedEventId ? 3 : 1;
      context.strokeRect(start, top, Math.max(2, end - start), Math.max(3, bottom - top));
      context.save();
      context.setLineDash([5, 4]);
      context.strokeStyle = "rgba(20,184,166,.48)";
      [item.lower_migration_boundary, item.upper_migration_boundary].forEach((boundary) => {
        context.beginPath(); context.moveTo(start, y(boundary)); context.lineTo(end, y(boundary)); context.stroke();
      });
      context.restore();
      zoneHits.push({ left: start, right: Math.max(start + 8, end), top: Math.min(top, bottom), bottom: Math.max(top + 8, bottom), item, kind: "mrz" });
    });

    const pointHits = [];
    items.observations.forEach((item) => {
      const xPosition = x(item.effective_at);
      const yPosition = y(item.price);
      const identity = eventIdentity(item);
      const routeColor = item.route === "BTD" ? COLORS.btd : COLORS.str;
      context.beginPath(); context.arc(xPosition, yPosition, 5, 0, Math.PI * 2);
      context.fillStyle = routeColor;
      context.fill();
      context.strokeStyle = "#0b1119";
      context.lineWidth = 1.5;
      context.stroke();
      if (eventIdentity(item) === selectedEventId) {
        context.beginPath(); context.arc(xPosition, yPosition, 10, 0, Math.PI * 2);
        context.strokeStyle = "#ffffff"; context.lineWidth = 2; context.stroke();
      }
      pointHits.push({ x: xPosition, y: yPosition, radius: 12, item });
    });
    selectedNearZones.forEach(({ start, end, top, bottom }) => {
      context.save();
      context.setLineDash([7, 3]);
      context.strokeStyle = "#f3e6ff";
      context.lineWidth = 3;
      context.strokeRect(start, top, Math.max(2, end - start), Math.max(2, bottom - top));
      context.restore();
    });
    canvas._opportunityHits = [...pointHits, ...zoneHits];
    canvas.onclick = (event) => {
      if (canvas._suppressOpportunityClick) { canvas._suppressOpportunityClick = false; return; }
      const box = canvas.getBoundingClientRect();
      const clickX = (event.clientX - box.left) * (canvas.width / box.width);
      const clickY = (event.clientY - box.top) * (canvas.height / box.height);
      const selectedPoint = pointHits
        .map((hit) => ({ hit, distance: Math.hypot(hit.x - clickX, hit.y - clickY) }))
        .filter((candidate) => candidate.distance <= candidate.hit.radius)
        .sort((left, right) => left.distance - right.distance)[0];
      if (selectedPoint) { onSelect(selectedPoint.hit.item); return; }
      const matchingZones = zoneHits.filter((hit) => (
        clickX >= hit.left && clickX <= hit.right && clickY >= hit.top && clickY <= hit.bottom
      ));
      if (matchingZones.length) {
        const nearZones = matchingZones.filter((hit) => hit.kind === "near");
        const candidates = nearZones.length ? nearZones : matchingZones;
        const selectedIndex = candidates.findIndex((hit) => eventIdentity(hit.item) === selectedEventId);
        const nextIndex = candidates.length > 1 ? (selectedIndex + 1 + candidates.length) % candidates.length : 0;
        onSelect(candidates[nextIndex].item);
      }
    };
  }

  function renderLegend(options = {}) {
    const legend = node("div", "opportunity-map-legend");
    [
      ["btd", "BTD observation"], ["str", "STR observation"],
      ["mrz", "MRZ zone"], ["near", "Near Miss candidate"],
    ].forEach(([tone, label]) => {
      const item = node("span", tone);
      item.append(node("i", ""), node("b", "", label));
      legend.append(item);
    });
    return legend;
  }

  function renderEventDetails(target, item, options = {}) {
    target.replaceChildren();
    if (!item) {
      target.append(node("p", "", "Select a chart marker to inspect its canonical evidence."));
      return;
    }
    const heading = node("div", "opportunity-selected-event-heading");
    heading.append(
      node("strong", "", `${item.symbol ? `${item.symbol} · ` : ""}${item.source_tracker} · ${item.event_type}`),
      node("span", "", item.canonical_event_id),
    );
    if (options.onClose) {
      const close = node("button", "quiet-button", "Close");
      close.type = "button";
      close.addEventListener("click", options.onClose);
      heading.append(close);
    }
    const grid = node("dl", "opportunity-selected-event-grid");
    [
      ["Event time", exactTime(item.effective_at)],
      ["First known", exactTime(item.known_at)],
      ["Price", price(item.price)],
      ["Bounds", rangeText(item)],
      ["Route", item.route || item.mrz_route || "—"],
      ["IPDA location", item.ipda_location_label || item.structural_location || "—"],
      ["MRZ lifecycle", item.mrz_lifecycle_event_id || "—"],
      ["Chart marker", item._classifications?.join(" + ") || item.route || item.direction || item.source_tracker || "Canonical evidence"],
      ["Relationship", item.relationship || "Canonical chart evidence"],
    ].forEach(([term, value]) => {
      grid.append(node("dt", "", term), node("dd", "", value));
    });
    target.append(heading, grid);
  }

  function timelineRows(detail) {
    const records = new Map();
    const structural = detail.structural_intelligence || {};
    const structuralRows = [...(structural.pivots || [])];
    if (structural.latest_development && !structuralRows.some((item) => item.development_id === structural.latest_development.development_id)) structuralRows.push(structural.latest_development);
    const sources = [
      [detail.observations || [], "Route observation"],
      [detail.near_miss_events || [], "Near Miss"],
      [detail.mrz_lifecycles || [], "MRZ"],
      [structuralRows.map((item) => ({
        ...item,
        canonical_event_id: item.development_id,
        event_type: `STRUCTURAL_${item.type}_${String(item.maturity || "").toUpperCase()}`,
        effective_at: item.event_time,
        known_at: item.confirmation_time || item.first_known_time,
        source_tracker: "structural_intelligence",
        relationship: `${item.type} · ${item.maturity} · detector ${item.detector_version}`,
        lower_bound: item.lower,
        upper_bound: item.upper,
      })), "Structural Development"],
    ];
    sources.forEach(([items, classification]) => items.forEach((item) => {
      const identity = eventIdentity(item);
      const existing = records.get(identity);
      if (!existing) {
        records.set(identity, {
          ...item,
          _classifications: [classification === "Route observation" ? (item.route || classification) : classification],
          _trackers: [item.source_tracker].filter(Boolean),
        });
        return;
      }
      Object.entries(item).forEach(([key, value]) => {
        if ((existing[key] === null || existing[key] === undefined || existing[key] === "") && value !== null && value !== undefined) existing[key] = value;
      });
      const visualClassification = classification === "Route observation" ? (item.route || classification) : classification;
      if (!existing._classifications.includes(visualClassification)) existing._classifications.push(visualClassification);
      if (item.source_tracker && !existing._trackers.includes(item.source_tracker)) existing._trackers.push(item.source_tracker);
    }));
    return [...records.values()].sort((left, right) => parseTime(right.effective_at) - parseTime(left.effective_at) || parseTime(right.known_at) - parseTime(left.known_at) || eventIdentity(left).localeCompare(eventIdentity(right)));
  }

  function timelineRowsForMode(detail, mode = "all") {
    const rows = timelineRows(detail);
    if (mode !== "key") return rows;
    return rows.filter((item) => item._classifications?.some((value) => ["Near Miss", "MRZ", "Structural Development"].includes(value)));
  }

  function timelineBody(rows, onSelect) {
    const body = node("tbody", "");
    rows.forEach((item) => {
      const row = node("tr", "");
      row.tabIndex = 0;
      row.dataset.eventId = eventIdentity(item);
      const evidence = item.relationship
        || item.ipda_location_label
        || item.structural_location
        || "Canonical observed evidence";
      const observedKnown = node("td", "opportunity-event-time");
      observedKnown.append(node("time", "", exactTime(item.effective_at)), node("small", "", `Known ${exactTime(item.known_at)}`));
      row.append(
        observedKnown,
        node("td", "", item._trackers?.join(" + ") || item.source_tracker),
        node("td", "", item.event_type),
        node("td", "", item.price ? price(item.price) : rangeText(item)),
        node("td", "", evidence),
      );
      row.setAttribute("aria-label", `${item.event_type}; observed ${exactTime(item.effective_at)}; known ${exactTime(item.known_at)}`);
      row.addEventListener("click", () => onSelect(item));
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(item); }
      });
      body.append(row);
    });
    if (!rows.length) {
      const row = node("tr", ""); const cell = node("td", "opportunity-empty", "No evidence is known at this replay cursor."); cell.colSpan = 5; row.append(cell); body.append(row);
    }
    return body;
  }

  function renderTimeline(detail, onSelect, expanded = false, mode = "all") {
    const wrap = node("div", "opportunity-timeline-wrap");
    wrap.classList.toggle("expanded", expanded);
    const table = node("table", "opportunity-timeline-table");
    const head = node("thead", "");
    head.innerHTML = "<tr><th>Observed / known</th><th>Tracker</th><th>Event</th><th>Price / structural zone</th><th>Evidence details</th></tr>";
    const rows = timelineRowsForMode(detail, mode);
    const visibleRows = expanded ? rows : rows.slice(0, 8);
    table.append(head, timelineBody(visibleRows, onSelect)); wrap.append(table); return wrap;
  }

  function renderMapComponent(target, detail, componentState, options = {}) {
    const mapPanel = node("section", `opportunity-map-panel panel${options.docked ? " docked-opportunity-map-panel" : ""}`);
    mapPanel.classList.toggle("maximized", Boolean(componentState.maximized));
    globalObject.document.body.classList.toggle("opportunity-map-maximized", Boolean(componentState.maximized));
    const mapHeader = node("header", "opportunity-panel-heading");
    const title = node("div", "");
    title.append(
      node("strong", "", "Opportunity Map (Time × Price)"),
      node("small", "", options.docked ? `${detail.symbol} · Actual event time · linear instrument price` : "Actual event time · linear instrument price"),
    );
    const mapTools = node("div", "opportunity-map-tools");
    const ranges = node("div", "opportunity-range-controls");
    let redraw = () => {};
    const rangeButtons = new Map();
    [[0, "All"], [90, "90D"], [30, "30D"]].forEach(([days, label]) => {
      const button = node("button", "", label); button.type = "button"; button.setAttribute("aria-pressed", String(componentState.rangeDays === days));
      button.addEventListener("click", () => {
        componentState.rangeDays = days;
        componentState.viewport = createOpportunityViewport(detail, days);
        rangeButtons.forEach((item, value) => item.setAttribute("aria-pressed", String(value === days)));
        options.onRangeChange?.(days);
        redraw();
      });
      rangeButtons.set(days, button);
      ranges.append(button);
    });
    mapTools.append(ranges);
    const zoomOut = node("button", "quiet-button chart-tool", "Zoom −"); zoomOut.type = "button"; zoomOut.title = "Zoom out";
    const zoomIn = node("button", "quiet-button chart-tool", "Zoom +"); zoomIn.type = "button"; zoomIn.title = "Zoom in";
    const reset = node("button", "quiet-button chart-tool", "Reset"); reset.type = "button"; reset.title = "Reset chart view";
    const maximize = node("button", "quiet-button chart-tool", "Maximize"); maximize.type = "button"; maximize.title = "Maximize chart"; maximize.setAttribute("aria-pressed", "false");
    zoomOut.addEventListener("click", () => { componentState.viewport = chartViewport.zoomTimeViewport(componentState.viewport, 1 / 1.35); redraw(); });
    zoomIn.addEventListener("click", () => { componentState.viewport = chartViewport.zoomTimeViewport(componentState.viewport, 1.35); redraw(); });
    reset.addEventListener("click", () => { componentState.viewport = createOpportunityViewport(detail, componentState.rangeDays); redraw(); });
    maximize.textContent = componentState.maximized ? "Restore" : "Maximize"; maximize.setAttribute("aria-pressed", String(Boolean(componentState.maximized)));
    maximize.addEventListener("click", () => {
      componentState.maximized = !componentState.maximized;
      const active = componentState.maximized; mapPanel.classList.toggle("maximized", active); document.body.classList.toggle("opportunity-map-maximized", active);
      maximize.textContent = active ? "Restore" : "Maximize"; maximize.title = active ? "Restore chart" : "Maximize chart"; maximize.setAttribute("aria-pressed", String(active));
      globalObject.requestAnimationFrame(redraw);
    });
    mapTools.append(zoomOut, zoomIn, reset, maximize);
    if (options.docked) {
      const evidence = renderCanonicalEvidenceLink(detail, { ...options, label: "Open Canonical Evidence" });
      evidence.addEventListener("click", (event) => {
        if (!globalObject.edgeDocking?.openInMain) return;
        event.preventDefault();
        globalObject.edgeDocking.openInMain(evidence.getAttribute("href"));
      });
      mapTools.append(evidence);
      if (globalObject.edgeDocking?.createDockButton) {
        const undock = globalObject.edgeDocking.createDockButton("Undock Opportunity Map");
        undock.addEventListener("click", () => {
          globalObject.edgeDocking.openInMain(options.returnUrl || "/mrz/watchlists");
          globalObject.close?.();
        });
        mapTools.append(undock);
      }
    } else if (globalObject.edgeDocking?.canDock()) {
      const dock = globalObject.edgeDocking.createDockButton("Dock Opportunity Map");
      dock.addEventListener("click", () => {
        const opened = globalObject.edgeDocking.openOpportunityMap(detail.symbol, {
          rangeDays: componentState.rangeDays,
          viewStart: componentState.viewport?.minimum,
          viewEnd: componentState.viewport?.maximum,
          selectedEventId: componentState.selectedEventId,
          returnUrl: `${globalObject.location.pathname}${globalObject.location.search}${globalObject.location.hash}`,
        });
        if (!opened) globalObject.alert?.("The dock window was blocked. Allow pop-ups for EDGE and try again.");
      });
      mapTools.append(dock);
    }
    mapHeader.append(title, mapTools); mapPanel.append(mapHeader);
    const scroll = node("div", "opportunity-chart-scroll");
    const canvas = node("canvas", "opportunity-map-canvas"); canvas.width = 1120; canvas.height = 280; canvas.setAttribute("aria-label", `Time-price opportunity map for ${detail.symbol}`); canvas.tabIndex = 0;
    scroll.append(canvas); mapPanel.append(scroll, renderLegend());
    const details = node("div", "opportunity-selected-event");
    const previouslySelected = timelineRows(detail).find((item) => eventIdentity(item) === componentState.selectedEventId) || null;
    if (options.docked) {
      const collapsible = node("details", "dock-selected-evidence");
      collapsible.open = !componentState.detailsCollapsed;
      collapsible.append(node("summary", "", `Selected canonical evidence · ${detail.symbol}`), details);
      collapsible.addEventListener("toggle", () => {
        componentState.detailsCollapsed = !collapsible.open;
        options.onDetailsChange?.(componentState.detailsCollapsed);
        componentState.resizeObserver?.disconnect();
        globalObject.requestAnimationFrame(() => componentState.resizeObserver?.observe(scroll));
      });
      mapPanel.append(collapsible);
    } else {
      mapPanel.append(details);
    }
    renderEventDetails(details, previouslySelected);
    target.append(mapPanel);
    const selectEvidence = (item) => {
      componentState.selectedEventId = item.pivot_event_key || eventIdentity(item);
      renderEventDetails(details, item);
      drawChart(canvas, detail, componentState.rangeDays, componentState.selectedEventId, selectEvidence, { timeBounds: chartViewportBounds(detail, componentState) });
      target.querySelectorAll(".opportunity-timeline-table tr[data-event-id]").forEach((row) => row.classList.toggle("selected", row.dataset.eventId === eventIdentity(item)));
      mapPanel.scrollIntoView({ block: "nearest", behavior: "smooth" });
    };
    const viewportStatus = node("output", "visually-hidden", "");
    viewportStatus.setAttribute("aria-live", "polite");
    mapPanel.append(viewportStatus);
    redraw = () => {
      const minimumWidth = options.docked ? 280 : 680;
      const available = Math.max(minimumWidth, Math.floor(scroll.clientWidth - (options.docked ? 16 : 20)));
      canvas.width = available;
      canvas.height = componentState.maximized
        ? Math.max(350, globalObject.innerHeight - 190)
        : options.docked
        ? Math.max(260, globalObject.innerHeight - (componentState.detailsCollapsed ? 178 : 300))
        : 350;
      canvas.style.width = `${canvas.width}px`;
      canvas.style.height = `${canvas.height}px`;
      const bounds = chartViewportBounds(detail, componentState);
      mapPanel.dataset.viewStart = String(Math.round(bounds.minimum));
      mapPanel.dataset.viewEnd = String(Math.round(bounds.maximum));
      mapPanel.dataset.viewSpanDays = ((bounds.maximum - bounds.minimum) / chartViewport.DAY_MS).toFixed(3);
      viewportStatus.textContent = `Visible chart domain ${shortTime(bounds.minimum)} to ${shortTime(bounds.maximum)}`;
      drawChart(canvas, detail, componentState.rangeDays, componentState.selectedEventId, selectEvidence, { timeBounds: bounds });
    };
    componentState.pointers = new Map();
    canvas.onwheel = (event) => {
      event.preventDefault();
      const box = canvas.getBoundingClientRect();
      if (event.ctrlKey || Math.abs(event.deltaY) > Math.abs(event.deltaX)) {
        const anchor = Math.max(0, Math.min(1, (event.clientX - box.left) / Math.max(1, box.width)));
        componentState.viewport = chartViewport.zoomTimeViewport(componentState.viewport, event.deltaY < 0 ? 1.15 : 1 / 1.15, anchor);
      } else {
        const span = componentState.viewport.maximum - componentState.viewport.minimum;
        componentState.viewport = chartViewport.panTimeViewport(componentState.viewport, event.deltaX / Math.max(1, box.width) * span);
      }
      redraw();
    };
    canvas.onkeydown = (event) => {
      const span = componentState.viewport.maximum - componentState.viewport.minimum;
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        const direction = event.key === "ArrowLeft" ? -1 : 1;
        componentState.viewport = chartViewport.panTimeViewport(componentState.viewport, direction * span * 0.1);
        redraw();
      } else if (event.key === "+" || event.key === "=") {
        event.preventDefault();
        componentState.viewport = chartViewport.zoomTimeViewport(componentState.viewport, 1.2);
        redraw();
      } else if (event.key === "-" || event.key === "_") {
        event.preventDefault();
        componentState.viewport = chartViewport.zoomTimeViewport(componentState.viewport, 1 / 1.2);
        redraw();
      } else if (event.key === "Home") {
        event.preventDefault();
        componentState.viewport = createOpportunityViewport(detail, componentState.rangeDays);
        redraw();
      }
    };
    canvas.onpointerdown = (event) => {
      componentState.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
      componentState.drag = { id: event.pointerId, x: event.clientX };
      canvas._suppressOpportunityClick = false;
      canvas.setPointerCapture?.(event.pointerId);
      if (componentState.pointers.size === 2) {
        const points = [...componentState.pointers.values()];
        componentState.pinch = { distance: Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y), viewport: { ...componentState.viewport } };
      }
    };
    canvas.onpointermove = (event) => {
      const previous = componentState.pointers.get(event.pointerId);
      if (!previous) return;
      componentState.pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
      const box = canvas.getBoundingClientRect();
      if (componentState.pointers.size >= 2 && componentState.pinch) {
        const points = [...componentState.pointers.values()];
        const distance = Math.max(1, Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y));
        const anchor = Math.max(0, Math.min(1, (((points[0].x + points[1].x) / 2) - box.left) / Math.max(1, box.width)));
        componentState.viewport = chartViewport.zoomTimeViewport(componentState.pinch.viewport, distance / Math.max(1, componentState.pinch.distance), anchor);
        canvas._suppressOpportunityClick = true;
        redraw();
        return;
      }
      if (!componentState.drag || componentState.drag.id !== event.pointerId) return;
      const delta = event.clientX - componentState.drag.x;
      if (Math.abs(delta) < 4) return;
      const span = componentState.viewport.maximum - componentState.viewport.minimum;
      componentState.viewport = chartViewport.panTimeViewport(componentState.viewport, -delta / Math.max(10, box.width) * span);
      componentState.drag.x = event.clientX;
      canvas._suppressOpportunityClick = true;
      redraw();
    };
    const endPointer = (event) => {
      componentState.pointers.delete(event.pointerId);
      componentState.drag = null;
      if (componentState.pointers.size < 2) componentState.pinch = null;
    };
    canvas.onpointerup = endPointer;
    canvas.onpointercancel = endPointer;
    componentState.resizeObserver?.disconnect();
    componentState.resizeObserver = typeof globalObject.ResizeObserver === "function" ? new globalObject.ResizeObserver(redraw) : null;
    componentState.resizeObserver?.observe(scroll);
    globalObject.requestAnimationFrame(redraw);
    return { mapPanel, selectEvidence };
  }

  function evidenceLabel(value, fallback = "Unavailable") {
    if (!value) return fallback;
    return String(value).replaceAll("_", " ").toLowerCase().replace(/(^|\s)\S/g, (letter) => letter.toUpperCase());
  }

  function rangeMidpoint(item) {
    const lower = Number(item?.lower_bound);
    const upper = Number(item?.upper_bound);
    return Number.isFinite(lower) && Number.isFinite(upper) ? (lower + upper) / 2 : null;
  }

  function renderCurrentReadout(detail) {
    const intelligence = detail.structural_intelligence || {};
    const activeMrz = [...(detail.mrz_lifecycles || [])].sort((left, right) => parseTime(right.known_at) - parseTime(left.known_at))[0] || null;
    const latestNear = [...(detail.near_miss_events || [])].sort((left, right) => parseTime(right.known_at) - parseTime(left.known_at))[0] || null;
    const readout = node("section", "opportunity-current-readout panel");
    const heading = node("header", "opportunity-current-readout-heading");
    const headingCopy = node("div", "");
    headingCopy.append(node("strong", "", "Current Readout"), node("small", "", `Latest canonical opportunity context for ${detail.symbol}.`));
    heading.append(headingCopy);
    const grid = node("dl", "opportunity-current-readout-grid");
    const activeMidpoint = rangeMidpoint(activeMrz);
    const nearMidpoint = rangeMidpoint(latestNear);
    const nearDeviation = latestNear?.deviation_pct ?? latestNear?.minimum_required_allowance_pct;
    const fields = [
      ["IPDA Location", detail.latest_ipda_location || "Unavailable", "location"],
      ["Active MRZ", activeMrz ? `${rangeText(activeMrz)} · Mid ${price(activeMidpoint)} · ${activeMrz.route || activeMrz.mrz_route || "Route unavailable"}` : "Unavailable", "mrz"],
      ["Latest Near Miss", latestNear ? `${rangeText(latestNear)} · Mid ${price(nearMidpoint)}${nearDeviation !== null && nearDeviation !== undefined ? ` · ${Number(nearDeviation).toFixed(2)}%` : " · deviation unavailable"}` : "Unavailable", "near"],
      ["Migration Structure", intelligence.migration_structure_label || "Undetermined", `structure-${intelligence.migration_structure || "undetermined"}`],
      ["Derived Route Hypothesis", intelligence.route_hypothesis_label || "Insufficient history", "route"],
      ["Opportunity Evidence State", evidenceLabel(intelligence.evidence_state, "Insufficient evidence"), `evidence-${intelligence.evidence_state || "insufficient"}`],
    ];
    fields.forEach(([label, value, tone]) => {
      const item = node("div", `opportunity-current-readout-item ${tone}`);
      item.append(node("dt", "", label), node("dd", "", value));
      grid.append(item);
    });
    readout.append(heading, grid);
    return readout;
  }

  function renderOpportunityWorkspace(target, detail, componentState, options = {}) {
    target.replaceChildren();
    if (options.docked) {
      renderMapComponent(target, detail, componentState, options);
      return;
    }
    const breadcrumb = node("nav", "opportunity-breadcrumb");
    breadcrumb.setAttribute("aria-label", "Opportunity workspace breadcrumb");
    const groups = node("button", "", "Group Radar"); groups.type = "button"; groups.addEventListener("click", options.onBackToGroups || (() => {}));
    const group = node("button", "", options.groupName || "Selected group"); group.type = "button"; group.addEventListener("click", options.onBackToGroup || (() => {}));
    breadcrumb.append(groups, node("span", "", "/"), group, node("span", "", "/"), node("strong", "", detail.symbol));
    target.append(breadcrumb);
    const header = node("header", "opportunity-symbol-header");
    const identity = node("div", "");
    const headerActions = node("div", "opportunity-symbol-actions");
    const backToGroup = node("button", "quiet-button opportunity-back-to-group", "← Back to Group Evolution");
    backToGroup.type = "button";
    backToGroup.addEventListener("click", options.onBackToGroup || (() => {}));
    headerActions.append(backToGroup);
    headerActions.append(renderCanonicalEvidenceLink(detail, options));
    identity.append(headerActions, node("p", "", "OPPORTUNITY INTELLIGENCE"), node("h3", "", `${detail.symbol} — Opportunity Map`));
    header.append(identity); target.append(header);

    const replay = node("section", "opportunity-replay panel");
    const replayHeading = node("header", "opportunity-panel-heading");
    const replayTitle = node("div", ""); replayTitle.append(node("strong", "", "Historical Replay — As Known At"), node("small", "", "Future-known evidence is hidden"));
    const controls = node("div", "opportunity-replay-controls");
    const previous = node("button", "quiet-button", "Previous"); previous.type = "button";
    const play = node("button", "primary-button", componentState.playing ? "Pause" : "Play"); play.type = "button";
    const next = node("button", "quiet-button", "Next"); next.type = "button";
    const latest = node("button", "quiet-button", "Latest"); latest.type = "button";
    const replaySlider = node("input", "opportunity-replay-slider");
    replaySlider.type = "range";
    replaySlider.setAttribute("aria-label", "Historical replay timestamp");
    const currentReplayIndex = cursorIndexAtOrBefore(
      componentState.cursors,
      componentState.replayTimestamp || detail.as_known_at || componentState.cursors.at(-1),
    );
    replaySlider.min = "0";
    replaySlider.max = String(Math.max(0, componentState.cursors.length - 1));
    replaySlider.step = "1";
    replaySlider.value = String(currentReplayIndex);
    replaySlider.disabled = componentState.cursors.length <= 1;
    const selectedTime = node("output", "opportunity-replay-selected", exactTime(componentState.cursors[currentReplayIndex]));
    selectedTime.htmlFor = replaySlider.id = `opportunityReplaySlider-${detail.symbol}`;
    const moveTo = (index) => {
      const bounded = Math.max(0, Math.min(componentState.cursors.length - 1, index));
      componentState.cursorIndex = bounded;
      componentState.replayTimestamp = componentState.cursors[bounded];
      componentState.loadCursor(componentState.cursors[bounded]);
    };
    previous.addEventListener("click", () => moveTo(componentState.cursorIndex - 1));
    next.addEventListener("click", () => moveTo(componentState.cursorIndex + 1));
    latest.addEventListener("click", () => moveTo(componentState.cursors.length - 1));
    const loadSliderTime = () => {
      componentState.cursorIndex = Number(replaySlider.value);
      componentState.replayTimestamp = componentState.cursors[componentState.cursorIndex];
      componentState.loadCursor(componentState.replayTimestamp);
    };
    replaySlider.addEventListener("input", () => {
      componentState.cursorIndex = Number(replaySlider.value);
      componentState.replayTimestamp = componentState.cursors[componentState.cursorIndex];
      selectedTime.textContent = exactTime(componentState.replayTimestamp);
      globalObject.clearTimeout(componentState.sliderTimer);
      componentState.sliderTimer = globalObject.setTimeout(loadSliderTime, 160);
    });
    replaySlider.addEventListener("change", () => {
      globalObject.clearTimeout(componentState.sliderTimer);
      loadSliderTime();
    });
    play.addEventListener("click", () => {
      componentState.playing = !componentState.playing;
      if (!componentState.playing) { globalObject.clearTimeout(componentState.playTimer); renderOpportunityWorkspace(target, detail, componentState, options); return; }
      const advance = () => {
        if (!componentState.playing) return;
        if (componentState.cursorIndex >= componentState.cursors.length - 1) componentState.cursorIndex = 0;
        else componentState.cursorIndex += 1;
        componentState.replayTimestamp = componentState.cursors[componentState.cursorIndex];
        componentState.loadCursor(componentState.cursors[componentState.cursorIndex]).finally(() => {
          if (componentState.playing) componentState.playTimer = globalObject.setTimeout(advance, 900);
        });
      };
      advance();
    });
    controls.append(previous, play, next); replayHeading.append(replayTitle, controls); replay.append(replayHeading);
    const sliderRow = node("div", "opportunity-replay-slider-row");
    sliderRow.append(replaySlider, selectedTime, latest);
    replay.append(sliderRow, node("p", "opportunity-replay-note", `Visible evidence known by ${exactTime(detail.as_known_at)}. Event time and knowledge time remain separate.`)); target.append(replay);

    const visualGrid = node("div", "opportunity-map-timeline-grid"); target.append(visualGrid);
    const { selectEvidence } = renderMapComponent(visualGrid, detail, componentState, { ...options, workspaceTarget: target });

    const timeline = node("section", "opportunity-event-timeline panel");
    const recordCount = timelineRowsForMode(detail, componentState.timelineMode).length;
    const timelineHeader = node("header", "opportunity-panel-heading");
    const timelineTitle = node("div", ""); timelineTitle.append(node("strong", "", `Opportunity Event Timeline (${detail.symbol})`), node("small", "", `${recordCount} records · newest first`));
    const timelineModes = node("div", "opportunity-range-controls timeline-mode-controls");
    [["all", "All Events"], ["key", "Key Events"]].forEach(([mode, label]) => {
      const button = node("button", "", label); button.type = "button"; button.setAttribute("aria-pressed", String(componentState.timelineMode === mode));
      button.addEventListener("click", () => { componentState.timelineMode = mode; componentState.timelineExpanded = false; renderOpportunityWorkspace(target, detail, componentState, options); });
      timelineModes.append(button);
    });
    timelineHeader.append(timelineTitle, timelineModes);
    const timelineWrap = renderTimeline(detail, selectEvidence, componentState.timelineExpanded, componentState.timelineMode);
    timeline.append(timelineHeader, timelineWrap);
    if (recordCount > 8) {
      const expansion = node("button", "opportunity-timeline-toggle", componentState.timelineExpanded ? "Show first 8 events" : `View all ${recordCount} events`);
      expansion.type = "button";
      expansion.setAttribute("aria-expanded", String(Boolean(componentState.timelineExpanded)));
      expansion.addEventListener("click", () => {
        componentState.timelineExpanded = !componentState.timelineExpanded;
        const rows = timelineRowsForMode(detail, componentState.timelineMode);
        const body = timelineBody(componentState.timelineExpanded ? rows : rows.slice(0, 8), selectEvidence);
        timelineWrap.querySelector("tbody").replaceWith(body);
        timelineWrap.classList.toggle("expanded", componentState.timelineExpanded);
        expansion.textContent = componentState.timelineExpanded ? "Show first 8 events" : `View all ${recordCount} events`;
        expansion.setAttribute("aria-expanded", String(componentState.timelineExpanded));
      });
      timeline.append(expansion);
    }
    visualGrid.append(timeline);
    target.append(renderCurrentReadout(detail));
  }

  function renderCandidateTable(target, summary, onSelect, options = {}) {
    target.replaceChildren();
    const header = node("header", "opportunity-candidate-heading");
    const identity = node("div", "", "Symbol Opportunity Candidates");
    const actions = node("div", "opportunity-candidate-actions");
    actions.append(node("span", "", `${summary.candidates.length} research hypotheses`));
    if (options.onCompare && (options.members || []).length >= 2) {
      const compare = node("button", "opportunity-compare-action", "Compare Maps");
      compare.type = "button";
      compare.addEventListener("click", options.onCompare);
      actions.append(compare);
    }
    header.append(identity, actions); target.append(header);
    const wrap = node("div", "opportunity-candidate-table-wrap");
    const table = node("table", "opportunity-candidate-table");
    const head = node("thead", "");
    head.innerHTML = "<tr><th>Symbol</th><th>Hypothesis</th><th>IPDA location</th><th>MRZ levels</th><th>Observations</th><th>Opportunity state</th><th>Latest development</th><th aria-label=\"Open\"></th></tr>";
    const body = node("tbody", "");
    summary.candidates
      .slice()
      .sort((left, right) => (STAGE_ORDER[right.state] || 0) - (STAGE_ORDER[left.state] || 0) || left.symbol.localeCompare(right.symbol))
      .forEach((candidate) => {
        const primary = options.primaryHypotheses?.[candidate.symbol]?.hypothesis || candidate.hypothesis;
        const latestEvidence = options.latestEvidence?.[candidate.symbol];
        const row = node("tr", ""); row.tabIndex = 0;
        const symbol = node("td", "opportunity-candidate-symbol", candidate.symbol);
        const hypothesis = node("td", ""); hypothesis.append(node("b", `route ${String(primary).toLowerCase()}`, primary));
        const location = node("td", "", candidate.ipda_location || "Unavailable");
        const mrz = node("td", "", candidate.mrz ? `${price(candidate.mrz.lower)}–${price(candidate.mrz.upper)}` : "No active MRZ");
        const observations = node("td", "", String(candidate.observation_count ?? 0));
        const stage = node("td", ""); stage.append(node("span", `opportunity-stage ${stageClass(candidate.state)}`, candidate.state_label));
        const latest = node("td", "opportunity-candidate-development", latestEvidence ? `${latestEvidence.event_type.replaceAll("_", " ")} · ${shortTime(latestEvidence.occurred_at)}` : `${candidate.latest_event_type} · ${shortTime(candidate.latest_event_at)}`);
        const open = node("td", "opportunity-candidate-open", "Open →");
        row.append(symbol, hypothesis, location, mrz, observations, stage, latest, open);
        row.addEventListener("click", () => onSelect(candidate.symbol));
        row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(candidate.symbol); } });
        body.append(row);
      });
    if (!summary.candidates.length) { const row = node("tr", ""); const cell = node("td", "opportunity-empty", "No canonical opportunity context is available for this group."); cell.colSpan = 8; row.append(cell); body.append(row); }
    table.append(head, body); wrap.append(table); target.append(wrap);
  }

  function migrationDirectionBreakdown(activityRecords = [], migrationEvidence = {}) {
    const evidenceByKey = new Map(
      (migrationEvidence.events || []).map((item) => [String(item.event_key), item]),
    );
    const categories = { higher: [], lower: [], unchanged: [], unknown: [] };
    activityRecords
      .filter((item) => item.tracker === "mrz" && item.event_type === "MRZ_MIGRATED")
      .forEach((record) => {
        const key = String(record.source_event_id || record.id || "");
        const evidence = evidenceByKey.get(key);
        const canonicalDirection = evidence?.direction;
        const direction = canonicalDirection === "higher" || canonicalDirection === "lower"
          ? canonicalDirection
          : canonicalDirection === "same_midpoint" ? "unchanged" : "unknown";
        categories[direction].push({
          ...record,
          ...(evidence || {}),
          direction,
          canonical_direction: canonicalDirection || "unknown",
          event_key: evidence?.event_key || record.source_event_id || record.id,
        });
      });
    const counts = Object.fromEntries(
      Object.entries(categories).map(([direction, events]) => [direction, events.length]),
    );
    const total = Object.values(counts).reduce((sum, count) => sum + count, 0);
    return {
      total,
      counts,
      categories,
      unique_symbols: new Set(
        Object.values(categories).flat().map((item) => item.symbol),
      ).size,
      reconciled: total === activityRecords.filter(
        (item) => item.tracker === "mrz" && item.event_type === "MRZ_MIGRATED",
      ).length,
    };
  }

  function renderGroupEvolution(target, report, options) {
    const section = node("section", "group-evolution panel");
    const heading = node("header", "group-evolution-heading");
    const title = node("div", ""); title.append(node("h2", "", "Group Evolution"), node("p", "", `Location Flow · Migration Structure · Structural Developments · ${report.window?.key || "Selected window"}`));
    heading.append(title, node("span", "group-evolution-basis", "Canonical evidence")); section.append(heading);
    const grid = node("div", "group-evolution-grid");

    const flow = report.location_flow || {};
    const flowCard = node("article", "group-evolution-card");
    flowCard.append(node("h3", "", `⌖ IPDA Location Flow (${report.window?.key || "window"})`), node("p", "group-evolution-help", "Movement across 20-week IPDA location categories."));
    const flowLayout = node("div", "group-flow-layout");
    const movement = node("section", "group-flow-movement");
    const movementHead = node("div", "group-flow-head"); movementHead.append(node("strong", "", "Movement (Start → Current)"), node("strong", "", "Symbols")); movement.append(movementHead);
    const pathList = node("div", "group-flow-paths");
    const flowInspector = node("div", "group-flow-inspector"); flowInspector.hidden = true;
    (flow.paths || []).forEach((path) => {
      const button = node("button", `group-flow-path ${path.direction || ""}`, ""); button.type = "button";
      const label = node("span", "group-flow-path-label"); label.append(node("i", "group-flow-arrow", path.direction === "higher" ? "↑" : "↓"), node("span", "", `${path.start_location_label} → ${path.current_location_label}`));
      button.append(label, node("strong", "", `${path.symbol_count} ${path.symbol_count === 1 ? "symbol" : "symbols"}`));
      button.title = path.symbols.join(", ");
      button.addEventListener("click", () => {
        if (path.symbols.length === 1) { options.onSelectSymbol?.(path.symbols[0]); return; }
        flowInspector.replaceChildren(node("strong", "", `${path.start_location_label} → ${path.current_location_label}`));
        const symbols = node("div", "group-flow-symbols");
        path.symbols.forEach((symbol) => { const open = node("button", "group-flow-symbol", symbol); open.type = "button"; open.addEventListener("click", () => options.onSelectSymbol?.(symbol)); symbols.append(open); });
        flowInspector.append(symbols); flowInspector.hidden = false;
      }); pathList.append(button);
    });
    if (!(flow.paths || []).length) pathList.append(node("p", "opportunity-empty", "No start-to-current location changes in this period."));
    movement.append(pathList, flowInspector);
    const fs = flow.summary || {};
    const flowSummary = node("aside", "group-evolution-summary"); flowSummary.append(node("h4", "", `Flow Summary (${report.window?.key || "window"})`));
    [["lower", "↓", fs.moved_lower || 0, "Moved lower"], ["higher", "↑", fs.moved_higher || 0, "Moved higher"], ["unchanged", "—", fs.same_bucket || 0, "Unchanged"], ["unavailable", "?", (flow.unavailable_members || []).length, "Unavailable"]].forEach(([tone, icon, count, label]) => { const item = node("span", tone); item.append(node("i", "", icon), node("b", "", String(count)), node("em", "", label)); flowSummary.append(item); });
    flowLayout.append(movement, flowSummary); flowCard.append(flowLayout);
    const distribution = report.structural?.current_distribution || {};
    const premium = Number(distribution.deep_premium || 0) + Number(distribution.shallow_premium || 0);
    const equilibrium = Number(distribution.at_eqm || 0);
    const discount = Number(distribution.shallow_discount || 0) + Number(distribution.deep_discount || 0);
    const currentDistribution = node("div", "group-current-distribution");
    currentDistribution.append(node("strong", "", "Current Location (Group)"));
    const distributionTotal = Math.max(1, premium + equilibrium + discount + Number(distribution.unavailable || 0));
    const premiumDegrees = premium / distributionTotal * 360;
    const equilibriumDegrees = equilibrium / distributionTotal * 360;
    const donut = node("span", "group-current-donut");
    donut.style.background = `conic-gradient(#ff4d55 0 ${premiumDegrees}deg, #f0b519 ${premiumDegrees}deg ${premiumDegrees + equilibriumDegrees}deg, #19d99a ${premiumDegrees + equilibriumDegrees}deg 360deg)`;
    donut.append(node("b", "", String(distributionTotal)), node("em", "", "symbols"));
    currentDistribution.append(donut);
    [["premium", "Premium", premium], ["equilibrium", "Equilibrium", equilibrium], ["discount", "Discount", discount], ["unavailable", "Unavailable", Number(distribution.unavailable || 0)]].forEach(([tone, label, count]) => {
      const item = node("span", tone); item.append(node("b", "", String(count)), node("em", "", label)); currentDistribution.append(item);
    });
    flowCard.append(currentDistribution);

    const intelligence = report.structural_intelligence || {};
    const structuralSummary = intelligence.summary || {};
    const structureCard = node("article", "group-evolution-card migration-structure-card");
    structureCard.append(node("h3", "", "Migration Structure (Group)"), node("p", "group-evolution-help", `Backend structural classification from complete canonical MRZ history · ${structuralSummary.eligible_count || 0}/${structuralSummary.member_count || 0} eligible.`));
    const structureTiles = node("div", "migration-structure-tiles");
    [["ascending", "Ascending"], ["descending", "Descending"], ["transitional", "Transitional"], ["undetermined", "Undetermined"]].forEach(([key, label]) => {
      const count = Number(structuralSummary[key] || 0);
      const percent = Number(structuralSummary.percentages?.[key] || 0);
      const tile = node("article", `migration-structure-tile ${key}`);
      tile.append(node("strong", "", label), node("b", "", String(count)), node("span", "", `${Math.round(percent)}%`));
      structureTiles.append(tile);
    });
    const dominant = String(structuralSummary.dominant_structure || "undetermined");
    const structureFoot = node("div", "migration-structure-foot");
    structureFoot.append(node("span", "", "Group Structure"), node("strong", `structure-dominance ${dominant}`, dominant === "undetermined" ? "Undetermined" : `${dominant[0].toUpperCase()}${dominant.slice(1)} Dominant`), node("em", "", `${structuralSummary.eligible_count || 0} / ${structuralSummary.member_count || 0} eligible · ${Math.round(Number(structuralSummary.coverage_percent || 0))}% coverage`));
    structureCard.append(structureTiles, structureFoot);
    grid.append(flowCard, structureCard); section.append(grid);

    const activity = report.activity || {}; const activityRecords = activity.records || [];
    const activationRecords = activityRecords.filter((item) => item.tracker === "mrz" && item.event_type === "MRZ_ACTIVATED");
    const migrationRecords = activityRecords.filter((item) => item.tracker === "mrz" && item.event_type === "MRZ_MIGRATED");
    const migrationBreakdown = migrationDirectionBreakdown(
      activityRecords,
      report.directional?.mrz_migrations || {},
    );
    const nearMissRecords = activityRecords.filter((item) => item.tracker === "near_miss");
    const migrationDetail = node("section", "migration-direction-detail"); migrationDetail.hidden = true; migrationDetail.id = `migrationDirectionDetail-${report.group?.id || "group"}`;
    const migrationButtons = [];
    const renderMigrationDetail = (direction) => {
      const labels = { all: "All", higher: "Higher", lower: "Lower", unchanged: "Unchanged", unknown: "Unknown" };
      const events = direction === "all"
        ? Object.values(migrationBreakdown.categories).flat().sort((left, right) => parseTime(right.occurred_at) - parseTime(left.occurred_at))
        : migrationBreakdown.categories[direction] || [];
      const uniqueSymbols = new Set(events.map((item) => item.symbol)).size;
      const detailHeading = node("header", "migration-direction-detail-heading");
      const headingCopy = node("div", ""); headingCopy.append(node("h3", "", `MRZ Migration — ${labels[direction]}`), node("p", "", `${events.length} ${events.length === 1 ? "event" : "events"} · ${uniqueSymbols} unique ${uniqueSymbols === 1 ? "symbol" : "symbols"}`));
      const close = node("button", "migration-direction-close", "Close"); close.type = "button"; close.addEventListener("click", () => { migrationDetail.hidden = true; migrationButtons.forEach((button) => button.setAttribute("aria-expanded", "false")); });
      detailHeading.append(headingCopy, close);
      const wrap = node("div", "migration-direction-table-wrap");
      const table = node("table", "migration-direction-table");
      const head = node("thead", ""); head.innerHTML = "<tr><th>Symbol</th><th>Migration time</th><th>Previous MRZ</th><th>Successor MRZ</th><th>Previous midpoint</th><th>Successor midpoint</th><th>Direction</th><th>Evidence</th></tr>";
      const body = node("tbody", "");
      events.forEach((item) => {
        const row = node("tr", "");
        const evidence = node("a", "migration-evidence-link", "Open →"); evidence.href = `/mrz/events?symbol=${encodeURIComponent(item.symbol)}&event=${encodeURIComponent(item.event_key || item.source_event_id || item.id)}`;
        row.append(
          node("td", "migration-symbol", item.symbol),
          node("td", "", exactTime(item.occurred_at)),
          node("td", "", item.old_lower != null && item.old_upper != null ? `${price(item.old_lower)}–${price(item.old_upper)}` : "Unavailable"),
          node("td", "", item.new_lower != null && item.new_upper != null ? `${price(item.new_lower)}–${price(item.new_upper)}` : "Unavailable"),
          node("td", "", item.old_midpoint != null ? price(item.old_midpoint) : "Unavailable"),
          node("td", "", item.new_midpoint != null ? price(item.new_midpoint) : "Unavailable"),
          node("td", `migration-direction ${item.direction || direction}`, labels[item.direction] || labels[direction]),
        );
        const linkCell = node("td", ""); linkCell.append(evidence); row.append(linkCell); body.append(row);
      });
      if (!events.length) { const row = node("tr", ""); const empty = node("td", "migration-direction-empty", `No ${direction === "all" ? "canonical" : labels[direction].toLowerCase()} migrations in this period.`); empty.colSpan = 8; row.append(empty); body.append(row); }
      table.append(head, body); wrap.append(table); migrationDetail.replaceChildren(detailHeading, wrap); migrationDetail.hidden = false;
      migrationButtons.forEach((button) => button.setAttribute("aria-expanded", String(button.dataset.direction === direction)));
    };
    const middleRow = node("div", "group-structural-middle-row");
    const eventActivity = node("section", "group-structural-event-activity");
    const activityIntro = node("header", "group-structural-panel-heading");
    activityIntro.append(
      node("h3", "", `Structural Event Activity (${report.window?.key || "window"})`),
      node("p", "", "Canonical structural events across group members."),
    );
    const activityMetrics = node("div", "group-structural-event-list");
    [["near", "Near Miss", activity.summary?.near_miss_episode_count || 0], ["activation", "MRZ Activation", activationRecords.length]].forEach(([tone, label, count]) => {
      const metric = node("article", `group-structural-event ${tone}`);
      metric.append(node("i", "event-marker", ""), node("span", "", label), node("strong", "", String(count)));
      activityMetrics.append(metric);
    });
    const migrationMetric = node("button", "group-structural-event migration", "");
    migrationMetric.type = "button";
    migrationMetric.dataset.direction = "all";
    migrationMetric.setAttribute("aria-controls", migrationDetail.id);
    migrationMetric.setAttribute("aria-expanded", "false");
    migrationMetric.setAttribute("aria-label", `Inspect ${migrationRecords.length} canonical MRZ migration events`);
    migrationMetric.append(node("i", "event-marker", ""), node("span", "", "MRZ Migration"), node("strong", "", String(migrationRecords.length)));
    migrationMetric.addEventListener("click", () => renderMigrationDetail("all"));
    migrationButtons.push(migrationMetric);
    activityMetrics.append(migrationMetric);
    eventActivity.append(activityIntro, activityMetrics);

    const developments = intelligence.developments || [];
    const isAccumulationCandidate = (item) => item.migration_structure === "transitional"
      && item.route_hypothesis === "STR_DOMINANT_EMERGING_BTD"
      && ["HL", "HH"].includes(item.type);
    const accumulationCount = developments.filter(isAccumulationCandidate).length;
    const developmentWrap = node("section", "group-structural-developments");
    const developmentTitle = node("header", "structural-development-heading");
    const developmentCopy = node("div", ""); developmentCopy.append(node("h3", "", `Structural Developments (${report.window?.key || "window"})`), node("p", "", "New or meaningful changes in migration structure."));
    const developmentMeta = node("div", "structural-development-meta");
    developmentMeta.append(
      node("span", "structural-focus", "Accumulation Focus"),
      node("span", "structural-focus-summary", accumulationCount
        ? `${accumulationCount} ${accumulationCount === 1 ? "symbol" : "symbols"} showing early accumulation evidence.`
        : "No symbols showing early accumulation evidence."),
    );
    const allEvents = node("a", "structural-view-all", "View All Events →");
    const eventsTarget = new URL(options.eventsUrl || "/mrz/events", globalObject.location.origin);
    eventsTarget.searchParams.set("return", `${globalObject.location.pathname}${globalObject.location.search}`);
    allEvents.href = `${eventsTarget.pathname}${eventsTarget.search}`;
    developmentTitle.append(developmentCopy, developmentMeta, allEvents);
    developmentWrap.append(developmentTitle);
    const developmentTable = node("table", "group-transition-table structural-development-table");
    const developmentHead = node("thead", ""); developmentHead.innerHTML = "<tr><th>Symbol</th><th>Development</th><th>Structure (Now)</th><th>Route Hypothesis</th><th>Opportunity</th><th>Evidence</th></tr>";
    const developmentBody = node("tbody", "");
    developments.forEach((item) => {
      const accumulationCandidate = isAccumulationCandidate(item);
      const distributionCandidate = item.migration_structure === "transitional" && item.route_hypothesis === "BTD_DOMINANT_EMERGING_STR" && ["LH", "LL"].includes(item.type);
      const distributionActive = item.migration_structure === "descending" && item.route_hypothesis === "STR_DOMINANT";
      const opportunity = accumulationCandidate ? "Accumulation Candidate" : distributionCandidate ? "Distribution Candidate" : distributionActive ? "Distribution (active)" : item.migration_structure === "ascending" ? "Accumulation" : "Monitor";
      const developmentNames = { HH: "Higher high", HL: "Higher low", LH: "Lower high", LL: "Lower low", HIGH: "High", LOW: "Low", EH: "Equal high", EL: "Equal low" };
      const maturity = item.maturity === "developing" ? "developing" : "confirmed";
      const row = node("tr", accumulationCandidate ? "accumulation-candidate" : "");
      const open = node("a", "group-transition-open", "Open →");
      const returnContext = encodeURIComponent(`${globalObject.location.pathname}${globalObject.location.search}`);
      open.href = `/mrz/symbols?symbol=${encodeURIComponent(item.symbol)}&focus=migration-path&development=${encodeURIComponent(item.development_id || "")}&return=${returnContext}`;
      const evidenceCell = node("td", ""); evidenceCell.append(open);
      const opportunityCell = node("td", ""); opportunityCell.append(node("span", `opportunity-label ${opportunity.toLowerCase().replaceAll(" ", "-").replace(/[()]/g, "")}`, opportunity));
      row.append(node("td", "symbol", item.symbol), node("td", "development", `${developmentNames[item.type] || item.type} (${item.type}) — ${maturity}`), node("td", `structure ${item.migration_structure}`, item.migration_structure_label), node("td", "hypothesis", item.route_hypothesis_label), opportunityCell, evidenceCell);
      developmentBody.append(row);
    });
    if (!developments.length) {
      const row = node("tr", "structural-development-empty-row"); const empty = node("td", "migration-direction-empty", "No new meaningful structural developments in this selected period."); empty.colSpan = 6; row.append(empty); developmentBody.append(row);
    }
    developmentTable.append(developmentHead, developmentBody); developmentWrap.append(developmentTable);
    middleRow.append(eventActivity, developmentWrap);
    section.append(middleRow, migrationDetail);

    const memberWrap = node("div", "group-transition-table-wrap group-structural-overview");
    memberWrap.append(node("h3", "", "Group Members — Structural Overview"));
    const memberTable = node("table", "group-transition-table"); const memberHead = node("thead", ""); memberHead.innerHTML = "<tr><th>Symbol</th><th>IPDA Location</th><th>Active MRZ (Route)</th><th>Migration Structure</th><th>Route Hypothesis</th><th>Latest Development</th><th>Structure (Recent)</th><th>Opportunity</th><th>View Map</th></tr>"; const memberBody = node("tbody", "");
    (report.members || []).forEach((item) => {
      const row = node("tr", ""); const activeMrz = item.mrz ? `${price(item.mrz.lower)}–${price(item.mrz.upper)} (${item.route || "—"})` : "Inactive";
      const development = item.latest_structural_development ? `${item.latest_structural_development.type} · ${item.latest_structural_development.maturity}` : "No qualified pivot";
      const view = node("button", "group-transition-open", "View Map →"); view.type = "button"; view.addEventListener("click", () => options.onSelectSymbol?.(item.symbol));
      const viewCell = node("td", ""); viewCell.append(view);
      const recent = node("td", ""); const sparkline = node("span", `structure-sparkline ${item.migration_structure || "undetermined"}`);
      const sequence = item.structural_intelligence?.recent_sequence || [];
      (sequence.length ? sequence.slice(-4) : ["—", "—", "—"]).forEach((pivot) => sparkline.append(node("i", "", pivot)));
      recent.append(sparkline);
      const hypothesis = String(item.route_hypothesis || item.structural_intelligence?.route_hypothesis || "");
      const opportunityLabel = hypothesis.includes("EMERGING") ? (hypothesis.startsWith("STR") ? "Accumulation Candidate" : "Distribution Candidate") : item.migration_structure === "ascending" ? "Accumulation" : item.migration_structure === "descending" ? "Distribution" : "Monitor";
      const opportunity = node("td", ""); opportunity.append(node("span", `opportunity-label ${opportunityLabel.toLowerCase().replaceAll(" ", "-")}`, opportunityLabel));
      row.append(node("td", "", item.symbol), node("td", "", item.location_label || "Unavailable"), node("td", "", activeMrz), node("td", `structure ${item.migration_structure}`, item.structural_intelligence?.migration_structure_label || "Undetermined"), node("td", "", item.route_hypothesis_label || "Insufficient history"), node("td", "", development), recent, opportunity, viewCell);
      memberBody.append(row);
    });
    memberTable.append(memberHead, memberBody); memberWrap.append(memberTable); section.append(memberWrap);
    target.append(section);
  }

  function renderGroup(target, payload, options = {}) {
    target.replaceChildren();
    const summary = payload.groups[0] || { candidates: [] };
    if (options.groupEvolution) renderGroupEvolution(target, options.groupEvolution, options);
    if (!options.groupEvolution) {
      const candidatePanel = node("section", "opportunity-candidates panel");
      renderCandidateTable(candidatePanel, summary, options.onSelectSymbol || (() => {}), options);
      target.append(candidatePanel);
    }
  }

  async function renderSymbol(target, symbol, options = {}) {
    target.replaceChildren(node("section", "panel opportunity-loading", `Reconstructing ${symbol}…`));
    let fullDetail = null;
    const componentState = {
      cursors: [], cursorIndex: 0, replayTimestamp: null, rangeDays: [0, 30, 90].includes(Number(options.initialRangeDays)) ? Number(options.initialRangeDays) : 90,
      playing: false, playTimer: null, sliderTimer: null, loadCursor: null,
      selectedEventId: options.initialSelectedEventId || null, timelineExpanded: false, timelineMode: "all", detailsCollapsed: Boolean(options.detailsCollapsed), resizeObserver: null,
      viewport: null, pointers: new Map(), pinch: null, drag: null, maximized: false,
    };
    const loadSymbol = async (symbol, asKnownAt = null) => {
      const params = new URLSearchParams(); if (asKnownAt) params.set("as_known_at", asKnownAt);
      const suffix = params.size ? `?${params}` : "";
      const [response, intelligenceResponse] = await Promise.all([
        globalObject.fetch(`/api/opportunities/${encodeURIComponent(symbol)}${suffix}`, { cache: "no-store" }),
        globalObject.fetch(`/api/symbols/${encodeURIComponent(symbol)}/structural-intelligence${suffix}`, { cache: "no-store" }),
      ]);
      if (!response.ok || !intelligenceResponse.ok) throw new Error("Opportunity history is unavailable.");
      const detail = await response.json();
      detail.structural_intelligence = await intelligenceResponse.json();
      if (!asKnownAt || !fullDetail || fullDetail.symbol !== symbol) {
        fullDetail = detail;
        componentState.cursors = collectReplayCursors(detail);
        componentState.cursorIndex = componentState.cursors.length - 1;
        componentState.replayTimestamp = componentState.cursors.at(-1);
        componentState.viewport = createOpportunityViewport(detail, componentState.rangeDays, options.initialViewport || null);
      } else {
        componentState.replayTimestamp = asKnownAt;
        componentState.cursorIndex = cursorIndexAtOrBefore(componentState.cursors, asKnownAt);
        componentState.viewport = createOpportunityViewport(detail, componentState.rangeDays);
      }
      componentState.loadCursor = (cursor) => loadSymbol(symbol, cursor).catch((error) => {
        target.replaceChildren(node("section", "panel opportunity-error", error.message));
      });
      renderOpportunityWorkspace(target, detail, componentState, options);
      return detail;
    };
    await loadSymbol(symbol);
  }

  globalObject.edgeOpportunityMap = {
    axisPrice,
    collectReplayCursors,
    cursorIndexAtOrBefore,
    comparisonTimeBounds,
    drawChart,
    eventIdentity,
    proportionalPosition,
    renderEventDetails,
    renderCanonicalEvidenceLink,
    renderGroup,
    renderLegend,
    migrationDirectionBreakdown,
    nearMissDisplayGeometry,
    renderSymbol,
    timelineRows,
    timeBounds,
  };
})(window);
