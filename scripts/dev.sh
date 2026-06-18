#!/usr/bin/env sh
set -eu
printf 'Starting SCBKR API on http://localhost:8787 ...\n'
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8787 &
api_pid=$!
trap 'kill "$api_pid" 2>/dev/null || true' INT TERM EXIT
printf 'Starting SCBKR Web on http://localhost:5500 ...\n'
npm --prefix apps/web run dev
