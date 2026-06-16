"""
iter306 — CSV Bulk Import of Lots into a Multi-Lot Vehicle Auction event
=========================================================================
POST /api/vehicle-multi-lot-auctions/{event_id}/bulk-import

Body: {
  lots: [
    {
      vin, year, make, model, trim?, body_type?, mileage?, engine_size?,
      transmission?, drivetrain?, fuel_type?, exterior_color?, condition_rating?,
      title_status?, starting_price, reserve_price?, bid_increment?,
      location_city, location_province, title (EN), title_fr?, description?
    },
    ...
  ]
}

Rules:
  • Maximum 50 lots per import
  • Required per row: vin (17 chars), year, make, model, starting_price, location_city,
    location_province, title
  • Bill 96 — `title_fr` REQUIRED when location_province == "QC"
  • Each created lot is in `draft` status (photos must be added before Live)
  • Lots are appended to the event's lots array; existing lots are preserved
  • Event must belong to the calling user (dealer scope)

Returns: { ok, created: N, errors: [{row, message_en, message_fr}], lot_ids: [...] }
"""
from datetime import datetime, timezone
import uuid
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import User, get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vehicle-multi-lot-auctions", tags=["multi-lot-bulk-import"])

MAX_LOTS_PER_IMPORT = 50


class BulkImportLot(BaseModel):
    vin: str
    year: int
    make: str
    model: str
    trim: Optional[str] = ""
    body_type: Optional[str] = "sedan"
    mileage: Optional[int] = 0
    engine_size: Optional[str] = ""
    transmission: Optional[str] = "automatic"
    drivetrain: Optional[str] = "fwd"
    fuel_type: Optional[str] = "gasoline"
    exterior_color: Optional[str] = ""
    condition_rating: Optional[str] = "good"
    title_status: Optional[str] = "clean"
    starting_price: float
    reserve_price: Optional[float] = None
    bid_increment: Optional[float] = 100
    location_city: str
    location_province: str
    title: str
    title_fr: Optional[str] = ""
    description: Optional[str] = ""


class BulkImportBody(BaseModel):
    lots: List[BulkImportLot] = Field(..., min_length=1)


def _validate_lot(row_idx: int, lot: BulkImportLot):
    """Returns (errors_en, errors_fr) — empty lists if valid."""
    en, fr = [], []
    vin = (lot.vin or "").strip().upper()
    if len(vin) != 17:
        en.append("VIN must be exactly 17 characters")
        fr.append("Le NIV doit comporter exactement 17 caractères")
    if not lot.year or lot.year < 1900 or lot.year > 2100:
        en.append("Year must be between 1900 and 2100")
        fr.append("L'année doit être entre 1900 et 2100")
    if not (lot.make or "").strip():
        en.append("Make is required")
        fr.append("Marque requise")
    if not (lot.model or "").strip():
        en.append("Model is required")
        fr.append("Modèle requis")
    if not lot.starting_price or lot.starting_price <= 0:
        en.append("Starting price must be > 0")
        fr.append("Prix de départ > 0 requis")
    if not (lot.location_city or "").strip():
        en.append("City is required")
        fr.append("Ville requise")
    province = (lot.location_province or "").strip().upper()
    if not province:
        en.append("Province is required")
        fr.append("Province requise")
    if not (lot.title or "").strip():
        en.append("Title (English) is required")
        fr.append("Titre (anglais) requis")
    if province == "QC" and not (lot.title_fr or "").strip():
        en.append("Bill 96: title_fr is required for QC lots")
        fr.append("Loi 96: titre français requis pour les lots du Québec")
    return en, fr


@router.post("/{event_id}/bulk-import")
async def bulk_import_lots(
    event_id: str,
    body: BulkImportBody,
    current_user: User = Depends(get_current_user),
):
    db = get_db()
    if len(body.lots) > MAX_LOTS_PER_IMPORT:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "max_lots_exceeded",
                "message_en": f"Maximum {MAX_LOTS_PER_IMPORT} lots per import",
                "message_fr": f"Maximum {MAX_LOTS_PER_IMPORT} lots par importation",
            },
        )

    event = await db.vehicle_multi_lot_auctions.find_one({"id": event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.get("seller_id") != current_user.id and not (
        getattr(current_user, "role", "") in {"admin", "super_admin"}
    ):
        raise HTTPException(status_code=403, detail="Not authorized for this event")

    errors = []
    new_lots = []
    lot_ids = []

    for idx, lot in enumerate(body.lots, start=1):
        en, fr = _validate_lot(idx, lot)
        if en:
            errors.append({
                "row": idx,
                "vin": (lot.vin or "")[-6:] if lot.vin else "",
                "message_en": "; ".join(en),
                "message_fr": "; ".join(fr),
            })
            continue

        lot_id = str(uuid.uuid4())
        lot_doc = {
            "id": lot_id,
            "event_id": event_id,
            "vin": lot.vin.strip().upper(),
            "year": int(lot.year),
            "make": lot.make.strip(),
            "model": lot.model.strip(),
            "trim": (lot.trim or "").strip(),
            "body_type": lot.body_type or "sedan",
            "mileage": int(lot.mileage or 0),
            "engine_size": lot.engine_size or "",
            "transmission": lot.transmission or "automatic",
            "drivetrain": lot.drivetrain or "fwd",
            "fuel_type": lot.fuel_type or "gasoline",
            "exterior_color": lot.exterior_color or "",
            "condition_rating": lot.condition_rating or "good",
            "title_status": lot.title_status or "clean",
            "starting_price": float(lot.starting_price),
            "reserve_price": (float(lot.reserve_price) if lot.reserve_price else None),
            "bid_increment": float(lot.bid_increment or 100),
            "location_city": lot.location_city.strip(),
            "location_province": lot.location_province.strip().upper(),
            "title": lot.title.strip(),
            "title_fr": (lot.title_fr or "").strip(),
            "description": (lot.description or "").strip(),
            "media": [],
            # New lots from CSV are drafts that need photos.
            "status": "draft_no_photos",
            "current_bid": float(lot.starting_price),
            "bid_count": 0,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "imported_via_csv": True,
        }
        new_lots.append(lot_doc)
        lot_ids.append(lot_id)

    if new_lots:
        # Append lots to the event AND mirror to flat collection (multi_lot_lots)
        # if the schema uses it; the existing routes use both patterns. We follow
        # the embedded pattern for backward compatibility.
        await db.vehicle_multi_lot_auctions.update_one(
            {"id": event_id},
            {
                "$push": {"lots": {"$each": new_lots}},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

    return {
        "ok": True,
        "event_id": event_id,
        "created": len(new_lots),
        "errors": errors,
        "lot_ids": lot_ids,
    }
