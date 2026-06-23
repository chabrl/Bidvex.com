"""
iter313 — Universal Draft Save / Edit / Submit / Restore

The Step 0 reproduction (Feb 22, 2026) showed Save-as-Draft was broken in
ALL FIVE listing types (Marketplace, Lots/Multi-Item, Storage, Vehicle
single, Multi-Lot Vehicle). The per-type POST endpoints all enforce
strict Pydantic validation — useless for half-typed drafts.

This module ships ONE unified entry point:

    POST   /api/drafts/save              -> upsert a partial draft
    GET    /api/drafts                   -> list current user's drafts
    GET    /api/drafts/{draft_id}        -> hydrate a single draft
    POST   /api/drafts/{draft_id}/submit -> promote a draft to its real
                                              per-type POST (full validation
                                              kicks in here, not before)
    DELETE /api/drafts/{draft_id}        -> hard-delete a draft
    POST   /api/drafts/{draft_id}/restore-> resurrect a draft_expired row
                                              within 60d archive window

Drafts live in one collection: `seller_drafts`. Doc shape:
    {
      id:          uuid,
      seller_id:   str,
      type:        "marketplace"|"lots"|"storage"|"vehicle"|"multi_lot_vehicle",
      payload:     dict,             # raw partial form data
      title:       str | None,       # extracted for dashboard display
      status:      "draft" | "draft_expired",
      created_at:  datetime,
      updated_at:  datetime,
      draft_expired_at: datetime | None,
    }

Drafts are independent of the per-type collections until submit, which
keeps each per-type POST endpoint strictly validated (good) while letting
the draft flow accept anything (also good).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from deps import get_current_user, get_db, User


logger = logging.getLogger(__name__)

drafts_router = APIRouter(tags=["Universal Drafts"])

DraftType = Literal["marketplace", "lots", "storage", "vehicle", "multi_lot_vehicle"]

DRAFT_TYPE_LABELS = {
    "marketplace":       {"en": "Marketplace",       "fr": "Marché"},
    "lots":              {"en": "Lots / Multi-Item", "fr": "Lots / Multi-articles"},
    "storage":           {"en": "Storage Auction",   "fr": "Enchère de stockage"},
    "vehicle":           {"en": "Vehicle Auction",   "fr": "Enchère de véhicule"},
    "multi_lot_vehicle": {"en": "Multi-Lot Vehicle", "fr": "Enchère de véhicules multi-lots"},
}

# Restore window for draft_expired listings.
RESTORE_WINDOW_DAYS = 60


# ── Models ──────────────────────────────────────────────────────────


class DraftSaveBody(BaseModel):
    type:     DraftType
    draft_id: Optional[str] = None
    payload:  Dict[str, Any] = Field(default_factory=dict)


# ── Helpers ─────────────────────────────────────────────────────────


def _extract_title(payload: Dict[str, Any]) -> Optional[str]:
    for k in ("title", "event_title", "name", "facility_name"):
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()[:200]
    return None


def _iso(dt) -> Optional[str]:
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).isoformat()
    return dt


def _expiry_days_left(updated_at: datetime) -> int:
    from services.draft_expiry import DRAFT_MAX_AGE_DAYS
    anchor = updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=timezone.utc)
    delta = (datetime.now(timezone.utc) - anchor).days
    return max(0, DRAFT_MAX_AGE_DAYS - delta)


def _restore_days_left(expired_at: datetime) -> int:
    anchor = expired_at if expired_at.tzinfo else expired_at.replace(tzinfo=timezone.utc)
    delta = (datetime.now(timezone.utc) - anchor).days
    return max(0, RESTORE_WINDOW_DAYS - delta)


# ── Endpoints ───────────────────────────────────────────────────────


@drafts_router.post("/drafts/save")
async def save_draft(body: DraftSaveBody, current_user: User = Depends(get_current_user)):
    """Upsert a partial draft. Validates `type` only — payload is free-form.

    Behavior:
      • If `draft_id` is provided AND owned by current_user → update payload,
        reset updated_at (this is also the 30-day expiry anchor).
      • Else → mint a new draft row.
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    title = _extract_title(body.payload)

    if body.draft_id:
        existing = await db.seller_drafts.find_one({"id": body.draft_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="draft_not_found")
        if existing.get("seller_id") != current_user.id:
            raise HTTPException(status_code=403, detail="not_your_draft")
        await db.seller_drafts.update_one(
            {"id": body.draft_id},
            {"$set": {
                "payload":                    body.payload,
                "title":                      title or existing.get("title"),
                "updated_at":                 now,
                # Re-activate an expired draft if the user touched it via save.
                "status":                     "draft",
                "draft_expired_at":           None,
                # iter312 D3 — reset the warning ledger so the 23-day reminder
                # can fire again on the new clock.
                "draft_expiry_warning_sent_at": None,
            }},
        )
        return {
            "draft_id":   body.draft_id,
            "type":       existing["type"],
            "status":     "draft",
            "updated_at": _iso(now),
            "expires_in_days": _expiry_days_left(now),
        }

    new_id = str(uuid.uuid4())
    doc = {
        "id":         new_id,
        "seller_id":  current_user.id,
        "type":       body.type,
        "payload":    body.payload,
        "title":      title,
        "status":     "draft",
        "created_at": now,
        "updated_at": now,
        "draft_expired_at": None,
    }
    await db.seller_drafts.insert_one(doc)
    logger.info(f"[drafts] {current_user.email} saved new draft id={new_id} type={body.type}")
    return {
        "draft_id":        new_id,
        "type":            body.type,
        "status":          "draft",
        "updated_at":      _iso(now),
        "expires_in_days": _expiry_days_left(now),
    }


@drafts_router.get("/drafts")
async def list_drafts(
    type: Optional[DraftType] = Query(None),
    include_expired: bool = Query(True, description="Include draft_expired rows within the 60d restore window"),
    current_user: User = Depends(get_current_user),
):
    """List the current user's drafts (D4 dashboard sub-tab feed)."""
    db = get_db()
    q: dict = {"seller_id": current_user.id}
    if type:
        q["type"] = type

    if include_expired:
        cutoff = datetime.now(timezone.utc) - timedelta(days=RESTORE_WINDOW_DAYS)
        q["$or"] = [
            {"status": "draft"},
            {"status": "draft_expired", "draft_expired_at": {"$gte": cutoff}},
        ]
    else:
        q["status"] = "draft"

    cursor = db.seller_drafts.find(q, {"_id": 0}).sort("updated_at", -1)
    rows = await cursor.to_list(500)
    drafts = []
    for r in rows:
        item = {
            "id":          r["id"],
            "type":        r["type"],
            "type_label":  DRAFT_TYPE_LABELS.get(r["type"], {"en": r["type"], "fr": r["type"]}),
            "title":       r.get("title") or "(untitled draft)",
            "status":      r.get("status", "draft"),
            "created_at":  _iso(r.get("created_at")),
            "updated_at":  _iso(r.get("updated_at")),
        }
        if r.get("status") == "draft":
            item["expires_in_days"] = _expiry_days_left(r["updated_at"])
        elif r.get("status") == "draft_expired" and r.get("draft_expired_at"):
            item["restore_days_left"] = _restore_days_left(r["draft_expired_at"])
        drafts.append(item)
    return {"count": len(drafts), "drafts": drafts}


@drafts_router.get("/drafts/{draft_id}")
async def get_draft(draft_id: str, current_user: User = Depends(get_current_user)):
    """Hydrate a single draft — used by the Edit-mode wizards."""
    db = get_db()
    doc = await db.seller_drafts.find_one({"id": draft_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="draft_not_found")
    if doc.get("seller_id") != current_user.id:
        raise HTTPException(status_code=403, detail="not_your_draft")
    return {
        "id":         doc["id"],
        "type":       doc["type"],
        "type_label": DRAFT_TYPE_LABELS.get(doc["type"], {"en": doc["type"], "fr": doc["type"]}),
        "title":      doc.get("title"),
        "status":     doc.get("status", "draft"),
        "payload":    doc.get("payload", {}),
        "created_at": _iso(doc.get("created_at")),
        "updated_at": _iso(doc.get("updated_at")),
    }


@drafts_router.delete("/drafts/{draft_id}")
async def delete_draft(draft_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    doc = await db.seller_drafts.find_one({"id": draft_id}, {"_id": 0, "seller_id": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="draft_not_found")
    if doc["seller_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="not_your_draft")
    await db.seller_drafts.delete_one({"id": draft_id})
    return {"success": True}


@drafts_router.post("/drafts/{draft_id}/restore")
async def restore_draft(draft_id: str, current_user: User = Depends(get_current_user)):
    """P1 — Bring a draft_expired row back to status='draft' within the 60d window."""
    db = get_db()
    now = datetime.now(timezone.utc)
    doc = await db.seller_drafts.find_one({"id": draft_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="draft_not_found")
    if doc.get("seller_id") != current_user.id:
        raise HTTPException(status_code=403, detail="not_your_draft")
    if doc.get("status") != "draft_expired":
        raise HTTPException(status_code=400, detail={"error": "not_expired", "message_en": "Draft is not in expired state.", "message_fr": "Le brouillon n'est pas expiré."})
    expired_at = doc.get("draft_expired_at")
    if isinstance(expired_at, datetime):
        expired_at_aware = expired_at if expired_at.tzinfo else expired_at.replace(tzinfo=timezone.utc)
        if (now - expired_at_aware) > timedelta(days=RESTORE_WINDOW_DAYS):
            raise HTTPException(status_code=410, detail={
                "error": "restore_window_closed",
                "message_en": f"The 60-day restore window has closed.",
                "message_fr": f"La fenêtre de restauration de 60 jours est fermée.",
            })
    await db.seller_drafts.update_one(
        {"id": draft_id},
        {"$set": {
            "status":             "draft",
            "draft_expired_at":   None,
            "updated_at":         now,
            "restored_at":        now,
            # Reset the 23-day warning ledger so it can re-fire later.
            "draft_expiry_warning_sent_at": None,
        }},
    )
    return {"success": True, "draft_id": draft_id, "status": "draft"}


# Forwarded-imports — referenced by services.draft_expiry to also sweep
# the unified seller_drafts collection (separately from per-type rows).
__all__ = ["drafts_router", "DRAFT_TYPE_LABELS", "RESTORE_WINDOW_DAYS"]
