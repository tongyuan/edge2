(function initializeGroupEvidence(globalObject) {
  "use strict";

  const derive = globalObject.edgeWorkspaceDerivations;
  const state = {
    scope: derive.parseGroupEvidenceState(globalObject.location?.search || ""),
    payload: null,
    requestId: 0,
    controller: null,
    lastSuccessful: new Map(),
    recentLoaded: false,
    editingGroup: null,
  };
  const $ = (selector) => globalObject.document.querySelector(selector);
  const text = (value) => value === null || value === undefined ? "—" : String(value);

  function node(tag, className, content) {
    const element = globalObject.document.createElement(tag);
    if (className) element.className = className;
    if (content !== undefined) element.textContent = content;
    return element;
  }

  function exactTime(value) {
    if (!value) return "Unavailable";
    return globalObject.formatOperatorTimestampUtcMinus4?.(value)
      || new Date(value).toLocaleString();
  }

  function ratio(numerator, denominator, unavailable = false) {
    const numericNumerator = Number(numerator);
    const numericDenominator = Number(denominator);
    if (unavailable || !Number.isFinite(numericNumerator) || !Number.isFinite(numericDenominator)) return "Unavailable";
    if (numericDenominator === 0) return "0 / 0 — unavailable";
    return `${numericNumerator} / ${numericDenominator}`;
  }

  function updateUrl(updates, { replace = false } = {}) {
    const url = new URL(globalObject.location.href);
    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === undefined || value === "") url.searchParams.delete(key);
      else url.searchParams.set(key, String(value));
    });
    const historyMethod = replace ? "replaceState" : "pushState";
    globalObject.history[historyMethod]({}, "", url);
    state.scope = derive.parseGroupEvidenceState(url.search);
  }

  function canonicalScopeUrl(extra = {}) {
    const params = new URLSearchParams({
      from: "watchlists",
      group: state.scope.groupId,
      window: state.scope.window,
      return: `${globalObject.location.pathname}${globalObject.location.search}`,
      ...extra,
    });
    return params;
  }

  function symbolUrl(symbol, extra = {}) {
    const params = canonicalScopeUrl(extra);
    params.set("symbol", symbol);
    return `/mrz/symbols?${params}`;
  }

  function eventUrl(symbol, eventId) {
    const params = canonicalScopeUrl({ symbol, event: eventId });
    return `/mrz/events?${params}`;
  }

  function setLoading(message = "Loading group evidence…") {
    $("#groupEvidenceLive").hidden = false;
    $("#groupEvidenceLive").className = "group-evidence-live";
    $("#groupEvidenceLive").textContent = message;
    $("#groupEvidenceContent").replaceChildren(node("div", "group-evidence-skeleton", message));
  }

  function setError(message, retry = true) {
    const live = $("#groupEvidenceLive");
    live.hidden = false;
    live.className = "group-evidence-live error";
    live.setAttribute("role", "alert");
    live.textContent = message;
    const panel = node("section", "panel group-evidence-error");
    panel.append(node("p", "", message));
    if (retry) {
      const button = node("button", "primary-button", "Retry");
      button.type = "button";
      button.addEventListener("click", load);
      panel.append(button);
    }
    $("#groupEvidenceContent").replaceChildren(panel);
  }

  function renderMeta(payload) {
    const meta = $("#groupEvidenceMeta");
    meta.replaceChildren();
    const values = payload.scope === "all_groups"
      ? [
        ["As of", exactTime(payload.window.as_of)],
        ["Comparison", exactTime(payload.window.comparison_at)],
        ["Saved groups", payload.scope_totals.group_count],
        ["Member slots", payload.scope_totals.member_slots],
        ["Unique symbols", payload.scope_totals.unique_members],
        ["Canonical migrations", payload.scope_totals.canonical_migration_events],
        ["Group appearances", payload.scope_totals.group_context_migration_appearances],
      ]
      : [
        ["As of", exactTime(payload.window.as_of)],
        ["Comparison", exactTime(payload.window.comparison_at)],
        ["Current members", payload.group.member_count],
        ["Latest relevant", exactTime(payload.latest_relevant_evidence_at)],
        ["Structural comparable", ratio(payload.coverage.structural_comparable, payload.group.member_count)],
        ["New observation inside window", ratio(payload.coverage.structural_fresh_in_window, payload.coverage.structural_comparable)],
        ["Current location unavailable", ratio(payload.coverage.structural_unavailable_current, payload.group.member_count)],
        ["Current-pressure active MRZ", ratio(payload.coverage.current_pressure_active_mrz, payload.group.member_count)],
        ["Current-pressure directional", ratio(payload.coverage.current_pressure_directional, payload.group.member_count)],
        ["Directional evidence inside window", ratio(payload.coverage.current_pressure_evidence_fresh_in_window, payload.coverage.current_pressure_directional)],
      ];
    values.forEach(([label, value]) => {
      const item = node("div", "");
      item.append(node("span", "", label), node("strong", "", text(value)));
      meta.append(item);
    });
  }

  function selectionButton(label, count, denominator, selection, support = "") {
    const button = node("button", "evidence-count");
    button.type = "button";
    button.dataset.selection = JSON.stringify(selection);
    button.setAttribute(
      "aria-label",
      `${label}, ${ratio(count, denominator)}, ${state.payload?.group?.name || "group"}, ${state.scope.window}`,
    );
    button.append(node("span", "", label), node("strong", "", text(count)), node("small", "", support || ratio(count, denominator)));
    return button;
  }

  function groupCard(group) {
    const card = node("article", "group-evidence-card");
    if (group.status === "partial") card.classList.add("partial");
    const heading = node("header", "group-evidence-card-heading");
    const identity = node("div", "");
    identity.append(node("h2", "", group.name), node("p", "", `${group.membership_total} current members · updated ${exactTime(group.updated_at)}`));
    const open = node("button", "primary-button", "Open group");
    open.type = "button";
    open.dataset.openGroup = group.id;
    heading.append(identity, open);

    const coverage = node("section", "group-evidence-card-section");
    coverage.append(node("h3", "", "Coverage & freshness"));
    const coverageList = node("dl", "evidence-facts");
    [
      ["Structural comparable", ratio(group.coverage.structural_comparable, group.membership_total)],
      ["New observation inside window", ratio(group.coverage.structural_fresh_in_window, group.coverage.structural_comparable)],
      ["No new observation inside window", ratio(group.coverage.structural_no_new_observation, group.coverage.structural_comparable)],
      ["Current location unavailable", ratio(group.coverage.structural_unavailable_current, group.membership_total)],
      ["Current-pressure active MRZ", ratio(group.coverage.current_pressure_active_mrz, group.membership_total)],
      ["Latest relevant evidence", exactTime(group.latest_relevant_evidence_at)],
    ].forEach(([label, value]) => coverageList.append(node("dt", "", label), node("dd", "", value)));
    coverage.append(coverageList);

    const structural = node("section", "group-evidence-card-section");
    structural.append(node("h3", "", "Structural evidence"));
    const structuralUnavailable = group.structural?.status === "unavailable";
    if (structuralUnavailable) structural.append(node("p", "evidence-empty", "Structural evidence unavailable for this snapshot."));
    else {
      const structuralGrid = node("div", "evidence-count-grid");
      const comparable = group.coverage.structural_comparable;
      structuralGrid.append(
        selectionButton("Moved Higher", group.structural.moved_higher, comparable, { group: group.id, dimension: "structural", bucket: "higher" }, `${group.structural.higher_steps} native steps`),
        selectionButton("Moved Lower", group.structural.moved_lower, comparable, { group: group.id, dimension: "structural", bucket: "lower" }, `${group.structural.lower_steps} native steps`),
        selectionButton("Same Bucket", group.structural.same_bucket, comparable, { group: group.id, dimension: "structural", bucket: "same_bucket" }),
      );
      structural.append(structuralGrid);
    }

    const directional = node("section", "group-evidence-card-section");
    directional.append(node("h3", "", "Directional evidence"));
    const current = group.directional.current_pressure || {};
    const latest = group.directional.latest_cumulative_event || {};
    if (current.status === "unavailable") directional.append(node("p", "evidence-empty", "Current pressure evidence unavailable for this snapshot."));
    else {
      const currentLine = node("p", "evidence-inline", `Current pressure now · ${current.higher} Higher · ${current.lower} Lower · ${current.neutral} Neutral`);
      const currentButtons = node("div", "evidence-count-grid");
      ["higher", "lower", "neutral"].forEach((bucket) => currentButtons.append(selectionButton(`Current ${bucket[0].toUpperCase()}${bucket.slice(1)}`, current[bucket], group.membership_total, { group: group.id, dimension: "directional", evidence: "current_pressure", bucket })));
      directional.append(currentLine, currentButtons, node("p", "evidence-inline", `Current-pressure evidence inside selected window ${ratio(group.coverage.current_pressure_evidence_fresh_in_window, group.coverage.current_pressure_directional)}`));
    }
    if (latest.status === "unavailable") directional.append(node("p", "evidence-empty", "Cumulative lifecycle pressure events unavailable for this snapshot."));
    else {
      const eventLine = node("p", "evidence-inline", `Latest Cumulative lifecycle pressure event · ${latest.higher} Higher · ${latest.lower} Lower · ${latest.none} No event in window`);
      const comparison = group.directional.latest_event_vs_current || {};
      const comparisonLine = node("p", "evidence-inline", `Event versus Current pressure · ${comparison.same_direction} Same · ${comparison.current_neutral} Current Neutral · ${comparison.opposite_direction} Opposite · ${comparison.current_unavailable} Current Unavailable`);
      const cumulativeButtons = node("div", "evidence-count-grid");
      ["higher", "lower", "none"].forEach((bucket) => cumulativeButtons.append(selectionButton(bucket === "none" ? "No event in window" : `Latest event ${bucket[0].toUpperCase()}${bucket.slice(1)}`, latest[bucket], group.membership_total, { group: group.id, dimension: "directional", evidence: "cumulative_latest", bucket })));
      directional.append(eventLine, cumulativeButtons, comparisonLine);
    }

    const migrations = node("section", "group-evidence-card-section");
    migrations.append(node("h3", "", "Recent canonical MRZ migrations"));
    const migration = group.migrations || {};
    if (migration.status === "unavailable") migrations.append(node("p", "evidence-empty", "Migration evidence unavailable for this snapshot."));
    else {
      const migrationButton = selectionButton(
        "Unique contributors",
        migration.unique_contributors,
        group.membership_total,
        { group: group.id, dimension: "directional", evidence: "migration_contributors" },
        `${migration.event_count} raw events`,
      );
      migrations.append(migrationButton, node("p", "evidence-inline", `${migration.higher_events} Higher · ${migration.lower_events} Lower · ${migration.same_midpoint_events || 0} Same midpoint · ${migration.repeated_contributors} repeated contributors · ${migration.both_direction_contributors} both directions · ${migration.route_change_events} route changes`));
      if (migration.event_count) migrations.append(node("p", "evidence-inline", `${exactTime(migration.earliest_at)} → ${exactTime(migration.latest_at)}${migration.event_count > 1 ? ` · ${migration.span_seconds}s raw span` : ""}`));
      else migrations.append(node("p", "evidence-empty", "No event in window."));
    }
    card.append(heading, coverage, structural, directional, migrations);
    return card;
  }

  function renderAllGroups(payload) {
    $("#groupEvidenceTitle").textContent = "All Groups";
    $("#groupEvidenceScope").textContent = "Historical evidence for today's members · elapsed calendar time · factual comparison ordered by group name";
    $("#groupEvidenceEdit").hidden = true;
    const wrapper = node("div", "all-groups-evidence");
    const controls = node("div", "group-evidence-sort");
    const label = node("label", "", "FACTUAL SORT ");
    const select = node("select", "");
    [
      ["name", "Group name A–Z"], ["latest", "Latest evidence time"],
      ["comparable", "Structural comparable ratio"], ["fresh", "Fresh-observation ratio"],
      ["migration_contributors", "Unique migration contributors"], ["migration_events", "Raw migration event count"],
    ].forEach(([value, copy]) => {
      const option = node("option", "", copy); option.value = value; option.selected = state.scope.sort === value; select.append(option);
    });
    select.addEventListener("change", () => { updateUrl({ sort: select.value }); renderAllGroups(payload); });
    const sortMeaning = {
      name: "A–Z by saved-group name",
      latest: "latest relevant evidence timestamp",
      comparable: "structural comparable / current members",
      fresh: "new observation inside window / structural comparable",
      migration_contributors: "unique migration contributors / current members",
      migration_events: "raw migration event count",
    }[state.scope.sort] || "A–Z by saved-group name";
    label.append(select); controls.append(label, node("span", "", `Active sort: ${sortMeaning}. Exact values remain visible on every card.`)); wrapper.append(controls);
    if (!payload.groups.length) {
      wrapper.append(node("section", "panel group-evidence-empty", "No saved groups. Create a group to inspect factual evidence for its current members."));
    } else {
      const cards = node("div", "group-evidence-cards");
      derive.sortGroupEvidenceRows(payload.groups, state.scope.sort).forEach((group) => cards.append(groupCard(group)));
      wrapper.append(cards);
    }
    const disclosure = node("p", "group-evidence-disclosure", `Canonical migration events: ${payload.scope_totals.canonical_migration_events}; group-context appearances: ${payload.scope_totals.group_context_migration_appearances}. Shared events retain one canonical identity.`);
    const limitationLink = detailLink("Current pressure snapshot limitations", "#groupEvidenceLimitations");
    const limitations = node("section", "panel group-evidence-limitations"); limitations.id = "groupEvidenceLimitations";
    limitations.append(node("h2", "", "Stage A limitations"));
    const limitationList = node("ul", ""); (payload.limitations || []).forEach((item) => limitationList.append(node("li", "", item))); limitations.append(limitationList);
    wrapper.append(disclosure, limitationLink, limitations);
    $("#groupEvidenceContent").replaceChildren(wrapper);
  }

  function detailLink(label, href) {
    const link = node("a", "quiet-button", label); link.href = href; return link;
  }

  function detailSection(title, support) {
    const section = node("section", "panel named-evidence-section");
    const header = node("header", "panel-heading");
    const copy = node("div", ""); copy.append(node("h2", "", title), node("span", "", support)); header.append(copy);
    section.append(header);
    return section;
  }

  function openSelection(selection) {
    updateUrl({
      dimension: selection.dimension,
      bucket: selection.bucket || null,
      evidence: selection.evidence || null,
    });
    renderNamedGroup(state.payload);
    $("#groupEvidenceDrilldown")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  function contributorCard(item, type) {
    const card = node("li", "evidence-contributor");
    const symbol = item.symbol || "Unavailable";
    const header = node("div", "evidence-contributor-heading");
    header.append(node("strong", "", symbol), detailLink("Open symbol", symbolUrl(symbol, { evidence: type, event: item.event_key || item.event_id || "" })));
    card.append(header);
    const facts = node("dl", "evidence-facts");
    const rows = type === "structural" ? [
      ["Endpoint", item.start_location_label ? `${item.start_location_label} → ${item.current_location_label}` : item.reason || "Unavailable"],
      ["Direction", item.direction ? item.direction.replace("same_bucket", "Same Bucket") : "Unavailable"],
      ["Native bucket steps", item.magnitude_steps],
      ["Comparison source", exactTime(item.comparison_observed_at)],
      ["Current source", exactTime(item.current_observed_at)],
      ["New observation inside window", item.new_observation_in_window === true ? "Yes" : item.new_observation_in_window === false ? "No" : "Unavailable"],
      ["Source observation IDs", (item.source_observation_ids || []).join(", ") || "Not available"],
    ] : type === "current_pressure" ? [
      ["Current pressure", item.direction_label || item.direction],
      ["Classifier status", item.evidence?.status],
      ["Reason", item.evidence?.reason],
      ["Active MRZ", item.active_mrz?.status],
      ["Lifecycle activation", item.lifecycle_activation_event_id],
      ["Route owner", item.active_mrz?.route_owner],
      ["Structural location", item.current_location_label],
      ["Current pressure since", exactTime(item.evidence?.current_pressure_since)],
      ["Latest pressure evidence", exactTime(item.evidence?.latest_pressure_observed_at)],
      ["Evidence inside selected window", item.evidence_in_window ? "Yes" : "No"],
      ["Latest four sequence", (item.evidence?.recent_sequence || []).map((entry) => `${entry.direction} ${exactTime(entry.observed_at)}`).join(" · ") || "Unavailable"],
    ] : type === "cumulative" ? [
      ["Cumulative lifecycle pressure event", item.event_direction ? `${item.event_direction[0].toUpperCase()}${item.event_direction.slice(1)}` : item.state === "none" ? "No event in window" : "Unavailable"],
      ["Canonical identity", item.source_event_key || item.event_id],
      ["Lifecycle activation", item.lifecycle_activation_event_id],
      ["Previous state", item.previous_state],
      ["Occurred / evaluated", exactTime(item.occurred_at)],
      ["Route owner", item.route_owner],
      ["Cumulative observations", item.post_activation_observation_count],
      ["Above / below envelope", item.above_envelope_count === undefined ? "Unavailable" : `${item.above_envelope_count} / ${item.below_envelope_count}`],
      ["Current pressure now", item.current_pressure_direction || "Unavailable"],
      ["Current pressure evidence time", exactTime(item.current_pressure_evidence_at)],
      ["Event versus Current pressure", item.comparison || "Unavailable"],
    ] : type === "migration_contributors" ? [
      ["Raw event count", item.event_count],
      ["Directions in window", (item.directions || []).join(" · ")],
      ["First event", exactTime(item.first_at)],
      ["Latest event", exactTime(item.latest_at)],
      ["Canonical event identities", (item.event_keys || []).join(", ")],
    ] : [
      ["Canonical event", item.event_key],
      ["Sequence", item.sequence],
      ["Occurred", exactTime(item.occurred_at)],
      ["Direction", item.direction],
      ["Route", `${item.previous_route_owner} → ${item.route_owner}`],
      ["Route changed", item.route_changed ? "Yes" : "No"],
      ["Old bounds / midpoint", `${text(item.old_lower)}–${text(item.old_upper)} / ${text(item.old_midpoint)}`],
      ["New bounds / midpoint", `${text(item.new_lower)}–${text(item.new_upper)} / ${text(item.new_midpoint)}`],
      ["New structural location", item.new_structural_location],
      ["Trigger observation", item.trigger_observation_event_id],
      ["Repeat index in window", item.repeat_index],
    ];
    rows.forEach(([label, value]) => facts.append(node("dt", "", label), node("dd", "", text(value))));
    card.append(facts);
    if ((type === "cumulative" || type === "migration_events") && (item.event_key || item.event_id)) {
      card.append(detailLink("Open event reference", eventUrl(symbol, item.event_key || item.event_id)));
    }
    return card;
  }

  function renderDrilldown(payload) {
    const selection = state.scope;
    if (!selection.dimension) return null;
    const section = detailSection("Exact contributors", `${state.scope.window} · canonical identities and source timestamps`);
    section.id = "groupEvidenceDrilldown";
    section.setAttribute("aria-live", "polite");
    const close = node("button", "quiet-button", "Close contributor view"); close.type = "button";
    close.addEventListener("click", () => { updateUrl({ dimension: null, bucket: null, evidence: null }); renderNamedGroup(payload); $("#groupEvidenceTitle").focus(); });
    section.querySelector("header").append(close);
    const rows = derive.filterGroupEvidenceContributors(payload, selection);
    const list = node("ul", "evidence-contributors");
    const type = selection.dimension === "structural" ? "structural"
      : selection.evidence?.startsWith("cumulative") ? "cumulative"
        : selection.evidence || "current_pressure";
    rows.forEach((item) => list.append(contributorCard(item, type)));
    if (!rows.length) list.append(node("li", "evidence-empty", "No contributors in this category for the selected window."));
    section.append(list);
    return section;
  }

  function renderConstituentBoard(payload) {
    const section = detailSection("Constituent board", "Current canonical reference · Symbol A–Z");
    const structural = new Map((payload.structural.contributors || []).map((item) => [item.symbol, item]));
    const pressure = new Map((payload.directional.current_pressure.members || []).map((item) => [item.symbol, item]));
    const latestEvents = new Map();
    const rememberEvent = (symbol, occurredAt, label) => {
      if (!occurredAt) return;
      const current = latestEvents.get(symbol);
      if (!current || String(occurredAt) > String(current.occurredAt)) latestEvents.set(symbol, { occurredAt, label });
    };
    (payload.directional.cumulative_lifecycle_pressure_events.events || []).forEach((item) => rememberEvent(item.symbol, item.occurred_at, `Cumulative pressure ${item.event_direction}`));
    (payload.directional.mrz_migrations.events || []).forEach((item) => rememberEvent(item.symbol, item.occurred_at, `MRZ migration ${item.direction}`));
    const tableWrap = node("div", "table-scroll");
    const table = node("table", "symbol-board group-evidence-board");
    const head = node("thead", ""); head.innerHTML = "<tr><th>Symbol</th><th>MRZ status</th><th>Authority</th><th>Route</th><th>Activated</th><th>Structural location</th><th>Current pressure</th><th>Latest selected-window event</th><th>Action</th></tr>";
    const body = node("tbody", "");
    [...payload.group.members].sort((a, b) => a.localeCompare(b)).forEach((symbol) => {
      const member = pressure.get(symbol) || { symbol };
      const movement = structural.get(symbol);
      const active = member.active_mrz || {};
      const authority = active.authority;
      const latest = latestEvents.get(symbol);
      const row = node("tr", "");
      const action = node("td", ""); action.append(detailLink("Open symbol", symbolUrl(symbol)));
      [
        symbol,
        active.status || "Unavailable",
        authority ? `${text(authority.lower)}–${text(authority.upper)}` : "Unavailable",
        active.route_owner || "Unavailable",
        exactTime(active.activated_at),
        movement?.current_location_label || member.current_location_label || "Unavailable",
        member.direction_label || member.direction || "Unavailable",
        latest ? `${latest.label} · ${exactTime(latest.occurredAt)}` : "No event in window",
      ].forEach((value) => row.append(node("td", "", text(value))));
      row.append(action); body.append(row);
    });
    table.append(head, body); tableWrap.append(table); section.append(tableWrap);
    return section;
  }

  function renderNamedGroup(payload) {
    const group = payload.group;
    $("#groupEvidenceTitle").textContent = group.name;
    $("#groupEvidenceScope").textContent = `${group.member_count} current members · Historical evidence for today's members · membership edits reattribute history to the new current membership`;
    $("#groupEvidenceEdit").hidden = false;
    const wrapper = node("div", "named-group-evidence");
    const research = node("nav", "group-evidence-research", ""); research.setAttribute("aria-label", "Specialist research and settings");
    [
      ["Universe Location", `/mrz/location-distribution?window=${state.scope.window}&${canonicalScopeUrl()}`],
      ["Universe Pressure", `/mrz/pressure?${canonicalScopeUrl()}`],
      ["Breadth research", `/mrz/breadth-leadership?window=${state.scope.window}&${canonicalScopeUrl()}`],
      ["Formation Diagnostics", `/mrz/formation-diagnostics?${canonicalScopeUrl()}`],
      ["Notification Event History", `/mrz/events?${canonicalScopeUrl()}`],
      ["Alert Settings", `/mrz/alert-settings?${canonicalScopeUrl()}`],
    ].forEach(([label, href]) => research.append(detailLink(label, href)));
    wrapper.append(research);

    const structural = detailSection("Structural evidence", "Endpoint comparison is not a stability claim");
    if (payload.structural.status === "unavailable") structural.append(node("p", "evidence-empty", "Structural evidence unavailable for this snapshot."));
    else {
      const counts = node("div", "evidence-count-grid");
      const summary = payload.structural.summary;
      const comparable = payload.coverage.structural_comparable;
      counts.append(
        selectionButton("Moved Higher", summary.moved_higher, comparable, { dimension: "structural", bucket: "higher" }, `${summary.higher_steps} native steps`),
        selectionButton("Moved Lower", summary.moved_lower, comparable, { dimension: "structural", bucket: "lower" }, `${summary.lower_steps} native steps`),
        selectionButton("Same Bucket", summary.same_bucket, comparable, { dimension: "structural", bucket: "same_bucket" }),
        selectionButton("No new observation inside window", payload.coverage.structural_no_new_observation, comparable, { dimension: "structural", bucket: "no_new_observation" }),
        selectionButton("Unavailable", payload.coverage.structural_unavailable_current, group.member_count, { dimension: "structural", bucket: "unavailable" }),
      );
      structural.append(counts, node("p", "evidence-inline", `New observation inside selected window ${ratio(payload.coverage.structural_fresh_in_window, comparable)} · current endpoints ${exactTime(payload.structural.endpoint_observed_at.earliest_current)} → ${exactTime(payload.structural.endpoint_observed_at.latest_current)}`));
      const distribution = node("p", "evidence-inline", `Current distribution · Deep Discount ${payload.structural.current_distribution.deep_discount} · Shallow Discount ${payload.structural.current_distribution.shallow_discount} · At EQM ${payload.structural.current_distribution.at_eqm} · Shallow Premium ${payload.structural.current_distribution.shallow_premium} · Deep Premium ${payload.structural.current_distribution.deep_premium} · Unavailable ${payload.structural.current_distribution.unavailable}`);
      structural.append(distribution);
    }

    const directional = detailSection("Directional evidence", `Current snapshot as of ${exactTime(payload.window.as_of)}; the selected window reports evidence freshness and events, not historical Current pressure`);
    const current = payload.directional.current_pressure;
    if (current.status === "unavailable") directional.append(node("p", "evidence-empty", "Current pressure evidence unavailable for this snapshot."));
    else {
      const currentHeading = node("h3", "", "Current pressure — now");
      const currentCounts = node("div", "evidence-count-grid");
      ["higher", "lower", "neutral"].forEach((bucket) => currentCounts.append(selectionButton(bucket[0].toUpperCase() + bucket.slice(1), current.summary[bucket], group.member_count, { dimension: "directional", evidence: "current_pressure", bucket })));
      directional.append(currentHeading, currentCounts, node("p", "evidence-inline", `Directional evidence inside selected window ${ratio(payload.coverage.current_pressure_evidence_fresh_in_window, payload.coverage.current_pressure_directional)}`));
    }
    const cumulative = payload.directional.cumulative_lifecycle_pressure_events;
    if (cumulative.status === "available") {
      directional.append(node("h3", "", "Cumulative lifecycle pressure events — selected window"));
      const latest = cumulative.summary.latest_event;
      const eventCounts = node("div", "evidence-count-grid");
      eventCounts.append(
        selectionButton("Latest Higher", latest.higher, group.member_count, { dimension: "directional", evidence: "cumulative_latest", bucket: "higher" }),
        selectionButton("Latest Lower", latest.lower, group.member_count, { dimension: "directional", evidence: "cumulative_latest", bucket: "lower" }),
        selectionButton("No event in window", latest.none, group.member_count, { dimension: "directional", evidence: "cumulative_latest", bucket: "none" }),
      );
      const rawEventButton = selectionButton("Raw cumulative events", cumulative.summary.event_count, cumulative.summary.event_count, { dimension: "directional", evidence: "cumulative_events" }, `${cumulative.summary.unique_contributors} unique members`);
      directional.append(eventCounts, rawEventButton, node("p", "evidence-inline", `${cumulative.summary.unique_contributors} unique members · ${cumulative.summary.event_count} raw events · ${cumulative.summary.repeated_contributors} repeated · ${cumulative.summary.both_direction_contributors} both directions within one lifecycle identity`));
      const compare = cumulative.summary.latest_event_vs_current;
      directional.append(node("p", "evidence-inline", `Latest event versus Current pressure · ${compare.same_direction} Same · ${compare.current_neutral} Current Neutral · ${compare.opposite_direction} Opposite · ${compare.current_unavailable} Current Unavailable`));
    } else directional.append(node("p", "evidence-empty", "Cumulative lifecycle pressure events unavailable for this snapshot."));
    const migrations = payload.directional.mrz_migrations;
    if (migrations.status === "available") {
      directional.append(node("h3", "", "Recent canonical MRZ migrations — selected window"));
      directional.append(selectionButton("Unique migration contributors", migrations.summary.unique_contributors, group.member_count, { dimension: "directional", evidence: "migration_contributors" }, `${migrations.summary.event_count} raw events`));
      directional.append(selectionButton("Raw migration events", migrations.summary.event_count, migrations.summary.event_count, { dimension: "directional", evidence: "migration_events" }, `${migrations.summary.unique_contributors} unique symbols`));
      directional.append(node("p", "evidence-inline", `${migrations.summary.higher_events} Higher · ${migrations.summary.lower_events} Lower · ${migrations.summary.same_midpoint_events || 0} Same midpoint · ${migrations.summary.repeated_contributors} repeated contributors · ${migrations.summary.both_direction_contributors} both directions · ${migrations.summary.route_change_events} route changes`));
      if (migrations.summary.event_count) directional.append(node("p", "evidence-inline", `${exactTime(migrations.summary.earliest_at)} → ${exactTime(migrations.summary.latest_at)}${migrations.summary.event_count > 1 ? ` · ${migrations.summary.span_seconds}s raw span` : ""}`));
      else directional.append(node("p", "evidence-empty", "No event in window."));
    } else directional.append(node("p", "evidence-empty", "Migration evidence unavailable for this snapshot."));
    wrapper.append(structural, directional);
    const drilldown = renderDrilldown(payload); if (drilldown) wrapper.append(drilldown);
    wrapper.append(renderConstituentBoard(payload));
    $("#groupEvidenceContent").replaceChildren(wrapper);
    $("#groupEvidenceContent").querySelectorAll("[data-selection]").forEach((button) => button.addEventListener("click", () => openSelection(JSON.parse(button.dataset.selection))));
  }

  function render(payload) {
    state.payload = payload;
    renderMeta(payload);
    if (payload.scope === "all_groups") renderAllGroups(payload); else renderNamedGroup(payload);
    $("#groupEvidenceLive").hidden = false;
    $("#groupEvidenceLive").removeAttribute("role");
    $("#groupEvidenceLive").setAttribute("role", "status");
    $("#groupEvidenceLive").className = "group-evidence-live";
    $("#groupEvidenceLive").textContent = payload.status === "partial"
      ? `Evidence loaded as of ${exactTime(payload.window.as_of)}; one or more dimensions are unavailable.`
      : `Evidence loaded as of ${exactTime(payload.window.as_of)}.`;
    globalObject.document.querySelectorAll("[data-group-window]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.groupWindow === state.scope.window)));
  }

  async function load() {
    state.controller?.abort();
    const controller = new AbortController(); state.controller = controller;
    const requestId = ++state.requestId;
    const scope = { ...state.scope };
    setLoading();
    const endpoint = scope.groupId === "all"
      ? `/api/group-evidence?window=${encodeURIComponent(scope.window)}`
      : `/api/group-evidence/${encodeURIComponent(scope.groupId)}?window=${encodeURIComponent(scope.window)}`;
    try {
      const response = await globalObject.fetch(endpoint, { cache: "no-store", signal: controller.signal });
      if (!derive.isGroupEvidenceRequestCurrent(
        { requestId, groupId: scope.groupId, window: scope.window },
        { requestId: state.requestId, groupId: state.scope.groupId, window: state.scope.window },
      )) return;
      if (response.status === 404) {
        const panel = node("section", "panel group-evidence-error");
        panel.append(node("h2", "", "Group no longer exists"), node("p", "", "This link points to a deleted saved group."));
        const back = node("button", "primary-button", "Return to All Groups"); back.type = "button"; back.addEventListener("click", () => { updateUrl({ group: "all", dimension: null, bucket: null, evidence: null }); load(); }); panel.append(back);
        $("#groupEvidenceContent").replaceChildren(panel); $("#groupEvidenceLive").textContent = "Group no longer exists."; return;
      }
      if (!response.ok) throw new Error(response.status === 422 ? "Unsupported window." : "Group evidence service unavailable.");
      const payload = await response.json();
      if (!derive.isGroupEvidenceRequestCurrent(
        { requestId, groupId: scope.groupId, window: scope.window },
        { requestId: state.requestId, groupId: state.scope.groupId, window: state.scope.window },
      )) return;
      state.lastSuccessful.set(`${scope.groupId}:${scope.window}`, payload);
      render(payload);
    } catch (error) {
      if (error.name === "AbortError") return;
      const previous = state.lastSuccessful.get(`${scope.groupId}:${scope.window}`);
      if (previous) {
        render(previous);
        $("#groupEvidenceLive").textContent = `Showing previously loaded evidence as of ${exactTime(previous.window.as_of)}. Refresh failed.`;
        $("#groupEvidenceLive").classList.add("error");
      } else setError(error.message || "Group evidence service unavailable.");
    }
  }

  async function loadRecentEvents() {
    const body = $("#recentTrackedEventsBody");
    const toggle = $("#recentTrackedEventsToggle");
    const expanded = body.hidden;
    body.hidden = !expanded; toggle.setAttribute("aria-expanded", String(expanded)); toggle.textContent = expanded ? "Hide" : "Show";
    if (!expanded || state.recentLoaded) return;
    $("#recentTrackedEventsStatus").textContent = "Loading recent tracked symbol events…";
    try {
      let members = state.payload?.group?.members || null;
      if (!members) {
        const groupsResponse = await globalObject.fetch("/api/groups", { cache: "no-store" });
        if (!groupsResponse.ok) throw new Error("Tracked membership unavailable.");
        const groups = (await groupsResponse.json()).groups || [];
        members = [...new Set(groups.flatMap((group) => group.members || []))];
      }
      const response = await globalObject.fetch("/api/mrz/events?limit=500", { cache: "no-store" });
      if (!response.ok) throw new Error("Recent event history unavailable.");
      const cutoff = Date.now() - 24 * 60 * 60 * 1000;
      const memberSet = new Set(members);
      const events = ((await response.json()).events || []).filter((event) => memberSet.has(event.symbol) && new Date(event.occurred_at).getTime() > cutoff);
      const list = node("ul", "recent-tracked-event-list");
      events.forEach((event) => {
        const row = node("li", "");
        const copy = node("div", ""); copy.append(node("strong", "", `${event.symbol} · ${event.event_name || event.event_type}`), node("p", "", `${exactTime(event.occurred_at)} · ${event.body || "Canonical event"}`));
        row.append(copy, detailLink("Open symbol", symbolUrl(event.symbol, { event: event.source_event_key || event.event_id || "" })));
        list.append(row);
      });
      if (!events.length) list.append(node("li", "evidence-empty", "No tracked symbol event in the last 24H."));
      $("#recentTrackedEventsList").replaceChildren(list);
      $("#recentTrackedEventsStatus").textContent = `${events.length} raw tracked symbol events loaded.`;
      state.recentLoaded = true;
    } catch (error) {
      $("#recentTrackedEventsStatus").textContent = `${error.message} Group Evidence remains available.`;
      $("#recentTrackedEventsStatus").classList.add("error");
    }
  }

  async function openEditor(group = null) {
    state.editingGroup = group;
    $("#groupEvidenceDialogTitle").textContent = group ? `Edit ${group.name}` : "New group";
    $("#groupEvidenceName").value = group?.name || "";
    $("#groupEvidenceDelete").hidden = !group;
    $("#groupEvidenceFormError").hidden = true;
    $("#groupEvidenceSymbolChoices").replaceChildren();
    $("#groupEvidenceChoicesStatus").textContent = "Loading symbols…";
    $("#groupEvidenceDialog").showModal();
    try {
      const response = await globalObject.fetch("/api/symbols", { cache: "no-store" });
      if (!response.ok) throw new Error("Symbols unavailable.");
      const symbols = (await response.json()).symbols || [];
      const selected = new Set(group?.members || []);
      symbols.forEach((symbolState) => {
        const label = node("label", ""); const input = node("input", ""); input.type = "checkbox"; input.value = symbolState.symbol; input.checked = selected.has(symbolState.symbol); label.append(input, globalObject.document.createTextNode(symbolState.symbol)); $("#groupEvidenceSymbolChoices").append(label);
      });
      $("#groupEvidenceChoicesStatus").textContent = `${symbols.length} canonical symbols available.`;
    } catch (error) {
      $("#groupEvidenceChoicesStatus").textContent = error.message;
    }
  }

  async function saveGroup(event) {
    event.preventDefault();
    if (event.submitter?.value === "cancel") { $("#groupEvidenceDialog").close(); return; }
    const members = [...$("#groupEvidenceSymbolChoices").querySelectorAll("input:checked")].map((input) => input.value);
    const payload = { name: $("#groupEvidenceName").value.trim(), members };
    if (!payload.name || !members.length) { $("#groupEvidenceFormError").textContent = "Add a name and at least one symbol."; $("#groupEvidenceFormError").hidden = false; return; }
    const editing = Boolean(state.editingGroup);
    const response = await globalObject.fetch(editing ? `/api/groups/${state.editingGroup.id}` : "/api/groups", { method: editing ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    if (!response.ok) { const body = await response.json().catch(() => ({})); $("#groupEvidenceFormError").textContent = body.detail || "Unable to save group."; $("#groupEvidenceFormError").hidden = false; return; }
    const saved = await response.json(); $("#groupEvidenceDialog").close(); updateUrl({ group: saved.id, dimension: null, bucket: null, evidence: null }); state.recentLoaded = false; await load();
  }

  async function deleteGroup() {
    if (!state.editingGroup || !globalObject.confirm(`Delete ${state.editingGroup.name}? Canonical EDGE observations and alerts are unaffected.`)) return;
    const response = await globalObject.fetch(`/api/groups/${state.editingGroup.id}`, { method: "DELETE" });
    if (!response.ok) { $("#groupEvidenceFormError").textContent = "Unable to delete group."; $("#groupEvidenceFormError").hidden = false; return; }
    $("#groupEvidenceDialog").close(); updateUrl({ group: "all", dimension: null, bucket: null, evidence: null }); state.recentLoaded = false; await load();
  }

  function bind() {
    globalObject.document.querySelectorAll("[data-group-window]").forEach((button) => button.addEventListener("click", () => { updateUrl({ window: button.dataset.groupWindow }); state.recentLoaded = false; load(); }));
    $("#groupEvidenceContent").addEventListener("click", (event) => {
      const groupButton = event.target.closest("[data-open-group]");
      if (groupButton) { updateUrl({ group: groupButton.dataset.openGroup, dimension: null, bucket: null, evidence: null }); state.recentLoaded = false; load(); return; }
      const selection = event.target.closest("[data-selection]");
      if (selection && state.payload?.scope === "all_groups") {
        const values = JSON.parse(selection.dataset.selection); updateUrl({ group: values.group, dimension: values.dimension, bucket: values.bucket || null, evidence: values.evidence || null }); state.recentLoaded = false; load();
      }
    });
    $("#recentTrackedEventsToggle").addEventListener("click", loadRecentEvents);
    $("#groupEvidenceNew").addEventListener("click", () => openEditor());
    $("#groupEvidenceEdit").addEventListener("click", () => openEditor(state.payload?.group || null));
    $("#groupEvidenceForm").addEventListener("submit", (event) => saveGroup(event).catch((error) => setError(error.message)));
    $("#groupEvidenceDelete").addEventListener("click", () => deleteGroup().catch((error) => setError(error.message)));
    globalObject.addEventListener("popstate", () => { state.scope = derive.parseGroupEvidenceState(globalObject.location.search); state.recentLoaded = false; load().then(() => $("#groupEvidenceTitle").focus()); });
  }

  async function mount() {
    if (state.scope.normalized) updateUrl({ group: state.scope.groupId, window: state.scope.window }, { replace: true });
    bind();
    await load();
    if (state.scope.openRecentEvents) loadRecentEvents();
  }

  const exported = { mount, state };
  globalObject.edgeGroupEvidence = exported;
  if (typeof module === "object" && module.exports) module.exports = exported;
}(globalThis));
