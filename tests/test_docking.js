"use strict";

const assert = require("node:assert/strict");

const opened = [];
const saved = new Map();
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

const docking = require("../app/static/docking.js");

assert.equal(docking.canDock(), true);
assert.equal(docking.dockUrl("inbox"), "/dock/inbox");
assert.equal(
  docking.dockUrl("opportunity-map", { symbol: "aapl", rangeDays: 90, returnUrl: "/mrz/watchlists?group=AI" }),
  "/dock/opportunity-map/AAPL?range=90&return=%2Fmrz%2Fwatchlists%3Fgroup%3DAI",
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

console.log("Docking tests passed");
