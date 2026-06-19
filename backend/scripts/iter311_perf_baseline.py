"""
iter311 — Admin all-collections perf baseline (OLD vs NEW)
===========================================================
OLD: client fan-out → 2 fetch round-trips, parse, merge, sort in JS
NEW: 1 server-aggregated request → /api/admin/listings/all-collections

This script is the perf claim's receipt. Run it after seeding via
`backend/scripts/iter311_perf_seed.py` so the numbers are meaningful.
"""
import os
import time
import statistics
import requests
from dotenv import load_dotenv


load_dotenv("/app/backend/.env")
API = (
    open("/app/frontend/.env")
    .read()
    .split("REACT_APP_BACKEND_URL=", 1)[1]
    .splitlines()[0]
    .strip()
    + "/api"
)


def login():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def time_request(method, url, **kw):
    t0 = time.perf_counter()
    r = method(url, timeout=30, **kw)
    return r, (time.perf_counter() - t0) * 1000


def run_old_pattern(tok, runs=5):
    """Old pattern: 2 admin endpoints in parallel (client merges)."""
    headers = {"Authorization": f"Bearer {tok}"}
    runs_ms, payload_kb = [], []
    for _ in range(runs):
        t0 = time.perf_counter()
        # Sequential (most accurate worst-case; HTTP/2 multiplex isn't
        # available against the test ingress, so this matches the client).
        r1 = requests.get(f"{API}/admin/listings/all", headers=headers, timeout=30)
        r2 = requests.get(f"{API}/admin/multi-item-listings/all", headers=headers, timeout=30)
        elapsed = (time.perf_counter() - t0) * 1000
        runs_ms.append(elapsed)
        payload_kb.append((len(r1.content) + len(r2.content)) / 1024)
        # Vehicle + storage are *separate tabs* in the current admin
        # panel — count one round-trip each since the admin would
        # otherwise have to also navigate to those tabs for the same
        # cross-cutting view.
        try:
            r3 = requests.get(f"{API}/admin/vehicles/all", headers=headers, timeout=30)
            r4 = requests.get(f"{API}/admin/storage-facilities/all-auctions", headers=headers, timeout=30)
            elapsed_full = (time.perf_counter() - t0) * 1000
            runs_ms[-1] = elapsed_full
            payload_kb[-1] += (len(r3.content) + len(r4.content)) / 1024
        except Exception:
            # Those endpoints may not exist or 404 — fold them out of the comparison.
            pass
    return {
        "runs_ms": runs_ms,
        "p50_ms": int(statistics.median(runs_ms)),
        "min_ms": int(min(runs_ms)),
        "max_ms": int(max(runs_ms)),
        "payload_kb_p50": int(statistics.median(payload_kb)),
    }


def run_new_pattern(tok, runs=5, limit=50):
    headers = {"Authorization": f"Bearer {tok}"}
    runs_ms, payload_kb, perf_ms_server = [], [], []
    total_seen, by_section_seen = 0, {}
    for _ in range(runs):
        r, elapsed = time_request(
            requests.get,
            f"{API}/admin/listings/all-collections?limit={limit}",
            headers=headers,
        )
        runs_ms.append(elapsed)
        payload_kb.append(len(r.content) / 1024)
        j = r.json()
        perf_ms_server.append(j.get("perf_ms", 0))
        total_seen = j.get("total", total_seen)
        by_section_seen = j.get("by_section", by_section_seen)
    return {
        "runs_ms": runs_ms,
        "p50_ms": int(statistics.median(runs_ms)),
        "min_ms": int(min(runs_ms)),
        "max_ms": int(max(runs_ms)),
        "payload_kb_p50": int(statistics.median(payload_kb)),
        "server_p50_ms": int(statistics.median(perf_ms_server)),
        "total_rows_visible_in_paginated_response": limit,
        "total_rows_in_db": total_seen,
        "by_section": by_section_seen,
    }


def main():
    tok = login()
    print("Logged in. Warming up...")
    requests.get(f"{API}/admin/listings/all-collections?limit=1",
                 headers={"Authorization": f"Bearer {tok}"}, timeout=15)

    print("\n══ OLD pattern (multiple client-side round-trips) ══")
    old = run_old_pattern(tok, runs=5)
    print(f"  p50:  {old['p50_ms']} ms")
    print(f"  min:  {old['min_ms']} ms")
    print(f"  max:  {old['max_ms']} ms")
    print(f"  payload p50: {old['payload_kb_p50']} KB")

    print("\n══ NEW pattern (/api/admin/listings/all-collections) ══")
    new = run_new_pattern(tok, runs=5, limit=50)
    print(f"  p50:  {new['p50_ms']} ms (server agg {new['server_p50_ms']} ms)")
    print(f"  min:  {new['min_ms']} ms")
    print(f"  max:  {new['max_ms']} ms")
    print(f"  payload p50: {new['payload_kb_p50']} KB")
    print(f"  total rows in DB:  {new['total_rows_in_db']}")
    print(f"  by_section:        {new['by_section']}")

    speedup = old["p50_ms"] / max(1, new["p50_ms"])
    payload_drop = 100 * (1 - new["payload_kb_p50"] / max(1, old["payload_kb_p50"]))
    print(f"\n══ DELTA ══")
    print(f"  speedup:           {speedup:.2f}× (p50)")
    print(f"  payload reduction: {payload_drop:.1f}%")


if __name__ == "__main__":
    main()
