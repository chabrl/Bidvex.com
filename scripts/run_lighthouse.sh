#!/bin/bash
# iter358 — Lighthouse audit runner
# Runs Lighthouse against 4 canonical pages and writes JSON reports
# to /app/test_reports/lighthouse_iter358/<label>/{en,fr}.json

set -e

BASE_URL="${LH_BASE_URL:-https://prod-verify-2.preview.emergentagent.com}"
LABEL="${1:-before}"
OUT_DIR="/app/test_reports/lighthouse_iter358/${LABEL}"

mkdir -p "$OUT_DIR"

# Chrome flags to disable sandbox (required in container)
CHROME_FLAGS="--headless=new --no-sandbox --disable-dev-shm-usage --disable-gpu --disable-setuid-sandbox --no-zygote"

# Common Lighthouse flags for mobile emulation + performance category
LH_FLAGS="--only-categories=performance --output=json --quiet --chrome-flags=\"$CHROME_FLAGS\" --preset=desktop --disable-full-page-screenshot"

audit() {
  local slug="$1"
  local url="$2"
  echo "[lighthouse] Auditing $url"
  timeout 90 npx --yes lighthouse "$url" \
    --output=json \
    --quiet \
    --chrome-flags="$CHROME_FLAGS" \
    --preset=desktop \
    --only-categories=performance \
    --disable-full-page-screenshot \
    --max-wait-for-load=45000 \
    > "$OUT_DIR/${slug}.json" 2> "$OUT_DIR/${slug}.stderr" || {
      echo "[lighthouse] FAILED: $url (see stderr)"
      tail -5 "$OUT_DIR/${slug}.stderr" || true
    }
}

audit "home"        "$BASE_URL/"
audit "marketplace" "$BASE_URL/marketplace"
audit "vehicles"    "$BASE_URL/vehicle-auctions"
audit "storage"     "$BASE_URL/storage-auctions"

echo "[lighthouse] Done. Reports in $OUT_DIR"
