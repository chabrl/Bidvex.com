"""
BidVex — Storage Facility CSV Bulk Import
==========================================

5-step wizard for VERIFIED storage facilities to bulk-upload up to 50
storage-unit auctions:

  1. GET  /api/storage-facilities/bulk-import/template
        Fixed CSV template (no buyer_premium column; 5 % is platform-fixed)

  2. POST /api/storage-facilities/bulk-import
        PREVIEW ONLY — parses + validates every row, returns per-cell
        bilingual errors + duplicate-unit conflicts (batch + facility's
        existing drafts / open auctions). NO writes.

  3. POST /api/storage-facilities/bulk-import/confirm
        Facility ACTIVELY accepts a bilingual legal-notice at this step.
        Server re-validates, enforces the 50-row cap, dedupes across the
        batch + open auctions, and writes each row to `storage_auctions`
        with `status="draft"`, `photos=[]`, `source="csv_bulk_import"`,
        and stamps the acceptance on every draft.

  4. POST /api/storage-facilities/bulk-import/{auction_id}/photos
        Append photos to a specific bulk draft.

  5. POST /api/storage-facilities/bulk-import/{auction_id}/publish
     POST /api/storage-facilities/bulk-import/publish-batch
        Flip drafts to `active` (or `upcoming` if start_time is in the
        future). Requires ≥ 1 photo per draft — no photo, no publish.

  GET  /api/storage-facilities/bulk-import/pending
        Return every bulk draft owned by the caller + photo status.

Rules:
  • 5 % buyer's premium is FIXED PLATFORM POLICY (iter445). The template
    has NO `buyer_premium` column; the server stamps `buyer_premium_pct=5.0`
    on every draft. No facility can bypass or change this.
  • Partner, Vehicle imports, fee rules, and existing live listings are
    NOT touched by this module.
"""
import csv
import io
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Request, UploadFile, File,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from deps import User, get_current_user, get_db
from rate_limit import limiter as _limiter
from models.storage_auction import (
    UNIT_SIZES, UNIT_TYPES, PAYMENT_METHODS,
)

logger = logging.getLogger(__name__)

storage_bulk_import_router = APIRouter(tags=["Storage Bulk Import"])

MAX_ROWS_PER_IMPORT = 50

# CSV column contract — order matches the downloadable template.
# NO `buyer_premium` column: platform-fixed 5 %.
# NO `accepted_legal_notice` column: acceptance is captured actively in
# the wizard at the Confirm step, not parsed from CSV values.
CSV_COLUMNS = [
    "unit_number",
    "unit_size",
    "unit_type",
    "is_lien_unit",
    "past_due_balance",
    "description_en",
    "description_fr",
    "video_url",
    "starting_price",
    "reserve_price",
    "bid_increment",
    "start_time",
    "end_time",
    "cleanup_deadline_hours",
    "payment_method",
    "currency",
    "deposit_required",
    "deposit_amount",
    "deposit_type",
]

CSV_REQUIRED = {
    "unit_number",
    "unit_size",
    "unit_type",
    "description_en",
    "starting_price",
    "start_time",
    "end_time",
}

VALID_CURRENCIES = {"CAD", "USD"}
VALID_DEPOSIT_TYPES = {"fixed", "percentage"}

# Auction statuses considered OPEN — a duplicate unit_number in any of
# these blocks a new bulk import. Anything not in this set (ended, sold,
# cancelled, expired, closed) means the unit_number is free to reuse.
OPEN_STATUSES = {"draft", "upcoming", "active", "scheduled", "live", "pending"}


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

async def _facility_for_user(db, user_id: str) -> Optional[dict]:
    return await db.storage_facilities.find_one(
        {"owner_user_id": user_id}, {"_id": 0}
    )


async def _require_verified_facility(current_user: User = Depends(get_current_user)):
    """Copy of the guard used by the single-form route; kept local so the
    wizard remains self-contained but semantically identical."""
    db = get_db()
    fac = await _facility_for_user(db, current_user.id)
    if not fac:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "no_facility_profile",
                "message_en": "No facility profile found for this account.",
                "message_fr": "Aucun profil de facilité trouvé pour ce compte.",
            },
        )
    if fac.get("status") != "verified":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "facility_not_verified",
                "message_en": "Your facility account is not yet verified by BidVex.",
                "message_fr": "Votre compte de facilité n'est pas encore vérifié par BidVex.",
            },
        )
    reg_verified = fac.get("company_registration_verified")
    if reg_verified is False:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "company_registration_not_verified",
                "message_en": (
                    "Your business-registration document is awaiting admin review. "
                    "You'll be able to list units once it is verified."
                ),
                "message_fr": (
                    "Votre document d'enregistrement d'entreprise est en attente "
                    "d'examen par l'administrateur. Vous pourrez lister des unités "
                    "une fois qu'il sera vérifié."
                ),
            },
        )
    return fac


def _row_error(row: int, field: str, code: str, message_en: str, message_fr: str) -> dict:
    """Bilingual per-cell error record; row is 1-indexed relative to the
    CSV (row 2 = first data row after the header)."""
    return {
        "row": row,
        "field": field,
        "code": code,
        "message_en": f"Row {row} — Field '{field}': {message_en}",
        "message_fr": f"Ligne {row} — Champ « {field} » : {message_fr}",
    }


def _norm_bool(v: Any) -> bool:
    """Accept 'Y', 'yes', 'true', '1', 'oui' as truthy — everything else falsy."""
    if v is None:
        return False
    return str(v).strip().lower() in {"y", "yes", "true", "1", "oui"}


def _parse_dt(v: str) -> Optional[datetime]:
    if not v:
        return None
    try:
        s = str(v).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:  # noqa: BLE001
        return None


async def _existing_open_unit_numbers(db, facility_id: str) -> dict[str, dict]:
    """Return a dict of `unit_number.lower()` → summary of open auctions
    owned by this facility. Used to block duplicate unit_number entries
    at import time.

    Only OPEN statuses (draft / upcoming / active / scheduled / live /
    pending) are included. Ended / sold / cancelled auctions free the
    unit_number for reuse.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    open_rows = await db.storage_auctions.find(
        {
            "facility_id": facility_id,
            "$or": [
                {"status": {"$in": list(OPEN_STATUSES)}},
                # Legacy rows without explicit status but with end_time
                # in the future are treated as open.
                {
                    "status": {"$exists": False},
                    "end_time": {"$gt": now_iso},
                },
            ],
        },
        {
            "_id": 0, "id": 1, "unit_number": 1, "status": 1,
            "end_time": 1, "start_time": 1,
        },
    ).to_list(length=2000)
    out: dict[str, dict] = {}
    for r in open_rows:
        u = str(r.get("unit_number") or "").strip().lower()
        if not u:
            continue
        # First one wins — deterministic reporting.
        if u not in out:
            out[u] = {
                "auction_id": r.get("id"),
                "unit_number": r.get("unit_number"),
                "status": r.get("status") or "active",
            }
    return out


def _validate_row(
    row_num: int,
    row: dict,
    is_quebec_facility: bool,
) -> tuple[list[dict], dict]:
    """Returns (errors, normalized_row). errors=[] means row is
    import-ready pending duplicate / cross-batch checks.
    """
    errors: list[dict] = []

    # ── unit_number ─────────────────────────────────────────────
    unit_number = (row.get("unit_number") or "").strip()
    if not unit_number:
        errors.append(_row_error(
            row_num, "unit_number", "unit_number_required",
            "Unit number is required.", "Numéro d'unité requis.",
        ))
    elif len(unit_number) > 40:
        errors.append(_row_error(
            row_num, "unit_number", "unit_number_too_long",
            "Unit number must be 40 characters or fewer.",
            "Le numéro d'unité doit contenir 40 caractères ou moins.",
        ))

    # ── unit_size ───────────────────────────────────────────────
    unit_size = (row.get("unit_size") or "").strip()
    if not unit_size:
        errors.append(_row_error(
            row_num, "unit_size", "unit_size_required",
            f"Unit size is required. Allowed: {', '.join(UNIT_SIZES)}.",
            f"Taille d'unité requise. Autorisées : {', '.join(UNIT_SIZES)}.",
        ))
    elif unit_size not in UNIT_SIZES:
        errors.append(_row_error(
            row_num, "unit_size", "unit_size_invalid",
            f"Unit size must be one of: {', '.join(UNIT_SIZES)}.",
            f"La taille d'unité doit être l'une de : {', '.join(UNIT_SIZES)}.",
        ))

    # ── unit_type ───────────────────────────────────────────────
    unit_type = (row.get("unit_type") or "").strip().lower()
    if not unit_type:
        errors.append(_row_error(
            row_num, "unit_type", "unit_type_required",
            f"Unit type is required. Allowed: {', '.join(UNIT_TYPES)}.",
            f"Type d'unité requis. Autorisés : {', '.join(UNIT_TYPES)}.",
        ))
    elif unit_type not in UNIT_TYPES:
        errors.append(_row_error(
            row_num, "unit_type", "unit_type_invalid",
            f"Unit type must be one of: {', '.join(UNIT_TYPES)}.",
            f"Le type d'unité doit être l'un de : {', '.join(UNIT_TYPES)}.",
        ))

    # ── is_lien_unit + past_due_balance ────────────────────────
    is_lien = _norm_bool(row.get("is_lien_unit"))
    past_due = None
    raw_pd = str(row.get("past_due_balance") or "").strip()
    if raw_pd:
        try:
            past_due = float(raw_pd)
            if past_due < 0:
                errors.append(_row_error(
                    row_num, "past_due_balance", "past_due_negative",
                    "Past-due balance must be zero or positive.",
                    "Le solde impayé doit être égal ou supérieur à zéro.",
                ))
        except ValueError:
            errors.append(_row_error(
                row_num, "past_due_balance", "past_due_not_numeric",
                "Past-due balance must be a number.",
                "Le solde impayé doit être un nombre.",
            ))
    if is_lien and (past_due is None or past_due <= 0):
        errors.append(_row_error(
            row_num, "past_due_balance", "past_due_required_for_lien",
            "Past-due balance is required and must be > 0 when the unit is a lien unit.",
            "Le solde impayé est requis et doit être supérieur à 0 pour une unité sous privilège.",
        ))

    # ── description_en (≥ 10 chars, mirrors single form) ──────
    description_en = (row.get("description_en") or "").strip()
    if not description_en:
        errors.append(_row_error(
            row_num, "description_en", "description_en_required",
            "English description is required.",
            "La description anglaise est requise.",
        ))
    elif len(description_en) < 10:
        errors.append(_row_error(
            row_num, "description_en", "description_en_too_short",
            "English description must be at least 10 characters.",
            "La description anglaise doit contenir au moins 10 caractères.",
        ))

    # ── description_fr (Bill 96: required for QC facilities) ───
    description_fr = (row.get("description_fr") or "").strip()
    if is_quebec_facility and not description_fr:
        errors.append(_row_error(
            row_num, "description_fr", "bill96_description_fr_required",
            "Bill 96 requires a French description for Quebec facilities.",
            "La Loi 96 exige une description française pour les facilités québécoises.",
        ))

    # ── starting_price ─────────────────────────────────────────
    starting_price = None
    raw_sp = str(row.get("starting_price") or "").strip()
    if not raw_sp:
        errors.append(_row_error(
            row_num, "starting_price", "starting_price_required",
            "Starting price is required.",
            "Le prix de départ est requis.",
        ))
    else:
        try:
            starting_price = float(raw_sp)
            if starting_price < 1 or starting_price > 100000:
                errors.append(_row_error(
                    row_num, "starting_price", "starting_price_out_of_range",
                    "Starting price must be between 1 and 100,000.",
                    "Le prix de départ doit être compris entre 1 et 100 000.",
                ))
        except ValueError:
            errors.append(_row_error(
                row_num, "starting_price", "starting_price_not_numeric",
                "Starting price must be a number.",
                "Le prix de départ doit être un nombre.",
            ))

    # ── reserve_price (optional; if present, ≥ starting) ──────
    reserve_price = None
    raw_rp = str(row.get("reserve_price") or "").strip()
    if raw_rp:
        try:
            reserve_price = float(raw_rp)
            if starting_price is not None and reserve_price < starting_price:
                errors.append(_row_error(
                    row_num, "reserve_price", "reserve_below_starting",
                    "Reserve price must be greater than or equal to the starting price.",
                    "Le prix de réserve doit être supérieur ou égal au prix de départ.",
                ))
        except ValueError:
            errors.append(_row_error(
                row_num, "reserve_price", "reserve_not_numeric",
                "Reserve price must be a number.",
                "Le prix de réserve doit être un nombre.",
            ))

    # ── bid_increment (optional; default 10) ──────────────────
    bid_increment = 10.0
    raw_bi = str(row.get("bid_increment") or "").strip()
    if raw_bi:
        try:
            bid_increment = float(raw_bi)
            if bid_increment < 1:
                errors.append(_row_error(
                    row_num, "bid_increment", "bid_increment_too_low",
                    "Bid increment must be at least 1.",
                    "L'incrément d'enchère doit être d'au moins 1.",
                ))
        except ValueError:
            errors.append(_row_error(
                row_num, "bid_increment", "bid_increment_not_numeric",
                "Bid increment must be a number.",
                "L'incrément d'enchère doit être un nombre.",
            ))

    # ── start_time / end_time ─────────────────────────────────
    start_time = _parse_dt(row.get("start_time"))
    end_time = _parse_dt(row.get("end_time"))
    if not row.get("start_time") or not str(row.get("start_time")).strip():
        errors.append(_row_error(
            row_num, "start_time", "start_time_required",
            "Start time is required (ISO 8601, e.g. 2026-06-15T18:00:00).",
            "Heure de début requise (ISO 8601, ex. : 2026-06-15T18:00:00).",
        ))
    elif start_time is None:
        errors.append(_row_error(
            row_num, "start_time", "start_time_invalid",
            "Start time must be a valid ISO datetime.",
            "L'heure de début doit être une date ISO valide.",
        ))
    if not row.get("end_time") or not str(row.get("end_time")).strip():
        errors.append(_row_error(
            row_num, "end_time", "end_time_required",
            "End time is required (ISO 8601, e.g. 2026-06-22T18:00:00).",
            "Heure de fin requise (ISO 8601, ex. : 2026-06-22T18:00:00).",
        ))
    elif end_time is None:
        errors.append(_row_error(
            row_num, "end_time", "end_time_invalid",
            "End time must be a valid ISO datetime.",
            "L'heure de fin doit être une date ISO valide.",
        ))
    if start_time and end_time:
        if start_time >= end_time:
            errors.append(_row_error(
                row_num, "end_time", "end_before_start",
                "End time must be after start time.",
                "L'heure de fin doit être postérieure à l'heure de début.",
            ))
        if end_time <= datetime.now(timezone.utc):
            errors.append(_row_error(
                row_num, "end_time", "end_time_past",
                "End time must be in the future.",
                "L'heure de fin doit être dans le futur.",
            ))

    # ── cleanup_deadline_hours (default 72; 24-168) ───────────
    cleanup = 72
    raw_cd = str(row.get("cleanup_deadline_hours") or "").strip()
    if raw_cd:
        try:
            cleanup = int(float(raw_cd))
            if cleanup < 24 or cleanup > 168:
                errors.append(_row_error(
                    row_num, "cleanup_deadline_hours", "cleanup_out_of_range",
                    "Cleanup deadline must be between 24 and 168 hours.",
                    "Le délai de nettoyage doit être entre 24 et 168 heures.",
                ))
        except ValueError:
            errors.append(_row_error(
                row_num, "cleanup_deadline_hours", "cleanup_not_integer",
                "Cleanup deadline must be an integer number of hours.",
                "Le délai de nettoyage doit être un entier en heures.",
            ))

    # ── payment_method (default stripe) ───────────────────────
    payment_method = (row.get("payment_method") or "stripe").strip().lower()
    if payment_method not in PAYMENT_METHODS:
        errors.append(_row_error(
            row_num, "payment_method", "payment_method_invalid",
            f"Payment method must be one of: {', '.join(PAYMENT_METHODS)}.",
            f"Le mode de paiement doit être l'un de : {', '.join(PAYMENT_METHODS)}.",
        ))

    # ── currency (default CAD) ─────────────────────────────────
    currency = (row.get("currency") or "CAD").strip().upper()
    if currency not in VALID_CURRENCIES:
        errors.append(_row_error(
            row_num, "currency", "currency_invalid",
            f"Currency must be one of: {', '.join(sorted(VALID_CURRENCIES))}.",
            f"La devise doit être l'une de : {', '.join(sorted(VALID_CURRENCIES))}.",
        ))

    # ── deposit block ─────────────────────────────────────────
    deposit_required = _norm_bool(row.get("deposit_required"))
    deposit_amount = None
    raw_da = str(row.get("deposit_amount") or "").strip()
    if raw_da:
        try:
            deposit_amount = float(raw_da)
        except ValueError:
            errors.append(_row_error(
                row_num, "deposit_amount", "deposit_amount_not_numeric",
                "Deposit amount must be a number.",
                "Le montant du dépôt doit être un nombre.",
            ))
    deposit_type = (row.get("deposit_type") or "").strip().lower() or None
    if deposit_type and deposit_type not in VALID_DEPOSIT_TYPES:
        errors.append(_row_error(
            row_num, "deposit_type", "deposit_type_invalid",
            f"Deposit type must be one of: {', '.join(sorted(VALID_DEPOSIT_TYPES))}.",
            f"Le type de dépôt doit être l'un de : {', '.join(sorted(VALID_DEPOSIT_TYPES))}.",
        ))
    if deposit_required:
        if deposit_amount is None or deposit_amount <= 0:
            errors.append(_row_error(
                row_num, "deposit_amount", "deposit_amount_required",
                "Deposit amount must be greater than 0 when a deposit is required.",
                "Le montant du dépôt doit être supérieur à 0 lorsqu'un dépôt est requis.",
            ))
        if not deposit_type:
            deposit_type = "fixed"
        # Percentage sanity check
        if deposit_type == "percentage" and deposit_amount is not None and (
            deposit_amount < 1 or deposit_amount > 100
        ):
            errors.append(_row_error(
                row_num, "deposit_amount", "deposit_percentage_out_of_range",
                "Deposit percentage must be between 1 and 100.",
                "Le pourcentage du dépôt doit être compris entre 1 et 100.",
            ))
    else:
        # If not required, clear deposit_type / amount for consistency
        deposit_amount = None
        deposit_type = None

    normalized = {
        "unit_number": unit_number,
        "unit_size": unit_size,
        "unit_type": unit_type,
        "is_lien_unit": is_lien,
        "past_due_balance": past_due,
        "description_en": description_en,
        "description_fr": description_fr,
        "video_url": (row.get("video_url") or "").strip() or None,
        "starting_price": starting_price,
        "reserve_price": reserve_price,
        "bid_increment": bid_increment,
        "start_time": start_time.isoformat() if start_time else None,
        "end_time": end_time.isoformat() if end_time else None,
        "cleanup_deadline_hours": cleanup,
        "payment_method": payment_method,
        "currency": currency,
        "deposit_required": deposit_required,
        "deposit_amount": deposit_amount,
        "deposit_type": deposit_type,
    }
    return errors, normalized


def _detect_within_batch_duplicates(rows: list[dict]) -> list[dict]:
    """Flag rows whose `unit_number` (case-insensitive) already appeared
    earlier in the same batch. Points the facility at the FIRST matching
    row so they can fix quickly.
    """
    seen: dict[str, int] = {}
    errors: list[dict] = []
    for row_num, r in enumerate(rows, start=2):
        u = (r.get("unit_number") or "").strip().lower()
        if not u:
            continue
        if u in seen:
            first = seen[u]
            errors.append(_row_error(
                row_num, "unit_number", "duplicate_unit_in_batch",
                f"Duplicate unit number — same as row {first} in this batch.",
                f"Numéro d'unité en double — identique à la ligne {first} de ce lot.",
            ))
        else:
            seen[u] = row_num
    return errors


def _detect_facility_open_conflicts(
    rows: list[dict],
    open_units: dict[str, dict],
) -> list[dict]:
    """Flag rows whose `unit_number` conflicts with an open auction /
    draft already owned by this facility. Ended / cancelled auctions
    do NOT block reuse (they're not in `open_units`).
    """
    errors: list[dict] = []
    for row_num, r in enumerate(rows, start=2):
        u = (r.get("unit_number") or "").strip().lower()
        if not u:
            continue
        conflict = open_units.get(u)
        if not conflict:
            continue
        status = conflict.get("status") or "active"
        errors.append({
            "row": row_num,
            "field": "unit_number",
            "code": "duplicate_unit_in_facility",
            "message_en": (
                f"Row {row_num} — Field 'unit_number': Unit '{conflict.get('unit_number')}' "
                f"already exists as an open {status} auction "
                f"(listing #{conflict.get('auction_id')}). Change the unit number, "
                f"or wait until that auction ends or is cancelled."
            ),
            "message_fr": (
                f"Ligne {row_num} — Champ « unit_number » : L'unité "
                f"« {conflict.get('unit_number')} » existe déjà en tant "
                f"qu'enchère {status} ouverte (annonce n° {conflict.get('auction_id')}). "
                f"Changez le numéro d'unité ou attendez la fin ou l'annulation de "
                f"cette enchère."
            ),
            "conflict_auction_id": conflict.get("auction_id"),
            "conflict_status": status,
        })
    return errors


def _is_quebec_facility(facility: dict) -> bool:
    return str(facility.get("province") or "").strip().upper() in ("QC", "QUEBEC")


# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────

@storage_bulk_import_router.get("/storage-facilities/bulk-import/template")
async def get_storage_csv_template(facility=Depends(_require_verified_facility)):
    """Fixed CSV template + 2 example rows. Auth-gated to verified
    storage facilities."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)

    now = datetime.now(timezone.utc)
    # Example 1 — indoor 10x10, non-lien, stripe payment, no deposit.
    writer.writerow([
        "A-101",                                      # unit_number
        "10x10",                                      # unit_size
        "indoor",                                     # unit_type
        "N",                                          # is_lien_unit
        "",                                           # past_due_balance
        "Household items — boxes, furniture, small appliances visible.",
        "Articles ménagers — boîtes, meubles, petits électroménagers visibles.",
        "",                                           # video_url
        "50.00",                                      # starting_price
        "",                                           # reserve_price
        "10",                                         # bid_increment
        (now + timedelta(days=1)).isoformat(),        # start_time
        (now + timedelta(days=8)).isoformat(),        # end_time
        "72",                                         # cleanup_deadline_hours
        "stripe",                                     # payment_method
        "CAD",                                        # currency
        "N",                                          # deposit_required
        "",                                           # deposit_amount
        "",                                           # deposit_type
    ])
    # Example 2 — lien unit, drive-up, with deposit.
    writer.writerow([
        "B-42",
        "10x20",
        "drive_up",
        "Y",
        "845.50",
        "Lien unit — tools, workshop equipment visible through door.",
        "Unité sous privilège — outils, équipement d'atelier visibles à travers la porte.",
        "",
        "100.00",
        "300.00",
        "25",
        (now + timedelta(days=2)).isoformat(),
        (now + timedelta(days=10)).isoformat(),
        "72",
        "cash",
        "CAD",
        "Y",
        "100.00",
        "fixed",
    ])

    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),  # BOM for Excel
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                "attachment; filename=bidvex_storage_bulk_import_template.csv"
            )
        },
    )


@storage_bulk_import_router.post("/storage-facilities/bulk-import")
@_limiter.limit("30/minute")
async def preview_storage_bulk_import(
    request: Request,
    file: UploadFile = File(...),
    facility=Depends(_require_verified_facility),
):
    """PREVIEW ONLY — parses + validates the CSV, returns per-cell
    bilingual errors + duplicate-unit conflicts (batch AND facility's
    open auctions). NO writes."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail={
            "code": "invalid_file_type",
            "message_en": "Only CSV files are accepted.",
            "message_fr": "Seuls les fichiers CSV sont acceptés.",
        })

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail={
            "code": "file_too_large",
            "message_en": "File too large (max 5 MB).",
            "message_fr": "Fichier trop volumineux (max. 5 Mo).",
        })

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_encoding",
            "message_en": "Invalid file encoding (UTF-8 required).",
            "message_fr": "Encodage de fichier invalide (UTF-8 requis).",
        })

    reader = csv.DictReader(io.StringIO(text))
    headers = {h.strip() for h in (reader.fieldnames or [])}
    missing_headers = CSV_REQUIRED - headers
    if missing_headers:
        raise HTTPException(status_code=400, detail={
            "code": "missing_columns",
            "message_en": (
                f"Missing required columns: {', '.join(sorted(missing_headers))}. "
                f"Download the template."
            ),
            "message_fr": (
                f"Colonnes obligatoires manquantes : {', '.join(sorted(missing_headers))}. "
                f"Téléchargez le modèle."
            ),
        })

    raw_rows = [
        r for r in reader
        if any((v or "").strip() for v in (r or {}).values())
    ]
    if len(raw_rows) == 0:
        raise HTTPException(status_code=400, detail={
            "code": "no_rows",
            "message_en": "The CSV has no data rows.",
            "message_fr": "Le fichier CSV ne contient aucune ligne de données.",
        })
    if len(raw_rows) > MAX_ROWS_PER_IMPORT:
        raise HTTPException(status_code=400, detail={
            "code": "row_limit_exceeded",
            "message_en": (
                f"Maximum {MAX_ROWS_PER_IMPORT} rows per import. "
                f"Your file has {len(raw_rows)}."
            ),
            "message_fr": (
                f"Maximum {MAX_ROWS_PER_IMPORT} lignes par importation. "
                f"Votre fichier en contient {len(raw_rows)}."
            ),
        })

    is_qc = _is_quebec_facility(facility)
    db = get_db()
    open_units = await _existing_open_unit_numbers(db, facility["id"])

    preview_rows: list[dict] = []
    normalized_list: list[dict] = []
    for row_num, raw in enumerate(raw_rows, start=2):
        errs, norm = _validate_row(row_num, raw, is_qc)
        preview_rows.append({
            "row": row_num,
            "raw": raw,
            "normalized": norm,
            "errors": errs,
        })
        normalized_list.append(norm)

    # Duplicate detection — batch first, then facility open auctions.
    for de in _detect_within_batch_duplicates(normalized_list):
        for pr in preview_rows:
            if pr["row"] == de["row"]:
                pr["errors"].append(de)
                break
    for de in _detect_facility_open_conflicts(normalized_list, open_units):
        for pr in preview_rows:
            if pr["row"] == de["row"]:
                pr["errors"].append(de)
                break

    total_errors = sum(len(r["errors"]) for r in preview_rows)

    return {
        "total_rows": len(preview_rows),
        "max_rows": MAX_ROWS_PER_IMPORT,
        "total_errors": total_errors,
        "can_import": total_errors == 0 and len(preview_rows) > 0,
        "preview": preview_rows,
        "columns": CSV_COLUMNS,
        "required_columns": sorted(CSV_REQUIRED),
        "facility": {
            "id": facility.get("id"),
            "name": facility.get("company_name"),
            "province": facility.get("province"),
            "is_quebec": is_qc,
        },
    }


class StorageBulkConfirmRow(BaseModel):
    unit_number: str
    unit_size: str
    unit_type: str
    is_lien_unit: bool = False
    past_due_balance: Optional[float] = None
    description_en: str
    description_fr: Optional[str] = ""
    video_url: Optional[str] = None
    starting_price: float
    reserve_price: Optional[float] = None
    bid_increment: float = 10.0
    start_time: str
    end_time: str
    cleanup_deadline_hours: int = 72
    payment_method: str = "stripe"
    currency: str = "CAD"
    deposit_required: bool = False
    deposit_amount: Optional[float] = None
    deposit_type: Optional[str] = None


class StorageBulkConfirmBody(BaseModel):
    rows: list[StorageBulkConfirmRow] = Field(default_factory=list)
    # Facility ACTIVELY accepts the bilingual legal notice at Confirm step.
    # Spreadsheet values do NOT satisfy this requirement.
    accepted_legal_notice: bool = False


@storage_bulk_import_router.post("/storage-facilities/bulk-import/confirm")
@_limiter.limit("10/minute")
async def confirm_storage_bulk_import(
    request: Request,
    body: StorageBulkConfirmBody,
    facility=Depends(_require_verified_facility),
):
    """Creates a `status="draft"` storage auction for every valid row.

    Facility must actively accept the bilingual legal notice at this
    step — the CSV cannot carry acceptance. Acceptance is stamped on
    every resulting draft.
    """
    if not body.accepted_legal_notice:
        raise HTTPException(status_code=400, detail={
            "code": "legal_notice_required",
            "message_en": (
                "You must accept the bilingual legal-notification confirmation "
                "before creating drafts. A spreadsheet value does not count as "
                "legal acceptance."
            ),
            "message_fr": (
                "Vous devez accepter la confirmation bilingue de la notification "
                "légale avant de créer les brouillons. Une valeur de tableur ne "
                "constitue pas une acceptation légale."
            ),
        })

    if len(body.rows) == 0:
        raise HTTPException(status_code=400, detail={
            "code": "empty_rows",
            "message_en": "At least one row is required.",
            "message_fr": "Au moins une ligne est requise.",
        })
    if len(body.rows) > MAX_ROWS_PER_IMPORT:
        raise HTTPException(status_code=400, detail={
            "code": "row_limit_exceeded",
            "message_en": f"Maximum {MAX_ROWS_PER_IMPORT} rows per import.",
            "message_fr": f"Maximum {MAX_ROWS_PER_IMPORT} lignes par importation.",
        })

    db = get_db()
    is_qc = _is_quebec_facility(facility)
    open_units = await _existing_open_unit_numbers(db, facility["id"])

    normalized: list[dict] = []
    all_errors: list[dict] = []
    for row_num, r in enumerate(body.rows, start=2):
        errs, norm = _validate_row(row_num, r.model_dump(), is_qc)
        normalized.append(norm)
        all_errors.extend(errs)
    all_errors.extend(_detect_within_batch_duplicates(normalized))
    all_errors.extend(_detect_facility_open_conflicts(normalized, open_units))

    if all_errors:
        return {
            "ok": False,
            "code": "validation_failed",
            "message_en": (
                "Some rows still have errors. Fix them in the review table "
                "before creating drafts."
            ),
            "message_fr": (
                "Certaines lignes contiennent encore des erreurs. Corrigez-les "
                "dans le tableau d'examen avant de créer les brouillons."
            ),
            "errors": all_errors,
            "created": 0,
        }

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    created: list[dict] = []
    batch_id = str(uuid.uuid4())

    for norm in normalized:
        auction_id = str(uuid.uuid4())
        end_dt = _parse_dt(norm["end_time"]) or (now + timedelta(days=7))
        cleanup_dt = end_dt + timedelta(hours=norm.get("cleanup_deadline_hours") or 72)
        starting = float(norm.get("starting_price") or 0)

        doc = {
            "id": auction_id,
            "facility_id": facility["id"],
            "facility_name": facility.get("company_name"),
            "facility_city": facility.get("city"),
            "facility_province": facility.get("province"),
            "unit_number": norm["unit_number"],
            "unit_size": norm["unit_size"],
            "unit_type": norm["unit_type"],
            "is_lien_unit": bool(norm.get("is_lien_unit")),
            "past_due_balance": norm.get("past_due_balance"),
            "description_en": norm["description_en"],
            "description_fr": norm.get("description_fr") or norm["description_en"],
            "photos": [],  # empty; facility must add ≥1 before publish
            "video_url": norm.get("video_url"),
            "starting_price": starting,
            "current_bid": starting,
            "reserve_price": norm.get("reserve_price"),
            "reserve_met": False if norm.get("reserve_price") else True,
            "bid_increment": float(norm.get("bid_increment") or 10.0),
            "start_time": norm["start_time"],
            "end_time": norm["end_time"],
            "soft_close_enabled": True,
            "soft_close_extension_minutes": 2,
            "cleanup_deadline": cleanup_dt.isoformat(),
            "cleanup_deadline_hours": int(norm.get("cleanup_deadline_hours") or 72),
            # Payment / currency
            "payment_method": norm.get("payment_method") or "stripe",
            "payment_methods_accepted": [norm.get("payment_method") or "stripe"],
            "payment_status": "pending",
            "currency": (norm.get("currency") or "CAD").upper(),
            # Deposit
            "deposit_required": bool(norm.get("deposit_required")),
            "deposit_amount": (
                float(norm["deposit_amount"])
                if norm.get("deposit_required") and norm.get("deposit_amount") is not None
                else 0.0
            ),
            "deposit_type": norm.get("deposit_type") if norm.get("deposit_required") else None,
            "requires_deposit": bool(norm.get("deposit_required")),
            # Draft lifecycle
            "status": "draft",  # ALWAYS starts as draft; photo-gated publish
            "source": "csv_bulk_import",
            "bulk_import_batch": batch_id,
            "bulk_import_batch_at": now_iso,
            # iter445 — FIXED platform BP; NOT configurable
            "buyer_premium_pct": 5.0,
            # Legal notice — actively confirmed at the wizard's Confirm step,
            # stamped on every resulting draft (never sourced from CSV).
            "accepted_legal_notice": True,
            "accepted_legal_notice_at": now_iso,
            "accepted_legal_notice_source": "bulk_import_wizard",
            # Bid tracking
            "winning_bidder_id": None,
            "winning_bid": None,
            "bid_count": 0,
            "bids": [],
            "created_at": now_iso,
            "updated_at": now_iso,
        }

        await db.storage_auctions.insert_one(doc.copy())
        doc.pop("_id", None)
        created.append({
            "id": auction_id,
            "unit_number": norm["unit_number"],
            "unit_size": norm["unit_size"],
            "unit_type": norm["unit_type"],
            "starting_price": starting,
            "image_count": 0,
            "needs_photos": True,
        })

    return {
        "ok": True,
        "code": "drafts_created",
        "message_en": (
            f"{len(created)} draft auction(s) created. "
            f"Add at least one photo per unit before publishing."
        ),
        "message_fr": (
            f"{len(created)} enchère(s) brouillon créée(s). "
            f"Ajoutez au moins une photo par unité avant de publier."
        ),
        "created": len(created),
        "batch_id": batch_id,
        "drafts": created,
    }


class StorageBulkPhotosBody(BaseModel):
    image_urls: list[str] = Field(..., min_length=1)


@storage_bulk_import_router.post(
    "/storage-facilities/bulk-import/{auction_id}/photos"
)
@_limiter.limit("60/minute")
async def attach_photos_to_bulk_storage_draft(
    request: Request,
    auction_id: str,
    body: StorageBulkPhotosBody,
    facility=Depends(_require_verified_facility),
):
    """Append photos to a bulk-imported draft storage auction."""
    db = get_db()
    auction = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0})
    if not auction:
        raise HTTPException(status_code=404, detail={
            "code": "auction_not_found",
            "message_en": "Draft auction not found.",
            "message_fr": "Enchère brouillon introuvable.",
        })
    if auction.get("facility_id") != facility["id"]:
        raise HTTPException(status_code=403, detail={
            "code": "not_your_draft",
            "message_en": "Not your draft.",
            "message_fr": "Ce brouillon ne vous appartient pas.",
        })
    if auction.get("status") != "draft" or auction.get("source") != "csv_bulk_import":
        raise HTTPException(status_code=400, detail={
            "code": "not_a_bulk_draft",
            "message_en": "This endpoint only accepts bulk-imported drafts.",
            "message_fr": "Ce point de terminaison n'accepte que les brouillons importés en masse.",
        })

    existing = list(auction.get("photos") or [])
    for u in body.image_urls:
        if u and u not in existing:
            existing.append(u)
    existing = existing[:10]  # single-form cap parity

    await db.storage_auctions.update_one(
        {"id": auction_id},
        {"$set": {
            "photos": existing,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {
        "ok": True,
        "auction_id": auction_id,
        "image_count": len(existing),
        "needs_photos": len(existing) == 0,
    }


def _resolve_publish_status(start_iso: Optional[str]) -> str:
    """Match the single-form logic: `upcoming` if start_time is in the
    future, otherwise `active`."""
    if not start_iso:
        return "active"
    try:
        dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return "upcoming" if dt > datetime.now(timezone.utc) else "active"
    except Exception:  # noqa: BLE001
        return "active"


@storage_bulk_import_router.post(
    "/storage-facilities/bulk-import/{auction_id}/publish"
)
@_limiter.limit("60/minute")
async def publish_bulk_storage_draft(
    request: Request,
    auction_id: str,
    facility=Depends(_require_verified_facility),
):
    """Flip a bulk-imported storage draft to `active` / `upcoming` (based
    on start_time) — requires ≥ 1 photo."""
    db = get_db()
    auction = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0})
    if not auction:
        raise HTTPException(status_code=404, detail={
            "code": "auction_not_found",
            "message_en": "Draft auction not found.",
            "message_fr": "Enchère brouillon introuvable.",
        })
    if auction.get("facility_id") != facility["id"]:
        raise HTTPException(status_code=403, detail={
            "code": "not_your_draft",
            "message_en": "Not your draft.",
            "message_fr": "Ce brouillon ne vous appartient pas.",
        })
    if auction.get("status") != "draft" or auction.get("source") != "csv_bulk_import":
        raise HTTPException(status_code=400, detail={
            "code": "not_a_bulk_draft",
            "message_en": "This endpoint only publishes bulk-imported drafts.",
            "message_fr": "Ce point de terminaison ne publie que les brouillons importés en masse.",
        })
    photos = auction.get("photos") or []
    if len(photos) < 1:
        raise HTTPException(status_code=400, detail={
            "code": "missing_photo",
            "message_en": "Add at least one photo before publishing this unit.",
            "message_fr": "Ajoutez au moins une photo avant de publier cette unité.",
        })

    new_status = _resolve_publish_status(auction.get("start_time"))
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.storage_auctions.update_one(
        {"id": auction_id},
        {"$set": {
            "status": new_status,
            "published_at": now_iso,
            "updated_at": now_iso,
        }},
    )
    return {"ok": True, "auction_id": auction_id, "status": new_status}


@storage_bulk_import_router.post(
    "/storage-facilities/bulk-import/publish-batch"
)
@_limiter.limit("10/minute")
async def publish_bulk_storage_batch(
    request: Request,
    facility=Depends(_require_verified_facility),
):
    """Publish every bulk-imported storage draft owned by the caller
    that has ≥ 1 photo. Drafts still missing a photo are returned in
    `pending_photos`."""
    db = get_db()
    drafts = await db.storage_auctions.find(
        {
            "facility_id": facility["id"],
            "status": "draft",
            "source": "csv_bulk_import",
        },
        {"_id": 0, "id": 1, "unit_number": 1, "photos": 1, "start_time": 1},
    ).to_list(length=MAX_ROWS_PER_IMPORT * 4)

    published: list[str] = []
    pending: list[dict] = []
    now_iso = datetime.now(timezone.utc).isoformat()
    for d in drafts:
        photos = d.get("photos") or []
        if len(photos) >= 1:
            new_status = _resolve_publish_status(d.get("start_time"))
            await db.storage_auctions.update_one(
                {"id": d["id"]},
                {"$set": {
                    "status": new_status,
                    "published_at": now_iso,
                    "updated_at": now_iso,
                }},
            )
            published.append(d["id"])
        else:
            pending.append({
                "id": d["id"],
                "unit_number": d.get("unit_number"),
            })

    return {
        "ok": True,
        "published_count": len(published),
        "pending_photos_count": len(pending),
        "published_ids": published,
        "pending_photos": pending,
        "message_en": (
            f"{len(published)} auction(s) published. "
            + (
                f"{len(pending)} unit(s) still need at least one photo before "
                f"they can go live."
                if pending else ""
            )
        ),
        "message_fr": (
            f"{len(published)} enchère(s) publiée(s). "
            + (
                f"{len(pending)} unité(s) nécessitent encore au moins une photo "
                f"avant d'être publiées."
                if pending else ""
            )
        ),
    }


@storage_bulk_import_router.get("/storage-facilities/bulk-import/pending")
async def list_pending_bulk_storage_drafts(
    facility=Depends(_require_verified_facility),
):
    """List every bulk-imported storage draft owned by the caller + photo
    counts, for the Photo Studio."""
    db = get_db()
    drafts = await db.storage_auctions.find(
        {
            "facility_id": facility["id"],
            "status": "draft",
            "source": "csv_bulk_import",
        },
        {
            "_id": 0, "id": 1, "unit_number": 1, "unit_size": 1, "unit_type": 1,
            "starting_price": 1, "photos": 1, "start_time": 1, "end_time": 1,
            "created_at": 1, "bulk_import_batch": 1,
        },
    ).sort("created_at", -1).to_list(length=MAX_ROWS_PER_IMPORT * 5)

    return {
        "count": len(drafts),
        "drafts": [
            {
                **d,
                "image_count": len(d.get("photos") or []),
                "needs_photos": len(d.get("photos") or []) == 0,
            }
            for d in drafts
        ],
    }


def try_match_filename_to_unit(filename: str, unit_numbers: list[str]) -> Optional[str]:
    """Fuzzy-match a photo filename to one of the provided unit numbers.

    Returns the matched unit_number (original casing) or None. Used by
    the Photo Studio's auto-matcher.

    Strategy — case-insensitive, tries progressively looser tokens:
      1. Exact substring match of the unit_number in the filename stem.
      2. Alphanumeric-only comparison (strip separators).
      3. Digit-suffix match (e.g. "A-101" → "101" in "unit_101.jpg").
    """
    if not filename or not unit_numbers:
        return None
    stem = re.sub(r"\.[^.]+$", "", filename).lower()
    stem_alnum = re.sub(r"[^a-z0-9]", "", stem)

    # Longest units first so "A-101" beats "A-1" in "photo-A-101.jpg".
    sorted_units = sorted(unit_numbers, key=lambda u: -len(str(u or "")))
    for u in sorted_units:
        s = str(u or "").strip().lower()
        if not s:
            continue
        if s in stem:
            return u
        s_alnum = re.sub(r"[^a-z0-9]", "", s)
        if s_alnum and s_alnum in stem_alnum:
            return u
        # Digit suffix (A-101 → 101)
        digits = re.sub(r"[^0-9]", "", s)
        if digits and len(digits) >= 2 and digits in stem_alnum:
            return u
    return None
