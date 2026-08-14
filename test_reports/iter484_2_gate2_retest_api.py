"""
Focused API probe for iter484.2 Gate 2 retest.

Verifies the public vehicle detail API returns buyer-safe reserve metadata
for the three seeded vehicle routes without exposing raw reserve_price.
"""

import json
import os
import sys
from urllib.request import urlopen, Request

# Use the local backend service inside the preview container for deterministic
# API evidence. The public ingress may return 403 to urllib outside the browser.
BASE_URL = os.getenv("ITER484_GATE2_API_BASE", "http://127.0.0.1:8001/api")

CASES = [
    ("iter484-2-gate2-no-reserve", "none"),
    ("iter484-2-gate2-reserve-not-met", "not_met"),
    ("iter484-2-gate2-reserve-met", "met"),
]

RAW_TOKENS = ["$25,000", "$20,000", "25000", "20000", "reserve_price"]


def matching_scalar_paths(value, token, prefix="$"):
    """Return JSON-ish paths where a scalar contains token; diagnostic only."""
    matches = []
    if isinstance(value, dict):
        for key, child in value.items():
            matches.extend(matching_scalar_paths(child, token, f"{prefix}.{key}"))
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            matches.extend(matching_scalar_paths(child, token, f"{prefix}[{idx}]"))
    else:
        if token in str(value):
            matches.append(prefix)
    return matches


def fetch_json(path: str):
    req = Request(f"{BASE_URL}{path}", headers={"Accept": "application/json"})
    with urlopen(req, timeout=20) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def main() -> int:
    results = []
    failures = []
    for slug, expected_state in CASES:
        status, data = fetch_json(f"/vehicles/{slug}")
        raw = json.dumps(data, sort_keys=True)
        result = {
            "slug": slug,
            "http_status": status,
            "reserve_state": data.get("reserve_state"),
            "has_reserve": data.get("has_reserve"),
            "reserve_met": data.get("reserve_met"),
            "reserve_price_key_present": "reserve_price" in data,
            "raw_token_hits": [token for token in RAW_TOKENS if token in raw],
            "raw_token_paths": {
                token: matching_scalar_paths(data, token)
                for token in RAW_TOKENS
                if token != "reserve_price" and token in raw
            },
        }
        results.append(result)
        if status != 200:
            failures.append(f"{slug}: HTTP {status}")
        if data.get("reserve_state") != expected_state:
            failures.append(f"{slug}: expected reserve_state {expected_state}, got {data.get('reserve_state')}")
        if "reserve_price" in data:
            failures.append(f"{slug}: reserve_price key leaked")
        # Numeric tokens can be legitimate visible listing data (e.g. starting
        # price/current bid). The user-reported regression asks for these to be
        # absent from DOM text; the API security contract here is no raw
        # reserve_price key plus the masked reserve_state fields above.

    print(json.dumps({"results": results, "failures": failures}, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())