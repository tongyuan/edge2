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
const selectedGroupPanel = document.querySelector("#selectedGroupPanel");
const selectedGroupSymbols = document.querySelector("#selectedGroupSymbols");
const showSelectedOnly = document.querySelector("#showSelectedOnly");
const clearSelectedGroup = document.querySelector("#clearSelectedGroup");
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
  createGroupTrackingState,
  setGroupTrackingEnabled,
  toggleGroupSymbol,
  setShowSelectedOnly,
  clearGroupSelection,
  reconcileGroupTrackingState,
  groupTrackingSummary,
  visibleSymbolsForGroupTracking,
} = globalThis.edgeHeatmapState;
const {
  buildEvidencePresentation,
  buildMigrationPresentation,
  formatLatestObservationContext,
  formatActivatedAt,
} = globalThis.edgeMonitorPresentation;

const fields = {
  symbol: document.querySelector("#symbolName"),
  status: document.querySelector("#mrzStatus"),
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
};
const activityTooltip = document.querySelector("#heatmapActivityTooltip");
let activityTooltipOwner = null;

const distributionFields = {
  deep_discount: {
    count: document.querySelector("#distributionDeepDiscountCount"),
    percentage: document.querySelector("#distributionDeepDiscountPercentage"),
  },
  shallow_discount: {
    count: document.querySelector("#distributionShallowDiscountCount"),
    percentage: document.querySelector("#distributionShallowDiscountPercentage"),
  },
  shallow_premium: {
    count: document.querySelector("#distributionShallowPremiumCount"),
    percentage: document.querySelector("#distributionShallowPremiumPercentage"),
  },
  deep_premium: {
    count: document.querySelector("#distributionDeepPremiumCount"),
    percentage: document.querySelector("#distributionDeepPremiumPercentage"),
  },
};
const distributionTotals = {
  discount: document.querySelector("#distributionDiscountTotal"),
  premium: document.querySelector("#distributionPremiumTotal"),
};
const selectedGroupFields = {
  count: document.querySelector("#selectedGroupCount"),
  btd: document.querySelector("#selectedGroupBtdCount"),
  str: document.querySelector("#selectedGroupStrCount"),
  active: document.querySelector("#selectedGroupActiveCount"),
  migrated: document.querySelector("#selectedGroupMigratedCount"),
  locations: {
    deep_discount: document.querySelector("#selectedGroupDeepDiscountCount"),
    shallow_discount: document.querySelector("#selectedGroupShallowDiscountCount"),
    shallow_premium: document.querySelector("#selectedGroupShallowPremiumCount"),
    deep_premium: document.querySelector("#selectedGroupDeepPremiumCount"),
  },
};

let overviewSymbols = [];
let minimumClusterObservations = null;
let groupTrackingState = createGroupTrackingState();

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
        groupTrackingState.enabled && groupTrackingState.selectedSymbols.has(symbol)
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

function renderLocationDistribution(groups) {
  const distribution = locationDistributionFromGroups(groups);
  primaryLocationKeys.forEach((key) => {
    const bucket = distribution.buckets[key];
    distributionFields[key].count.textContent = String(bucket.count);
    distributionFields[key].percentage.textContent = formatLocationPercentage(
      bucket.percentage,
    );
  });
  distributionTotals.discount.textContent = (
    `${distribution.discountTotal.count} · ${formatLocationPercentage(distribution.discountTotal.percentage)}`
  );
  distributionTotals.premium.textContent = (
    `${distribution.premiumTotal.count} · ${formatLocationPercentage(distribution.premiumTotal.percentage)}`
  );
  locationDistribution.setAttribute(
    "aria-label",
    `Location distribution for ${distribution.classifiedTotal} classified symbols`,
  );
}

function renderSelectedGroupPanel() {
  const summary = groupTrackingSummary(overviewSymbols, groupTrackingState);
  const visible = groupTrackingState.enabled && summary.selectedCount > 0;
  selectedGroupPanel.hidden = !visible;
  selectedGroupFields.count.textContent = String(summary.selectedCount);
  selectedGroupSymbols.replaceChildren(...summary.selectedStates.map(({ symbol }) => {
    const item = document.createElement("li");
    item.textContent = symbol;
    return item;
  }));
  selectedGroupFields.btd.textContent = String(summary.routeMix.BTD);
  selectedGroupFields.str.textContent = String(summary.routeMix.STR);
  primaryLocationKeys.forEach((key) => {
    selectedGroupFields.locations[key].textContent = String(summary.locationMix[key]);
  });
  selectedGroupFields.active.textContent = (
    `${summary.activeMrzCount} / ${summary.selectedCount}`
  );
  selectedGroupFields.migrated.textContent = (
    `${summary.migratedCount} / ${summary.selectedCount}`
  );
  showSelectedOnly.checked = groupTrackingState.showSelectedOnly;
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
  renderLocationDistribution(allGroups);
  const visibleSymbols = visibleSymbolsForGroupTracking(overviewSymbols, groupTrackingState);
  const visibleGroups = visibleSymbols === overviewSymbols
    ? allGroups
    : groupSymbolsByLocation(visibleSymbols, minimumClusterObservations);
  renderLocationHeatmap(visibleSymbols, minimumClusterObservations, visibleGroups);
  groupTrackingToggle.checked = groupTrackingState.enabled;
  groupTrackingStateLabel.textContent = groupTrackingState.enabled ? "On" : "Off";
  renderSelectedGroupPanel();
  updateSelectedChip(select.value);
}

function updateSelectedChip(symbol) {
  document.querySelectorAll(".symbol-chip").forEach((chip) => {
    const singleSelected = !groupTrackingState.enabled && chip.dataset.symbol === symbol;
    const groupSelected = (
      groupTrackingState.enabled
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
  groupTrackingState = reconcileGroupTrackingState(groupTrackingState, overviewSymbols);
  select.replaceChildren(new Option("Select a symbol", ""));
  overviewSymbols.forEach(({ symbol }) => select.add(new Option(symbol, symbol)));
  select.disabled = overviewSymbols.length === 0;
  select.value = selectedSymbol;
  renderMonitorOverview();
}

async function handleHeatmapChipClick(symbol) {
  if (!groupTrackingState.enabled) {
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
  emptyState.hidden = true;
  stateCard.hidden = false;
}

select.addEventListener("change", () => selectSymbol(select.value).catch(showError));
groupTrackingToggle.addEventListener("change", () => {
  groupTrackingState = setGroupTrackingEnabled(
    groupTrackingState,
    groupTrackingToggle.checked,
  );
  renderMonitorOverview();
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
  await loadSymbols();
  const requestedSymbol = requestedSymbolFromQuery();
  if (requestedSymbol && Array.from(select.options).some(({ value }) => value === requestedSymbol)) {
    await selectSymbol(requestedSymbol);
  }
}

initializeMonitor().catch(showError);
