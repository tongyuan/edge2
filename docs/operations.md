# Remote operations

## Isolation contract

```text
local source:  /Users/tonywong/edge2
remote source: /home/tony/edge2
Compose name:  edge2
app:           edge2-app, loopback 8792 -> container 8790
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

The script syncs source while protecting `.env` and backups, builds with Compose project `edge2`, and checks the loopback health endpoint. It makes no Tailscale or TradingView changes.

## Health and logs

```bash
ssh edge-server 'curl --fail http://127.0.0.1:8792/health'
ssh edge-server 'docker logs --tail 200 edge2-app'
ssh edge-server 'docker ps --filter name=edge2'
```

Health reports application/database state, latest accepted webhook time, durable accepted/rejected/duplicate counters, observed symbol count, and active MRZ count.

## Optional private preview

After loopback verification, a separate Tailscale HTTPS listener can proxy to `127.0.0.1:8792`. Use an unused port such as `8444` and verify the existing `443` and `8443` mappings before and after. This is a preview route only; do not enable Funnel for it.

## Rollback

Application rollback means redeploying a known local Git commit to `/home/tony/edge2` and rebuilding only Compose project `edge2`. Database rollback requires the explicit restore process. No rollback command should stop, recreate, or remove an EDGE 4.2 container or volume.
