"""
BidVex Careers module — public + admin REST API.

Mounted under /api/careers in server.py. Isolated from every other route
file — DO NOT cross-import job logic into other modules.

Endpoints
─────────
Public (no auth):
  GET    /api/careers/jobs
  GET    /api/careers/jobs/{job_id}
  POST   /api/careers/jobs/{job_id}/apply        (multipart/form-data)

Admin-only:
  GET    /api/admin/careers/jobs
  POST   /api/admin/careers/jobs
  PATCH  /api/admin/careers/jobs/{job_id}
  DELETE /api/admin/careers/jobs/{job_id}
  POST   /api/admin/careers/jobs/{job_id}/activate
  POST   /api/admin/careers/jobs/{job_id}/archive
  GET    /api/admin/careers/applicants
  GET    /api/admin/careers/applicants/{applicant_id}
  PATCH  /api/admin/careers/applicants/{applicant_id}/status
  GET    /api/admin/careers/applicants/{applicant_id}/attachments/{filename}
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile,
    BackgroundTasks,
)
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, EmailStr

from deps import get_current_user, get_db, User
from services.careers_security import (
    CV_MAX_BYTES, COVER_LETTER_MAX_BYTES, PHOTO_MAX_BYTES, CERTIFICATION_MAX_BYTES,
    MAX_PHOTOS, MAX_CERTIFICATIONS,
    validate_file, save_validated_file, safe_resolve_download, ensure_applicant_dir,
)
from services.careers_notifications import (
    send_applicant_confirmation,
    send_admin_new_applicant_notification,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["careers"])

ADMIN_ROLES = {"admin", "super_admin"}
JOB_STATUSES = {"draft", "active", "archived"}
APPLICANT_STATUSES = {"applied", "reviewing", "shortlisted", "rejected"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _role(user: User) -> str:
    return getattr(user, "role", None) or "user"


def require_admin(user: User = Depends(get_current_user)) -> User:
    if _role(user) not in ADMIN_ROLES:
        raise HTTPException(403, "admin only")
    return user


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_public_projection() -> Dict[str, int]:
    return {
        "_id": 0, "id": 1, "title": 1, "title_fr": 1, "department": 1,
        "location": 1, "commission_range": 1,
        "description_en": 1, "description_fr": 1,
        "required_inputs": 1, "created_at": 1,
    }


def _strip_mongo(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc


# ─── Models ─────────────────────────────────────────────────────────────

class RequiredInputs(BaseModel):
    requires_cv: bool = True
    requires_cover_letter: bool = False
    requires_photos: bool = False
    requires_certifications: bool = False
    custom_date_fields: List[str] = Field(default_factory=list)
    custom_text_fields: List[str] = Field(default_factory=list)


class JobOfferCreate(BaseModel):
    title: str
    title_fr: str = ""
    department: str = "Operations"
    location: str = "National"
    status: str = "draft"
    description_en: str = ""
    description_fr: str = ""
    commission_range: Optional[str] = None
    required_inputs: Optional[RequiredInputs] = None


class JobOfferUpdate(BaseModel):
    title: Optional[str] = None
    title_fr: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    description_en: Optional[str] = None
    description_fr: Optional[str] = None
    commission_range: Optional[str] = None
    required_inputs: Optional[RequiredInputs] = None


class ApplicantStatusUpdate(BaseModel):
    status: str
    admin_notes: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════
# PUBLIC ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@router.get("/careers/jobs")
async def list_active_jobs(response: Response) -> Dict[str, Any]:
    """Public: returns ONLY active jobs. Cache-Control: 5 minutes."""
    db = get_db()
    rows = await db.job_offers.find(
        {"status": "active"}, _job_public_projection(),
    ).sort("created_at", -1).to_list(length=200)
    response.headers["Cache-Control"] = "public, max-age=300"
    return {"items": rows, "count": len(rows)}


@router.get("/careers/jobs/{job_id}")
async def get_active_job(job_id: str) -> Dict[str, Any]:
    """Public: single active job detail. Returns 404 for any other status."""
    db = get_db()
    row = await db.job_offers.find_one(
        {"id": job_id, "status": "active"}, _job_public_projection(),
    )
    if not row:
        raise HTTPException(404, "job not found or not active")
    return row


@router.post("/careers/jobs/{job_id}/apply")
async def submit_application(
    job_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    province: str = Form(""),
    preferred_language: str = Form("en"),
    custom_responses: str = Form("{}"),
    cv: Optional[UploadFile] = File(None),
    cover_letter: Optional[UploadFile] = File(None),
    photos: Optional[List[UploadFile]] = File(None),
    certifications: Optional[List[UploadFile]] = File(None),
) -> Dict[str, Any]:
    """Public application submission — multipart/form-data.

    Validates every field + every file (size, extension, MIME magic
    bytes) before persisting. Files land under
    /uploads/careers/{job_id}/{applicant_id}/ with UUID prefixes.
    """
    db = get_db()
    job = await db.job_offers.find_one(
        {"id": job_id, "status": "active"}, {"_id": 0},
    )
    if not job:
        raise HTTPException(404, "job not found or not active")

    # ── Field validation ────────────────────────────────────────────
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(422, {
            "error": "invalid_email", "field": "email",
            "message_en": "Enter a valid email address.",
            "message_fr": "Saisissez une adresse courriel valide.",
        })
    if not (phone or "").strip():
        raise HTTPException(422, {
            "error": "missing_phone", "field": "phone",
            "message_en": "Phone number is required.",
            "message_fr": "Le numéro de téléphone est obligatoire.",
        })
    if not (first_name or "").strip() or not (last_name or "").strip():
        raise HTTPException(422, {
            "error": "missing_name", "field": "name",
            "message_en": "First and last name are required.",
            "message_fr": "Le prénom et le nom sont obligatoires.",
        })

    try:
        custom_responses_obj: Dict[str, Any] = json.loads(custom_responses or "{}")
    except json.JSONDecodeError:
        raise HTTPException(422, {
            "error": "invalid_custom_responses",
            "message_en": "Custom responses must be valid JSON.",
            "message_fr": "Les réponses personnalisées doivent être un JSON valide.",
        })

    req = job.get("required_inputs") or {}
    # Required custom-question fields.
    for label in (req.get("custom_text_fields") or []):
        if not custom_responses_obj.get(label):
            raise HTTPException(422, {
                "error": "missing_custom_field", "field": label,
                "message_en": f"Field '{label}' is required.",
                "message_fr": f"Le champ « {label} » est obligatoire.",
            })
    for label in (req.get("custom_date_fields") or []):
        if not custom_responses_obj.get(label):
            raise HTTPException(422, {
                "error": "missing_custom_field", "field": label,
                "message_en": f"Date '{label}' is required.",
                "message_fr": f"La date « {label} » est obligatoire.",
            })

    # File requirement gates.
    if req.get("requires_cv") and (cv is None or not cv.filename):
        raise HTTPException(422, {
            "error": "cv_required", "field": "cv",
            "message_en": "A CV is required for this position.",
            "message_fr": "Un CV est obligatoire pour ce poste.",
        })
    if req.get("requires_cover_letter") and (cover_letter is None or not cover_letter.filename):
        raise HTTPException(422, {
            "error": "cover_letter_required", "field": "cover_letter",
            "message_en": "A cover letter is required for this position.",
            "message_fr": "Une lettre de motivation est obligatoire pour ce poste.",
        })
    if req.get("requires_photos"):
        if not photos or all((p.filename or "") == "" for p in photos):
            raise HTTPException(422, {
                "error": "photos_required", "field": "photos",
                "message_en": "Portfolio photos are required for this position.",
                "message_fr": "Des photos de portfolio sont obligatoires pour ce poste.",
            })
    if req.get("requires_certifications"):
        if not certifications or all((c.filename or "") == "" for c in certifications):
            raise HTTPException(422, {
                "error": "certifications_required", "field": "certifications",
                "message_en": "Certifications are required for this position.",
                "message_fr": "Des certifications sont obligatoires pour ce poste.",
            })

    if photos and sum(1 for p in photos if p.filename) > MAX_PHOTOS:
        raise HTTPException(422, {
            "error": "too_many_photos",
            "message_en": f"Maximum {MAX_PHOTOS} photos allowed.",
            "message_fr": f"Maximum {MAX_PHOTOS} photos autorisées.",
        })
    if certifications and sum(1 for c in certifications if c.filename) > MAX_CERTIFICATIONS:
        raise HTTPException(422, {
            "error": "too_many_certifications",
            "message_en": f"Maximum {MAX_CERTIFICATIONS} certifications allowed.",
            "message_fr": f"Maximum {MAX_CERTIFICATIONS} certifications autorisées.",
        })

    # ── Persist applicant row (so we know the dir) ──────────────────
    applicant_id = str(uuid.uuid4())
    dest_dir = ensure_applicant_dir(job_id, applicant_id)

    attachments: Dict[str, Any] = {
        "cv_url": None, "cover_letter_url": None, "photos": [], "certifications": [],
    }

    if cv and cv.filename:
        content = await cv.read()
        validate_file(kind="cv", filename=cv.filename, content=content, max_bytes=CV_MAX_BYTES)
        fname, _abs = save_validated_file(
            dest_dir=dest_dir, kind="cv", original_filename=cv.filename, content=content,
        )
        attachments["cv_url"] = fname

    if cover_letter and cover_letter.filename:
        content = await cover_letter.read()
        validate_file(kind="cover_letter", filename=cover_letter.filename,
                       content=content, max_bytes=COVER_LETTER_MAX_BYTES)
        fname, _abs = save_validated_file(
            dest_dir=dest_dir, kind="cover_letter",
            original_filename=cover_letter.filename, content=content,
        )
        attachments["cover_letter_url"] = fname

    if photos:
        for p in photos:
            if not p.filename:
                continue
            content = await p.read()
            validate_file(kind="photos", filename=p.filename, content=content,
                           max_bytes=PHOTO_MAX_BYTES)
            fname, _abs = save_validated_file(
                dest_dir=dest_dir, kind="photos",
                original_filename=p.filename, content=content,
            )
            attachments["photos"].append(fname)

    if certifications:
        for c in certifications:
            if not c.filename:
                continue
            content = await c.read()
            validate_file(kind="certifications", filename=c.filename, content=content,
                           max_bytes=CERTIFICATION_MAX_BYTES)
            fname, _abs = save_validated_file(
                dest_dir=dest_dir, kind="certifications",
                original_filename=c.filename, content=content,
            )
            attachments["certifications"].append(fname)

    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "")
        or ""
    )
    user_agent = request.headers.get("user-agent", "")[:500]

    row = {
        "id":                  applicant_id,
        "job_offer_id":        job_id,
        "first_name":          (first_name or "").strip(),
        "last_name":           (last_name or "").strip(),
        "email":               email,
        "phone":               (phone or "").strip(),
        "province":            (province or "").strip(),
        "preferred_language":  "fr" if (preferred_language or "").lower().startswith("fr") else "en",
        "custom_responses":    custom_responses_obj,
        "attachments":         attachments,
        "status":              "applied",
        "admin_notes":         None,
        "applied_at":          _now_iso(),
        "ip_address":          client_ip,
        "user_agent":          user_agent,
    }
    await db.job_applicants.insert_one(row)

    # Fire-and-forget emails so a SendGrid hiccup never breaks the apply.
    job_title = job.get("title") or "BidVex role"
    background_tasks.add_task(
        send_applicant_confirmation,
        to_email=email,
        first_name=row["first_name"],
        job_title=job_title,
        locale=row["preferred_language"],
    )
    background_tasks.add_task(
        send_admin_new_applicant_notification,
        applicant=row,
        job_title=job_title,
        admin_panel_link=None,
    )

    return {
        "success":      True,
        "applicant_id": applicant_id,
        "message_en":   "Application submitted. We'll be in touch within 5–7 business days.",
        "message_fr":   "Candidature soumise. Nous vous contacterons dans les 5 à 7 jours ouvrables.",
    }


# ═══════════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@router.get("/admin/careers/jobs")
async def admin_list_jobs(
    user: User = Depends(require_admin),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    db = get_db()
    q: Dict[str, Any] = {}
    if status and status in JOB_STATUSES:
        q["status"] = status
    if search:
        q["$or"] = [
            {"title":    {"$regex": re.escape(search), "$options": "i"}},
            {"title_fr": {"$regex": re.escape(search), "$options": "i"}},
            {"department": {"$regex": re.escape(search), "$options": "i"}},
        ]
    skip = (page - 1) * limit
    total = await db.job_offers.count_documents(q)
    rows = await db.job_offers.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(length=limit)
    # Annotate with applicant count.
    for r in rows:
        r["applicants_count"] = await db.job_applicants.count_documents({"job_offer_id": r["id"]})
    return {"items": rows, "count": total, "page": page, "limit": limit}


@router.post("/admin/careers/jobs")
async def admin_create_job(body: JobOfferCreate,
                             user: User = Depends(require_admin)) -> Dict[str, Any]:
    db = get_db()
    if body.status not in JOB_STATUSES:
        raise HTTPException(422, "invalid status")
    now = _now_iso()
    row = {
        "id":               str(uuid.uuid4()),
        "title":            body.title.strip(),
        "title_fr":         (body.title_fr or "").strip(),
        "department":       body.department,
        "location":         body.location,
        "status":           body.status,
        "description_en":   body.description_en or "",
        "description_fr":   body.description_fr or "",
        "commission_range": body.commission_range,
        "required_inputs":  (body.required_inputs or RequiredInputs()).model_dump(),
        "created_by":       getattr(user, "email", None),
        "created_at":       now,
        "updated_at":       now,
    }
    await db.job_offers.insert_one(row)
    row.pop("_id", None)
    return row


@router.patch("/admin/careers/jobs/{job_id}")
async def admin_update_job(job_id: str, body: JobOfferUpdate,
                              user: User = Depends(require_admin)) -> Dict[str, Any]:
    db = get_db()
    existing = await db.job_offers.find_one({"id": job_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "job not found")
    patch: Dict[str, Any] = {"updated_at": _now_iso()}
    src = body.model_dump(exclude_unset=True)
    for k, v in src.items():
        if k == "required_inputs" and v is not None:
            patch[k] = RequiredInputs(**v).model_dump() if isinstance(v, dict) else v.model_dump()
        elif k == "status":
            if v not in JOB_STATUSES:
                raise HTTPException(422, "invalid status")
            patch[k] = v
        else:
            patch[k] = v
    await db.job_offers.update_one({"id": job_id}, {"$set": patch})
    return {**existing, **patch}


@router.delete("/admin/careers/jobs/{job_id}")
async def admin_delete_job(job_id: str, user: User = Depends(require_admin)) -> Dict[str, Any]:
    db = get_db()
    existing = await db.job_offers.find_one({"id": job_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "job not found")
    applicants = await db.job_applicants.count_documents({"job_offer_id": job_id})
    if applicants > 0:
        raise HTTPException(409, {
            "error": "has_applicants",
            "message_en": "Cannot delete a job that has applicants — archive instead.",
            "message_fr": "Impossible de supprimer une offre qui a des candidatures — archivez-la.",
        })
    if existing.get("status") != "draft":
        raise HTTPException(409, {
            "error": "not_draft",
            "message_en": "Only draft jobs can be deleted. Archive active jobs instead.",
            "message_fr": "Seules les offres en brouillon peuvent être supprimées.",
        })
    await db.job_offers.delete_one({"id": job_id})
    return {"deleted": True, "id": job_id}


@router.post("/admin/careers/jobs/{job_id}/activate")
async def admin_activate_job(job_id: str, user: User = Depends(require_admin)) -> Dict[str, Any]:
    db = get_db()
    job = await db.job_offers.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(404, "job not found")
    missing: List[str] = []
    for k in ("title", "description_en", "description_fr"):
        if not (job.get(k) or "").strip():
            missing.append(k)
    if missing:
        raise HTTPException(422, {
            "error": "incomplete_job",
            "missing": missing,
            "message_en": f"Cannot activate — missing: {', '.join(missing)}.",
            "message_fr": f"Activation impossible — champs manquants : {', '.join(missing)}.",
        })
    await db.job_offers.update_one(
        {"id": job_id}, {"$set": {"status": "active", "updated_at": _now_iso()}},
    )
    return {"id": job_id, "status": "active"}


@router.post("/admin/careers/jobs/{job_id}/archive")
async def admin_archive_job(job_id: str, user: User = Depends(require_admin)) -> Dict[str, Any]:
    db = get_db()
    job = await db.job_offers.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(404, "job not found")
    await db.job_offers.update_one(
        {"id": job_id}, {"$set": {"status": "archived", "updated_at": _now_iso()}},
    )
    return {"id": job_id, "status": "archived"}


@router.get("/admin/careers/applicants")
async def admin_list_applicants(
    user: User = Depends(require_admin),
    job_offer_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    province: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    db = get_db()
    q: Dict[str, Any] = {}
    if job_offer_id:
        q["job_offer_id"] = job_offer_id
    if status and status in APPLICANT_STATUSES:
        q["status"] = status
    if province:
        q["province"] = province
    if search:
        q["$or"] = [
            {"first_name": {"$regex": re.escape(search), "$options": "i"}},
            {"last_name":  {"$regex": re.escape(search), "$options": "i"}},
            {"email":       {"$regex": re.escape(search), "$options": "i"}},
        ]
    if date_from or date_to:
        rng: Dict[str, str] = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        q["applied_at"] = rng

    skip = (page - 1) * limit
    total = await db.job_applicants.count_documents(q)
    rows = await db.job_applicants.find(q, {"_id": 0}).sort("applied_at", -1).skip(skip).limit(limit).to_list(length=limit)

    # Join job title in.
    job_ids = list({r["job_offer_id"] for r in rows if r.get("job_offer_id")})
    titles: Dict[str, str] = {}
    if job_ids:
        jrows = await db.job_offers.find(
            {"id": {"$in": job_ids}}, {"_id": 0, "id": 1, "title": 1},
        ).to_list(length=len(job_ids))
        titles = {j["id"]: j.get("title", "") for j in jrows}
    for r in rows:
        r["job_title"] = titles.get(r.get("job_offer_id"), "")

    return {"items": rows, "count": total, "page": page, "limit": limit}


@router.get("/admin/careers/applicants/{applicant_id}")
async def admin_get_applicant(applicant_id: str,
                                 user: User = Depends(require_admin)) -> Dict[str, Any]:
    db = get_db()
    row = await db.job_applicants.find_one({"id": applicant_id}, {"_id": 0})
    if not row:
        raise HTTPException(404, "applicant not found")
    job = await db.job_offers.find_one({"id": row.get("job_offer_id")}, {"_id": 0})
    row["job"] = _strip_mongo(job)
    return row


@router.patch("/admin/careers/applicants/{applicant_id}/status")
async def admin_update_applicant_status(
    applicant_id: str,
    body: ApplicantStatusUpdate,
    user: User = Depends(require_admin),
) -> Dict[str, Any]:
    if body.status not in APPLICANT_STATUSES:
        raise HTTPException(422, {
            "error": "invalid_status",
            "allowed": sorted(APPLICANT_STATUSES),
            "message_en": "Invalid status value.",
            "message_fr": "Valeur de statut invalide.",
        })
    db = get_db()
    existing = await db.job_applicants.find_one({"id": applicant_id}, {"_id": 0})
    if not existing:
        raise HTTPException(404, "applicant not found")
    patch: Dict[str, Any] = {
        "status": body.status,
        "status_updated_at": _now_iso(),
        "status_updated_by": getattr(user, "email", None),
    }
    if body.admin_notes is not None:
        patch["admin_notes"] = body.admin_notes
    await db.job_applicants.update_one({"id": applicant_id}, {"$set": patch})
    return {**existing, **patch}


@router.get("/admin/careers/applicants/{applicant_id}/attachments/{filename}")
async def admin_download_attachment(applicant_id: str, filename: str,
                                      user: User = Depends(require_admin)):
    db = get_db()
    applicant = await db.job_applicants.find_one(
        {"id": applicant_id}, {"_id": 0, "job_offer_id": 1},
    )
    if not applicant:
        raise HTTPException(404, "applicant not found")
    target = safe_resolve_download(
        job_id=applicant["job_offer_id"],
        applicant_id=applicant_id,
        filename=filename,
    )
    return FileResponse(
        path=str(target),
        filename=filename,
        media_type="application/octet-stream",
    )


__all__ = ["router"]
