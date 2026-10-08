(function initializeMrzShell(globalObject) {
  "use strict";

  const SIDEBAR_STORAGE_KEY = "edge2.mrz.sidebar.collapsed";
  const MRZ_NAVIGATION = [
    {
      section: "OVERVIEW",
      routes: [
        { name: "overview", label: "Overview", abbreviation: "OV", href: "/mrz/overview" },
      ],
    },
    {
      section: "TRADING",
      routes: [
        { name: "watchlists", label: "Watchlists", abbreviation: "WL", href: "/mrz/watchlists", badgeId: "navAttentionCount" },
        { name: "attention", label: "Attention", abbreviation: "AT", href: "/mrz/attention" },
        { name: "symbols", label: "Symbols", abbreviation: "SY", href: "/mrz/symbols" },
        { name: "pressure", label: "Pressure", abbreviation: "PR", href: "/mrz/pressure" },
        { name: "alert-settings", label: "Alert Settings", abbreviation: "AL", href: "/mrz/alert-settings" },
      ],
    },
    {
      section: "MRZ RESEARCH",
      routes: [
        { name: "location-distribution", label: "Location Distribution", abbreviation: "LD", href: "/mrz/location-distribution" },
        { name: "formation-diagnostics", label: "Formation Diagnostics", abbreviation: "FD", href: "/mrz/formation-diagnostics" },
        { name: "events", label: "Events", abbreviation: "EV", href: "/mrz/events" },
      ],
    },
  ];

  function routeNameForPath(pathname) {
    const normalized = String(pathname || "/").replace(/\/$/, "");
    if (normalized === "" || normalized === "/" || normalized === "/mrz") return "overview";
    if (
      normalized === "/mrz/formation-diagnostics"
      || normalized === "/diagnostics/activation-feasibility"
    ) return "formation-diagnostics";
    const candidate = normalized.split("/").pop();
    return MRZ_NAVIGATION.flatMap((group) => group.routes)
      .some((route) => route.name === candidate)
      ? candidate
      : "overview";
  }

  function navigationMarkup(activeRoute) {
    return MRZ_NAVIGATION.map((group) => `
      <p>${group.section}</p>
      ${group.routes.map((route) => {
        const current = route.name === activeRoute ? ' aria-current="page"' : "";
        const badge = route.badgeId ? `<b id="${route.badgeId}" hidden>0</b>` : "";
        return `<a href="${route.href}" data-route="${route.name}" aria-label="${route.label}" title="${route.label}"${current}><span class="nav-abbreviation" aria-hidden="true">${route.abbreviation}</span><span class="nav-label">${route.label}</span>${badge}</a>`;
      }).join("")}
    `).join("");
  }

  function sidebarMarkup(activeRoute) {
    return `
      <a class="workspace-brand" href="/mrz/overview" aria-label="EDGE 2.0 MRZ Monitor home"><span class="brand-mark">E</span><span class="brand-copy"><strong>EDGE 2.0</strong><small>MRZ Monitor</small></span></a>
      <nav class="workspace-navigation">${navigationMarkup(activeRoute)}</nav>
      <button class="sidebar-toggle" id="sidebarToggle" type="button" aria-controls="mrzWorkspaceMain"><span class="sidebar-toggle-icon" aria-hidden="true">‹</span><span class="sidebar-toggle-label">Collapse</span></button>
      <div class="sidebar-foot"><span class="health-dot" id="healthState">Checking system</span><small>Canonical universe monitoring</small></div>
    `;
  }

  function readCollapsedPreference(storage) {
    try {
      return storage?.getItem(SIDEBAR_STORAGE_KEY) === "true";
    } catch {
      return false;
    }
  }

  function applyCollapsedState(documentRef, collapsed) {
    documentRef.body.classList.toggle("sidebar-collapsed", collapsed);
    const button = documentRef.querySelector("#sidebarToggle");
    if (!button) return;
    button.setAttribute("aria-expanded", String(!collapsed));
    button.setAttribute("aria-label", collapsed ? "Expand MRZ navigation" : "Collapse MRZ navigation");
    button.title = collapsed ? "Expand MRZ navigation" : "Collapse MRZ navigation";
    const icon = button.querySelector(".sidebar-toggle-icon");
    const label = button.querySelector(".sidebar-toggle-label");
    if (icon) icon.textContent = collapsed ? "›" : "‹";
    if (label) label.textContent = collapsed ? "Expand" : "Collapse";
  }

  function storeCollapsedPreference(storage, collapsed) {
    try {
      storage?.setItem(SIDEBAR_STORAGE_KEY, String(collapsed));
    } catch {
      // The shell still works when storage is unavailable or blocked.
    }
  }

  async function loadShellHealth(documentRef, fetchImpl) {
    const sidebarHealth = documentRef.querySelector("#healthState");
    const headerHealth = documentRef.querySelector("#headerHealth");
    try {
      const response = await fetchImpl("/health", { cache: "no-store" });
      const healthy = response.ok;
      if (sidebarHealth) {
        sidebarHealth.textContent = healthy ? "System healthy" : "System degraded";
        sidebarHealth.className = `health-dot ${healthy ? "healthy" : "unhealthy"}`;
      }
      if (headerHealth) {
        headerHealth.textContent = healthy ? "● System healthy" : "● System degraded";
        headerHealth.style.color = healthy ? "var(--accent)" : "var(--red)";
      }
    } catch {
      if (sidebarHealth) {
        sidebarHealth.textContent = "System unavailable";
        sidebarHealth.className = "health-dot unhealthy";
      }
      if (headerHealth) headerHealth.textContent = "● System unavailable";
    }
  }

  function mountMrzShell({
    documentRef = globalObject.document,
    locationObject = globalObject.location,
    storage = globalObject.localStorage,
    fetchImpl = globalObject.fetch?.bind(globalObject),
  } = {}) {
    if (!documentRef) return null;
    const sidebar = documentRef.querySelector("[data-mrz-sidebar]");
    if (!sidebar) return null;
    const activeRoute = routeNameForPath(locationObject?.pathname);
    sidebar.innerHTML = sidebarMarkup(activeRoute);
    const collapsed = readCollapsedPreference(storage);
    applyCollapsedState(documentRef, collapsed);

    documentRef.querySelector("#sidebarToggle")?.addEventListener("click", () => {
      const nextCollapsed = !documentRef.body.classList.contains("sidebar-collapsed");
      applyCollapsedState(documentRef, nextCollapsed);
      storeCollapsedPreference(storage, nextCollapsed);
    });
    documentRef.querySelector("#mobileNavButton")?.addEventListener("click", () => {
      documentRef.body.classList.toggle("nav-open");
    });
    sidebar.querySelectorAll(".workspace-navigation a").forEach((link) => {
      link.addEventListener("click", () => documentRef.body.classList.remove("nav-open"));
    });
    if (fetchImpl) loadShellHealth(documentRef, fetchImpl);
    return { activeRoute, collapsed };
  }

  const exported = {
    MRZ_NAVIGATION,
    SIDEBAR_STORAGE_KEY,
    applyCollapsedState,
    mountMrzShell,
    navigationMarkup,
    readCollapsedPreference,
    routeNameForPath,
    sidebarMarkup,
    storeCollapsedPreference,
  };
  globalObject.edgeMrzShell = exported;

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", () => mountMrzShell(), { once: true });
  }
  if (typeof module === "object" && module.exports) module.exports = exported;
}(globalThis));
