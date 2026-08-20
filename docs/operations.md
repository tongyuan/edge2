# Remote operations

## Isolation contract

```text
local source:  /Users/tonywong/edge2
remote source: /home/tony/edge2
Compose name:  edge2
app:           edge2-app, loopback 8792 -> container 8790
ingress:       edge2-ingress, loopback 8793 -> container 8080
database:      edge2-db, loopback 5435 -> container 5432
volume:        edge2_pgdata
backups:       /home/tony/edge2-backups
```

EDGE 4.2 remains at `/home/tony/edge` with its independent containers, Redis, database volume, ports, and Tailscale routes.

## Initial remote environment

Create `/home/tony/edge2/.env` with mode `600`, based on `.env.example`. Use independent random values for `EDGE2_DB_PASSWORD` and `WEBHOOK_SECRET`. Do not reuse a 4.2 credential or public path token.

## Deploy

From a clean local EDGE 2.0 Git repository:

```bash
./scripts/deploy_remote.sh
```

The script syncs source while protecting `.env` and backups, builds with Compose
project `edge2`, and checks both the application and ingress health endpoints.
It makes no TradingView alert changes.

## Health and logs

```bash
ssh edge-server 'curl --fail http://127.0.0.1:8792/health'
ssh edge-server 'curl --fail http://127.0.0.1:8793/health'
ssh edge-server 'docker logs --tail 200 edge2-app'
ssh edge-server 'docker logs --tail 200 edge2-ingress'
ssh edge-server 'docker ps --filter name=edge2'
```

Health reports application/database state, latest accepted webhook time, durable accepted/rejected/duplicate counters, observed symbol count, and active MRZ count.

## TradingView ingress

The stable ngrok hostname is managed by the user service
`~/.config/systemd/user/edge-ngrok.service`. Its committed definition is
`ops/systemd/edge-ngrok.service` and targets loopback port `8793`. The ingress
then injects the protected webhook-secret header and proxies the exact webhook
path to `edge2-app`.

Before replacing the old unit, preserve it as:

```text
/home/tony/.config/systemd/user/edge-ngrok.service.pre-edge2-20260820T0845Z
```

The stable public endpoint is:

```text
https://unretroactively-latticed-fidela.ngrok-free.dev/webhook/tradingview
```

Do not expose the application port directly through ngrok. Doing so would
bypass header injection and cause exact nine-field TradingView payloads to fail
authentication.

## Optional private preview

After loopback verification, a separate Tailscale HTTPS listener can proxy to `127.0.0.1:8792`. Use an unused port such as `8444` and verify the existing `443` and `8443` mappings before and after. This is a preview route only; do not enable Funnel for it.

## Rollback

Application rollback means redeploying a known local Git commit to `/home/tony/edge2` and rebuilding only Compose project `edge2`. Database rollback requires the explicit restore process. Ngrok rollback restores the preserved pre-EDGE-2 unit and restarts only the user-level ngrok service. No rollback command should stop, recreate, or remove an EDGE 4.2 container or volume.
