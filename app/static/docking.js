(function initializeEdgeDocking(globalObject) {
  const FEATURES = {
    "opportunity-map": { name: "edge-opportunity-map-dock", width: 1120, height: 760 },
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
    if (feature !== "opportunity-map") throw new Error(`Unknown dock feature: ${feature}`);
    const symbol = String(context.symbol || "").trim().toUpperCase();
    if (!symbol) throw new Error("A symbol is required to dock the Opportunity Map.");
    const query = new URLSearchParams();
    const rangeDays = Number(context.rangeDays);
    if ([0, 30, 90].includes(rangeDays)) query.set("range", String(rangeDays));
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
    dockUrl,
    openDock,
    openInbox: () => openDock("inbox"),
    openOpportunityMap: (symbol, context = {}) => openDock("opportunity-map", { ...context, symbol }),
    openInMain,
    readSize,
    trackDockedWindow,
    writeSize,
  };
  globalObject.edgeDocking = exported;
  if (typeof module === "object" && module.exports) module.exports = exported;
}(globalThis));
