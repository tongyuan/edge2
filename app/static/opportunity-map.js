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
    (detail.near_miss_events || []).forEach((item) => times.push(parseTime(item.known_at)));
    (detail.mrz_lifecycles || []).forEach((item) => times.push(parseTime(item.known_at)));
    const finite = times.filter(Number.isFinite);
    const latest = finite.length ? Math.max(...finite, parseTime(detail.as_known_at)) : Date.now();
    const earliest = finite.length ? Math.min(...finite) : latest - (24 * 60 * 60 * 1000);
    if (!rangeDays) return { minimum: earliest, maximum: latest };
    return { minimum: Math.max(earliest, latest - rangeDays * 86400000), maximum: latest };
  }

  function comparisonTimeBounds(details, rangeDays) {
    const all = (details || []).flatMap((detail) => {
      const values = [];
      (detail.observations || []).forEach((item) => values.push(parseTime(item.effective_at)));
      (detail.near_miss_events || []).forEach((item) => values.push(parseTime(item.known_at), parseTime(item.ended_at)));
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
      near: (detail.near_miss_events || []).filter((item) => {
        const start = parseTime(item.known_at);
        const end = parseTime(item.ended_at || detail.as_known_at);
        return start <= bounds.maximum && end >= bounds.minimum;
      }),
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
    items.near.forEach((item) => {
      const start = Math.max(margin.left, x(item.known_at));
      const end = Math.min(width - margin.right, x(item.ended_at || detail.as_known_at));
      const top = y(item.upper_bound);
      const bottom = y(item.lower_bound);
      context.save();
      context.strokeStyle = eventIdentity(item) === selectedEventId ? "#f0dcff" : COLORS.near;
      context.lineWidth = eventIdentity(item) === selectedEventId ? 3 : 1;
      context.setLineDash([6, 4]);
      context.strokeRect(start, top, Math.max(2, end - start), Math.max(2, bottom - top));
      context.restore();
      zoneHits.push({ left: start, right: Math.max(start + 8, end), top: Math.min(top, bottom), bottom: Math.max(top + 8, bottom), item });
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
      zoneHits.push({ left: start, right: Math.max(start + 8, end), top: Math.min(top, bottom), bottom: Math.max(top + 8, bottom), item });
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
    canvas._opportunityHits = [...pointHits, ...zoneHits];
    canvas.onclick = (event) => {
      const box = canvas.getBoundingClientRect();
      const clickX = (event.clientX - box.left) * (canvas.width / box.width);
      const clickY = (event.clientY - box.top) * (canvas.height / box.height);
      const selectedPoint = pointHits
        .map((hit) => ({ hit, distance: Math.hypot(hit.x - clickX, hit.y - clickY) }))
        .filter((candidate) => candidate.distance <= candidate.hit.radius)
        .sort((left, right) => left.distance - right.distance)[0];
      if (selectedPoint) { onSelect(selectedPoint.hit.item); return; }
      const selectedZone = zoneHits.slice().reverse().find((hit) => (
        clickX >= hit.left && clickX <= hit.right && clickY >= hit.top && clickY <= hit.bottom
      ));
      if (selectedZone) onSelect(selectedZone.item);
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
    const sources = [
      [detail.observations || [], "Route observation"],
      [detail.near_miss_events || [], "Near Miss"],
      [detail.mrz_lifecycles || [], "MRZ"],
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
    return [...records.values()].sort((left, right) => parseTime(left.effective_at) - parseTime(right.effective_at) || parseTime(left.known_at) - parseTime(right.known_at) || eventIdentity(left).localeCompare(eventIdentity(right)));
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

  function renderTimeline(detail, onSelect, expanded = false) {
    const wrap = node("div", "opportunity-timeline-wrap");
    wrap.classList.toggle("expanded", expanded);
    const table = node("table", "opportunity-timeline-table");
    const head = node("thead", "");
    head.innerHTML = "<tr><th>Observed / known</th><th>Tracker</th><th>Event</th><th>Price / structural zone</th><th>Evidence details</th></tr>";
    const rows = timelineRows(detail);
    const visibleRows = expanded ? rows : rows.slice(0, 8);
    table.append(head, timelineBody(visibleRows, onSelect)); wrap.append(table); return wrap;
  }

  function renderMapComponent(target, detail, componentState, options = {}) {
    const mapPanel = node("section", `opportunity-map-panel panel${options.docked ? " docked-opportunity-map-panel" : ""}`);
    const mapHeader = node("header", "opportunity-panel-heading");
    const title = node("div", "");
    title.append(
      node("strong", "", "Opportunity Map (Time × Price)"),
      node("small", "", options.docked ? `${detail.symbol} · Actual event time · linear instrument price` : "Actual event time · linear instrument price"),
    );
    const mapTools = node("div", "opportunity-map-tools");
    const ranges = node("div", "opportunity-range-controls");
    [[0, "All"], [90, "90D"], [30, "30D"]].forEach(([days, label]) => {
      const button = node("button", "", label); button.type = "button"; button.setAttribute("aria-pressed", String(componentState.rangeDays === days));
      button.addEventListener("click", () => { componentState.rangeDays = days; options.onRangeChange?.(days); renderOpportunityWorkspace(target, detail, componentState, options); }); ranges.append(button);
    });
    mapTools.append(ranges);
    if (options.docked) {
      const evidence = renderCanonicalEvidenceLink(detail, { ...options, label: "Open Canonical Evidence" });
      evidence.addEventListener("click", (event) => {
        if (!globalObject.edgeDocking?.openInMain) return;
        event.preventDefault();
        globalObject.edgeDocking.openInMain(evidence.getAttribute("href"));
      });
      mapTools.append(evidence);
    } else if (globalObject.edgeDocking?.canDock()) {
      const dock = globalObject.edgeDocking.createDockButton("Dock Opportunity Map");
      dock.addEventListener("click", () => {
        const opened = globalObject.edgeDocking.openOpportunityMap(detail.symbol, {
          rangeDays: componentState.rangeDays,
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
      componentState.selectedEventId = eventIdentity(item);
      renderEventDetails(details, item);
      drawChart(canvas, detail, componentState.rangeDays, componentState.selectedEventId, selectEvidence);
      target.querySelectorAll(".opportunity-timeline-table tr[data-event-id]").forEach((row) => row.classList.toggle("selected", row.dataset.eventId === componentState.selectedEventId));
      mapPanel.scrollIntoView({ block: "nearest", behavior: "smooth" });
    };
    const redraw = () => {
      const minimumWidth = options.docked ? 280 : 680;
      const available = Math.max(minimumWidth, Math.floor(scroll.clientWidth - (options.docked ? 16 : 20)));
      canvas.width = available;
      canvas.height = options.docked
        ? Math.max(260, globalObject.innerHeight - (componentState.detailsCollapsed ? 178 : 300))
        : 280;
      if (options.docked) {
        canvas.style.width = `${canvas.width}px`;
        canvas.style.height = `${canvas.height}px`;
      }
      drawChart(canvas, detail, componentState.rangeDays, componentState.selectedEventId, selectEvidence);
    };
    componentState.resizeObserver?.disconnect();
    componentState.resizeObserver = typeof globalObject.ResizeObserver === "function" ? new globalObject.ResizeObserver(redraw) : null;
    componentState.resizeObserver?.observe(scroll);
    globalObject.requestAnimationFrame(redraw);
    return { mapPanel, selectEvidence };
  }

  function renderOpportunityWorkspace(target, detail, componentState, options = {}) {
    target.replaceChildren();
    if (options.docked) {
      renderMapComponent(target, detail, componentState, options);
      return;
    }
    const selectedEpisode = detail.episodes.find((item) => item.episode_id === detail.selected_episode_id) || detail.episodes[0] || {
      hypothesis: "NO KNOWN",
      origin_effective_at: null,
      state_label: "No evidence",
    };
    const breadcrumb = node("nav", "opportunity-breadcrumb");
    breadcrumb.setAttribute("aria-label", "Opportunity workspace breadcrumb");
    const groups = node("button", "", "Group Radar"); groups.type = "button"; groups.addEventListener("click", options.onBackToGroups || (() => {}));
    const group = node("button", "", options.groupName || "Selected group"); group.type = "button"; group.addEventListener("click", options.onBackToGroup || (() => {}));
    breadcrumb.append(groups, node("span", "", "/"), group, node("span", "", "/"), node("strong", "", detail.symbol));
    target.append(breadcrumb);
    const header = node("header", "opportunity-symbol-header");
    const identity = node("div", "");
    const headerActions = node("div", "opportunity-symbol-actions");
    const backToGroup = node("button", "quiet-button opportunity-back-to-group", "← Back to Group");
    backToGroup.type = "button";
    backToGroup.addEventListener("click", options.onBackToGroup || (() => {}));
    headerActions.append(backToGroup);
    headerActions.append(renderCanonicalEvidenceLink(detail, options));
    identity.append(headerActions, node("p", "", `${selectedEpisode.hypothesis} RESEARCH HYPOTHESIS`), node("h3", "", `${detail.symbol} — Opportunity History`));
    const facts = node("div", "opportunity-symbol-facts");
    [
      ["First observed", shortTime(selectedEpisode.origin_effective_at)],
      ["Research state", selectedEpisode.state_label],
      ["IPDA", detail.latest_ipda_location || "Unavailable"],
      ["Entry", "Not verified"],
    ].forEach(([label, value]) => {
      const fact = node("span", ""); fact.append(node("small", "", label), node("strong", "", value)); facts.append(fact);
    });
    header.append(identity, facts); target.append(header);

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

    const { selectEvidence } = renderMapComponent(target, detail, componentState, options);

    const timeline = node("section", "opportunity-event-timeline panel");
    const recordCount = timelineRows(detail).length;
    const timelineHeader = node("header", "opportunity-panel-heading"); timelineHeader.append(node("div", "", `Opportunity Event Timeline (${detail.symbol})`), node("span", "", `${recordCount} records`));
    const timelineWrap = renderTimeline(detail, selectEvidence, componentState.timelineExpanded);
    timeline.append(timelineHeader, timelineWrap);
    if (recordCount > 8) {
      const expansion = node("button", "opportunity-timeline-toggle", componentState.timelineExpanded ? "Show first 8 events" : `View all ${recordCount} events`);
      expansion.type = "button";
      expansion.setAttribute("aria-expanded", String(Boolean(componentState.timelineExpanded)));
      expansion.addEventListener("click", () => {
        componentState.timelineExpanded = !componentState.timelineExpanded;
        const rows = timelineRows(detail);
        const body = timelineBody(componentState.timelineExpanded ? rows : rows.slice(0, 8), selectEvidence);
        timelineWrap.querySelector("tbody").replaceWith(body);
        timelineWrap.classList.toggle("expanded", componentState.timelineExpanded);
        expansion.textContent = componentState.timelineExpanded ? "Show first 8 events" : `View all ${recordCount} events`;
        expansion.setAttribute("aria-expanded", String(componentState.timelineExpanded));
      });
      timeline.append(expansion);
    }
    target.append(timeline);
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
    const title = node("div", ""); title.append(node("h2", "", "Group Evolution"), node("p", "", `Location Flow × Structural Transitions × Event Activity · ${report.window?.key || "Selected window"}`));
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
    [["lower", "↓", fs.lower || 0, "Moved lower"], ["higher", "↑", fs.higher || 0, "Moved higher"], ["unchanged", "—", fs.unchanged || 0, "Unchanged"], ["unavailable", "?", fs.unavailable || 0, "Unavailable"]].forEach(([tone, icon, count, label]) => { const item = node("span", tone); item.append(node("i", "", icon), node("b", "", String(count)), node("em", "", label)); flowSummary.append(item); });
    flowLayout.append(movement, flowSummary); flowCard.append(flowLayout);

    const transitions = report.structural_transitions || {};
    const ts = transitions.summary || {};
    const transitionCard = node("article", "group-evolution-card");
    transitionCard.append(node("h3", "", "⇄ Structural Transitions"), node("p", "group-evolution-help", "Opposite-route MRZ activations requiring operator review."));
    const directions = node("div", "transition-directions");
    [["STR → BTD", ts.str_to_btd_unique_symbols || 0, "btd"], ["BTD → STR", ts.btd_to_str_unique_symbols || 0, "str"]].forEach(([label, count, tone]) => {
      const card = node("div", `transition-direction ${tone}`); card.append(node("strong", "", label), node("span", "", `${count} / ${report.group?.member_count || 0} detected`)); directions.append(card);
    });
    transitionCard.append(directions);
    if (ts.event_count) {
      const statuses = node("div", "transition-statuses");
      [["Detected", ts.event_count || 0], ["Pending Review", ts.pending || 0], ["Promoted", ts.promoted || 0], ["Retained Primary", ts.retained_primary || 0]].forEach(([label, count]) => { const item = node("span", ""); item.append(node("b", "", label), node("strong", "", count)); statuses.append(item); });
      transitionCard.append(statuses, node("small", "transition-caution", "ⓘ Detected transition ≠ confirmed trend reversal. Primary changes only on operator approval."));
    } else {
      const empty = node("div", "transition-empty-state"); empty.append(node("strong", "", "No structural transitions in the selected period."), node("span", "", "Opposite-route MRZ activations will appear here when detected.")); transitionCard.append(empty);
    }
    grid.append(flowCard, transitionCard); section.append(grid);

    const activity = report.activity || {}; const activityRecords = activity.records || [];
    const activationRecords = activityRecords.filter((item) => item.tracker === "mrz" && item.event_type === "MRZ_ACTIVATED");
    const migrationRecords = activityRecords.filter((item) => item.tracker === "mrz" && item.event_type === "MRZ_MIGRATED");
    const migrationBreakdown = migrationDirectionBreakdown(
      activityRecords,
      report.directional?.mrz_migrations || {},
    );
    const nearMissRecords = activityRecords.filter((item) => item.tracker === "near_miss");
    const eventActivity = node("section", "group-event-activity");
    const activityIntro = node("div", "group-event-intro"); activityIntro.append(node("h3", "", `Event Activity (${report.window?.key || "window"})`), node("p", "", "Key canonical structural events across group members.")); eventActivity.append(activityIntro);
    const activityMetrics = node("div", "group-event-metrics");
    [["near", "Near Miss", activity.summary?.near_miss_episode_count || 0, "Canonical episodes in period"], ["activation", "MRZ Activation", activationRecords.length, "New canonical MRZ established"]].forEach(([tone, label, count, description]) => { const metric = node("article", tone); metric.append(node("span", "", label), node("strong", "", String(count)), node("small", "", description)); activityMetrics.append(metric); });
    const migrationDetail = node("section", "migration-direction-detail"); migrationDetail.hidden = true; migrationDetail.id = `migrationDirectionDetail-${report.group?.id || "group"}`;
    const migrationButtons = [];
    const renderMigrationDetail = (direction) => {
      const labels = { higher: "Higher", lower: "Lower", unchanged: "Unchanged", unknown: "Unknown" };
      const events = migrationBreakdown.categories[direction] || [];
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
          node("td", `migration-direction ${direction}`, labels[direction]),
        );
        const linkCell = node("td", ""); linkCell.append(evidence); row.append(linkCell); body.append(row);
      });
      if (!events.length) { const row = node("tr", ""); const empty = node("td", "migration-direction-empty", `No ${labels[direction].toLowerCase()} migrations in this period.`); empty.colSpan = 8; row.append(empty); body.append(row); }
      table.append(head, body); wrap.append(table); migrationDetail.replaceChildren(detailHeading, wrap); migrationDetail.hidden = false;
      migrationButtons.forEach((button) => button.setAttribute("aria-expanded", String(button.dataset.direction === direction)));
    };
    const migrationMetric = node("article", "migration"); migrationMetric.append(node("span", "", "MRZ Migration"), node("strong", "", String(migrationRecords.length)), node("small", "", "Canonical migration events"));
    const breakdown = node("div", "migration-direction-breakdown");
    const directionItems = [["higher", "↑", "Higher"], ["lower", "↓", "Lower"], ["unchanged", "—", "Unchanged"]];
    if (migrationBreakdown.counts.unknown) directionItems.push(["unknown", "?", "Unknown"]);
    directionItems.forEach(([direction, icon, label]) => { const button = node("button", direction, ""); button.type = "button"; button.dataset.direction = direction; button.setAttribute("aria-controls", migrationDetail.id); button.setAttribute("aria-expanded", "false"); button.setAttribute("aria-label", `Inspect ${migrationBreakdown.counts[direction]} ${label.toLowerCase()} MRZ migrations`); button.append(node("i", "", icon), node("span", "", label), node("b", "", String(migrationBreakdown.counts[direction]))); button.addEventListener("click", () => renderMigrationDetail(direction)); migrationButtons.push(button); breakdown.append(button); });
    migrationMetric.append(breakdown); activityMetrics.append(migrationMetric); eventActivity.append(activityMetrics);
    const recentPanel = node("div", "group-recent-events"); const recentHead = node("header", ""); recentHead.append(node("strong", "", "Recent Events")); const allEvents = node("a", "", "View All Events →"); allEvents.href = options.eventsUrl || "/mrz/events"; recentHead.append(allEvents); recentPanel.append(recentHead);
    const recentList = node("ul", "");
    const recentRecords = [...nearMissRecords, ...activationRecords, ...migrationRecords].sort((left, right) => parseTime(right.occurred_at) - parseTime(left.occurred_at)).slice(0, 3);
    const eventLabel = (item) => item.event_type === "MRZ_ACTIVATED" ? "MRZ Activation" : item.event_type === "MRZ_MIGRATED" ? "MRZ Migration" : item.event_type === "NEAR_MISS_EPISODE_ENDED" ? "Near Miss Ended" : "Near Miss";
    recentRecords.forEach((item) => { const row = node("li", ""); const identity = node("span", "group-recent-event-identity"); identity.append(node("b", "", item.symbol), node("em", item.tracker === "near_miss" ? "near" : item.event_type === "MRZ_ACTIVATED" ? "activation" : "migration", eventLabel(item))); const open = node("a", "", "Open →"); open.href = item.tracker === "near_miss" ? `/mrz/symbols?symbol=${encodeURIComponent(item.symbol)}` : `/mrz/events?symbol=${encodeURIComponent(item.symbol)}&event=${encodeURIComponent(item.source_event_id || item.id)}`; row.append(identity, node("time", "", exactTime(item.occurred_at)), open); recentList.append(row); });
    if (!recentRecords.length) recentList.append(node("li", "group-event-empty", "No Near Miss, activation or migration events in this period.")); recentPanel.append(recentList); eventActivity.append(recentPanel); section.append(eventActivity, migrationDetail);

    if ((transitions.contributors || []).length) {
      const tableWrap = node("div", "group-transition-table-wrap"); tableWrap.append(node("h3", "", "Contributing Symbols — Structural Transition Candidates"));
      const table = node("table", "group-transition-table"); const head = node("thead", ""); head.innerHTML = "<tr><th>Symbol</th><th>Latest IPDA Movement</th><th>Opposite MRZ</th><th>Primary Hypothesis</th><th>Review Status</th><th>Evidence</th></tr>"; const body = node("tbody", "");
      transitions.contributors.forEach((item) => {
        const row = node("tr", "");
        const evidence = node("button", "group-transition-open", "Open →"); evidence.type = "button"; evidence.addEventListener("click", () => options.onOpenTransition?.(item));
        const latestMovement = item.latest_ipda_movement;
        const movementLabel = latestMovement?.start_location_label && latestMovement?.current_location_label
          ? `${latestMovement.start_location_label} → ${latestMovement.current_location_label}`
          : "Unavailable";
        const primaryCell = node("td", ""); primaryCell.append(node("b", `route ${String(item.current_primary_hypothesis).toLowerCase()}`, item.current_primary_hypothesis));
        const statusCell = node("td", ""); statusCell.append(node("span", `transition-review-status ${String(item.status).toLowerCase()}`, item.status === "PENDING" ? "Pending Review" : item.status.replaceAll("_", " ")));
        const evidenceCell = node("td", ""); evidenceCell.append(evidence);
        row.append(node("td", "", item.symbol), node("td", "", movementLabel), node("td", "", `${item.previous_hypothesis} → ${item.candidate_hypothesis}`), primaryCell, statusCell, evidenceCell); body.append(row);
      });
      table.append(head, body); tableWrap.append(table); section.append(tableWrap);
    }
    target.append(section);
  }

  function renderGroup(target, payload, options = {}) {
    target.replaceChildren();
    const summary = payload.groups[0] || { candidates: [] };
    if (options.groupEvolution) renderGroupEvolution(target, options.groupEvolution, options);
    const candidatePanel = node("section", "opportunity-candidates panel");
    renderCandidateTable(candidatePanel, summary, options.onSelectSymbol || (() => {}), options);
    target.append(candidatePanel);
  }

  async function renderSymbol(target, symbol, options = {}) {
    target.replaceChildren(node("section", "panel opportunity-loading", `Reconstructing ${symbol}…`));
    let fullDetail = null;
    const componentState = {
      cursors: [], cursorIndex: 0, replayTimestamp: null, rangeDays: [0, 30, 90].includes(Number(options.initialRangeDays)) ? Number(options.initialRangeDays) : 0,
      playing: false, playTimer: null, sliderTimer: null, loadCursor: null,
      selectedEventId: null, timelineExpanded: false, detailsCollapsed: Boolean(options.detailsCollapsed), resizeObserver: null,
    };
    const loadSymbol = async (symbol, asKnownAt = null) => {
      const params = new URLSearchParams(); if (asKnownAt) params.set("as_known_at", asKnownAt);
      const response = await globalObject.fetch(`/api/opportunities/${encodeURIComponent(symbol)}${params.size ? `?${params}` : ""}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Opportunity history is unavailable.");
      const detail = await response.json();
      if (!asKnownAt || !fullDetail || fullDetail.symbol !== symbol) {
        fullDetail = detail;
        componentState.cursors = collectReplayCursors(detail);
        componentState.cursorIndex = componentState.cursors.length - 1;
        componentState.replayTimestamp = componentState.cursors.at(-1);
      } else {
        componentState.replayTimestamp = asKnownAt;
        componentState.cursorIndex = cursorIndexAtOrBefore(componentState.cursors, asKnownAt);
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
    renderSymbol,
    timelineRows,
    timeBounds,
  };
})(window);
