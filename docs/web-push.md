# MRZ activation Web Push

## Scope and authority boundary

Web Push is an operational output only. V1 consumes only an already-persisted
`MRZ_ACTIVATED` row:

```text
TradingView observation
  -> unchanged MRZ engine
  -> active_mrz + mrz_events commit
  -> notification background task re-reads persisted MRZ_ACTIVATED
  -> logical notification deduplication
  -> active Web Push subscriptions
```

The notification subsystem never evaluates concentration, qualification,
migration, successor state, route ownership, or structural authority. The
webhook response and MRZ commit do not depend on push delivery.

Migration `005_web_push_notifications.sql` is additive. It creates:

- `web_push_subscriptions` for endpoint/key material and delivery health;
- `web_push_notifications` for one logical notification per deterministic
  `mrz_events.event_key`;
- `web_push_delivery_attempts` for per-subscription outcomes.

The migration records existing `MRZ_ACTIVATED` event keys as non-deliverable.
This baseline prevents deployment, restart, or deterministic MRZ replay from
sending historical activations. It does not update `observations`, `active_mrz`,
or `mrz_events`.

## Configuration

Configure all three values together in the remote `.env`:

```text
WEB_PUSH_VAPID_PUBLIC_KEY=...
WEB_PUSH_VAPID_PRIVATE_KEY=...
WEB_PUSH_VAPID_SUBJECT=mailto:operator@example.com
```

The private key remains server-side. The config endpoint returns only the
public key. Do not commit generated keys and do not rotate them casually;
rotation invalidates existing browser subscriptions.

After building the application image, generate a new pair with:

```bash
docker compose build edge2-app
docker compose run --rm --no-deps edge2-app python3 scripts/generate_vapid_keys.py
```

Copy the three printed values into `/home/tony/edge2/.env`, replace the example
subject with the operator contact, and retain mode `600` on that file. The
utility prints keys but does not write them into the repository.

## API and browser flow

```text
GET    /api/notifications/config
POST   /api/notifications/subscriptions
DELETE /api/notifications/subscriptions
GET    /api/notifications/events?after=<logical-id>
```

The browser asks for notification permission only after the operator presses
`Enable MRZ Notifications`. It registers `/service-worker.js`, subscribes with
the public VAPID key, and persists the endpoint. The UI detects unsupported,
denied, subscribed, disabled, expired/revoked, and server-unconfigured states.
It does not repeat the permission prompt after denial.

Subscription payloads require an absolute HTTPS endpoint plus bounded
base64url `p256dh` and `auth` values. Duplicate endpoints are updated and
re-enabled. A 404 or 410 response from a push service permanently disables the
subscription; other failures are recorded without changing MRZ authority.
Endpoint/key material is not written to application logs.

V1 allows at most three delivery attempts per logical notification and
subscription. HTTP 404/410 expires the subscription, success is terminal, and
timeouts, network exceptions, HTTP 408/425/429, and HTTP 5xx remain retryable.
Other provider 4xx responses are recorded as non-retryable for that
notification without disabling the subscription. Retries retain the same
logical `source_event_key` and are resumed by a later webhook processing pass
or startup recovery; there is no tight retry loop and push work remains outside
the authoritative webhook transaction.

The in-site toast polls only logical notification records. It does not infer an
activation by comparing symbol state. The service worker has no `fetch` handler
and does not cache or intercept operational HTML or MRZ API responses.

## Payload and deep link

The compact JSON payload contains:

```json
{
  "version": 1,
  "event_type": "MRZ_ACTIVATED",
  "event_id": "WLDUSDT:1:MRZ_ACTIVATED:event-4",
  "title": "EDGE MRZ",
  "body": "WLDUSDT · BTD MRZ activated\nShallow Discount · 0.3502–0.3541",
  "symbol": "WLDUSDT",
  "route_owner": "BTD",
  "structural_location": "shallow_discount_core_mrz",
  "mrz_lower": "0.3502",
  "mrz_upper": "0.3541",
  "activated_at": "2026-08-20T12:00:04Z",
  "url": "/?symbol=WLDUSDT"
}
```

All MRZ fields are copied from the persisted activation event. The service
worker accepts only the existing same-origin `/` monitor route with a validated
symbol query. It focuses and navigates an existing EDGE window when possible,
or opens one new window. External or unexpected paths fall back to `/`.

## Deployment

Normal Git deployment remains unchanged:

```bash
make test
./scripts/deploy-remote.sh
```

Application startup applies migration `005` before Uvicorn starts. It is also
safe to run the existing explicit migration command:

```bash
make migrate
```

The ingress continues to inject the TradingView secret only for the exact
webhook path. It now also proxies the monitor, static/PWA assets, diagnostics,
and `/api/` routes through the existing HTTPS ngrok origin. The fallback route
still returns 404. HTTPS is mandatory for service workers and Web Push.

EDGE has no account/session layer. The notification API therefore follows the
existing single-operator access model. The stable URL must not be treated as a
credential; if wider URL exposure is possible, enforce an operator access
policy at the existing HTTPS edge without changing the app's Web Push origin.

## iPhone Home Screen verification

Use development/test data only; do not manufacture production MRZ authority.

1. Deploy the reviewed commit and VAPID environment values over the existing
   HTTPS origin.
2. On iPhone with iOS 16.4 or later, open the EDGE root URL in Safari.
3. Use Share -> Add to Home Screen, then launch `EDGE MRZ` from its icon.
4. Press `Enable MRZ Notifications` and allow notifications.
5. Verify one enabled row exists without selecting private key material:

   ```sql
   SELECT id, enabled, created_at, last_success_at, last_failure_at
   FROM web_push_subscriptions;
   ```

6. In a development/test environment, submit the exact observation sequence
   that produces one authoritative persisted `MRZ_ACTIVATED` event.
7. Put EDGE in the background and verify one iOS system notification appears.
8. Tap it and verify EDGE focuses/opens the correct `/?symbol=...` monitor
   detail.
9. Retry the confirming webhook event and restart the service. Confirm that no
   second logical notification or system alert is produced for that activation.

On iPhone/iPad, Web Push is available to Home Screen web apps on iOS/iPadOS
16.4 or later, and permission must be requested from a direct operator gesture.
Focus modes and per-app notification settings can suppress visible alerts.
Icon badge counts are intentionally deferred: V1 supplies notification badge
artwork but does not invent an unread count.
