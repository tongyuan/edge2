const select = document.querySelector("#symbolSelect");
const emptyState = document.querySelector("#emptyState");
const stateCard = document.querySelector("#stateCard");
const healthState = document.querySelector("#healthState");
const locationHeatmap = document.querySelector("#locationHeatmap");
const heatmapEmpty = document.querySelector("#heatmapEmpty");
const primaryLocationGroups = document.querySelector("#primaryLocationGroups");
const secondaryLocationGroups = document.querySelector("#secondaryLocationGroups");
const locationDistribution = document.querySelector("#locationDistribution");
const groupTrackingToggle = document.querySelector("#groupTrackingToggle");
const groupTrackingStateLabel = document.querySelector("#groupTrackingStateLabel");
const groupTrackingWorkspace = document.querySelector("#groupTrackingWorkspace");
const savedGroupSelect = document.querySelector("#savedGroupSelect");
const newSavedGroup = document.querySelector("#newSavedGroup");
const groupEditor = document.querySelector("#groupEditor");
const groupEditorTitle = document.querySelector("#groupEditorTitle");
const groupName = document.querySelector("#groupName");
const selectedGroupSymbols = document.querySelector("#selectedGroupSymbols");
const showSelectedOnly = document.querySelector("#showSelectedOnly");
const clearSelectedGroup = document.querySelector("#clearSelectedGroup");
const cancelGroupEdit = document.querySelector("#cancelGroupEdit");
const saveSelectedGroup = document.querySelector("#saveSelectedGroup");
const groupFormError = document.querySelector("#groupFormError");
const savedGroupView = document.querySelector("#savedGroupView");
const savedGroupHeading = document.querySelector("#savedGroupHeading");
const savedGroupUpdated = document.querySelector("#savedGroupUpdated");
const savedGroupMembers = document.querySelector("#savedGroupMembers");
const editSavedGroup = document.querySelector("#editSavedGroup");
const deleteSavedGroup = document.querySelector("#deleteSavedGroup");
const currentStateTab = document.querySelector("#currentStateTab");
const migrationPathTab = document.querySelector("#migrationPathTab");
const currentStatePanel = document.querySelector("#currentStatePanel");
const migrationPathPanel = document.querySelector("#migrationPathPanel");
const migrationPathScroller = document.querySelector("#migrationPathScroller");
const {
  primaryLocationKeys,
  secondaryLocationKeys,
  hasActiveMrz,
  concentrationCheckEligible,
  routeAlignedActivity,
  activityTooltipText,
  accessibleChipLabel,
  preservedSelectedSymbol,
  groupSymbolsByLocation,
  locationDistributionFromGroups,
  formatLocationPercentage,
  migrationTendencyPresentation,
  createGroupTrackingState,
  setGroupTrackingEnabled,
  isGroupSelectionMode,
  beginNewGroup,
  beginEditGroup,
  openSavedGroup,
  toggleGroupSymbol,
  setShowSelectedOnly,
  clearGroupSelection,
  reconcileGroupTrackingState,
  groupTrackingSummary,
  visibleSymbolsForGroupTracking,
  timelinePosition,
  timelineTicks,
  authoritativeMrzEqmPair,
} = globalThis.edgeHeatmapState;
const {
  buildEvidencePresentation,
  buildActivationSourcePresentation,
  buildProductionConfirmationPresentation,
  buildMigrationPresentation,
  formatLatestObservationContext,
  formatActivatedAt,
  operatorCardHref,
} = globalThis.edgeMonitorPresentation;

const fields = {
  symbol: document.querySelector("#symbolName"),
  status: document.querySelector("#mrzStatus"),
  operatorCard: document.querySelector("#operatorCardLink"),
  owner: document.querySelector("#routeOwner"),
  bounds: document.querySelector("#mrzBounds"),
  activation: document.querySelector("#mrzActivation"),
  activatedAt: document.querySelector("#mrzActivatedAt"),
  migration: document.querySelector("#mrzMigration"),
  migrationTitle: document.querySelector("#mrzMigrationTitle"),
  migratedAt: document.querySelector("#mrzMigratedAt"),
  previousRange: document.querySelector("#mrzPreviousRange"),
  location: document.querySelector("#structuralLocation"),
  currentLocation: document.querySelector("#currentPriceLocation"),
  currentLocationContext: document.querySelector("#currentLocationContext"),
  evidence: document.querySelector("#evidence"),
  latest: document.querySelector("#latestObservation"),
  midpoint: document.querySelector("#mrzMidpoint"),
  activationSourceFact: document.querySelector("#activationSourceFact"),
  activationSource: document.querySelector("#activationSource"),
  productionConfirmationFact: document.querySelector("#productionConfirmationFact"),
  productionConfirmation: document.querySelector("#productionConfirmation"),
};
const activityTooltip = document.querySelector("#heatmapActivityTooltip");
let activityTooltipOwner = null;

const distributionFields = {
  deep_discount: {
    count: document.querySelector("#distributionDeepDiscountCount"),
    percentage: document.querySelector("#distributionDeepDiscountPercentage"),
    history: document.querySelector("#distributionDeepDiscountHistory"),
    historyEmpty: document.querySelector("#distributionDeepDiscountHistoryEmpty"),
    higher: document.querySelector("#distributionDeepDiscountHigher"),
    lower: document.querySelector("#distributionDeepDiscountLower"),
    samples: document.querySelector("#distributionDeepDiscountSamples"),
  },
  shallow_discount: {
    count: document.querySelector("#distributionShallowDiscountCount"),
    percentage: document.querySelector("#distributionShallowDiscountPercentage"),
    history: document.querySelector("#distributionShallowDiscountHistory"),
    historyEmpty: document.querySelector("#distributionShallowDiscountHistoryEmpty"),
    higher: document.querySelector("#distributionShallowDiscountHigher"),
    lower: document.querySelector("#distributionShallowDiscountLower"),
    samples: document.querySelector("#distributionShallowDiscountSamples"),
  },
  shallow_premium: {
    count: document.querySelector("#distributionShallowPremiumCount"),
    percentage: document.querySelector("#distributionShallowPremiumPercentage"),
    history: document.querySelector("#distributionShallowPremiumHistory"),
    historyEmpty: document.querySelector("#distributionShallowPremiumHistoryEmpty"),
    higher: document.querySelector("#distributionShallowPremiumHigher"),
    lower: document.querySelector("#distributionShallowPremiumLower"),
    samples: document.querySelector("#distributionShallowPremiumSamples"),
  },
  deep_premium: {
    count: document.querySelector("#distributionDeepPremiumCount"),
    percentage: document.querySelector("#distributionDeepPremiumPercentage"),
    history: document.querySelector("#distributionDeepPremiumHistory"),
    historyEmpty: document.querySelector("#distributionDeepPremiumHistoryEmpty"),
    higher: document.querySelector("#distributionDeepPremiumHigher"),
    lower: document.querySelector("#distributionDeepPremiumLower"),
    samples: document.querySelector("#distributionDeepPremiumSamples"),
  },
};
const distributionTotals = {
  discount: document.querySelector("#distributionDiscountTotal"),
  premium: document.querySelector("#distributionPremiumTotal"),
};
const groupCurrentFields = {
  count: document.querySelector("#selectedGroupCount"),
  btd: document.querySelector("#groupBtdCount"),
  str: document.querySelector("#groupStrCount"),
  active: document.querySelector("#groupActiveMrzCount"),
  higher: document.querySelector("#groupHigherCount"),
  lower: document.querySelector("#groupLowerCount"),
  noMigration: document.querySelector("#groupNoMigrationCount"),
  locations: {
    deep_discount: document.querySelector("#groupDeepDiscountCount"),
    shallow_discount: document.querySelector("#groupShallowDiscountCount"),
    shallow_premium: document.querySelector("#groupShallowPremiumCount"),
    deep_premium: document.querySelector("#groupDeepPremiumCount"),
  },
};

let overviewSymbols = [];
let minimumClusterObservations = null;
let locationMigrationTendency = {};
let groupTrackingState = createGroupTrackingState();
let savedGroups = [];
let activeSavedGroup = null;

const formatPrice = (value) => value == null ? "—" : new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 12,
}).format(value);

const locationLabels = {
  deep_discount_core_mrz: "Deep Discount",
  shallow_discount_core_mrz: "Shallow Discount",
  shallow_premium_core_mrz: "Shallow Premium",
  deep_premium_core_mrz: "Deep Premium",
  deep_discount: "Deep Discount",
  shallow_discount: "Shallow Discount",
  shallow_premium: "Shallow Premium",
  deep_premium: "Deep Premium",
  below_ipda_range: "Below IPDA Range",
  above_ipda_range: "Above IPDA Range",
};

const formatLocation = (value) => value == null ? "—" : locationLabels[value] || "—";

function renderFact(field, primary, secondary = [], sections = []) {
  const primaryLine = document.createElement("span");
  primaryLine.className = "fact-primary";
  primaryLine.textContent = primary;
  const secondaryLines = secondary.filter(Boolean).map((text) => {
    const line = document.createElement("span");
    line.className = "fact-support";
    line.textContent = text;
    return line;
  });
  const sectionLines = sections.flatMap((section) => {
    const label = document.createElement("span");
    label.className = "fact-section-label";
    label.textContent = section.label;
    const lines = section.lines.filter(Boolean).map((text) => {
      const line = document.createElement("span");
      line.className = "fact-diagnostic";
      line.textContent = text;
      return line;
    });
    return [label, ...lines];
  });
  field.replaceChildren(primaryLine, ...secondaryLines, ...sectionLines);
}

function positionActivityTooltip(button) {
  const triggerRect = button.getBoundingClientRect();
  const tooltipRect = activityTooltip.getBoundingClientRect();
  const viewportMargin = 8;
  const gap = 8;
  const centeredLeft = triggerRect.left + ((triggerRect.width - tooltipRect.width) / 2);
  const maximumLeft = Math.max(viewportMargin, window.innerWidth - tooltipRect.width - viewportMargin);
  const left = Math.min(Math.max(centeredLeft, viewportMargin), maximumLeft);
  let top = triggerRect.top - tooltipRect.height - gap;
  if (top < viewportMargin) top = triggerRect.bottom + gap;
  top = Math.min(top, window.innerHeight - tooltipRect.height - viewportMargin);
  activityTooltip.style.left = `${Math.round(left)}px`;
  activityTooltip.style.top = `${Math.round(Math.max(top, viewportMargin))}px`;
}

function showActivityTooltip(button, text) {
  if (!text) return;
  activityTooltipOwner = button;
  activityTooltip.textContent = text;
  activityTooltip.hidden = false;
  button.setAttribute("aria-describedby", activityTooltip.id);
  positionActivityTooltip(button);
}

function hideActivityTooltip(button) {
  if (activityTooltipOwner !== button) return;
  button.removeAttribute("aria-describedby");
  activityTooltip.hidden = true;
  activityTooltipOwner = null;
}

window.addEventListener("resize", () => {
  if (activityTooltipOwner) positionActivityTooltip(activityTooltipOwner);
});
window.addEventListener("scroll", () => {
  if (activityTooltipOwner) positionActivityTooltip(activityTooltipOwner);
}, true);

function createLocationGroup(key, symbols, minimumClusterObservations, secondary = false) {
  const group = document.createElement("section");
  group.className = secondary ? "location-group secondary" : "location-group";

  const heading = document.createElement("h3");
  heading.textContent = key === "unavailable" ? "Unavailable" : locationLabels[key];
  group.append(heading);

  const symbolList = document.createElement("div");
  symbolList.className = "symbol-chips";
  if (symbols.length === 0) {
    const empty = document.createElement("span");
    empty.className = "group-empty";
    empty.textContent = "No symbols";
    symbolList.append(empty);
  } else {
    symbols.forEach((symbolState) => {
      const active = hasActiveMrz(symbolState);
      const activity = routeAlignedActivity(symbolState);
      const { symbol } = symbolState;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "symbol-chip";
      const groupSelected = (
        isGroupSelectionMode(groupTrackingState)
        && groupTrackingState.selectedSymbols.has(symbol)
      );
      button.classList.toggle("active-mrz", active);
      button.classList.toggle("group-selected", groupSelected);
      button.classList.toggle(
        "evidence-ready",
        concentrationCheckEligible(symbolState, minimumClusterObservations),
      );
      if (activity && activity.tier !== "none") {
        button.classList.add(`activity-${activity.tier}`);
      }
      button.dataset.symbol = symbol;
      button.setAttribute("aria-pressed", String(groupSelected));
      const locationLabel = key === "unavailable" ? "Unavailable" : formatLocation(key);
      const chipLabel = accessibleChipLabel(symbolState, locationLabel);
      button.setAttribute(
        "aria-label",
        groupSelected ? `${chipLabel}, selected for group tracking` : chipLabel,
      );
      const tooltipText = activity ? activityTooltipText(activity.count) : null;
      if (tooltipText) {
        button.addEventListener("mouseenter", () => showActivityTooltip(button, tooltipText));
        button.addEventListener("mouseleave", () => hideActivityTooltip(button));
        button.addEventListener("focus", () => showActivityTooltip(button, tooltipText));
        button.addEventListener("blur", () => hideActivityTooltip(button));
      }
      if (active) {
        const indicator = document.createElement("span");
        indicator.className = "active-mrz-dot";
        indicator.setAttribute("aria-hidden", "true");
        button.append(indicator);
      }
      if (groupSelected) {
        const check = document.createElement("span");
        check.className = "group-selection-check";
        check.setAttribute("aria-hidden", "true");
        check.textContent = "✓";
        button.append(check);
      }
      const label = document.createElement("span");
      label.textContent = symbol;
      button.append(label);
      button.addEventListener("click", () => handleHeatmapChipClick(symbol).catch(showError));
      symbolList.append(button);
    });
  }
  group.append(symbolList);
  return group;
}

function renderLocationDistribution(groups, migrationTendency) {
  const distribution = locationDistributionFromGroups(groups);
  primaryLocationKeys.forEach((key) => {
    const bucket = distribution.buckets[key];
    const fieldsForLocation = distributionFields[key];
    fieldsForLocation.count.textContent = String(bucket.count);
    fieldsForLocation.percentage.textContent = formatLocationPercentage(
      bucket.percentage,
    );
    const migration = migrationTendencyPresentation(migrationTendency?.[key]);
    fieldsForLocation.history.hidden = !migration.hasHistory;
    fieldsForLocation.historyEmpty.hidden = migration.hasHistory;
    fieldsForLocation.higher.textContent = migration.higherLabel;
    fieldsForLocation.lower.textContent = migration.lowerLabel;
    fieldsForLocation.samples.textContent = migration.sampleLabel;
  });
  distributionTotals.discount.textContent = (
    `${distribution.discountTotal.count} · ${formatLocationPercentage(distribution.discountTotal.percentage)}`
  );
  distributionTotals.premium.textContent = (
    `${distribution.premiumTotal.count} · ${formatLocationPercentage(distribution.premiumTotal.percentage)}`
  );
  locationDistribution.setAttribute(
    "aria-label",
    `Current location distribution and historical MRZ migration tendency for ${distribution.classifiedTotal} classified symbols`,
  );
}

function groupMemberListItems(symbols, clickable = false) {
  return symbols.map((symbol) => {
    const item = document.createElement("li");
    if (clickable) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = symbol;
      button.setAttribute("aria-label", `Open ${symbol} in MRZ Monitor`);
      button.addEventListener("click", () => selectGroupMember(symbol).catch(showError));
      item.append(button);
    } else {
      item.textContent = symbol;
    }
    return item;
  });
}

function renderSavedGroupSelector() {
  if (savedGroups.length === 0) {
    savedGroupSelect.replaceChildren(new Option("No saved groups", ""));
    savedGroupSelect.disabled = true;
    return;
  }
  savedGroupSelect.replaceChildren(...savedGroups.map((group) => (
    new Option(`${group.name} · ${group.member_count}`, String(group.id))
  )));
  savedGroupSelect.disabled = false;
  const selectedId = groupTrackingState.activeGroupId;
  savedGroupSelect.value = selectedId == null ? "" : String(selectedId);
}

function updateSaveGroupAvailability() {
  saveSelectedGroup.disabled = (
    !groupName.value.trim() || groupTrackingState.selectedSymbols.size === 0
  );
}

function renderGroupEditor() {
  const selecting = isGroupSelectionMode(groupTrackingState);
  groupEditor.hidden = !selecting;
  if (!selecting) return;
  const summary = groupTrackingSummary(overviewSymbols, groupTrackingState);
  groupCurrentFields.count.textContent = String(summary.selectedCount);
  selectedGroupSymbols.replaceChildren(
    ...groupMemberListItems(summary.selectedStates.map(({ symbol }) => symbol)),
  );
  groupEditorTitle.textContent = groupTrackingState.mode === "edit" ? "EDIT GROUP" : "NEW GROUP";
  showSelectedOnly.checked = groupTrackingState.showSelectedOnly;
  updateSaveGroupAvailability();
}

function showGroupTab(tabName) {
  const showCurrent = tabName !== "migration";
  currentStateTab.setAttribute("aria-selected", String(showCurrent));
  migrationPathTab.setAttribute("aria-selected", String(!showCurrent));
  currentStatePanel.hidden = !showCurrent;
  migrationPathPanel.hidden = showCurrent;
}

function renderSavedGroupView() {
  const visible = groupTrackingState.mode === "saved" && activeSavedGroup !== null;
  savedGroupView.hidden = !visible;
  if (!visible) return;
  const noun = activeSavedGroup.member_count === 1 ? "member" : "members";
  savedGroupHeading.textContent = (
    `${activeSavedGroup.name} · ${activeSavedGroup.member_count} ${noun}`
  );
  savedGroupUpdated.textContent = "Saved cohort · Live canonical EDGE state";
  savedGroupMembers.replaceChildren(
    ...groupMemberListItems(activeSavedGroup.members, true),
  );
  const state = activeSavedGroup.current_state;
  primaryLocationKeys.forEach((key) => {
    groupCurrentFields.locations[key].textContent = String(state.location[key] ?? 0);
  });
  groupCurrentFields.active.textContent = `${state.active_mrz.count} / ${state.active_mrz.total}`;
  groupCurrentFields.higher.textContent = String(state.migration_breadth.higher);
  groupCurrentFields.lower.textContent = String(state.migration_breadth.lower);
  groupCurrentFields.noMigration.textContent = String(state.migration_breadth.no_migration);
  groupCurrentFields.btd.textContent = String(state.route.BTD);
  groupCurrentFields.str.textContent = String(state.route.STR);
}

function renderGroupWorkspace() {
  groupTrackingWorkspace.hidden = !groupTrackingState.enabled;
  groupTrackingToggle.checked = groupTrackingState.enabled;
  groupTrackingStateLabel.textContent = groupTrackingState.enabled ? "On" : "Off";
  renderSavedGroupSelector();
  if (!groupTrackingState.enabled) return;
  renderGroupEditor();
  renderSavedGroupView();
}

function formatPathTimestamp(value) {
  const formatted = formatOperatorTimestampUtcMinus4(value);
  return formatted || "Time unavailable";
}

function formatPathTick(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
  }).format(date);
}

function migrationStateTooltip(symbol, state, eqmPair) {
  const fields = [
    `${symbol} · ${state.location_label}`,
    formatPathTimestamp(state.occurred_at),
    `Current midpoint: ${formatPrice(state.midpoint)}`,
  ];
  if (state.direction) {
    fields.push(`Migration: ${state.direction === "higher" ? "Higher" : "Lower"}`);
  } else if (!eqmPair) {
    fields.push("Initial authority");
  }
  if (eqmPair) {
    fields.push(
      `Previous MRZ midpoint: ${formatPrice(eqmPair.previousMidpoint)}`,
      `MRZ EQM: ${formatPrice(eqmPair.eqm)}`,
    );
  }
  return fields.join(" · ");
}

function renderMigrationPath(payload) {
  const hasAnyHistory = payload.paths.some(({ states }) => states.length > 0);
  if (!hasAnyHistory) {
    const empty = document.createElement("p");
    empty.className = "migration-path-all-empty";
    empty.textContent = "No authoritative MRZ history for this group.";
    migrationPathScroller.replaceChildren(empty);
    return;
  }

  const timeline = document.createElement("div");
  timeline.className = "migration-path-timeline";
  const axis = document.createElement("div");
  axis.className = "migration-path-axis";
  axis.append(document.createElement("span"));
  const ticks = document.createElement("div");
  ticks.className = "migration-path-ticks";
  timelineTicks(payload.timeline.started_at, payload.timeline.ended_at).forEach((value) => {
    const tick = document.createElement("span");
    tick.className = "migration-path-tick";
    tick.style.left = `${timelinePosition(value, payload.timeline.started_at, payload.timeline.ended_at)}%`;
    tick.textContent = formatPathTick(value);
    tick.title = formatPathTimestamp(value);
    ticks.append(tick);
  });
  axis.append(ticks);
  timeline.append(axis);

  payload.paths.forEach((path) => {
    const row = document.createElement("div");
    row.className = "migration-path-row";
    const label = document.createElement("div");
    label.className = "migration-path-row-label";
    label.textContent = path.symbol;
    const track = document.createElement("div");
    track.className = "migration-path-track";
    if (path.states.length === 0) {
      const empty = document.createElement("span");
      empty.className = "migration-path-empty";
      empty.textContent = "No authoritative MRZ history";
      track.append(empty);
    } else {
      const positions = path.states.map((state) => Math.min(98, Math.max(
        2,
        timelinePosition(
          state.occurred_at,
          payload.timeline.started_at,
          payload.timeline.ended_at,
        ),
      )));
      const line = document.createElement("span");
      line.className = "migration-path-line";
      line.style.left = `${positions[0]}%`;
      line.style.width = `${positions.at(-1) - positions[0]}%`;
      track.append(line);
      path.states.forEach((state, index) => {
        const node = document.createElement("span");
        const eqmPair = authoritativeMrzEqmPair(path.states, index);
        node.className = `migration-path-state${state.direction ? ` ${state.direction}` : ""}`;
        node.style.left = `${positions[index]}%`;
        node.textContent = state.location_code;
        node.title = migrationStateTooltip(path.symbol, state, eqmPair);
        node.setAttribute("aria-label", node.title);
        if (state.direction) {
          const direction = document.createElement("span");
          direction.className = "migration-path-direction";
          direction.setAttribute("aria-hidden", "true");
          direction.textContent = state.direction === "higher" ? "↑" : "↓";
          node.append(direction);
        }
        track.append(node);
      });
    }
    row.append(label, track);
    timeline.append(row);
  });
  migrationPathScroller.replaceChildren(timeline);
}

function renderLocationHeatmap(symbols, minimumObservations, groups) {
  if (symbols.length === 0) {
    locationHeatmap.hidden = true;
    heatmapEmpty.hidden = false;
    heatmapEmpty.textContent = "No symbols yet";
    return;
  }

  primaryLocationGroups.replaceChildren(
    ...primaryLocationKeys.map((key) => (
      createLocationGroup(key, groups[key], minimumObservations)
    )),
  );
  const populatedSecondaryKeys = secondaryLocationKeys.filter((key) => groups[key].length > 0);
  secondaryLocationGroups.replaceChildren(
    ...populatedSecondaryKeys.map((key) => (
      createLocationGroup(key, groups[key], minimumObservations, true)
    )),
  );
  secondaryLocationGroups.hidden = populatedSecondaryKeys.length === 0;
  heatmapEmpty.hidden = true;
  locationHeatmap.hidden = false;
}

function renderMonitorOverview() {
  const allGroups = groupSymbolsByLocation(overviewSymbols, minimumClusterObservations);
  renderLocationDistribution(allGroups, locationMigrationTendency);
  const visibleSymbols = visibleSymbolsForGroupTracking(overviewSymbols, groupTrackingState);
  const visibleGroups = visibleSymbols === overviewSymbols
    ? allGroups
    : groupSymbolsByLocation(visibleSymbols, minimumClusterObservations);
  renderLocationHeatmap(visibleSymbols, minimumClusterObservations, visibleGroups);
  renderGroupWorkspace();
  updateSelectedChip(select.value);
}

function updateSelectedChip(symbol) {
  document.querySelectorAll(".symbol-chip").forEach((chip) => {
    const singleSelected = !isGroupSelectionMode(groupTrackingState) && chip.dataset.symbol === symbol;
    const groupSelected = (
      isGroupSelectionMode(groupTrackingState)
      && groupTrackingState.selectedSymbols.has(chip.dataset.symbol)
    );
    chip.classList.toggle("selected", singleSelected);
    chip.classList.toggle("group-selected", groupSelected);
    chip.setAttribute("aria-pressed", String(groupSelected || singleSelected));
  });
}

async function loadHealth() {
  try {
    const response = await fetch("/health");
    const health = await response.json();
    healthState.textContent = health.status === "ok" ? "System healthy" : "System unavailable";
    healthState.classList.toggle("ok", health.status === "ok");
  } catch {
    healthState.textContent = "System unavailable";
  }
}

async function loadSymbols() {
  const response = await fetch("/api/symbols");
  if (!response.ok) throw new Error("Unable to load symbols");
  const payload = await response.json();
  const selectedSymbol = preservedSelectedSymbol(select.value, payload.symbols);
  overviewSymbols = payload.symbols;
  minimumClusterObservations = payload.minimum_cluster_observations;
  locationMigrationTendency = payload.location_migration_tendency || {};
  groupTrackingState = reconcileGroupTrackingState(groupTrackingState, overviewSymbols);
  select.replaceChildren(new Option("Select a symbol", ""));
  overviewSymbols.forEach(({ symbol }) => select.add(new Option(symbol, symbol)));
  select.disabled = overviewSymbols.length === 0;
  select.value = selectedSymbol;
  renderMonitorOverview();
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = "Unable to complete the group request";
    try {
      const payload = await response.json();
      if (payload.detail) message = String(payload.detail).replaceAll("_", " ");
    } catch {
      // Retain the operator-safe fallback.
    }
    throw new Error(message);
  }
  return response.json();
}

async function loadSavedGroupDefinitions() {
  const payload = await requestJson("/api/groups");
  savedGroups = payload.groups;
  renderSavedGroupSelector();
}

async function openSavedGroupById(groupId) {
  const report = await requestJson(`/api/groups/${encodeURIComponent(groupId)}`);
  activeSavedGroup = report;
  groupTrackingState = openSavedGroup(groupTrackingState, report.id);
  showGroupTab("current");
  renderMonitorOverview();
}

function startNewGroup() {
  groupTrackingState = beginNewGroup(groupTrackingState);
  groupName.value = "";
  groupFormError.hidden = true;
  showGroupTab("current");
  renderMonitorOverview();
  groupName.focus();
}

function startEditingGroup() {
  if (!activeSavedGroup) return;
  groupTrackingState = beginEditGroup(groupTrackingState, activeSavedGroup);
  groupName.value = activeSavedGroup.name;
  groupFormError.hidden = true;
  renderMonitorOverview();
  groupName.focus();
}

async function cancelGroupEditor() {
  groupFormError.hidden = true;
  if (activeSavedGroup) {
    groupTrackingState = openSavedGroup(groupTrackingState, activeSavedGroup.id);
    showGroupTab("current");
    renderMonitorOverview();
    return;
  }
  if (savedGroups.length > 0) {
    await openSavedGroupById(savedGroups[0].id);
    return;
  }
  groupTrackingState = setGroupTrackingEnabled(groupTrackingState, false);
  renderMonitorOverview();
}

async function saveGroup(event) {
  event.preventDefault();
  const name = groupName.value.trim();
  const members = [...groupTrackingState.selectedSymbols];
  if (!name || members.length === 0) {
    groupFormError.textContent = "Enter a group name and select at least one symbol.";
    groupFormError.hidden = false;
    return;
  }
  saveSelectedGroup.disabled = true;
  groupFormError.hidden = true;
  const editing = groupTrackingState.mode === "edit";
  const groupId = groupTrackingState.activeGroupId;
  try {
    const report = await requestJson(
      editing ? `/api/groups/${encodeURIComponent(groupId)}` : "/api/groups",
      {
        method: editing ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, members }),
      },
    );
    activeSavedGroup = report;
    await loadSavedGroupDefinitions();
    groupTrackingState = openSavedGroup(groupTrackingState, report.id);
    showGroupTab("current");
    renderMonitorOverview();
  } catch (error) {
    groupFormError.textContent = error.message;
    groupFormError.hidden = false;
    updateSaveGroupAvailability();
  }
}

async function removeActiveSavedGroup() {
  if (!activeSavedGroup) return;
  if (!globalThis.confirm(`Delete saved group ${activeSavedGroup.name}? MRZ history is not affected.`)) {
    return;
  }
  const removedId = activeSavedGroup.id;
  await requestJson(`/api/groups/${encodeURIComponent(removedId)}`, { method: "DELETE" });
  activeSavedGroup = null;
  await loadSavedGroupDefinitions();
  if (savedGroups.length > 0) {
    await openSavedGroupById(savedGroups[0].id);
  } else {
    startNewGroup();
  }
}

async function openMigrationPath() {
  if (!activeSavedGroup) return;
  showGroupTab("migration");
  const groupId = activeSavedGroup.id;
  const loading = document.createElement("p");
  loading.className = "migration-path-all-empty";
  loading.textContent = "Loading authoritative history…";
  migrationPathScroller.replaceChildren(loading);
  const payload = await requestJson(`/api/groups/${encodeURIComponent(groupId)}/migration-path`);
  if (activeSavedGroup?.id === groupId) renderMigrationPath(payload);
}

async function selectGroupMember(symbol) {
  await selectSymbol(symbol);
  document.querySelector(".selected-detail")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function handleHeatmapChipClick(symbol) {
  if (!isGroupSelectionMode(groupTrackingState)) {
    await selectSymbol(symbol);
    return;
  }
  groupTrackingState = toggleGroupSymbol(groupTrackingState, symbol);
  renderMonitorOverview();
}

async function selectSymbol(symbol) {
  select.value = symbol;
  updateSelectedChip(symbol);
  await loadSymbol(symbol);
}

async function loadSymbol(symbol) {
  if (!symbol) {
    stateCard.hidden = true;
    emptyState.hidden = false;
    return;
  }
  const response = await fetch(`/api/symbols/${encodeURIComponent(symbol)}`);
  if (!response.ok) throw new Error("Unable to load symbol state");
  renderSymbol(await response.json());
}

function renderSymbol(state) {
  const active = state.mrz_status === "active";
  fields.symbol.textContent = state.symbol;
  fields.status.textContent = active ? "ACTIVE" : "UNESTABLISHED";
  fields.status.classList.toggle("unestablished", !active);
  const operatorCardUrl = operatorCardHref(state);
  fields.operatorCard.hidden = operatorCardUrl === null;
  if (operatorCardUrl) {
    fields.operatorCard.href = operatorCardUrl;
    fields.operatorCard.setAttribute("aria-label", `Operator Card for ${state.symbol}`);
  } else {
    fields.operatorCard.removeAttribute("href");
    fields.operatorCard.removeAttribute("aria-label");
  }
  fields.owner.textContent = active ? state.route_owner : "—";
  fields.owner.classList.toggle("unestablished", !active);
  fields.owner.classList.toggle("btd", active && state.route_owner === "BTD");
  fields.owner.classList.toggle("str", active && state.route_owner === "STR");
  fields.bounds.textContent = active
    ? `${formatPrice(state.core_mrz_lower)} – ${formatPrice(state.core_mrz_upper)}`
    : "—";
  const activatedAt = formatActivatedAt(state, formatOperatorTimestampUtcMinus4);
  fields.activation.hidden = !activatedAt;
  fields.activatedAt.textContent = activatedAt || "—";
  const migration = buildMigrationPresentation(
    state,
    formatOperatorTimestampUtcMinus4,
    formatPrice,
  );
  fields.migration.hidden = migration === null;
  fields.migrationTitle.textContent = migration?.title || "MIGRATED";
  fields.migratedAt.textContent = migration?.timestamp || "—";
  fields.previousRange.textContent = migration?.previousRange || "—";
  fields.location.textContent = active ? formatLocation(state.structural_location) : "—";
  fields.currentLocation.textContent = formatLocation(state.current_price_location);
  fields.currentLocationContext.textContent = state.current_location_context || "—";
  const evidence = buildEvidencePresentation(
    state,
    formatOperatorTimestampUtcMinus4,
    formatPrice,
    formatLocation,
  );
  renderFact(fields.evidence, evidence.primary, evidence.secondary, evidence.checks);
  renderFact(
    fields.latest,
    formatPrice(state.latest_observation_price),
    [formatLatestObservationContext(state, formatOperatorTimestampUtcMinus4)],
  );
  fields.midpoint.textContent = formatPrice(state.core_mrz_midpoint);
  const activationSource = buildActivationSourcePresentation(state);
  fields.activationSourceFact.hidden = activationSource === null;
  renderFact(
    fields.activationSource,
    activationSource?.primary || "—",
    activationSource?.secondary || [],
  );
  const productionConfirmation = buildProductionConfirmationPresentation(
    state,
    formatOperatorTimestampUtcMinus4,
    formatPrice,
  );
  fields.productionConfirmationFact.hidden = productionConfirmation === null;
  renderFact(
    fields.productionConfirmation,
    productionConfirmation?.primary || "—",
    productionConfirmation?.secondary || [],
  );
  emptyState.hidden = true;
  stateCard.hidden = false;
}

select.addEventListener("change", () => selectSymbol(select.value).catch(showError));
groupTrackingToggle.addEventListener("change", () => (async () => {
  if (!groupTrackingToggle.checked) {
    groupTrackingState = setGroupTrackingEnabled(groupTrackingState, false);
    renderMonitorOverview();
    return;
  }
  groupTrackingState = setGroupTrackingEnabled(groupTrackingState, true);
  if (activeSavedGroup) {
    await openSavedGroupById(activeSavedGroup.id);
  } else if (savedGroups.length > 0) {
    await openSavedGroupById(savedGroups[0].id);
  } else {
    startNewGroup();
  }
})().catch(showError));
savedGroupSelect.addEventListener("change", () => {
  if (savedGroupSelect.value) openSavedGroupById(savedGroupSelect.value).catch(showError);
});
newSavedGroup.addEventListener("click", startNewGroup);
editSavedGroup.addEventListener("click", startEditingGroup);
deleteSavedGroup.addEventListener("click", () => removeActiveSavedGroup().catch(showError));
groupEditor.addEventListener("submit", saveGroup);
groupName.addEventListener("input", updateSaveGroupAvailability);
cancelGroupEdit.addEventListener("click", () => cancelGroupEditor().catch(showError));
currentStateTab.addEventListener("click", () => showGroupTab("current"));
migrationPathTab.addEventListener("click", () => openMigrationPath().catch(showError));
showSelectedOnly.addEventListener("change", () => {
  groupTrackingState = setShowSelectedOnly(
    groupTrackingState,
    showSelectedOnly.checked,
  );
  renderMonitorOverview();
});
clearSelectedGroup.addEventListener("click", () => {
  groupTrackingState = clearGroupSelection(groupTrackingState);
  renderMonitorOverview();
});

function showError(error) {
  emptyState.hidden = false;
  stateCard.hidden = true;
  emptyState.querySelector("p").textContent = error.message;
  if (heatmapEmpty.textContent === "Loading locations…") {
    heatmapEmpty.textContent = "Locations unavailable";
  }
}

function requestedSymbolFromQuery(search = globalThis.location?.search || "") {
  const symbol = new URLSearchParams(search).get("symbol");
  return symbol && /^[A-Z0-9][A-Z0-9:._-]{0,39}$/.test(symbol) ? symbol : null;
}

async function initializeMonitor() {
  loadHealth();
  await Promise.all([loadSymbols(), loadSavedGroupDefinitions()]);
  const requestedSymbol = requestedSymbolFromQuery();
  if (requestedSymbol && Array.from(select.options).some(({ value }) => value === requestedSymbol)) {
    await selectSymbol(requestedSymbol);
  }
}

initializeMonitor().catch(showError);
