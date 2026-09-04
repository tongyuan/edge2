const EDGE_ORIGIN = self.location.origin;
const SYMBOL_PATTERN = /^[A-Z0-9][A-Z0-9:._-]{0,39}$/;
const CANDIDATE_PATTERN = /^[a-f0-9]{64}$/;

function safeNotificationPath(candidate) {
  try {
    const parsed = new URL(typeof candidate === "string" ? candidate : "/", EDGE_ORIGIN);
    if (parsed.origin !== EDGE_ORIGIN) return "/";
    const symbol = parsed.searchParams.get("symbol");
    if (!symbol || !SYMBOL_PATTERN.test(symbol)) return "/";
    if (parsed.pathname === "/") return `/?symbol=${encodeURIComponent(symbol)}`;
    if (parsed.pathname !== "/diagnostics/activation-feasibility") return "/";
    const candidateIdentity = parsed.searchParams.get("candidate");
    if (!candidateIdentity || !CANDIDATE_PATTERN.test(candidateIdentity)) return "/";
    return `/diagnostics/activation-feasibility?symbol=${encodeURIComponent(symbol)}&candidate=${encodeURIComponent(candidateIdentity)}#current-production-near-misses`;
  } catch {
    return "/";
  }
}

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = {};
  }
  const eventId = typeof payload.event_id === "string" ? payload.event_id : "unknown";
  const eventType = ["MRZ_ACTIVATED", "MRZ_MIGRATED", "MRZ_NEAR_MISS"].includes(payload.event_type)
    ? payload.event_type
    : null;
  const url = safeNotificationPath(payload.url);
  event.waitUntil(self.registration.showNotification(payload.title || "EDGE MRZ", {
    body: payload.body || "An authoritative MRZ changed.",
    icon: "/static/edge-mrz-icon-192.png",
    badge: "/static/edge-mrz-icon-192.png",
    tag: `edge-mrz:${eventId}`,
    renotify: false,
    data: {
      event_id: eventId,
      event_type: eventType,
      symbol: typeof payload.symbol === "string" ? payload.symbol : null,
      url,
    },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const path = safeNotificationPath(event.notification.data?.url);
  const targetUrl = new URL(path, EDGE_ORIGIN).href;
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    const existing = windows.find((client) => {
      try {
        return new URL(client.url).origin === EDGE_ORIGIN;
      } catch {
        return false;
      }
    });
    if (existing) {
      if (typeof existing.navigate === "function") await existing.navigate(targetUrl);
      return existing.focus();
    }
    return self.clients.openWindow(targetUrl);
  })());
});
