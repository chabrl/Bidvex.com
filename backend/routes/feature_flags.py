"""
Feature Flags + Vehicle Auctions Waitlist — iter176
====================================================

Feature flags system for gating surfaces like /vehicle-auctions.
Admin can toggle ON/OFF; public endpoint returns current state
with 60s client cache.

Also exposes the vehicle-auctions waitlist (public signup + admin count).

Endpoints
---------
  Admin-only (require_admin):
    GET   /api/admin/feature-flags                      list all
    PATCH /api/admin/feature-flags/{key}                { enabled: bool }
    GET   /api/admin/waitlist/vehicle-auctions/count    count
    GET   /api/admin/waitlist/vehicle-auctions          list (limit 500)

  Public (no auth):
    GET  /api/feature-flags/{key}                       { key, enabled }
    POST /api/waitlist/vehicle-auctions                 { email, lang }

Seed defaults
-------------
`vehicle_auctions_enabled` defaults to `enabled=false` (Coming Soon mode)
on first read. Subsequent admin toggles are persisted.
"""
from datetime import datetime, timezone
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field, field_validator

from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)

# Whitelist of managed flags so admins can't mint arbitrary keys.
KNOWN_FLAGS: dict[str, dict] = {
    "vehicle_auctions_enabled": {
        "default": False,
        "description_en": "Toggle the vehicle auctions page on or off for all users. When disabled, visitors see a Coming Soon page with a waitlist form.",
        "description_fr": "Activer ou désactiver la page d'enchères de véhicules pour tous les utilisateurs. Lorsque désactivée, les visiteurs voient une page « Bientôt disponible » avec un formulaire d'inscription.",
    },
}


async def _get_or_seed_flag(db, key: str) -> dict:
    """Fetch the flag from Mongo; seed it with default if missing."""
    if key not in KNOWN_FLAGS:
        raise HTTPException(status_code=404, detail="flag_not_found")
    doc = await db.feature_flags.find_one({"key": key}, {"_id": 0})
    if doc:
        return doc
    # Seed
    now = datetime.now(timezone.utc)
    seeded = {
        "key": key,
        "enabled": KNOWN_FLAGS[key]["default"],
        "updated_at": now.isoformat(),
        "updated_by": "system:seed",
    }
    try:
        await db.feature_flags.insert_one({**seeded})
    except Exception as e:
        logger.warning(f"[FEATURE_FLAGS] seed insert failed for {key}: {e}")
    return seeded


# ── Admin router ───────────────────────────────────────────────
admin_feature_flags_router = APIRouter(tags=["Feature Flags (Admin)"])


class FeatureFlagUpdate(BaseModel):
    enabled: bool


@admin_feature_flags_router.get("/admin/feature-flags")
async def admin_list_feature_flags(_: User = Depends(require_admin)):
    """List every known flag (seed-if-missing)."""
    db = get_db()
    out = []
    for key, meta in KNOWN_FLAGS.items():
        doc = await _get_or_seed_flag(db, key)
        out.append({
            **doc,
            "description_en": meta["description_en"],
            "description_fr": meta["description_fr"],
        })
    return {"flags": out}


@admin_feature_flags_router.patch("/admin/feature-flags/{key}")
async def admin_update_feature_flag(
    key: str,
    payload: FeatureFlagUpdate,
    current_user: User = Depends(require_admin),
):
    """Toggle a single feature flag."""
    if key not in KNOWN_FLAGS:
        raise HTTPException(status_code=404, detail="flag_not_found")
    db = get_db()
    now = datetime.now(timezone.utc)
    await db.feature_flags.update_one(
        {"key": key},
        {"$set": {
            "key": key,
            "enabled": bool(payload.enabled),
            "updated_at": now.isoformat(),
            "updated_by": current_user.email,
        }},
        upsert=True,
    )
    doc = await db.feature_flags.find_one({"key": key}, {"_id": 0})
    logger.info(f"[FEATURE_FLAGS] {current_user.email} toggled {key} → enabled={doc.get('enabled')}")
    return doc


# ── Public router ──────────────────────────────────────────────
public_feature_flags_router = APIRouter(tags=["Feature Flags (Public)"])


@public_feature_flags_router.get("/feature-flags/{key}")
async def public_get_feature_flag(key: str, response: Response):
    """Public read with 60s client-side cache."""
    if key not in KNOWN_FLAGS:
        raise HTTPException(status_code=404, detail="flag_not_found")
    db = get_db()
    doc = await _get_or_seed_flag(db, key)
    response.headers["Cache-Control"] = "public, max-age=60"
    return {"key": key, "enabled": bool(doc.get("enabled", False))}


# ── Vehicle waitlist ───────────────────────────────────────────
waitlist_router = APIRouter(tags=["Vehicle Auctions Waitlist"])
admin_waitlist_router = APIRouter(tags=["Vehicle Auctions Waitlist (Admin)"])


class VehicleWaitlistSignup(BaseModel):
    email: EmailStr
    lang: str = Field(default="en")

    @field_validator("lang")
    @classmethod
    def _vl(cls, v):
        v = (v or "en").lower()
        if v not in {"en", "fr"}:
            v = "en"
        return v


@waitlist_router.post("/waitlist/vehicle-auctions")
async def join_vehicle_waitlist(payload: VehicleWaitlistSignup, request: Request):
    """Public: join the vehicle-auctions waitlist. Upsert on email.

    EmailStr already validates the address shape — no need for a second regex.
    """
    email = payload.email.strip().lower()

    db = get_db()
    now = datetime.now(timezone.utc)
    existing = await db.vehicle_waitlist.find_one({"email": email}, {"_id": 0})

    update_doc = {
        "$set": {
            "email": email,
            "lang": payload.lang,
            "updated_at": now.isoformat(),
            "ip": (request.client.host if request.client else None),
        },
        "$setOnInsert": {
            "id": str(uuid.uuid4()),
            "created_at": now.isoformat(),
        },
    }
    await db.vehicle_waitlist.update_one({"email": email}, update_doc, upsert=True)

    return {
        "success": True,
        "already_on_list": bool(existing),
        "lang": payload.lang,
    }


@admin_waitlist_router.get("/admin/waitlist/vehicle-auctions/count")
async def admin_waitlist_count(_: User = Depends(require_admin)):
    db = get_db()
    count = await db.vehicle_waitlist.count_documents({})
    return {"count": count}


@admin_waitlist_router.get("/admin/waitlist/vehicle-auctions")
async def admin_waitlist_list(
    _: User = Depends(require_admin),
    limit: int = 500,
):
    db = get_db()
    items = await db.vehicle_waitlist.find({}, {"_id": 0}).sort("created_at", -1).limit(max(1, min(limit, 2000))).to_list(limit)
    return {"items": items, "count": len(items)}
