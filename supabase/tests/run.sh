#!/usr/bin/env bash
# Spin up a scratch Postgres, apply the migration, run the schema tests.
# Usage: supabase/tests/run.sh
set -euo pipefail
PGBIN=${PGBIN:-/usr/lib/postgresql/16/bin}
PGDATA=${PGDATA:-/var/tmp/pgdata}
PORT=${PORT:-5433}
SOCK=${SOCK:-/var/tmp}

if [ ! -d "$PGDATA" ]; then
  id -u pgtest >/dev/null 2>&1 || useradd -m pgtest
  mkdir -p "$PGDATA"; chown pgtest "$PGDATA"; chmod 700 "$PGDATA"
  su pgtest -c "$PGBIN/initdb -D $PGDATA -U postgres --auth=trust" >/dev/null
fi
su pgtest -c "$PGBIN/pg_ctl -D $PGDATA -o '-p $PORT -k $SOCK' -l /var/tmp/pg.log start" >/dev/null 2>&1 || true
sleep 2

PSQL="psql -h $SOCK -p $PORT -U postgres -v ON_ERROR_STOP=1 -q"
$PSQL -c "drop database if exists eman;" -c "create database eman;"
# Stub the pieces Supabase provides that a bare Postgres does not.
$PSQL -d eman <<'BOOTSTRAP'
create publication supabase_realtime;
do $$ begin
  if not exists (select 1 from pg_roles where rolname='anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname='authenticated') then create role authenticated nologin; end if;
end $$;
grant usage on schema public to anon, authenticated;
create schema if not exists auth;
create table if not exists auth.users (id uuid primary key, email text);
create or replace function auth.uid() returns uuid language sql stable as
  $f$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $f$;
BOOTSTRAP
$PSQL -d eman -f "$(dirname "$0")/../migrations/0001_init.sql"
psql -h "$SOCK" -p "$PORT" -U postgres -d eman -f "$(dirname "$0")/schema_tests.sql"
