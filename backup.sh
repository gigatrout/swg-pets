#!/usr/bin/env bash
# Download a full offline copy of swgpets.com/pets into ./mirror
set -euo pipefail
cd "$(dirname "$0")"

export NO_PROXY='*'
export no_proxy='*'
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy 2>/dev/null || true

echo "Creating offline backup of www.swgpets.com/pets -> ./mirror"
echo "This downloads the pet list, every /pet/* page, and all images/CSS."
echo ""

exec python3 -m swgpets.backup "$@"
