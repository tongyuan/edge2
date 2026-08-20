const select = document.querySelector("#symbolSelect");
const emptyState = document.querySelector("#emptyState");
const stateCard = document.querySelector("#stateCard");
const healthState = document.querySelector("#healthState");
const locationHeatmap = document.querySelector("#locationHeatmap");
const heatmapEmpty = document.querySelector("#heatmapEmpty");
const primaryLocationGroups = document.querySelector("#primaryLocationGroups");
const secondaryLocationGroups = document.querySelector("#secondaryLocationGroups");

const fields = {
  symbol: document.querySelector("#symbolName"),
  status: document.querySelector("#mrzStatus"),
  owner: document.querySelector("#routeOwner"),
  bounds: document.querySelector("#mrzBounds"),
  location: document.querySelector("#structuralLocation"),
  currentLocation: document.querySelector("#currentPriceLocation"),
  evidence: document.querySelector("#evidence"),
  latest: document.querySelector("#latestObservation"),
  midpoint: document.querySelector("#mrzMidpoint"),
};

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

const primaryLocationKeys = [
  "deep_discount",
  "shallow_discount",
  "shallow_premium",
  "deep_premium",
];

const secondaryLocationKeys = [
  "below_ipda_range",
  "above_ipda_range",
  "unavailable",
];

const allLocationKeys = new Set([...primaryLocationKeys, ...secondaryLocationKeys]);

function groupSymbolsByLocation(symbols) {
  const groups = Object.fromEntries([...allLocationKeys].map((key) => [key, []]));
  symbols.forEach(({ symbol, current_price_location: currentLocation }) => {
    const key = allLocationKeys.has(currentLocation) ? currentLocation : "unavailable";
    groups[key].push(symbol);
  });
  Object.values(groups).forEach((symbolsInGroup) => symbolsInGroup.sort((left, right) => left.localeCompare(right)));
  return groups;
}

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
    symbols.forEach((symbol) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "symbol-chip";
      button.dataset.symbol = symbol;
      button.setAttribute("aria-pressed", "false");
      button.setAttribute("aria-label", `Select ${symbol}`);
      button.textContent = symbol;
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
  fields.evidence.textContent = active
    ? `${state.confirming_observation_count} qualifying ${state.route_owner === "BTD" ? "reclaim" : "rejection"} observations`
    : "Concentration not established";
  fields.latest.textContent = formatPrice(state.latest_observation_price);
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
