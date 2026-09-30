#!/usr/bin/env bash
#
# bootstrap.sh — bring the DB + backend up on a fresh server from a Postgres dump.
#
# What it does, in order:
#   1. sanity-checks docker / compose / .env / the dump file
#   2. starts ONLY postgres and waits until it is healthy
#   3. restores your dump into the target database (drops + recreates it first,
#      so the script is safe to re-run)
#   4. starts the app (+ pgadmin)
#
# The restore happens BEFORE the app boots on purpose: the app runs create_all()
# on startup, and letting it create empty tables first would collide with the dump.
#
# Usage:
#   ./bootstrap.sh <path-to-dump>
#   ./bootstrap.sh backup.sql            # plain SQL  -> psql
#   ./bootstrap.sh backup.sql.gz         # gzipped SQL -> gunzip | psql
#   ./bootstrap.sh backup.dump           # pg_dump -Fc custom format -> pg_restore
#
# If you omit the argument it looks for ./dump.sql, ./dump.sql.gz or ./dump.dump.
#
set -eu
# pipefail catches failures in the `gunzip | psql` restore, but it's a bash/ksh
# feature — enable it only if the running shell supports it (so `sh bootstrap.sh`
# doesn't die with "illegal option -o pipefail").
(set -o pipefail) 2>/dev/null && set -o pipefail || true

cd "$(dirname "$0")"

# ── pick a docker compose command (v2 plugin or legacy binary) ─────────────────
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  echo "ERROR: docker compose is not installed." >&2
  exit 1
fi

# ── locate the dump ────────────────────────────────────────────────────────────
DUMP="${1:-}"
if [ -z "$DUMP" ]; then
  for f in dump.sql dump.sql.gz dump.dump; do
    [ -f "$f" ] && DUMP="$f" && break
  done
fi
if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
  echo "ERROR: dump file not found. Pass it as an argument: ./bootstrap.sh <dump>" >&2
  exit 1
fi
echo ">> Using dump: $DUMP"

# ── .env is required (compose 'app' service reads it via env_file) ─────────────
if [ ! -f .env ]; then
  echo ">> .env missing — copying from .env.example (EDIT IT before production use!)."
  cp .env.example .env
fi

# ── load DB creds from .env, falling back to compose defaults ──────────────────
set -a; . ./.env 2>/dev/null || true; set +a
PGUSER="${POSTGRES_USER:-postgres}"
PGPASS="${POSTGRES_PASSWORD:-password}"
PGDB="${POSTGRES_DB:-vismay_pavos_db}"

# ── 1. start postgres only, wait for healthy ───────────────────────────────────
echo ">> Starting postgres..."
$DC up -d postgres

echo -n ">> Waiting for postgres to accept connections"
for _ in $(seq 1 60); do
  if $DC exec -T postgres pg_isready -U "$PGUSER" >/dev/null 2>&1; then
    echo " — ready."
    break
  fi
  echo -n "."
  sleep 2
done
if ! $DC exec -T postgres pg_isready -U "$PGUSER" >/dev/null 2>&1; then
  echo; echo "ERROR: postgres did not become ready in time." >&2
  exit 1
fi

# ── 2. drop + recreate the target database (clean restore, re-runnable) ────────
echo ">> Recreating database '$PGDB'..."
$DC exec -T -e PGPASSWORD="$PGPASS" postgres \
  psql -U "$PGUSER" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
  WHERE datname = '$PGDB' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS "$PGDB";
CREATE DATABASE "$PGDB";
SQL

# ── 3. restore the dump ─────────────────────────────────────────────────────────
echo ">> Restoring dump into '$PGDB'..."
case "$DUMP" in
  *.gz)
    gunzip -c "$DUMP" | $DC exec -T -e PGPASSWORD="$PGPASS" postgres \
      psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1
    ;;
  *.sql)
    $DC exec -T -e PGPASSWORD="$PGPASS" postgres \
      psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 < "$DUMP"
    ;;
  *)
    # custom / directory / tar format produced by `pg_dump -Fc` (or -Fd/-Ft)
    $DC exec -T -e PGPASSWORD="$PGPASS" postgres \
      pg_restore -U "$PGUSER" -d "$PGDB" --no-owner --no-privileges < "$DUMP"
    ;;
esac
echo ">> Restore complete."

# ── 4. start the app (+ pgadmin) ────────────────────────────────────────────────
echo ">> Building & starting the app..."
$DC up -d --build app pgadmin

echo
echo "==================================================================="
echo " Done."
echo "   API      : http://localhost:8000"
echo "   pgAdmin  : http://localhost:5050"
echo "   Logs     : $DC logs -f app"
echo "==================================================================="
