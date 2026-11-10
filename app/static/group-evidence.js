(function initializeGroupRadar(globalObject) {
  "use strict";

  const derive = globalObject.edgeWorkspaceDerivations;
  const state = {
    scope: derive.parseGroupEvidenceState(globalObject.location?.search || ""),
    overview: null,
    detail: null,
    groups: [],
    allSymbols: [],
    editingGroup: null,
    editorMembers: new Set(),
    requestId: 0,
    controller: null,
    lastSuccessful: new Map(),
    recentLoaded: false,
    search: "",
    mounted: false,
  };
  const $ = (selector) => globalObject.document.querySelector(selector);
  const text = (value, fallback = "—") => value === null || value === undefined || value === "" ? fallback : String(value);
  const titleCase = (value) => text(value, "Unavailable").replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

  function node(tag, className, content) {
    const element = globalObject.document.createElement(tag);
    if (className) element.className = className;
    if (content !== undefined) element.textContent = content;
    return element;
  }

  function exactTime(value) {
    if (!value) return "Unavailable";
    return globalObject.formatOperatorTimestampUtcMinus4?.(value) || new Date(value).toLocaleString();
  }

  function shortDate(value) {
    if (!value) return "—";
    return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  function operatorDate(value) {
    if (!value) return "—";
    const shifted = new Date(new Date(value).getTime() - (4 * 60 * 60 * 1000));
    return shifted.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });
  }

  function ratio(numerator, denominator) {
    if (!Number.isFinite(Number(numerator)) || !Number.isFinite(Number(denominator))) return "Unavailable";
    if (!Number(denominator)) return "0 / 0 — unavailable";
    return `${numerator} / ${denominator}`;
  }

  function percent(value, total) {
    return total > 0 ? Math.max(0, Math.min(100, Number(value) / Number(total) * 100)) : 0;
  }

  function updateUrl(updates, { replace = false } = {}) {
    const url = new URL(globalObject.location.href);
    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === undefined || value === "") url.searchParams.delete(key);
      else url.searchParams.set(key, String(value));
    });
    globalObject.history[replace ? "replaceState" : "pushState"]({}, "", url);
    state.scope = derive.parseGroupEvidenceState(url.search);
  }

  function canonicalScopeUrl(extra = {}) {
    return new URLSearchParams({
      from: "watchlists",
      group: state.scope.groupId,
      window: state.scope.window,
      return: `${globalObject.location.pathname}${globalObject.location.search}`,
      ...extra,
    });
  }

  function symbolUrl(symbol) {
    const params = canonicalScopeUrl({ symbol });
    return `/mrz/symbols?${params}`;
  }

  function detailLink(label, href, className = "quiet-button") {
    const link = node("a", className, label);
    link.href = href;
    return link;
  }

  function setLoading(message = "Loading Group Radar…") {
    const live = $("#groupEvidenceLive");
    live.hidden = false;
    live.className = "group-evidence-live";
    live.textContent = message;
    $("#groupEvidenceContent").replaceChildren(node("div", "group-evidence-skeleton", message));
  }

  function setError(message) {
    const live = $("#groupEvidenceLive");
    live.hidden = false;
    live.className = "group-evidence-live error";
    live.setAttribute("role", "alert");
    live.textContent = message;
    const panel = node("section", "panel group-evidence-error");
    panel.append(node("h2", "", "Radar unavailable"), node("p", "", message));
    const retry = node("button", "primary-button", "Retry");
    retry.type = "button";
    retry.addEventListener("click", load);
    panel.append(retry);
    $("#groupEvidenceContent").replaceChildren(panel);
  }

  function selectedGroup() {
    if (state.detail?.group) return state.groups.find((group) => String(group.id) === String(state.detail.group.id)) || state.detail.group;
    return state.groups.find((group) => String(group.id) === String(state.scope.groupId)) || null;
  }

  function openGroup(groupId) {
    updateUrl({ group: groupId, dimension: null, bucket: null, evidence: null });
    state.recentLoaded = false;
    load().then(() => $("#selectedGroupWorkspace")?.scrollIntoView({ block: "start", behavior: "smooth" }));
  }

  function breadthCounts(group) {
    const distribution = group.structural?.current_distribution;
    if (!distribution) return null;
    const discount = Number(distribution.deep_discount || 0) + Number(distribution.shallow_discount || 0);
    const equilibrium = Number(distribution.at_eqm || 0);
    const premium = Number(distribution.shallow_premium || 0) + Number(distribution.deep_premium || 0);
    const unavailable = Number(distribution.unavailable || 0);
    return { premium, equilibrium, discount, unavailable, eligible: premium + equilibrium + discount };
  }

  function renderBreadth(group) {
    const counts = breadthCounts(group);
    if (!counts || !counts.eligible) return node("span", "radar-unavailable", "Unavailable");
    const wrap = node("div", "breadth-cell");
    const bar = node("div", "breadth-bar");
    [["premium", "Premium"], ["equilibrium", "Equilibrium"], ["discount", "Discount"]].forEach(([bucket, label]) => {
      const segment = node("span", bucket);
      segment.style.width = `${percent(counts[bucket], counts.eligible)}%`;
      segment.title = `${label} ${counts[bucket]} (${Math.round(percent(counts[bucket], counts.eligible))}%)`;
      bar.append(segment);
    });
    const values = node("span", "breadth-values", `${counts.premium} / ${counts.equilibrium} / ${counts.discount} (P / E / D)`);
    const coverage = node("small", "breadth-coverage", counts.unavailable
      ? `${counts.eligible} eligible · ${counts.unavailable} unavailable`
      : `${counts.eligible} / ${counts.eligible} eligible`);
    if (counts.unavailable) wrap.title = `${counts.unavailable} member(s) unavailable and excluded from the IPDA breadth denominator.`;
    wrap.append(bar, values, coverage);
    return wrap;
  }

  function directionMetric(higher, lower, empty = "—") {
    if (higher === undefined || lower === undefined) return node("span", "radar-unavailable", "Unavailable");
    const wrap = node("span", "direction-metric");
    if (!higher && !lower) wrap.textContent = empty;
    else {
      if (higher) wrap.append(node("span", "higher", `Higher ${higher}`));
      if (lower) wrap.append(node("span", "lower", `Lower ${lower}`));
    }
    return wrap;
  }

  function renderOverviewTable() {
    const section = node("section", "radar-overview");
    const tableWrap = node("div", "radar-table-wrap");
    const table = node("table", "radar-table");
    const head = node("thead", "");
    head.innerHTML = "<tr><th>Group</th><th>Members</th><th>IPDA Breadth (P / E / D)</th><th>Migration</th><th>Current Pressure State</th><th>Near Miss</th><th>OTE (1D)</th><th>OTE (1W)</th><th>Latest OTE Alert</th><th aria-label=\"Open\"></th></tr>";
    const body = node("tbody", "");
    const groups = (state.overview?.groups || []).filter((group) => group.name.toLowerCase().includes(state.search));
    groups.forEach((group) => {
      const row = node("tr", "");
      row.tabIndex = 0;
      row.dataset.groupId = group.id;
      if (String(group.id) === String(state.scope.groupId)) row.classList.add("selected");
      const nameCell = node("td", "group-name-cell");
      nameCell.append(node("span", "group-initial", group.name.slice(0, 2).toUpperCase()), node("strong", "", group.name));
      const memberCell = node("td", "", group.membership_total);
      const breadthCell = node("td", ""); breadthCell.append(renderBreadth(group));
      const migrationCell = node("td", ""); migrationCell.append(directionMetric(group.migrations?.unique_higher_contributors, group.migrations?.unique_lower_contributors));
      const current = group.directional?.current_pressure || {};
      const pressureCell = node("td", ""); pressureCell.append(directionMetric(current.higher, current.lower));
      const nearCell = node("td", "near-miss-count", group.near_miss?.status === "available" ? group.near_miss.active_episode_count : "Unavailable");
      const oteDaily = node("td", "ote-unavailable", group.ote?.status === "not_connected" ? "Not connected" : text(group.ote?.daily));
      const oteWeekly = node("td", "ote-unavailable", group.ote?.status === "not_connected" ? "Not connected" : text(group.ote?.weekly));
      const latestOte = node("td", "ote-unavailable", group.ote?.status === "not_connected" ? "OTE feed not connected" : text(group.ote?.latest));
      const open = node("td", "radar-open-cell"); open.append(node("span", "", "Open"));
      row.append(nameCell, memberCell, breadthCell, migrationCell, pressureCell, nearCell, oteDaily, oteWeekly, latestOte, open);
      row.addEventListener("click", () => openGroup(group.id));
      row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openGroup(group.id); } });
      body.append(row);
    });
    if (!groups.length) {
      const row = node("tr", "");
      const cell = node("td", "radar-empty", state.overview?.groups?.length ? "No groups match this search." : "No saved groups. Create a group to begin.");
      cell.colSpan = 10; row.append(cell); body.append(row);
    }
    table.append(head, body); tableWrap.append(table); section.append(tableWrap);
    return section;
  }

  function evidenceCard(kind, title, value, supporting, tone) {
    const card = node("button", `radar-evidence-card ${tone || ""}`);
    card.type = "button";
    card.dataset.inspect = kind;
    card.append(node("span", "evidence-card-label", title), node("strong", "evidence-card-value", value), node("small", "", supporting));
    return card;
  }

  function renderEvidenceCards(payload) {
    const current = payload.directional.current_pressure;
    const migrations = payload.directional.mrz_migrations;
    const near = payload.near_miss;
    const cards = node("div", "radar-evidence-cards");
    const migrationValue = migrations.status === "available" ? `${migrations.summary.unique_contributors} contributor${migrations.summary.unique_contributors === 1 ? "" : "s"}` : "Unavailable";
    const migrationSupport = migrations.status === "available" && migrations.summary.event_count ? `Latest ${shortDate(migrations.summary.latest_at)} · ${migrations.summary.event_count} event${migrations.summary.event_count === 1 ? "" : "s"}` : "No migration in selected window";
    const dominant = current.status === "available" ? current.summary.lower > current.summary.higher ? `Lower ${current.summary.lower}` : current.summary.higher > current.summary.lower ? `Higher ${current.summary.higher}` : `Balanced ${current.summary.higher}/${current.summary.lower}` : "Unavailable";
    cards.append(
      evidenceCard("migration", "MRZ Migration", migrationValue, migrationSupport, "migration"),
      evidenceCard("pressure", "Current Pressure State", dominant, current.status === "available" ? `${current.summary.neutral} neutral · retained canonical snapshot` : "Current pressure unavailable", "pressure"),
      evidenceCard("near-miss", "Near Miss", near.status === "available" ? `${near.active_episode_count} active` : "Unavailable", near.status === "available" ? `${near.historical_episode_count} historical in window` : "Episode data unavailable", "near-miss"),
      evidenceCard("ote", "OTE (from EDGE_BOT)", payload.ote.status === "not_connected" ? "Feed not connected" : `${text(payload.ote.daily)} 1D · ${text(payload.ote.weekly)} 1W`, payload.ote.status === "not_connected" ? "No counts until a supported feed exists" : `Latest ${exactTime(payload.ote.latest)}`, "ote"),
    );
    return cards;
  }

  function renderInspector(payload, kind) {
    const inspector = $("#radarEvidenceInspector");
    if (!inspector) return;
    inspector.replaceChildren();
    const header = node("header", "");
    const close = node("button", "quiet-button", "Close"); close.type = "button";
    close.addEventListener("click", () => { inspector.hidden = true; });
    const list = node("div", "inspector-list");
    let title = "Evidence"; let rows = [];
    if (kind === "migration") {
      title = "Migration contributors"; rows = payload.directional.mrz_migrations.contributors || [];
      rows.forEach((item) => { const row = node("a", "inspector-row"); row.href = symbolUrl(item.symbol); row.append(node("strong", "", item.symbol), node("span", "", `${item.directions.map(titleCase).join(" · ")} · ${item.event_count} event${item.event_count === 1 ? "" : "s"} · latest ${exactTime(item.latest_at)}`)); list.append(row); });
    } else if (kind === "pressure") {
      title = "Current pressure contributors"; rows = (payload.directional.current_pressure.members || []).filter((item) => item.direction !== "neutral");
      rows.forEach((item) => { const row = node("a", "inspector-row"); row.href = symbolUrl(item.symbol); row.append(node("strong", item.direction, item.symbol), node("span", "", `${titleCase(item.direction)} · evidence ${exactTime(item.evidence?.latest_pressure_observed_at)}`)); list.append(row); });
    } else if (kind === "near-miss") {
      title = "Near Miss episodes"; rows = payload.near_miss.episodes || [];
      rows.forEach((item) => { const row = node("a", "inspector-row"); row.href = symbolUrl(item.symbol); row.append(node("strong", item.active ? "active" : "", item.symbol), node("span", "", `${item.route_owner} · ${item.active ? "Active episode" : `Ended ${exactTime(item.ended_at)}`} · started ${exactTime(item.started_at)}`)); list.append(row); });
    } else {
      title = "OTE integration"; list.append(node("div", "inspector-empty", "OTE feed not connected. EDGE 2.0 is ready to present supported EDGE_BOT events without recreating OTE calculations."));
    }
    if (!rows.length && kind !== "ote") list.append(node("div", "inspector-empty", "No contributing symbols or events in the selected window."));
    header.append(node("h3", "", title), close); inspector.append(header, list); inspector.hidden = false;
    inspector.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function drawLocationFlow(canvas, history) {
    if (!canvas || history?.status !== "available") return;
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(420, Math.floor(rect.width)); const height = 180; const scale = globalObject.devicePixelRatio || 1;
    canvas.width = Math.floor(width * scale); canvas.height = Math.floor(height * scale);
    const ctx = canvas.getContext("2d"); ctx.scale(scale, scale);
    const points = history.points || []; const left = 42, right = 12, top = 12, bottom = 24; const chartWidth = width - left - right, chartHeight = height - top - bottom;
    ctx.clearRect(0, 0, width, height); ctx.strokeStyle = "#263747"; ctx.fillStyle = "#8290a1"; ctx.lineWidth = 1; ctx.font = "10px Inter, sans-serif";
    [0, 25, 50, 75, 100].forEach((tick) => { const y = top + chartHeight - chartHeight * tick / 100; ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(width - right, y); ctx.stroke(); ctx.fillText(`${tick}%`, 4, y + 3); });
    const layers = [
      { key: "deep_discount", fill: "rgba(153,38,50,.92)" },
      { key: "shallow_discount", fill: "rgba(255,101,108,.82)" },
      { key: "at_eqm", fill: "rgba(130,144,161,.78)" },
      { key: "shallow_premium", fill: "rgba(73,204,139,.82)" },
      { key: "deep_premium", fill: "rgba(11,115,78,.95)" },
    ];
    const xAt = (index) => left + (points.length <= 1 ? 0 : chartWidth * index / (points.length - 1)); let baseline = points.map(() => 0);
    layers.forEach((layer) => {
      const values = points.map((point) => percent(point.buckets[layer.key], point.aggregate.eligible));
      ctx.beginPath(); ctx.moveTo(xAt(0), top + chartHeight - chartHeight * baseline[0] / 100);
      values.forEach((value, index) => ctx.lineTo(xAt(index), top + chartHeight - chartHeight * (baseline[index] + value) / 100));
      for (let index = values.length - 1; index >= 0; index -= 1) ctx.lineTo(xAt(index), top + chartHeight - chartHeight * baseline[index] / 100);
      ctx.closePath(); ctx.fillStyle = layer.fill; ctx.fill(); baseline = baseline.map((value, index) => value + values[index]);
    });
    ctx.fillStyle = "#8290a1";
    if (points.length) { ctx.fillText(shortDate(points[0].at), left, height - 5); const end = shortDate(points[points.length - 1].at); ctx.fillText(end, width - right - ctx.measureText(end).width, height - 5); }
    canvas._locationChart = { points, left, chartWidth };
  }

  function signed(value, suffix = "") {
    const number = Number(value);
    if (!Number.isFinite(number)) return "Unavailable";
    return `${number > 0 ? "+" : ""}${Number.isInteger(number) ? number : number.toFixed(1)}${suffix}`;
  }

  function renderDistributionSummary(history) {
    const aside = node("aside", "location-distribution-summary");
    aside.append(node("h4", "", "Current Distribution"));
    const table = node("table", "location-summary-table");
    const head = node("thead", ""); head.innerHTML = "<tr><th>Location</th><th>Current</th><th>Change</th></tr>";
    const body = node("tbody", "");
    (history.current_distribution_summary || []).forEach((item) => {
      const row = node("tr", "");
      const current = item.current_eligible
        ? `${item.current_count}/${item.current_eligible} (${Math.round(item.current_percent)}%)`
        : "Unavailable";
      const change = item.change_status === "comparable"
        ? `${signed(item.count_change)} member${Math.abs(item.count_change) === 1 ? "" : "s"} (${signed(item.percentage_point_change, " pp")})`
        : "Coverage changed";
      row.append(node("th", item.key, item.label), node("td", "", current), node("td", item.change_status, change));
      body.append(row);
    });
    table.append(head, body);
    aside.append(table, node("p", "comparison-basis", history.comparison_basis?.message || "Endpoint comparison unavailable."));
    return aside;
  }

  function renderLocationFlow(payload) {
    const panel = node("section", "radar-panel location-flow-panel"); const header = node("header", "radar-panel-heading");
    header.append(node("h3", "", "Group IPDA Location Distribution (20W)"), node("span", "", `Historical evidence · ${state.scope.window}`)); panel.append(header);
    if (payload.location_history?.status !== "available") { panel.append(node("div", "chart-unavailable", payload.location_history?.message || "Historical location data unavailable.")); return panel; }
    const legend = node("div", "flow-legend five-bucket-legend"); [["deep_premium", "Deep Premium"], ["shallow_premium", "Shallow Premium"], ["at_eqm", "Equilibrium"], ["shallow_discount", "Shallow Discount"], ["deep_discount", "Deep Discount"]].forEach(([key, label]) => legend.append(node("span", key, label)));
    const canvas = node("canvas", "location-flow-canvas"); canvas.setAttribute("aria-label", "Historical group member distribution by structural location");
    const tooltip = node("div", "location-flow-tooltip"); tooltip.hidden = true;
    canvas.addEventListener("mousemove", (event) => {
      const chart = canvas._locationChart; if (!chart?.points?.length) return;
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const index = chart.points.length === 1 ? 0 : Math.max(0, Math.min(chart.points.length - 1, Math.round((x - chart.left) / chart.chartWidth * (chart.points.length - 1))));
      const point = chart.points[index];
      const rows = payload.location_history.canonical_buckets.slice().reverse().map((bucket) => `${bucket.label}: ${point.buckets[bucket.key]} (${Math.round(percent(point.buckets[bucket.key], point.aggregate.eligible))}%)`);
      tooltip.textContent = `${exactTime(point.at)} · ${point.aggregate.eligible} eligible · ${rows.join(" · ")}`;
      tooltip.style.left = `${Math.min(rect.width - 260, Math.max(8, x + 10))}px`; tooltip.style.top = `${Math.max(8, event.clientY - rect.top - 36)}px`; tooltip.hidden = false;
    });
    canvas.addEventListener("mouseleave", () => { tooltip.hidden = true; });
    const chart = node("div", "location-chart-column"); chart.append(legend, canvas, tooltip);
    const layout = node("div", "location-distribution-layout"); layout.append(chart, renderDistributionSummary(payload.location_history));
    panel.append(layout); globalObject.requestAnimationFrame(() => drawLocationFlow(canvas, payload.location_history)); return panel;
  }

  function timelineEvents(payload) {
    return {
      migration: (payload.directional.mrz_migrations.events || []).map((event) => ({ ...event, at: event.occurred_at, label: `${event.symbol} · ${titleCase(event.direction)}`, tone: event.direction })),
      pressure: (payload.directional.cumulative_lifecycle_pressure_events.events || []).map((event) => ({ ...event, at: event.occurred_at, label: `${event.symbol} · ${titleCase(event.event_direction)}`, tone: event.event_direction })),
      "near-miss": (payload.near_miss.episodes || []).flatMap((episode) => { const events = [{ ...episode, at: episode.started_at, label: `${episode.symbol} · Started`, tone: "near-miss" }]; if (episode.ended_at) events.push({ ...episode, at: episode.ended_at, label: `${episode.symbol} · Ended`, tone: "near-miss-ended" }); return events; }),
      ote: [],
    };
  }

  function renderTimeline(payload) {
    const panel = node("section", "radar-panel event-timeline-panel"); const header = node("header", "radar-panel-heading"); header.append(node("h3", "", "Group Event Timeline"), node("span", "", `Last ${state.scope.window}`)); panel.append(header);
    const lanes = node("div", "timeline-lanes"); const events = timelineEvents(payload); const start = new Date(payload.window.comparison_at).getTime(); const end = new Date(payload.window.as_of).getTime();
    [["migration", "Migration"], ["pressure", "Pressure"], ["near-miss", "Near Miss"], ["ote", "OTE"]].forEach(([key, label]) => {
      const lane = node("div", "timeline-lane"); lane.append(node("span", `lane-label ${key}`, label)); const track = node("div", "timeline-track");
      (events[key] || []).forEach((event) => { const marker = node("button", `timeline-marker ${event.tone || key}`); marker.type = "button"; marker.title = `${event.label} · ${exactTime(event.at)}`; marker.style.left = `${percent(new Date(event.at).getTime() - start, end - start)}%`; marker.setAttribute("aria-label", marker.title); marker.addEventListener("click", () => { const details = $("#timelineEventDetails"); details.textContent = `${event.label} · ${exactTime(event.at)} · ${text(event.event_key || event.episode_key || event.source_event_key, "Canonical event")}`; details.hidden = false; }); track.append(marker); });
      if (key === "ote" && payload.ote.status === "not_connected") track.append(node("span", "timeline-unavailable", "Feed not connected")); lane.append(track); lanes.append(lane);
    });
    const axis = node("div", "timeline-axis"); axis.append(node("span", "", shortDate(payload.window.comparison_at)), node("span", "", shortDate(payload.window.as_of))); const detail = node("div", "timeline-event-details"); detail.id = "timelineEventDetails"; detail.hidden = true;
    panel.append(lanes, axis, detail); return panel;
  }

  function statusPill(value, tone) { return node("span", `radar-pill ${tone || ""}`, value); }

  function renderMembers(payload) {
    const panel = node("section", "radar-panel group-members-panel"); const header = node("header", "radar-panel-heading"); header.append(node("h3", "", `Group Members (${payload.group.member_count})`)); panel.append(header);
    const wrap = node("div", "radar-table-wrap"); const table = node("table", "member-evidence-table"); const head = node("thead", ""); head.innerHTML = "<tr><th>Symbol</th><th>Route</th><th>Location</th><th>MRZ Levels</th><th>Last Pressure Direction</th><th>Near Miss</th><th>OTE (1D)</th><th>OTE (1W)</th><th>Latest OTE Alert</th><th aria-label=\"Open\"></th></tr>"; const body = node("tbody", "");
    (payload.members || []).forEach((member) => {
      const row = node("tr", ""); const symbol = node("td", "symbol-cell"); symbol.append(detailLink(member.symbol, symbolUrl(member.symbol), "symbol-link")); const route = node("td", ""); route.append(statusPill(text(member.route), String(member.route || "").toLowerCase())); const location = node("td", ""); location.append(statusPill(member.location_label, member.location?.includes("discount") ? "lower" : member.location?.includes("premium") ? "higher" : "neutral"));
      const mrz = node("td", "mrz-levels-cell");
      if (member.mrz?.status === "active") {
        const details = node("details", "member-mrz-details");
        details.append(node("summary", "", `${member.mrz.lower} – ${member.mrz.upper}`));
        details.append(node("span", "", `Midpoint ${member.mrz.midpoint}`), node("span", "", `Activated ${exactTime(member.mrz.activated_at)}`), node("span", "", `Route ${member.mrz.route_owner}`));
        mrz.append(details);
      } else mrz.append(node("span", "radar-unavailable", member.mrz?.status === "inactive" ? "No active MRZ" : "Unavailable"));
      const pressure = node("td", "last-pressure-cell");
      if (member.last_pressure_direction) {
        const arrow = member.last_pressure_direction === "higher" ? "↑" : "↓";
        const block = node("div", `pressure-event ${member.last_pressure_direction}`);
        block.append(node("strong", "", `${arrow} ${titleCase(member.last_pressure_direction)}`), node("time", "", operatorDate(member.last_pressure_event_at)));
        if (["opposite_direction", "current_neutral"].includes(member.last_pressure_vs_current)) block.append(node("small", "pressure-mismatch", `Current state: ${titleCase(member.pressure)}`));
        pressure.append(block);
      } else pressure.append(node("span", "radar-unavailable", "No directional event"));
      const near = node("td", "near-miss-cell", member.near_miss ? (member.near_miss.active ? "Active" : "Historical") : "—"); const daily = node("td", "ote-unavailable", member.ote?.status === "not_connected" ? "Not connected" : text(member.ote?.daily)); const weekly = node("td", "ote-unavailable", member.ote?.status === "not_connected" ? "Not connected" : text(member.ote?.weekly)); const latest = node("td", "ote-unavailable", member.ote?.status === "not_connected" ? "OTE feed not connected" : text(member.ote?.latest)); const open = node("td", "radar-open-cell"); open.append(detailLink("Open", symbolUrl(member.symbol), "table-open-link")); row.append(symbol, route, location, mrz, pressure, near, daily, weekly, latest, open); body.append(row);
    });
    table.append(head, body); wrap.append(table); panel.append(wrap); return panel;
  }

  function renderNamedGroup(payload) {
    const workspace = node("section", "selected-group-workspace"); workspace.id = "selectedGroupWorkspace";
    const header = node("header", "selected-group-header"); const back = node("button", "back-button", "Back to all groups"); back.type = "button"; back.addEventListener("click", () => { updateUrl({ group: "all" }); state.detail = null; render(); globalObject.scrollTo({ top: 0, behavior: "smooth" }); }); const identity = node("div", "selected-group-identity"); identity.append(node("h2", "", payload.group.name), node("p", "", `${payload.group.member_count} members · Group evidence`)); const edit = node("button", "quiet-button", "Edit Group"); edit.type = "button"; edit.addEventListener("click", () => openEditor(selectedGroup())); header.append(back, identity, edit); workspace.append(header, renderEvidenceCards(payload));
    const inspector = node("section", "radar-evidence-inspector"); inspector.id = "radarEvidenceInspector"; inspector.hidden = true; workspace.append(inspector); const charts = node("div", "radar-chart-grid"); charts.append(renderLocationFlow(payload), renderTimeline(payload)); workspace.append(charts, renderMembers(payload)); workspace.querySelectorAll("[data-inspect]").forEach((button) => button.addEventListener("click", () => renderInspector(payload, button.dataset.inspect))); return workspace;
  }

  function renderDetails() {
    const body = $("#groupEvidenceDetailsBody"); body.replaceChildren(); const payload = state.detail || state.overview; if (!payload) return; const grid = node("dl", "evidence-detail-grid");
    const values = payload.scope === "named_group" ? [["As of", exactTime(payload.window.as_of)], ["Comparison", exactTime(payload.window.comparison_at)], ["Members", payload.group.member_count], ["Structural comparable", ratio(payload.coverage.structural_comparable, payload.group.member_count)], ["Current locations available", ratio(payload.coverage.structural_current_available, payload.group.member_count)], ["Fresh observations", ratio(payload.coverage.structural_fresh_in_window, payload.coverage.structural_comparable)], ["Active MRZ coverage", ratio(payload.coverage.current_pressure_active_mrz, payload.group.member_count)], ["Latest relevant evidence", exactTime(payload.latest_relevant_evidence_at)], ["Membership updated", exactTime(payload.group.updated_at)]] : [["As of", exactTime(payload.window.as_of)], ["Comparison", exactTime(payload.window.comparison_at)], ["Saved groups", payload.scope_totals.group_count], ["Member slots", payload.scope_totals.member_slots], ["Unique symbols", payload.scope_totals.unique_members], ["Canonical migrations", payload.scope_totals.canonical_migration_events]];
    values.forEach(([label, value]) => { grid.append(node("dt", "", label), node("dd", "", text(value))); }); const limitations = node("ul", "evidence-limitations"); (payload.limitations || []).forEach((item) => limitations.append(node("li", "", item))); body.append(grid, limitations);
  }

  function render() {
    const wrapper = node("div", "radar-content"); wrapper.append(renderOverviewTable()); if (state.detail?.scope === "named_group") wrapper.append(renderNamedGroup(state.detail)); $("#groupEvidenceContent").replaceChildren(wrapper);
    $("#groupEvidenceGroupCount").textContent = `Groups (${state.overview?.scope_totals?.group_count || 0})`; $("#groupEvidenceAsOf").textContent = exactTime((state.detail || state.overview)?.window?.as_of); $("#groupEvidenceEdit").hidden = true;
    globalObject.document.querySelectorAll("[data-group-window]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.groupWindow === state.scope.window)));
    const live = $("#groupEvidenceLive"); live.className = "group-evidence-live"; live.hidden = false; live.textContent = state.detail?.status === "partial" || state.overview?.status === "partial" ? "Evidence loaded with one or more unavailable dimensions." : "Canonical group evidence loaded."; renderDetails(); updateManageMenuState();
  }

  async function loadGroups() {
    const response = await globalObject.fetch("/api/groups", { cache: "no-store" }); if (!response.ok) throw new Error("Saved groups unavailable."); state.groups = (await response.json()).groups || []; return state.groups;
  }

  async function load() {
    state.controller?.abort(); const controller = new AbortController(); state.controller = controller; const requestId = ++state.requestId; const scope = { ...state.scope }; setLoading();
    try {
      const requests = [globalObject.fetch(`/api/group-evidence?window=${encodeURIComponent(scope.window)}`, { cache: "no-store", signal: controller.signal }), loadGroups()];
      if (scope.groupId !== "all") requests.push(globalObject.fetch(`/api/group-evidence/${encodeURIComponent(scope.groupId)}?window=${encodeURIComponent(scope.window)}`, { cache: "no-store", signal: controller.signal }));
      const results = await Promise.all(requests); if (requestId !== state.requestId || scope.window !== state.scope.window || scope.groupId !== state.scope.groupId) return;
      const overviewResponse = results[0]; if (!overviewResponse.ok) throw new Error("Group evidence service unavailable."); state.overview = await overviewResponse.json();
      if (scope.groupId !== "all") { const detailResponse = results[2]; if (detailResponse.status === 404) { updateUrl({ group: "all" }, { replace: true }); state.detail = null; } else if (!detailResponse.ok) throw new Error("Selected group evidence unavailable."); else state.detail = await detailResponse.json(); } else state.detail = null;
      state.lastSuccessful.set(`${scope.groupId}:${scope.window}`, { overview: state.overview, detail: state.detail }); render();
    } catch (error) {
      if (error.name === "AbortError") return; const previous = state.lastSuccessful.get(`${scope.groupId}:${scope.window}`); if (previous) { state.overview = previous.overview; state.detail = previous.detail; render(); $("#groupEvidenceLive").textContent = "Showing the last successfully loaded snapshot."; $("#groupEvidenceLive").classList.add("error"); } else setError(error.message || "Group evidence service unavailable.");
    }
  }

  async function loadRecentEvents() {
    const body = $("#recentTrackedEventsBody"); const toggle = $("#recentTrackedEventsToggle"); const expanded = body.hidden; body.hidden = !expanded; toggle.setAttribute("aria-expanded", String(expanded)); toggle.textContent = expanded ? "Hide" : "Show"; if (!expanded || state.recentLoaded) return; $("#recentTrackedEventsStatus").textContent = "Loading recent tracked symbol events…";
    try {
      const members = state.detail?.group?.members || [...new Set(state.groups.flatMap((group) => group.members || []))]; const response = await globalObject.fetch("/api/mrz/events?limit=500", { cache: "no-store" }); if (!response.ok) throw new Error("Recent event history unavailable."); const cutoff = Date.now() - 24 * 60 * 60 * 1000; const memberSet = new Set(members); const events = ((await response.json()).events || []).filter((event) => memberSet.has(event.symbol) && new Date(event.occurred_at).getTime() > cutoff); const list = node("ul", "recent-tracked-event-list"); events.forEach((event) => { const row = node("li", ""); const copy = node("div", ""); copy.append(node("strong", "", `${event.symbol} · ${event.event_name || event.event_type}`), node("p", "", `${exactTime(event.occurred_at)} · ${event.body || "Canonical event"}`)); row.append(copy, detailLink("Open symbol", symbolUrl(event.symbol))); list.append(row); }); if (!events.length) list.append(node("li", "evidence-empty", "No tracked symbol event in the last 24H.")); $("#recentTrackedEventsList").replaceChildren(list); $("#recentTrackedEventsStatus").textContent = `${events.length} raw tracked symbol events loaded.`; state.recentLoaded = true;
    } catch (error) { $("#recentTrackedEventsStatus").textContent = `${error.message} Group Radar remains available.`; $("#recentTrackedEventsStatus").classList.add("error"); }
  }

  function closeMenu() { $("#groupEvidenceManageMenu").hidden = true; $("#groupEvidenceManage").setAttribute("aria-expanded", "false"); }

  function updateManageMenuState() {
    const groupSelected = Boolean(selectedGroup()); ["edit", "duplicate", "delete"].forEach((action) => { const button = $(`[data-manage-action="${action}"]`); if (button) button.disabled = !groupSelected; });
  }

  async function ensureSymbols() {
    if (state.allSymbols.length) return state.allSymbols; const response = await globalObject.fetch("/api/symbols", { cache: "no-store" }); if (!response.ok) throw new Error("Canonical symbols unavailable."); state.allSymbols = (await response.json()).symbols || []; return state.allSymbols;
  }

  function renderEditorMembers() {
    const chips = $("#groupEvidenceSelectedChips"); chips.replaceChildren(); [...state.editorMembers].sort().forEach((symbol) => { const chip = node("button", "member-chip", `${symbol} ×`); chip.type = "button"; chip.setAttribute("aria-label", `Remove ${symbol}`); chip.addEventListener("click", () => { state.editorMembers.delete(symbol); renderEditorMembers(); renderSymbolChoices(); }); chips.append(chip); }); $("#groupEvidenceChoicesStatus").textContent = `${state.editorMembers.size} member${state.editorMembers.size === 1 ? "" : "s"} selected`;
  }

  function renderSymbolChoices() {
    const query = $("#groupEvidenceSymbolSearch").value.trim().toLowerCase(); const results = $("#groupEvidenceSymbolChoices"); results.replaceChildren(); const matches = state.allSymbols.filter((item) => !state.editorMembers.has(item.symbol) && (!query || item.symbol.toLowerCase().includes(query))).slice(0, 20); matches.forEach((item) => { const button = node("button", "symbol-result", item.symbol); button.type = "button"; button.addEventListener("click", () => { state.editorMembers.add(item.symbol); $("#groupEvidenceSymbolSearch").value = ""; renderEditorMembers(); renderSymbolChoices(); }); results.append(button); }); if (!matches.length) results.append(node("p", "evidence-empty", query ? "No matching canonical symbols." : "All matching symbols are selected."));
  }

  async function openEditor(group = null) {
    closeMenu(); if ($("#groupEvidenceManageDialog").open) $("#groupEvidenceManageDialog").close(); state.editingGroup = group; state.editorMembers = new Set(group?.members || []); $("#groupEvidenceDialogTitle").textContent = group ? `Edit ${group.name}` : "Create Group"; $("#groupEvidenceName").value = group?.name || ""; $("#groupEvidenceDelete").hidden = !group; $("#groupEvidenceSave").textContent = group ? "Save Changes" : "Create Group"; $("#groupEvidenceFormError").hidden = true; $("#groupEvidenceSymbolSearch").value = ""; $("#groupEvidenceDialog").showModal();
    try { await ensureSymbols(); renderEditorMembers(); renderSymbolChoices(); } catch (error) { $("#groupEvidenceChoicesStatus").textContent = error.message; }
  }

  async function saveGroup(event) {
    event.preventDefault(); if (event.submitter?.value === "cancel") { $("#groupEvidenceDialog").close(); return; } const payload = { name: $("#groupEvidenceName").value.trim(), members: [...state.editorMembers] }; if (!payload.name || !payload.members.length) { $("#groupEvidenceFormError").textContent = "Add a group name and at least one member."; $("#groupEvidenceFormError").hidden = false; return; } const url = state.editingGroup ? `/api/groups/${state.editingGroup.id}` : "/api/groups"; const response = await globalObject.fetch(url, { method: state.editingGroup ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); if (!response.ok) { const body = await response.json().catch(() => ({})); $("#groupEvidenceFormError").textContent = body.detail || "Unable to save group."; $("#groupEvidenceFormError").hidden = false; return; } const saved = await response.json(); $("#groupEvidenceDialog").close(); updateUrl({ group: saved.id }); state.recentLoaded = false; await load();
  }

  async function deleteGroup(group = state.editingGroup || selectedGroup()) {
    if (!group) return; if (!globalObject.confirm(`Delete “${group.name}”? Canonical MRZ, pressure, Near Miss and event evidence will not be changed.`)) return; const response = await globalObject.fetch(`/api/groups/${group.id}`, { method: "DELETE" }); if (!response.ok) throw new Error("Unable to delete group."); if ($("#groupEvidenceDialog").open) $("#groupEvidenceDialog").close(); if ($("#groupEvidenceManageDialog").open) $("#groupEvidenceManageDialog").close(); updateUrl({ group: "all" }); state.detail = null; state.recentLoaded = false; await load();
  }

  async function duplicateGroup(group = selectedGroup()) {
    if (!group) return; const names = new Set(state.groups.map((item) => item.name.toLowerCase())); let name = `${group.name} Copy`; let index = 2; while (names.has(name.toLowerCase())) { name = `${group.name} Copy ${index}`; index += 1; } const response = await globalObject.fetch("/api/groups", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, members: group.members }) }); if (!response.ok) throw new Error("Unable to duplicate group."); const saved = await response.json(); updateUrl({ group: saved.id }); await load();
  }

  function renderManageList() {
    const list = $("#groupEvidenceManageList"); list.replaceChildren(); state.groups.forEach((group) => { const row = node("article", "manage-group-row"); const identity = node("div", ""); identity.append(node("strong", "", group.name), node("span", "", `${group.members.length} members`)); const actions = node("div", "manage-group-actions"); const edit = node("button", "quiet-button", "Edit"); edit.type = "button"; edit.addEventListener("click", () => openEditor(group)); const remove = node("button", "danger-button", "Delete"); remove.type = "button"; remove.addEventListener("click", () => deleteGroup(group).catch((error) => setError(error.message))); actions.append(edit, remove); row.append(identity, actions); list.append(row); }); if (!state.groups.length) list.append(node("p", "evidence-empty", "No saved groups."));
  }

  function openManageAll() { closeMenu(); renderManageList(); $("#groupEvidenceManageDialog").showModal(); }

  function syncAlertBadge() {
    const source = $("#notificationUnreadBadge"); const target = $("#radarUnreadBadge"); if (!source || !target) return; target.textContent = source.textContent; target.hidden = source.hidden;
  }

  function bindEvents() {
    globalObject.document.querySelectorAll("[data-group-window]").forEach((button) => button.addEventListener("click", () => { updateUrl({ window: button.dataset.groupWindow }); state.recentLoaded = false; load(); }));
    $("#groupEvidenceSearch").addEventListener("input", (event) => { state.search = event.target.value.trim().toLowerCase(); render(); });
    $("#groupEvidenceNew").addEventListener("click", () => openEditor()); $("#groupEvidenceEdit").addEventListener("click", () => openEditor(selectedGroup()));
    $("#groupEvidenceManage").addEventListener("click", () => { const menu = $("#groupEvidenceManageMenu"); menu.hidden = !menu.hidden; $("#groupEvidenceManage").setAttribute("aria-expanded", String(!menu.hidden)); });
    $("#groupEvidenceManageMenu").addEventListener("click", (event) => { const action = event.target.closest("[data-manage-action]")?.dataset.manageAction; if (!action) return; if (action === "edit") openEditor(selectedGroup()); else if (action === "duplicate") duplicateGroup().catch((error) => setError(error.message)); else if (action === "delete") deleteGroup().catch((error) => setError(error.message)); else if (action === "all") openManageAll(); });
    globalObject.document.addEventListener("click", (event) => { if (!event.target.closest(".manage-menu-wrap")) closeMenu(); });
    $("#groupEvidenceForm").addEventListener("submit", (event) => saveGroup(event).catch((error) => { $("#groupEvidenceFormError").textContent = error.message; $("#groupEvidenceFormError").hidden = false; })); $("#groupEvidenceDelete").addEventListener("click", () => deleteGroup().catch((error) => setError(error.message))); $("#groupEvidenceSymbolSearch").addEventListener("input", renderSymbolChoices);
    $("#groupEvidenceDialogClose").addEventListener("click", () => $("#groupEvidenceDialog").close()); $("#groupEvidenceCancel").addEventListener("click", () => $("#groupEvidenceDialog").close());
    $("#groupEvidenceManageClose").addEventListener("click", () => $("#groupEvidenceManageDialog").close()); $("#groupEvidenceManageDone").addEventListener("click", () => $("#groupEvidenceManageDialog").close()); $("#groupEvidenceManageNew").addEventListener("click", () => openEditor());
    $("#recentTrackedEventsToggle").addEventListener("click", () => loadRecentEvents()); $("#radarAlertsButton").addEventListener("click", () => $("#notificationInboxButton")?.click());
    globalObject.addEventListener("popstate", () => { state.scope = derive.parseGroupEvidenceState(globalObject.location.search); state.recentLoaded = false; load(); });
    const badge = $("#notificationUnreadBadge"); if (badge) new MutationObserver(syncAlertBadge).observe(badge, { childList: true, attributes: true, subtree: true }); syncAlertBadge();
  }

  function mount() {
    if (!globalObject.document?.querySelector('[data-route-panel="watchlists"]')) return Promise.resolve();
    if (state.mounted) return Promise.resolve();
    state.mounted = true;
    bindEvents();
    return load();
  }

  globalObject.edgeGroupEvidence = { mount };
})(window);
