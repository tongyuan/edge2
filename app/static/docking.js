(function initializeEdgeDocking(globalObject) {
  const FEATURES = {
    "opportunity-map": { name: "edge-opportunity-map-dock", width: 1120, height: 760 },
    "migration-path": { name: "edge-migration-path-dock", width: 1080, height: 620 },
    inbox: { name: "edge-inbox-dock", width: 430, height: 720 },
  };
  const STORAGE_PREFIX = "edgeDockWindow:";

  function isStandalone() {
    return Boolean(globalObject.matchMedia?.("(display-mode: standalone)").matches || globalObject.navigator?.standalone);
  }

  function canDock() {
    const usefulWidth = Number(globalObject.screen?.availWidth || globalObject.innerWidth || 0);
    return typeof globalObject.open === "function" && !isStandalone() && usefulWidth >= 700;
  }

  function decorateDockButton(button, label) {
    if (!button) return button;
    button.classList.add("opportunity-dock-button", "dock-icon-button");
    button.setAttribute("aria-label", label);
    button.title = label;
    button.replaceChildren();
    const namespace = "http://www.w3.org/2000/svg";
    const icon = globalObject.document.createElementNS(namespace, "svg");
    icon.setAttribute("viewBox", "0 0 24 24");
    icon.setAttribute("aria-hidden", "true");
    icon.setAttribute("focusable", "false");
    const rectangle = globalObject.document.createElementNS(namespace, "rect");
    rectangle.setAttribute("width", "18"); rectangle.setAttribute("height", "18");
    rectangle.setAttribute("x", "3"); rectangle.setAttribute("y", "3"); rectangle.setAttribute("rx", "2");
    const horizontal = globalObject.document.createElementNS(namespace, "path"); horizontal.setAttribute("d", "M3 9h18");
    const vertical = globalObject.document.createElementNS(namespace, "path"); vertical.setAttribute("d", "M9 21V9");
    icon.append(rectangle, horizontal, vertical);
    button.append(icon);
    return button;
  }

  function createDockButton(label) {
    const button = globalObject.document.createElement("button");
    button.type = "button";
    return decorateDockButton(button, label);
  }

  function readSize(feature) {
    const defaults = FEATURES[feature];
    if (!defaults) throw new Error(`Unknown dock feature: ${feature}`);
    try {
      const stored = JSON.parse(globalObject.localStorage?.getItem(`${STORAGE_PREFIX}${feature}`) || "null");
      return {
        width: Math.max(360, Math.min(Number(stored?.width) || defaults.width, Number(globalObject.screen?.availWidth) || 2400)),
        height: Math.max(480, Math.min(Number(stored?.height) || defaults.height, Number(globalObject.screen?.availHeight) || 1600)),
      };
    } catch {
      return { width: defaults.width, height: defaults.height };
    }
  }

  function writeSize(feature, width, height) {
    try {
      globalObject.localStorage?.setItem(`${STORAGE_PREFIX}${feature}`, JSON.stringify({
        width: Math.round(width), height: Math.round(height),
      }));
    } catch { /* Window sizing is a convenience only. */ }
  }

  function dockUrl(feature, context = {}) {
    if (feature === "inbox") return "/dock/inbox";
    if (feature === "migration-path") {
      const params = new URLSearchParams({ symbol: String(context.symbol || "").toUpperCase(), focus: "migration-path", chart_only: "1" });
      if (context.returnUrl) params.set("return", context.returnUrl);
      if (Number.isFinite(Number(context.windowStart))) params.set("migration_start", String(Math.max(0, Math.round(Number(context.windowStart)))));
      if (Number.isFinite(Number(context.windowSize)) && Number(context.windowSize) > 0) params.set("migration_size", String(Math.round(Number(context.windowSize))));
      if (context.selectedEventId) params.set("migration_event", String(context.selectedEventId));
      return `/mrz/symbols?${params}`;
    }
    if (feature !== "opportunity-map") throw new Error(`Unknown dock feature: ${feature}`);
    const symbol = String(context.symbol || "").trim().toUpperCase();
    if (!symbol) throw new Error("A symbol is required to dock the Opportunity Map.");
    const query = new URLSearchParams();
    const rangeDays = Number(context.rangeDays);
    if ([0, 30, 90].includes(rangeDays)) query.set("range", String(rangeDays));
    const viewStart = Number(context.viewStart);
    const viewEnd = Number(context.viewEnd);
    if (Number.isFinite(viewStart) && Number.isFinite(viewEnd) && viewEnd > viewStart) {
      query.set("view_start", String(Math.round(viewStart)));
      query.set("view_end", String(Math.round(viewEnd)));
    }
    if (context.selectedEventId) query.set("event", String(context.selectedEventId));
    if (context.returnUrl && String(context.returnUrl).startsWith("/")) query.set("return", context.returnUrl);
    return `/dock/opportunity-map/${encodeURIComponent(symbol)}${query.size ? `?${query}` : ""}`;
  }

  function openDock(feature, context = {}) {
    if (!canDock()) return null;
    const config = FEATURES[feature];
    const size = readSize(feature);
    const features = `popup=yes,resizable=yes,scrollbars=yes,width=${size.width},height=${size.height}`;
    const dock = globalObject.open(dockUrl(feature, context), config.name, features);
    if (!dock) {
      globalObject.dispatchEvent?.(new CustomEvent("edge:dock-blocked", { detail: { feature } }));
      return null;
    }
    try { dock.focus(); } catch { /* Browser focus policy may decline the request. */ }
    return dock;
  }

  function trackDockedWindow(feature) {
    let timer = null;
    const save = () => writeSize(feature, globalObject.outerWidth, globalObject.outerHeight);
    const queueSave = () => {
      globalObject.clearTimeout(timer);
      timer = globalObject.setTimeout(save, 180);
    };
    globalObject.addEventListener?.("resize", queueSave);
    globalObject.addEventListener?.("pagehide", save);
    return save;
  }

  function openInMain(path) {
    const safePath = String(path || "/").startsWith("/") ? String(path || "/") : "/";
    let target = null;
    try {
      if (globalObject.opener && !globalObject.opener.closed && globalObject.opener.location.origin === globalObject.location.origin) {
        target = globalObject.opener;
        target.location.assign(safePath);
      }
    } catch { target = null; }
    if (!target) target = globalObject.open(safePath, "edge-main-workspace");
    try { target?.focus(); } catch { /* Focus is best effort. */ }
    return target;
  }

  const exported = {
    canDock,
    createDockButton,
    decorateDockButton,
    dockUrl,
    openDock,
    openInbox: () => openDock("inbox"),
    openMigrationPath: (symbol, context = {}) => openDock("migration-path", { ...context, symbol }),
    openOpportunityMap: (symbol, context = {}) => openDock("opportunity-map", { ...context, symbol }),
    openInMain,
    readSize,
    trackDockedWindow,
    writeSize,
  };
  globalObject.edgeDocking = exported;
  if (typeof module === "object" && module.exports) module.exports = exported;
}(globalThis));
