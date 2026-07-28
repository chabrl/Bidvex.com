"""
iter402 — Backfill `platform_terms_accepted_at` for legacy users.

Any user who accepted a per-listing T&C (populated `auction_agreements`)
BEFORE iter400 introduced the platform-wide stamp is now blocked by the
tightened Trust Gate that requires `platform_terms_accepted_at` to be
set. This migration heals those legacy accounts in-place by copying the
user's OLDEST auction-agreement timestamp into `platform_terms_accepted_at`.

Rules:
  * Only touches users with a non-empty `auction_agreements` dict AND
    a missing/empty/null `platform_terms_accepted_at`.
  * Uses the OLDEST timestamp so the audit trail preserves the true
    first-acceptance moment (not the most recent bid).
  * Sets:
      platform_terms_accepted_at   = <oldest_iso>
      platform_terms_version       = "v1"
      platform_terms_source        = "backfill:iter402_auction_agreements"
      platform_terms_backfilled_at = <now>
  * Idempotent — running twice is a no-op on the same set.
  * Logs the total scanned + updated counts.

Usage:
    cd /app/backend && python scripts/backfill_platform_terms.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger("backfill_platform_terms")


def _bootstrap_env() -> None:
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as fh:
            for line in fh:
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.strip().partition("=")
                    if k and v and k not in os.environ:
                        os.environ[k] = v


def _pick_oldest_iso(agreements: dict) -> Optional[str]:
    """Return the smallest (oldest) ISO-8601 timestamp value across
    `auction_agreements`. Returns None if the dict is empty or all
    values are unusable."""
    if not isinstance(agreements, dict) or not agreements:
        return None
    parsed: list[tuple[datetime, str]] = []
    for _lid, ts in agreements.items():
        if not ts or not isinstance(ts, str):
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            parsed.append((dt, ts))
        except Exception:
            continue
    if not parsed:
        return None
    parsed.sort(key=lambda x: x[0])
    return parsed[0][1]


async def run() -> dict:
    _bootstrap_env()
    from motor.motor_asyncio import AsyncIOMotorClient  # local import so path is set
    mongo_url = os.environ["MONGO_URL"]
    db_name   = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    now_iso = datetime.now(timezone.utc).isoformat()

    query = {
        "auction_agreements": {"$exists": True, "$ne": {}, "$type": "object"},
        "$or": [
            {"platform_terms_accepted_at": {"$exists": False}},
            {"platform_terms_accepted_at": None},
            {"platform_terms_accepted_at": ""},
        ],
    }

    scanned = 0
    updated = 0
    skipped_no_timestamp = 0
    errors = 0

    try:
        async for user in db.users.find(query, {"_id": 0, "id": 1, "email": 1, "auction_agreements": 1}):
            scanned += 1
            oldest = _pick_oldest_iso(user.get("auction_agreements") or {})
            if not oldest:
                skipped_no_timestamp += 1
                logger.warning(
                    "skipping user id=%s email=%s — no parseable agreement timestamp",
                    user.get("id"), user.get("email"),
                )
                continue
            try:
                res = await db.users.update_one(
                    {"id": user["id"],
                     "$or": [
                         {"platform_terms_accepted_at": {"$exists": False}},
                         {"platform_terms_accepted_at": None},
                         {"platform_terms_accepted_at": ""},
                     ]},
                    {"$set": {
                        "platform_terms_accepted_at":    oldest,
                        "platform_terms_version":        "v1",
                        "platform_terms_source":         "backfill:iter402_auction_agreements",
                        "platform_terms_backfilled_at":  now_iso,
                        "platform_terms_last_seen_at":   now_iso,
                    }},
                )
                if res.modified_count:
                    updated += 1
                    logger.info(
                        "healed id=%s email=%s → platform_terms_accepted_at=%s",
                        user.get("id"), user.get("email"), oldest,
                    )
            except Exception as e:  # noqa: BLE001
                errors += 1
                logger.error("update failed for id=%s: %s", user.get("id"), e)
    finally:
        client.close()

    summary = {
        "scanned":              scanned,
        "updated":              updated,
        "skipped_no_timestamp": skipped_no_timestamp,
        "errors":               errors,
    }
    logger.info("iter402 backfill complete — %s", summary)
    return summary


if __name__ == "__main__":
    result = asyncio.run(run())
    # Exit non-zero if any errors so CI/manual runs surface issues.
    sys.exit(1 if result["errors"] else 0)
