const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const {
  enableWebPush,
  safeNotificationPath,
  supportsWebPush,
} = require("../app/static/notifications.js");

function fakeSubscription(endpoint = "https://push.example.test/device") {
  return {
    endpoint,
    toJSON() {
      return {
        endpoint,
        keys: { p256dh: "A".repeat(87), auth: "B".repeat(22) },
      };
    },
  };
}

async function testGrantedPermissionPath() {
  const subscription = fakeSubscription();
  const fetchCalls = [];
  let subscribedWith = null;
  const registration = {
    pushManager: {
      async getSubscription() { return null; },
      async subscribe(options) {
        subscribedWith = options;
        return subscription;
      },
    },
  };
  const result = await enableWebPush({
    navigatorObject: {
      serviceWorker: {
        async register(url, options) {
          assert.equal(url, "/service-worker.js");
          assert.deepEqual(options, { scope: "/" });
          return registration;
        },
      },
    },
    notificationObject: {
      permission: "default",
      async requestPermission() { return "granted"; },
    },
    async fetchImpl(url, options) {
      fetchCalls.push({ url, options });
      return { ok: true };
    },
    vapidPublicKey: "AAAA",
  });

  assert.equal(result.state, "subscribed");
  assert.equal(result.subscription, subscription);
  assert.equal(subscribedWith.userVisibleOnly, true);
  assert.ok(subscribedWith.applicationServerKey instanceof Uint8Array);
  assert.equal(fetchCalls.length, 1);
  assert.equal(fetchCalls[0].url, "/api/notifications/subscriptions");
  assert.equal(fetchCalls[0].options.method, "POST");
  assert.equal(JSON.parse(fetchCalls[0].options.body).endpoint, subscription.endpoint);
}

async function testDeniedPermissionPath() {
  let subscribeCalled = false;
  let fetchCalled = false;
  const result = await enableWebPush({
    navigatorObject: {
      serviceWorker: {
        async register() {
          return {
            pushManager: {
              async getSubscription() { return null; },
              async subscribe() {
                subscribeCalled = true;
                return fakeSubscription();
              },
            },
          };
        },
      },
    },
    notificationObject: {
      permission: "default",
      async requestPermission() { return "denied"; },
    },
    async fetchImpl() {
      fetchCalled = true;
      return { ok: true };
    },
    vapidPublicKey: "AAAA",
  });

  assert.equal(result.state, "denied");
  assert.equal(subscribeCalled, false);
  assert.equal(fetchCalled, false);
}

async function testExpiredSubscriptionIsRenewed() {
  let unsubscribed = false;
  const expired = {
    ...fakeSubscription("https://push.example.test/expired"),
    async unsubscribe() { unsubscribed = true; },
  };
  const renewed = fakeSubscription("https://push.example.test/renewed");
  let postCount = 0;
  const result = await enableWebPush({
    navigatorObject: {
      serviceWorker: {
        async register() {
          return {
            pushManager: {
              async getSubscription() { return expired; },
              async subscribe() { return renewed; },
            },
          };
        },
      },
    },
    notificationObject: { permission: "granted" },
    async fetchImpl() {
      postCount += 1;
      return postCount === 1 ? { ok: false, status: 410 } : { ok: true, status: 201 };
    },
    vapidPublicKey: "AAAA",
  });

  assert.equal(unsubscribed, true);
  assert.equal(postCount, 2);
  assert.equal(result.subscription, renewed);
}

async function testServiceWorkerPushAndClick() {
  const listeners = {};
  const shown = [];
  const navigated = [];
  const opened = [];
  let focusCount = 0;
  const existingClient = {
    url: "https://edge.example.test/diagnostics/activation-feasibility?symbol=OTHER",
    async navigate(url) { navigated.push(url); },
    async focus() { focusCount += 1; },
  };
  let currentClients = [existingClient];
  const self = {
    location: { origin: "https://edge.example.test" },
    addEventListener(type, listener) { listeners[type] = listener; },
    skipWaiting() {},
    registration: {
      async showNotification(title, options) { shown.push({ title, options }); },
    },
    clients: {
      async claim() {},
      async matchAll() { return currentClients; },
      async openWindow(url) { opened.push(url); },
    },
  };
  const source = fs.readFileSync(
    path.join(__dirname, "../app/static/service-worker.js"),
    "utf8",
  );
  const context = { self, URL, encodeURIComponent };
  vm.runInNewContext(source, context);

  assert.equal(typeof listeners.push, "function");
  assert.equal(typeof listeners.notificationclick, "function");
  assert.equal(listeners.fetch, undefined, "worker must not cache or intercept MRZ API reads");

  async function push(payload) {
    let work;
    listeners.push({
      data: { json() { return payload; } },
      waitUntil(promise) { work = promise; },
    });
    await work;
    return shown[shown.length - 1];
  }

  async function click(notification) {
    let work;
    listeners.notificationclick({
      notification: { data: notification.options.data, close() {} },
      waitUntil(promise) { work = promise; },
    });
    await work;
  }

  const activation = await push({
    event_id: "BTCUSDT:1:MRZ_ACTIVATED:event-4",
    event_type: "MRZ_ACTIVATED",
    title: "BTCUSDT MRZ Activated",
    body: "BTD · 77,309.19–77,436.91",
    symbol: "BTCUSDT",
    destination: "/diagnostics/mrz-robustness?symbol=BTCUSDT#active-mrz",
    url: "/diagnostics/mrz-robustness?symbol=BTCUSDT#active-mrz",
  });
  assert.equal(activation.options.data.event_type, "MRZ_ACTIVATED");
  assert.equal(
    activation.options.data.destination,
    "/diagnostics/mrz-robustness?symbol=BTCUSDT#active-mrz",
  );

  const migration = await push({
    event_id: "BTCUSDT:2:MRZ_MIGRATED:event-8",
    event_type: "MRZ_MIGRATED",
    title: "BTCUSDT MRZ Migrated",
    body: "BTD · 77,309.19–77,436.91 → 78,919.34–79,030",
    symbol: "BTCUSDT",
    destination: "/diagnostics/mrz-robustness?symbol=BTCUSDT#migration-history",
  });
  assert.equal(migration.options.data.event_type, "MRZ_MIGRATED");
  assert.equal(
    migration.options.data.destination,
    "/diagnostics/mrz-robustness?symbol=BTCUSDT#migration-history",
  );

  const candidateIdentity = "a".repeat(64);
  const nearMissDestination = `/diagnostics/activation-feasibility?symbol=RGTI&candidate=${candidateIdentity}#current-production-near-misses`;
  const nearMiss = await push({
    event_id: `near-miss:RGTI:STR:${candidateIdentity}`,
    event_type: "MRZ_NEAR_MISS",
    title: "RGTI MRZ Near Miss",
    body: "STR · 1.02% required · 1.00% production threshold",
    symbol: "RGTI",
    candidate_identity: candidateIdentity,
    destination: nearMissDestination,
  });
  assert.equal(nearMiss.options.data.event_type, "MRZ_NEAR_MISS");
  assert.equal(nearMiss.options.data.destination, nearMissDestination);

  const pressure = await push({
    event_id: "POST_ACTIVATION_PRESSURE_CHANGED:ZECUSDT:event-4:event-6:DOWN",
    event_type: "POST_ACTIVATION_PRESSURE_CHANGED",
    title: "ZECUSDT · Downward Pressure",
    body: "Post-activation activity materially favors below-envelope observations",
    symbol: "ZECUSDT",
    destination: "/diagnostics/mrz-robustness?symbol=ZECUSDT#post-activation",
  });
  assert.equal(shown.length, 4);
  assert.equal(
    pressure.options.data.event_type,
    "POST_ACTIVATION_PRESSURE_CHANGED",
  );
  assert.equal(
    pressure.options.data.destination,
    "/diagnostics/mrz-robustness?symbol=ZECUSDT#post-activation",
  );

  await click(activation);
  await click(migration);
  await click(pressure);
  await click(nearMiss);
  assert.deepEqual(navigated, [
    "https://edge.example.test/diagnostics/mrz-robustness?symbol=BTCUSDT#active-mrz",
    "https://edge.example.test/diagnostics/mrz-robustness?symbol=BTCUSDT#migration-history",
    "https://edge.example.test/diagnostics/mrz-robustness?symbol=ZECUSDT#post-activation",
    `https://edge.example.test${nearMissDestination}`,
  ]);
  assert.equal(focusCount, 4, "the existing EDGE client is focused after navigation");

  currentClients = [];
  await click(pressure);
  assert.equal(
    opened[0],
    "https://edge.example.test/diagnostics/mrz-robustness?symbol=ZECUSDT#post-activation",
    "a cold launch opens the exact destination",
  );

  const legacy = await push({
    event_id: "legacy",
    event_type: "MRZ_ACTIVATED",
    symbol: "BTCUSDT",
    url: "/?symbol=BTCUSDT",
  });
  assert.equal(legacy.options.data.destination, "/");
  await click(legacy);
  assert.equal(opened[1], "https://edge.example.test/");

  const external = await push({
    event_id: "invalid-external",
    event_type: "MRZ_ACTIVATED",
    symbol: "BTCUSDT",
    destination: "https://attacker.example/phish",
  });
  assert.equal(external.options.data.destination, "/");
  await click(external);
  assert.equal(opened[2], "https://edge.example.test/");
  assert.equal(context.safeNotificationPath("https://attacker.example/phish"), "/");
}

async function main() {
  assert.equal(supportsWebPush({
    navigator: { serviceWorker: {} },
    PushManager: function PushManager() {},
    Notification: function Notification() {},
  }), true);
  assert.equal(supportsWebPush({ navigator: {} }), false);
  assert.equal(
    safeNotificationPath("/?symbol=WLDUSDT", "https://edge.example.test"),
    "/?symbol=WLDUSDT",
  );
  assert.equal(
    safeNotificationPath(
      "/diagnostics/mrz-robustness?symbol=WLDUSDT#post-activation",
      "https://edge.example.test",
    ),
    "/diagnostics/mrz-robustness?symbol=WLDUSDT#post-activation",
  );
  assert.equal(
    safeNotificationPath(
      "/diagnostics/mrz-robustness?symbol=WLDUSDT#active-mrz",
      "https://edge.example.test",
    ),
    "/diagnostics/mrz-robustness?symbol=WLDUSDT#active-mrz",
  );
  assert.equal(
    safeNotificationPath(
      "/diagnostics/mrz-robustness?symbol=WLDUSDT#migration-history",
      "https://edge.example.test",
    ),
    "/diagnostics/mrz-robustness?symbol=WLDUSDT#migration-history",
  );
  assert.equal(
    safeNotificationPath(
      "/diagnostics/mrz-robustness?symbol=WLDUSDT#unknown",
      "https://edge.example.test",
    ),
    "/",
  );
  assert.equal(
    safeNotificationPath(
      `/diagnostics/activation-feasibility?symbol=WLDUSDT&candidate=${"a".repeat(64)}#current-production-near-misses`,
      "https://edge.example.test",
    ),
    `/diagnostics/activation-feasibility?symbol=WLDUSDT&candidate=${"a".repeat(64)}#current-production-near-misses`,
  );
  assert.equal(
    safeNotificationPath(
      "/diagnostics/activation-feasibility?symbol=WLDUSDT&candidate=bad",
      "https://edge.example.test",
    ),
    "/",
  );
  assert.equal(
    safeNotificationPath("https://attacker.example/phish", "https://edge.example.test"),
    "/",
  );
  await testGrantedPermissionPath();
  await testDeniedPermissionPath();
  await testExpiredSubscriptionIsRenewed();
  await testServiceWorkerPushAndClick();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
