"""
iter271 — External email campaign admin routes.

Completely isolated from the platform `email_campaigns` collection.
Implements:

  • Campaign CRUD + status transitions
  • Manual + CSV recipient ingestion (dedupe + suppression filter)
  • Attachment upload / download / delete (PDF, JPG, PNG, DOCX, XLSX)
  • Test send, schedule, send-now (batched), pause, cancel
  • Analytics fetch + manual refresh
  • External suppression list management
  • Public unsubscribe handler (`GET /api/external/unsubscribe?token=...`)
"""
from __future__ import annotations

import csv
import io
import logging
import mimetypes
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter, Depends, File, HTTPException, Query, UploadFile,
)
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from deps import User, get_current_user, get_db
from services.external_email import (
    EXTERNAL_FROM_EMAIL, EXTERNAL_FROM_NAME,
    EXTERNAL_REPLY_TO, EXTERNAL_REPLY_TO_NAME,
    casl_footer_html, decode_unsubscribe_token, send_external_campaign_email,
    validate_casl,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/external-campaigns", tags=["External Campaigns"])
public_router = APIRouter(prefix="/external", tags=["External Public"])
suppression_router = APIRouter(prefix="/admin/external-suppressions", tags=["External Suppressions"])


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
ATTACHMENT_BASE = "/app/uploads/campaign_attachments/external"
MAX_ATTACHMENT_BYTES = 3 * 1024 * 1024  # 3 MB
MAX_ATTACHMENTS_PER_CAMPAIGN = 3
MAX_CSV_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_CSV_ROWS = 10_000
ALLOWED_ATTACHMENT_EXT = {"pdf", "jpg", "jpeg", "png", "docx", "xlsx"}

VALID_STATUSES = {"draft", "scheduled", "sending", "sent", "failed", "paused"}


def _require_admin(user: User) -> None:
    if not (getattr(user, "is_admin", False) or getattr(user, "role", None) == "admin"):
        raise HTTPException(status_code=403, detail="Admin only")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def _campaign_to_payload(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Strip Mongo ObjectId; the `id` field is the canonical key."""
    if not doc:
        return doc
    out = {k: v for k, v in doc.items() if k != "_id"}
    return out


def _empty_analytics() -> Dict[str, Any]:
    return {
        "delivered": 0, "delivery_rate_pct": 0.0,
        "opened": 0,    "open_rate_pct": 0.0,
        "clicked": 0,   "click_rate_pct": 0.0,
        "bounced": 0,   "bounce_rate_pct": 0.0,
        "unsubscribed": 0,
        "spam_reports": 0,
        # iter272 — Conversion ROI counters wired in by the auth +
        # partner/webhook flows. `registrations` increments on
        # signup-binding; `premium_upgrades` increments when a tracked
        # user pays their partner annual fee (Stripe checkout, free
        # activation coupon, or subscription renewal).
        "registrations": 0,
        "premium_upgrades": 0,
        "last_updated_at": None,
    }


# ─── Schemas ──────────────────────────────────────────────────────────


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    subject_en: str = Field(..., min_length=2, max_length=300)
    subject_fr: Optional[str] = None
    body_html_en: str = Field(..., min_length=10)
    body_html_fr: Optional[str] = None
    cta_label_en: Optional[str] = "Register Now"
    cta_label_fr: Optional[str] = "S'inscrire maintenant"
    cta_url: Optional[str] = "https://bidvex.com/register"
    reply_to_email: Optional[str] = EXTERNAL_REPLY_TO
    scheduled_at: Optional[datetime] = None
    # iter274 — Auctioneer acquisition coupon attachment. When
    # `attach_trial_coupon=True`, every recipient gets a unique
    # `BVX-TRIAL-*` code minted on send-now and the `{trial_signup_url}`
    # template token in the body resolves to a deep registration link
    # that skips the annual fee gate.
    # iter309 D3 — Added `partner` (30-day generic Partner Account trial).
    attach_trial_coupon: bool = False
    trial_partner_type: Optional[str] = Field(
        default=None, pattern="^(dealer|broker|storage|partner)$",
    )


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    subject_en: Optional[str] = None
    subject_fr: Optional[str] = None
    body_html_en: Optional[str] = None
    body_html_fr: Optional[str] = None
    cta_label_en: Optional[str] = None
    cta_label_fr: Optional[str] = None
    cta_url: Optional[str] = None
    reply_to_email: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    attach_trial_coupon: Optional[bool] = None
    trial_partner_type: Optional[str] = Field(
        default=None, pattern="^(dealer|broker|storage|partner)$",
    )


class ManualRecipients(BaseModel):
    emails: List[str] = Field(default_factory=list)


class ScheduleBody(BaseModel):
    scheduled_at: datetime


class TestSendBody(BaseModel):
    to_email: str


class SuppressionAdd(BaseModel):
    email: str
    reason: str = "manual"


# ─── 2A — Campaign CRUD ───────────────────────────────────────────────


@router.post("")
async def create_campaign(body: CampaignCreate, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()

    campaign_id = _new_id()
    utm_campaign = re.sub(r"[^a-zA-Z0-9_-]+", "_", body.name.strip().lower())[:60]
    doc = {
        "id":             campaign_id,
        "name":           body.name.strip(),
        "subject_en":     body.subject_en.strip(),
        "subject_fr":     (body.subject_fr or body.subject_en).strip(),
        "body_html_en":   body.body_html_en,
        "body_html_fr":   body.body_html_fr or body.body_html_en,
        "from_name":      EXTERNAL_FROM_NAME,
        "from_email":     EXTERNAL_FROM_EMAIL,
        "reply_to_email": body.reply_to_email or EXTERNAL_REPLY_TO,
        "recipient_source":  "manual_list",
        "recipient_emails":  [],
        "recipient_count":   0,
        "recipient_file_url": None,
        "attachments":   [],
        "cta_label_en":  body.cta_label_en,
        "cta_label_fr":  body.cta_label_fr,
        "cta_url":       body.cta_url,
        "utm_source":    "email",
        "utm_medium":    "marketing",
        "utm_campaign":  utm_campaign,
        "status":        "draft",
        "scheduled_at":  body.scheduled_at.isoformat() if body.scheduled_at else None,
        "sent_at":       None,
        "created_at":    _now_iso(),
        "created_by":    current_user.email or current_user.id,
        "updated_at":    _now_iso(),
        "analytics":     _empty_analytics(),
        "custom_args":   {"campaign_id": campaign_id, "campaign_type": "external"},
        # iter274 — Auctioneer coupon attachment metadata. Defaults
        # `attach_trial_coupon=False` keep existing iter271 campaigns
        # behaving unchanged.
        "attach_trial_coupon": bool(body.attach_trial_coupon),
        "trial_partner_type":  body.trial_partner_type if body.attach_trial_coupon else None,
    }
    await db.external_email_campaigns.insert_one(doc)
    return {"campaign_id": campaign_id, "status": "draft"}


@router.get("")
async def list_campaigns(
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if search:
        q["name"] = {"$regex": re.escape(search), "$options": "i"}
    total = await db.external_email_campaigns.count_documents(q)
    page = max(1, int(page))
    limit = max(1, min(200, int(limit)))
    cursor = db.external_email_campaigns.find(q, {"_id": 0}) \
        .sort("created_at", -1).skip((page - 1) * limit).limit(limit)
    items: List[Dict[str, Any]] = await cursor.to_list(length=limit)
    return {
        "campaigns": items,
        "total":     total,
        "page":      page,
        "pages":     (total + limit - 1) // limit,
    }


@router.get("/{campaign_id}")
async def get_campaign(campaign_id: str, current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return doc


@router.patch("/{campaign_id}")
async def update_campaign(
    campaign_id: str, body: CampaignUpdate,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if doc.get("status") != "draft":
        raise HTTPException(status_code=400, detail="Only draft campaigns can be edited")
    update = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "scheduled_at" in update and update["scheduled_at"]:
        update["scheduled_at"] = update["scheduled_at"].isoformat()
    update["updated_at"] = _now_iso()
    await db.external_email_campaigns.update_one({"id": campaign_id}, {"$set": update})
    return await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0})


@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: str, current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if doc.get("status") not in ("draft", "scheduled"):
        raise HTTPException(status_code=400, detail="Only draft or scheduled campaigns can be deleted")

    # Delete attachments from disk + collection.
    cdir = os.path.join(ATTACHMENT_BASE, campaign_id)
    if os.path.isdir(cdir):
        for fn in os.listdir(cdir):
            try:
                os.remove(os.path.join(cdir, fn))
            except Exception:
                pass
        try:
            os.rmdir(cdir)
        except Exception:
            pass
    await db.external_campaign_attachments.delete_many({"campaign_id": campaign_id})
    await db.external_email_campaigns.delete_one({"id": campaign_id})
    return {"deleted": True}


# ─── 2B — Recipient management ────────────────────────────────────────


async def _suppressed_set(db, candidates: List[str]) -> set:
    if not candidates:
        return set()
    cur = db.external_email_suppressions.find(
        {"email": {"$in": candidates}}, {"_id": 0, "email": 1},
    )
    return {d["email"] async for d in cur}


def _normalize_emails(raw: List[str]) -> Dict[str, List[str]]:
    valid: List[str] = []
    invalid: List[str] = []
    seen = set()
    for e in raw or []:
        e = (e or "").strip().lower()
        if not e:
            continue
        if not EMAIL_RE.match(e):
            invalid.append(e)
            continue
        if e in seen:
            continue
        seen.add(e)
        valid.append(e)
    return {"valid": valid, "invalid": invalid}


@router.post("/{campaign_id}/recipients/manual")
async def add_recipients_manual(
    campaign_id: str, body: ManualRecipients,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if doc.get("status") != "draft":
        raise HTTPException(status_code=400, detail="Only draft campaigns accept recipient edits")

    parsed = _normalize_emails(body.emails)
    suppressed = await _suppressed_set(db, parsed["valid"])

    existing = set(doc.get("recipient_emails") or [])
    duplicates = 0
    suppressed_count = 0
    added: List[str] = []
    for e in parsed["valid"]:
        if e in suppressed:
            suppressed_count += 1
            continue
        if e in existing:
            duplicates += 1
            continue
        existing.add(e)
        added.append(e)

    new_list = sorted(existing)
    await db.external_email_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {
            "recipient_source": "manual_list",
            "recipient_emails": new_list,
            "recipient_count":  len(new_list),
            "updated_at":       _now_iso(),
        }},
    )
    return {
        "added":      len(added),
        "duplicates": duplicates,
        "suppressed": suppressed_count,
        "invalid":    len(parsed["invalid"]),
        "total":      len(new_list),
    }


@router.post("/{campaign_id}/recipients/csv")
async def add_recipients_csv(
    campaign_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if doc.get("status") != "draft":
        raise HTTPException(status_code=400, detail="Only draft campaigns accept recipient edits")

    contents = await file.read()
    if len(contents) > MAX_CSV_BYTES:
        raise HTTPException(status_code=400, detail=f"CSV too large (max {MAX_CSV_BYTES // 1024 // 1024} MB)")

    # Best-effort decode; tolerate UTF-8 BOM + Latin-1.
    text = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = contents.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise HTTPException(status_code=400, detail="Unable to decode CSV file")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV is empty or missing header row")
    # Tolerate capitalised / quoted headers.
    fields_lower = {(f or "").strip().lower(): f for f in reader.fieldnames}
    if "email" not in fields_lower:
        raise HTTPException(status_code=400, detail='CSV must contain an "email" column')
    email_field = fields_lower["email"]

    rows = 0
    candidates: List[str] = []
    for row in reader:
        rows += 1
        if rows > MAX_CSV_ROWS:
            break
        candidates.append((row.get(email_field) or "").strip())

    parsed = _normalize_emails(candidates)
    suppressed = await _suppressed_set(db, parsed["valid"])

    existing = set(doc.get("recipient_emails") or [])
    added: List[str] = []
    for e in parsed["valid"]:
        if e in suppressed or e in existing:
            continue
        existing.add(e)
        added.append(e)

    new_list = sorted(existing)
    await db.external_email_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {
            "recipient_source": "csv_upload",
            "recipient_emails": new_list,
            "recipient_count":  len(new_list),
            "updated_at":       _now_iso(),
        }},
    )
    return {
        "processed":  rows,
        "added":      len(added),
        "invalid":    len(parsed["invalid"]),
        "suppressed": len(suppressed),
        "sample":     new_list[:5],
        "total":      len(new_list),
    }


@router.get("/{campaign_id}/recipients/preview")
async def preview_recipients(
    campaign_id: str, current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0, "recipient_emails": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    emails = doc.get("recipient_emails") or []
    suppressed = await _suppressed_set(db, emails)
    return {
        "total":               len(emails) - len(suppressed),
        "sample":              [e for e in emails if e not in suppressed][:10],
        "suppressed_excluded": len(suppressed),
    }


@router.delete("/{campaign_id}/recipients")
async def clear_recipients(
    campaign_id: str, current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if doc.get("status") != "draft":
        raise HTTPException(status_code=400, detail="Only draft campaigns accept recipient edits")
    await db.external_email_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"recipient_emails": [], "recipient_count": 0, "updated_at": _now_iso()}},
    )
    return {"cleared": True}


# ─── 2C — Attachment management ───────────────────────────────────────


@router.post("/{campaign_id}/attachments")
async def upload_attachment(
    campaign_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if doc.get("status") != "draft":
        raise HTTPException(status_code=400, detail="Only draft campaigns accept attachments")

    existing = list(doc.get("attachments") or [])
    if len(existing) >= MAX_ATTACHMENTS_PER_CAMPAIGN:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_ATTACHMENTS_PER_CAMPAIGN} attachments per campaign",
        )

    filename = (file.filename or "upload").strip()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_ATTACHMENT_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '.{ext}' — allowed: {sorted(ALLOWED_ATTACHMENT_EXT)}",
        )

    contents = await file.read()
    if len(contents) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {len(contents) / 1024 / 1024:.2f} MB (max 3 MB)",
        )

    target_dir = os.path.join(ATTACHMENT_BASE, campaign_id)
    os.makedirs(target_dir, exist_ok=True)
    stored_filename = f"{uuid.uuid4().hex}_{filename.replace('/', '_').replace(' ', '_')}"
    fpath = os.path.join(target_dir, stored_filename)
    with open(fpath, "wb") as fh:
        fh.write(contents)

    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    attachment_id = _new_id()
    att_doc = {
        "id":                attachment_id,
        "campaign_id":       campaign_id,
        "original_filename": filename,
        "stored_filename":   stored_filename,
        "file_path":         fpath,
        "file_size_bytes":   len(contents),
        "mime_type":         mime_type,
        "uploaded_by":       current_user.email or current_user.id,
        "uploaded_at":       _now_iso(),
    }
    await db.external_campaign_attachments.insert_one(att_doc)

    public_summary = {
        "id":                attachment_id,
        "filename":          filename,
        "file_url":          f"/uploads/campaign_attachments/external/{campaign_id}/{stored_filename}",
        "file_size_bytes":   len(contents),
        "mime_type":         mime_type,
        "uploaded_at":       att_doc["uploaded_at"],
    }
    existing.append(public_summary)
    await db.external_email_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"attachments": existing, "updated_at": _now_iso()}},
    )
    return {
        "attachment_id": attachment_id,
        "filename":      filename,
        "size_kb":       round(len(contents) / 1024, 2),
        "mime_type":     mime_type,
    }


@router.delete("/{campaign_id}/attachments/{attachment_id}")
async def delete_attachment(
    campaign_id: str, attachment_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if doc.get("status") != "draft":
        raise HTTPException(status_code=400, detail="Only draft campaigns accept attachment deletion")

    att = await db.external_campaign_attachments.find_one(
        {"id": attachment_id, "campaign_id": campaign_id}, {"_id": 0},
    )
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")

    fpath = att.get("file_path")
    if fpath and os.path.isfile(fpath):
        try:
            os.remove(fpath)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[external-attach-delete] {fpath}: {exc}")

    await db.external_campaign_attachments.delete_one({"id": attachment_id})
    remaining = [a for a in (doc.get("attachments") or []) if a.get("id") != attachment_id]
    await db.external_email_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"attachments": remaining, "updated_at": _now_iso()}},
    )
    return {"deleted": True}


@router.get("/{campaign_id}/attachments/{attachment_id}/download")
async def download_attachment(
    campaign_id: str, attachment_id: str,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    att = await db.external_campaign_attachments.find_one(
        {"id": attachment_id, "campaign_id": campaign_id}, {"_id": 0},
    )
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    fpath = att.get("file_path")
    if not fpath or not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="File missing on disk")
    # Path-traversal guard.
    base_resolved = os.path.realpath(ATTACHMENT_BASE)
    resolved = os.path.realpath(fpath)
    if not resolved.startswith(base_resolved + os.sep):
        raise HTTPException(status_code=403, detail="Access denied")
    return FileResponse(
        path=resolved,
        media_type=att.get("mime_type") or "application/octet-stream",
        filename=att.get("original_filename") or os.path.basename(resolved),
    )


# ─── 2D — Send + schedule ─────────────────────────────────────────────


def _collect_attachments_for_send(att_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map the public summary list back into the file_path objects the
    sender expects. Reads from external_campaign_attachments isn't
    needed when the in-doc summary carries the URL."""
    out: List[Dict[str, Any]] = []
    for a in att_list or []:
        url = a.get("file_url") or ""
        if not url:
            continue
        # The URL is /uploads/campaign_attachments/external/{cid}/{fn}.
        rel = url.lstrip("/")
        if rel.startswith("uploads/"):
            rel = rel[len("uploads/"):]
        fpath = os.path.join("/app/uploads", rel)
        out.append({
            "file_path":         fpath,
            "original_filename": a.get("filename"),
            "mime_type":         a.get("mime_type"),
        })
    return out


async def _do_dispatch(
    db, doc: Dict[str, Any], to_emails: List[str], *, is_test: bool = False,
) -> Dict[str, Any]:
    """Iterate the recipient list, suppression-check, then send one by
    one. Each failure is collected but never aborts the batch.

    iter272 — Returns extra envelope keys (`fallback_used`,
    `from_emails_used`) so `send-now` can persist them onto the campaign
    document for ROI + debugging visibility.

    iter274 — When the campaign opts into `attach_trial_coupon`, mint a
    unique `BVX-TRIAL-*` code per recipient and substitute
    `{trial_signup_url}` in the body HTML before each send. The minted
    codes are recorded on the partner_trial_coupons collection with
    `source="external_campaign"` and `recipient_email` locked, so a
    forwarded link can't be redeemed by anyone else."""
    err = validate_casl(doc.get("subject_en", ""), doc.get("body_html_en", ""))
    if err:
        raise HTTPException(status_code=400, detail=err)

    suppressed = await _suppressed_set(db, to_emails)
    sent = 0
    skipped = 0
    failures: List[Dict[str, Any]] = []
    fallback_used = 0
    from_emails_used: Dict[str, int] = {}
    coupons_minted = 0
    subject = doc["subject_en"]
    if is_test:
        subject = f"[TEST] {subject}"
    attachments = _collect_attachments_for_send(doc.get("attachments") or [])
    base_body = doc["body_html_en"]

    # iter274 — Coupon attachment mode pre-resolves the partner_type +
    # minting helper so the per-recipient loop stays a single import.
    coupon_mode = bool(doc.get("attach_trial_coupon")) and bool(doc.get("trial_partner_type"))
    if coupon_mode:
        from routes.trial_coupons import (
            TRIAL_DURATIONS, build_signup_url, _ensure_unique_code, _now_iso,
        )
        from datetime import timedelta, datetime as _dt, timezone as _tz

    for email in to_emails:
        if email in suppressed:
            skipped += 1
            continue

        # iter274 — Resolve the per-recipient body (with coupon URL) BEFORE
        # the actual send. If minting fails (DB hiccup), we still ship the
        # campaign — the {trial_signup_url} token just resolves to the
        # generic /register URL so the recipient lands cleanly.
        body_for_recipient = base_body
        if coupon_mode:
            try:
                code = await _ensure_unique_code(db)
                expires = (_dt.now(_tz.utc)
                           + timedelta(days=90)).isoformat()
                coupon_doc = {
                    "id":              str(uuid.uuid4()),
                    "code":            code,
                    "partner_type":    doc["trial_partner_type"],
                    "duration_days":   TRIAL_DURATIONS[doc["trial_partner_type"]],
                    "status":          "issued",
                    "created_by":      doc.get("created_by") or "system",
                    "created_at":      _now_iso(),
                    "expires_at":      expires,
                    "redeemed_by_user_id": None,
                    "redeemed_at":     None,
                    "source":          "external_campaign",
                    "campaign_id":     doc["id"],
                    "campaign_slug":   doc.get("utm_campaign"),
                    "recipient_email": email.lower(),
                    "recipient_name":  None,
                    "company_name":    None,
                    "note":            None,
                }
                await db.partner_trial_coupons.insert_one(coupon_doc)
                signup_url = build_signup_url(
                    code,
                    campaign_slug=doc.get("utm_campaign"),
                )
                body_for_recipient = base_body.replace(
                    "{trial_signup_url}", signup_url,
                ).replace("{promo_code}", code)
                coupons_minted += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[iter274 coupon-mint] failed for {email}: {exc}")
                # Fallback — drop the placeholders so they don't ship raw.
                body_for_recipient = (
                    base_body
                    .replace("{trial_signup_url}", "https://bidvex.com/register")
                    .replace("{promo_code}", "")
                )

        try:
            result = await send_external_campaign_email(
                to_email=email,
                to_name="",
                subject=subject,
                body_html=body_for_recipient,
                campaign_id=doc["id"],
                utm_campaign=doc.get("utm_campaign") or doc["id"],
                attachments=attachments,
                language="en",
            )
        except Exception as exc:  # noqa: BLE001
            # iter272 — Defensive: send_external_campaign_email is meant to
            # never raise, but if it does (e.g. SendGrid SDK bug), we
            # still keep the batch alive instead of crashing the request.
            logger.error(f"[external-dispatch] unexpected exception for {email}: {exc}")
            failures.append({"to": email, "error": str(exc)})
            continue

        used = result.get("from_email_used") or ""
        if used:
            from_emails_used[used] = from_emails_used.get(used, 0) + 1
        if result.get("fallback_used"):
            fallback_used += 1

        status = result.get("status")
        if status == "sent":
            sent += 1
        elif status == "logged":
            sent += 1  # treat dev-mode logged as sent for stats
        else:
            failures.append({"to": email, "error": result.get("message", "unknown")})

    return {
        "sent":             sent,
        "skipped":          skipped,
        "failures":         failures,
        "fallback_used":    fallback_used,
        "from_emails_used": from_emails_used,
        "coupons_minted":   coupons_minted,
    }


@router.post("/{campaign_id}/send-test")
async def send_test(
    campaign_id: str, body: TestSendBody,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    to_email = (body.to_email or current_user.email or "").strip().lower()
    if not to_email or not EMAIL_RE.match(to_email):
        raise HTTPException(status_code=400, detail="Invalid recipient email")
    result = await _do_dispatch(db, doc, [to_email], is_test=True)
    return {"sent": result["sent"] >= 1, "to": to_email}


@router.post("/{campaign_id}/schedule")
async def schedule_campaign(
    campaign_id: str, body: ScheduleBody,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if doc.get("status") not in ("draft", "scheduled"):
        raise HTTPException(status_code=400, detail="Only draft campaigns can be scheduled")
    when = body.scheduled_at
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if when <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="scheduled_at must be in the future")
    await db.external_email_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"status": "scheduled", "scheduled_at": when.isoformat(), "updated_at": _now_iso()}},
    )
    return {"scheduled_at": when.isoformat(), "status": "scheduled"}


@router.post("/{campaign_id}/send-now")
async def send_now(
    campaign_id: str, current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if doc.get("status") not in ("draft", "scheduled"):
        raise HTTPException(status_code=400, detail="Only draft/scheduled campaigns can be sent")

    err = validate_casl(doc.get("subject_en", ""), doc.get("body_html_en", ""))
    if err:
        raise HTTPException(status_code=400, detail=err)

    recipients = doc.get("recipient_emails") or []
    if not recipients:
        raise HTTPException(status_code=400, detail="Campaign has no recipients")

    await db.external_email_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"status": "sending", "updated_at": _now_iso()}},
    )

    result = await _do_dispatch(db, doc, recipients, is_test=False)

    sent_at = _now_iso()
    # iter272 — Status reflects actual SendGrid outcome:
    #   • All recipients suppressed (sent=0, failures=0) → 'sent' (no work).
    #   • At least one delivered → 'sent' (partial success counts).
    #   • Every attempt failed → 'failed'.
    if result["sent"] > 0:
        new_status = "sent"
    elif not result["failures"]:
        new_status = "sent"  # everyone was on the suppression list
    else:
        new_status = "failed"

    update_doc = {
        "status":                     new_status,
        "sent_at":                    sent_at,
        "updated_at":                 sent_at,
        "analytics.delivered":        result["sent"],
        "analytics.last_updated_at":  sent_at,
        # iter272 — Surface the operational metadata so the admin UI
        # can show "X emails shipped via fallback sender" + the
        # last failure message for fast diagnosis.
        # iter274 — Track coupons minted into the same envelope so the
        # ROI dashboard can chart auctioneer acquisition flow per
        # campaign without a second query.
        "last_dispatch": {
            "sent":             result["sent"],
            "skipped":          result["skipped"],
            "failed":           len(result["failures"]),
            "fallback_used":    result.get("fallback_used", 0),
            "coupons_minted":   result.get("coupons_minted", 0),
            "from_emails_used": result.get("from_emails_used", {}),
            "first_failure":   (result["failures"][0]["error"] if result["failures"] else None),
            "dispatched_at":    sent_at,
        },
    }
    await db.external_email_campaigns.update_one(
        {"id": campaign_id},
        {"$set": update_doc},
    )

    return {
        "sent":            result["sent"],
        "skipped":         result["skipped"],
        "failures":        len(result["failures"]),
        "recipient_count": len(recipients),
        "sent_at":         sent_at,
        "status":          new_status,
        "fallback_used":   result.get("fallback_used", 0),
        "coupons_minted":  result.get("coupons_minted", 0),
    }


@router.post("/{campaign_id}/pause")
async def pause_campaign(
    campaign_id: str, current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if doc.get("status") != "sending":
        raise HTTPException(status_code=400, detail="Only a sending campaign can be paused")
    await db.external_email_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"status": "paused", "updated_at": _now_iso()}},
    )
    return {"paused": True, "status": "paused"}


@router.post("/{campaign_id}/cancel")
async def cancel_campaign(
    campaign_id: str, current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if doc.get("status") != "scheduled":
        raise HTTPException(status_code=400, detail="Only a scheduled campaign can be cancelled")
    await db.external_email_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"status": "draft", "scheduled_at": None, "updated_at": _now_iso()}},
    )
    return {"cancelled": True, "status": "draft"}


# ─── 2E — Analytics ───────────────────────────────────────────────────


def _compute_rates(analytics: Dict[str, Any], denom: int) -> Dict[str, Any]:
    if denom <= 0:
        return analytics
    a = dict(analytics)
    a["delivery_rate_pct"] = round((a.get("delivered", 0) / denom) * 100, 2)
    delivered = max(1, a.get("delivered", 0))
    a["open_rate_pct"]   = round((a.get("opened", 0) / delivered) * 100, 2)
    a["click_rate_pct"]  = round((a.get("clicked", 0) / delivered) * 100, 2)
    a["bounce_rate_pct"] = round((a.get("bounced", 0) / denom) * 100, 2)
    return a


@router.get("/{campaign_id}/analytics")
async def get_analytics(
    campaign_id: str, current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    doc = await db.external_email_campaigns.find_one(
        {"id": campaign_id},
        {"_id": 0, "analytics": 1, "recipient_count": 1, "sent_at": 1, "last_dispatch": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Campaign not found")
    a = doc.get("analytics") or _empty_analytics()
    a = _compute_rates(a, doc.get("recipient_count") or 0)
    a["daily_chart"] = a.get("daily_chart") or []
    a["sent_at"] = doc.get("sent_at")
    # iter273 — Surface the fallback-sender retry count to the analytics
    # endpoint so the admin ROI dashboard can chart it without a second
    # round trip into the campaign document.
    last_dispatch = doc.get("last_dispatch") or {}
    a["fallback_dispatches"] = int(last_dispatch.get("fallback_used") or 0)
    a["last_dispatch"] = last_dispatch
    return a


@router.post("/analytics/refresh")
async def refresh_all_analytics(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """SendGrid Stats API key fetch is environment-dependent. This
    endpoint recomputes the derived rates from the stored counters
    so the UI updates immediately even when the Stats API is
    unreachable. The webhook is the canonical event source."""
    _require_admin(current_user)
    db = get_db()
    n = 0
    cursor = db.external_email_campaigns.find({}, {"_id": 0, "id": 1, "analytics": 1, "recipient_count": 1})
    async for doc in cursor:
        a = doc.get("analytics") or _empty_analytics()
        a = _compute_rates(a, doc.get("recipient_count") or 0)
        a["last_updated_at"] = _now_iso()
        await db.external_email_campaigns.update_one(
            {"id": doc["id"]}, {"$set": {"analytics": a}},
        )
        n += 1
    return {"refreshed": n}


# ─── 2F — Unsubscribe ─────────────────────────────────────────────────


@public_router.get("/unsubscribe", response_class=HTMLResponse)
async def public_unsubscribe(token: str = Query(...)):
    """Public endpoint — no auth required. Decodes the JWT, suppresses
    the email, returns a small bilingual confirmation page.

    iter309 D4 — Backward-compat handler for OLD external campaign emails
    that still point to /api/external/unsubscribe?token=... New emails ship
    a canonical https://bidvex.com/unsubscribe?token=...&lang=... URL that
    hits the unified /api/unsubscribe/auto-* endpoints instead. We mirror
    the same DB writes here so already-delivered emails keep working.
    """
    db = get_db()
    try:
        payload = decode_unsubscribe_token(token)
        if payload.get("type") != "external_unsub":
            raise HTTPException(status_code=400, detail="Invalid token type")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        return HTMLResponse(
            f"<h1>Invalid unsubscribe link</h1><p>{exc}</p>",
            status_code=400,
        )

    email = (payload.get("email") or "").strip().lower()
    campaign_id = payload.get("campaign_id")
    lang = (payload.get("lang") or "en").lower()
    if email:
        now = datetime.now(timezone.utc)
        # External suppression row (legacy).
        await db.external_email_suppressions.update_one(
            {"email": email},
            {"$setOnInsert": {
                "email":         email,
                "reason":        "unsubscribe",
                "campaign_id":   campaign_id,
                "suppressed_at": _now_iso(),
                "source":        "external",
            }},
            upsert=True,
        )
        # iter309 D4 — Canonical email_unsubscribed flag + platform suppression
        # so the unified suppression check used by all sender pipelines agrees.
        await db.users.update_one(
            {"email": email},
            {
                "$set": {
                    "email_unsubscribed":          True,
                    "email_unsubscribed_at":       now,
                    "email_unsubscribed_source":   "external",
                    "marketing_unsubscribed":      True,
                    "marketing_unsubscribed_at":   now,
                    "marketing_unsubscribed_source": "link",
                },
                "$setOnInsert": {
                    "id":              str(uuid.uuid4()),
                    "email":           email,
                    "created_at":      now,
                    "is_contact_only": True,
                },
            },
            upsert=True,
        )
        await db.email_suppressions.update_one(
            {"email": email},
            {"$set": {"email": email, "unsubscribed_at": now, "source": "external"}},
            upsert=True,
        )
        if campaign_id:
            await db.external_email_campaigns.update_one(
                {"id": campaign_id},
                {"$inc": {"analytics.unsubscribed": 1},
                 "$set": {"analytics.last_updated_at": _now_iso()}},
            )

        # iter310 — Unsubscribe Audit Trail. Legacy /api/external/unsubscribe
        # path mirrors the canonical /api/unsubscribe/auto-confirm writer.
        try:
            user_doc = await db.users.find_one({"email": email}, {"_id": 0, "id": 1})
            await db.unsubscribe_events.insert_one({
                "id":              str(uuid.uuid4()),
                "user_id":         (user_doc or {}).get("id"),
                "email":           email,
                "campaign_id":     campaign_id,
                "source":          "external_campaign",
                "unsubscribed_at": now,
                "token_type":      "jwt",
                "lang":            lang or "en",
                "event":           "unsubscribed",
                "ip":              None,
                "user_agent":      None,
            })
        except Exception as audit_err:
            logger.warning(f"[UNSUBSCRIBE audit legacy] insert failed: {audit_err}")

    if lang == "fr":
        msg = "Vous avez été désabonné avec succès."
    else:
        msg = "You have been unsubscribed successfully."
    return HTMLResponse(
        f"""<!doctype html><html><head><meta charset="utf-8"><title>Unsubscribed</title>
        <style>body{{font-family:Arial,sans-serif;text-align:center;padding:48px;color:#1e293b}}</style>
        </head><body><h1>✅ {msg}</h1>
        <p>BidVex Inc. — Sherbrooke, QC, Canada</p>
        <p><a href="https://bidvex.com" style="color:#2f80ff">bidvex.com</a></p>
        </body></html>""",
    )


# ─── External suppression list management ─────────────────────────────


@suppression_router.post("/add")
async def add_suppression(
    body: SuppressionAdd, current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    email = (body.email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email")
    await db.external_email_suppressions.update_one(
        {"email": email},
        {"$setOnInsert": {
            "email": email, "reason": body.reason,
            "campaign_id": None, "suppressed_at": _now_iso(),
        }},
        upsert=True,
    )
    return {"added": True, "email": email}


@suppression_router.delete("/{email}")
async def remove_suppression(
    email: str, current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    res = await db.external_email_suppressions.delete_one({"email": email.strip().lower()})
    return {"removed": res.deleted_count > 0}


@suppression_router.get("")
async def list_suppressions(
    page: int = 1, limit: int = 100, search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    _require_admin(current_user)
    db = get_db()
    q: Dict[str, Any] = {}
    if search:
        q["email"] = {"$regex": re.escape(search), "$options": "i"}
    total = await db.external_email_suppressions.count_documents(q)
    page = max(1, int(page))
    limit = max(1, min(500, int(limit)))
    cursor = db.external_email_suppressions.find(q, {"_id": 0}) \
        .sort("suppressed_at", -1).skip((page - 1) * limit).limit(limit)
    items = await cursor.to_list(length=limit)
    return {"items": items, "total": total, "page": page,
            "pages": (total + limit - 1) // limit}


__all__ = ["router", "public_router", "suppression_router"]
