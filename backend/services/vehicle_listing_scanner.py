"""
iter203 P0 Compliance — AI-Backed Vehicle Listing Scanner
==========================================================
Background-task scanner that runs AFTER a marketplace listing is created.

If the AI detects vehicle-shaped content the listing is moved to
`status: "pending_review"` and an admin notification is emitted. This is a
secondary defence — the primary gate is the hard-coded `enforce_vehicle_dealer_gate`
which already runs synchronously inside `POST /api/listings`. The AI is the
"smart safety net" the user explicitly requested.

Designed to fail-OPEN (never crashes the request) and fail-SAFE (errors
log but never auto-approve). When the LLM is unavailable, the listing is
left as-is (the hard gate already ran synchronously).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


VEHICLE_SCANNER_PROMPT = """You are a strict content-moderation scanner for an
auction marketplace. The platform separates VEHICLE listings (cars, trucks,
SUVs, vans, motorcycles, ATVs, boats, RVs, heavy equipment, etc.) into a
dedicated dealer-licensed Vehicle Auctions section. The general Marketplace
is NOT permitted to contain vehicle listings UNLESS the seller is a verified
licensed dealer (OMVIC, AMVIC, VSA, SAAQ, FCAA, etc.).

Analyse the following marketplace listing and decide if it is a vehicle.

LISTING:
Category: {category}
Title:    {title}
Description: {description}

Return a STRICT JSON object with these keys (no markdown, no prose):
  is_vehicle           (boolean)
  vehicle_type         (string|null — "car"/"truck"/"motorcycle"/"boat"/"atv"/"rv"/"heavy_equipment"/"other"/null)
  confidence           (float 0.0 to 1.0)
  reasons              (array of short strings explaining the decision)
  recommended_action   (one of: "allow", "require_dealer_verification", "block_and_review")

Be strict: a 2018 Honda Civic posted under the "Toys & Hobbies" category is
STILL a vehicle. Use any year + brand pattern, VIN mention, mileage, engine
specs, transmission type, or fuel-type field as strong indicators."""


async def _call_gemini_scanner(category: Optional[str], title: Optional[str], description: Optional[str]) -> dict:
    """Call Gemini with the vehicle-detection prompt. Returns parsed JSON.

    Raises RuntimeError on any failure (caller decides the policy)."""
    api_key = (
        os.environ.get("EMERGENT_LLM_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or ""
    )
    if not api_key:
        raise RuntimeError("no_llm_credentials")

    try:
        from google import genai  # type: ignore
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError(f"genai_import_failed: {exc}") from exc

    client = genai.Client(api_key=api_key)
    prompt = VEHICLE_SCANNER_PROMPT.format(
        category=category or "",
        title=(title or "")[:300],
        description=(description or "")[:1500],
    )
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
        config={
            "response_mime_type": "application/json",
            "temperature": 0.1,
            "max_output_tokens": 256,
        },
    )
    raw = (response.text or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gemini_returned_non_json: {raw[:200]}") from exc


async def scan_listing_for_vehicles(
    db,
    *,
    listing_id: str,
    collection: str = "listings",
) -> dict:
    """Background-task entry point.

    Re-reads the listing, runs the AI scanner, and (if flagged) moves it to
    `status: "pending_review"`. Always writes a `listing_scans` audit row.

    Returns a summary dict (also useful for unit tests).
    """
    coll = db[collection]
    listing = await coll.find_one(
        {"id": listing_id},
        {"_id": 0, "id": 1, "seller_id": 1, "category": 1, "title": 1, "description": 1, "status": 1},
    )
    if not listing:
        logger.info("[vehicle_scanner] listing %s not found — skipping", listing_id)
        return {"skipped": "not_found", "listing_id": listing_id}

    # Skip if already in a non-active state — don't reverse human decisions
    if listing.get("status") not in ("active", "upcoming", "pending"):
        return {"skipped": f"status:{listing.get('status')}", "listing_id": listing_id}

    # Determine seller verification first — verified dealers are auto-trusted
    from .vehicle_listing_guard import check_user_is_verified_dealer
    is_dealer, _ = await check_user_is_verified_dealer(db, listing.get("seller_id"))

    try:
        ai_result = await _call_gemini_scanner(
            listing.get("category"),
            listing.get("title"),
            listing.get("description"),
        )
    except Exception as exc:
        # Fail OPEN — the synchronous hard gate already ran. Log only.
        logger.warning("[vehicle_scanner] AI unavailable for listing %s: %s", listing_id, exc)
        await db.listing_scans.insert_one({
            "listing_id": listing_id,
            "collection": collection,
            "status": "ai_unavailable",
            "error": str(exc)[:500],
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"listing_id": listing_id, "ai_unavailable": True, "error": str(exc)[:200]}

    is_vehicle = bool(ai_result.get("is_vehicle"))
    confidence = float(ai_result.get("confidence") or 0.0)
    reasons = ai_result.get("reasons") or []
    recommended_action = ai_result.get("recommended_action")

    scan_record = {
        "listing_id": listing_id,
        "collection": collection,
        "status": "scanned",
        "ai_is_vehicle": is_vehicle,
        "ai_confidence": confidence,
        "ai_reasons": reasons,
        "ai_recommended_action": recommended_action,
        "ai_vehicle_type": ai_result.get("vehicle_type"),
        "seller_is_dealer": is_dealer,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.listing_scans.insert_one(scan_record)

    if not is_vehicle:
        return {"listing_id": listing_id, "is_vehicle": False, "action_taken": "none"}

    # AI says vehicle. If seller is dealer → log only. Else → pause.
    if is_dealer:
        return {
            "listing_id": listing_id,
            "is_vehicle": True,
            "verified_dealer": True,
            "action_taken": "logged_only",
        }

    # Pause + audit
    await coll.update_one(
        {"id": listing_id},
        {"$set": {
            "status": "pending_review",
            "paused_at": datetime.now(timezone.utc).isoformat(),
            "paused_reason": "ai_scanner_vehicle_by_non_dealer",
            "paused_by": "ai_scanner",
            "ai_confidence": confidence,
            "ai_reasons": reasons,
        }},
    )
    await db.audit_logs.insert_one({
        "action": "vehicle_listing_paused_by_ai_scanner",
        "listing_id": listing_id,
        "collection": collection,
        "seller_id": listing.get("seller_id"),
        "ai_confidence": confidence,
        "ai_reasons": reasons,
        "category": listing.get("category"),
        "title": (listing.get("title") or "")[:160],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    # iter205 — admin notification (non-blocking)
    try:
        from .compliance_notifier import notify_admins_of_violation
        await notify_admins_of_violation(
            db,
            kind="paused_by_ai",
            listing=listing,
            signals=[f"ai_reason:{r}" for r in (reasons or [])][:5],
            extra={"collection": collection, "ai_confidence": confidence},
        )
    except Exception as e:
        logger.error("[ai_scanner] notification dispatch failed: %s", e)
    logger.warning(
        "[vehicle_scanner] PAUSED listing=%s seller=%s confidence=%s reasons=%s",
        listing_id, listing.get("seller_id"), confidence, reasons,
    )
    return {
        "listing_id": listing_id,
        "is_vehicle": True,
        "verified_dealer": False,
        "ai_confidence": confidence,
        "ai_reasons": reasons,
        "action_taken": "paused_pending_review",
    }
