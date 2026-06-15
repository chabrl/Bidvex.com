"""
iter304 — Lot Templates for Multi-Lot Vehicle Auctions
========================================================
CRUD endpoints for dealer lot templates. A template lets a dealer save a
reusable set of "common" fields (Make/Model/Body/Engine/Transmission/etc.)
that auto-fills Steps 2–5 of the per-lot wizard during multi-lot creation.

Endpoints:
  GET    /api/lot-templates              — list current dealer's templates
  POST   /api/lot-templates              — create new template (max 20/dealer)
  PUT    /api/lot-templates/{id}         — update existing template
  DELETE /api/lot-templates/{id}         — delete template

Fields stored per template:
  make, model, body_type, engine_size, transmission, drivetrain, fuel_type,
  exterior_color, interior_color, doors, seats,
  starting_price, reserve_price, bid_increment,
  location_city, location_province,
  title_status, condition_rating
  (VIN / Year / Mileage / Photos NOT stored — always unique per vehicle)
"""
from datetime import datetime, timezone
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

from deps import User, get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lot-templates", tags=["lot-templates"])

MAX_TEMPLATES_PER_DEALER = 20


class LotTemplateFields(BaseModel):
    make: Optional[str] = ""
    model: Optional[str] = ""
    body_type: Optional[str] = ""
    engine_size: Optional[str] = ""
    transmission: Optional[str] = ""
    drivetrain: Optional[str] = ""
    fuel_type: Optional[str] = ""
    exterior_color: Optional[str] = ""
    interior_color: Optional[str] = ""
    doors: Optional[str] = ""
    seats: Optional[str] = ""
    starting_price: Optional[float] = 0
    reserve_price: Optional[float] = None
    bid_increment: Optional[float] = 100
    location_city: Optional[str] = ""
    location_province: Optional[str] = ""
    title_status: Optional[str] = "clean"
    condition_rating: Optional[str] = "good"


class LotTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    fields: LotTemplateFields


class LotTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=60)
    fields: Optional[LotTemplateFields] = None


def _serialize(doc: dict) -> dict:
    """Strip Mongo internal _id."""
    if doc is None:
        return None
    out = {k: v for k, v in doc.items() if k != "_id"}
    return out


@router.get("")
async def list_templates(current_user: User = Depends(get_current_user)):
    """Returns the current dealer's saved lot templates (sorted by recent)."""
    db = get_db()
    cursor = db.lot_templates.find({"dealer_id": current_user.id}).sort("created_at", -1)
    items = [_serialize(d) async for d in cursor]
    return {"items": items, "count": len(items), "max": MAX_TEMPLATES_PER_DEALER}


@router.post("")
async def create_template(body: LotTemplateCreate, current_user: User = Depends(get_current_user)):
    """Create a new lot template (max 20 per dealer)."""
    db = get_db()
    current_count = await db.lot_templates.count_documents({"dealer_id": current_user.id})
    if current_count >= MAX_TEMPLATES_PER_DEALER:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "max_templates_reached",
                "message_en": f"Maximum {MAX_TEMPLATES_PER_DEALER} templates allowed.",
                "message_fr": f"Maximum {MAX_TEMPLATES_PER_DEALER} modèles autorisés.",
            },
        )
    doc = {
        "id": str(uuid.uuid4()),
        "dealer_id": current_user.id,
        "name": body.name.strip(),
        "fields": body.fields.model_dump(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await db.lot_templates.insert_one(doc)
    return _serialize(doc)


@router.put("/{template_id}")
async def update_template(template_id: str, body: LotTemplateUpdate, current_user: User = Depends(get_current_user)):
    """Update name and/or fields of an existing template."""
    db = get_db()
    existing = await db.lot_templates.find_one({"id": template_id, "dealer_id": current_user.id})
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    update_set = {"updated_at": datetime.now(timezone.utc)}
    if body.name is not None:
        update_set["name"] = body.name.strip()
    if body.fields is not None:
        update_set["fields"] = body.fields.model_dump()
    await db.lot_templates.update_one(
        {"id": template_id, "dealer_id": current_user.id},
        {"$set": update_set},
    )
    refreshed = await db.lot_templates.find_one({"id": template_id, "dealer_id": current_user.id})
    return _serialize(refreshed)


@router.delete("/{template_id}")
async def delete_template(template_id: str, current_user: User = Depends(get_current_user)):
    """Delete a lot template owned by the current dealer."""
    db = get_db()
    res = await db.lot_templates.delete_one({"id": template_id, "dealer_id": current_user.id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"ok": True, "id": template_id}
