#!/usr/bin/env bash
# Quick check that every ability filter resolves in the offline mirror.
set -euo pipefail
cd "$(dirname "$0")"

python3 <<'PY'
from pathlib import Path
from swgpets.backup import SPECIAL_IDS, mirror_dest
from swgpets.offline_forms import pets_query_fallbacks

root = Path("mirror")
missing = []
for sid in SPECIAL_IDS:
    direct = mirror_dest(f"/pets?specials={sid}", root)
    full = f"sort1=name&sort2=name&show=info&specials={sid}"
    fallbacks = pets_query_fallbacks(full)
    resolved = any(mirror_dest(f"/pets?{fb}", root).is_file() for fb in fallbacks)
    if not direct.is_file() or not resolved:
        missing.append(sid)

if missing:
    print(f"Missing filter pages for specials: {', '.join(missing)}")
    print("Run: ./refresh-filters.sh")
    raise SystemExit(1)

print(f"OK — all {len(SPECIAL_IDS)} ability filters are mirrored and resolvable.")
PY
