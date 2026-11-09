(function initializeMrzWorkspace(globalObject) {
  "use strict";

  const derive = globalObject.edgeWorkspaceDerivations;
  const state = {
    symbols: [],
    symbolPayload: null,
    groups: [],
    events: [],
    preferences: null,
    locationHistory: null,
    locationWindow: "24H",
    locationTaxonomyLevel: "sector",
    locationTaxonomyMode: "movement",
    locationTaxonomySort: "lower",
    locationTaxonomySelection: null,
    locationFlowSelection: null,
    peerWindow: "24H",
    peerLocationHistory: null,
    peerPressure: null,
    peerContextKey: null,
    peerSelection: null,
    selectedGroupId: "all",
    editingGroupId: null,
    symbolBoardSort: derive.restoreSymbolBoardSort(globalObject.localStorage),
  };
  let locationFlowPaths = [];
  const locationLabels = {
    deep_discount: "Deep Discount",
    shallow_discount: "Shallow Discount",
    at_eqm: "At EQM",
    shallow_premium: "Shallow Premium",
    deep_premium: "Deep Premium",
    deep_discount_core_mrz: "Deep Discount",
    shallow_discount_core_mrz: "Shallow Discount",
    shallow_premium_core_mrz: "Shallow Premium",
    deep_premium_core_mrz: "Deep Premium",
    below_ipda_range: "Below IPDA Range",
    above_ipda_range: "Above IPDA Range",
  };
  const pressureLabels = {
    higher: "↑ Higher",
    lower: "↓ Lower",
    neutral: "↔ Neutral",
  };

  const $ = (selector) => document.querySelector(selector);
  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function routeName() {
    const path = globalObject.location.pathname.replace(/\/$/, "");
    if (path === "" || path === "/") return "overview";
    return path.split("/").pop() || "overview";
  }
  function activateRoute() {
    const route = routeName();
    document.querySelectorAll("[data-route-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.routePanel !== route;
    });
    document.querySelectorAll("[data-route]").forEach((link) => {
      if (link.dataset.route === route) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }
  function formatPrice(value) {
    if (value === null || value === undefined) return "—";
    return new Intl.NumberFormat("en-US", { maximumFractionDigits: 12 }).format(Number(value));
  }
  function exactTime(value) {
    if (!value) return "—";
    return globalObject.formatOperatorTimestampUtcMinus4?.(value)
      || new Date(value).toLocaleString();
  }
  function relativeTime(value) {
    const timestamp = new Date(value);
    if (!value || Number.isNaN(timestamp.getTime())) return "—";
    const seconds = Math.max(0, Math.round((Date.now() - timestamp.getTime()) / 1000));
    if (seconds < 60) return "now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  }
  function pressureBySymbol() {
    const result = new Map();
    const categories = state.symbolPayload?.pressure?.categories || {};
    Object.entries(categories).forEach(([direction, members]) => {
      (members || []).forEach((member) => result.set(member.symbol, { ...member, direction }));
    });
    return result;
  }
  function pressureSourceBySymbol() {
    const result = new Map();
    const sources = state.symbolPayload?.taxonomy_pressure?.sources || {};
    Object.values(sources).flat().forEach((member) => result.set(member.symbol, member));
    return result;
  }
  function latestEvents() { return derive.latestEventsBySymbol(state.events); }
  function selectedGroup() {
    return state.groups.find((group) => String(group.id) === String(state.selectedGroupId)) || null;
  }
  function groupNamesForSymbol(symbol) {
    return (derive.groupMembership(state.groups).get(symbol) || []).map((group) => group.name);
  }
  function symbolLink(symbol, label = "Open") {
    const link = element("a", "event-open", label);
    link.href = `/mrz/symbols?symbol=${encodeURIComponent(symbol)}`;
    return link;
  }
  function empty(message) { return element("div", "empty-inline", message); }

  function eventList(events, { showGroups = true, limit = null } = {}) {
    const visible = limit ? events.slice(0, limit) : events;
    if (visible.length === 0) return empty("No current attention events in this window.");
    const list = element("ul", "event-list");
    visible.forEach((event) => {
      const row = element("li", "event-row");
      const time = element("time", "", relativeTime(event.occurred_at));
      time.dateTime = event.occurred_at || "";
      time.title = exactTime(event.occurred_at);
      row.append(
        time,
        element("strong", "event-symbol", event.symbol),
        element("span", "event-name", derive.eventLabel(event)),
        element("span", "event-context", showGroups ? groupNamesForSymbol(event.symbol).join(" · ") || event.body : event.body),
        symbolLink(event.symbol),
      );
      list.append(row);
    });
    return list;
  }

  function renderOverview(attention) {
    const tracked = derive.uniqueTrackedSymbols(state.groups);
    const trackedStates = state.symbols.filter((item) => tracked.has(item.symbol));
    $("#overviewGroupCount").textContent = String(state.groups.length);
    $("#overviewSymbolCount").textContent = String(tracked.size);
    $("#overviewActiveCount").textContent = String(trackedStates.filter((item) => item.mrz_status === "active").length);
    $("#overviewAttentionCount").textContent = String(attention.length);
    $("#overviewAttention").replaceChildren(eventList(attention, { limit: 6 }));

    const list = element("ul", "group-status-list");
    if (state.groups.length === 0) list.append(empty("Create a trading watchlist to elevate symbols into the operator workflow."));
    state.groups.forEach((group) => {
      const members = new Set(group.members || []);
      const active = state.symbols.filter((item) => members.has(item.symbol) && item.mrz_status === "active").length;
      const count = attention.filter((event) => members.has(event.symbol)).length;
      const row = element("li", "group-status-row");
      row.append(element("strong", "", group.name), element("span", "", `${active}/${group.member_count} active MRZ`), element("span", "", `${count} current attention`));
      list.append(row);
    });
    $("#overviewGroups").replaceChildren(list);
  }

  function scopedAttention() {
    const attention = derive.deriveAttention(state.events, state.groups);
    if (state.selectedGroupId === "all") return attention;
    const members = new Set(selectedGroup()?.members || []);
    return attention.filter((event) => members.has(event.symbol));
  }
  function renderWatchlistTabs(attention) {
    const tabs = $("#watchlistTabs");
    tabs.replaceChildren();
    if (state.groups.length > 1) {
      tabs.append(watchlistTab("all", "ALL GROUPS", attention.length));
    } else if (state.groups.length === 1 && state.selectedGroupId === "all") {
      state.selectedGroupId = String(state.groups[0].id);
    }
    state.groups.forEach((group) => {
      const members = new Set(group.members || []);
      tabs.append(watchlistTab(group.id, group.name.toUpperCase(), attention.filter((event) => members.has(event.symbol)).length));
    });
    if (state.groups.length === 0) tabs.append(empty("No trading watchlists yet."));
  }
  function watchlistTab(id, label, count) {
    const button = element("button", "");
    button.type = "button";
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(String(state.selectedGroupId) === String(id)));
    button.append(document.createTextNode(label), element("b", "", String(count)));
    button.addEventListener("click", () => {
      state.selectedGroupId = String(id);
      state.peerContextKey = null;
      state.peerSelection = null;
      renderWatchlists(derive.deriveAttention(state.events, state.groups));
      loadPeerContext().catch(showError);
    });
    return button;
  }
  function renderWatchlists(attention) {
    renderWatchlistTabs(attention);
    const symbols = derive.symbolsForWatchlist(state.symbols, state.groups, state.selectedGroupId);
    const currentAttention = scopedAttention();
    const group = selectedGroup();
    const title = group ? group.name.toUpperCase() : "ALL GROUPS";
    const eventCounts = (type) => currentAttention.filter((event) => event.event_type === type).length;
    const pressureCount = symbols.filter((symbol) => (pressureBySymbol().get(symbol.symbol)?.direction || "neutral") !== "neutral").length;
    $("#watchlistSummary").replaceChildren(
      summaryCell(title, `${symbols.length} symbols`, group ? "Trading watchlist" : `${state.groups.length} watchlists`),
      summaryCell("ACTIVE MRZ", symbols.filter((item) => item.mrz_status === "active").length, "Current authority"),
      summaryCell("NEW MRZ", eventCounts("MRZ_ACTIVATED"), "Last 24 hours"),
      summaryCell("MIGRATION", eventCounts("MRZ_MIGRATED"), "Last 24 hours"),
      summaryCell("PRESSURE WATCHES", pressureCount, "Canonical direction"),
    );
    $("#watchlistAttentionHeading").textContent = title;
    $("#watchlistAttention").replaceChildren(eventList(currentAttention, { limit: 8 }));
    renderPeerContext(group);
    renderSymbolBoard(symbols);
    $("#editWatchlistButton").hidden = !group;
  }
  function summaryCell(label, value, support) {
    const cell = element("div", "");
    cell.append(element("span", "", label), element("strong", "", String(value)), element("small", "", support));
    return cell;
  }

  function peerCountButton(label, count, support, selected, onClick, disabled = false) {
    const button = element("button", "peer-count-button");
    button.type = "button";
    button.disabled = disabled;
    button.setAttribute("aria-expanded", String(selected));
    button.append(
      element("span", "", label),
      element("strong", "", String(count)),
      element("small", "", support),
    );
    button.addEventListener("click", onClick);
    return button;
  }

  function selectPeerDetail(type, key, label) {
    state.peerSelection = { type, key, label };
    renderPeerContext(selectedGroup());
    $("#peerContextDrilldown").scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  }

  function renderPeerContext(group) {
    const content = $("#peerContextContent");
    document.querySelectorAll("[data-peer-window]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.peerWindow === state.peerWindow));
    });
    if (!group) {
      $("#peerContextHeading").textContent = "Select one watchlist";
      $("#peerContextStatus").textContent = state.groups.length
        ? "Choose a named watchlist tab to inspect peer context."
        : "Create a watchlist to inspect peer context.";
      content.hidden = true;
      return;
    }
    content.hidden = false;
    $("#peerContextHeading").textContent = group.name;
    const loaded = state.peerContextKey === `${group.id}:${state.peerWindow}`;
    $("#peerContextStatus").textContent = loaded ? "" : `Loading ${state.peerWindow} peer context…`;

    const hasCurrentState = Boolean(group.current_state?.members);
    const locations = hasCurrentState ? derive.derivePeerLocation(group) : [];
    const locationTarget = $("#peerLocation"); locationTarget.replaceChildren();
    if (!hasCurrentState) locationTarget.append(empty("Loading current peer locations…"));
    locations.forEach(({ key, members }) => {
      const label = key === "unavailable" ? "Unavailable" : locationLabels[key];
      locationTarget.append(peerCountButton(
        label,
        members.length,
        `${members.length} of ${group.member_count}`,
        state.peerSelection?.type === "location" && state.peerSelection.key === key,
        () => selectPeerDetail("location", key, label),
        !hasCurrentState,
      ));
    });

    const flow = loaded
      ? derive.derivePeerLocationFlow(
        state.peerLocationHistory,
        group.members,
        state.symbolPayload?.pressure || {},
      )
      : { counts: { higher: 0, lower: 0, unchanged: 0 }, comparable: 0, categories: {} };
    $("#peerLocationFlowHeading").textContent = `Structural movement · ${state.peerWindow}`;
    $("#peerLocationFlowCoverage").textContent = loaded
      ? `${flow.comparable} of ${group.member_count} comparable members`
      : "Loading comparable members";
    const flowTarget = $("#peerLocationFlow"); flowTarget.replaceChildren();
    [
      ["higher", "↑ Moved Higher"],
      ["lower", "↓ Moved Lower"],
      ["unchanged", "↔ Unchanged"],
    ].forEach(([key, label]) => flowTarget.append(peerCountButton(
      label,
      flow.counts[key] || 0,
      `${state.peerWindow} start → current`,
      state.peerSelection?.type === "flow" && state.peerSelection.key === key,
      () => selectPeerDetail("flow", key, label),
      !loaded,
    )));

    const recent = loaded ? state.peerPressure : null;
    $("#peerPressureHeading").textContent = `Recent directional pressure · ${state.peerWindow}`;
    const pressureTarget = $("#peerPressure"); pressureTarget.replaceChildren();
    [
      ["higher", "↑ Higher pressure"],
      ["lower", "↓ Lower pressure"],
      ["none", "— No recent directional pressure"],
    ].forEach(([key, label]) => pressureTarget.append(peerCountButton(
      label,
      recent?.counts?.[key] || 0,
      key === "none" ? "No directional event in window" : "Latest event per member",
      state.peerSelection?.type === "pressure" && state.peerSelection.key === key,
      () => selectPeerDetail("pressure", key, label),
      !loaded,
    )));
    renderPeerContextDrilldown(group, locations, flow, recent);
  }

  function renderPeerContextDrilldown(group, locations, flow, recent) {
    const panel = $("#peerContextDrilldown");
    const selection = state.peerSelection;
    if (!selection) { panel.hidden = true; $("#peerContextMembers").replaceChildren(); return; }
    let members = [];
    if (selection.type === "location") {
      members = locations.find((item) => item.key === selection.key)?.members || [];
    } else if (selection.type === "flow") {
      members = flow.categories?.[selection.key] || [];
    } else if (selection.type === "pressure") {
      members = recent?.categories?.[selection.key] || [];
    }
    panel.hidden = false;
    $("#peerContextDrilldownHeading").textContent = `${selection.label} · ${members.length}`;
    $("#peerContextDrilldownSupport").textContent = selection.type === "location"
      ? `${group.name} · current canonical state`
      : `${group.name} · ${state.peerWindow}`;
    const target = $("#peerContextMembers"); target.replaceChildren();
    if (!members.length) { target.append(empty("No members in this selection.")); return; }
    members.forEach((member) => {
      const item = element("li", "peer-context-member");
      const heading = element("div", "peer-context-member-heading");
      heading.append(symbolLink(member.symbol, member.symbol));
      const context = element("div", "peer-context-member-body");
      if (selection.type === "location") {
        context.append(
          element("span", "", member.current_location ? locationLabels[member.current_location] : "Location unavailable"),
          element("span", "", `Route · ${member.route_owner || "—"}`),
          element("span", "", member.has_active_mrz ? "Active MRZ" : "No active MRZ"),
        );
      } else if (selection.type === "flow") {
        const signed = member.direction === "higher" ? `+${member.magnitude}` : member.direction === "lower" ? `-${member.magnitude}` : "0";
        const migrations = member.migrationEvents || [];
        const migration = migrations.length
          ? [...new Set(migrations.map((event) => event.direction === "higher" ? "↑" : "↓"))].join(" / ")
          : "—";
        context.append(
          element("strong", "", `${member.start_location_label} → ${member.current_location_label}`),
          element("span", "", `${signed} bucket${Number(member.magnitude) === 1 ? "" : "s"} · ${member.direction}`),
          element("span", `pressure-${member.pressure}`, `Current pressure · ${pressureLabels[member.pressure] || pressureLabels.neutral}`),
          element("span", "", `MRZ migration · ${migration}`),
        );
      } else {
        const event = member.latest_event;
        context.append(
          element("span", "", event ? `Latest directional · ${member.recent_direction === "higher" ? "↑ Higher" : "↓ Lower"} · ${relativeTime(event.occurred_at)}` : "Latest directional · —"),
          element("span", `pressure-${member.current_pressure}`, `Current pressure · ${pressureLabels[member.current_pressure] || pressureLabels.neutral}`),
          element("span", "", `Location · ${member.current_location_label || "Unavailable"}`),
          element("span", "", `Route · ${member.route_owner || "—"}`),
        );
        if (event?.occurred_at) {
          const time = element("time", "", exactTime(event.occurred_at));
          time.dateTime = event.occurred_at;
          context.append(time);
        }
      }
      item.append(heading, context); target.append(item);
    });
  }
  function renderSymbolBoard(symbols) {
    const pressure = pressureBySymbol();
    const latest = latestEvents();
    const body = $("#watchlistBoard");
    body.replaceChildren();
    if (symbols.length === 0) {
      const row = element("tr", "");
      const cell = element("td", "", "No symbols in this watchlist scope.");
      cell.colSpan = 8;
      row.append(cell); body.append(row); return;
    }
    const rows = symbols
      .map((symbol) => derive.currentAuthorityRow(symbol, pressure.get(symbol.symbol), latest.get(symbol.symbol)))
    const sorted = derive.sortSymbolBoardRows(rows, state.symbolBoardSort);
    const select = $("#symbolBoardSort");
    if (select) select.value = state.symbolBoardSort;
    const groups = state.symbolBoardSort === "attention"
      ? derive.groupSymbolBoardRows(sorted)
      : [{ key: null, label: null, rows: sorted }];
    groups.forEach((group) => {
      if (group.label) {
        const heading = element("tr", "symbol-board-group-row");
        const cell = element("th", "", group.label);
        cell.colSpan = 8;
        cell.scope = "rowgroup";
        heading.append(cell);
        body.append(heading);
      }
      group.rows.forEach((item) => {
        const row = element("tr", item.latestEvent || item.pressure !== "neutral" ? "" : "quiet");
        const symbolCell = element("td", "");
        const button = element("button", "symbol-button", item.symbol);
        button.type = "button";
        button.addEventListener("click", () => { globalObject.location.href = `/mrz/symbols?symbol=${encodeURIComponent(item.symbol)}`; });
        symbolCell.append(button);
        const activated = element("td", "", relativeTime(item.activatedAt));
        activated.title = exactTime(item.activatedAt);
        const event = item.latestEvent ? `${derive.eventLabel(item.latestEvent)} · ${relativeTime(item.latestEvent.occurred_at)}` : "—";
        row.append(
          symbolCell,
          element("td", item.active ? "active-state" : "inactive-state", item.active ? "● ACTIVE" : "—"),
          element("td", "", item.active ? `${formatPrice(item.lower)}–${formatPrice(item.upper)}` : "—"),
          element("td", "", item.route || "—"), activated,
          element("td", "", locationLabels[item.location] || "—"),
          element("td", `pressure-${item.pressure}`, pressureLabels[item.pressure] || pressureLabels.neutral),
          element("td", "", event),
        );
        body.append(row);
      });
    });
  }

  function renderAttention(attention) {
    $("#attentionQueue").replaceChildren(eventList(attention));
    const badge = $("#navAttentionCount");
    badge.textContent = String(attention.length);
    badge.hidden = attention.length === 0;
  }

  function renderSymbolOptions() {
    const select = $("#symbolSelect");
    select.replaceChildren(new Option("Select a symbol", ""), ...state.symbols.map((item) => new Option(item.symbol, item.symbol)));
    const symbol = new URLSearchParams(globalObject.location.search).get("symbol") || "";
    if (symbol && state.symbols.some((item) => item.symbol === symbol)) {
      select.value = symbol;
      loadSymbolDetail(symbol);
    }
  }
  async function loadSymbolDetail(symbol) {
    if (!symbol) { $("#symbolEmpty").hidden = false; $("#symbolDetail").hidden = true; return; }
    const response = await fetch(`/api/symbols/${encodeURIComponent(symbol)}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Unable to load ${symbol}.`);
    const detail = await response.json();
    const event = latestEvents().get(symbol);
    const pressure = pressureBySymbol().get(symbol);
    const pressureSource = pressureSourceBySymbol().get(symbol) || {};
    const pressurePresentation = derive.pressureDetailPresentation({
      ...pressureSource,
      direction: pressure?.direction || "neutral",
    });
    $("#symbolEmpty").hidden = true; $("#symbolDetail").hidden = false;
    $("#detailSymbol").textContent = symbol;
    $("#detailStatus").textContent = detail.mrz_status === "active" ? "● ACTIVE" : "NO ACTIVE MRZ";
    $("#detailRange").textContent = detail.mrz_status === "active" ? `${formatPrice(detail.core_mrz_lower)}–${formatPrice(detail.core_mrz_upper)}` : "No current authority";
    $("#detailMeta").replaceChildren(
      element("span", "", `Route · ${detail.route_owner || "—"}`),
      element("span", "", `Activated · ${exactTime(detail.activated_at)}`),
      element("span", "", `Location · ${locationLabels[detail.structural_location] || "—"}`),
    );
    if (detail.migration?.has_migrated) {
      $("#detailPrevious").replaceChildren(element("strong", "", `${formatPrice(detail.migration.previous_lower)}–${formatPrice(detail.migration.previous_upper)}`), element("span", "", `Previous authority · ${detail.migration.direction === "UP" ? "migrated upward" : "migrated downward"}`), element("span", "", exactTime(detail.migration.previous_activated_at)));
    } else $("#detailPrevious").textContent = "No previous migrated authority for the current lifecycle.";
    if (event) $("#detailLatestEvent").replaceChildren(element("strong", "", derive.eventLabel(event)), element("span", "", exactTime(event.occurred_at)), element("span", "", event.body || ""));
    else $("#detailLatestEvent").textContent = "No recent canonical event.";
    const direction = pressurePresentation.current.direction;
    const latestDirectional = pressurePresentation.latest;
    $("#detailPressure").replaceChildren(
      element("strong", `pressure-${direction}`, `Current pressure · ${pressureLabels[direction]}`),
      element("span", "", pressure?.evidence?.label || "Canonical current pressure"),
      element("span", latestDirectional ? `pressure-${latestDirectional.direction}` : "", latestDirectional
        ? `Latest directional · ${pressureLabels[latestDirectional.direction]} · ${relativeTime(latestDirectional.occurred_at)}`
        : "Latest directional · —"),
      ...(latestDirectional?.occurred_at ? [element("time", "", exactTime(latestDirectional.occurred_at))] : []),
    );
  }

  function syncLocationUrl() {
    if (routeName() !== "location-distribution") return;
    const url = new URL(globalObject.location.href);
    url.searchParams.set("window", state.locationWindow);
    url.searchParams.set("taxonomy_level", state.locationTaxonomyLevel);
    url.searchParams.set("view", state.locationTaxonomyMode);
    url.searchParams.set("sort", state.locationTaxonomySort);
    if (state.locationTaxonomySelection) url.searchParams.set("taxonomy", state.locationTaxonomySelection); else url.searchParams.delete("taxonomy");
    if (state.locationFlowSelection) url.searchParams.set("transition", state.locationFlowSelection); else url.searchParams.delete("transition");
    globalObject.history.replaceState({}, "", url);
  }

  function restoreLocationStateFromUrl() {
    const params = new URLSearchParams(globalObject.location.search);
    if (["24H", "5D", "20D"].includes(params.get("window"))) state.locationWindow = params.get("window");
    if (["asset_class", "sector", "industry"].includes(params.get("taxonomy_level"))) state.locationTaxonomyLevel = params.get("taxonomy_level");
    if (["movement", "all"].includes(params.get("view"))) state.locationTaxonomyMode = params.get("view");
    if (["lower", "higher", "lower_pct", "higher_pct", "name"].includes(params.get("sort"))) state.locationTaxonomySort = params.get("sort");
    state.locationTaxonomySelection = params.get("taxonomy") || null;
    state.locationFlowSelection = params.get("transition") || null;
  }

  function renderLocationDistribution() {
    document.querySelectorAll("[data-location-window]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.locationWindow === state.locationWindow));
    });
    if (!state.locationHistory) return;
    const history = state.locationHistory;
    const coverage = history.coverage || {};
    const fullReport = derive.deriveLocationTransitionHeatmap(history);
    const coverageCards = $("#locationCoverageCards"); coverageCards.replaceChildren();
    [
      ["Eligible", coverage.total_eligible ?? history.universe?.now_eligible ?? 0],
      ["Comparable", coverage.comparable_symbols ?? fullReport.totals.comparable],
      ["New observations", coverage.comparable_with_new_observation ?? 0],
    ].forEach(([label, value]) => {
      const card = element("article", ""); card.append(element("span", "", label), element("strong", "", String(value))); coverageCards.append(card);
    });
    const strip = $("#locationCoverageStrip"); strip.replaceChildren();
    [
      ["Comparison", exactTime(history.comparison_at)],
      ["Current", exactTime(history.current_at)],
      ["No new observations", coverage.comparable_without_new_observation ?? 0],
      ["Unavailable / incomparable", coverage.unavailable_or_incomparable ?? 0],
    ].forEach(([label, value]) => {
      const item = element("div", ""); item.append(element("dt", "", label), element("dd", "", String(value))); strip.append(item);
    });
    $("#locationTaxonomyWindow").textContent = state.locationWindow;
    $("#locationFlowWindow").textContent = state.locationWindow;
    const levelSelect = $("#locationTaxonomyLevel"); if (levelSelect.value !== state.locationTaxonomyLevel) levelSelect.value = state.locationTaxonomyLevel;
    const sortSelect = $("#locationTaxonomySort"); if (sortSelect.value !== state.locationTaxonomySort) sortSelect.value = state.locationTaxonomySort;
    document.querySelectorAll("[data-taxonomy-mode]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.taxonomyMode === state.locationTaxonomyMode)));
    const overview = derive.deriveLocationTaxonomyOverview(history, state.symbols, {
      level: state.locationTaxonomyLevel, mode: state.locationTaxonomyMode, sort: state.locationTaxonomySort,
    });
    const selectedExists = overview.groups.some((group) => group.name === state.locationTaxonomySelection);
    if (!selectedExists) state.locationTaxonomySelection = overview.groups[0]?.name || null;
    const statusBits = [`${overview.groups.length} of ${overview.totalTaxonomies} taxonomies shown`];
    if (overview.unclassifiedComparable) statusBits.push(`${overview.unclassifiedComparable} comparable symbol${overview.unclassifiedComparable === 1 ? "" : "s"} lack ${state.locationTaxonomyLevel.replace("_", " ")} metadata`);
    if (overview.unknownDirectionComparable) statusBits.push(`${overview.unknownDirectionComparable} comparable symbol${overview.unknownDirectionComparable === 1 ? " has" : "s have"} unknown canonical direction`);
    $("#locationTaxonomyStatus").textContent = statusBits.join(" · ");
    const cards = $("#locationTaxonomyCards"); cards.replaceChildren();
    if (!overview.groups.length) cards.append(empty(state.locationTaxonomyMode === "movement" ? "No classified taxonomies moved in this window." : "No classified taxonomies are available."));
    overview.groups.forEach((group) => cards.append(locationTaxonomyCard(group)));
    const flowReport = derive.deriveLocationTaxonomyFlow(history, state.symbols, state.locationTaxonomyLevel, state.locationTaxonomySelection);
    if (state.locationFlowSelection && !flowReport.cells.some((cell) => cell.key === state.locationFlowSelection && cell.count)) state.locationFlowSelection = null;
    renderLocationFlow(flowReport);
    renderLocationContributors(flowReport);
    syncLocationUrl();
  }

  function locationTaxonomyCard(group) {
    const button = element("button", "location-taxonomy-card");
    button.type = "button";
    button.setAttribute("aria-pressed", String(group.name === state.locationTaxonomySelection));
    button.setAttribute("aria-label", `${group.name}: ${group.comparable} comparable; ${group.lower} moved lower, ${group.unchanged} same bucket, ${group.higher} moved higher.`);
    const heading = element("span", "location-taxonomy-card-heading"); heading.append(element("strong", "", group.name), element("small", "", `${group.comparable} comparable`));
    const bar = element("span", "location-taxonomy-bar");
    [["lower", group.lower], ["unchanged", group.unchanged], ["higher", group.higher]].forEach(([direction, count]) => {
      const segment = element("i", direction); segment.style.flexGrow = String(count); segment.hidden = count === 0; bar.append(segment);
    });
    const percentage = (share) => share === null ? "—" : `${Math.round(share * 100)}%`;
    const counts = element("span", "location-taxonomy-counts");
    counts.append(
      element("span", "lower", `↓ ${group.lower} lower (${percentage(group.lower_share)})`),
      element("span", "same", `${group.unchanged} same`),
      element("span", "higher", `↑ ${group.higher} higher (${percentage(group.higher_share)})`),
    );
    button.append(heading, bar, counts);
    button.addEventListener("click", () => {
      state.locationTaxonomySelection = group.name;
      state.locationFlowSelection = null;
      renderLocationDistribution();
    });
    return button;
  }

  function renderLocationFlow(report) {
    const name = state.locationTaxonomySelection || "No taxonomy selected";
    $("#locationFlowScope").textContent = state.locationTaxonomySelection
      ? `${name} · ${report.totals.comparable} comparable symbol${report.totals.comparable === 1 ? "" : "s"}`
      : "Select a taxonomy to inspect its endpoint flow.";
    $("#locationFlowLower").textContent = String(report.totals.lower);
    $("#locationFlowSame").textContent = String(report.totals.unchanged);
    $("#locationFlowHigher").textContent = String(report.totals.higher);
    const canvas = $("#locationFlowCanvas");
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "#0b0f14"; context.fillRect(0, 0, canvas.width, canvas.height);
    const displayBuckets = [...report.buckets].reverse();
    const rowY = new Map(displayBuckets.map((bucket, index) => [bucket.key, 76 + index * 61]));
    const leftX = 26; const rightX = 655; const nodeWidth = 178; const nodeHeight = 42;
    context.fillStyle = "#edf3fa"; context.font = "700 12px Inter, system-ui, sans-serif";
    context.fillText("PREVIOUS", leftX + 8, 28); context.fillText("CURRENT", rightX + 8, 28);
    locationFlowPaths = [];
    const visibleCells = report.cells.filter((cell) => cell.count).sort((left, right) => left.direction.localeCompare(right.direction) || right.count - left.count);
    const maximum = Math.max(1, ...visibleCells.map((cell) => cell.count));
    visibleCells.forEach((cell) => {
      const startY = rowY.get(cell.fromKey); const endY = rowY.get(cell.toKey);
      const path = new Path2D(); path.moveTo(leftX + nodeWidth, startY); path.bezierCurveTo(355, startY, 505, endY, rightX, endY);
      const selected = state.locationFlowSelection === cell.key;
      const colors = { lower: "#d46c7b", unchanged: "#8f99a8", higher: "#4fc6a6" };
      const lineWidth = 4 + (cell.count / maximum) * 17;
      context.save(); context.strokeStyle = colors[cell.direction]; context.globalAlpha = selected ? 1 : .72; context.lineCap = "round"; context.lineWidth = lineWidth; context.stroke(path); context.restore();
      locationFlowPaths.push({ path, cell, lineWidth: lineWidth + 10 });
    });
    const previousCounts = new Map(); const currentCounts = new Map();
    displayBuckets.forEach((bucket) => { previousCounts.set(bucket.key, 0); currentCounts.set(bucket.key, 0); });
    visibleCells.forEach((cell) => { previousCounts.set(cell.fromKey, previousCounts.get(cell.fromKey) + cell.count); currentCounts.set(cell.toKey, currentCounts.get(cell.toKey) + cell.count); });
    displayBuckets.forEach((bucket) => {
      const y = rowY.get(bucket.key) - nodeHeight / 2;
      [[leftX, previousCounts.get(bucket.key)], [rightX, currentCounts.get(bucket.key)]].forEach(([x, count]) => {
        context.fillStyle = "#172231"; context.strokeStyle = "#39506d"; context.lineWidth = 1;
        context.beginPath(); context.roundRect(x, y, nodeWidth, nodeHeight, 7); context.fill(); context.stroke();
        context.fillStyle = "#edf3fa"; context.font = "600 12px Inter, system-ui, sans-serif"; context.fillText(bucket.label, x + 11, y + 17);
        context.fillStyle = "#bac5d3"; context.font = "12px Inter, system-ui, sans-serif"; context.fillText(`${count} symbol${count === 1 ? "" : "s"}`, x + 11, y + 34);
      });
    });
    const targets = $("#locationFlowTargets"); targets.replaceChildren();
    visibleCells.forEach((cell) => {
      const button = element("button", "visually-hidden", `${cell.fromLabel} to ${cell.toLabel}: ${cell.count} symbols`);
      button.type = "button"; button.setAttribute("aria-pressed", String(state.locationFlowSelection === cell.key));
      button.addEventListener("click", () => selectLocationFlow(cell)); targets.append(button);
    });
  }

  function selectLocationFlow(cell) {
    state.locationFlowSelection = cell.key;
    renderLocationDistribution();
    $("#locationContributorsHeading")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function renderLocationContributors(report) {
    const cell = report.cells.find((item) => item.key === state.locationFlowSelection && item.count);
    const target = $("#locationContributorRows"); target.replaceChildren();
    if (!cell) {
      $("#locationContributorScope").textContent = "Select a flow to reveal its exact underlying symbols.";
      const row = element("tr", ""); const data = element("td", "location-contributors-empty", "No flow selected."); data.colSpan = 5; row.append(data); target.append(row); return;
    }
    const members = cell.members;
    $("#locationContributorScope").textContent = `${cell.fromLabel} → ${cell.toLabel} · ${cell.count} symbol${cell.count === 1 ? "" : "s"}`;
    members.forEach((item) => {
      const row = element("tr", "");
      const symbol = element("td", "", item.symbol); symbol.dataset.label = "Symbol";
      const previous = element("td", "", item.start_location_label || "—"); previous.dataset.label = "Previous";
      const current = element("td", "", item.current_location_label || "—"); current.dataset.label = "Current";
      const freshness = element("td", ""); freshness.dataset.label = "Observation freshness";
      freshness.append(element("strong", item.has_new_observation ? "is-fresh" : "", item.has_new_observation ? `New observation inside ${state.locationWindow}` : `No new observation inside ${state.locationWindow}`), element("small", "", `${exactTime(item.comparison_observed_at)} → ${exactTime(item.current_observed_at)}`));
      const open = element("td", ""); open.append(symbolLink(item.symbol, "Open details"));
      row.append(symbol, previous, current, freshness, open); target.append(row);
    });
  }
  async function loadLocationHistory(window) {
    state.locationWindow = window;
    state.locationFlowSelection = null;
    $("#locationTaxonomyStatus").textContent = `Loading ${window} canonical history…`;
    document.querySelectorAll("[data-location-window]").forEach((button) => {
      button.disabled = true;
      button.setAttribute("aria-pressed", String(button.dataset.locationWindow === window));
    });
    try {
      const response = await fetch(`/api/location-distribution/history?window=${encodeURIComponent(window)}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Unable to load canonical location history.");
      state.locationHistory = await response.json();
      renderLocationDistribution();
    } catch (error) {
      $("#locationTaxonomyStatus").textContent = error.message || "Unable to load canonical location history.";
    } finally {
      document.querySelectorAll("[data-location-window]").forEach((button) => { button.disabled = false; });
    }
  }
  function summaryArticle(label, value) { const node = element("article", ""); node.append(element("span", "", label), element("strong", "", String(value))); return node; }
  async function loadPeerContext() {
    const group = selectedGroup();
    if (!group) { renderPeerContext(null); return; }
    const key = `${group.id}:${state.peerWindow}`;
    state.peerContextKey = null;
    renderPeerContext(group);
    const [groupResponse, historyResponse, pressureResponse] = await Promise.all([
      fetch(`/api/groups/${encodeURIComponent(group.id)}`, { cache: "no-store" }),
      fetch(`/api/location-distribution/history?window=${encodeURIComponent(state.peerWindow)}`, { cache: "no-store" }),
      fetch(`/api/groups/${encodeURIComponent(group.id)}/peer-pressure?window=${encodeURIComponent(state.peerWindow)}`, { cache: "no-store" }),
    ]);
    if (!groupResponse.ok || !historyResponse.ok || !pressureResponse.ok) throw new Error("Unable to load peer context.");
    const [groupReport, history, pressure] = await Promise.all([
      groupResponse.json(), historyResponse.json(), pressureResponse.json(),
    ]);
    if (`${selectedGroup()?.id}:${state.peerWindow}` !== key) return;
    state.groups = state.groups.map((item) => (
      String(item.id) === String(groupReport.id) ? groupReport : item
    ));
    state.peerLocationHistory = history;
    state.peerPressure = pressure;
    state.peerContextKey = key;
    renderPeerContext(selectedGroup());
  }

  function renderEvents() {
    const filter = $("#eventTypeFilter").value;
    const events = filter === "all" ? state.events : state.events.filter((event) => event.event_type === filter);
    $("#eventsList").replaceChildren(eventList(events, { showGroups: false }));
  }

  function openWatchlistDialog(group = null) {
    state.editingGroupId = group?.id || null;
    $("#watchlistDialogTitle").textContent = group ? `Edit ${group.name}` : "New watchlist";
    $("#watchlistName").value = group?.name || "";
    $("#deleteWatchlistButton").hidden = !group;
    $("#watchlistFormError").hidden = true;
    const selected = new Set(group?.members || []);
    const choices = $("#watchlistSymbolChoices"); choices.replaceChildren();
    state.symbols.forEach((symbol) => {
      const label = element("label", ""); const input = document.createElement("input"); input.type = "checkbox"; input.value = symbol.symbol; input.checked = selected.has(symbol.symbol); label.append(input, document.createTextNode(symbol.symbol)); choices.append(label);
    });
    $("#watchlistDialog").showModal();
  }
  async function saveWatchlist(event) {
    event.preventDefault();
    if (event.submitter?.value === "cancel") { $("#watchlistDialog").close(); return; }
    const members = [...document.querySelectorAll("#watchlistSymbolChoices input:checked")].map((input) => input.value);
    const payload = { name: $("#watchlistName").value.trim(), members };
    if (!payload.name || members.length === 0) { $("#watchlistFormError").textContent = "Add a name and at least one symbol."; $("#watchlistFormError").hidden = false; return; }
    const editing = state.editingGroupId !== null;
    const url = editing ? `/api/groups/${state.editingGroupId}` : "/api/groups";
    const response = await fetch(url, { method: editing ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!response.ok) { const body = await response.json().catch(() => ({})); $("#watchlistFormError").textContent = body.detail || "Unable to save watchlist."; $("#watchlistFormError").hidden = false; return; }
    const saved = await response.json();
    state.selectedGroupId = String(saved.id);
    $("#watchlistDialog").close();
    await refreshGroups();
  }
  async function deleteWatchlist() {
    const group = selectedGroup();
    if (!group || !globalObject.confirm(`Delete ${group.name}? Canonical EDGE events and symbol monitoring are unaffected.`)) return;
    const response = await fetch(`/api/groups/${group.id}`, { method: "DELETE" });
    if (!response.ok) throw new Error("Unable to delete watchlist.");
    $("#watchlistDialog").close(); state.selectedGroupId = "all"; await refreshGroups();
  }
  async function refreshGroups() {
    const response = await fetch("/api/groups", { cache: "no-store" });
    if (!response.ok) throw new Error("Unable to load watchlists.");
    state.groups = (await response.json()).groups || [];
    if (state.groups.length === 1 && state.selectedGroupId === "all") state.selectedGroupId = String(state.groups[0].id);
    renderAll();
    await loadPeerContext();
  }

  function renderPreferences() {
    const prefs = state.preferences;
    if (!prefs) return;
    const scope = document.querySelector(`input[name="alertScope"][value="${prefs.alert_scope}"]`);
    if (scope) scope.checked = true;
    $("#prefActivation").checked = prefs.activation_enabled;
    $("#prefMigration").checked = prefs.migration_enabled;
    $("#prefPressure").checked = prefs.pressure_enabled;
    $("#prefNearMiss").checked = prefs.near_miss_enabled;
    $("#alertScopeLabel").textContent = prefs.alert_scope === "TRACKED_GROUPS_ONLY" ? "Alerts: Tracked Groups" : "Alerts: All Symbols";
  }
  async function savePreferences(event) {
    event.preventDefault();
    $("#alertPreferencesError").hidden = true;
    $("#alertPreferencesSaved").textContent = "";
    const selectedScope = document.querySelector('input[name="alertScope"]:checked');
    const payload = { alert_scope: selectedScope?.value || "ALL_SYMBOLS", activation_enabled: $("#prefActivation").checked, migration_enabled: $("#prefMigration").checked, pressure_enabled: $("#prefPressure").checked, near_miss_enabled: $("#prefNearMiss").checked };
    const response = await fetch("/api/notifications/preferences", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!response.ok) { $("#alertPreferencesError").textContent = "Unable to save alert preferences."; $("#alertPreferencesError").hidden = false; return; }
    state.preferences = await response.json(); renderPreferences(); $("#alertPreferencesSaved").textContent = "Preferences saved.";
  }

  function renderAll() {
    const attention = derive.deriveAttention(state.events, state.groups);
    renderOverview(attention); renderAttention(attention); renderSymbolOptions(); renderLocationDistribution(); renderEvents(); renderPreferences();
  }
  async function initialize() {
    activateRoute();
    if (routeName() === "location-distribution") restoreLocationStateFromUrl();
    if (routeName() === "watchlists") {
      await globalObject.edgeGroupEvidence.mount();
      $("#workspaceStatus").hidden = true;
      return;
    }
    try {
      const needsLocationHistory = routeName() === "location-distribution";
      const [symbolsResponse, groupsResponse, eventsResponse, preferencesResponse, locationHistoryResponse] = await Promise.all([
        fetch("/api/symbols", { cache: "no-store" }), fetch("/api/groups", { cache: "no-store" }), fetch("/api/mrz/events?limit=500", { cache: "no-store" }), fetch("/api/notifications/preferences", { cache: "no-store" }), needsLocationHistory ? fetch(`/api/location-distribution/history?window=${state.locationWindow}`, { cache: "no-store" }) : Promise.resolve(null),
      ]);
      if (![symbolsResponse, groupsResponse, eventsResponse, preferencesResponse, locationHistoryResponse].filter(Boolean).every((response) => response.ok)) throw new Error("One or more MRZ workspace sources are unavailable.");
      state.symbolPayload = await symbolsResponse.json(); state.symbols = state.symbolPayload.symbols || [];
      state.groups = (await groupsResponse.json()).groups || [];
      state.events = (await eventsResponse.json()).events || [];
      state.preferences = await preferencesResponse.json();
      state.locationHistory = locationHistoryResponse ? await locationHistoryResponse.json() : null;
      if (state.groups.length === 1) state.selectedGroupId = String(state.groups[0].id);
      renderAll();
      if (routeName() === "watchlists") await loadPeerContext();
      $("#workspaceStatus").hidden = true;
    } catch (error) { $("#workspaceStatus").textContent = error.message || "Unable to load MRZ workspace."; $("#workspaceStatus").classList.add("error"); }
  }

  $("#newWatchlistButton")?.addEventListener("click", () => openWatchlistDialog());
  $("#editWatchlistButton")?.addEventListener("click", () => openWatchlistDialog(selectedGroup()));
  $("#watchlistForm")?.addEventListener("submit", (event) => saveWatchlist(event).catch(showError));
  $("#deleteWatchlistButton")?.addEventListener("click", () => deleteWatchlist().catch(showError));
  $("#symbolSelect")?.addEventListener("change", (event) => {
    const symbol = event.target.value;
    const url = new URL(globalObject.location.href); if (symbol) url.searchParams.set("symbol", symbol); else url.searchParams.delete("symbol"); globalObject.history.replaceState({}, "", url); loadSymbolDetail(symbol).catch(showError);
  });
  document.querySelectorAll("[data-peer-window]").forEach((button) => button.addEventListener("click", () => {
    state.peerWindow = button.dataset.peerWindow;
    state.peerSelection = null;
    loadPeerContext().catch(showError);
  }));
  $("#peerContextDrilldownClose")?.addEventListener("click", () => {
    state.peerSelection = null;
    renderPeerContext(selectedGroup());
  });
  $("#symbolBoardSort")?.addEventListener("change", (event) => {
    state.symbolBoardSort = derive.persistSymbolBoardSort(
      globalObject.localStorage,
      event.target.value,
    );
    renderSymbolBoard(
      derive.symbolsForWatchlist(state.symbols, state.groups, state.selectedGroupId),
    );
  });
  document.querySelectorAll("[data-location-window]").forEach((button) => button.addEventListener("click", () => loadLocationHistory(button.dataset.locationWindow)));
  document.querySelectorAll("[data-taxonomy-mode]").forEach((button) => button.addEventListener("click", () => {
    state.locationTaxonomyMode = button.dataset.taxonomyMode;
    renderLocationDistribution();
  }));
  $("#locationTaxonomyLevel")?.addEventListener("change", (event) => {
    state.locationTaxonomyLevel = event.target.value; state.locationTaxonomySelection = null; state.locationFlowSelection = null; renderLocationDistribution();
  });
  $("#locationTaxonomySort")?.addEventListener("change", (event) => {
    state.locationTaxonomySort = event.target.value; renderLocationDistribution();
  });
  $("#locationFlowCanvas")?.addEventListener("mousemove", (event) => {
    const canvas = event.currentTarget; const bounds = canvas.getBoundingClientRect();
    const x = (event.clientX - bounds.left) * canvas.width / bounds.width; const y = (event.clientY - bounds.top) * canvas.height / bounds.height;
    const context = canvas.getContext("2d");
    const hit = [...locationFlowPaths].reverse().find((item) => { context.lineWidth = item.lineWidth; return context.isPointInStroke(item.path, x, y); });
    canvas.style.cursor = hit ? "pointer" : "default";
    const tooltip = $("#locationFlowTooltip");
    if (!hit) { tooltip.hidden = true; return; }
    tooltip.textContent = `${hit.cell.fromLabel} → ${hit.cell.toLabel} · ${hit.cell.count} symbol${hit.cell.count === 1 ? "" : "s"}`;
    tooltip.style.left = `${event.clientX - bounds.left + 12}px`; tooltip.style.top = `${event.clientY - bounds.top + 12}px`; tooltip.hidden = false;
  });
  $("#locationFlowCanvas")?.addEventListener("mouseleave", () => { $("#locationFlowTooltip").hidden = true; });
  $("#locationFlowCanvas")?.addEventListener("click", (event) => {
    const canvas = event.currentTarget; const bounds = canvas.getBoundingClientRect();
    const x = (event.clientX - bounds.left) * canvas.width / bounds.width; const y = (event.clientY - bounds.top) * canvas.height / bounds.height;
    const context = canvas.getContext("2d");
    const hit = [...locationFlowPaths].reverse().find((item) => { context.lineWidth = item.lineWidth; return context.isPointInStroke(item.path, x, y); });
    if (hit) selectLocationFlow(hit.cell);
  });
  $("#eventTypeFilter")?.addEventListener("change", renderEvents);
  $("#alertPreferencesForm")?.addEventListener("submit", (event) => savePreferences(event).catch(showError));
  function showError(error) { $("#workspaceStatus").hidden = false; $("#workspaceStatus").textContent = error.message || "The request could not be completed."; $("#workspaceStatus").classList.add("error"); }
  document.addEventListener("DOMContentLoaded", initialize, { once: true });
}(globalThis));
