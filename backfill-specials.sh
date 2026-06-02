#!/usr/bin/env bash
# Backfill specials pages and pet-by-ability filters into ./mirror
set -euo pipefail
cd "$(dirname "$0")"

export NO_PROXY='*'
export no_proxy='*'
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy 2>/dev/null || true

echo "Backfilling specials and ability filters into ./mirror"
exec python3 -m swgpets.backfill_specials "$@"
