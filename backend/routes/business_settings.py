"""iter476 — Shared Business Settings / Billing Profile.

One endpoint set, used by four dashboards (Seller / Partner / Vehicle
Dealer / Storage Facility). Owner-only: a business can only edit its
OWN billing profile.

Fields (reuses existing ``db.users`` columns wherever possible):
  • name / company_name                  (existing — legal display name)
  • business_address                     (new)
  • phone                                (existing — reused)
  • email                                (existing — read-only)
  • gst_number                           (new — CRA GST/HST registration)
  • qst_number                           (new — Revenu QC QST registration)
  • tax_number                           (existing — kept as generic fallback)
  • logo_url                             (new — public S3 URL)
  • logo_storage_path                    (new — private S3 key for delete)

Logo constraints: max 2 MB. Accept PNG / JPG / JPEG / SVG.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from deps import get_current_user, User, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/business-settings", tags=["business-settings"])

MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2 MB
ALLOWED_LOGO_TYPES = {
    "image/png":     "png",
    "image/jpeg":    "jpg",
    "image/jpg":     "jpg",
    "image/svg+xml": "svg",
}


def init(_db):
    """Kept for compatibility with server.py's dynamic loader. This
    module actually depends on `deps.get_db` — the argument is ignored."""
    return None


class BusinessProfileUpdate(BaseModel):
    business_name:    Optional[str] = Field(None, max_length=200)
    business_address: Optional[str] = Field(None, max_length=500)
    phone:            Optional[str] = Field(None, max_length=40)
    gst_number:       Optional[str] = Field(None, max_length=32)
    qst_number:       Optional[str] = Field(None, max_length=32)
    tax_number:       Optional[str] = Field(None, max_length=64)


PROFILE_PROJECTION = {
    "_id": 0, "id": 1, "email": 1, "name": 1, "company_name": 1,
    "business_address": 1, "phone": 1, "gst_number": 1,
    "qst_number": 1, "tax_number": 1, "logo_url": 1,
    "logo_storage_path": 1, "role": 1, "seller_type": 1,
}


@router.get("/me")
async def get_my_business_profile(
    user: User = Depends(get_current_user),
    db = Depends(get_db),
):
    """Return the current caller's business/billing profile."""
    doc = await db.users.find_one({"id": user.id}, PROFILE_PROJECTION) or {}
    return {
        "id":               doc.get("id", user.id),
        "email":            doc.get("email", ""),
        "business_name":    doc.get("company_name") or doc.get("name") or "",
        "business_address": doc.get("business_address") or "",
        "phone":            doc.get("phone") or "",
        "gst_number":       doc.get("gst_number") or "",
        "qst_number":       doc.get("qst_number") or "",
        "tax_number":       doc.get("tax_number") or "",
        "logo_url":         doc.get("logo_url") or "",
        "role":             doc.get("role", ""),
        "seller_type":      doc.get("seller_type", ""),
    }


@router.put("/me")
async def update_my_business_profile(
    body: BusinessProfileUpdate,
    user: User = Depends(get_current_user),
    db = Depends(get_db),
):
    """Owner-only update of the caller's billing profile."""
    payload = body.dict(exclude_none=True, exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates: Dict[str, Any] = {}
    if "business_name" in payload:
        updates["company_name"] = (payload["business_name"] or "").strip()
    if "business_address" in payload:
        updates["business_address"] = (payload["business_address"] or "").strip()
    if "phone" in payload:
        updates["phone"] = (payload["phone"] or "").strip()
    for k in ("gst_number", "qst_number", "tax_number"):
        if k in payload:
            v = (payload[k] or "").strip()
            v = re.sub(r"[^A-Za-z0-9\-\s/]", "", v)[:32]
            updates[k] = v
    updates["billing_profile_updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.users.update_one({"id": user.id}, {"$set": updates})
    return await get_my_business_profile(user=user, db=db)


@router.post("/me/logo")
async def upload_business_logo(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db = Depends(get_db),
):
    """Upload / replace a business logo. Owner-only. Max 2 MB. PNG/JPG/SVG."""
    ctype = (file.content_type or "").lower()
    if ctype not in ALLOWED_LOGO_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported logo type: {ctype}. Use PNG/JPG/SVG.",
        )
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty upload")
    if len(contents) > MAX_LOGO_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Logo exceeds 2 MB limit ({len(contents)} bytes)",
        )

    from services.cloud_storage import (
        store_business_logo, delete_business_logo,
    )
    ext = ALLOWED_LOGO_TYPES[ctype]
    key, public_url = await store_business_logo(user.id, contents, ctype, ext)
    prev = await db.users.find_one(
        {"id": user.id}, {"_id": 0, "logo_storage_path": 1}
    )
    if prev and prev.get("logo_storage_path"):
        try:
            await delete_business_logo(prev["logo_storage_path"])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[business-settings] failed to remove previous logo: {e}")

    await db.users.update_one(
        {"id": user.id},
        {"$set": {
            "logo_url":          public_url,
            "logo_storage_path": key,
            "logo_updated_at":   datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"logo_url": public_url}


@router.delete("/me/logo")
async def remove_business_logo(
    user: User = Depends(get_current_user),
    db = Depends(get_db),
):
    """Remove the caller's business logo. Owner-only."""
    doc = await db.users.find_one(
        {"id": user.id}, {"_id": 0, "logo_storage_path": 1}
    ) or {}
    if doc.get("logo_storage_path"):
        try:
            from services.cloud_storage import delete_business_logo
            await delete_business_logo(doc["logo_storage_path"])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[business-settings] logo delete: {e}")
    await db.users.update_one(
        {"id": user.id},
        {"$unset": {"logo_url": "", "logo_storage_path": ""}},
    )
    return {"ok": True}
