(function initializeDockWorkspace(globalObject) {
  function storedCollapsed(symbol) {
    try { return globalObject.localStorage.getItem(`edgeDockDetails:${symbol}`) === "true"; } catch { return false; }
  }

  globalObject.addEventListener("DOMContentLoaded", () => {
    const path = globalObject.location.pathname;
    if (path === "/dock/inbox") {
      document.body.dataset.dockFeature = "inbox";
      document.querySelector("#dockInbox").hidden = false;
      globalObject.edgeDocking.trackDockedWindow("inbox");
      return;
    }
    const match = path.match(/^\/dock\/opportunity-map\/([^/]+)$/);
    if (!match) return;
    const symbol = decodeURIComponent(match[1]).toUpperCase();
    const params = new URLSearchParams(globalObject.location.search);
    const requestedRange = Number(params.get("range"));
    const rangeDays = [0, 30, 90].includes(requestedRange) ? requestedRange : 90;
    const requestedViewStart = Number(params.get("view_start"));
    const requestedViewEnd = Number(params.get("view_end"));
    const initialViewport = Number.isFinite(requestedViewStart) && Number.isFinite(requestedViewEnd) && requestedViewEnd > requestedViewStart
      ? { minimum: requestedViewStart, maximum: requestedViewEnd }
      : null;
    const returnUrl = params.get("return")?.startsWith("/") ? params.get("return") : "/mrz/watchlists";
    document.body.dataset.dockFeature = "opportunity-map";
    const target = document.querySelector("#dockOpportunityMap");
    target.hidden = false;
    globalObject.edgeDocking.trackDockedWindow("opportunity-map");
    globalObject.edgeOpportunityMap.renderSymbol(target, symbol, {
      docked: true,
      initialRangeDays: rangeDays,
      initialViewport,
      initialSelectedEventId: params.get("event") || null,
      detailsCollapsed: storedCollapsed(symbol),
      returnUrl,
      onRangeChange: (days) => {
        params.set("range", String(days));
        globalObject.history.replaceState(null, "", `${path}?${params}`);
      },
      onDetailsChange: (collapsed) => {
        try { globalObject.localStorage.setItem(`edgeDockDetails:${symbol}`, String(collapsed)); } catch { /* optional */ }
      },
    }).catch((error) => { target.textContent = error.message || "Opportunity Map is unavailable."; });
  });
}(globalThis));
