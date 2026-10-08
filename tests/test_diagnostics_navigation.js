const assert = require("node:assert/strict");
const {
  setupDiagnosticsNavigation,
} = require("../app/static/diagnostics-nav.js");
const {
  MRZ_NAVIGATION,
  SIDEBAR_STORAGE_KEY,
  applyCollapsedState,
  mountMrzShell,
  navigationMarkup,
  readCollapsedPreference,
  routeNameForPath,
  sidebarMarkup,
  storeCollapsedPreference,
} = require("../app/static/mrz-shell.js");

class FakeEventTarget {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  dispatch(type, event = {}) {
    const dispatched = {
      target: this,
      key: undefined,
      defaultPrevented: false,
      preventDefault() { this.defaultPrevented = true; },
      ...event,
    };
    (this.listeners.get(type) || []).forEach((listener) => listener(dispatched));
    return dispatched;
  }
}

class FakeElement extends FakeEventTarget {
  constructor(documentRef) {
    super();
    this.attributes = new Map();
    this.documentRef = documentRef;
    this.hidden = false;
  }

  focus() {
    this.documentRef.activeElement = this;
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
}

class FakeDocument extends FakeEventTarget {
  constructor() {
    super();
    this.activeElement = null;
  }
}

function fixture() {
  const documentRef = new FakeDocument();
  const trigger = new FakeElement(documentRef);
  const menu = new FakeElement(documentRef);
  const items = [0, 1, 2].map(() => new FakeElement(documentRef));
  const members = new Set([trigger, menu, ...items]);
  const navigation = {
    querySelector(selector) {
      if (selector === "[data-diagnostics-trigger]") return trigger;
      if (selector === "[data-diagnostics-menu]") return menu;
      return null;
    },
    contains(target) { return members.has(target); },
  };
  menu.querySelectorAll = (selector) => (
    selector === 'a[role="menuitem"]' ? items : []
  );
  trigger.setAttribute("aria-expanded", "false");
  menu.hidden = true;
  return {
    controller: setupDiagnosticsNavigation(navigation, documentRef),
    documentRef,
    items,
    menu,
    trigger,
  };
}

{
  const { controller, menu, trigger } = fixture();
  assert.equal(controller.isOpen(), false);
  trigger.dispatch("click");
  assert.equal(controller.isOpen(), true);
  assert.equal(menu.hidden, false);
  trigger.dispatch("click");
  assert.equal(controller.isOpen(), false);
  assert.equal(menu.hidden, true);
}

{
  const { controller, documentRef, menu, trigger } = fixture();
  trigger.dispatch("click");
  documentRef.dispatch("click", { target: {} });
  assert.equal(controller.isOpen(), false);
  assert.equal(menu.hidden, true);
}

{
  const { controller, documentRef, trigger } = fixture();
  trigger.dispatch("click");
  const escape = documentRef.dispatch("keydown", { key: "Escape" });
  assert.equal(escape.defaultPrevented, true);
  assert.equal(controller.isOpen(), false);
  assert.equal(documentRef.activeElement, trigger);
}

{
  const { controller, documentRef, items, menu, trigger } = fixture();
  const openFromKeyboard = trigger.dispatch("keydown", { key: "ArrowDown" });
  assert.equal(openFromKeyboard.defaultPrevented, true);
  assert.equal(controller.isOpen(), true);
  assert.equal(documentRef.activeElement, items[0]);

  menu.dispatch("keydown", { key: "ArrowDown" });
  assert.equal(documentRef.activeElement, items[1]);
  menu.dispatch("keydown", { key: "End" });
  assert.equal(documentRef.activeElement, items[2]);
  menu.dispatch("keydown", { key: "Home" });
  assert.equal(documentRef.activeElement, items[0]);

  const selectItem = items[0].dispatch("click");
  assert.equal(selectItem.defaultPrevented, false, "menu item navigation remains native");
  assert.equal(controller.isOpen(), false);
}

console.log("diagnostics navigation tests passed");

{
  const routes = MRZ_NAVIGATION.flatMap((group) => group.routes);
  assert.deepEqual(
    routes.map((route) => route.name),
    ["overview", "watchlists", "attention", "symbols", "pressure", "alert-settings", "formation-diagnostics", "events"],
  );
  const formationNavigation = navigationMarkup("formation-diagnostics");
  assert.match(formationNavigation, /href="\/mrz\/formation-diagnostics"[^>]+aria-current="page"/);
  assert.match(formationNavigation, /href="\/mrz\/events"/);
  assert.match(formationNavigation, /aria-label="Alert Settings" title="Alert Settings"/);
  assert.match(sidebarMarkup("events"), /id="sidebarToggle"/);
  assert.equal(routeNameForPath("/mrz/formation-diagnostics"), "formation-diagnostics");
  assert.equal(routeNameForPath("/diagnostics/activation-feasibility"), "formation-diagnostics");
  assert.equal(routeNameForPath("/mrz/events"), "events");
}

{
  const values = new Map();
  const storage = {
    getItem(key) { return values.get(key) ?? null; },
    setItem(key, value) { values.set(key, value); },
  };
  assert.equal(readCollapsedPreference(storage), false);
  storeCollapsedPreference(storage, true);
  assert.equal(values.get(SIDEBAR_STORAGE_KEY), "true");
  assert.equal(readCollapsedPreference(storage), true);
}

{
  const classes = new Set();
  const attributes = new Map();
  const icon = { textContent: "" };
  const label = { textContent: "" };
  const button = {
    title: "",
    setAttribute(name, value) { attributes.set(name, String(value)); },
    querySelector(selector) {
      if (selector === ".sidebar-toggle-icon") return icon;
      if (selector === ".sidebar-toggle-label") return label;
      return null;
    },
  };
  const documentRef = {
    body: {
      classList: {
        toggle(name, enabled) {
          if (enabled) classes.add(name); else classes.delete(name);
        },
      },
    },
    querySelector(selector) { return selector === "#sidebarToggle" ? button : null; },
  };
  applyCollapsedState(documentRef, true);
  assert.equal(classes.has("sidebar-collapsed"), true);
  assert.equal(attributes.get("aria-expanded"), "false");
  assert.equal(attributes.get("aria-label"), "Expand MRZ navigation");
  assert.equal(icon.textContent, "›");
  applyCollapsedState(documentRef, false);
  assert.equal(classes.has("sidebar-collapsed"), false);
  assert.equal(attributes.get("aria-expanded"), "true");
  assert.equal(attributes.get("aria-label"), "Collapse MRZ navigation");
  assert.equal(icon.textContent, "‹");
}

console.log("shared MRZ shell tests passed");

{
  const classes = new Set();
  const classList = {
    contains(name) { return classes.has(name); },
    remove(name) { classes.delete(name); },
    toggle(name, enabled) {
      const next = enabled === undefined ? !classes.has(name) : enabled;
      if (next) classes.add(name); else classes.delete(name);
      return next;
    },
  };
  const icon = { textContent: "" };
  const label = { textContent: "" };
  const toggle = new FakeEventTarget();
  toggle.attributes = new Map();
  toggle.setAttribute = (name, value) => toggle.attributes.set(name, String(value));
  toggle.querySelector = (selector) => (
    selector === ".sidebar-toggle-icon" ? icon
      : selector === ".sidebar-toggle-label" ? label
        : null
  );
  const mobile = new FakeEventTarget();
  const routeLinks = Array.from({ length: 8 }, () => new FakeEventTarget());
  const sidebar = {
    innerHTML: "",
    querySelectorAll(selector) {
      return selector === ".workspace-navigation a" ? routeLinks : [];
    },
  };
  const storageValues = new Map([[SIDEBAR_STORAGE_KEY, "true"]]);
  const storage = {
    getItem(key) { return storageValues.get(key) ?? null; },
    setItem(key, value) { storageValues.set(key, value); },
  };
  const documentRef = {
    body: { classList },
    querySelector(selector) {
      if (selector === "[data-mrz-sidebar]") return sidebar;
      if (selector === "#sidebarToggle") return toggle;
      if (selector === "#mobileNavButton") return mobile;
      return null;
    },
  };
  const mounted = mountMrzShell({
    documentRef,
    locationObject: { pathname: "/mrz/formation-diagnostics" },
    storage,
    fetchImpl: null,
  });
  assert.deepEqual(mounted, { activeRoute: "formation-diagnostics", collapsed: true });
  assert.equal(classes.has("sidebar-collapsed"), true);
  assert.match(sidebar.innerHTML, /href="\/mrz\/formation-diagnostics"[^>]+aria-current="page"/);
  assert.match(sidebar.innerHTML, /href="\/mrz\/events"/);
  toggle.dispatch("click");
  assert.equal(classes.has("sidebar-collapsed"), false, "collapse button restores the sidebar");
  assert.equal(storageValues.get(SIDEBAR_STORAGE_KEY), "false");
  toggle.dispatch("click");
  assert.equal(classes.has("sidebar-collapsed"), true, "collapse button narrows the sidebar");
  assert.equal(storageValues.get(SIDEBAR_STORAGE_KEY), "true");
  mobile.dispatch("click");
  assert.equal(classes.has("nav-open"), true);
  routeLinks[7].dispatch("click");
  assert.equal(classes.has("nav-open"), false, "mobile route navigation closes the drawer");
}
