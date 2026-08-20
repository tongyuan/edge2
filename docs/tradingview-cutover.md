# TradingView cutover contract

The deployed EDGE 2.0 runtime does not alter an existing TradingView alert or the current EDGE 4.2 public webhook route. Cutover is a deliberate operator action after verification.

## Endpoint isolation

Use a new high-entropy public path that proxies only to:

```text
http://127.0.0.1:8792/webhook/tradingview
```

Do not reuse the 4.2 path. Keep `WEBHOOK_SECRET` independent from the public path token. TradingView should include `webhook_secret` in the JSON body because it cannot be assumed to set a custom header.

## Alert body

BTD:

```json
{
  "schema_version": "4.3",
  "event_id": "{{ticker}}-BTD-{{time}}-{{close}}",
  "symbol": "{{ticker}}",
  "route": "BTD",
  "observation_type": "reclaim",
  "observation_price": {{close}},
  "ipda_20w_high": <indicator 20W high value>,
  "ipda_20w_low": <indicator 20W low value>,
  "observed_at": "<canonical RFC 3339 timestamp>",
  "webhook_secret": "<EDGE 2.0 deployment secret>"
}
```

STR mirrors this with route `STR` and observation type `rejection`.

The alert producer must guarantee a stable, unique event ID for the same logical observation across TradingView retries. Timestamp and price alone may collide; include stable bar/route identity available to the Pine script.

## Staged verification

1. Verify remote loopback `/health` and an empty clean database.
2. Send synthetic BTD and STR schema 4.3 packets to the loopback endpoint using the remote secret; verify validation, duplicate no-op, and WHO/WHERE API state.
3. Add a new Tailscale Funnel path without changing the existing 4.2 handler.
4. Create a separate TradingView canary alert targeting the new path. Do not edit the existing alert.
5. Confirm accepted counts, rejection/duplicate counts, latest timestamp, symbol normalization, and expected deterministic examples.
6. Explicitly approve production-alert changes outside this deployment workflow.
7. Keep 4.2 independently recoverable until the observation window and active MRZ state are verified.

## Rollback

Point only the newly created EDGE 2.0 canary alert away from the new route or disable that canary. The existing EDGE 4.2 alert and route remain the fallback because this build never modified them.

## Forbidden automatic actions

Deployment scripts must not edit TradingView alerts, replace the existing Funnel handler, stop 4.2 ingestion, reuse the 4.2 database, or copy 4.2 records into EDGE 2.0.
