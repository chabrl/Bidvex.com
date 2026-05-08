#!/usr/bin/env python3
"""
iter203 P0 Compliance — Cleanup Script
=======================================
Scans every CURRENTLY ACTIVE marketplace and multi-item listing and pauses
any vehicle listing posted by a non-dealer.

Run manually:
    cd /app/backend && python -m scripts.cleanup_vehicle_violations

Run from outside the package:
    cd /app/backend && python scripts/cleanup_vehicle_violations.py

Idempotent — safe to re-run. Only rewrites status when a violation is
detected and the seller is not a verified dealer.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure backend root on sys.path when invoked as a file
THIS_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = THIS_DIR.parent
sys.path.insert(0, str(BACKEND_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_ROOT / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.safety_watchdog import cleanup_existing_violations  # noqa: E402


async def _main() -> int:
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        print("ERROR: MONGO_URL / DB_NAME missing from environment", file=sys.stderr)
        return 1

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    try:
        summary = await cleanup_existing_violations(db)
    finally:
        client.close()

    print("=" * 72)
    print("iter203 — Vehicle Listing Compliance Cleanup")
    print("=" * 72)
    print(f"Started: {summary['started_at']}")
    print(f"Ended:   {summary['ended_at']}")
    print()
    for col_key in ("listings", "multi_item_listings"):
        s = summary[col_key]
        print(f"  {s['collection']:>22}: examined={s['examined']:>5} paused={s['paused']:>3}")
        for fid in s.get("flagged_ids", []):
            print(f"      → paused: {fid}")
    print("-" * 72)
    print(f"  Total examined: {summary['total_examined']}")
    print(f"  Total paused:   {summary['total_paused']}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(_main())
    sys.exit(exit_code)
