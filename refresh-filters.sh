#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export NO_PROXY='*'
export no_proxy='*'
exec python3 -m swgpets.refresh_filters "$@"
