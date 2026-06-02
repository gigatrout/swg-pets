#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

export NO_PROXY='*'
export no_proxy='*'
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy 2>/dev/null || true

HOST="${SWGPETS_HOST:-127.0.0.1}"
PORT="${SWGPETS_PORT:-8765}"

"$(dirname "$0")/stop.sh" 2>/dev/null || true

EXTRA_ARGS=("$@")
if [[ ${#EXTRA_ARGS[@]} -eq 0 && -d mirror/pets ]]; then
  EXTRA_ARGS=(--mirror-only)
  echo "Found ./mirror — starting in offline mode (no network required)."
fi

echo "Starting SWG Pets at http://${HOST}:${PORT}/pets"
if [[ " ${EXTRA_ARGS[*]} " == *" --mirror-only "* ]]; then
  echo "Serving static backup from ./mirror (offline — pets section only)"
else
  echo "Live proxy mode (needs network). Run ./backup.sh first for offline use."
fi

exec python3 -m swgpets.server --host "$HOST" --port "$PORT" "${EXTRA_ARGS[@]}"
