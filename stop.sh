#!/usr/bin/env bash
# Stop the local SWG Pets server if it is listening on SWGPETS_PORT.
set -uo pipefail

PORT="${SWGPETS_PORT:-8765}"

if ! command -v lsof >/dev/null 2>&1; then
  echo "lsof not found; cannot find server on port ${PORT}" >&2
  exit 1
fi

pids=$(lsof -ti "tcp:${PORT}" -sTCP:LISTEN 2>/dev/null || true)

if [[ -z "${pids}" ]]; then
  echo "No server listening on port ${PORT}."
  exit 0
fi

echo "Stopping server on port ${PORT} (PID: ${pids//$'\n'/, })..."
kill ${pids} 2>/dev/null || true
sleep 0.5

# Force-kill anything still bound to the port.
pids=$(lsof -ti "tcp:${PORT}" -sTCP:LISTEN 2>/dev/null || true)
if [[ -n "${pids}" ]]; then
  kill -9 ${pids} 2>/dev/null || true
fi

if lsof -ti "tcp:${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Could not free port ${PORT}." >&2
  exit 1
fi

echo "Port ${PORT} is free."
