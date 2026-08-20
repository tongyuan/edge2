# Database backup and restore

The remote PostgreSQL volume `edge2_pgdata` survives application and database container restarts. Host backups are written outside container filesystems to `/home/tony/edge2-backups` by default.

## Backup

From `/home/tony/edge2`:

```bash
./scripts/backup.sh
```

The script uses PostgreSQL custom format, writes to a temporary host file, verifies that it is non-empty, atomically renames it, and applies mode `600`.

Verify a backup without restoring:

```bash
docker exec -i edge2-db pg_restore --list < /home/tony/edge2-backups/edge2_TIMESTAMP.dump
```

## Restore rehearsal

Restores are destructive to the current EDGE 2.0 database contents. Confirm the exact absolute backup path and take a fresh backup first. Then:

```bash
cd /home/tony/edge2
EDGE2_ALLOW_RESTORE=YES ./scripts/restore.sh /home/tony/edge2-backups/edge2_TIMESTAMP.dump
curl --fail http://127.0.0.1:8792/health
```

The restore script stops only `edge2-app`, restores into `edge2-db`, restarts the app, and lets startup migrations verify schema state. It does not address EDGE 4.2 containers or volumes.

## Recovery boundary

The Mac checkout contains code and Git history only. Operational observations and MRZ authority live on the remote server and must be recovered from `edge2_pgdata` or a host backup.
