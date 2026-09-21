(function initializeEdgeNotifications(globalObject) {
  const REQUESTED_STORAGE_KEY = "edgeMRZNotificationsRequested";
  const SYMBOL_PATTERN = /^[A-Z0-9][A-Z0-9:._-]{0,39}$/;
  const CANDIDATE_PATTERN = /^[a-f0-9]{64}$/;
  const OPERATOR_CARD_SECTIONS = new Set([
    "active-mrz",
    "migration-history",
    "post-activation",
  ]);

  function supportsWebPush(environment = globalObject) {
    return Boolean(
      environment.navigator?.serviceWorker
      && environment.PushManager
      && environment.Notification,
    );
  }

  function urlBase64ToUint8Array(value) {
    const padding = "=".repeat((4 - (value.length % 4)) % 4);
    const base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = globalObject.atob(base64);
    return Uint8Array.from([...raw].map((character) => character.charCodeAt(0)));
  }

  function subscriptionPayload(subscription) {
    const value = subscription.toJSON();
    return {
      endpoint: value.endpoint,
      keys: {
        p256dh: value.keys.p256dh,
        auth: value.keys.auth,
      },
    };
  }

  function safeNotificationPath(candidate, origin = globalObject.location?.origin) {
    try {
      const parsed = new URL(typeof candidate === "string" ? candidate : "/", origin);
      if (parsed.origin !== origin) return "/";
      const symbol = parsed.searchParams.get("symbol");
      if (!symbol || !SYMBOL_PATTERN.test(symbol)) return "/";
      if (parsed.pathname === "/") return `/?symbol=${encodeURIComponent(symbol)}`;
      if (parsed.pathname === "/diagnostics/mrz-robustness") {
        const section = parsed.hash.startsWith("#") ? parsed.hash.slice(1) : "";
        if (!OPERATOR_CARD_SECTIONS.has(section)) return "/";
        return `/diagnostics/mrz-robustness?symbol=${encodeURIComponent(symbol)}#${section}`;
      }
      if (parsed.pathname !== "/diagnostics/activation-feasibility") return "/";
      const candidateIdentity = parsed.searchParams.get("candidate");
      if (!candidateIdentity || !CANDIDATE_PATTERN.test(candidateIdentity)) return "/";
      return `/diagnostics/activation-feasibility?symbol=${encodeURIComponent(symbol)}&candidate=${encodeURIComponent(candidateIdentity)}#current-production-near-misses`;
    } catch {
      return "/";
    }
  }

  function formatNotificationTimestamp(value, formatter = null) {
    const resolvedFormatter = formatter || (
      typeof formatOperatorTimestampUtcMinus4 === "function"
        ? formatOperatorTimestampUtcMinus4
        : null
    );
    return resolvedFormatter?.(value) || "Time unavailable";
  }

  async function persistSubscription(subscription, fetchImpl) {
    const response = await fetchImpl("/api/notifications/subscriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(subscriptionPayload(subscription)),
    });
    if (response.status === 410) {
      const error = new Error("The previous subscription expired and must be renewed.");
      error.code = "subscription_expired";
      throw error;
    }
    if (!response.ok) throw new Error("EDGE could not save this notification subscription.");
  }

  async function enableWebPush({
    navigatorObject,
    notificationObject,
    fetchImpl,
    vapidPublicKey,
  }) {
    const registration = await navigatorObject.serviceWorker.register(
      "/service-worker.js",
      { scope: "/" },
    );
    const permission = notificationObject.permission === "granted"
      ? "granted"
      : await notificationObject.requestPermission();
    if (permission !== "granted") return { state: permission };

    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
      });
    }
    try {
      await persistSubscription(subscription, fetchImpl);
    } catch (error) {
      if (error.code !== "subscription_expired") throw error;
      await subscription.unsubscribe();
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
      });
      await persistSubscription(subscription, fetchImpl);
    }
    return { state: "subscribed", subscription };
  }

  async function disableWebPush({ subscription, fetchImpl }) {
    const endpoint = subscription.endpoint;
    const response = await fetchImpl("/api/notifications/subscriptions", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint }),
    });
    if (!response.ok) throw new Error("EDGE could not disable this notification subscription.");
    await subscription.unsubscribe();
    return { state: "disabled" };
  }

  class NotificationController {
    constructor() {
      this.button = document.querySelector("#notificationButton");
      this.status = document.querySelector("#notificationStatus");
      this.toastHost = document.querySelector("#notificationToastHost");
      this.inboxButton = document.querySelector("#notificationInboxButton");
      this.unreadBadge = document.querySelector("#notificationUnreadBadge");
      this.inboxDialog = document.querySelector("#notificationInboxDialog");
      this.inboxClose = document.querySelector("#notificationInboxClose");
      this.inboxSummary = document.querySelector("#notificationInboxSummary");
      this.inboxEmpty = document.querySelector("#notificationInboxEmpty");
      this.inboxList = document.querySelector("#notificationInboxList");
      this.clearReadButton = document.querySelector("#notificationClearRead");
      this.config = null;
      this.subscription = null;
      this.cursor = 0;
      this.pollTimer = null;
    }

    render(state, detail) {
      this.status.textContent = detail;
      this.status.dataset.state = state;
      this.button.dataset.state = state;
      const states = {
        unsupported: ["Notifications unsupported", true],
        unavailable: ["Notifications unavailable", true],
        denied: ["Notifications blocked", true],
        subscribed: ["Disable MRZ Notifications", false],
        expired: ["Re-enable MRZ Notifications", false],
        working: ["Working…", true],
        error: ["Try MRZ Notifications Again", false],
        ready: ["Enable MRZ Notifications", false],
      };
      const [label, disabled] = states[state] || states.ready;
      this.button.textContent = label;
      this.button.disabled = disabled;
    }

    requestedBefore() {
      try {
        return globalObject.localStorage.getItem(REQUESTED_STORAGE_KEY) === "true";
      } catch {
        return false;
      }
    }

    rememberRequested() {
      try {
        globalObject.localStorage.setItem(REQUESTED_STORAGE_KEY, "true");
      } catch {
        // Local storage is optional; PushManager remains authoritative.
      }
    }

    async loadConfig() {
      const response = await fetch("/api/notifications/config", { cache: "no-store" });
      if (!response.ok) throw new Error("Notification configuration is unavailable.");
      this.config = await response.json();
      this.cursor = Number(this.config.latest_notification_id) || 0;
    }

    async initialize() {
      this.button.addEventListener("click", () => this.toggle());
      this.inboxButton.addEventListener("click", () => {
        this.openInbox().catch(() => this.showInboxError());
      });
      this.inboxClose.addEventListener("click", () => this.inboxDialog.close());
      this.clearReadButton.addEventListener("click", () => {
        this.clearRead().catch(() => this.showInboxError());
      });
      try {
        await this.refreshInbox();
      } catch {
        this.showInboxError();
      }
      try {
        await this.loadConfig();
      } catch (error) {
        this.render("unavailable", error.message);
        return;
      }
      this.startEventPolling();
      if (!supportsWebPush()) {
        this.render("unsupported", "This browser cannot use Web Push.");
        return;
      }
      if (!this.config.supported || !this.config.vapid_public_key) {
        this.render("unavailable", "The EDGE server has not enabled Web Push yet.");
        return;
      }
      if (Notification.permission === "denied") {
        this.render("denied", "Permission is blocked in browser settings.");
        return;
      }

      const registration = await navigator.serviceWorker.getRegistration("/");
      this.subscription = registration
        ? await registration.pushManager.getSubscription()
        : null;
      if (this.subscription) {
        try {
          await persistSubscription(this.subscription, fetch.bind(globalObject));
          this.rememberRequested();
          this.render("subscribed", "MRZ pressure, near-miss, activation and migration alerts are enabled on this device.");
        } catch (error) {
          if (error.code === "subscription_expired") {
            await this.subscription.unsubscribe();
            this.subscription = null;
            this.rememberRequested();
            this.render("expired", "The previous subscription expired or was revoked.");
          } else {
            this.render("error", error.message);
          }
        }
        return;
      }
      if (Notification.permission === "granted" && this.requestedBefore()) {
        this.render("expired", "The previous subscription expired or was revoked.");
      } else {
        this.render("ready", "Alerts are off until you enable them.");
      }
    }

    async toggle() {
      this.render("working", "Updating notification settings…");
      try {
        if (this.subscription) {
          await disableWebPush({
            subscription: this.subscription,
            fetchImpl: fetch.bind(globalObject),
          });
          this.subscription = null;
          this.render("ready", "MRZ pressure, near-miss, activation and migration alerts are off on this device.");
          return;
        }
        const result = await enableWebPush({
          navigatorObject: navigator,
          notificationObject: Notification,
          fetchImpl: fetch.bind(globalObject),
          vapidPublicKey: this.config.vapid_public_key,
        });
        if (result.state === "denied") {
          this.render("denied", "Permission is blocked in browser settings.");
          return;
        }
        if (result.state !== "subscribed") {
          this.render("ready", "Permission was not granted; alerts remain off.");
          return;
        }
        this.subscription = result.subscription;
        this.rememberRequested();
        this.render("subscribed", "MRZ pressure, near-miss, activation and migration alerts are enabled on this device.");
      } catch (error) {
        this.render("error", error.message || "Unable to update notifications.");
      }
    }

    startEventPolling() {
      this.pollTimer = globalObject.setInterval(() => {
        if (document.visibilityState === "visible") this.pollEvents();
      }, 20000);
    }

    async pollEvents() {
      try {
        const response = await fetch(
          `/api/notifications/events?after=${encodeURIComponent(this.cursor)}`,
          { cache: "no-store" },
        );
        if (!response.ok) return;
        const payload = await response.json();
        payload.events.forEach((event) => this.showToast(event));
        this.cursor = Math.max(
          this.cursor,
          Number(payload.latest_notification_id) || 0,
          ...payload.events.map((event) => Number(event.id) || 0),
        );
        if (payload.events.length > 0) await this.refreshInbox();
      } catch {
        // The system notification path is independent; a failed toast poll is quiet.
      }
    }

    showToast(event) {
      const toast = document.createElement("article");
      toast.className = "notification-toast";
      const copy = document.createElement("div");
      const title = document.createElement("strong");
      title.textContent = event.title || "EDGE MRZ";
      const body = document.createElement("p");
      body.textContent = event.body || "An authoritative MRZ changed.";
      copy.append(title, body);
      const link = document.createElement("a");
      link.href = safeNotificationPath(event.destination);
      link.textContent = "Open symbol";
      toast.append(copy, link);
      this.toastHost.append(toast);
      globalObject.setTimeout(() => toast.remove(), 12000);
    }

    async openInbox() {
      await this.refreshInbox().catch(() => {
        this.showInboxError();
      });
      if (!this.inboxDialog.open) this.inboxDialog.showModal();
    }

    async refreshInbox() {
      const response = await fetch("/api/notifications/inbox?limit=50", {
        cache: "no-store",
      });
      if (!response.ok) throw new Error("Notification Inbox is unavailable.");
      this.renderInbox(await response.json());
    }

    renderInbox(payload) {
      const items = Array.isArray(payload.items) ? payload.items : [];
      const unreadCount = Number(payload.unread_count) || 0;
      const readCount = Number(payload.read_count) || 0;
      this.unreadBadge.textContent = unreadCount > 99 ? "99+" : String(unreadCount);
      this.unreadBadge.hidden = unreadCount === 0;
      this.inboxButton.setAttribute(
        "aria-label",
        unreadCount === 1
          ? "Notification Inbox, 1 unread notification"
          : `Notification Inbox, ${unreadCount} unread notifications`,
      );
      this.inboxSummary.textContent = unreadCount === 1
        ? "1 unread notification"
        : `${unreadCount} unread notifications`;
      this.inboxEmpty.hidden = items.length > 0;
      this.clearReadButton.disabled = readCount === 0;
      this.inboxList.replaceChildren(...items.map((item) => this.inboxItem(item)));
    }

    inboxItem(item) {
      const row = document.createElement("li");
      row.className = `notification-inbox-item${item.is_read ? "" : " unread"}`;
      const heading = document.createElement("div");
      heading.className = "notification-inbox-item-heading";
      const identity = document.createElement("div");
      identity.className = "notification-inbox-item-identity";
      const symbol = document.createElement("strong");
      symbol.textContent = item.symbol || "EDGE";
      const readState = document.createElement("span");
      readState.className = "notification-inbox-item-state";
      readState.textContent = item.is_read ? "Read" : "Unread";
      const timestamp = document.createElement("time");
      timestamp.className = "notification-inbox-item-time";
      timestamp.dateTime = item.occurred_at || "";
      timestamp.textContent = formatNotificationTimestamp(item.occurred_at);
      identity.append(symbol, readState);
      heading.append(identity, timestamp);
      const eventName = document.createElement("p");
      eventName.className = "notification-inbox-item-name";
      eventName.textContent = item.event_name || "EDGE Notification";
      const body = document.createElement("p");
      body.className = "notification-inbox-item-body";
      body.textContent = item.body || "An EDGE event occurred.";
      const actions = document.createElement("div");
      actions.className = "notification-inbox-item-actions";
      const open = document.createElement("a");
      const destination = safeNotificationPath(item.destination);
      open.href = destination;
      open.textContent = "Open context";
      open.addEventListener("click", (event) => {
        event.preventDefault();
        this.openItem(item.id, destination);
      });
      const dismiss = document.createElement("button");
      dismiss.type = "button";
      dismiss.textContent = "Dismiss";
      dismiss.addEventListener("click", () => {
        this.dismissItem(item.id).catch(() => this.showInboxError());
      });
      actions.append(open, dismiss);
      row.append(heading, eventName, body, actions);
      return row;
    }

    async openItem(notificationId, destination) {
      try {
        await this.mutateInbox(`/api/notifications/inbox/${notificationId}/read`);
      } catch {
        // An uncertain write remains unread, but the canonical deep link still opens.
      } finally {
        this.inboxDialog.close();
        globalObject.location.assign(destination);
      }
    }

    async dismissItem(notificationId) {
      await this.mutateInbox(`/api/notifications/inbox/${notificationId}/dismiss`);
      await this.refreshInbox();
    }

    async clearRead() {
      await this.mutateInbox("/api/notifications/inbox/clear-read");
      await this.refreshInbox();
    }

    async mutateInbox(url) {
      const response = await fetch(url, { method: "POST" });
      if (!response.ok) throw new Error("Notification state could not be updated.");
      return response.json();
    }

    showInboxError() {
      this.inboxSummary.textContent = "Inbox temporarily unavailable";
    }
  }

  const exported = {
    NotificationController,
    disableWebPush,
    enableWebPush,
    formatNotificationTimestamp,
    safeNotificationPath,
    subscriptionPayload,
    supportsWebPush,
    urlBase64ToUint8Array,
  };
  globalObject.edgeNotifications = exported;

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", () => {
      const button = document.querySelector("#notificationButton");
      if (button) new NotificationController().initialize();
    });
  }

  if (typeof module === "object" && module.exports) module.exports = exported;
}(globalThis));
