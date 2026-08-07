"""
iter447 — Vehicle Dealer Multi-Lot CSV Bulk Import
====================================================

Extension of iter306. Adds preview/confirm/capacity/template endpoints
and per-cell bilingual errors, while keeping the original
`POST /vehicle-multi-lot-auctions/{event_id}/bulk-import` endpoint
for backward compatibility.

Endpoints:
  GET  /vehicle-multi-lot-auctions/{event_id}/bulk-import/capacity
    → { used, max, remaining }  — remaining vehicle capacity in the event

  GET  /vehicle-multi-lot-auctions/{event_id}/bulk-import/template
    → text/csv                  — column contract + 2 sample rows

  POST /vehicle-multi-lot-auctions/{event_id}/bulk-import/preview
    body: { lots: [...] }
    → { total_rows, remaining_capacity, total_errors, can_import,
        preview: [{row, raw, normalized, errors}], columns }
    Validates every row + cross-checks duplicate VINs in three scopes:
      1. same batch
      2. lots already inside this event
      3. dealer's OTHER open (draft/upcoming/live) multi-lot events
         AND single-vehicle listings
    No writes.

  POST /vehicle-multi-lot-auctions/{event_id}/bulk-import/confirm
    body: { lots: [...] }
    → { ok, created, event_id, lot_ids, remaining_capacity }
    ATOMIC. Any single error blocks the entire batch. The event's
    500-vehicle cap is enforced (200 existing + 300 upload = 500 ok;
    200 + 350 = rejected).

  POST /vehicle-multi-lot-auctions/{event_id}/bulk-import
    Kept from iter306 for backward compatibility. Under the hood it
    invokes the new preview+confirm path, so callers using the
    original endpoint automatically get the tighter rules.

Rules:
  • MAX_LOTS_PER_IMPORT       = 500
  • MAX_LOTS_PER_EVENT        = 500
  • VIN 17 chars, uppercase alnum (no I O Q)
  • Bill 96 title_fr required for QC lots
  • Bulk-imported lots always land as `status="draft_no_photos"`
  • The publish gate (≥ 1 photo per lot) is enforced in the
    `POST /vehicle-multi-lot-auctions/{event_id}/activate` route
    of `routes/vehicle_multi_lot.py`.
"""
import csv
import io
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from deps import User, get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/vehicle-multi-lot-auctions",
    tags=["multi-lot-bulk-import"],
)

MAX_LOTS_PER_IMPORT = 500
MAX_LOTS_PER_EVENT = 500

# Multi-lot event statuses considered OPEN — any existing lot in one
# of these blocks a duplicate VIN. Ended/cancelled do not block reuse.
OPEN_EVENT_STATUSES = {"draft", "upcoming", "live", "scheduled", "pending"}

# Single-vehicle listing statuses considered OPEN for VIN-conflict
# purposes.
OPEN_VEHICLE_STATUSES = {"draft", "pending", "active", "upcoming", "live", "scheduled"}

# Valid VIN body: 17 chars, uppercase A-Z/0-9 minus I, O, Q.
_VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


# ─────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────

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
    bid_increment: Optional[float] = 100.0
    location_city: str
    location_province: str
    title: str
    title_fr: Optional[str] = ""
    description: Optional[str] = ""


class BulkImportBody(BaseModel):
    lots: List[BulkImportLot] = Field(..., min_length=1)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _row_error(row: int, field: str, code: str, message_en: str, message_fr: str, **extra) -> dict:
    """Bilingual per-cell error record. `row` is 1-indexed (first data row = 1)."""
    payload = {
        "row": row,
        "field": field,
        "code": code,
        "message_en": f"Row {row} — Field '{field}': {message_en}",
        "message_fr": f"Ligne {row} — Champ « {field} » : {message_fr}",
    }
    payload.update(extra)
    return payload


async def _ensure_event(db, event_id: str, user: dict) -> dict:
    event = await db.vehicle_multi_lot_auctions.find_one({"id": event_id})
    if not event:
        raise HTTPException(status_code=404, detail={
            "code": "event_not_found",
            "message_en": "Multi-lot event not found.",
            "message_fr": "Événement multi-lots introuvable.",
        })
    is_admin = user.get("role") in {"admin", "super_admin"}
    if event.get("seller_id") != user["id"] and not is_admin:
        raise HTTPException(status_code=403, detail={
            "code": "not_your_event",
            "message_en": "Not your event.",
            "message_fr": "Cet événement ne vous appartient pas.",
        })
    if user.get("vehicle_dealer_suspended") is True and not is_admin:
        raise HTTPException(status_code=403, detail={
            "code": "dealer_suspended",
            "message_en": "Your dealer account is currently suspended by an administrator. Please contact support.",
            "message_fr": "Votre compte concessionnaire est actuellement suspendu par un administrateur. Veuillez contacter le support.",
        })
    return event


async def _load_existing_vins(db, event_id: str, seller_id: str) -> dict[str, dict]:
    """Return dict of VIN.upper() → conflict record for VINs already
    used by the dealer on OTHER open surfaces:
      • lots inside this event
      • lots inside dealer's OTHER open multi-lot events
      • dealer's single-vehicle listings still open
    """
    conflicts: dict[str, dict] = {}

    events = await db.vehicle_multi_lot_auctions.find(
        {"seller_id": seller_id, "status": {"$in": list(OPEN_EVENT_STATUSES)}},
        {"_id": 0, "id": 1, "title": 1, "status": 1, "lots.vin": 1, "lots.id": 1},
    ).to_list(length=500)
    for ev in events:
        ev_id = ev.get("id")
        is_this_event = (ev_id == event_id)
        for lot in ev.get("lots") or []:
            v = str(lot.get("vin") or "").strip().upper()
            if not v or v in conflicts:
                continue
            conflicts[v] = {
                "scope": "same_event" if is_this_event else "other_event",
                "event_id": ev_id,
                "event_title": ev.get("title"),
                "event_status": ev.get("status"),
                "lot_id": lot.get("id"),
            }

    try:
        vehicles = await db.vehicle_listings.find(
            {
                "seller_id": seller_id,
                "status": {"$in": list(OPEN_VEHICLE_STATUSES)},
            },
            {"_id": 0, "id": 1, "vin": 1, "status": 1, "title": 1},
        ).to_list(length=500)
        for veh in vehicles:
            v = str(veh.get("vin") or "").strip().upper()
            if not v or v in conflicts:
                continue
            conflicts[v] = {
                "scope": "single_listing",
                "listing_id": veh.get("id"),
                "listing_status": veh.get("status"),
                "listing_title": veh.get("title"),
            }
    except Exception as e:  # noqa: BLE001
        logger.debug("vehicle_listings scan skipped: %s", e)

    return conflicts


def _validate_lot(row: int, lot_dict: dict) -> tuple[list[dict], dict]:
    """Full per-cell validation. Returns (errors, normalised_lot)."""
    errors: list[dict] = []

    vin_raw = (lot_dict.get("vin") or "").strip().upper()
    if not vin_raw:
        errors.append(_row_error(row, "vin", "vin_required",
            "VIN is required.", "NIV requis."))
    elif len(vin_raw) != 17:
        errors.append(_row_error(row, "vin", "vin_length_invalid",
            "VIN must be exactly 17 characters.",
            "Le NIV doit comporter exactement 17 caractères."))
    elif not _VIN_RE.match(vin_raw):
        errors.append(_row_error(row, "vin", "vin_charset_invalid",
            "VIN must be 17 uppercase alphanumeric characters (letters I, O and Q are not allowed).",
            "Le NIV doit contenir 17 caractères alphanumériques majuscules (les lettres I, O et Q sont interdites)."))

    year_raw = lot_dict.get("year")
    year: Optional[int] = None
    try:
        year = int(year_raw) if year_raw not in (None, "") else None
    except (TypeError, ValueError):
        year = None
    if year is None:
        errors.append(_row_error(row, "year", "year_required",
            "Year is required.", "Année requise."))
    elif year < 1900 or year > 2100:
        errors.append(_row_error(row, "year", "year_out_of_range",
            "Year must be between 1900 and 2100.",
            "L'année doit être entre 1900 et 2100."))

    make = (lot_dict.get("make") or "").strip()
    if not make:
        errors.append(_row_error(row, "make", "make_required",
            "Make is required.", "Marque requise."))
    model = (lot_dict.get("model") or "").strip()
    if not model:
        errors.append(_row_error(row, "model", "model_required",
            "Model is required.", "Modèle requis."))

    starting_price: Optional[float] = None
    sp_raw = lot_dict.get("starting_price")
    if sp_raw in (None, ""):
        errors.append(_row_error(row, "starting_price", "starting_price_required",
            "Starting price is required.", "Prix de départ requis."))
    else:
        try:
            starting_price = float(sp_raw)
            if starting_price <= 0:
                errors.append(_row_error(row, "starting_price", "starting_price_not_positive",
                    "Starting price must be greater than 0.",
                    "Le prix de départ doit être supérieur à 0."))
            elif starting_price > 10_000_000:
                errors.append(_row_error(row, "starting_price", "starting_price_too_high",
                    "Starting price must be less than 10,000,000.",
                    "Le prix de départ doit être inférieur à 10 000 000."))
        except (TypeError, ValueError):
            errors.append(_row_error(row, "starting_price", "starting_price_not_numeric",
                "Starting price must be a number.",
                "Le prix de départ doit être un nombre."))

    reserve_price: Optional[float] = None
    rp_raw = lot_dict.get("reserve_price")
    if rp_raw not in (None, ""):
        try:
            reserve_price = float(rp_raw)
            if starting_price is not None and reserve_price < starting_price:
                errors.append(_row_error(row, "reserve_price", "reserve_below_starting",
                    "Reserve price must be greater than or equal to the starting price.",
                    "Le prix de réserve doit être supérieur ou égal au prix de départ."))
        except (TypeError, ValueError):
            errors.append(_row_error(row, "reserve_price", "reserve_not_numeric",
                "Reserve price must be a number.",
                "Le prix de réserve doit être un nombre."))

    bid_increment: float = 100.0
    bi_raw = lot_dict.get("bid_increment")
    if bi_raw not in (None, ""):
        try:
            bid_increment = float(bi_raw)
            if bid_increment < 1:
                errors.append(_row_error(row, "bid_increment", "bid_increment_too_low",
                    "Bid increment must be at least 1.",
                    "L'incrément d'enchère doit être d'au moins 1."))
        except (TypeError, ValueError):
            errors.append(_row_error(row, "bid_increment", "bid_increment_not_numeric",
                "Bid increment must be a number.",
                "L'incrément d'enchère doit être un nombre."))

    city = (lot_dict.get("location_city") or "").strip()
    if not city:
        errors.append(_row_error(row, "location_city", "city_required",
            "City is required.", "Ville requise."))
    province = (lot_dict.get("location_province") or "").strip().upper()
    if not province:
        errors.append(_row_error(row, "location_province", "province_required",
            "Province is required.", "Province requise."))
    elif len(province) != 2:
        errors.append(_row_error(row, "location_province", "province_invalid",
            "Province must be a 2-letter code (e.g. ON, QC, BC).",
            "La province doit être un code à 2 lettres (p. ex. ON, QC, BC)."))

    title_en = (lot_dict.get("title") or "").strip()
    if not title_en:
        errors.append(_row_error(row, "title", "title_required",
            "Title (English) is required.", "Titre (anglais) requis."))
    title_fr = (lot_dict.get("title_fr") or "").strip()
    if province == "QC" and not title_fr:
        errors.append(_row_error(row, "title_fr", "bill96_title_fr_required",
            "Bill 96 requires a French title for QC lots.",
            "La Loi 96 exige un titre français pour les lots du Québec."))

    mileage: Optional[int] = None
    m_raw = lot_dict.get("mileage")
    if m_raw not in (None, ""):
        try:
            mileage = int(float(m_raw))
            if mileage < 0:
                errors.append(_row_error(row, "mileage", "mileage_negative",
                    "Mileage cannot be negative.",
                    "Le kilométrage ne peut pas être négatif."))
        except (TypeError, ValueError):
            errors.append(_row_error(row, "mileage", "mileage_not_integer",
                "Mileage must be a whole number.",
                "Le kilométrage doit être un nombre entier."))

    normalized = {
        "vin": vin_raw,
        "year": year,
        "make": make,
        "model": model,
        "trim": (lot_dict.get("trim") or "").strip(),
        "body_type": (lot_dict.get("body_type") or "sedan").strip().lower(),
        "mileage": mileage if mileage is not None else 0,
        "engine_size": (lot_dict.get("engine_size") or "").strip(),
        "transmission": (lot_dict.get("transmission") or "automatic").strip().lower(),
        "drivetrain": (lot_dict.get("drivetrain") or "fwd").strip().lower(),
        "fuel_type": (lot_dict.get("fuel_type") or "gasoline").strip().lower(),
        "exterior_color": (lot_dict.get("exterior_color") or "").strip(),
        "condition_rating": (lot_dict.get("condition_rating") or "good").strip().lower(),
        "title_status": (lot_dict.get("title_status") or "clean").strip().lower(),
        "starting_price": starting_price,
        "reserve_price": reserve_price,
        "bid_increment": bid_increment,
        "location_city": city,
        "location_province": province,
        "title": title_en,
        "title_fr": title_fr,
        "description": (lot_dict.get("description") or "").strip(),
    }
    return errors, normalized


def _detect_within_batch_duplicates(rows: list[dict]) -> list[dict]:
    """Flag rows whose VIN duplicates an earlier row in the same batch."""
    seen: dict[str, int] = {}
    errors: list[dict] = []
    for row_num, r in enumerate(rows, start=1):
        v = (r.get("vin") or "").strip().upper()
        if not v or len(v) != 17:
            continue
        if v in seen:
            first = seen[v]
            errors.append(_row_error(row_num, "vin", "duplicate_vin_in_batch",
                f"Duplicate VIN — same as row {first} in this batch.",
                f"NIV en double — identique à la ligne {first} de ce lot."))
        else:
            seen[v] = row_num
    return errors


def _detect_existing_vin_conflicts(
    rows: list[dict], existing_vins: dict[str, dict],
) -> list[dict]:
    """Flag rows whose VIN conflicts with dealer's OTHER open listings."""
    errors: list[dict] = []
    for row_num, r in enumerate(rows, start=1):
        v = (r.get("vin") or "").strip().upper()
        if not v:
            continue
        conflict = existing_vins.get(v)
        if not conflict:
            continue
        scope = conflict.get("scope")
        if scope == "same_event":
            en = ("VIN is already listed as a lot in this event "
                  f"(lot #{str(conflict.get('lot_id'))[:8]}).")
            fr = ("Le NIV est déjà inscrit comme lot dans cet événement "
                  f"(lot n° {str(conflict.get('lot_id'))[:8]}).")
        elif scope == "other_event":
            en = ("VIN is already in another open multi-lot event: "
                  f"'{conflict.get('event_title')}' ({conflict.get('event_status')}).")
            fr = ("Le NIV est déjà dans un autre événement multi-lots ouvert : "
                  f"« {conflict.get('event_title')} » ({conflict.get('event_status')}).")
        else:
            en = ("VIN is already an active single-vehicle listing: "
                  f"'{conflict.get('listing_title')}' ({conflict.get('listing_status')}).")
            fr = ("Le NIV est déjà une annonce de véhicule active : "
                  f"« {conflict.get('listing_title')} » ({conflict.get('listing_status')}).")
        errors.append(_row_error(
            row_num, "vin", "duplicate_vin_across_dealer",
            en, fr, conflict=conflict,
        ))
    return errors


def _event_is_editable(event: dict) -> bool:
    """Bulk import is only allowed on non-live events (draft/upcoming)."""
    return (event.get("status") or "draft") in {"draft", "upcoming", "scheduled"}


# ─────────────────────────────────────────────────────────────
# CAPACITY
# ─────────────────────────────────────────────────────────────

@router.get("/{event_id}/bulk-import/capacity")
async def get_bulk_import_capacity(
    event_id: str, current_user: User = Depends(get_current_user),
):
    db = get_db()
    event = await _ensure_event(db, event_id, current_user.__dict__ if hasattr(current_user, "__dict__") else current_user.model_dump())
    used = len(event.get("lots") or [])
    remaining = max(0, MAX_LOTS_PER_EVENT - used)
    return {
        "event_id": event_id,
        "event_title": event.get("title"),
        "event_status": event.get("status"),
        "editable": _event_is_editable(event),
        "used": used,
        "max": MAX_LOTS_PER_EVENT,
        "remaining": remaining,
        "max_per_import": MAX_LOTS_PER_IMPORT,
    }


# ─────────────────────────────────────────────────────────────
# TEMPLATE
# ─────────────────────────────────────────────────────────────

CSV_COLUMNS_TEMPLATE = [
    "vin", "year", "make", "model", "trim", "body_type", "mileage",
    "engine_size", "transmission", "drivetrain", "fuel_type",
    "exterior_color", "condition_rating", "title_status",
    "starting_price", "reserve_price", "bid_increment",
    "location_city", "location_province",
    "title", "title_fr", "description",
]


@router.get("/{event_id}/bulk-import/template")
async def get_bulk_import_template(
    event_id: str, current_user: User = Depends(get_current_user),
):
    db = get_db()
    await _ensure_event(db, event_id, current_user.__dict__ if hasattr(current_user, "__dict__") else current_user.model_dump())

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_COLUMNS_TEMPLATE)
    w.writerow([
        "1HGBH41JXMN109186", "2020", "Toyota", "Camry", "XSE", "sedan",
        "52000", "2.5L I4", "automatic", "fwd", "gasoline", "Pearl White",
        "good", "clean", "8500", "", "100", "Toronto", "ON",
        "2020 Toyota Camry XSE", "2020 Toyota Camry XSE",
        "Clean 1-owner trade-in.",
    ])
    w.writerow([
        "1FTFW1ET9DFA12345", "2019", "Ford", "F-150", "XLT", "truck",
        "82000", "5.0L V8", "automatic", "4wd", "gasoline",
        "Oxford White", "good", "clean", "12000", "15000", "100",
        "Montréal", "QC", "2019 Ford F-150 XLT",
        "2019 Ford F-150 XLT — camion de travail",
        "4x4 work truck.",
    ])
    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=bidvex_multi_lot_bulk_template.csv"
        },
    )


# ─────────────────────────────────────────────────────────────
# PREVIEW
# ─────────────────────────────────────────────────────────────

@router.post("/{event_id}/bulk-import/preview")
async def preview_bulk_import(
    event_id: str, body: BulkImportBody,
    current_user: User = Depends(get_current_user),
):
    """Validate every row + surface duplicate-VIN conflicts. No writes."""
    db = get_db()
    user_dict = current_user.__dict__ if hasattr(current_user, "__dict__") else current_user.model_dump()
    event = await _ensure_event(db, event_id, user_dict)

    if not _event_is_editable(event):
        raise HTTPException(status_code=409, detail={
            "code": "event_not_editable",
            "message_en": "This event is live or ended — bulk import is only allowed on draft/upcoming events.",
            "message_fr": "Cet événement est en direct ou terminé — l'importation groupée n'est autorisée que sur les événements brouillon/à venir.",
        })

    lots_in = body.lots
    if len(lots_in) == 0:
        raise HTTPException(status_code=400, detail={
            "code": "empty_batch",
            "message_en": "At least one row is required.",
            "message_fr": "Au moins une ligne est requise.",
        })
    if len(lots_in) > MAX_LOTS_PER_IMPORT:
        raise HTTPException(status_code=400, detail={
            "code": "max_lots_exceeded",
            "message_en": f"Maximum {MAX_LOTS_PER_IMPORT} lots per import. You supplied {len(lots_in)}.",
            "message_fr": f"Maximum {MAX_LOTS_PER_IMPORT} lots par importation. Vous en avez fourni {len(lots_in)}.",
        })

    used = len(event.get("lots") or [])
    remaining = max(0, MAX_LOTS_PER_EVENT - used)
    capacity_exceeded = len(lots_in) > remaining

    preview_rows: list[dict] = []
    normalized_list: list[dict] = []
    for idx, lot in enumerate(lots_in, start=1):
        errs, norm = _validate_lot(idx, lot.model_dump())
        preview_rows.append({
            "row": idx,
            "raw": lot.model_dump(),
            "normalized": norm,
            "errors": errs,
        })
        normalized_list.append(norm)

    for de in _detect_within_batch_duplicates(normalized_list):
        for pr in preview_rows:
            if pr["row"] == de["row"]:
                pr["errors"].append(de)
                break

    existing_vins = await _load_existing_vins(db, event_id, event["seller_id"])
    for de in _detect_existing_vin_conflicts(normalized_list, existing_vins):
        for pr in preview_rows:
            if pr["row"] == de["row"]:
                pr["errors"].append(de)
                break

    total_errors = sum(len(r["errors"]) for r in preview_rows)

    return {
        "event_id": event_id,
        "event_title": event.get("title"),
        "total_rows": len(preview_rows),
        "used_capacity": used,
        "max_capacity": MAX_LOTS_PER_EVENT,
        "remaining_capacity": remaining,
        "capacity_exceeded": capacity_exceeded,
        "total_errors": total_errors,
        "can_import": (
            total_errors == 0
            and len(preview_rows) > 0
            and not capacity_exceeded
        ),
        "preview": preview_rows,
        "columns": CSV_COLUMNS_TEMPLATE,
    }


# ─────────────────────────────────────────────────────────────
# CONFIRM  (atomic — all or none)
# ─────────────────────────────────────────────────────────────

async def _validate_and_build_lots(
    db, event: dict, lots_in: list[BulkImportLot],
) -> tuple[list[dict], list[dict]]:
    """Runs the full validation stack and returns (errors, lot_docs).
    lot_docs are ready to be inserted into `event.lots` in one shot."""
    all_errors: list[dict] = []
    normalized_list: list[dict] = []
    for idx, lot in enumerate(lots_in, start=1):
        errs, norm = _validate_lot(idx, lot.model_dump())
        all_errors.extend(errs)
        normalized_list.append(norm)

    all_errors.extend(_detect_within_batch_duplicates(normalized_list))
    existing_vins = await _load_existing_vins(db, event["id"], event["seller_id"])
    all_errors.extend(_detect_existing_vin_conflicts(normalized_list, existing_vins))

    if all_errors:
        return all_errors, []

    now = datetime.now(timezone.utc)
    lot_docs: list[dict] = []
    for norm in normalized_list:
        lot_id = str(uuid.uuid4())
        lot_docs.append({
            "id": lot_id,
            "vin": norm["vin"],
            "year": int(norm["year"]),
            "make": norm["make"],
            "model": norm["model"],
            "trim": norm["trim"],
            "body_type": norm["body_type"],
            "mileage": int(norm["mileage"] or 0),
            "engine_size": norm["engine_size"],
            "transmission": norm["transmission"],
            "drivetrain": norm["drivetrain"],
            "fuel_type": norm["fuel_type"],
            "exterior_color": norm["exterior_color"],
            "condition_rating": norm["condition_rating"],
            "title_status": norm["title_status"],
            "starting_price": float(norm["starting_price"]),
            "reserve_price": (
                float(norm["reserve_price"])
                if norm["reserve_price"] is not None else None
            ),
            "bid_increment": float(norm["bid_increment"] or 100),
            "location_city": norm["location_city"],
            "location_province": norm["location_province"],
            "title": norm["title"],
            "title_fr": norm["title_fr"],
            "description": norm["description"],
            "media": [],
            # Bulk-imported lots ALWAYS start as `draft_no_photos`.
            # The event `activate` route (iter447) will refuse to
            # promote until every lot has ≥ 1 photo.
            "status": "draft_no_photos",
            "current_bid": float(norm["starting_price"]),
            "bid_count": 0,
            "start_time": None,
            "end_time": None,
            "created_at": now,
            "updated_at": now,
            "imported_via_csv": True,
        })
    return [], lot_docs


@router.post("/{event_id}/bulk-import/confirm")
async def confirm_bulk_import(
    event_id: str, body: BulkImportBody,
    current_user: User = Depends(get_current_user),
):
    """Atomic bulk import — any single error blocks the whole batch.
    Repeat imports into the same event are supported up to the 500-cap."""
    db = get_db()
    user_dict = current_user.__dict__ if hasattr(current_user, "__dict__") else current_user.model_dump()
    event = await _ensure_event(db, event_id, user_dict)

    if not _event_is_editable(event):
        raise HTTPException(status_code=409, detail={
            "code": "event_not_editable",
            "message_en": "This event is live or ended — bulk import is only allowed on draft/upcoming events.",
            "message_fr": "Cet événement est en direct ou terminé — l'importation groupée n'est autorisée que sur les événements brouillon/à venir.",
        })
    if len(body.lots) == 0:
        raise HTTPException(status_code=400, detail={
            "code": "empty_batch",
            "message_en": "At least one row is required.",
            "message_fr": "Au moins une ligne est requise.",
        })
    if len(body.lots) > MAX_LOTS_PER_IMPORT:
        raise HTTPException(status_code=400, detail={
            "code": "max_lots_exceeded",
            "message_en": f"Maximum {MAX_LOTS_PER_IMPORT} lots per import.",
            "message_fr": f"Maximum {MAX_LOTS_PER_IMPORT} lots par importation.",
        })

    used = len(event.get("lots") or [])
    remaining = max(0, MAX_LOTS_PER_EVENT - used)
    if len(body.lots) > remaining:
        return {
            "ok": False,
            "code": "capacity_exceeded",
            "message_en": (
                f"This event already holds {used} lots. Only {remaining} more "
                f"can be added (500-vehicle cap). You supplied {len(body.lots)}."
            ),
            "message_fr": (
                f"Cet événement contient déjà {used} lots. Seuls {remaining} "
                f"supplémentaires peuvent être ajoutés (plafond de 500 véhicules). "
                f"Vous en avez fourni {len(body.lots)}."
            ),
            "used_capacity": used,
            "max_capacity": MAX_LOTS_PER_EVENT,
            "remaining_capacity": remaining,
            "supplied": len(body.lots),
            "created": 0,
            "errors": [],
        }

    errors, lot_docs = await _validate_and_build_lots(db, event, body.lots)
    if errors:
        return {
            "ok": False,
            "code": "validation_failed",
            "message_en": (
                "Some rows still have errors. Fix them in the review table "
                "before confirming the batch."
            ),
            "message_fr": (
                "Certaines lignes contiennent encore des erreurs. Corrigez-les "
                "dans le tableau d'examen avant de confirmer le lot."
            ),
            "errors": errors,
            "created": 0,
            "used_capacity": used,
            "max_capacity": MAX_LOTS_PER_EVENT,
            "remaining_capacity": remaining,
        }

    now = datetime.now(timezone.utc)
    await db.vehicle_multi_lot_auctions.update_one(
        {"id": event_id},
        {"$push": {"lots": {"$each": lot_docs}},
         "$set":  {"updated_at": now}},
    )
    new_used = used + len(lot_docs)
    return {
        "ok": True,
        "event_id": event_id,
        "created": len(lot_docs),
        "lot_ids": [d["id"] for d in lot_docs],
        "used_capacity": new_used,
        "max_capacity": MAX_LOTS_PER_EVENT,
        "remaining_capacity": max(0, MAX_LOTS_PER_EVENT - new_used),
        "message_en": (
            f"{len(lot_docs)} lot(s) added. Add at least one photo per lot "
            f"before going live."
        ),
        "message_fr": (
            f"{len(lot_docs)} lot(s) ajouté(s). Ajoutez au moins une photo "
            f"par lot avant de passer en direct."
        ),
    }


# ─────────────────────────────────────────────────────────────
# LEGACY (iter306) — kept for backward compatibility.
# ─────────────────────────────────────────────────────────────

@router.post("/{event_id}/bulk-import")
async def bulk_import_lots_legacy(
    event_id: str, body: BulkImportBody,
    current_user: User = Depends(get_current_user),
):
    """Legacy iter306 endpoint — now internally uses the iter447 preview
    + confirm path. Behaviour is IDENTICAL to `/bulk-import/confirm`
    except that it also returns a truncated `errors[]` list on legacy
    validation failure for the older frontend to consume."""
    return await confirm_bulk_import(event_id, body, current_user)
