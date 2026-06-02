#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

export NO_PROXY='*'
export no_proxy='*'
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy 2>/dev/null || true

echo "Prefetching images, CSS, and icons into ./cache ..."
python3 -m swgpets.prefetch "$@"
