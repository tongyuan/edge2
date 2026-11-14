(function initializeMrzShell(globalObject) {
  "use strict";

  const SIDEBAR_STORAGE_KEY = "edge2.mrz.sidebar.collapsed";
  const MRZ_NAVIGATION = [
    {
      section: "TRADING",
      routes: [
        { name: "watchlists", label: "Group Radar", href: "/mrz/watchlists?group=all&window=24H", badgeId: "navAttentionCount" },
        { name: "symbols", label: "Symbols", href: "/mrz/symbols" },
        { name: "alert-settings", label: "Alert Settings", href: "/mrz/alert-settings" },
      ],
    },
    {
      section: "RESEARCH",
      routes: [
        { name: "location-distribution", label: "Location Distribution", href: "/mrz/location-distribution" },
        { name: "formation-diagnostics", label: "Formation Diagnostics", href: "/mrz/formation-diagnostics" },
        { name: "events", label: "Events History", href: "/mrz/events" },
      ],
    },
  ];
  const NAVIGATION_ICON_PATHS = {
    watchlists: '<circle cx="12" cy="12" r="8"></circle><circle cx="12" cy="12" r="2"></circle><path d="M12 2v3M22 12h-3M12 22v-3M2 12h3"></path>',
    symbols: '<path d="M4 6h16M4 12h16M4 18h16"></path><circle cx="8" cy="6" r="2"></circle><circle cx="15" cy="12" r="2"></circle><circle cx="10" cy="18" r="2"></circle>',
    "alert-settings": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"></path><path d="M10 21h4"></path>',
    "location-distribution": '<path d="M12 21s6-5.2 6-11a6 6 0 1 0-12 0c0 5.8 6 11 6 11"></path><circle cx="12" cy="10" r="2"></circle>',
    "formation-diagnostics": '<path d="M3 12h4l2-6 4 12 2-6h6"></path>',
    events: '<circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path>',
  };

  function navigationIcon(routeName) {
    return `<span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24" focusable="false">${NAVIGATION_ICON_PATHS[routeName] || NAVIGATION_ICON_PATHS.events}</svg></span>`;
  }

  function routeNameForPath(pathname) {
    const normalized = String(pathname || "/").replace(/\/$/, "");
    if (normalized === "" || normalized === "/" || normalized === "/mrz" || normalized === "/mrz/overview" || normalized === "/mrz/attention") return "watchlists";
    if (normalized === "/mrz/pressure" || normalized === "/mrz/pressure-history") return "events";
    if (normalized === "/mrz/breadth-leadership") return "location-distribution";
    if (
      normalized === "/mrz/formation-diagnostics"
      || normalized === "/diagnostics/activation-feasibility"
    ) return "formation-diagnostics";
    const candidate = normalized.split("/").pop();
    return MRZ_NAVIGATION.flatMap((group) => group.routes)
      .some((route) => route.name === candidate)
      ? candidate
      : "watchlists";
  }

  function navigationMarkup(activeRoute) {
    return MRZ_NAVIGATION.map((group) => `
      <p>${group.section}</p>
      ${group.routes.map((route) => {
        const current = route.name === activeRoute ? ' aria-current="page"' : "";
        const badge = route.badgeId ? `<b id="${route.badgeId}" hidden>0</b>` : "";
        return `<a href="${route.href}" data-route="${route.name}" aria-label="${route.label}" title="${route.label}"${current}>${navigationIcon(route.name)}<span class="nav-label">${route.label}</span>${badge}</a>`;
      }).join("")}
    `).join("");
  }

  function sidebarMarkup(activeRoute) {
    return `
      <a class="workspace-brand" href="/mrz/watchlists?group=all&window=24H" aria-label="EDGE 2.0 Group Radar home"><span class="brand-mark"><img src="/static/edge-intel-radar-icon-192.png" alt="" /></span><span class="brand-copy"><strong>EDGE 2.0</strong></span></a>
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
    button.setAttribute("aria-label", collapsed ? "Expand EDGE Intel navigation" : "Collapse EDGE Intel navigation");
    button.title = collapsed ? "Expand EDGE Intel navigation" : "Collapse EDGE Intel navigation";
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
    documentRef.body.classList.toggle("group-opportunity-active", activeRoute === "watchlists");
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
    navigationIcon,
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
