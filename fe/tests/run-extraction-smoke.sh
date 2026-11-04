#!/bin/bash
# Isolated integration/browser smoke environment. Ctrl-C cleans up both servers
# and stops PostgreSQL. Never connects to the configured application database.
set -eu
cd "$(dirname "$0")/../../be"
smoke_root=$(mktemp -d /private/tmp/extraction-review-pg.XXXXXX)
smoke_pg_bin=${SMOKE_PG_BIN:-/usr/local/opt/postgresql@16/bin}
smoke_api_pid=
smoke_fe_pid=
cleanup() {
  if [ -n "$smoke_fe_pid" ]; then kill "$smoke_fe_pid" 2>/dev/null || true; wait "$smoke_fe_pid" 2>/dev/null || true; fi
  if [ -n "$smoke_api_pid" ]; then kill "$smoke_api_pid" 2>/dev/null || true; wait "$smoke_api_pid" 2>/dev/null || true; fi
  "$smoke_pg_bin/pg_ctl" -D "$smoke_root/data" -m fast -w stop > "$smoke_root/stop.log" 2>&1 || true
}
trap cleanup EXIT
trap 'exit 0' INT TERM
"$smoke_pg_bin/initdb" -D "$smoke_root/data" --locale-provider=icu --icu-locale=und --encoding=UTF8 --auth=trust -U extraction_test > "$smoke_root/init.log" 2>&1
"$smoke_pg_bin/pg_ctl" -D "$smoke_root/data" -l "$smoke_root/server.log" -o "-F -h '' -k $smoke_root -p 55439 -c shared_buffers=16MB" -w start
"$smoke_pg_bin/createdb" -h "$smoke_root" -p 55439 -U extraction_test extraction_review_test
export TEST_DATABASE_URL="postgresql+psycopg://extraction_test@/extraction_review_test?host=$smoke_root&port=55439"
RUN_EXTRACTION_PDF_SMOKE=1 .venv/bin/python -m pytest -q tests --tb=short
export DATABASE_HOST="$smoke_root" DATABASE_PORT=55439 DATABASE_USERNAME=extraction_test DATABASE_PASSWORD='' DATABASE_NAME=extraction_review_test
export EXTRACTION_REVIEW_SMOKE=1
.venv/bin/python ../fe/tests/serve_backend.py > "$smoke_root/api.log" 2>&1 &
smoke_api_pid=$!
cd ../fe
BACKEND_API_URL=http://127.0.0.1:8001/api/v1 NODE_OPTIONS="--import=./tests/helpers/mock-r2.mjs" node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3100 > "$smoke_root/fe.log" 2>&1 &
smoke_fe_pid=$!
printf 'Smoke UI: http://localhost:3100\nLogs: %s\n' "$smoke_root"
wait
