(function initializeMrzWorkspace(globalObject) {
  "use strict";

  const derive = globalObject.edgeWorkspaceDerivations;
  const { migrationTendencyPresentation } = globalObject.edgeHeatmapState;
  const state = {
    symbols: [],
    symbolPayload: null,
    groups: [],
    events: [],
    preferences: null,
    locationHistory: null,
    locationWindow: "24H",
    locationFlowSelection: null,
    locationFlowPressure: "all",
    selectedGroupId: "all",
    editingGroupId: null,
    symbolBoardSort: derive.restoreSymbolBoardSort(globalObject.localStorage),
  };
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
      renderWatchlists(derive.deriveAttention(state.events, state.groups));
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
    renderSymbolBoard(symbols);
    $("#editWatchlistButton").hidden = !group;
  }
  function summaryCell(label, value, support) {
    const cell = element("div", "");
    cell.append(element("span", "", label), element("strong", "", String(value)), element("small", "", support));
    return cell;
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
    const direction = pressure?.direction || "neutral";
    $("#detailPressure").replaceChildren(element("strong", `pressure-${direction}`, pressureLabels[direction]), element("span", "", pressure?.evidence?.label || "Canonical current pressure"), element("span", "", pressure?.evidence?.latest_pressure_observed_at ? `Latest pressure · ${exactTime(pressure.evidence.latest_pressure_observed_at)}` : "No qualifying directional pressure"));
  }

  function renderPressure() {
    const report = state.symbolPayload?.pressure || {};
    const counts = report.counts || { higher: 0, lower: 0, neutral: 0 };
    const selectedSymbol = new URLSearchParams(globalObject.location.search).get("symbol") || "";
    const selectedState = state.symbols.find((item) => item.symbol === selectedSymbol);
    const selectedPressure = pressureBySymbol().get(selectedSymbol);
    const selectedContext = $("#pressureSelectedContext");
    selectedContext.hidden = !selectedState;
    if (selectedState) {
      const direction = selectedPressure?.direction || "neutral";
      $("#pressureSelectedSymbol").textContent = selectedSymbol;
      $("#pressureSelectedDetails").href = `/mrz/symbols?symbol=${encodeURIComponent(selectedSymbol)}`;
      $("#pressureSelectedBody").replaceChildren(
        element("strong", `pressure-${direction}`, pressureLabels[direction] || pressureLabels.neutral),
        element("span", "", `Location · ${locationLabels[selectedState.current_price_location] || "—"}`),
        element("span", "", `Route · ${selectedState.route_owner || "—"}`),
        element("span", "", selectedPressure?.evidence?.latest_pressure_observed_at ? `Latest pressure · ${exactTime(selectedPressure.evidence.latest_pressure_observed_at)}` : "No qualifying directional pressure"),
      );
    }
    $("#pressureSummary").replaceChildren(
      summaryArticle("STATE", report.headline?.label || "—"), summaryArticle("↑ HIGHER", counts.higher || 0), summaryArticle("↓ LOWER", counts.lower || 0), summaryArticle("↔ NEUTRAL", counts.neutral || 0),
    );
    const map = $("#pressureMap"); map.replaceChildren();
    const locations = report.pressure_map?.locations || {};
    ["deep_discount", "shallow_discount", "at_eqm", "shallow_premium", "deep_premium"].forEach((key) => {
      const card = element("article", ""); card.append(element("h3", "", locationLabels[key]));
      const dl = element("dl", "");
      ["higher", "neutral", "lower"].forEach((direction) => { const row = element("div", ""); row.append(element("dt", `pressure-${direction}`, pressureLabels[direction]), element("dd", "", String(locations[key]?.counts?.[direction] || 0))); dl.append(row); });
      card.append(dl); map.append(card);
    });
    $("#pressureGroupSelect").replaceChildren(new Option("Select watchlist", ""), ...state.groups.map((group) => new Option(group.name, String(group.id))));
  }

  function renderLocationDistribution() {
    const selectedSymbol = new URLSearchParams(globalObject.location.search).get("symbol") || "";
    const columns = new Map();
    ["deep_discount", "shallow_discount", "at_eqm", "shallow_premium", "deep_premium"].forEach((key) => columns.set(key, []));
    state.symbols.forEach((symbol) => { if (columns.has(symbol.current_price_location)) columns.get(symbol.current_price_location).push(symbol.symbol); });
    const classifiedTotal = [...columns.values()].reduce((total, symbols) => total + symbols.length, 0);
    const migrationTendency = state.symbolPayload?.location_migration_tendency || {};
    const historyLocations = new Map((state.locationHistory?.locations || []).map((item) => [item.key, item]));
    const heatmap = $("#locationHeatmap"); heatmap.replaceChildren();
    columns.forEach((symbols, key) => {
      const column = element("section", `location-column${key === "at_eqm" ? " location-column-boundary" : ""}`);
      column.append(element("h3", "", locationLabels[key]));
      const current = element("div", "location-distribution-current");
      const percentage = classifiedTotal ? ((symbols.length / classifiedTotal) * 100).toFixed(1) : "0.0";
      current.append(element("span", "", "Current"), element("strong", "", `${symbols.length} symbol${symbols.length === 1 ? "" : "s"} · ${percentage}% of universe`));
      const historical = historyLocations.get(key);
      if (historical) {
        const delta = Number(historical.change_count || 0);
        const arrow = delta > 0 ? "↑" : delta < 0 ? "↓" : "↔";
        const deltaLabel = delta === 0 ? "0" : `${Math.abs(delta)}`;
        current.append(element("span", `location-distribution-change${delta > 0 ? " location-change-higher" : delta < 0 ? " location-change-lower" : ""}`, `${arrow} ${deltaLabel} vs ${state.locationWindow}`));
      }
      column.append(current);
      if (key === "at_eqm") {
        column.append(element("p", "location-boundary-note", "Exact canonical IPDA 20W midpoint"));
      } else {
        const migration = migrationTendencyPresentation(migrationTendency[key]);
        const history = element("details", "location-migration-history");
        history.append(element("summary", "", "Historical migration outcomes"));
        if (migration.hasHistory) {
          const directions = element("div", "location-migration-directions");
          [["↑ Higher", migration.higherPercentageLabel, migration.higherCountLabel], ["↓ Lower", migration.lowerPercentageLabel, migration.lowerCountLabel]].forEach(([label, outcome, count]) => {
            const direction = element("div", "location-migration-direction");
            direction.append(element("span", "migration-direction-label", label), element("strong", "", outcome), element("span", "migration-direction-count", `${count} migration${count === "1" ? "" : "s"}`));
            directions.append(direction);
          });
          history.append(directions);
        } else history.append(element("p", "location-migration-empty", "No migration history"));
        history.append(element("p", "location-migration-sample", migration.sampleLabel));
        column.append(history);
      }
      const symbolList = element("div", "location-symbol-list");
      symbols.forEach((symbol) => { const button = element("button", "", symbol); button.type = "button"; if (symbol === selectedSymbol) button.setAttribute("aria-current", "true"); button.addEventListener("click", () => { globalObject.location.href = `/mrz/symbols?symbol=${encodeURIComponent(symbol)}`; }); symbolList.append(button); });
      column.append(symbolList);
      heatmap.append(column);
    });
    renderLocationHistory();
  }

  function formatSigned(value, suffix = "") {
    const numeric = Number(value || 0);
    return `${numeric > 0 ? "+" : ""}${numeric.toFixed(suffix ? 1 : 0)}${suffix}`;
  }
  function renderLocationHistory() {
    document.querySelectorAll("[data-location-window]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.locationWindow === state.locationWindow));
    });
    const history = state.locationHistory;
    if (!history) return;
    $("#locationTrendHeading").textContent = `${history.window} comparison · then → now`;
    $("#locationFlowHeading").textContent = `Location flow · last ${history.window}`;
    $("#locationStructuralReadHeading").textContent = `Structural breadth · last ${history.window}`;
    $("#locationHistoryStatus").textContent = `Comparison point ${exactTime(history.comparison_at)}`;
    const universe = history.universe || {};
    $("#locationUniverseDisclosure").textContent = `${universe.now_eligible || 0} eligible now · ${universe.then_eligible || 0} eligible then · ${universe.common_eligible || 0} comparable · ${universe.added_or_became_eligible || 0} added/became eligible · ${universe.removed_or_became_ineligible || 0} removed/became ineligible. Windows are elapsed calendar time.`;

    const rows = $("#locationTrendRows"); rows.replaceChildren();
    (history.locations || []).forEach((item) => {
      const row = element("tr", "");
      const thenCell = element("td", ""); thenCell.append(document.createTextNode(String(item.then_count)), element("small", "", `${Number(item.then_pct).toFixed(1)}% of then universe`));
      const nowCell = element("td", ""); nowCell.append(document.createTextNode(String(item.now_count)), element("small", "", `${Number(item.now_pct).toFixed(1)}% of now universe`));
      const changeClass = item.change_count > 0 ? "location-change-higher" : item.change_count < 0 ? "location-change-lower" : "";
      const changeCell = element("td", changeClass); changeCell.append(document.createTextNode(formatSigned(item.change_count)), element("small", "", `${formatSigned(item.change_pp, " pp")}`));
      row.append(element("td", "", item.label), thenCell, nowCell, changeCell); rows.append(row);
    });

    const flow = history.flow || {};
    const read = history.structural_read || {};
    const netFlow = Number(flow.net_higher || 0);
    $("#locationStructuralRead").replaceChildren(
      structuralReadMetric("DISCOUNT SHARE", read.discount_share),
      structuralReadMetric("PREMIUM SHARE", read.premium_share),
      structuralReadMetric("EXTREME SHARE", read.extreme_share),
      flowMetric("NET LOCATION FLOW", formatSigned(netFlow), `${netFlow > 0 ? "higher" : netFlow < 0 ? "lower" : "balanced"} · ${flow.comparable_symbols || 0} comparable`),
    );
    const flowSummary = $("#locationFlowSummary"); flowSummary.replaceChildren(
      locationFlowButton("higher", "MOVED HIGHER", flow.moved_higher || 0, `${flow.comparable_symbols || 0} comparable symbols`),
      locationFlowButton("lower", "MOVED LOWER", flow.moved_lower || 0, `${flow.comparable_symbols || 0} comparable symbols`),
      locationFlowButton("unchanged", "UNCHANGED", flow.unchanged || 0, `Net ${formatSigned(netFlow)} ${netFlow > 0 ? "higher" : netFlow < 0 ? "lower" : "balanced"}`),
    );
    const transitions = $("#locationDominantTransitions"); transitions.replaceChildren();
    if (!(history.dominant_transitions || []).length) {
      transitions.append(element("li", "", "No cross-bucket transitions in this window."));
    } else {
      history.dominant_transitions.forEach((transition) => {
        const item = element("li", "");
        const button = element("button", "location-transition-button", `${transition.from_label} → ${transition.to_label} · ${transition.count}`);
        button.type = "button";
        button.setAttribute("aria-pressed", String(state.locationFlowSelection?.fromKey === transition.from_key && state.locationFlowSelection?.toKey === transition.to_key));
        button.addEventListener("click", () => {
          state.locationFlowSelection = { fromKey: transition.from_key, toKey: transition.to_key, label: `${transition.from_label} → ${transition.to_label}` };
          state.locationFlowPressure = "all";
          renderLocationHistory();
        });
        item.append(button);
        transitions.append(item);
      });
    }
    renderLocationFlowDrilldown();
  }
  function locationFlowButton(direction, label, value, support) {
    const button = element("button", "");
    button.type = "button";
    button.setAttribute("aria-controls", "locationFlowDrilldown");
    button.setAttribute("aria-expanded", String(state.locationFlowSelection?.direction === direction));
    button.append(element("span", "", label), element("strong", "", String(value)), element("small", "", support));
    button.addEventListener("click", () => {
      state.locationFlowSelection = { direction, label: label.replace("MOVED ", "Moved ").replace("UNCHANGED", "Unchanged") };
      state.locationFlowPressure = "all";
      renderLocationHistory();
    });
    return button;
  }
  function renderLocationFlowDrilldown() {
    const panel = $("#locationFlowDrilldown");
    const selection = state.locationFlowSelection;
    if (!selection || !state.locationHistory) {
      panel.hidden = true;
      $("#locationFlowSymbols").replaceChildren();
      return;
    }
    const groups = derive.deriveLocationFlowDetails(state.locationHistory, state.symbolPayload?.pressure || {});
    const allRows = selection.direction
      ? groups[selection.direction] || []
      : Object.values(groups).flat().filter((item) => item.start_location === selection.fromKey && item.current_location === selection.toKey);
    const rows = state.locationFlowPressure === "all"
      ? allRows
      : allRows.filter((item) => item.pressure === state.locationFlowPressure);
    panel.hidden = false;
    $("#locationFlowDrilldownHeading").textContent = `${selection.label} · ${allRows.length}`;
    $("#locationFlowDrilldownSupport").textContent = `${state.locationWindow} start → current · ${rows.length} shown`;
    document.querySelectorAll("[data-flow-pressure]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.flowPressure === state.locationFlowPressure));
    });
    const list = $("#locationFlowSymbols"); list.replaceChildren();
    if (!rows.length) {
      list.append(element("li", "flow-empty", "No symbols match this pressure filter."));
      return;
    }
    rows.forEach((item) => {
      const row = element("li", "");
      const direction = item.direction === "higher" ? "Higher" : item.direction === "lower" ? "Lower" : "Unchanged";
      const magnitude = item.direction === "higher" ? `+${item.magnitude}` : item.direction === "lower" ? `-${item.magnitude}` : "0";
      const migrationDirections = new Set(item.migrationEvents.map((event) => event.direction));
      const migration = migrationDirections.size > 1 ? "↑ + ↓" : migrationDirections.has("higher") ? "↑" : migrationDirections.has("lower") ? "↓" : "—";
      row.append(
        symbolLink(item.symbol, item.symbol),
        element("span", "", `${item.start_location_label} → ${item.current_location_label}`),
        element("span", "flow-magnitude", `${magnitude} bucket${item.magnitude === 1 ? "" : "s"} · ${direction}`),
        element("span", `pressure-${item.pressure}`, `Pressure: ${pressureLabels[item.pressure] || pressureLabels.neutral}`),
        element("span", "", `MRZ migration: ${migration}`),
      );
      list.append(row);
    });
  }
  function percentage(numerator, denominator) {
    return denominator ? `${((Number(numerator) / Number(denominator)) * 100).toFixed(1)}%` : "0.0%";
  }
  function migrationStateLabel(stateValue) {
    return { up_only: "Up-only", down_only: "Down-only", mixed: "Mixed", none: "No migration" }[stateValue] || "No migration";
  }
  function renderLeadershipRows(targetSelector, rows) {
    const target = $(targetSelector); target.replaceChildren();
    if (!rows.length) {
      const row = element("tr", ""); const cell = element("td", "", "No qualifying symbols in this window.");
      cell.colSpan = 7; row.append(cell); target.append(row); return;
    }
    rows.forEach((item) => {
      const row = element("tr", "");
      const symbolCell = element("td", ""); symbolCell.append(symbolLink(item.symbol, item.symbol));
      const move = `${item.direction === "higher" ? "↑" : "↓"} ${item.magnitude} bucket${item.magnitude === 1 ? "" : "s"}`;
      row.append(
        symbolCell,
        element("td", "", item.start_location_label),
        element("td", "", item.current_location_label),
        element("td", item.direction === "higher" ? "location-change-higher" : "location-change-lower", move),
        element("td", `pressure-${item.pressure}`, pressureLabels[item.pressure] || pressureLabels.neutral),
        element("td", "", `${migrationStateLabel(item.migrationState)}${item.migrationEvents.length ? ` · ${item.migrationEvents.length}` : ""}`),
        element("td", "", exactTime(item.latestRelevantAt)),
      );
      target.append(row);
    });
  }
  function renderDivergenceSymbols(targetSelector, rows) {
    const target = $(targetSelector); target.replaceChildren();
    if (!rows.length) { target.append(element("span", "empty-inline", "No divergence in this window.")); return; }
    const links = element("div", "research-symbol-links");
    rows.forEach((item) => links.append(symbolLink(item.symbol, item.symbol)));
    target.append(links);
  }
  function renderBreadthLeadership() {
    const report = derive.deriveBreadthLeadership(state.locationHistory || {}, state.symbolPayload?.pressure || {});
    document.querySelectorAll("[data-breadth-window]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.breadthWindow === state.locationWindow));
    });
    const breadth = report.breadth;
    const universe = report.universe;
    $("#breadthSummaryHeading").textContent = `${report.window} structural breadth`;
    $("#breadthResearchSummary").textContent = `Structural participation is ${breadth.participationPct.toFixed(1)}%: ${breadth.movedHigher + breadth.movedLower} of ${breadth.comparable} comparable symbols changed bucket over the last ${report.window}. Higher and lower flows produce net breadth ${formatSigned(breadth.netHigher)} ${breadth.netHigher > 0 ? "higher" : breadth.netHigher < 0 ? "lower" : "balanced"}. ${report.confirmationRates.higher.numerator} of ${report.confirmationRates.higher.denominator} higher movers currently show Higher pressure.`;
    $("#breadthUniverseDisclosure").textContent = `${universe.now_eligible || 0} eligible now · ${universe.then_eligible || 0} eligible then · ${universe.common_eligible || 0} comparable · ${universe.added_or_became_eligible || 0} added/became eligible · ${universe.removed_or_became_ineligible || 0} removed/became ineligible. Universe changes are excluded from movement breadth.`;
    $("#breadthMetrics").replaceChildren(
      flowMetric("MOVED HIGHER", breadth.movedHigher, "Comparable symbols"),
      flowMetric("MOVED LOWER", breadth.movedLower, "Comparable symbols"),
      flowMetric("UNCHANGED", breadth.unchanged, "Comparable symbols"),
      flowMetric("NET BREADTH", formatSigned(breadth.netHigher), breadth.netHigher > 0 ? "higher" : breadth.netHigher < 0 ? "lower" : "balanced"),
      flowMetric("PARTICIPATION", `${breadth.participationPct.toFixed(1)}%`, `${breadth.movedHigher + breadth.movedLower} of ${breadth.comparable}`),
    );
    const confirmationRows = $("#pressureConfirmationRows"); confirmationRows.replaceChildren();
    [["Moved higher", report.confirmation.higher], ["Moved lower", report.confirmation.lower]].forEach(([label, counts]) => {
      const row = element("tr", ""); row.append(element("td", "", label), element("td", "pressure-higher", String(counts.higher)), element("td", "pressure-neutral", String(counts.neutral)), element("td", "pressure-lower", String(counts.lower))); confirmationRows.append(row);
    });
    const higherRate = report.confirmationRates.higher; const lowerRate = report.confirmationRates.lower;
    $("#confirmationRates").replaceChildren(
      flowMetric("HIGHER-MOVER CONFIRMATION", percentage(higherRate.numerator, higherRate.denominator), `${higherRate.numerator} of ${higherRate.denominator} · current Higher pressure`),
      flowMetric("LOWER-MOVER CONFIRMATION", percentage(lowerRate.numerator, lowerRate.denominator), `${lowerRate.numerator} of ${lowerRate.denominator} · current Lower pressure`),
    );
    renderLeadershipRows("#breadthLeaders", report.leaders);
    renderLeadershipRows("#breadthLaggards", report.laggards);
    renderDivergenceSymbols("#higherLowerDivergences", report.divergences.higherWithLower);
    renderDivergenceSymbols("#lowerHigherDivergences", report.divergences.lowerWithHigher);
    const migration = report.migrationBreadth;
    $("#migrationBreadth").replaceChildren(
      flowMetric("UP-ONLY", migration.up_only, "Unique symbols"),
      flowMetric("DOWN-ONLY", migration.down_only, "Unique symbols"),
      flowMetric("MIXED", migration.mixed, "Both directions"),
      flowMetric("NO MIGRATION", migration.none, "Comparable symbols"),
      flowMetric("MIGRATING SYMBOLS", migration.uniqueSymbols, "Unique symbols"),
      flowMetric("MIGRATION EVENTS", migration.eventCount, "Canonical events"),
    );
    const pressureRows = $("#locationPressureRows"); pressureRows.replaceChildren();
    ["deep_discount", "shallow_discount", "at_eqm", "shallow_premium", "deep_premium"].forEach((key) => {
      const counts = report.currentLocationPressure[key]?.counts || {};
      const row = element("tr", ""); row.append(element("td", "", locationLabels[key]), element("td", "pressure-higher", String(counts.higher || 0)), element("td", "pressure-neutral", String(counts.neutral || 0)), element("td", "pressure-lower", String(counts.lower || 0))); pressureRows.append(row);
    });
  }
  function flowMetric(label, value, support) {
    const node = element("article", "");
    node.append(element("span", "", label), element("strong", "", String(value)), element("small", "", support));
    return node;
  }
  function structuralReadMetric(label, measure = {}) {
    const delta = Number(measure.change_pp || 0);
    const node = flowMetric(label, `${Number(measure.now_pct || 0).toFixed(1)}%`, `${formatSigned(delta, " pp")} vs ${state.locationWindow}`);
    if (delta > 0) node.classList.add("location-change-higher");
    if (delta < 0) node.classList.add("location-change-lower");
    return node;
  }
  async function loadLocationHistory(window) {
    state.locationWindow = window;
    $("#locationHistoryStatus").textContent = "Loading canonical history…";
    $("#locationFlowSymbols").replaceChildren();
    if (state.locationFlowSelection) $("#locationFlowDrilldownSupport").textContent = `Loading ${window} flow…`;
    document.querySelectorAll("[data-location-window]").forEach((button) => {
      button.disabled = true;
      button.setAttribute("aria-pressed", String(button.dataset.locationWindow === window));
    });
    try {
      const response = await fetch(`/api/location-distribution/history?window=${encodeURIComponent(window)}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Unable to load canonical location history.");
      state.locationHistory = await response.json();
      renderLocationDistribution();
      renderBreadthLeadership();
    } catch (error) {
      $("#locationHistoryStatus").textContent = error.message || "Unable to load canonical location history.";
    } finally {
      document.querySelectorAll("[data-location-window]").forEach((button) => { button.disabled = false; });
    }
  }
  function summaryArticle(label, value) { const node = element("article", ""); node.append(element("span", "", label), element("strong", "", String(value))); return node; }
  async function loadPeerPressure(groupId) {
    const target = $("#peerPressureDetail");
    if (!groupId) { target.className = "empty-inline"; target.textContent = "Choose a watchlist to load canonical peer pressure."; return; }
    target.className = "empty-inline"; target.textContent = "Loading peer pressure…";
    const response = await fetch(`/api/groups/${encodeURIComponent(groupId)}/peer-pressure`, { cache: "no-store" });
    if (!response.ok) throw new Error("Unable to load peer pressure.");
    const payload = await response.json();
    const grid = element("div", "peer-pressure-grid");
    ["higher", "neutral", "lower"].forEach((direction) => {
      const section = element("section", ""); section.append(element("h3", `pressure-${direction}`, `${pressureLabels[direction]} · ${payload.counts?.[direction] || 0}`));
      const list = element("ul", ""); (payload.categories?.[direction] || []).forEach((member) => list.append(element("li", "", `${member.symbol} · ${member.active_mrz?.route_owner || "—"} · ${member.current_location_label}`))); section.append(list); grid.append(section);
    });
    target.className = ""; target.replaceChildren(grid);
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
    renderOverview(attention); renderWatchlists(attention); renderAttention(attention); renderSymbolOptions(); renderPressure(); renderLocationDistribution(); renderBreadthLeadership(); renderEvents(); renderPreferences();
  }
  async function initialize() {
    activateRoute();
    try {
      const needsLocationHistory = ["location-distribution", "breadth-leadership"].includes(routeName());
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
      renderAll(); $("#workspaceStatus").hidden = true;
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
  $("#pressureGroupSelect")?.addEventListener("change", (event) => loadPeerPressure(event.target.value).catch(showError));
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
  document.querySelectorAll("[data-breadth-window]").forEach((button) => button.addEventListener("click", () => loadLocationHistory(button.dataset.breadthWindow)));
  $("#locationFlowDrilldownClose")?.addEventListener("click", () => {
    state.locationFlowSelection = null;
    renderLocationHistory();
  });
  document.querySelectorAll("[data-flow-pressure]").forEach((button) => button.addEventListener("click", () => {
    state.locationFlowPressure = button.dataset.flowPressure;
    renderLocationFlowDrilldown();
  }));
  $("#eventTypeFilter")?.addEventListener("change", renderEvents);
  $("#alertPreferencesForm")?.addEventListener("submit", (event) => savePreferences(event).catch(showError));
  function showError(error) { $("#workspaceStatus").hidden = false; $("#workspaceStatus").textContent = error.message || "The request could not be completed."; $("#workspaceStatus").classList.add("error"); }
  document.addEventListener("DOMContentLoaded", initialize, { once: true });
}(globalThis));
