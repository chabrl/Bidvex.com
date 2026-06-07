"""
iter288 — Listing Change Request Pipeline.

Centralizes the user-self-service edit / deletion workflow across every
listing directory (vehicles, storage units, lots, marketplace items).
Active auctions cannot be edited or deleted unilaterally — sellers
submit a request that lands in the admin moderation inbox.

Collections
-----------
db.listing_requests:
    {
      id, listing_id, listing_type, user_id, request_type,
      reason, current_payload_delta, status, created_at,
      resolved_at, resolved_by, admin_notes
    }
  status ∈ {pending, approved, rejected}
  request_type ∈ {edit, delete}
  listing_type ∈ {vehicle, storage, lot, marketplace}

Endpoints
---------
POST   /api/listings/{id}/request-change       user submits request
GET    /api/admin/listing-requests             admin queue (filterable)
POST   /api/admin/listing-requests/{rid}/approve
POST   /api/admin/listing-requests/{rid}/reject
GET    /api/listing-requests/mine              user's own requests
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from deps import get_db, get_current_user
from routes.admin import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(tags=["listing_requests"])
security = HTTPBearer()


# ── Pydantic ───────────────────────────────────────────────────────────


class ListingChangeRequest(BaseModel):
    """Body of POST /api/listings/{id}/request-change."""
    request_type: str = Field(..., description="'edit' or 'delete'")
    reason: str = Field(..., min_length=3, max_length=2000)
    current_payload_delta: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional delta of fields the seller wants to change "
                    "(only used when request_type='edit').",
    )
    listing_type: Optional[str] = Field(
        default=None,
        description="Optional override — auto-detected when omitted.",
    )


# ── Helpers ────────────────────────────────────────────────────────────


async def _resolve_listing(db, listing_id: str) -> Optional[Dict[str, Any]]:
    """Locate a listing across every directory collection.

    Returns the doc + the source collection so the approve handler can
    operate on the right table when executing the change.
    """
    for collection, ltype in (
        ("vehicle_listings", "vehicle"),
        ("storage_auctions",  "storage"),
        ("listings",          "marketplace"),
        ("multi_item_listings", "lot"),
    ):
        doc = await db[collection].find_one({"id": listing_id}, {"_id": 0})
        if doc:
            return {"doc": doc, "collection": collection, "listing_type": ltype}
    return None


# ── USER-SIDE: submit request ─────────────────────────────────────────


@router.post("/listings/{listing_id}/request-change")
async def submit_listing_change_request(
    listing_id: str,
    payload: ListingChangeRequest,
    user=Depends(get_current_user),
):
    """Sellers (and only sellers) submit edit / deletion requests.

    Returns the persisted request with a `status='pending'` stamp. Admin
    triage happens via the admin inbox; the listing itself is unchanged
    until an approval lands.
    """
    if payload.request_type not in ("edit", "delete"):
        raise HTTPException(status_code=400, detail="request_type must be 'edit' or 'delete'")

    db = get_db()
    found = await _resolve_listing(db, listing_id)
    if not found:
        raise HTTPException(status_code=404, detail="Listing not found")

    doc = found["doc"]
    user_id    = user.id if hasattr(user, "id") else user.get("id")
    user_email = user.email if hasattr(user, "email") else user.get("email")
    if doc.get("seller_id") and doc["seller_id"] != user_id:
        raise HTTPException(status_code=403, detail="Only the listing owner can submit a change request")

    # Block duplicate pending requests for the same listing (avoid inbox spam).
    existing = await db.listing_requests.find_one(
        {"listing_id": listing_id, "user_id": user_id, "status": "pending"},
        {"_id": 0},
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_pending_request",
                "message": "You already have a pending change request on this listing.",
                "existing_request_id": existing["id"],
            },
        )

    request_row = {
        "id":                   str(uuid.uuid4()),
        "listing_id":           listing_id,
        "listing_type":         payload.listing_type or found["listing_type"],
        "listing_collection":   found["collection"],
        "user_id":              user_id,
        "user_email":           user_email,
        "request_type":         payload.request_type,
        "reason":               payload.reason.strip(),
        "current_payload_delta": payload.current_payload_delta or {},
        "status":               "pending",
        "created_at":           datetime.now(timezone.utc).isoformat(),
        "resolved_at":          None,
        "resolved_by":          None,
        "admin_notes":          None,
    }
    await db.listing_requests.insert_one(request_row.copy())
    return {"message": "Change request submitted", "request": request_row}


@router.get("/listing-requests/mine")
async def list_my_listing_requests(
    user=Depends(get_current_user),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    """Caller's own listing-change requests across every directory."""
    db = get_db()
    user_id = user.id if hasattr(user, "id") else user.get("id")
    q: Dict[str, Any] = {"user_id": user_id}
    if status:
        q["status"] = status
    rows = await db.listing_requests.find(q, {"_id": 0}) \
        .sort("created_at", -1).limit(limit).to_list(limit)
    return {"requests": rows, "total": len(rows)}


# ── ADMIN-SIDE: triage inbox ──────────────────────────────────────────


@router.get("/admin/listing-requests")
async def admin_list_listing_requests(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    status: Optional[str] = Query(default="pending"),
    listing_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
):
    """Admin queue for listing change requests."""
    await require_admin(credentials)
    db = get_db()
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if listing_type:
        q["listing_type"] = listing_type
    rows = await db.listing_requests.find(q, {"_id": 0}) \
        .sort("created_at", -1).limit(limit).to_list(limit)
    return {
        "requests":     rows,
        "total":        len(rows),
        "pending_count": await db.listing_requests.count_documents({"status": "pending"}),
    }


@router.post("/admin/listing-requests/{request_id}/approve")
async def admin_approve_listing_request(
    request_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    admin_notes: Optional[str] = Query(default=None),
):
    """Approve a pending request.

    - `delete`: soft-cancels the listing across both the canonical
      collection and the marketplace mirror (keeps audit trail).
    - `edit`:   merges `current_payload_delta` into the listing.

    Always idempotent — already-resolved requests return their last
    state without re-applying the change.
    """
    admin_user = await require_admin(credentials)
    db = get_db()
    req = await db.listing_requests.find_one({"id": request_id}, {"_id": 0})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req["status"] != "pending":
        return {
            "message": f"Request was already resolved as '{req['status']}'.",
            "request": req,
        }

    listing_id     = req["listing_id"]
    collection     = req.get("listing_collection") or "listings"
    request_type   = req["request_type"]
    now            = datetime.now(timezone.utc).isoformat()

    # Apply the change.
    if request_type == "delete":
        await db[collection].update_one(
            {"id": listing_id},
            {"$set": {
                "status":      "cancelled",
                "is_visible":  False,
                "deleted_at":  now,
                "deleted_by":  admin_user.email,
                "deleted_reason": req.get("reason"),
            }},
        )
        if collection != "listings":
            await db.listings.update_one(
                {"id": listing_id},
                {"$set": {
                    "status":     "cancelled",
                    "is_visible": False,
                    "deleted_at": now,
                    "deleted_by": admin_user.email,
                }},
            )
    elif request_type == "edit":
        delta = req.get("current_payload_delta") or {}
        # Strip mongo-dangerous keys for safety.
        safe = {k: v for k, v in delta.items() if not k.startswith("$") and "." not in k}
        if safe:
            safe["updated_at"]      = now
            safe["last_edited_by"]  = admin_user.email
            await db[collection].update_one({"id": listing_id}, {"$set": safe})
            if collection != "listings":
                # Mirror best-effort — ignore if not present.
                await db.listings.update_one({"id": listing_id}, {"$set": safe})

    # Resolve the request row.
    updated = {
        "status":      "approved",
        "resolved_at": now,
        "resolved_by": admin_user.email,
        "admin_notes": admin_notes,
    }
    await db.listing_requests.update_one({"id": request_id}, {"$set": updated})
    req.update(updated)
    return {"message": "Request approved", "request": req}


@router.post("/admin/listing-requests/{request_id}/reject")
async def admin_reject_listing_request(
    request_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    admin_notes: Optional[str] = Query(default=None),
):
    """Reject a pending request — no change is applied to the listing."""
    admin_user = await require_admin(credentials)
    db = get_db()
    req = await db.listing_requests.find_one({"id": request_id}, {"_id": 0})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req["status"] != "pending":
        return {
            "message": f"Request was already resolved as '{req['status']}'.",
            "request": req,
        }
    now = datetime.now(timezone.utc).isoformat()
    updated = {
        "status":      "rejected",
        "resolved_at": now,
        "resolved_by": admin_user.email,
        "admin_notes": admin_notes,
    }
    await db.listing_requests.update_one({"id": request_id}, {"$set": updated})
    req.update(updated)
    return {"message": "Request rejected", "request": req}
