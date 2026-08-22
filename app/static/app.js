const select = document.querySelector("#symbolSelect");
const emptyState = document.querySelector("#emptyState");
const stateCard = document.querySelector("#stateCard");
const healthState = document.querySelector("#healthState");
const locationHeatmap = document.querySelector("#locationHeatmap");
const heatmapEmpty = document.querySelector("#heatmapEmpty");
const primaryLocationGroups = document.querySelector("#primaryLocationGroups");
const secondaryLocationGroups = document.querySelector("#secondaryLocationGroups");
const {
  primaryLocationKeys,
  secondaryLocationKeys,
  hasActiveMrz,
  routeAlignedActivity,
  activityTooltipText,
  accessibleChipLabel,
  groupSymbolsByLocation,
} = globalThis.edgeHeatmapState;
const {
  buildEvidencePresentation,
  formatLatestObservationContext,
} = globalThis.edgeMonitorPresentation;

const fields = {
  symbol: document.querySelector("#symbolName"),
  status: document.querySelector("#mrzStatus"),
  owner: document.querySelector("#routeOwner"),
  bounds: document.querySelector("#mrzBounds"),
  location: document.querySelector("#structuralLocation"),
  currentLocation: document.querySelector("#currentPriceLocation"),
  currentLocationContext: document.querySelector("#currentLocationContext"),
  evidence: document.querySelector("#evidence"),
  latest: document.querySelector("#latestObservation"),
  midpoint: document.querySelector("#mrzMidpoint"),
};
const activityTooltip = document.querySelector("#heatmapActivityTooltip");
let activityTooltipOwner = null;

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

function renderFact(field, primary, secondary = []) {
  const primaryLine = document.createElement("span");
  primaryLine.className = "fact-primary";
  primaryLine.textContent = primary;
  const secondaryLines = secondary.filter(Boolean).map((text) => {
    const line = document.createElement("span");
    line.className = "fact-support";
    line.textContent = text;
    return line;
  });
  field.replaceChildren(primaryLine, ...secondaryLines);
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

function createLocationGroup(key, symbols, secondary = false) {
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
      button.classList.toggle("active-mrz", active);
      if (activity && activity.tier !== "none") {
        button.classList.add(`activity-${activity.tier}`);
      }
      button.dataset.symbol = symbol;
      button.setAttribute("aria-pressed", "false");
      const locationLabel = key === "unavailable" ? "Unavailable" : formatLocation(key);
      button.setAttribute("aria-label", accessibleChipLabel(symbolState, locationLabel));
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
      const label = document.createElement("span");
      label.textContent = symbol;
      button.append(label);
      button.addEventListener("click", () => selectSymbol(symbol).catch(showError));
      symbolList.append(button);
    });
  }
  group.append(symbolList);
  return group;
}

function renderLocationHeatmap(symbols) {
  if (symbols.length === 0) {
    locationHeatmap.hidden = true;
    heatmapEmpty.hidden = false;
    heatmapEmpty.textContent = "No symbols yet";
    return;
  }

  const groups = groupSymbolsByLocation(symbols);
  primaryLocationGroups.replaceChildren(
    ...primaryLocationKeys.map((key) => createLocationGroup(key, groups[key])),
  );
  const populatedSecondaryKeys = secondaryLocationKeys.filter((key) => groups[key].length > 0);
  secondaryLocationGroups.replaceChildren(
    ...populatedSecondaryKeys.map((key) => createLocationGroup(key, groups[key], true)),
  );
  secondaryLocationGroups.hidden = populatedSecondaryKeys.length === 0;
  heatmapEmpty.hidden = true;
  locationHeatmap.hidden = false;
}

function updateSelectedChip(symbol) {
  document.querySelectorAll(".symbol-chip").forEach((chip) => {
    const selected = chip.dataset.symbol === symbol;
    chip.classList.toggle("selected", selected);
    chip.setAttribute("aria-pressed", String(selected));
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
  select.replaceChildren(new Option("Select a symbol", ""));
  payload.symbols.forEach(({ symbol }) => select.add(new Option(symbol, symbol)));
  select.disabled = payload.symbols.length === 0;
  renderLocationHeatmap(payload.symbols);
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
  fields.location.textContent = active ? formatLocation(state.structural_location) : "—";
  fields.currentLocation.textContent = formatLocation(state.current_price_location);
  fields.currentLocationContext.textContent = state.current_location_context || "—";
  const evidence = buildEvidencePresentation(state);
  renderFact(fields.evidence, evidence.primary, evidence.secondary);
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

function showError(error) {
  emptyState.hidden = false;
  stateCard.hidden = true;
  emptyState.querySelector("p").textContent = error.message;
  if (heatmapEmpty.textContent === "Loading locations…") {
    heatmapEmpty.textContent = "Locations unavailable";
  }
}

loadHealth();
loadSymbols().catch(showError);
