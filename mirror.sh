#!/usr/bin/env bash
# Alias for offline backup (replaces old limited mirror crawler).
set -euo pipefail
cd "$(dirname "$0")"
exec ./backup.sh "$@"
