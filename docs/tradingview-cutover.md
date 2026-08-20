# TradingView cutover contract

On 2026-08-20 the operator confirmed that the 4.2 alerts were defunct and
authorized reuse of the existing stable ngrok hostname for EDGE 2.0. The 4.2
application, containers, Redis, and database remain intact; only the ngrok
forwarding destination changes.

## Endpoint isolation

TradingView posts to this exact URL:

```text
https://unretroactively-latticed-fidela.ngrok-free.dev/webhook/tradingview
```

The route is deliberately layered:

```text
ngrok hostname -> 127.0.0.1:8793 -> edge2-ingress -> edge2-app:8790
```

`edge2-ingress` exposes only `/health` and the exact POST webhook path. It
injects `X-EDGE2-Webhook-Secret` from the protected EDGE 2.0 environment before
forwarding. TradingView therefore sends the exact nine-field schema 4.3 body
without carrying a credential in the observation contract.

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
2. Apply it to the one-minute chart previously used for the 4.2 route emitter.
3. Compare the EQM20, EQM20 +1/-1, arm, first dip/rip, and reclaim/reject output
   against 4.2. Compare the current 20-week high/low against the chart's existing
   IPDA structural context; the first canary payload will expose the exact values
   captured by the observation builder.
4. Create the BTD alert: in the script inputs enable BTD emission, disable STR
   emission, select **Any alert() function call**, choose **Once Per Bar Close**,
   and leave the alert message unchanged.
5. Create the STR alert from a separate input snapshot: disable BTD emission,
   enable STR emission, and use the same alert condition/frequency.
6. Give both new alerts the exact ngrok URL shown above. Ngrok forwards to the
   loopback-only ingress on port `8793`; never point it directly at port `8792`.
7. Observe the first real BTD reclaim and STR rejection. Confirm that each alert
   posts one nine-field schema 4.3 JSON object and receives a successful response.
8. Verify accepted counts and the symbol in EDGE 2.0 Symbol Lab/API. Confirm the
   stored observation price, IPDA high/low, and observed time match TradingView.
9. Confirm the old 4.2 alerts remain disabled/retired after both routes pass
   validation and EDGE 2.0 state survives a service restart.

## Staged verification

1. Verify app health on loopback `8792` and ingress health on loopback `8793`.
2. Take a fresh EDGE 2.0 database backup.
3. POST one exact nine-field schema 4.3 canary through the public ngrok URL,
   without an authentication field or header, and require HTTP 201.
4. Confirm accepted counts and the canary symbol, then restore the pre-canary
   backup so verification leaves no synthetic operational state.
5. Create separate BTD and STR TradingView alerts using the exact public URL.
6. Confirm accepted/rejected/duplicate counts, timestamps, symbol normalization,
   and deterministic WHO/WHERE state with real observations.

## Rollback

Restore the backed-up `edge-ngrok.service`, reload the user systemd manager, and
restart the unit to point the hostname back at the preserved 4.2 gateway on
`127.0.0.1:8765`. Disable the EDGE 2.0 TradingView alerts before rollback.

## Forbidden automatic actions

Deployment scripts must not edit TradingView alerts, stop the preserved 4.2
application/database, reuse the 4.2 database, or copy 4.2 records into EDGE 2.0.
