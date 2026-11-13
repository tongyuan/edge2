(function initializeOpportunityMap(globalObject) {
  "use strict";

  const STAGE_ORDER = {
    REASSESSMENT: 6,
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
    higher: "#22C55E",
    lower: "#F87171",
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
    link.append(icon, node("span", "", "Evidence"));
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
      ...(detail.pressure_observations || []),
    ].forEach((item) => { if (item.known_at) values.add(item.known_at); });
    return [...values].sort((left, right) => parseTime(left) - parseTime(right));
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
      (detail.pressure_observations || []).forEach((item) => values.push(parseTime(item.effective_at)));
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
      pressure: (detail.pressure_observations || []).filter((item) => within(item.effective_at)),
    };
  }

  function priceBounds(items) {
    const values = [];
    const add = (value) => {
      const numeric = Number(value);
      if (Number.isFinite(numeric)) values.push(numeric);
    };
    items.observations.forEach((item) => add(item.price));
    items.pressure.forEach((item) => add(item.price));
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

  function drawCombinedMarker(context, xPosition, yPosition, direction, routeColor, pressureColor) {
    drawTriangle(context, xPosition, yPosition, direction, 8, "#0b1119", pressureColor, 2.5);
    context.beginPath();
    context.arc(xPosition, yPosition, 3, 0, Math.PI * 2);
    context.fillStyle = routeColor;
    context.fill();
    context.strokeStyle = "#0b1119";
    context.lineWidth = 1;
    context.stroke();
  }

  function drawPressureCircle(context, xPosition, yPosition, direction) {
    context.beginPath();
    context.arc(xPosition, yPosition, 6.5, 0, Math.PI * 2);
    context.fillStyle = direction === "LOWER" ? COLORS.lower : COLORS.higher;
    context.fill();
    context.strokeStyle = "#0b1119";
    context.lineWidth = 2;
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
    for (let index = 0; index <= 6; index += 1) {
      const ratio = index / 6;
      const xPosition = margin.left + ratio * plotWidth;
      const time = new Date(times.minimum + ratio * (times.maximum - times.minimum));
      context.strokeStyle = "rgba(34,50,66,.48)";
      context.beginPath(); context.moveTo(xPosition, margin.top); context.lineTo(xPosition, height - margin.bottom); context.stroke();
      context.fillStyle = COLORS.text;
      context.textAlign = index === 0 ? "left" : index === 6 ? "right" : "center";
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
    });

    const hits = [];
    const pressureByIdentity = new Map(items.pressure.map((item) => [eventIdentity(item), item]));
    const combinedPressureIds = new Set();
    items.observations.forEach((item) => {
      const xPosition = x(item.effective_at);
      const yPosition = y(item.price);
      const identity = eventIdentity(item);
      const pressureItem = pressureByIdentity.get(identity);
      const routeColor = item.route === "BTD" ? COLORS.btd : COLORS.str;
      const visualItem = pressureItem
        ? {
            ...item,
            ...pressureItem,
            route: item.route,
            source_tracker: `${item.source_tracker} + ${pressureItem.source_tracker}`,
            event_type: item.event_type,
            direction: pressureItem.direction,
            _classifications: [item.route, `${pressureItem.direction} Pressure`],
          }
        : item;
      if (pressureItem && options.pressureStyle === "circle") {
        combinedPressureIds.add(identity);
        drawPressureCircle(context, xPosition, yPosition, pressureItem.direction);
      } else if (pressureItem) {
        combinedPressureIds.add(identity);
        drawCombinedMarker(
          context,
          xPosition,
          yPosition,
          pressureItem.direction,
          routeColor,
          pressureItem.direction === "LOWER" ? COLORS.lower : COLORS.higher,
        );
      } else {
        context.beginPath(); context.arc(xPosition, yPosition, 5, 0, Math.PI * 2);
        context.fillStyle = routeColor;
        context.fill();
        context.strokeStyle = "#0b1119";
        context.lineWidth = 1.5;
        context.stroke();
      }
      if (eventIdentity(item) === selectedEventId) {
        context.beginPath(); context.arc(xPosition, yPosition, 10, 0, Math.PI * 2);
        context.strokeStyle = "#ffffff"; context.lineWidth = 2; context.stroke();
      }
      hits.push({ x: xPosition, y: yPosition, radius: 12, item: visualItem });
    });
    items.pressure.forEach((item) => {
      if (combinedPressureIds.has(eventIdentity(item))) return;
      const xPosition = x(item.effective_at);
      const yPosition = y(item.price);
      if (options.pressureStyle === "circle") {
        drawPressureCircle(context, xPosition, yPosition, item.direction);
      } else if (item.route === "BTD" || item.route === "STR") {
        drawCombinedMarker(
          context,
          xPosition,
          yPosition,
          item.direction,
          item.route === "BTD" ? COLORS.btd : COLORS.str,
          item.direction === "LOWER" ? COLORS.lower : COLORS.higher,
        );
      } else {
        drawTriangle(context, xPosition, yPosition, item.direction, 8, item.direction === "LOWER" ? COLORS.lower : COLORS.higher);
      }
      if (eventIdentity(item) === selectedEventId) {
        context.beginPath(); context.arc(xPosition, yPosition, 12, 0, Math.PI * 2);
        context.strokeStyle = "#ffffff"; context.lineWidth = 2; context.stroke();
      }
      hits.push({ x: xPosition, y: yPosition, radius: 13, item });
    });
    canvas._opportunityHits = hits;
    canvas.onclick = (event) => {
      const box = canvas.getBoundingClientRect();
      const clickX = (event.clientX - box.left) * (canvas.width / box.width);
      const clickY = (event.clientY - box.top) * (canvas.height / box.height);
      const selected = hits
        .map((hit) => ({ hit, distance: Math.hypot(hit.x - clickX, hit.y - clickY) }))
        .filter((candidate) => candidate.distance <= candidate.hit.radius)
        .sort((left, right) => left.distance - right.distance)[0];
      if (selected) onSelect(selected.hit.item);
    };
  }

  function renderLegend(options = {}) {
    const legend = node("div", "opportunity-map-legend");
    if (options.pressureStyle === "circle") legend.classList.add("circular-pressure");
    [
      ["btd", "BTD observation"], ["str", "STR observation"],
      ["mrz", "MRZ zone"], ["near", "Near Miss candidate"],
      ["lower", "Lower Pressure"], ["higher", "Higher Pressure"],
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
      [detail.pressure_observations || [], "Pressure"],
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
        || (item.current_pressure_state ? `${item.current_pressure_label} ${item.recent_higher_observation_count}/${item.recent_lower_observation_count}` : "Canonical observed evidence");
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

  function renderOpportunityWorkspace(target, detail, componentState, options = {}) {
    target.replaceChildren();
    const selectedEpisode = detail.episodes.find((item) => item.episode_id === detail.selected_episode_id) || detail.episodes[0];
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
    headerActions.append(backToGroup, renderCanonicalEvidenceLink(detail, options));
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
    const minimumReplayTime = parseTime(componentState.cursors[0]);
    const maximumReplayTime = parseTime(componentState.cursors.at(-1));
    const currentReplayTime = parseTime(componentState.replayTimestamp || detail.as_known_at || componentState.cursors.at(-1));
    replaySlider.min = String(minimumReplayTime);
    replaySlider.max = String(maximumReplayTime);
    replaySlider.step = "any";
    replaySlider.value = String(Math.max(minimumReplayTime, Math.min(maximumReplayTime, currentReplayTime)));
    replaySlider.disabled = componentState.cursors.length <= 1;
    const selectedTime = node("output", "opportunity-replay-selected", exactTime(new Date(Number(replaySlider.value)).toISOString()));
    selectedTime.htmlFor = replaySlider.id = `opportunityReplaySlider-${detail.symbol}`;
    const cursorAtOrBefore = (timestamp) => {
      let index = 0;
      componentState.cursors.forEach((value, candidate) => { if (parseTime(value) <= timestamp) index = candidate; });
      return index;
    };
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
      const timestamp = Number(replaySlider.value);
      componentState.cursorIndex = cursorAtOrBefore(timestamp);
      componentState.replayTimestamp = new Date(timestamp).toISOString();
      componentState.loadCursor(componentState.replayTimestamp);
    };
    replaySlider.addEventListener("input", () => {
      const timestamp = Number(replaySlider.value);
      selectedTime.textContent = exactTime(new Date(timestamp).toISOString());
      componentState.cursorIndex = cursorAtOrBefore(timestamp);
      componentState.replayTimestamp = new Date(timestamp).toISOString();
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

    const mapPanel = node("section", "opportunity-map-panel panel");
    const mapHeader = node("header", "opportunity-panel-heading");
    const title = node("div", ""); title.append(node("strong", "", "Opportunity Map (Time × Price)"), node("small", "", "Actual event time · linear instrument price"));
    const mapTools = node("div", "opportunity-map-tools");
    const ranges = node("div", "opportunity-range-controls");
    [[0, "All"], [90, "90D"], [30, "30D"]].forEach(([days, label]) => {
      const button = node("button", "", label); button.type = "button"; button.setAttribute("aria-pressed", String(componentState.rangeDays === days));
      button.addEventListener("click", () => { componentState.rangeDays = days; renderOpportunityWorkspace(target, detail, componentState, options); }); ranges.append(button);
    });
    const maximize = node("button", "opportunity-maximize-button", componentState.maximized ? "Restore" : "Maximize");
    maximize.type = "button";
    maximize.setAttribute("aria-pressed", String(Boolean(componentState.maximized)));
    maximize.setAttribute("aria-label", componentState.maximized ? "Restore Opportunity Map" : "Maximize Opportunity Map");
    const setMaximized = (value) => {
      componentState.maximized = value;
      mapPanel.classList.toggle("maximized", value);
      globalObject.document.body.classList.toggle("opportunity-map-maximized", value);
      maximize.textContent = value ? "Restore" : "Maximize";
      maximize.setAttribute("aria-pressed", String(value));
      maximize.setAttribute("aria-label", value ? "Restore Opportunity Map" : "Maximize Opportunity Map");
      globalObject.requestAnimationFrame(() => drawChart(canvas, detail, componentState.rangeDays, componentState.selectedEventId, selectEvidence, { pressureStyle: "circle" }));
    };
    maximize.addEventListener("click", () => setMaximized(!componentState.maximized));
    mapTools.append(ranges, maximize);
    mapHeader.append(title, mapTools); mapPanel.append(mapHeader);
    const scroll = node("div", "opportunity-chart-scroll");
    const canvas = node("canvas", "opportunity-map-canvas"); canvas.width = 1120; canvas.height = 280; canvas.setAttribute("aria-label", `Time-price opportunity map for ${detail.symbol}`); canvas.tabIndex = 0;
    scroll.append(canvas); mapPanel.append(scroll, renderLegend({ pressureStyle: "circle" }));
    const details = node("div", "opportunity-selected-event");
    const previouslySelected = timelineRows(detail).find((item) => eventIdentity(item) === componentState.selectedEventId) || null;
    mapPanel.append(details); renderEventDetails(details, previouslySelected);
    target.append(mapPanel);
    const selectEvidence = (item) => {
      componentState.selectedEventId = eventIdentity(item);
      renderEventDetails(details, item);
      drawChart(canvas, detail, componentState.rangeDays, componentState.selectedEventId, selectEvidence, { pressureStyle: "circle" });
      target.querySelectorAll(".opportunity-timeline-table tr[data-event-id]").forEach((row) => row.classList.toggle("selected", row.dataset.eventId === componentState.selectedEventId));
      mapPanel.scrollIntoView({ block: "nearest", behavior: "smooth" });
    };
    if (componentState.escapeHandler) globalObject.document.removeEventListener("keydown", componentState.escapeHandler);
    componentState.escapeHandler = (event) => { if (event.key === "Escape" && componentState.maximized) setMaximized(false); };
    globalObject.document.addEventListener("keydown", componentState.escapeHandler);
    if (componentState.maximized) setMaximized(true);
    globalObject.requestAnimationFrame(() => drawChart(canvas, detail, componentState.rangeDays, componentState.selectedEventId, selectEvidence, { pressureStyle: "circle" }));

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
    head.innerHTML = "<tr><th>Symbol</th><th>Hypothesis</th><th>IPDA location</th><th>MRZ levels</th><th>Current pressure</th><th>Opportunity state</th><th>Latest development</th><th aria-label=\"Open\"></th></tr>";
    const body = node("tbody", "");
    summary.candidates
      .slice()
      .sort((left, right) => (STAGE_ORDER[right.state] || 0) - (STAGE_ORDER[left.state] || 0) || left.symbol.localeCompare(right.symbol))
      .forEach((candidate) => {
        const row = node("tr", ""); row.tabIndex = 0;
        const symbol = node("td", "opportunity-candidate-symbol", candidate.symbol);
        const hypothesis = node("td", ""); hypothesis.append(node("b", `route ${candidate.hypothesis.toLowerCase()}`, candidate.hypothesis));
        const location = node("td", "", candidate.ipda_location || "Unavailable");
        const mrz = node("td", "", candidate.mrz ? `${price(candidate.mrz.lower)}–${price(candidate.mrz.upper)}` : "No active MRZ");
        const pressure = node("td", candidate.current_pressure?.state === "LOWER" ? "lower" : candidate.current_pressure?.state === "HIGHER" ? "higher" : "", candidate.current_pressure ? `${candidate.current_pressure.label} ${candidate.current_pressure.higher}/${candidate.current_pressure.lower}` : "Neutral");
        const stage = node("td", ""); stage.append(node("span", `opportunity-stage ${stageClass(candidate.state)}`, candidate.state_label));
        const latest = node("td", "opportunity-candidate-development", `${candidate.latest_event_type} · ${shortTime(candidate.latest_event_at)}`);
        const open = node("td", "opportunity-candidate-open", "Open →");
        row.append(symbol, hypothesis, location, mrz, pressure, stage, latest, open);
        row.addEventListener("click", () => onSelect(candidate.symbol));
        row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(candidate.symbol); } });
        body.append(row);
      });
    if (!summary.candidates.length) { const row = node("tr", ""); const cell = node("td", "opportunity-empty", "No canonical opportunity context is available for this group."); cell.colSpan = 8; row.append(cell); body.append(row); }
    table.append(head, body); wrap.append(table); target.append(wrap);
  }

  function renderGroup(target, payload, options = {}) {
    target.replaceChildren();
    const summary = payload.groups[0] || { candidates: [] };
    const overview = node("section", "opportunity-overview");
    const cards = [
      ["Developing context", summary.context_or_developing_count || 0, "No invented count threshold", "context"],
      ["Near Miss", summary.near_miss_count || 0, "Canonical candidates", "near"],
      ["Structure established", summary.structure_established_count || 0, "Authoritative MRZ", "structure"],
      ["Needs reassessment", summary.reassessment_count || 0, "Material context change", "reassessment"],
    ];
    cards.forEach(([label, value, detail, tone]) => {
      const card = node("article", `opportunity-overview-card ${tone}`); card.append(node("strong", "", value), node("span", "", label), node("small", "", detail)); overview.append(card);
    });
    target.append(overview);
    const candidatePanel = node("section", "opportunity-candidates panel");
    renderCandidateTable(candidatePanel, summary, options.onSelectSymbol || (() => {}), options);
    target.append(candidatePanel);
  }

  async function renderSymbol(target, symbol, options = {}) {
    target.replaceChildren(node("section", "panel opportunity-loading", `Reconstructing ${symbol}…`));
    let fullDetail = null;
    const componentState = {
      cursors: [], cursorIndex: 0, replayTimestamp: null, rangeDays: 0,
      playing: false, playTimer: null, sliderTimer: null, loadCursor: null,
      selectedEventId: null, timelineExpanded: false, maximized: false, escapeHandler: null,
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
        componentState.cursorIndex = componentState.cursors.reduce((current, item, index) => (parseTime(item) <= parseTime(asKnownAt) ? index : current), 0);
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
    comparisonTimeBounds,
    drawChart,
    eventIdentity,
    proportionalPosition,
    renderEventDetails,
    renderCanonicalEvidenceLink,
    renderGroup,
    renderLegend,
    renderSymbol,
    timelineRows,
    timeBounds,
  };
})(window);
