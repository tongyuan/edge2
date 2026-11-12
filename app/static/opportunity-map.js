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
    btd: "#22d7bd",
    str: "#a879ef",
    higher: "#36d6c1",
    lower: "#ff6873",
    mrz: "#18d9a5",
    near: "#ae82ef",
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

  function rangeText(item) {
    if (!item?.lower_bound || !item?.upper_bound) return "—";
    return `${price(item.lower_bound)}–${price(item.upper_bound)}`;
  }

  function stageClass(value) {
    return String(value || "context").toLowerCase().replaceAll("_", "-");
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

  function drawChart(canvas, detail, rangeDays, onSelect) {
    const context = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    const margin = { left: 68, right: 26, top: 30, bottom: 48 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const times = timeBounds(detail, rangeDays);
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
      context.fillText(price(priceValue), margin.left - 10, yPosition + 4);
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

    items.near.forEach((item) => {
      const start = Math.max(margin.left, x(item.known_at));
      const end = Math.min(width - margin.right, x(item.ended_at || detail.as_known_at));
      const top = y(item.upper_bound);
      const bottom = y(item.lower_bound);
      context.save();
      context.strokeStyle = COLORS.near;
      context.setLineDash([6, 4]);
      context.strokeRect(start, top, Math.max(2, end - start), Math.max(2, bottom - top));
      context.restore();
    });
    items.mrz.forEach((item) => {
      const start = Math.max(margin.left, x(item.known_at));
      const end = Math.min(width - margin.right, x(item.ended_known_at || detail.as_known_at));
      const top = y(item.upper_bound);
      const bottom = y(item.lower_bound);
      context.fillStyle = "rgba(24,217,165,.14)";
      context.fillRect(start, top, Math.max(2, end - start), Math.max(3, bottom - top));
      context.strokeStyle = COLORS.mrz;
      context.strokeRect(start, top, Math.max(2, end - start), Math.max(3, bottom - top));
      context.save();
      context.setLineDash([5, 4]);
      context.strokeStyle = "rgba(24,217,165,.45)";
      [item.lower_migration_boundary, item.upper_migration_boundary].forEach((boundary) => {
        context.beginPath(); context.moveTo(start, y(boundary)); context.lineTo(end, y(boundary)); context.stroke();
      });
      context.restore();
    });

    const hits = [];
    items.observations.forEach((item) => {
      const xPosition = x(item.effective_at);
      const yPosition = y(item.price);
      context.beginPath(); context.arc(xPosition, yPosition, 4, 0, Math.PI * 2);
      context.fillStyle = item.route === "BTD" ? COLORS.btd : COLORS.str;
      context.fill();
      hits.push({ x: xPosition, y: yPosition, radius: 10, item });
    });
    items.pressure.forEach((item) => {
      const xPosition = x(item.effective_at);
      const yPosition = y(item.price);
      context.beginPath(); context.arc(xPosition, yPosition, 7, 0, Math.PI * 2);
      context.fillStyle = item.direction === "LOWER" ? COLORS.lower : COLORS.higher;
      context.fill();
      context.strokeStyle = "#0b1119"; context.lineWidth = 2; context.stroke();
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

  function renderLegend() {
    const legend = node("div", "opportunity-map-legend");
    [
      ["btd", "BTD observation"], ["str", "STR observation"],
      ["mrz", "MRZ zone"], ["near", "Near Miss candidate"],
      ["lower", "Lower Pressure"], ["higher", "Higher Pressure"],
      ["ote", "OTE unavailable"],
    ].forEach(([tone, label]) => {
      const item = node("span", tone);
      item.append(node("i", ""), node("b", "", label));
      legend.append(item);
    });
    return legend;
  }

  function renderEventDetails(target, item) {
    target.replaceChildren();
    if (!item) {
      target.append(node("p", "", "Select a chart marker to inspect its canonical evidence."));
      return;
    }
    const heading = node("div", "opportunity-selected-event-heading");
    heading.append(
      node("strong", "", `${item.source_tracker} · ${item.event_type}`),
      node("span", "", item.canonical_event_id),
    );
    const grid = node("dl", "opportunity-selected-event-grid");
    [
      ["Event time", exactTime(item.effective_at)],
      ["First known", exactTime(item.known_at)],
      ["Price", price(item.price)],
      ["Bounds", rangeText(item)],
      ["Route", item.route || item.mrz_route || "—"],
      ["IPDA location", item.ipda_location_label || item.structural_location || "—"],
      ["MRZ lifecycle", item.mrz_lifecycle_event_id || "—"],
      ["Relationship", item.relationship || "Canonical chart evidence"],
    ].forEach(([term, value]) => {
      grid.append(node("dt", "", term), node("dd", "", value));
    });
    target.append(heading, grid);
  }

  function renderTimeline(detail) {
    const wrap = node("div", "opportunity-timeline-wrap");
    const table = node("table", "opportunity-timeline-table");
    const head = node("thead", "");
    head.innerHTML = "<tr><th>Event time</th><th>Known at</th><th>Tracker</th><th>Event</th><th>Price / zone</th><th>State after</th></tr>";
    const rows = [
      ...(detail.observations || []),
      ...(detail.near_miss_events || []),
      ...(detail.mrz_lifecycles || []),
      ...(detail.pressure_observations || []),
    ].sort((left, right) => parseTime(left.effective_at) - parseTime(right.effective_at) || parseTime(left.known_at) - parseTime(right.known_at));
    const body = node("tbody", "");
    rows.forEach((item) => {
      const row = node("tr", "");
      const state = item.current_pressure_state
        ? `${item.current_pressure_label} ${item.recent_higher_observation_count}/${item.recent_lower_observation_count}`
        : "—";
      [
        exactTime(item.effective_at), exactTime(item.known_at), item.source_tracker,
        item.event_type, item.price ? price(item.price) : rangeText(item), state,
      ].forEach((value) => row.append(node("td", "", value)));
      body.append(row);
    });
    if (!rows.length) {
      const row = node("tr", ""); const cell = node("td", "opportunity-empty", "No evidence is known at this replay cursor."); cell.colSpan = 6; row.append(cell); body.append(row);
    }
    table.append(head, body); wrap.append(table); return wrap;
  }

  function renderAssessment(detail) {
    const panel = node("section", "opportunity-assessment panel");
    const header = node("header", "opportunity-panel-heading");
    header.append(node("div", "", "Opportunity Assessment"), node("span", "", "Evidence-derived"));
    panel.append(header);
    const list = node("dl", "opportunity-assessment-list");
    [
      ["What happened?", detail.assessment.what_happened],
      ["What changed?", detail.assessment.what_changed],
      ["What evidence conflicts?", detail.assessment.conflicting_evidence],
      ["What should be monitored next?", detail.assessment.next_condition],
      ["Is an entry verified?", detail.assessment.entry_message],
    ].forEach(([term, value], index) => {
      const dt = node("dt", "", term);
      const dd = node("dd", index === 4 ? "entry-not-verified" : "", value);
      list.append(dt, dd);
    });
    panel.append(list); return panel;
  }

  function renderOpportunityWorkspace(target, detail, componentState) {
    target.replaceChildren();
    const selectedEpisode = detail.episodes.find((item) => item.episode_id === detail.selected_episode_id) || detail.episodes[0];
    const header = node("header", "opportunity-symbol-header");
    const identity = node("div", "");
    identity.append(node("p", "", `${selectedEpisode.hypothesis} RESEARCH HYPOTHESIS`), node("h3", "", `${detail.symbol} — Opportunity History`));
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

    const mapPanel = node("section", "opportunity-map-panel panel");
    const mapHeader = node("header", "opportunity-panel-heading");
    const title = node("div", ""); title.append(node("strong", "", "Opportunity Map (Time × Price)"), node("small", "", "Actual event time · linear instrument price"));
    const ranges = node("div", "opportunity-range-controls");
    [[0, "All"], [90, "90D"], [30, "30D"]].forEach(([days, label]) => {
      const button = node("button", "", label); button.type = "button"; button.setAttribute("aria-pressed", String(componentState.rangeDays === days));
      button.addEventListener("click", () => { componentState.rangeDays = days; renderOpportunityWorkspace(target, detail, componentState); }); ranges.append(button);
    });
    mapHeader.append(title, ranges); mapPanel.append(mapHeader);
    const scroll = node("div", "opportunity-chart-scroll");
    const canvas = node("canvas", "opportunity-map-canvas"); canvas.width = 1120; canvas.height = 460; canvas.setAttribute("aria-label", `Time-price opportunity map for ${detail.symbol}`); canvas.tabIndex = 0;
    scroll.append(canvas); mapPanel.append(scroll, renderLegend());
    const details = node("div", "opportunity-selected-event");
    mapPanel.append(details); renderEventDetails(details, null);
    target.append(mapPanel);
    globalObject.requestAnimationFrame(() => drawChart(canvas, detail, componentState.rangeDays, (item) => renderEventDetails(details, item)));

    const replay = node("section", "opportunity-replay panel");
    const replayHeading = node("header", "opportunity-panel-heading");
    const replayTitle = node("div", ""); replayTitle.append(node("strong", "", "Historical Replay — As Known At"), node("small", "", "Future-known evidence is hidden"));
    const controls = node("div", "opportunity-replay-controls");
    const previous = node("button", "quiet-button", "Previous"); previous.type = "button";
    const play = node("button", "primary-button", componentState.playing ? "Pause" : "Play"); play.type = "button";
    const next = node("button", "quiet-button", "Next"); next.type = "button";
    const latest = node("button", "quiet-button", "Latest"); latest.type = "button";
    const select = node("select", "");
    componentState.cursors.forEach((value, index) => { const option = node("option", "", exactTime(value)); option.value = String(index); if (index === componentState.cursorIndex) option.selected = true; select.append(option); });
    const moveTo = (index) => {
      const bounded = Math.max(0, Math.min(componentState.cursors.length - 1, index));
      componentState.cursorIndex = bounded;
      componentState.loadCursor(componentState.cursors[bounded]);
    };
    previous.addEventListener("click", () => moveTo(componentState.cursorIndex - 1));
    next.addEventListener("click", () => moveTo(componentState.cursorIndex + 1));
    latest.addEventListener("click", () => moveTo(componentState.cursors.length - 1));
    select.addEventListener("change", () => moveTo(Number(select.value)));
    play.addEventListener("click", () => {
      componentState.playing = !componentState.playing;
      if (!componentState.playing) { globalObject.clearTimeout(componentState.playTimer); renderOpportunityWorkspace(target, detail, componentState); return; }
      const advance = () => {
        if (!componentState.playing) return;
        if (componentState.cursorIndex >= componentState.cursors.length - 1) componentState.cursorIndex = 0;
        else componentState.cursorIndex += 1;
        componentState.loadCursor(componentState.cursors[componentState.cursorIndex]).finally(() => {
          if (componentState.playing) componentState.playTimer = globalObject.setTimeout(advance, 900);
        });
      };
      advance();
    });
    controls.append(previous, play, next, latest, select); replayHeading.append(replayTitle, controls); replay.append(replayHeading);
    const track = node("div", "opportunity-replay-track");
    const progress = node("span", ""); progress.style.width = `${componentState.cursors.length <= 1 ? 100 : componentState.cursorIndex / (componentState.cursors.length - 1) * 100}%`; track.append(progress);
    replay.append(track, node("p", "opportunity-replay-note", `Visible evidence known by ${exactTime(detail.as_known_at)}. Event time and knowledge time remain separate.`)); target.append(replay);

    const bottom = node("div", "opportunity-bottom-grid");
    const timeline = node("section", "opportunity-event-timeline panel");
    const timelineHeader = node("header", "opportunity-panel-heading"); timelineHeader.append(node("div", "", `Opportunity Event Timeline (${detail.symbol})`), node("span", "", `${detail.observations.length + detail.near_miss_events.length + detail.mrz_lifecycles.length + detail.pressure_observations.length} records`)); timeline.append(timelineHeader, renderTimeline(detail));
    bottom.append(timeline, renderAssessment(detail)); target.append(bottom);
  }

  function renderCandidateList(target, summary, selectedSymbol, onSelect) {
    target.replaceChildren();
    const header = node("header", "opportunity-candidate-heading");
    header.append(node("div", "", "Symbol Candidates"), node("span", "", `${summary.candidates.length} hypotheses`)); target.append(header);
    const list = node("div", "opportunity-candidate-list");
    summary.candidates
      .slice()
      .sort((left, right) => (STAGE_ORDER[right.state] || 0) - (STAGE_ORDER[left.state] || 0) || left.symbol.localeCompare(right.symbol))
      .forEach((candidate) => {
        const button = node("button", `opportunity-candidate ${candidate.symbol === selectedSymbol ? "selected" : ""}`); button.type = "button";
        const top = node("span", "opportunity-candidate-top"); top.append(node("strong", "", candidate.symbol), node("b", `route ${candidate.hypothesis.toLowerCase()}`, candidate.hypothesis));
        const state = node("span", `opportunity-stage ${stageClass(candidate.state)}`, candidate.state_label);
        const evidence = node("small", "", `${candidate.ipda_location || "IPDA unavailable"} · ${candidate.latest_event_type}`);
        const monitor = node("em", "", candidate.next_observable_condition);
        button.append(top, state, evidence, monitor); button.addEventListener("click", () => onSelect(candidate.symbol)); list.append(button);
      });
    if (!summary.candidates.length) list.append(node("p", "opportunity-empty", "No canonical opportunity context is available for this group."));
    target.append(list);
  }

  async function renderGroup(target, payload) {
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
    const layout = node("div", "opportunity-workspace-layout");
    const candidatePanel = node("aside", "opportunity-candidates panel");
    const workspace = node("section", "opportunity-symbol-workspace");
    layout.append(candidatePanel, workspace); target.append(layout);
    if (!summary.candidates.length) { renderCandidateList(candidatePanel, summary, null, () => {}); workspace.append(node("section", "panel opportunity-empty", "Select a group with observable opportunity evidence.")); return; }
    let selectedSymbol = summary.candidates[0].symbol;
    let fullDetail = null;
    const componentState = { cursors: [], cursorIndex: 0, rangeDays: 0, playing: false, playTimer: null, loadCursor: null };
    const loadSymbol = async (symbol, asKnownAt = null) => {
      selectedSymbol = symbol;
      renderCandidateList(candidatePanel, summary, selectedSymbol, (next) => loadSymbol(next));
      workspace.replaceChildren(node("section", "panel opportunity-loading", `Reconstructing ${symbol}…`));
      const params = new URLSearchParams(); if (asKnownAt) params.set("as_known_at", asKnownAt);
      const response = await globalObject.fetch(`/api/opportunities/${encodeURIComponent(symbol)}${params.size ? `?${params}` : ""}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Opportunity history is unavailable.");
      const detail = await response.json();
      if (!asKnownAt || !fullDetail || fullDetail.symbol !== symbol) {
        fullDetail = detail;
        componentState.cursors = collectReplayCursors(detail);
        componentState.cursorIndex = componentState.cursors.length - 1;
      } else {
        componentState.cursorIndex = Math.max(0, componentState.cursors.findIndex((item) => item === asKnownAt));
      }
      componentState.loadCursor = (cursor) => loadSymbol(symbol, cursor).catch((error) => {
        workspace.replaceChildren(node("section", "panel opportunity-error", error.message));
      });
      renderOpportunityWorkspace(workspace, detail, componentState);
      return detail;
    };
    renderCandidateList(candidatePanel, summary, selectedSymbol, (symbol) => loadSymbol(symbol).catch((error) => workspace.replaceChildren(node("section", "panel opportunity-error", error.message))));
    await loadSymbol(selectedSymbol);
  }

  globalObject.edgeOpportunityMap = {
    collectReplayCursors,
    proportionalPosition,
    renderGroup,
    timeBounds,
  };
})(window);
