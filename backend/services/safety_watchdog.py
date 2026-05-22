"""
iter203 P0 Compliance — Safety Watchdog
========================================
Backstop service that re-scans every active marketplace + multi-item lot
listing every 60 minutes. Any listing that looks like a vehicle but was
posted by a non-dealer is moved to `status: "pending_review"` and stays
there until a human admin manually approves or rejects it.

This is layered defence — even if the API gate is bypassed (race condition,
back-fill from old data, schema migration drift) the watchdog will catch
the listing within 60 minutes and lock it out.

Public surface:
  • run_safety_watchdog(db) → dict with per-collection counters
  • cleanup_existing_violations(db) → identical scan, marked as a one-shot

Outputs (always emitted to `audit_logs`):
  • action="vehicle_listing_paused_by_watchdog" — per listing
  • action="watchdog_run" — per scan with summary
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from .vehicle_listing_guard import (
    is_vehicle_listing,
    check_user_is_verified_dealer,
)

logger = logging.getLogger(__name__)

PAUSED_STATUS = "pending_review"
ACTIVE_STATUSES = ("active", "upcoming")


async def _pause_listing(
    db,
    *,
    collection_name: str,
    listing: dict,
    signals: list[str],
    strength: int,
    triggered_by: str,
    seller_user_doc: dict,
) -> None:
    listing_id = listing.get("id")

    # HOTFIX (Infinite Re-flag Loop) / FIX 4 — Absolute admin-exempt guard.
    # If a direct caller bypasses _scan_collection's query filter, this
    # blocks any pause action AND any compliance email. Admin must NEVER
    # receive a compliance email for a listing they already approved.
    if (
        listing.get("watchdog_exempt") is True
        or listing.get("admin_approved_override") is True
        or listing.get("ai_scan_bypass") is True
    ):
        logger.info(
            "[safety_watchdog] BLOCKED — refusing to pause/email admin-exempt listing %s",
            listing_id,
        )
        return

    update = {
        "$set": {
            "status": PAUSED_STATUS,
            "paused_at": datetime.now(timezone.utc).isoformat(),
            "paused_reason": "vehicle_listing_by_non_dealer",
            "paused_by": triggered_by,
            "compliance_signals": signals,
            "compliance_strength": strength,
            "previous_status": listing.get("status"),
        }
    }
    coll = db[collection_name]
    await coll.update_one({"id": listing_id}, update)

    await db.audit_logs.insert_one({
        "action": "vehicle_listing_paused_by_watchdog",
        "collection": collection_name,
        "listing_id": listing_id,
        "seller_id": listing.get("seller_id"),
        "seller_email": seller_user_doc.get("email"),
        "category": listing.get("category"),
        "title": (listing.get("title") or "")[:160],
        "detection_signals": signals,
        "detection_strength": strength,
        "triggered_by": triggered_by,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    logger.warning(
        "[safety_watchdog] paused listing id=%s collection=%s seller=%s signals=%s",
        listing_id, collection_name, listing.get("seller_id"), signals,
    )

    # iter205 P0 — Admin notification dispatch (non-blocking, best-effort)
    try:
        from services.compliance_notifier import notify_admins_of_violation
        await notify_admins_of_violation(
            db,
            kind="paused_by_watchdog",
            listing=listing,
            signals=signals,
            seller_email=seller_user_doc.get("email"),
            extra={"collection": collection_name, "triggered_by": triggered_by},
        )
    except Exception as e:
        logger.error("[safety_watchdog] notification dispatch failed: %s", e)


async def _scan_collection(db, collection_name: str, triggered_by: str) -> dict:
    """Generic scanner used for both `listings` and `multi_item_listings`.
    Multi-item listings are paused when EITHER the parent or any LOT looks
    like a vehicle from a non-dealer (the listing is the unit of moderation).

    HOTFIX (AI Watchdog Infinite Re-flag Loop) / FIX 2:
      Exempt admin-approved listings at the DB query level so they never even
      enter the scanner loop. The compound query also filters out the legacy
      `admin_approved_override` / `ai_scan_bypass` passport set by the AI
      review approve flow (so a single admin approve protects against BOTH
      the scheduled cron and the seller-edit re-trigger path).
    """
    coll = db[collection_name]
    paused = 0
    flagged_ids: list[str] = []
    examined = 0

    cursor = coll.find(
        {
            "status": {"$in": list(ACTIVE_STATUSES)},
            # ── FIX 2 — Admin-approved listings never enter the scan ──
            "watchdog_exempt": {"$ne": True},
            "admin_approved_override": {"$ne": True},
            "ai_scan_bypass": {"$ne": True},
        },
        {
            "_id": 0,
            "id": 1,
            "seller_id": 1,
            "category": 1,
            "title": 1,
            "description": 1,
            "lots": 1,
            "status": 1,
            "watchdog_exempt": 1,
            "admin_approved_override": 1,
        },
    )

    # Cache dealer-status per seller during this run
    dealer_cache: dict[str, tuple[bool, dict]] = {}

    async for listing in cursor:
        examined += 1

        # ── FIX 2 (safety net) — in-loop guard for defence-in-depth. The
        # DB query already excludes exempt listings, but if a future caller
        # invokes _pause_listing directly (or someone removes the query
        # filter), this guard guarantees the immunity passport still wins.
        if listing.get("watchdog_exempt") is True \
           or listing.get("admin_approved_override") is True \
           or listing.get("ai_scan_bypass") is True:
            logger.info(
                "[safety_watchdog] SKIP — listing %s is admin-exempt (no scan, no email)",
                listing.get("id"),
            )
            continue

        all_signals: list[str] = []
        max_strength = 0

        # Top-level title/category
        is_v, sigs, strength = is_vehicle_listing(
            listing.get("category"),
            listing.get("title"),
            listing.get("description"),
        )
        if is_v:
            all_signals.extend(sigs)
            max_strength = max(max_strength, strength)

        # Multi-item lots — scan each
        for lot in (listing.get("lots") or []):
            lis_v, lsigs, lstrength = is_vehicle_listing(
                listing.get("category"),  # parent category applies to all lots
                lot.get("title"),
                lot.get("description"),
            )
            if lis_v:
                all_signals.extend([f"lot:{s}" for s in lsigs])
                max_strength = max(max_strength, lstrength)

        if max_strength == 0:
            continue

        # Deduplicate signals while preserving order
        seen = set()
        all_signals = [s for s in all_signals if not (s in seen or seen.add(s))]

        seller_id = listing.get("seller_id")
        if seller_id in dealer_cache:
            is_dealer, user_doc = dealer_cache[seller_id]
        else:
            is_dealer, user_doc = await check_user_is_verified_dealer(db, seller_id)
            dealer_cache[seller_id] = (is_dealer, user_doc)

        if is_dealer:
            continue

        await _pause_listing(
            db,
            collection_name=collection_name,
            listing=listing,
            signals=all_signals,
            strength=max_strength,
            triggered_by=triggered_by,
            seller_user_doc=user_doc,
        )
        paused += 1
        flagged_ids.append(listing.get("id"))

    return {
        "collection": collection_name,
        "examined": examined,
        "paused": paused,
        "flagged_ids": flagged_ids,
    }


async def run_safety_watchdog(db, *, triggered_by: str = "scheduler") -> dict:
    """Main entry point — invoked every 60 minutes by the scheduler.

    Returns a summary dict suitable for logging and admin telemetry.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    listings_summary = await _scan_collection(db, "listings", triggered_by)
    multi_summary = await _scan_collection(db, "multi_item_listings", triggered_by)

    summary = {
        "started_at": started_at,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "triggered_by": triggered_by,
        "listings": listings_summary,
        "multi_item_listings": multi_summary,
        "total_paused": listings_summary["paused"] + multi_summary["paused"],
        "total_examined": listings_summary["examined"] + multi_summary["examined"],
    }

    await db.audit_logs.insert_one({
        "action": "watchdog_run",
        **summary,
        "timestamp": summary["ended_at"],
    })
    logger.info(
        "[safety_watchdog] run complete examined=%s paused=%s",
        summary["total_examined"], summary["total_paused"],
    )
    return summary


async def cleanup_existing_violations(db) -> dict:
    """Same logic as the watchdog, but explicitly tagged as a one-shot
    cleanup (used by the manual remediation script). Returns the same
    summary shape so the script can pretty-print results."""
    return await run_safety_watchdog(db, triggered_by="cleanup_script")
