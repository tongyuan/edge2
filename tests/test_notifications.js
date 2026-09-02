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
  let focused = false;
  const existingClient = {
    url: "https://edge.example.test/",
    async navigate(url) { navigated.push(url); },
    async focus() { focused = true; },
  };
  const self = {
    location: { origin: "https://edge.example.test" },
    addEventListener(type, listener) { listeners[type] = listener; },
    skipWaiting() {},
    registration: {
      async showNotification(title, options) { shown.push({ title, options }); },
    },
    clients: {
      async claim() {},
      async matchAll() { return [existingClient]; },
      async openWindow() { throw new Error("existing EDGE window should be reused"); },
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

  let pushWork;
  listeners.push({
    data: {
      json() {
        return {
          event_id: "WLDUSDT:1:MRZ_ACTIVATED:event-4",
          event_type: "MRZ_ACTIVATED",
          title: "EDGE MRZ",
          body: "WLDUSDT · BTD MRZ activated\nShallow Discount · 0.3502–0.3541",
          symbol: "WLDUSDT",
          url: "/?symbol=WLDUSDT",
        };
      },
    },
    waitUntil(promise) { pushWork = promise; },
  });
  await pushWork;

  assert.equal(shown.length, 1);
  assert.equal(shown[0].title, "EDGE MRZ");
  assert.match(shown[0].options.body, /WLDUSDT · BTD MRZ activated/);
  assert.equal(shown[0].options.data.url, "/?symbol=WLDUSDT");
  assert.equal(shown[0].options.data.event_type, "MRZ_ACTIVATED");

  let migrationPushWork;
  listeners.push({
    data: {
      json() {
        return {
          event_id: "WLDUSDT:2:MRZ_MIGRATED:event-8",
          event_type: "MRZ_MIGRATED",
          title: "WLDUSDT MRZ Migrated",
          body: "BTD → STR · 0.3502–0.3541 → 0.4001–0.4042",
          symbol: "WLDUSDT",
          url: "/?symbol=WLDUSDT",
        };
      },
    },
    waitUntil(promise) { migrationPushWork = promise; },
  });
  await migrationPushWork;

  assert.equal(shown.length, 2);
  assert.equal(shown[1].title, "WLDUSDT MRZ Migrated");
  assert.equal(shown[1].options.data.event_type, "MRZ_MIGRATED");

  let clickWork;
  listeners.notificationclick({
    notification: {
      data: shown[0].options.data,
      close() {},
    },
    waitUntil(promise) { clickWork = promise; },
  });
  await clickWork;
  assert.deepEqual(navigated, ["https://edge.example.test/?symbol=WLDUSDT"]);
  assert.equal(focused, true);
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
