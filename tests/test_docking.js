"use strict";

const assert = require("node:assert/strict");

const opened = [];
const saved = new Map();
class FakeElement {
  constructor(tag) { this.tag = tag; this.attributes = {}; this.children = []; this.classNames = []; this.classList = { add: (...names) => this.classNames.push(...names) }; }
  setAttribute(name, value) { this.attributes[name] = value; }
  replaceChildren(...children) { this.children = children; }
  append(...children) { this.children.push(...children); }
}
global.screen = { availWidth: 1600, availHeight: 1000 };
global.innerWidth = 1200;
global.location = { origin: "https://edge.example.test", pathname: "/mrz/watchlists", search: "?group=AI", hash: "" };
global.localStorage = { getItem: (key) => saved.get(key) || null, setItem: (key, value) => saved.set(key, value) };
global.matchMedia = () => ({ matches: false });
global.open = (url, name, features) => {
  const item = { url, name, features, focused: false, focus() { this.focused = true; } };
  opened.push(item);
  return item;
};
global.addEventListener = () => {};
global.document = {
  createElement: (tag) => new FakeElement(tag),
  createElementNS: (_namespace, tag) => new FakeElement(tag),
};

const docking = require("../app/static/docking.js");

assert.equal(docking.canDock(), true);
const dockButton = docking.createDockButton("Dock Opportunity Map");
assert.deepEqual(dockButton.classNames, ["opportunity-dock-button", "dock-icon-button"]);
assert.equal(dockButton.attributes["aria-label"], "Dock Opportunity Map");
assert.equal(dockButton.title, "Dock Opportunity Map");
assert.equal(dockButton.children[0].tag, "svg");
assert.equal(dockButton.children[0].attributes["aria-hidden"], "true");
assert.equal(docking.dockUrl("inbox"), "/dock/inbox");
assert.equal(
  docking.dockUrl("opportunity-map", { symbol: "aapl", rangeDays: 90, returnUrl: "/mrz/watchlists?group=AI" }),
  "/dock/opportunity-map/AAPL?range=90&return=%2Fmrz%2Fwatchlists%3Fgroup%3DAI",
);
assert.equal(
  docking.dockUrl("opportunity-map", {
    symbol: "aapl", rangeDays: 90, viewStart: 100, viewEnd: 200, selectedEventId: "canonical:event:1",
    returnUrl: "/mrz/watchlists?group=AI",
  }),
  "/dock/opportunity-map/AAPL?range=90&view_start=100&view_end=200&event=canonical%3Aevent%3A1&return=%2Fmrz%2Fwatchlists%3Fgroup%3DAI",
);
assert.equal(
  docking.dockUrl("migration-path", { symbol: "nbis", returnUrl: "/mrz/watchlists?group=AI" }),
  "/mrz/symbols?symbol=NBIS&focus=migration-path&chart_only=1&return=%2Fmrz%2Fwatchlists%3Fgroup%3DAI",
);

docking.writeSize("inbox", 505, 805);
assert.deepEqual(docking.readSize("inbox"), { width: 505, height: 805 });

const mapWindow = docking.openOpportunityMap("NVDA", { rangeDays: 30 });
assert.equal(mapWindow.name, "edge-opportunity-map-dock");
assert.equal(mapWindow.url, "/dock/opportunity-map/NVDA?range=30");
assert.equal(mapWindow.focused, true);
assert.match(mapWindow.features, /width=1120/);

const inboxWindow = docking.openInbox();
assert.equal(inboxWindow.name, "edge-inbox-dock");
assert.equal(inboxWindow.focused, true);

const migrationWindow = docking.openMigrationPath("NBIS");
assert.equal(migrationWindow.name, "edge-migration-path-dock");
assert.equal(migrationWindow.url, "/mrz/symbols?symbol=NBIS&focus=migration-path&chart_only=1");

assert.equal(
  docking.dockUrl("migration-path", { symbol: "NBIS", windowStart: 4, windowSize: 6, selectedEventId: "NBIS:7" }),
  "/mrz/symbols?symbol=NBIS&focus=migration-path&chart_only=1&migration_start=4&migration_size=6&migration_event=NBIS%3A7",
  "migration docking preserves the viewport and selected canonical state",
);

console.log("Docking tests passed");
