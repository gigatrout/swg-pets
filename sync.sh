#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Bypass corporate/system HTTP proxies that block archive.org / swgpets.
export NO_PROXY='*'
export no_proxy='*'
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy 2>/dev/null || true

if command -v curl >/dev/null 2>&1; then
  echo "Syncing via curl (recommended)..."
  exec python3 -m swgpets.sync_curl "$@"
fi

echo "Syncing SWG Pets (live site first, Wayback fallback)..."
python3 -m swgpets.sync "$@"
