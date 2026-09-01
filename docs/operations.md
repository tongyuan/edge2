# Development and deployment operations

## Canonical architecture

```text
Mac: /Users/tonywong/edge2
development, tests, commits, and pushes
                |
                v
GitHub: https://github.com/tongyuan/edge2
public canonical source-code history
                |
                v
Remote: /home/tony/edge2
read-only Git consumer and operational runtime
```

The Mac is the only normal development checkout. The remote server does not
author or push code. It pulls public `main` over HTTPS and therefore needs no
GitHub write token or stored GitHub credential.

Git is authoritative for source code, migrations, configuration templates,
deployment scripts, PineScript, and documentation. The remote server remains
authoritative for observations, active MRZ records, MRZ events, the production
database, backups, and production secrets.

## Runtime isolation and persistence

```text
remote source:       /home/tony/edge2
production env:      /home/tony/edge2/.env (mode 600, never tracked)
Compose project:     edge2
app service:         edge2-app, loopback 8792 -> container 8790
ingress service:     edge2-ingress, loopback 8793 -> container 8080
database service:    edge2-db, loopback 5435 -> container 5432
database volume:     edge2_pgdata
Docker volume data:  /var/lib/docker/volumes/edge2_pgdata/_data
host backups:        /home/tony/edge2-backups
```

EDGE 4.2 remains at `/home/tony/edge` with independent containers, Redis,
database volume, ports, and Tailscale routes.

## Initial remote clone

For a fresh server, clone the public repository, then create the environment
file locally on that server:

```bash
git clone https://github.com/tongyuan/edge2.git /home/tony/edge2
cd /home/tony/edge2
cp .env.example .env
chmod 600 .env
```

Fill `.env` with independent production values for `EDGE2_DB_PASSWORD` and
`WEBHOOK_SECRET`. Do not copy a 4.2 credential. The current pre-Git deployment
can be adopted in place only after its non-secret files have been verified
against the intended Git commit:

```bash
cd /home/tony/edge2
git init -b main
git remote add origin https://github.com/tongyuan/edge2.git
git fetch origin main
git reset origin/main
git branch --set-upstream-to=origin/main main
git status --short
```

`git reset` above updates Git metadata and the index without replacing the
verified working files. The ignored `.env`, external backup directory, and
named database volume remain outside Git.

## Normal development and deployment

The normal local workflow is:

```text
edit -> test -> review git diff -> commit -> deploy
```

Deploy from clean local `main`:

```bash
./scripts/deploy-remote.sh
```

The helper runs `make test`, pushes `main`, captures the intended SHA, verifies
`origin/main`, checks that the remote checkout is clean, and pulls with:

```bash
git pull --ff-only origin main
```

It refuses to overwrite a dirty remote tree. It then rebuilds/restarts the
actual Compose services, checks both health endpoints, and fails unless local
HEAD, `origin/main`, and remote HEAD are identical.

Do not deploy source with `rsync`, `scp`, tar archives, or SSH file heredocs.
Remote file inspection is reserved for actual deployment discrepancies.

## Docker restart and health verification

The deploy helper runs these service commands remotely:

```bash
docker compose --project-name edge2 up -d --build
docker compose --project-name edge2 up -d --force-recreate --no-deps edge2-ingress
```

The second command reloads the ingress template without touching the database
volume. Verify the runtime independently with:

```bash
ssh edge-server 'curl --fail http://127.0.0.1:8792/health'
ssh edge-server 'curl --fail http://127.0.0.1:8793/health'
ssh edge-server 'docker ps --filter name=edge2'
```

Verify the deployed commit with:

```bash
git rev-parse HEAD
git rev-parse origin/main
ssh edge-server 'cd /home/tony/edge2 && git rev-parse HEAD'
```

## Rollback

For a normal source rollback, identify the known-good commit, create a revert
commit locally, push `main`, and run the normal deploy helper. This preserves a
clear public history and returns the remote to a clean, tracked `main` state.

For an emergency source-only rollback, the remote may temporarily fetch and
check out a specific known-good commit in detached-HEAD state, then rebuild the
same Compose project. Immediately reconcile by making and pushing a local
rollback commit and deploying normally so the server returns to `main`.

Database rollback is separate. Never remove `edge2_pgdata` or automatically
reverse a migration unless the migration tooling explicitly supports it. Use
the reviewed backup/restore process in [backup-restore.md](backup-restore.md).

## Secret policy

- Commit `.env.example` with names and public-safe defaults only.
- Keep `/home/tony/edge2/.env`, SSH private keys, tokens, TLS keys, database
  files, dumps, and backup archives out of Git.
- Audit tracked files, untracked files, and reachable history before any public
  push. Removing a secret in a later commit is insufficient; clean history and
  rotate any credential that may have been exposed.
- The remote uses anonymous read-only HTTPS Git access and does not push.

## TradingView ingress

The stable ngrok hostname is managed by the user service
`~/.config/systemd/user/edge-ngrok.service`. Its committed definition is
`ops/systemd/edge-ngrok.service` and targets loopback port `8793`. The ingress
injects the protected webhook-secret header and proxies only the exact webhook
path to `edge2-app`.

The stable public endpoint remains:

```text
https://unretroactively-latticed-fidela.ngrok-free.dev/webhook/tradingview
```

Do not expose the application port directly through ngrok. The Git migration
does not change PineScript logic or live TradingView alerts.

The same HTTPS ingress now serves the allowlisted EDGE website, static/PWA
assets, diagnostics, and API paths required by the iPhone Home Screen web app.
The webhook secret is still injected only on the exact TradingView path. Web
Push VAPID setup, migration behavior, and device verification are documented in
[web-push.md](web-push.md).
