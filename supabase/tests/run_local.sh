#!/usr/bin/env bash
# يشغّل فحصًا من supabase/tests على Postgres محلّيّ فارغ، ثمّ يمحو القاعدة.
# النواة تُقتطع من الترحيل نفسه بين علامتَي ⟪core⟫ و⟪/core⟫ — فما يُفحص هو
# ما يُطبَّق، لا نسخةٌ تتباعد عنه.
#
#   bash supabase/tests/run_local.sh client_base_local.sql
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
TEST="$HERE/${1:?اسم ملفّ الفحص}"
MIG="$HERE/../migrations/0039_client_base.sql"
PSQL=(psql -h "${PGHOST:-/tmp}" -p "${PGPORT:-54329}" -U "${PGUSER:-postgres}" -v ON_ERROR_STOP=0 -q)
DB="t_$$"
CORE="$(mktemp)"; trap 'rm -f "$CORE"; "${PSQL[@]}" -d postgres -c "drop database if exists $DB" >/dev/null' EXIT
sed -n '/⟪core⟫/,/⟪\/core⟫/p' "$MIG" > "$CORE"
"${PSQL[@]}" -d postgres -c "create database $DB" >/dev/null
"${PSQL[@]}" -d "$DB" -v core="$CORE" -f "$TEST" 2>&1 | grep -E "ROLLBACK_OK|ERROR" | sed 's/^psql:[^ ]* //'
