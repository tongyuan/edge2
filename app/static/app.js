const select = document.querySelector("#symbolSelect");
const emptyState = document.querySelector("#emptyState");
const stateCard = document.querySelector("#stateCard");
const healthState = document.querySelector("#healthState");

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
  select.disabled = false;
  if (payload.symbols.length === 1) {
    select.value = payload.symbols[0].symbol;
    await loadSymbol(select.value);
  }
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

select.addEventListener("change", () => loadSymbol(select.value).catch(showError));

function showError(error) {
  emptyState.hidden = false;
  stateCard.hidden = true;
  emptyState.querySelector("p").textContent = error.message;
}

loadHealth();
loadSymbols().catch(showError);
