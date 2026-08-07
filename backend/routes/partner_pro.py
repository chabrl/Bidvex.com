"""
BidVex Partner Pro Features Router
Handles: CSV bulk import, analytics export, branded storefront, 
early auction access, featured listings management.
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from deps import User, get_current_user
from typing import Optional
from datetime import datetime, timezone, timedelta
import logging
import uuid
import csv
import io
import json

logger = logging.getLogger(__name__)

partner_pro_router = APIRouter(tags=["Partner Pro"])

_db = None


def set_partner_pro_db(db_instance):
    global _db
    _db = db_instance


def get_db():
    if _db is None:
        raise RuntimeError("Partner Pro DB not initialised")
    return _db


PARTNER_PRO_TIERS = {"partner_pro", "vip"}
TRIAL_DURATION_DAYS = 14
TRIAL_REMINDER_DAY = 10  # Send reminder 3 days before expiry


def _require_partner_pro(user: User):
    # iter444 — super_admin bypasses subscription gate (support / testing).
    if getattr(user, "role", "") in {"admin", "super_admin"}:
        return
    tier = getattr(user, "subscription_tier", "free")
    if tier not in PARTNER_PRO_TIERS:
        raise HTTPException(
            status_code=403,
            detail="Partner Pro or VIP subscription required",
        )


from rate_limit import limiter as _limiter


# =====================================================================
# 14-DAY FREE TRIAL
# =====================================================================

@partner_pro_router.post("/partner-pro/trial/start")
@_limiter.limit("3/minute")
async def start_trial(request: Request, current_user: User = Depends(get_current_user)):
    """
    Start a 14-day free trial of Partner Pro.
    No credit card required. One trial per account, non-renewable.
    """
    db = get_db()
    user = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user already used trial
    if user.get("partner_pro_trial_used"):
        raise HTTPException(status_code=400, detail="Trial already used. Each account gets one free trial.")

    # Check if already on partner_pro or vip
    current_tier = user.get("subscription_tier", "free")
    if current_tier in PARTNER_PRO_TIERS:
        raise HTTPException(status_code=400, detail="You already have Partner Pro or higher.")

    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=TRIAL_DURATION_DAYS)

    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {
            "subscription_tier": "partner_pro",
            "subscription_status": "trialing",
            "subscription_source": "trial",
            "partner_pro_trial_used": True,
            "partner_pro_trial_start": now.isoformat(),
            "partner_pro_trial_end": trial_end.isoformat(),
            "subscription_start_date": now.isoformat(),
            "subscription_end_date": trial_end.isoformat(),
            "updated_at": now.isoformat(),
        }}
    )

    # Schedule reminder (stored for the scheduler to pick up)
    reminder_date = now + timedelta(days=TRIAL_REMINDER_DAY)
    await db.scheduled_emails.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "email": user.get("email"),
        "type": "trial_expiry_reminder",
        "scheduled_for": reminder_date.isoformat(),
        "sent": False,
        "created_at": now.isoformat(),
    })

    logger.info(f"Partner Pro trial started for user {current_user.id}, expires {trial_end.isoformat()}")

    # Send trial confirmation email
    try:
        from services.email_service import get_email_service
        from services.partner_pro_emails import trial_started
        svc = get_email_service()
        if svc and svc.is_configured():
            tmpl = trial_started(user.get("name", "there"), trial_end.strftime("%B %d, %Y"))
            await svc.send_raw_html(user.get("email"), tmpl["subject"], tmpl["html"])
    except Exception as em:
        logger.warning(f"Trial confirmation email failed: {em}")

    return {
        "success": True,
        "trial_start": now.isoformat(),
        "trial_end": trial_end.isoformat(),
        "days_remaining": TRIAL_DURATION_DAYS,
        "message": f"Your {TRIAL_DURATION_DAYS}-day Partner Pro trial has started! All features are now unlocked.",
    }


@partner_pro_router.get("/partner-pro/trial/status")
async def get_trial_status(current_user: User = Depends(get_current_user)):
    """Get the current user's trial status."""
    db = get_db()
    user = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    trial_used = user.get("partner_pro_trial_used", False)
    trial_end = user.get("partner_pro_trial_end")
    is_trialing = user.get("subscription_status") == "trialing" and user.get("subscription_source") == "trial"

    days_remaining = 0
    if trial_end and is_trialing:
        end_dt = datetime.fromisoformat(trial_end)
        remaining = end_dt - datetime.now(timezone.utc)
        days_remaining = max(0, remaining.days)

    return {
        "trial_used": trial_used,
        "is_trialing": is_trialing,
        "trial_end": trial_end,
        "days_remaining": days_remaining,
        "eligible_for_trial": not trial_used and user.get("subscription_tier", "free") not in PARTNER_PRO_TIERS,
    }


# =====================================================================
# iter444 — CSV BULK LISTING IMPORT (Partner Pro / VIP only)
#
# Two-step wizard on the client:
#   1. Client POSTs the raw CSV to /partner-pro/bulk-import        (PREVIEW ONLY, no writes)
#      Server parses + validates every row and returns a preview
#      payload with per-cell bilingual errors.
#   2. Client PATCH-edits rows in the review table and POSTs the
#      finalized rows to /partner-pro/bulk-import/confirm             (CREATES DRAFTS)
#      Server re-validates, enforces the 100-row cap, dedupes
#      within the batch, and writes each row to `listings` with
#      `status="draft"` and `images=[]`.
#   3. Client attaches photos with /bulk-import/{id}/photos.
#   4. Client publishes drafts with /bulk-import/{id}/publish (single)
#      or /bulk-import/publish-batch (many). Publish requires ≥1 image.
#
# NO existing live listing is touched. Storage, Vehicle, and fee logic
# are untouched.
# =====================================================================

MAX_ROWS_PER_IMPORT = 100

# Canonical column order for both the downloadable template AND the
# server's DictReader field-name normalisation. Order matters — the CSV
# template is emitted in exactly this order.
CSV_COLUMNS = [
    "title",
    "title_fr",
    "category",
    "starting_price",
    "quantity",
    "condition",
    "auction_end_date",
    "city",
    "region",
    "country",
    "postal_code",
    "description",
    "buy_now_price",
    "buyers_premium_percent",
    "shipping_available",
    "visit_offered",
    "visit_dates",
]

# Which columns MUST be non-empty for every row. `title_fr` is
# conditionally required (only when region == "QC") — validated inline.
CSV_REQUIRED = {
    "title",
    "category",
    "starting_price",
    "quantity",
    "condition",
    "auction_end_date",
    "city",
    "region",
}

VALID_CONDITIONS = {"new", "like_new", "excellent", "good", "fair", "poor", "used"}


def _row_error(row: int, field: str, code: str, message_en: str, message_fr: str) -> dict:
    """Bilingual per-cell error record — flat dict for easy JSON handling."""
    return {
        "row": row,
        "field": field,
        "code": code,
        "message_en": f"Row {row} — Field '{field}': {message_en}",
        "message_fr": f"Ligne {row} — Champ « {field} » : {message_fr}",
    }


def _norm_bool(v) -> bool:
    """Accept 'Y', 'yes', 'true', '1' (any case) as truthy — everything else falsy."""
    if v is None:
        return False
    return str(v).strip().lower() in {"y", "yes", "true", "1", "oui"}


async def _validate_row(db, row_num: int, row: dict, valid_categories: set) -> tuple[list, dict]:
    """Returns (errors, normalized_row). errors=[] means row is import-ready."""
    errors: list[dict] = []

    # ── title (required, non-empty) ─────────────────────────────────
    title = (row.get("title") or "").strip()
    if not title:
        errors.append(_row_error(
            row_num, "title", "title_required",
            "Title is required.", "Titre requis.",
        ))
    elif len(title) > 200:
        errors.append(_row_error(
            row_num, "title", "title_too_long",
            "Title must be ≤ 200 characters.",
            "Le titre doit contenir 200 caractères ou moins.",
        ))

    # ── category (required, must exist) ─────────────────────────────
    category = (row.get("category") or "").strip()
    if not category:
        errors.append(_row_error(
            row_num, "category", "category_required",
            "Category is required.", "Catégorie requise.",
        ))
    elif category not in valid_categories:
        errors.append(_row_error(
            row_num, "category", "category_unknown",
            f"Category '{category}' does not exist. Download the template for the current list.",
            f"La catégorie « {category} » n'existe pas. Téléchargez le modèle pour la liste actuelle.",
        ))

    # ── starting_price (required, 1-10000 CAD) ──────────────────────
    starting_price = None
    raw_sp = str(row.get("starting_price") or "").strip()
    if not raw_sp:
        errors.append(_row_error(
            row_num, "starting_price", "starting_price_required",
            "Starting price is required.", "Prix de départ requis.",
        ))
    else:
        try:
            starting_price = float(raw_sp)
            if starting_price < 1 or starting_price > 10000:
                errors.append(_row_error(
                    row_num, "starting_price", "starting_price_out_of_range",
                    "Starting price must be between 1 and 10,000 CAD.",
                    "Le prix de départ doit être entre 1 et 10 000 CAD.",
                ))
        except ValueError:
            errors.append(_row_error(
                row_num, "starting_price", "starting_price_not_numeric",
                "Starting price must be a number.",
                "Le prix de départ doit être un nombre.",
            ))

    # ── quantity (required, positive integer) ───────────────────────
    quantity = None
    raw_q = str(row.get("quantity") or "").strip()
    if not raw_q:
        errors.append(_row_error(
            row_num, "quantity", "quantity_required",
            "Quantity is required.", "Quantité requise.",
        ))
    else:
        try:
            quantity = int(float(raw_q))
            if quantity < 1:
                errors.append(_row_error(
                    row_num, "quantity", "quantity_positive",
                    "Quantity must be a positive integer.",
                    "La quantité doit être un entier positif.",
                ))
        except ValueError:
            errors.append(_row_error(
                row_num, "quantity", "quantity_not_integer",
                "Quantity must be a positive integer.",
                "La quantité doit être un entier positif.",
            ))

    # ── condition (required, enum) ─────────────────────────────────
    condition = (row.get("condition") or "").strip().lower()
    if not condition:
        errors.append(_row_error(
            row_num, "condition", "condition_required",
            "Condition is required.", "État requis.",
        ))
    elif condition not in VALID_CONDITIONS:
        errors.append(_row_error(
            row_num, "condition", "condition_invalid",
            f"Condition must be one of: {', '.join(sorted(VALID_CONDITIONS))}.",
            f"L'état doit être l'un de : {', '.join(sorted(VALID_CONDITIONS))}.",
        ))

    # ── auction_end_date (required, valid ISO, in the future) ───────
    end_dt = None
    raw_end = (row.get("auction_end_date") or "").strip()
    if not raw_end:
        errors.append(_row_error(
            row_num, "auction_end_date", "auction_end_date_required",
            "Auction end date is required (ISO format, e.g. 2026-06-15T18:00:00).",
            "Date de fin de l'enchère requise (format ISO, ex. : 2026-06-15T18:00:00).",
        ))
    else:
        try:
            end_dt = datetime.fromisoformat(raw_end.replace("Z", "+00:00"))
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            if end_dt <= datetime.now(timezone.utc):
                errors.append(_row_error(
                    row_num, "auction_end_date", "auction_end_date_past",
                    "Auction end date must be in the future.",
                    "La date de fin de l'enchère doit être dans le futur.",
                ))
        except ValueError:
            errors.append(_row_error(
                row_num, "auction_end_date", "auction_end_date_invalid",
                "Auction end date must be a valid ISO datetime (e.g. 2026-06-15T18:00:00).",
                "La date de fin doit être une date ISO valide (ex. : 2026-06-15T18:00:00).",
            ))

    # ── city + region (required) ────────────────────────────────────
    city = (row.get("city") or "").strip()
    if not city:
        errors.append(_row_error(
            row_num, "city", "city_required",
            "City is required.", "Ville requise.",
        ))

    region = (row.get("region") or "").strip().upper()
    if not region:
        errors.append(_row_error(
            row_num, "region", "region_required",
            "Region / province is required.",
            "Région / province requise.",
        ))

    # ── title_fr — Bill 96: required when region == "QC" ────────────
    title_fr = (row.get("title_fr") or "").strip()
    if region == "QC" and not title_fr:
        errors.append(_row_error(
            row_num, "title_fr", "bill96_title_fr_required",
            "Bill 96 requires a French title for Quebec listings.",
            "La Loi 96 exige un titre français pour les annonces au Québec.",
        ))

    # ── description (optional; if present, 20-500 chars) ────────────
    description = (row.get("description") or "").strip()
    if description and (len(description) < 20 or len(description) > 500):
        errors.append(_row_error(
            row_num, "description", "description_length",
            "Description must be 20-500 characters when provided.",
            "La description doit contenir de 20 à 500 caractères si elle est fournie.",
        ))

    # ── buy_now_price (optional; if present, ≥ 1.2 × starting_price) ─
    buy_now_price = None
    raw_bn = str(row.get("buy_now_price") or "").strip()
    if raw_bn:
        try:
            buy_now_price = float(raw_bn)
            if starting_price is not None and buy_now_price < starting_price * 1.2:
                errors.append(_row_error(
                    row_num, "buy_now_price", "buy_now_price_too_low",
                    f"Buy Now price must be at least 20% above starting price (≥ {starting_price * 1.2:.2f} CAD).",
                    f"Le prix Achat Immédiat doit être au moins 20 % au-dessus du prix de départ (≥ {starting_price * 1.2:.2f} CAD).",
                ))
        except ValueError:
            errors.append(_row_error(
                row_num, "buy_now_price", "buy_now_price_not_numeric",
                "Buy Now price must be a number.",
                "Le prix Achat Immédiat doit être un nombre.",
            ))

    # ── buyers_premium_percent (optional; 0-25 per iter441 rule) ────
    bp = None
    raw_bp = str(row.get("buyers_premium_percent") or "").strip()
    if raw_bp:
        try:
            bp = float(raw_bp)
            if bp < 0 or bp > 25:
                errors.append(_row_error(
                    row_num, "buyers_premium_percent",
                    "buyers_premium_out_of_range",
                    "Buyer's premium must be between 0 and 25 percent.",
                    "La prime acheteur doit être entre 0 et 25 pour cent.",
                ))
        except ValueError:
            errors.append(_row_error(
                row_num, "buyers_premium_percent",
                "buyers_premium_not_numeric",
                "Buyer's premium must be a number.",
                "La prime acheteur doit être un nombre.",
            ))

    return errors, {
        "title": title,
        "title_fr": title_fr,
        "category": category,
        "starting_price": starting_price,
        "quantity": quantity,
        "condition": condition,
        "auction_end_date": end_dt.isoformat() if end_dt else None,
        "city": city,
        "region": region,
        "country": (row.get("country") or "CA").strip().upper() or "CA",
        "postal_code": (row.get("postal_code") or "").strip(),
        "description": description,
        "buy_now_price": buy_now_price,
        "buyers_premium_percent": bp,
        "shipping_available": _norm_bool(row.get("shipping_available")),
        "visit_offered": _norm_bool(row.get("visit_offered")),
        "visit_dates": (row.get("visit_dates") or "").strip(),
    }


def _detect_within_batch_duplicates(rows: list[dict]) -> list[dict]:
    """Flag rows whose (title, starting_price, category) triplet already
    appeared earlier in the same batch. Points the Partner at the FIRST
    matching row so they can fix quickly.

    Returns a list of duplicate-error records (same shape as _row_error).
    """
    seen: dict[tuple, int] = {}  # triplet -> first row_num
    errors: list[dict] = []
    for row_num, r in enumerate(rows, start=2):
        # Skip rows already failing basic validation — pointless to dupe-check them.
        title = (r.get("title") or "").strip().lower()
        cat = (r.get("category") or "").strip().lower()
        sp = r.get("starting_price")
        if not title or not cat or sp is None:
            continue
        key = (title, cat, round(float(sp), 2))
        if key in seen:
            first = seen[key]
            errors.append(_row_error(
                row_num, "title", "duplicate_row",
                f"Duplicate — same title, starting price, and category as row {first}. Change one field to import both.",
                f"Doublon — même titre, prix de départ et catégorie que la ligne {first}. Modifiez un champ pour importer les deux.",
            ))
        else:
            seen[key] = row_num
    return errors


@partner_pro_router.get("/partner-pro/bulk-import/template")
async def get_csv_template():
    """iter444 — Fixed template with correct column order + 3 example rows."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    # Example row 1 — Ontario, no French title needed.
    writer.writerow([
        "Sony Camera A7 III",                                # title
        "",                                                  # title_fr
        "electronics",                                       # category
        "250.00",                                            # starting_price
        "1",                                                 # quantity
        "excellent",                                         # condition
        (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),  # auction_end_date
        "Toronto",                                           # city
        "ON",                                                # region
        "CA",                                                # country
        "M5V 2H1",                                           # postal_code
        "Full-frame mirrorless camera, low shutter count, boxed with charger and 2 batteries.",  # description
        "500.00",                                            # buy_now_price
        "5",                                                 # buyers_premium_percent
        "Y",                                                 # shipping_available
        "N",                                                 # visit_offered
        "",                                                  # visit_dates
    ])
    # Example row 2 — Quebec, French title required.
    writer.writerow([
        "Vintage Leather Sofa",                              # title
        "Canapé en cuir vintage",                            # title_fr
        "furniture",                                         # category
        "300.00",                                            # starting_price
        "1",                                                 # quantity
        "good",                                              # condition
        (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),  # auction_end_date
        "Montreal",                                          # city
        "QC",                                                # region
        "CA",                                                # country
        "H3B 1A7",                                           # postal_code
        "Genuine leather three-seater sofa, minor wear on the arms, freshly cleaned.",
        "",                                                  # buy_now_price
        "",                                                  # buyers_premium_percent
        "N",                                                 # shipping_available
        "Y",                                                 # visit_offered
        "Weekdays 10:00–18:00",                              # visit_dates
    ])
    # Example row 3 — BC, multi-quantity lot.
    writer.writerow([
        "iPhone 12 (refurbished)",                           # title
        "",                                                  # title_fr
        "electronics",                                       # category
        "180.00",                                            # starting_price
        "5",                                                 # quantity
        "like_new",                                          # condition
        (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),   # auction_end_date
        "Vancouver",                                         # city
        "BC",                                                # region
        "CA",                                                # country
        "V6B 5K3",                                           # postal_code
        "Refurbished iPhone 12 units — 128GB — reset to factory, 90-day warranty.",
        "300.00",                                            # buy_now_price
        "",                                                  # buyers_premium_percent
        "Y",                                                 # shipping_available
        "N",                                                 # visit_offered
        "",                                                  # visit_dates
    ])
    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),  # BOM so Excel opens it correctly
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bidvex_partner_bulk_import_template.csv"},
    )


@partner_pro_router.post("/partner-pro/bulk-import")
@_limiter.limit("30/minute")
async def preview_bulk_import(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """iter444 — PREVIEW ONLY. Parses + validates the CSV and returns
    per-row + per-cell bilingual errors. NO listings are created.

    Client renders the preview payload in an editable review table,
    then POSTs the fixed rows back to `/bulk-import/confirm`.
    """
    _require_partner_pro(current_user)

    if not file.filename.endswith(".csv"):
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
    headers = set(h.strip() for h in (reader.fieldnames or []))
    missing_headers = CSV_REQUIRED - headers
    if missing_headers:
        raise HTTPException(status_code=400, detail={
            "code": "missing_columns",
            "message_en": f"Missing required columns: {', '.join(sorted(missing_headers))}. Download the template.",
            "message_fr": f"Colonnes obligatoires manquantes : {', '.join(sorted(missing_headers))}. Téléchargez le modèle.",
        })

    raw_rows = list(reader)
    if len(raw_rows) > MAX_ROWS_PER_IMPORT:
        raise HTTPException(status_code=400, detail={
            "code": "row_limit_exceeded",
            "message_en": f"Maximum {MAX_ROWS_PER_IMPORT} rows per import. Your file has {len(raw_rows)}.",
            "message_fr": f"Maximum {MAX_ROWS_PER_IMPORT} lignes par importation. Votre fichier en contient {len(raw_rows)}.",
        })

    db = get_db()
    # Fetch valid category slugs once.
    cats = await db.categories.find({}, {"_id": 0, "slug": 1, "name": 1}).to_list(length=1000)
    valid_categories = {c.get("slug") or c.get("name") for c in cats if c.get("slug") or c.get("name")}
    # Common fallback categories (in case the categories collection is empty).
    if not valid_categories:
        valid_categories = {"electronics", "furniture", "clothing", "collectibles", "tools",
                            "toys", "sports", "vehicles", "jewelry", "art", "books", "other"}

    preview_rows: list[dict] = []
    normalized: list[dict] = []
    for row_num, raw in enumerate(raw_rows, start=2):
        errors, norm = await _validate_row(db, row_num, raw, valid_categories)
        preview_rows.append({
            "row": row_num,
            "raw": raw,
            "normalized": norm,
            "errors": errors,
        })
        normalized.append(norm)

    # Batch-wide duplicate detection (only after per-row validation).
    dup_errors = _detect_within_batch_duplicates(normalized)
    for de in dup_errors:
        # Attach the duplicate error to the correct preview row.
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
        "valid_categories": sorted(valid_categories),
    }


class BulkImportConfirmRow(BaseModel):
    title: str
    title_fr: Optional[str] = ""
    category: str
    starting_price: float
    quantity: int
    condition: str
    auction_end_date: str
    city: str
    region: str
    country: Optional[str] = "CA"
    postal_code: Optional[str] = ""
    description: Optional[str] = ""
    buy_now_price: Optional[float] = None
    buyers_premium_percent: Optional[float] = None
    shipping_available: Optional[bool] = False
    visit_offered: Optional[bool] = False
    visit_dates: Optional[str] = ""


class BulkImportConfirmBody(BaseModel):
    rows: list[BulkImportConfirmRow] = Field(..., min_length=1)


@partner_pro_router.post("/partner-pro/bulk-import/confirm")
@_limiter.limit("10/minute")
async def confirm_bulk_import(
    request: Request,
    body: BulkImportConfirmBody,
    current_user: User = Depends(get_current_user),
):
    """iter444 — Creates a draft listing for every valid row.

    Server re-validates every row (defense in depth). Enforces the 100-
    row cap and intra-batch dedupe. Writes each row to `listings` with
    `status="draft"`, `images=[]`, and `source="csv_bulk_import"`.
    """
    _require_partner_pro(current_user)

    if len(body.rows) > MAX_ROWS_PER_IMPORT:
        raise HTTPException(status_code=400, detail={
            "code": "row_limit_exceeded",
            "message_en": f"Maximum {MAX_ROWS_PER_IMPORT} rows per import.",
            "message_fr": f"Maximum {MAX_ROWS_PER_IMPORT} lignes par importation.",
        })

    db = get_db()
    cats = await db.categories.find({}, {"_id": 0, "slug": 1, "name": 1}).to_list(length=1000)
    valid_categories = {c.get("slug") or c.get("name") for c in cats if c.get("slug") or c.get("name")}
    if not valid_categories:
        valid_categories = {"electronics", "furniture", "clothing", "collectibles", "tools",
                            "toys", "sports", "vehicles", "jewelry", "art", "books", "other"}

    normalized: list[dict] = []
    all_errors: list[dict] = []
    for row_num, r in enumerate(body.rows, start=2):
        errors, norm = await _validate_row(db, row_num, r.model_dump(), valid_categories)
        normalized.append(norm)
        all_errors.extend(errors)

    all_errors.extend(_detect_within_batch_duplicates(normalized))

    if all_errors:
        return {
            "ok": False,
            "code": "validation_failed",
            "message_en": "Some rows still have errors. Fix them in the preview table before creating drafts.",
            "message_fr": "Certaines lignes contiennent encore des erreurs. Corrigez-les dans le tableau d'aperçu avant de créer les brouillons.",
            "errors": all_errors,
            "created": 0,
        }

    now = datetime.now(timezone.utc).isoformat()
    created: list[dict] = []
    for norm in normalized:
        listing_id = str(uuid.uuid4())
        listing = {
            "id": listing_id,
            "seller_id": current_user.id,
            "title": norm["title"],
            "title_fr": norm["title_fr"] or None,
            "description": norm["description"] or "",
            "category": norm["category"],
            "starting_price": norm["starting_price"],
            "current_price": norm["starting_price"],
            "quantity": norm["quantity"],
            "condition": norm["condition"],
            "auction_end_date": norm["auction_end_date"],
            "city": norm["city"],
            "region": norm["region"],
            "country": norm["country"] or "CA",
            "postal_code": norm["postal_code"] or "",
            "location": f"{norm['city']}, {norm['region']}",
            "buy_now_price": norm["buy_now_price"],
            "buy_now_enabled": norm["buy_now_price"] is not None,
            # iter441 — partner may override BP per listing.
            "custom_buyer_premium_rate": (
                round(norm["buyers_premium_percent"] / 100.0, 4)
                if norm["buyers_premium_percent"] is not None else None
            ),
            "shipping_available": norm["shipping_available"],
            "visit_offered": norm["visit_offered"],
            "visit_dates": norm["visit_dates"] or "",
            "images": [],  # iter444 — starts empty; Partner must attach ≥1 photo before publish
            "listing_type": "private_sale",
            "status": "draft",  # iter444 — always draft, never active on create
            "views": 0,
            "total_bids": 0,
            "bid_count": 0,
            "watchers": [],
            "created_at": now,
            "updated_at": now,
            "source": "csv_bulk_import",
            "bulk_import_batch": now,  # groups all rows from this import
        }

        # Enrich seller record (best-effort; failure won't block draft creation).
        try:
            from services.listing_seller_enrichment import enrich_listing_async
            listing = await enrich_listing_async(db, listing, "general")
        except Exception:  # noqa: BLE001
            pass

        await db.listings.insert_one(listing)
        created.append({
            "id": listing_id,
            "title": norm["title"],
            "title_fr": norm["title_fr"] or "",
            "needs_photos": True,
        })

    return {
        "ok": True,
        "code": "drafts_created",
        "message_en": f"{len(created)} draft listing(s) created. Add at least one photo per draft to publish.",
        "message_fr": f"{len(created)} annonce(s) brouillon créée(s). Ajoutez au moins une photo par brouillon pour publier.",
        "created": len(created),
        "drafts": created,
    }


class BulkImportPhotosBody(BaseModel):
    image_urls: list[str] = Field(..., min_length=1)


@partner_pro_router.post("/partner-pro/bulk-import/{listing_id}/photos")
@_limiter.limit("60/minute")
async def attach_photos_to_bulk_draft(
    request: Request,
    listing_id: str,
    body: BulkImportPhotosBody,
    current_user: User = Depends(get_current_user),
):
    """iter444 — Attach photos to a bulk-imported draft (append, not replace).

    Only works on listings the caller owns AND that are currently `draft`
    AND were imported via CSV. Prevents accidental image overwrites on
    already-live listings.
    """
    _require_partner_pro(current_user)
    db = get_db()

    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail={
            "code": "listing_not_found",
            "message_en": "Draft not found.",
            "message_fr": "Brouillon introuvable.",
        })
    if listing.get("seller_id") != current_user.id:
        raise HTTPException(status_code=403, detail={
            "code": "not_your_draft",
            "message_en": "Not your draft.",
            "message_fr": "Ce brouillon ne vous appartient pas.",
        })
    if listing.get("status") != "draft" or listing.get("source") != "csv_bulk_import":
        raise HTTPException(status_code=400, detail={
            "code": "not_a_bulk_draft",
            "message_en": "This endpoint only accepts bulk-imported drafts.",
            "message_fr": "Ce point de terminaison n'accepte que les brouillons importés en masse.",
        })

    existing = list(listing.get("images") or [])
    for u in body.image_urls:
        if u and u not in existing:
            existing.append(u)

    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "images": existing,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {
        "ok": True,
        "listing_id": listing_id,
        "image_count": len(existing),
        "needs_photos": len(existing) == 0,
    }


@partner_pro_router.post("/partner-pro/bulk-import/{listing_id}/publish")
@_limiter.limit("60/minute")
async def publish_bulk_draft(
    request: Request,
    listing_id: str,
    current_user: User = Depends(get_current_user),
):
    """iter444 — Flip a bulk-imported draft to `active` if — and ONLY if
    — it has ≥ 1 photo. Any other status returns a bilingual 400."""
    _require_partner_pro(current_user)
    db = get_db()

    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail={
            "code": "listing_not_found",
            "message_en": "Draft not found.",
            "message_fr": "Brouillon introuvable.",
        })
    if listing.get("seller_id") != current_user.id:
        raise HTTPException(status_code=403, detail={
            "code": "not_your_draft",
            "message_en": "Not your draft.",
            "message_fr": "Ce brouillon ne vous appartient pas.",
        })
    if listing.get("status") != "draft" or listing.get("source") != "csv_bulk_import":
        raise HTTPException(status_code=400, detail={
            "code": "not_a_bulk_draft",
            "message_en": "This endpoint only publishes bulk-imported drafts.",
            "message_fr": "Ce point de terminaison ne publie que les brouillons importés en masse.",
        })

    images = listing.get("images") or []
    if len(images) < 1:
        raise HTTPException(status_code=400, detail={
            "code": "missing_photo",
            "message_en": "Add at least one photo before publishing.",
            "message_fr": "Ajoutez au moins une photo avant de publier.",
        })

    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "status": "active",
            "published_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"ok": True, "listing_id": listing_id, "status": "active"}


@partner_pro_router.post("/partner-pro/bulk-import/publish-batch")
@_limiter.limit("10/minute")
async def publish_bulk_batch(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """iter444 — Publish every bulk-imported draft owned by the caller
    that has ≥ 1 photo. Drafts still missing a photo are skipped and
    returned in `pending_photos`."""
    _require_partner_pro(current_user)
    db = get_db()

    drafts = await db.listings.find(
        {"seller_id": current_user.id, "status": "draft", "source": "csv_bulk_import"},
        {"_id": 0, "id": 1, "images": 1, "title": 1},
    ).to_list(length=MAX_ROWS_PER_IMPORT * 2)

    published: list[str] = []
    pending: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    for d in drafts:
        imgs = d.get("images") or []
        if len(imgs) >= 1:
            await db.listings.update_one(
                {"id": d["id"]},
                {"$set": {"status": "active", "published_at": now, "updated_at": now}},
            )
            published.append(d["id"])
        else:
            pending.append({"id": d["id"], "title": d.get("title", "")})

    return {
        "ok": True,
        "published_count": len(published),
        "pending_photos_count": len(pending),
        "published_ids": published,
        "pending_photos": pending,
        "message_en": (
            f"{len(published)} listing(s) published. "
            + (f"{len(pending)} still need at least one photo before they can go live." if pending else "")
        ),
        "message_fr": (
            f"{len(published)} annonce(s) publiée(s). "
            + (f"{len(pending)} nécessitent encore au moins une photo avant d'être publiées." if pending else "")
        ),
    }


@partner_pro_router.get("/partner-pro/bulk-import/pending")
async def list_pending_bulk_drafts(current_user: User = Depends(get_current_user)):
    """iter444 — Return every bulk-imported draft owned by the caller,
    with photo counts, so the Photo Studio can render the "missing
    photo" pills next to each draft."""
    _require_partner_pro(current_user)
    db = get_db()

    drafts = await db.listings.find(
        {"seller_id": current_user.id, "status": "draft", "source": "csv_bulk_import"},
        {"_id": 0, "id": 1, "title": 1, "title_fr": 1, "starting_price": 1,
         "category": 1, "region": 1, "city": 1, "images": 1, "created_at": 1,
         "bulk_import_batch": 1},
    ).sort("created_at", -1).to_list(length=MAX_ROWS_PER_IMPORT * 5)

    return {
        "count": len(drafts),
        "drafts": [
            {**d, "image_count": len(d.get("images") or []),
             "needs_photos": len(d.get("images") or []) == 0}
            for d in drafts
        ],
    }



# =====================================================================
# ANALYTICS EXPORT
# =====================================================================

@partner_pro_router.get("/partner-pro/analytics/export")
async def export_analytics(
    format: str = Query("csv", pattern="^(csv|json)$"),
    period_days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
):
    """Export seller analytics data as CSV or JSON."""
    _require_partner_pro(current_user)
    db = get_db()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()

    listings = await db.listings.find(
        {"seller_id": current_user.id, "created_at": {"$gte": cutoff}},
        {"_id": 0, "id": 1, "title": 1, "current_price": 1, "starting_price": 1,
         "views": 1, "total_bids": 1, "bid_count": 1, "status": 1,
         "category": 1, "created_at": 1, "auction_end_date": 1},
    ).to_list(5000)

    bids = await db.bids.find(
        {"bidder_id": current_user.id, "created_at": {"$gte": cutoff}},
        {"_id": 0, "id": 1, "listing_id": 1, "amount": 1, "created_at": 1},
    ).to_list(5000)

    if format == "json":
        payload = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "period_days": period_days,
            "listings": listings,
            "bids": bids,
            "summary": {
                "total_listings": len(listings),
                "total_bids": len(bids),
                "active_listings": sum(1 for item in listings if item.get("status") == "active"),
                "total_views": sum(item.get("views", 0) for item in listings),
            },
        }
        return StreamingResponse(
            io.BytesIO(json.dumps(payload, indent=2, default=str).encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=bidvex_analytics.json"},
        )

    # CSV export
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["type", "id", "title", "price", "views", "bids", "status", "category", "date"])
    for listing in listings:
        writer.writerow([
            "listing", listing.get("id"), listing.get("title"), listing.get("current_price"),
            listing.get("views", 0), listing.get("total_bids", 0) or listing.get("bid_count", 0),
            listing.get("status"), listing.get("category"), listing.get("created_at"),
        ])
    for bid in bids:
        writer.writerow([
            "bid", bid.get("id"), "", bid.get("amount"),
            "", "", "", "", bid.get("created_at"),
        ])
    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bidvex_analytics.csv"},
    )


# =====================================================================
# BRANDED STOREFRONT
# =====================================================================

@partner_pro_router.get("/storefronts/{user_id}")
async def get_storefront(user_id: str):
    """Get a seller's branded storefront (public)."""
    db = get_db()
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Seller not found")

    tier = user.get("subscription_tier", "free")
    storefront = await db.storefronts.find_one({"user_id": user_id}, {"_id": 0})

    # ── iter300 P2 — active listings across ALL FOUR sections ──
    listings = await db.listings.find(
        {"seller_id": user_id, "status": "active"},
        {"_id": 0},
    ).sort("created_at", -1).limit(50).to_list(50)
    for l in listings:
        l["_section"] = "marketplace"
        l["_url"] = f"/listing/{l.get('id')}"
    for coll, section, url_prefix, owner_field in (
        ("multi_item_listings", "lots", "/lots/", "seller_id"),
        ("vehicle_listings", "vehicles", "/vehicles/", "seller_id"),
        ("storage_auctions", "storage", "/storage-auctions/", "facility_owner_id"),
    ):
        extra = await db[coll].find(
            {"$or": [{"seller_id": user_id}, {owner_field: user_id}], "status": "active"},
            {"_id": 0},
        ).sort("created_at", -1).limit(30).to_list(30)
        for l in extra:
            l["_section"] = section
            l["_url"] = f"{url_prefix}{l.get('id')}"
        listings.extend(extra)

    # ── iter300 P2 — seller stats: completed auctions / items sold ──
    _ended_union = ["ended", "sold", "completed", "ended_no_sale", "expired"]
    completed_auctions = 0
    items_sold = 0
    for coll, owner_field in (("listings", "seller_id"), ("multi_item_listings", "seller_id"),
                              ("vehicle_listings", "seller_id"), ("storage_auctions", "facility_owner_id")):
        owner_q = {"$or": [{"seller_id": user_id}, {owner_field: user_id}]}
        completed_auctions += await db[coll].count_documents(
            {**owner_q, "status": {"$in": _ended_union}})
        items_sold += await db[coll].count_documents({
            **owner_q,
            "$and": [{"$or": [
                {"status": "sold"},
                {"status": {"$in": ["ended", "completed"]},
                 "$or": [{"winner_user_id": {"$nin": [None, ""]}},
                         {"winner_id": {"$nin": [None, ""]}}]},
            ]}],
        })
    followers_count = await db.seller_follows.count_documents({"seller_id": user_id})

    return {
        "seller": {
            "id": user.get("id"),
            "name": user.get("name"),
            "picture": user.get("picture"),
            "subscription_tier": tier,
            "joined": user.get("created_at"),
            # iter300 — public badges
            "is_top_seller": bool(user.get("is_top_seller")),
            "is_verified": bool(user.get("identity_verified") or user.get("is_verified")),
            "account_type": user.get("account_type"),
            "role": user.get("role"),
        },
        "storefront": storefront or {
            "banner_url": None,
            "tagline": "",
            "about": "",
            "accent_color": "#06b6d4",
        },
        "listings": listings,
        "stats": {
            "completed_auctions": completed_auctions,
            "items_sold": items_sold,
            "followers": followers_count,
        },
        "has_storefront": tier in PARTNER_PRO_TIERS,
    }


@partner_pro_router.put("/partner-pro/storefront")
async def update_storefront(
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    """Update the current user's branded storefront."""
    _require_partner_pro(current_user)
    db = get_db()

    allowed = {"tagline", "about", "accent_color", "banner_url"}
    updates = {k: v for k, v in payload.items() if k in allowed}
    updates["user_id"] = current_user.id
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.storefronts.update_one(
        {"user_id": current_user.id},
        {"$set": updates},
        upsert=True,
    )
    return {"success": True, "storefront": updates}


# =====================================================================
# FEATURED LISTINGS MANAGEMENT
# =====================================================================

@partner_pro_router.get("/partner-pro/featured-listings")
async def get_featured_listings_status(
    current_user: User = Depends(get_current_user),
):
    """Get the user's featured listing usage for the current month."""
    _require_partner_pro(current_user)
    db = get_db()

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    used = await db.featured_listings.count_documents({
        "user_id": current_user.id,
        "featured_at": {"$gte": month_start},
    })

    tier = getattr(current_user, "subscription_tier", "free")
    limit = 10 if tier == "partner_pro" else (-1 if tier == "vip" else 0)

    return {
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used) if limit >= 0 else -1,
        "month": now.strftime("%Y-%m"),
    }


@partner_pro_router.post("/partner-pro/featured-listings/{listing_id}")
async def feature_listing(
    listing_id: str,
    current_user: User = Depends(get_current_user),
):
    """Mark a listing as featured for the current month."""
    _require_partner_pro(current_user)
    db = get_db()

    listing = await db.listings.find_one({"id": listing_id, "seller_id": current_user.id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    tier = getattr(current_user, "subscription_tier", "free")
    limit = 10 if tier == "partner_pro" else -1

    if limit > 0:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        used = await db.featured_listings.count_documents({
            "user_id": current_user.id,
            "featured_at": {"$gte": month_start},
        })
        if used >= limit:
            raise HTTPException(status_code=400, detail=f"Monthly featured listing limit reached ({limit})")

    await db.featured_listings.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "listing_id": listing_id,
        "featured_at": datetime.now(timezone.utc).isoformat(),
    })

    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {"is_featured": True, "featured_at": datetime.now(timezone.utc).isoformat()}},
    )

    return {"success": True, "message": "Listing featured successfully"}


# =====================================================================
# EARLY AUCTION ACCESS
# =====================================================================

@partner_pro_router.get("/partner-pro/early-access")
async def get_early_access_listings(
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    """
    Get listings that are in the early-access window (visible only to Partner Pro / VIP).
    These are auctions that haven't started publicly yet but are within 2h of going live.
    """
    _require_partner_pro(current_user)
    db = get_db()

    now = datetime.now(timezone.utc)
    early_window = now + timedelta(hours=2)

    early_listings = await db.listings.find(
        {
            "status": "scheduled",
            "auction_start_date": {
                "$gte": now.isoformat(),
                "$lte": early_window.isoformat(),
            },
        },
        {"_id": 0},
    ).sort("auction_start_date", 1).limit(limit).to_list(limit)

    return {
        "success": True,
        "early_access_listings": early_listings,
        "count": len(early_listings),
        "window_hours": 2,
    }
