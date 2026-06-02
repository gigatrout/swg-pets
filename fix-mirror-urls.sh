#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m swgpets.fix_mirror_urls "$@"
