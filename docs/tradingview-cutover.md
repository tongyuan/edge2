# TradingView cutover contract

The deployed EDGE 2.0 runtime does not alter an existing TradingView alert or the current EDGE 4.2 public webhook route. Cutover is a deliberate operator action after verification.

## Endpoint isolation

Use a new high-entropy public path that proxies only to:

```text
http://127.0.0.1:8792/webhook/tradingview
```

Do not reuse the 4.2 path. Keep `WEBHOOK_SECRET` independent from the public path token. The public reverse proxy must inject `X-EDGE2-Webhook-Secret` when it forwards the new high-entropy EDGE 2.0 path to the loopback endpoint. TradingView then sends the exact minimal schema 4.3 body without carrying a credential in the observation contract.

## Pine source and exact alert body

Copy `pine/EDGE_2_ROUTE.pine` into a new TradingView Pine Editor script named
`EDGE_2_ROUTE`. Its two operational branches construct these bodies directly;
do not paste a separate message template into the alert.

BTD:

```json
{
  "schema_version": "4.3",
  "event_id": "BINANCE:BTCUSDT|4.3|BTD|reclaim|1767225660000",
  "symbol": "BTCUSDT",
  "route": "BTD",
  "observation_type": "reclaim",
  "observation_price": 91234.5,
  "ipda_20w_high": 108000.0,
  "ipda_20w_low": 49000.0,
  "observed_at": "2026-01-01T00:01:00Z"
}
```

STR mirrors this with route `STR` and observation type `rejection`.

The script builds event identity from exchange-qualified symbol, schema, route,
observation type, and confirmed trigger `time_close`. It sends the exact close
and IPDA values at minimum-tick precision.

## Manual TradingView cutover

1. Open Pine Editor, create a new script named `EDGE_2_ROUTE`, paste the complete
   contents of `pine/EDGE_2_ROUTE.pine`, save it, and confirm Pine v6 compilation.
2. Apply it to the same 1-minute chart used for the 4.2 route emitter. Do not
   remove the 4.2 script or edit its alerts.
3. Compare the EQM20, EQM20 +1/-1, arm, first dip/rip, and reclaim/reject output
   against 4.2. Compare the current 20-week high/low against the chart's existing
   IPDA structural context; the first canary payload will expose the exact values
   captured by the observation builder.
4. Create the BTD alert: in the script inputs enable BTD emission, disable STR
   emission, select **Any alert() function call**, choose **Once Per Bar Close**,
   and leave the alert message unchanged.
5. Create the STR alert from a separate input snapshot: disable BTD emission,
   enable STR emission, and use the same alert condition/frequency.
6. Give both new alerts only the isolated EDGE 2.0 public webhook URL. The proxy
   for that URL must forward to `127.0.0.1:8792/webhook/tradingview` and inject
   the independent `X-EDGE2-Webhook-Secret`; it must not change the 4.2 handler.
7. Observe the first real BTD reclaim and STR rejection. Confirm that each alert
   posts one nine-field schema 4.3 JSON object and receives a successful response.
8. Verify accepted counts and the symbol in EDGE 2.0 Symbol Lab/API. Confirm the
   stored observation price, IPDA high/low, and observed time match TradingView.
9. Retire the old 4.2 alerts manually only after both routes pass this validation
   and EDGE 2.0 state survives a service restart.

## Staged verification

1. Verify remote loopback `/health` and an empty clean database.
2. Send synthetic BTD and STR schema 4.3 packets to the loopback endpoint using the remote secret; verify validation, duplicate no-op, and WHO/WHERE API state.
3. Add a new Tailscale Funnel path without changing the existing 4.2 handler.
4. Create separate BTD and STR TradingView canary alerts targeting the new path. Do not edit the existing alerts.
5. Confirm accepted counts, rejection/duplicate counts, latest timestamp, symbol normalization, and expected deterministic examples.
6. Explicitly approve production-alert changes outside this deployment workflow.
7. Keep 4.2 independently recoverable until the observation window and active MRZ state are verified.

## Rollback

Point only the newly created EDGE 2.0 canary alert away from the new route or disable that canary. The existing EDGE 4.2 alert and route remain the fallback because this build never modified them.

## Forbidden automatic actions

Deployment scripts must not edit TradingView alerts, replace the existing Funnel handler, stop 4.2 ingestion, reuse the 4.2 database, or copy 4.2 records into EDGE 2.0.
