#!/usr/bin/env bash
# Download creature icons, ranked ability icons, and flags into ./mirror
set -euo pipefail
cd "$(dirname "$0")"

export NO_PROXY='*'
export no_proxy='*'
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy 2>/dev/null || true

echo "Backfilling images/icons into ./mirror (creature acquire pages, etc.)"
exec python3 -m swgpets.backfill_assets "$@"
