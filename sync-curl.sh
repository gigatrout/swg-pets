#!/usr/bin/env bash
# Sync cache using curl (live first, Wayback latest snapshot fallback).
set -uo pipefail
cd "$(dirname "$0")"

export NO_PROXY='*'
export no_proxy='*'
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy 2>/dev/null || true

LIVE_BASE="https://www.swgpets.com"
# No fixed timestamp — follows redirect to newest archived copy.
WB_BASE="https://web.archive.org/web/${LIVE_BASE}"
CACHE="cache"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
LIVE_TIMEOUT=15
WB_TIMEOUT=120
DELAY="${SWGPETS_DELAY:-0.12}"

mkdir -p "$CACHE"

fetch_one() {
  local path="$1"
  local dest="$2"
  mkdir -p "$(dirname "$dest")"

  if curl -sSL --max-time "$LIVE_TIMEOUT" --noproxy '*' -A "$UA" \
      -H "Referer: ${LIVE_BASE}/" \
      -o "$dest" "${LIVE_BASE}${path}" 2>/dev/null && [[ -s "$dest" ]]; then
    echo "[live] ${path}"
    return 0
  fi
  rm -f "$dest"

  if curl -sSL --max-time "$WB_TIMEOUT" --noproxy '*' -A "$UA" \
      -o "$dest" "${WB_BASE}${path}" 2>/dev/null && [[ -s "$dest" ]]; then
    echo "[wayback] ${path}"
    return 0
  fi

  echo "[FAIL] ${path}" >&2
  rm -f "$dest"
  return 1
}

PATHS=(
  "/"
  "/pets"
  "/creatures"
  "/specials"
  "/research"
  "/planner"
  "/spots"
  "/lyase"
  "/known"
  "/sheet"
  "/exp"
  "/statcalc"
  "/hydro"
  "/oekevo"
  "/family"
  "/unknown"
  "/about"
  "/profiles"
  "/profile-pets"
  "/galaxies"
  "/expertise"
  "/wiki/"
  "/templates/swgpets/swgpets.css"
  "/templates/swgpets/swgpetsmenu.css"
  "/favicon.ico"
  "/templates/swgpets/images/swgpets_header.png"
  "/templates/swgpets/images/spacer.png"
  "/templates/swgpets/images/tail_top.png"
  "/templates/swgpets/images/tail_left.png"
  "/templates/swgpets/images/tail_right.png"
)

echo "Syncing SWG Pets -> ${CACHE}/ (live first, Wayback latest fallback)"

for path in "${PATHS[@]}"; do
  if [[ "$path" == "/" ]]; then
    dest="${CACHE}/index.html"
  else
    dest="${CACHE}${path}"
  fi
  fetch_one "$path" "$dest" || true
  sleep "$DELAY"
done

echo "Extracting asset URLs from cached HTML..."
HTML_FILES=()
for f in "${CACHE}/index.html" "${CACHE}/pets" "${CACHE}/creatures" "${CACHE}/specials"; do
  [[ -f "$f" ]] && HTML_FILES+=("$f")
done
ASSETS=""
if ((${#HTML_FILES[@]} > 0)); then
  ASSETS=$(grep -ohE "(src|href|background)=['\"][^'\"]+\.(png|jpg|gif|ico|css|js)['\"]" "${HTML_FILES[@]}" 2>/dev/null \
    | sed -E "s/.*=['\"]([^'\"]+)['\"].*/\1/" | sort -u || true)
fi

n=0
for asset in $ASSETS; do
  [[ "$asset" == http* ]] && continue
  [[ "$asset" != /* ]] && continue
  dest="${CACHE}${asset}"
  [[ -f "$dest" && -s "$dest" ]] && continue
  fetch_one "$asset" "$dest" || true
  n=$((n + 1))
  [[ $n -ge 800 ]] && break
  sleep "$DELAY"
done

count=$(find "$CACHE" -type f | wc -l | tr -d ' ')
echo "Done. ${count} files in ${CACHE}/"
echo "Run ./start.sh to serve locally."
