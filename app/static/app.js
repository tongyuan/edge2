const select = document.querySelector("#symbolSelect");
const emptyState = document.querySelector("#emptyState");
const stateCard = document.querySelector("#stateCard");
const healthState = document.querySelector("#healthState");
const locationHeatmap = document.querySelector("#locationHeatmap");
const heatmapEmpty = document.querySelector("#heatmapEmpty");
const primaryLocationGroups = document.querySelector("#primaryLocationGroups");
const secondaryLocationGroups = document.querySelector("#secondaryLocationGroups");
const locationDistribution = document.querySelector("#locationDistribution");
const distributionAtEqmCount = document.querySelector("#distributionAtEqmCount");
const universePressureHeadline = document.querySelector("#universePressureHeadline");
const universePressureParticipation = document.querySelector("#universePressureParticipation");
const universePressureButtons = [...document.querySelectorAll("[data-universe-pressure-direction]")];
const universePressureCounts = {
  higher: document.querySelector("#universePressureHigherCount"),
  lower: document.querySelector("#universePressureLowerCount"),
  neutral: document.querySelector("#universePressureNeutralCount"),
};
const pressureMap = document.querySelector("#pressureMap");
const pressureMapDrilldown = document.querySelector("#pressureMapDrilldown");
const pressureMapDrilldownTitle = document.querySelector("#pressureMapDrilldownTitle");
const pressureMapDrilldownSummary = document.querySelector("#pressureMapDrilldownSummary");
const pressureMapMembers = document.querySelector("#pressureMapMembers");
const heatmapPressureButtons = [...document.querySelectorAll("[data-heatmap-pressure-filter]")];
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
const peerPressureTab = document.querySelector("#peerPressureTab");
const currentStatePanel = document.querySelector("#currentStatePanel");
const peerPressurePanel = document.querySelector("#peerPressurePanel");
const peerPressureHeadline = document.querySelector("#peerPressureHeadline");
const peerPressureSummary = document.querySelector("#peerPressureSummary");
const peerPressureParticipation = document.querySelector("#peerPressureParticipation");
const peerPressureDrilldown = document.querySelector("#peerPressureDrilldown");
const peerPressureDrilldownTitle = document.querySelector("#peerPressureDrilldownTitle");
const peerPressureDrilldownSummary = document.querySelector("#peerPressureDrilldownSummary");
const peerPressureMembers = document.querySelector("#peerPressureMembers");
const peerPressureButtons = [...document.querySelectorAll("[data-pressure-direction]")];
const peerPressureCounts = {
  higher: document.querySelector("#peerPressureHigherCount"),
  lower: document.querySelector("#peerPressureLowerCount"),
  neutral: document.querySelector("#peerPressureNeutralCount"),
};
const migrationHistoryDisclosure = document.querySelector("#migrationHistoryDisclosure");
const migrationPathScroller = document.querySelector("#migrationPathScroller");
const groupMigrationState = document.querySelector("#groupMigrationState");
const recentMigrationDirection = document.querySelector("#recentMigrationDirection");
const migrationParticipation = document.querySelector("#migrationParticipation");
const pressureMigrationAlignment = document.querySelector("#pressureMigrationAlignment");
const migrationMomentumMagnitude = document.querySelector("#migrationMomentumMagnitude");
const migrationMomentumHistogram = document.querySelector("#migrationMomentumHistogram");
const migrationMomentumDetail = document.querySelector("#migrationMomentumDetail");
const symbolMigrationStates = document.querySelector("#symbolMigrationStates");
const migrationEvidenceDialog = document.querySelector("#migrationEvidenceDialog");
const migrationEvidenceTitle = document.querySelector("#migrationEvidenceTitle");
const migrationEvidenceSummary = document.querySelector("#migrationEvidenceSummary");
const migrationEvidenceList = document.querySelector("#migrationEvidenceList");
const migrationEvidenceClose = document.querySelector("#migrationEvidenceClose");
const {
  primaryLocationKeys,
  boundaryLocationKeys,
  secondaryLocationKeys,
  pressureDirection,
  filterSymbolsByPressure,
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
  migrationEvidenceSelection,
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
  migrationBarMagnitudePercent,
  buildMigrationMomentumReport,
  migrationTrajectoryDomain,
  migrationTrajectory,
  migrationDirectionCounts,
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
    higherButton: document.querySelector("#distributionDeepDiscountHigherButton"),
    higherCount: document.querySelector("#distributionDeepDiscountHigherCount"),
    lower: document.querySelector("#distributionDeepDiscountLower"),
    lowerButton: document.querySelector("#distributionDeepDiscountLowerButton"),
    lowerCount: document.querySelector("#distributionDeepDiscountLowerCount"),
    samples: document.querySelector("#distributionDeepDiscountSamples"),
  },
  shallow_discount: {
    count: document.querySelector("#distributionShallowDiscountCount"),
    percentage: document.querySelector("#distributionShallowDiscountPercentage"),
    history: document.querySelector("#distributionShallowDiscountHistory"),
    historyEmpty: document.querySelector("#distributionShallowDiscountHistoryEmpty"),
    higher: document.querySelector("#distributionShallowDiscountHigher"),
    higherButton: document.querySelector("#distributionShallowDiscountHigherButton"),
    higherCount: document.querySelector("#distributionShallowDiscountHigherCount"),
    lower: document.querySelector("#distributionShallowDiscountLower"),
    lowerButton: document.querySelector("#distributionShallowDiscountLowerButton"),
    lowerCount: document.querySelector("#distributionShallowDiscountLowerCount"),
    samples: document.querySelector("#distributionShallowDiscountSamples"),
  },
  shallow_premium: {
    count: document.querySelector("#distributionShallowPremiumCount"),
    percentage: document.querySelector("#distributionShallowPremiumPercentage"),
    history: document.querySelector("#distributionShallowPremiumHistory"),
    historyEmpty: document.querySelector("#distributionShallowPremiumHistoryEmpty"),
    higher: document.querySelector("#distributionShallowPremiumHigher"),
    higherButton: document.querySelector("#distributionShallowPremiumHigherButton"),
    higherCount: document.querySelector("#distributionShallowPremiumHigherCount"),
    lower: document.querySelector("#distributionShallowPremiumLower"),
    lowerButton: document.querySelector("#distributionShallowPremiumLowerButton"),
    lowerCount: document.querySelector("#distributionShallowPremiumLowerCount"),
    samples: document.querySelector("#distributionShallowPremiumSamples"),
  },
  deep_premium: {
    count: document.querySelector("#distributionDeepPremiumCount"),
    percentage: document.querySelector("#distributionDeepPremiumPercentage"),
    history: document.querySelector("#distributionDeepPremiumHistory"),
    historyEmpty: document.querySelector("#distributionDeepPremiumHistoryEmpty"),
    higher: document.querySelector("#distributionDeepPremiumHigher"),
    higherButton: document.querySelector("#distributionDeepPremiumHigherButton"),
    higherCount: document.querySelector("#distributionDeepPremiumHigherCount"),
    lower: document.querySelector("#distributionDeepPremiumLower"),
    lowerButton: document.querySelector("#distributionDeepPremiumLowerButton"),
    lowerCount: document.querySelector("#distributionDeepPremiumLowerCount"),
    samples: document.querySelector("#distributionDeepPremiumSamples"),
  },
};
const distributionTotals = {
  discount: document.querySelector("#distributionDiscountTotal"),
  atEqm: document.querySelector("#distributionAtEqmTotal"),
  premium: document.querySelector("#distributionPremiumTotal"),
  unavailable: document.querySelector("#distributionUnavailableTotal"),
};
const groupCurrentFields = {
  count: document.querySelector("#selectedGroupCount"),
  btd: document.querySelector("#groupBtdCount"),
  str: document.querySelector("#groupStrCount"),
  active: document.querySelector("#groupActiveMrzCount"),
  locations: {
    deep_discount: document.querySelector("#groupDeepDiscountCount"),
    shallow_discount: document.querySelector("#groupShallowDiscountCount"),
    at_eqm: document.querySelector("#groupAtEqmCount"),
    shallow_premium: document.querySelector("#groupShallowPremiumCount"),
    deep_premium: document.querySelector("#groupDeepPremiumCount"),
  },
};

let overviewSymbols = [];
let minimumClusterObservations = null;
let locationMigrationTendency = {};
let universePressure = null;
let heatmapPressureFilter = "all";
let groupTrackingState = createGroupTrackingState();
let savedGroups = [];
let activeSavedGroup = null;
let activePeerPressure = null;
let migrationHistoryGroupId = null;
let activeMigrationPath = null;
let migrationEvidenceReturnFocus = null;

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
  at_eqm: "At EQM",
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

function pressureArrow(direction) {
  if (direction === "higher") return "↑";
  if (direction === "lower") return "↓";
  return "↔";
}

function createLocationGroup(
  key,
  symbols,
  minimumClusterObservations,
  secondary = false,
  totalCount = symbols.length,
) {
  const group = document.createElement("section");
  group.className = secondary ? "location-group secondary" : "location-group";

  const heading = document.createElement("h3");
  const locationLabel = key === "unavailable" ? "Unavailable" : locationLabels[key];
  heading.textContent = heatmapPressureFilter === "all"
    ? locationLabel
    : `${locationLabel} · ${symbols.length} ${pressureDirectionLabels[heatmapPressureFilter]} / ${totalCount} total`;
  group.append(heading);

  const symbolList = document.createElement("div");
  symbolList.className = "symbol-chips";
  if (symbols.length === 0) {
    const empty = document.createElement("span");
    empty.className = "group-empty";
    empty.textContent = heatmapPressureFilter === "all"
      ? "No symbols"
      : `No ${pressureDirectionLabels[heatmapPressureFilter]} symbols`;
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
      const chipLocationLabel = key === "unavailable" ? "Unavailable" : formatLocation(key);
      const chipLabel = accessibleChipLabel(symbolState, chipLocationLabel);
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
      const direction = pressureDirection(symbolState);
      const pressure = document.createElement("span");
      pressure.className = `symbol-pressure ${direction}`;
      pressure.setAttribute("aria-hidden", "true");
      pressure.textContent = pressureArrow(direction);
      button.append(pressure);
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
    configureMigrationDirection(fieldsForLocation, key, "HIGHER", migration);
    configureMigrationDirection(fieldsForLocation, key, "LOWER", migration);
    fieldsForLocation.samples.textContent = migration.sampleLabel;
  });
  const atEqm = distribution.buckets.at_eqm;
  distributionAtEqmCount.textContent = String(atEqm.count);
  distributionTotals.atEqm.textContent = (
    `${atEqm.count} · ${formatLocationPercentage(atEqm.percentage)}`
  );
  distributionTotals.discount.textContent = (
    `${distribution.discountTotal.count} · ${formatLocationPercentage(distribution.discountTotal.percentage)}`
  );
  distributionTotals.premium.textContent = (
    `${distribution.premiumTotal.count} · ${formatLocationPercentage(distribution.premiumTotal.percentage)}`
  );
  distributionTotals.unavailable.textContent = String(distribution.unavailableCount);
  locationDistribution.setAttribute(
    "aria-label",
    `Current location distribution and historical MRZ migration tendency for ${distribution.classifiedTotal} classified symbols; ${distribution.unavailableCount} unavailable of ${distribution.monitoredTotal} monitored`,
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
  const showCurrent = tabName !== "pressure";
  currentStateTab.setAttribute("aria-selected", String(showCurrent));
  peerPressureTab.setAttribute("aria-selected", String(!showCurrent));
  currentStatePanel.hidden = !showCurrent;
  peerPressurePanel.hidden = showCurrent;
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
  [...primaryLocationKeys, ...boundaryLocationKeys].forEach((key) => {
    groupCurrentFields.locations[key].textContent = String(state.location[key] ?? 0);
  });
  groupCurrentFields.active.textContent = `${state.active_mrz.count} / ${state.active_mrz.total}`;
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

const pressureDirectionLabels = {
  higher: "Higher",
  lower: "Lower",
  neutral: "Neutral",
};

function pressureMemberItem(member) {
  const item = document.createElement("li");
  item.className = `peer-pressure-member ${member.direction}`;
  const header = document.createElement("div");
  header.className = "peer-pressure-member-header";
  const symbol = document.createElement("button");
  symbol.type = "button";
  symbol.textContent = member.symbol;
  symbol.setAttribute("aria-label", `Open ${member.symbol} in MRZ Monitor`);
  symbol.addEventListener("click", () => selectGroupMember(member.symbol).catch(showError));
  const status = document.createElement("span");
  status.className = "peer-pressure-member-status";
  status.textContent = member.active_mrz.status === "active"
    ? `${member.direction_label} · Active MRZ`
    : `${member.direction_label} · No active MRZ`;
  header.append(symbol, status);

  const location = document.createElement("p");
  location.className = "peer-pressure-member-location";
  location.textContent = member.active_mrz.status === "active"
    ? `Current ${member.current_location_label} · MRZ ${member.active_mrz.location_label}`
    : `Current ${member.current_location_label} · MRZ unestablished`;

  const evidence = document.createElement("p");
  evidence.className = "peer-pressure-member-evidence";
  if (member.active_mrz.status === "active") {
    const sequence = (member.evidence.recent_sequence || [])
      .map((entry) => (entry.direction === "UP" ? "↑" : "↓"))
      .join(" ") || "—";
    const since = member.evidence.current_pressure_since
      ? `Since ${formatPathTimestamp(member.evidence.current_pressure_since)}`
      : "Regime not established";
    const latest = member.evidence.latest_pressure_observed_at
      ? `Latest pressure ${formatPathTimestamp(member.evidence.latest_pressure_observed_at)}`
      : "No qualifying pressure observations";
    evidence.textContent = (
      `Recent ${sequence} · ${since} · ${latest} · `
      + `Cumulative since activation ↑ ${member.evidence.higher_observation_count} · `
      + `↓ ${member.evidence.lower_observation_count}`
    );
  } else {
    evidence.textContent = member.evidence.reason;
  }
  item.append(header, location, evidence);
  return item;
}

function renderPeerPressureDrilldown(direction) {
  if (!activePeerPressure) return;
  const members = activePeerPressure.categories[direction] || [];
  peerPressureButtons.forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.pressureDirection === direction));
  });
  peerPressureDrilldown.hidden = false;
  peerPressureDrilldownTitle.textContent = `${pressureDirectionLabels[direction]} · ${members.length}`;
  peerPressureDrilldownSummary.textContent = (
    `${members.length} of ${activePeerPressure.member_count} cohort members`
  );
  if (members.length === 0) {
    const empty = document.createElement("li");
    empty.className = "migration-path-all-empty";
    empty.textContent = `No members are currently classified ${pressureDirectionLabels[direction]}.`;
    peerPressureMembers.replaceChildren(empty);
    return;
  }
  peerPressureMembers.replaceChildren(...members.map(pressureMemberItem));
}

function renderPeerPressure(payload) {
  activePeerPressure = payload;
  peerPressureHeadline.textContent = payload.headline.label;
  peerPressureSummary.textContent = (
    `${payload.counts.higher} Higher · ${payload.counts.lower} Lower · `
    + `${payload.counts.neutral} Neutral`
  );
  peerPressureParticipation.textContent = (
    `${payload.participation.count} / ${payload.participation.total}`
  );
  peerPressureButtons.forEach((button) => {
    const direction = button.dataset.pressureDirection;
    const count = payload.counts[direction];
    peerPressureCounts[direction].textContent = String(count);
    button.setAttribute("aria-pressed", "false");
    button.setAttribute(
      "aria-label",
      `${pressureDirectionLabels[direction]} Peer Pressure, ${count} of ${payload.member_count} members`,
    );
  });
  peerPressureDrilldown.hidden = true;
  peerPressureMembers.replaceChildren();
}

function migrationDirectionFromMove(value) {
  return Number(value) > 0 ? "higher" : "lower";
}

function migrationArrow(direction) {
  if (direction === "higher") return "↑";
  if (direction === "lower") return "↓";
  return "↔";
}

function formatSignedMigrationValue(value, maximumFractionDigits = 2) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "Unavailable";
  const formatted = new Intl.NumberFormat("en-US", {
    maximumFractionDigits,
    minimumFractionDigits: Math.min(2, maximumFractionDigits),
    signDisplay: "always",
  }).format(numeric);
  return formatted.replace("-0.00", "+0.00");
}

function resetMigrationMomentum(message = "Load Peer Pressure to inspect authoritative migration.") {
  groupMigrationState.textContent = "—";
  recentMigrationDirection.textContent = "—";
  migrationParticipation.textContent = "0 / 0 symbols";
  pressureMigrationAlignment.textContent = "—";
  migrationMomentumMagnitude.textContent = "—";
  migrationMomentumDetail.hidden = true;
  migrationMomentumDetail.replaceChildren();
  symbolMigrationStates.replaceChildren();
  const empty = document.createElement("p");
  empty.className = "migration-momentum-empty";
  empty.textContent = message;
  migrationMomentumHistogram.replaceChildren(empty);
}

function migrationMomentumDetailPresentation(event) {
  const direction = migrationDirectionFromMove(event.normalizedMove);
  return {
    heading: `${event.symbol} · ${direction === "higher" ? "Upward" : "Downward"} authoritative migration`,
    timestamp: formatPathTimestamp(event.occurredAt),
    fields: [
      ["Normalized move", `${formatSignedMigrationValue(event.normalizedMove)} previous-MRZ widths`],
      ["Midpoint Δ", formatSignedMigrationValue(event.rawMidpointDelta, 8)],
      ["Previous midpoint", formatPrice(event.previous.midpoint)],
      ["Current midpoint", formatPrice(event.current.midpoint)],
      ["Previous MRZ", formatPathRange(event.previous)],
      ["Current MRZ", formatPathRange(event.current)],
      ["Route", event.routeOwner],
      ["Location", event.locationLabel],
    ],
  };
}

function renderMigrationMomentumDetail(event) {
  const presentation = migrationMomentumDetailPresentation(event);
  const header = document.createElement("header");
  const heading = document.createElement("strong");
  heading.textContent = presentation.heading;
  const timestamp = document.createElement("span");
  timestamp.textContent = presentation.timestamp;
  header.append(heading, timestamp);
  const fields = document.createElement("dl");
  presentation.fields.forEach(([label, value]) => {
    const field = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = value;
    field.append(term, description);
    fields.append(field);
  });
  migrationMomentumDetail.replaceChildren(header, fields);
  migrationMomentumDetail.hidden = false;
}

function revealMigrationEvidence(eventKey) {
  migrationHistoryDisclosure.open = true;
  if (activeMigrationPath) renderMigrationPath(activeMigrationPath);
  globalThis.requestAnimationFrame(() => {
    const node = [...migrationPathScroller.querySelectorAll("[data-event-key]")]
      .find((candidate) => candidate.dataset.eventKey === eventKey);
    if (!node) return;
    node.focus({ preventScroll: true });
    node.click();
    node.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
  });
}

function renderMigrationHistogram(report) {
  if (report.events.length === 0) {
    const empty = document.createElement("p");
    empty.className = "migration-momentum-empty";
    empty.textContent = "No valid authoritative migration events are available for this group.";
    migrationMomentumHistogram.replaceChildren(empty);
    migrationMomentumDetail.hidden = true;
    return;
  }

  const bars = document.createElement("div");
  bars.className = "migration-momentum-bars";
  const eventButtons = [];
  const showEvent = (event, button) => {
    eventButtons.forEach((candidate) => {
      const selected = candidate === button;
      candidate.classList.toggle("inspected", selected);
      candidate.setAttribute("aria-pressed", String(selected));
    });
    renderMigrationMomentumDetail(event);
  };
  report.events.forEach((event) => {
    const direction = migrationDirectionFromMove(event.normalizedMove);
    const magnitude = migrationBarMagnitudePercent(event.normalizedMove, report.barDomain);
    const button = document.createElement("button");
    button.type = "button";
    button.className = `migration-momentum-event ${direction}`;
    button.dataset.eventKey = event.eventKey;
    button.style.setProperty("--migration-bar-height", `${(magnitude || 0) * 0.39}%`);
    button.setAttribute("aria-pressed", "false");
    button.setAttribute(
      "aria-label",
      `${event.symbol}, ${direction === "higher" ? "upward" : "downward"} authoritative migration, `
      + `${formatSignedMigrationValue(event.normalizedMove)} previous-MRZ widths, `
      + `${formatPathTimestamp(event.occurredAt)}`,
    );
    const bar = document.createElement("span");
    bar.className = "migration-momentum-bar";
    bar.setAttribute("aria-hidden", "true");
    const symbol = document.createElement("span");
    symbol.className = "migration-momentum-event-symbol";
    symbol.textContent = event.symbol.replace(/USDT$/, "");
    symbol.setAttribute("aria-hidden", "true");
    button.append(bar, symbol);
    button.addEventListener("mouseenter", () => showEvent(event, button));
    button.addEventListener("focus", () => showEvent(event, button));
    button.addEventListener("click", () => {
      showEvent(event, button);
      revealMigrationEvidence(event.eventKey);
    });
    eventButtons.push(button);
    bars.append(button);
  });
  migrationMomentumHistogram.replaceChildren(bars);
}

function renderSymbolMigrationStates(report) {
  const items = report.symbols.map((symbolState) => {
    const item = document.createElement("li");
    item.className = `symbol-migration-state ${symbolState.direction}`;
    const button = document.createElement("button");
    button.type = "button";
    const symbol = document.createElement("strong");
    symbol.textContent = symbolState.symbol;
    const sequence = document.createElement("span");
    sequence.className = "symbol-migration-sequence";
    sequence.textContent = symbolState.recentEvents.length > 0
      ? symbolState.recentEvents.map(({ normalizedMove, available }) => (
        available ? migrationArrow(migrationDirectionFromMove(normalizedMove)) : "—"
      )).join(" ")
      : "—";
    const label = document.createElement("span");
    label.className = "symbol-migration-state-label";
    label.textContent = symbolState.label;
    button.append(symbol, sequence, label);
    const latestEvent = [...symbolState.recentEvents].reverse().find(({ available }) => available);
    button.disabled = !latestEvent;
    button.setAttribute(
      "aria-label",
      latestEvent
        ? `${symbolState.symbol}, ${symbolState.label}. Open latest migration evidence.`
        : `${symbolState.symbol}, ${symbolState.label}. No migration evidence available.`,
    );
    if (latestEvent) {
      button.addEventListener("click", () => revealMigrationEvidence(latestEvent.eventKey));
    }
    item.append(button);
    return item;
  });
  symbolMigrationStates.replaceChildren(...items);
}

function renderMigrationMomentum(pathPayload, peerPressure) {
  const report = buildMigrationMomentumReport(pathPayload, peerPressure);
  groupMigrationState.textContent = report.group.label;
  groupMigrationState.dataset.migrationDirection = report.group.direction;
  recentMigrationDirection.textContent = (
    `↑ ${report.recentDirection.higher} · ↓ ${report.recentDirection.lower}`
  );
  migrationParticipation.textContent = (
    `${report.group.participation.count} / ${report.group.participation.total} symbols`
  );
  pressureMigrationAlignment.textContent = report.alignmentLabel;
  pressureMigrationAlignment.dataset.alignment = report.alignment;
  migrationMomentumMagnitude.textContent = report.magnitude === null
    ? "—"
    : `${report.magnitude.toFixed(2)} MRZ widths`;
  renderMigrationHistogram(report);
  renderSymbolMigrationStates(report);
}

function universePressureBySymbol(payload) {
  return new Map(
    Object.values(payload?.categories || {})
      .flat()
      .map((member) => [member.symbol, member]),
  );
}

function pressureMapCell(location, direction, count, total) {
  const button = document.createElement("button");
  button.type = "button";
  button.dataset.pressureMapLocation = location;
  button.dataset.pressureMapDirection = direction;
  button.setAttribute("aria-pressed", "false");
  button.setAttribute(
    "aria-label",
    `${formatLocation(location)}, ${pressureDirectionLabels[direction]} pressure, ${count} of ${total} symbols`,
  );
  const label = document.createElement("span");
  label.textContent = `${pressureArrow(direction)} ${pressureDirectionLabels[direction]}`;
  const value = document.createElement("strong");
  value.textContent = String(count);
  button.append(label, value);
  button.addEventListener("click", () => selectPressureMapCell(location, direction));
  return button;
}

function renderPressureMap(payload) {
  const rows = payload.pressure_map?.locations || {};
  pressureMap.replaceChildren(...[...primaryLocationKeys, ...boundaryLocationKeys].map((location) => {
    const row = rows[location] || {
      counts: { higher: 0, lower: 0, neutral: 0 },
      participation: { count: 0, total: 0 },
    };
    const card = document.createElement("article");
    card.className = "pressure-map-card";
    const header = document.createElement("header");
    const heading = document.createElement("h3");
    heading.textContent = formatLocation(location);
    const total = document.createElement("span");
    total.textContent = String(row.participation.total);
    header.append(heading, total);
    const cells = document.createElement("div");
    cells.className = "pressure-map-cells";
    ["higher", "neutral", "lower"].forEach((direction) => {
      cells.append(pressureMapCell(
        location,
        direction,
        row.counts[direction],
        row.participation.total,
      ));
    });
    const participation = document.createElement("p");
    participation.textContent = (
      `Participation ${row.participation.count} / ${row.participation.total}`
    );
    card.append(header, cells, participation);
    return card;
  }));
}

function renderPressureMapDrilldown(location, direction) {
  if (!universePressure) return;
  const members = (universePressure.categories[direction] || []).filter(
    (member) => member.current_location === location,
  );
  document.querySelectorAll("[data-pressure-map-direction]").forEach((button) => {
    button.setAttribute("aria-pressed", String(
      button.dataset.pressureMapLocation === location
      && button.dataset.pressureMapDirection === direction
    ));
  });
  pressureMapDrilldown.hidden = false;
  pressureMapDrilldownTitle.textContent = (
    `${formatLocation(location)} × ${pressureDirectionLabels[direction]} · ${members.length}`
  );
  pressureMapDrilldownSummary.textContent = (
    `${members.length} exact contributor${members.length === 1 ? "" : "s"}`
  );
  if (members.length === 0) {
    const empty = document.createElement("li");
    empty.className = "migration-path-all-empty";
    empty.textContent = "No symbols currently match this location and pressure direction.";
    pressureMapMembers.replaceChildren(empty);
    return;
  }
  pressureMapMembers.replaceChildren(...members.map(pressureMemberItem));
}

function setHeatmapPressureFilter(direction, scrollToHeatmap = false) {
  const normalized = ["higher", "lower", "neutral"].includes(direction)
    ? direction
    : "all";
  heatmapPressureFilter = normalized;
  heatmapPressureButtons.forEach((button) => {
    button.setAttribute(
      "aria-pressed",
      String(button.dataset.heatmapPressureFilter === normalized),
    );
  });
  universePressureButtons.forEach((button) => {
    button.setAttribute(
      "aria-pressed",
      String(button.dataset.universePressureDirection === normalized),
    );
  });
  renderMonitorOverview();
  if (scrollToHeatmap) {
    document.querySelector(".heatmap-panel")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }
}

function selectPressureMapCell(location, direction) {
  setHeatmapPressureFilter(direction);
  renderPressureMapDrilldown(location, direction);
}

function renderUniversePressure(payload) {
  universePressure = payload;
  universePressureHeadline.textContent = payload.headline.label;
  universePressureParticipation.textContent = (
    `${payload.participation.count} / ${payload.participation.total}`
  );
  universePressureButtons.forEach((button) => {
    const direction = button.dataset.universePressureDirection;
    const count = payload.counts[direction];
    universePressureCounts[direction].textContent = String(count);
    button.setAttribute(
      "aria-label",
      `${pressureDirectionLabels[direction]} pressure, ${count} of ${payload.member_count} classified symbols`,
    );
  });
  renderPressureMap(payload);
  pressureMapDrilldown.hidden = true;
  pressureMapMembers.replaceChildren();
}

function formatPathTimestamp(value) {
  const formatted = formatOperatorTimestampUtcMinus4(value);
  return formatted || "Time unavailable";
}

function formatPathTick(value) {
  const formatted = formatOperatorTimestampUtcMinus4(value);
  return formatted ? formatted.split(" · ")[0] : "—";
}

function formatPathRange(state) {
  if (state?.lower == null || state?.upper == null) return "Unavailable";
  return `${formatPrice(state.lower)} – ${formatPrice(state.upper)}`;
}

function migrationStateDetailPresentation(symbol, state, previousState, eqmPair) {
  const isMigration = state.event_type === "MRZ_MIGRATED";
  const fields = [
    ["Event", isMigration ? "Authoritative migration" : "Initial activation"],
    ["Route", state.route_owner],
  ];
  if (isMigration && state.direction) {
    fields.push(["Migration", state.direction === "higher" ? "Higher ↑" : "Lower ↓"]);
  }
  if (previousState) {
    fields.push(["Previous MRZ", formatPathRange(previousState)]);
  }
  fields.push(["Current MRZ", formatPathRange(state)]);
  if (eqmPair) {
    fields.push(
      ["Previous midpoint", formatPrice(eqmPair.previousMidpoint)],
      ["Current midpoint", formatPrice(eqmPair.currentMidpoint)],
      ["MRZ EQM", formatPrice(eqmPair.eqm)],
    );
  } else {
    fields.push(["Current midpoint", formatPrice(state.midpoint)]);
  }
  return {
    heading: `${symbol} · ${state.location_label}`,
    timestamp: formatPathTimestamp(state.occurred_at),
    fields,
  };
}

function migrationStateAccessibleLabel(symbol, state, previousState, eqmPair) {
  const presentation = migrationStateDetailPresentation(
    symbol,
    state,
    previousState,
    eqmPair,
  );
  return [
    presentation.heading,
    presentation.timestamp,
    ...presentation.fields.map(([label, value]) => `${label}: ${value}`),
  ].join(" · ");
}

function renderMigrationStateDetail(container, symbol, state, previousState, eqmPair) {
  const presentation = migrationStateDetailPresentation(
    symbol,
    state,
    previousState,
    eqmPair,
  );
  const header = document.createElement("div");
  header.className = "migration-trajectory-detail-header";
  const heading = document.createElement("strong");
  heading.textContent = presentation.heading;
  const timestamp = document.createElement("span");
  timestamp.textContent = presentation.timestamp;
  header.append(heading, timestamp);
  const facts = document.createElement("dl");
  facts.className = "migration-trajectory-detail-fields";
  presentation.fields.forEach(([label, value]) => {
    const field = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = value;
    field.append(term, description);
    facts.append(field);
  });
  container.replaceChildren(header, facts);
  container.hidden = false;
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
  timeline.className = "migration-trajectory-chart";
  const axis = document.createElement("div");
  axis.className = "migration-trajectory-axis";
  axis.append(document.createElement("span"));
  const ticks = document.createElement("div");
  ticks.className = "migration-trajectory-ticks";
  timelineTicks(payload.timeline.started_at, payload.timeline.ended_at).forEach((value) => {
    const tick = document.createElement("span");
    tick.className = "migration-trajectory-tick";
    tick.style.left = `${timelinePosition(value, payload.timeline.started_at, payload.timeline.ended_at)}%`;
    tick.textContent = formatPathTick(value);
    tick.setAttribute("aria-label", formatPathTimestamp(value));
    ticks.append(tick);
  });
  axis.append(ticks);
  timeline.append(axis);
  const trajectoryDomain = migrationTrajectoryDomain(payload.paths);

  payload.paths.forEach((path, pathIndex) => {
    const row = document.createElement("div");
    row.className = "migration-trajectory-row";
    const label = document.createElement("div");
    label.className = "migration-trajectory-row-label";
    const symbol = document.createElement("strong");
    symbol.textContent = path.symbol;
    label.append(symbol);
    const counts = migrationDirectionCounts(path.states);
    if (counts.higher + counts.lower > 0) {
      const summary = document.createElement("span");
      summary.textContent = `↑ ${counts.higher} · ↓ ${counts.lower}`;
      summary.setAttribute(
        "aria-label",
        `${counts.higher} higher and ${counts.lower} lower authoritative migrations`,
      );
      label.append(summary);
    }
    const track = document.createElement("div");
    track.className = "migration-trajectory-track";
    if (path.states.length === 0) {
      const empty = document.createElement("span");
      empty.className = "migration-path-empty";
      empty.textContent = "No authoritative MRZ history";
      track.append(empty);
    } else {
      const baseline = document.createElement("span");
      baseline.className = "migration-trajectory-baseline";
      baseline.setAttribute("aria-hidden", "true");
      track.append(baseline);
      const points = migrationTrajectory(
        path.states,
        payload.timeline.started_at,
        payload.timeline.ended_at,
        trajectoryDomain,
      );
      const plottablePoints = points.filter(({ y }) => y !== null);
      if (plottablePoints.length > 1) {
        const svgNamespace = "http://www.w3.org/2000/svg";
        const connector = document.createElementNS(svgNamespace, "svg");
        connector.classList.add("migration-trajectory-connector");
        connector.setAttribute("viewBox", "0 0 1000 100");
        connector.setAttribute("preserveAspectRatio", "none");
        connector.setAttribute("aria-hidden", "true");
        const line = document.createElementNS(svgNamespace, "polyline");
        line.setAttribute(
          "points",
          plottablePoints.map(({ x, y }) => `${x * 10},${y}`).join(" "),
        );
        connector.append(line);
        track.append(connector);
      }
      const detail = document.createElement("section");
      detail.className = "migration-trajectory-detail";
      detail.id = `migrationTrajectoryDetail${pathIndex}`;
      detail.hidden = true;
      detail.setAttribute("aria-live", "polite");
      const nodes = [];
      const showDetail = (index) => {
        const state = path.states[index];
        const eqmPair = authoritativeMrzEqmPair(path.states, index);
        nodes.forEach(({ element, stateIndex }) => {
          const inspected = stateIndex === index;
          element.classList.toggle("inspected", inspected);
          element.setAttribute("aria-pressed", String(inspected));
        });
        renderMigrationStateDetail(
          detail,
          path.symbol,
          state,
          path.states[index - 1] || null,
          eqmPair,
        );
      };
      points.forEach((point, index) => {
        if (point.y === null) return;
        const { state } = point;
        const node = document.createElement("button");
        node.type = "button";
        const eqmPair = authoritativeMrzEqmPair(path.states, index);
        node.className = [
          "migration-trajectory-state",
          point.direction,
          point.initial ? "initial" : "",
          point.latest ? "current" : "",
        ].filter(Boolean).join(" ");
        node.style.left = `${point.x}%`;
        node.style.top = `${point.y}%`;
        node.textContent = state.location_code;
        node.setAttribute("aria-label", migrationStateAccessibleLabel(
          path.symbol,
          state,
          path.states[index - 1] || null,
          eqmPair,
        ));
        node.setAttribute("aria-controls", detail.id);
        node.setAttribute("aria-pressed", "false");
        node.dataset.eventKey = state.event_key;
        if (point.direction) {
          const direction = document.createElement("span");
          direction.className = "migration-trajectory-direction";
          direction.setAttribute("aria-hidden", "true");
          direction.textContent = point.direction === "higher" ? "↑" : "↓";
          node.append(direction);
        }
        node.addEventListener("mouseenter", () => showDetail(index));
        node.addEventListener("focus", () => showDetail(index));
        node.addEventListener("click", () => showDetail(index));
        nodes.push({ element: node, stateIndex: index });
        track.append(node);
      });
      row.append(detail);
    }
    row.prepend(label, track);
    timeline.append(row);
  });
  migrationPathScroller.replaceChildren(timeline);
}

function renderLocationHeatmap(
  symbols,
  minimumObservations,
  groups,
  totalSymbols = symbols,
  totalGroups = groups,
) {
  if (totalSymbols.length === 0) {
    locationHeatmap.hidden = true;
    heatmapEmpty.hidden = false;
    heatmapEmpty.textContent = "No symbols yet";
    return;
  }

  primaryLocationGroups.replaceChildren(
    ...primaryLocationKeys.map((key) => (
      createLocationGroup(
        key,
        groups[key],
        minimumObservations,
        false,
        totalGroups[key].length,
      )
    )),
  );
  const populatedSecondaryKeys = [...boundaryLocationKeys, ...secondaryLocationKeys].filter(
    (key) => totalGroups[key].length > 0,
  );
  secondaryLocationGroups.replaceChildren(
    ...populatedSecondaryKeys.map((key) => (
      createLocationGroup(
        key,
        groups[key],
        minimumObservations,
        true,
        totalGroups[key].length,
      )
    )),
  );
  secondaryLocationGroups.hidden = populatedSecondaryKeys.length === 0;
  heatmapEmpty.hidden = true;
  locationHeatmap.hidden = false;
}

function definitionRow(term, value) {
  const row = document.createElement("div");
  const name = document.createElement("dt");
  const content = document.createElement("dd");
  name.textContent = term;
  content.textContent = value == null || value === "" ? "—" : String(value);
  row.append(name, content);
  return row;
}

function authorityProvenance(label, authority = {}) {
  const section = document.createElement("section");
  section.className = "migration-provenance-section";
  const heading = document.createElement("p");
  heading.className = "migration-provenance-label";
  heading.textContent = label;
  const facts = document.createElement("dl");
  const range = `${formatPrice(authority.lower)}–${formatPrice(authority.upper)}`;
  facts.append(
    definitionRow("Location", formatLocation(authority.structural_location)),
    definitionRow("Route", authority.route_owner),
    definitionRow("MRZ", range),
    definitionRow("Midpoint", formatPrice(authority.midpoint)),
    definitionRow("Activated", formatOperatorTimestampUtcMinus4(authority.activated_at)),
    definitionRow("Source", String(authority.activation_source || "").replaceAll("_", " ")),
    definitionRow("Authority event", authority.authority_event_key),
  );
  section.append(heading, facts);
  return section;
}

function signedMetric(value, suffix = "") {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "—";
  const formatted = suffix
    ? new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 }).format(Math.abs(numeric))
    : formatPrice(Math.abs(numeric));
  const sign = numeric > 0 ? "+" : numeric < 0 ? "−" : "";
  return `${sign}${formatted}${suffix}`;
}

function migrationEvidenceRecord(record) {
  const details = document.createElement("details");
  details.className = "migration-evidence-record";
  const summary = document.createElement("summary");
  const heading = document.createElement("div");
  heading.className = "migration-evidence-record-heading";
  const symbol = document.createElement("strong");
  symbol.textContent = record.symbol;
  const inspect = document.createElement("span");
  inspect.textContent = "Inspect provenance";
  heading.append(symbol, inspect);
  const ranges = document.createElement("div");
  ranges.className = "migration-evidence-ranges";
  const fromRange = document.createElement("span");
  fromRange.textContent = `${formatPrice(record.source?.lower)}–${formatPrice(record.source?.upper)}`;
  const arrow = document.createElement("span");
  arrow.textContent = record.direction === "LOWER" ? "↓" : "↑";
  const toRange = document.createElement("span");
  toRange.textContent = `${formatPrice(record.destination?.lower)}–${formatPrice(record.destination?.upper)}`;
  ranges.append(fromRange, arrow, toRange);
  const timestamp = document.createElement("time");
  timestamp.className = "migration-evidence-time";
  timestamp.dateTime = record.migrated_at;
  timestamp.textContent = formatOperatorTimestampUtcMinus4(record.migrated_at) || "—";
  summary.append(heading, ranges, timestamp);

  const provenance = document.createElement("div");
  provenance.className = "migration-provenance";
  const authorities = document.createElement("div");
  authorities.className = "migration-provenance-grid";
  authorities.append(
    authorityProvenance("FROM", record.source),
    authorityProvenance("TO", record.destination),
  );
  const metadata = document.createElement("dl");
  metadata.className = "migration-event-metadata";
  metadata.append(
    definitionRow("Direction", record.direction),
    definitionRow("Migrated", formatOperatorTimestampUtcMinus4(record.migrated_at)),
    definitionRow("Midpoint delta", signedMetric(record.midpoint_delta)),
    definitionRow("Midpoint delta %", signedMetric(record.midpoint_delta_pct, "%")),
    definitionRow("Evidence", `${record.confirming_observation_count} confirming observations`),
    definitionRow("Migration event", record.migration_event_key),
    definitionRow("Trigger observation", record.trigger_event_id),
  );
  provenance.append(authorities, metadata);
  details.append(summary, provenance);
  return details;
}

function openMigrationEvidence(locationKey, direction, trigger) {
  const selection = migrationEvidenceSelection(
    locationMigrationTendency?.[locationKey],
    direction,
  );
  if (!selection) return;
  const arrow = selection.direction === "LOWER" ? "↓" : "↑";
  const directionLabel = selection.direction === "LOWER" ? "Lower" : "Higher";
  migrationEvidenceTitle.textContent = formatLocation(locationKey);
  migrationEvidenceSummary.textContent = (
    `${arrow} ${directionLabel} · ${selection.count} of ${selection.total} migrations · ${selection.percentageLabel}`
  );
  migrationEvidenceList.replaceChildren(
    ...selection.records.map(migrationEvidenceRecord),
  );
  migrationEvidenceReturnFocus = trigger;
  migrationEvidenceDialog.showModal();
}

function configureMigrationDirection(fieldsForLocation, locationKey, direction, migration) {
  const directionKey = direction.toLowerCase();
  const button = fieldsForLocation[`${directionKey}Button`];
  const value = fieldsForLocation[directionKey];
  const count = fieldsForLocation[`${directionKey}Count`];
  const interactive = migration[`${directionKey}Interactive`];
  value.textContent = migration[`${directionKey}PercentageLabel`];
  count.textContent = migration[`${directionKey}CountLabel`];
  button.disabled = !interactive;
  button.onclick = interactive
    ? () => openMigrationEvidence(locationKey, direction, button)
    : null;
  if (interactive) {
    const accessiblePercentage = migration[`${directionKey}PercentageLabel`]
      .replace("%", " percent");
    button.setAttribute(
      "aria-label",
      `${formatLocation(locationKey)}, ${directionKey} migration evidence, ${accessiblePercentage}, ${migration[`${directionKey}CountLabel`]} migration${migration[`${directionKey}Count`] === 1 ? "" : "s"}`,
    );
  } else {
    button.removeAttribute("aria-label");
  }
}

function renderMonitorOverview() {
  const allGroups = groupSymbolsByLocation(overviewSymbols, minimumClusterObservations);
  renderLocationDistribution(allGroups, locationMigrationTendency);
  const trackedSymbols = visibleSymbolsForGroupTracking(overviewSymbols, groupTrackingState);
  const trackedGroups = trackedSymbols === overviewSymbols
    ? allGroups
    : groupSymbolsByLocation(trackedSymbols, minimumClusterObservations);
  const visibleSymbols = filterSymbolsByPressure(trackedSymbols, heatmapPressureFilter);
  const visibleGroups = visibleSymbols === trackedSymbols
    ? trackedGroups
    : groupSymbolsByLocation(visibleSymbols, minimumClusterObservations);
  renderLocationHeatmap(
    visibleSymbols,
    minimumClusterObservations,
    visibleGroups,
    trackedSymbols,
    trackedGroups,
  );
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
  const pressureBySymbol = universePressureBySymbol(payload.pressure);
  overviewSymbols = payload.symbols.map((symbolState) => ({
    ...symbolState,
    pressure_direction: pressureBySymbol.get(symbolState.symbol)?.direction || "neutral",
  }));
  minimumClusterObservations = payload.minimum_cluster_observations;
  locationMigrationTendency = payload.location_migration_tendency || {};
  renderUniversePressure(payload.pressure);
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
  activePeerPressure = null;
  migrationHistoryGroupId = null;
  activeMigrationPath = null;
  migrationHistoryDisclosure.open = false;
  migrationPathScroller.replaceChildren();
  resetMigrationMomentum();
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
    activePeerPressure = null;
    activeMigrationPath = null;
    migrationHistoryGroupId = null;
    migrationHistoryDisclosure.open = false;
    migrationPathScroller.replaceChildren();
    resetMigrationMomentum();
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

async function openPeerPressure() {
  if (!activeSavedGroup) return;
  showGroupTab("pressure");
  const groupId = activeSavedGroup.id;
  peerPressureHeadline.textContent = "Loading Peer Pressure…";
  peerPressureSummary.textContent = "Reading canonical post-activation evidence.";
  peerPressureDrilldown.hidden = true;
  resetMigrationMomentum("Loading authoritative migration momentum…");
  const [pressurePayload, pathPayload] = await Promise.all([
    requestJson(`/api/groups/${encodeURIComponent(groupId)}/peer-pressure`),
    requestJson(`/api/groups/${encodeURIComponent(groupId)}/migration-path`),
  ]);
  if (activeSavedGroup?.id !== groupId) return;
  activeMigrationPath = pathPayload;
  migrationHistoryGroupId = groupId;
  renderPeerPressure(pressurePayload);
  renderMigrationMomentum(pathPayload, pressurePayload);
  if (migrationHistoryDisclosure.open) renderMigrationPath(pathPayload);
}

async function loadMigrationHistory() {
  if (!activeSavedGroup || !migrationHistoryDisclosure.open) return;
  const groupId = activeSavedGroup.id;
  if (migrationHistoryGroupId === groupId && activeMigrationPath) {
    renderMigrationPath(activeMigrationPath);
    return;
  }
  const loading = document.createElement("p");
  loading.className = "migration-path-all-empty";
  loading.textContent = "Loading authoritative migration history…";
  migrationPathScroller.replaceChildren(loading);
  const payload = await requestJson(`/api/groups/${encodeURIComponent(groupId)}/migration-path`);
  if (activeSavedGroup?.id === groupId && migrationHistoryDisclosure.open) {
    migrationHistoryGroupId = groupId;
    activeMigrationPath = payload;
    renderMigrationPath(payload);
  }
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
peerPressureTab.addEventListener("click", () => openPeerPressure().catch(showError));
peerPressureButtons.forEach((button) => {
  button.addEventListener("click", () => {
    renderPeerPressureDrilldown(button.dataset.pressureDirection);
  });
});
universePressureButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setHeatmapPressureFilter(button.dataset.universePressureDirection, true);
  });
});
heatmapPressureButtons.forEach((button) => {
  button.addEventListener("click", () => {
    setHeatmapPressureFilter(button.dataset.heatmapPressureFilter);
  });
});
migrationHistoryDisclosure.addEventListener("toggle", () => {
  if (migrationHistoryDisclosure.open) loadMigrationHistory().catch(showError);
});
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
migrationEvidenceClose.addEventListener("click", () => migrationEvidenceDialog.close());
migrationEvidenceDialog.addEventListener("click", (event) => {
  if (event.target === migrationEvidenceDialog) migrationEvidenceDialog.close();
});
migrationEvidenceDialog.addEventListener("close", () => {
  migrationEvidenceReturnFocus?.focus();
  migrationEvidenceReturnFocus = null;
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
  if (groupTrackingState.enabled) {
    if (savedGroups.length > 0) await openSavedGroupById(savedGroups[0].id);
    else startNewGroup();
  }
  const requestedSymbol = requestedSymbolFromQuery();
  if (requestedSymbol && Array.from(select.options).some(({ value }) => value === requestedSymbol)) {
    await selectSymbol(requestedSymbol);
  }
}

initializeMonitor().catch(showError);
