"""
iter214 P2 — Admin User Management Actions
============================================
Two endpoints used by the Admin → Users tab:

  • POST /api/admin/users/{user_id}/send-notification
      Body: {
        notification_type: "upload_required" | "invoice" | "warning"
                          | "approval" | "rejection" | "general",
        subject:           str,
        body_en:           str,
        body_fr:           Optional[str],
        attached_transaction_id: Optional[str],
        send_via:          "email" | "in_app" | "both",
      }
      Sends bilingual email via SendGrid + creates an in-app notification.
      Logs the action to admin_actions for audit.

  • POST /api/admin/users/{user_id}/request-documents
      Body: {
        document_types:  list[str],   # ["government_id", "business_registration", ...]
        deadline:        ISO date,
        message:         Optional[str],
      }
      Sends bilingual email + creates an in-app notification.
      Stores the request in user_document_requests for the "Documents Overdue"
      badge logic.
"""
from datetime import datetime, timezone
from typing import List, Optional
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import User, get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["admin-user-actions"])


# ───────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────

async def _require_admin(user: User = Depends(get_current_user)) -> User:
    if getattr(user, "role", None) not in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def _record_admin_action(db, *, admin_id: str, admin_email: str, action: str, target_user_id: str, content: dict) -> None:
    """Append to admin_actions audit log. Non-fatal."""
    try:
        await db.admin_actions.insert_one({
            "id": str(uuid.uuid4()),
            "admin_id": admin_id,
            "admin_email": admin_email,
            "action": action,
            "target_user_id": target_user_id,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"[admin_action_log] failed: {e}")


# ───────────────────────────────────────────────────────────────────────
# Send Notification
# ───────────────────────────────────────────────────────────────────────

class SendNotificationPayload(BaseModel):
    notification_type: str = Field(...)  # upload_required|invoice|warning|approval|rejection|general
    subject: str = Field(..., min_length=2, max_length=200)
    body_en: str = Field(..., min_length=2)
    body_fr: Optional[str] = None
    attached_transaction_id: Optional[str] = None
    send_via: str = Field("both")  # email|in_app|both


_VALID_TYPES = {
    "upload_required", "invoice", "warning",
    "approval", "rejection", "general",
}


@router.post("/{user_id}/send-notification")
async def admin_send_notification(
    user_id: str,
    payload: SendNotificationPayload,
    current_user: User = Depends(_require_admin),
):
    if payload.notification_type not in _VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_type",
                "message_en": f"notification_type must be one of {sorted(_VALID_TYPES)}",
                "message_fr": f"notification_type doit être l'un de {sorted(_VALID_TYPES)}",
            },
        )

    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    sent_email = False
    in_app_id = None

    # ── In-app notification ──
    if payload.send_via in {"in_app", "both"}:
        in_app_id = str(uuid.uuid4())
        await db.notifications.insert_one({
            "id": in_app_id,
            "user_id": user_id,
            "type": f"admin_{payload.notification_type}",
            "title": payload.subject,
            "message_en": payload.body_en,
            "message_fr": payload.body_fr or payload.body_en,
            "attached_transaction_id": payload.attached_transaction_id,
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by_admin": current_user.id,
        })

    # ── Email via SendGrid ──
    if payload.send_via in {"email", "both"} and user_doc.get("email"):
        try:
            from services.email_notifications import send_email
            body_fr = payload.body_fr or payload.body_en
            html = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f8fafc;border-radius:12px;">
              <div style="padding:20px;background:white;border-radius:8px;">
                <h2 style="color:#1e40af;margin:0 0 12px;">{payload.subject}</h2>
                <div style="color:#334155;line-height:1.6;white-space:pre-wrap;">{payload.body_en}</div>
                <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">
                <div style="color:#334155;line-height:1.6;white-space:pre-wrap;">{body_fr}</div>
                <p style="color:#64748b;font-size:11px;margin-top:24px;">
                  BidVex Inc. — Sent by an administrator · Envoyé par un administrateur
                </p>
              </div>
            </div>
            """
            await send_email(to_email=user_doc["email"], subject=payload.subject, html_content=html)
            sent_email = True
        except Exception as e:
            logger.warning(f"[admin_send_notification] email failed: {e}")

    await _record_admin_action(
        db,
        admin_id=current_user.id,
        admin_email=current_user.email,
        action=f"send_notification:{payload.notification_type}",
        target_user_id=user_id,
        content={
            "subject": payload.subject,
            "send_via": payload.send_via,
            "email_sent": sent_email,
            "in_app_id": in_app_id,
        },
    )

    return {
        "success": True,
        "email_sent": sent_email,
        "in_app_id": in_app_id,
    }


# ───────────────────────────────────────────────────────────────────────
# Request Documents
# ───────────────────────────────────────────────────────────────────────

class RequestDocumentsPayload(BaseModel):
    document_types: List[str] = Field(..., min_length=1)
    deadline: str = Field(...)  # ISO date string
    message: Optional[str] = None


_DOC_TYPE_LABELS = {
    "government_id":           ("Government-issued ID", "Pièce d'identité gouvernementale"),
    "business_registration":   ("Business registration certificate", "Certificat d'enregistrement d'entreprise"),
    "dealer_licence":          ("Dealer licence", "Permis de concessionnaire"),
    "neq_proof":               ("NEQ proof", "Preuve NEQ"),
    "insurance_certificate":   ("Insurance certificate", "Certificat d'assurance"),
    "other":                   ("Other document", "Autre document"),
}


@router.post("/{user_id}/request-documents")
async def admin_request_documents(
    user_id: str,
    payload: RequestDocumentsPayload,
    current_user: User = Depends(_require_admin),
):
    # Validate document types
    unknown = [t for t in payload.document_types if t not in _DOC_TYPE_LABELS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unknown_document_types",
                "unknown": unknown,
                "message_en": f"Unknown document types: {unknown}. Valid: {sorted(_DOC_TYPE_LABELS)}",
                "message_fr": f"Types de documents inconnus : {unknown}",
            },
        )

    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    # ── Persist the request ──
    req_id = str(uuid.uuid4())
    await db.user_document_requests.insert_one({
        "id": req_id,
        "user_id": user_id,
        "document_types": payload.document_types,
        "deadline": payload.deadline,
        "message": payload.message,
        "status": "pending",         # pending | fulfilled | overdue
        "created_by_admin": current_user.id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # ── In-app notification ──
    titles = [_DOC_TYPE_LABELS[t][0] for t in payload.document_types]
    titles_fr = [_DOC_TYPE_LABELS[t][1] for t in payload.document_types]
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "admin_document_request",
        "title": "Action Required — Document Upload Needed",
        "message_en": (
            f"Please upload: {', '.join(titles)}. Deadline: {payload.deadline}.\n\n"
            f"{payload.message or ''}"
        ).strip(),
        "message_fr": (
            f"Veuillez téléverser : {', '.join(titles_fr)}. Date limite : {payload.deadline}.\n\n"
            f"{payload.message or ''}"
        ).strip(),
        "is_read": False,
        "doc_request_id": req_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by_admin": current_user.id,
    })

    # ── Email ──
    try:
        from services.email_notifications import send_email
        list_html_en = "".join(f"<li>{t}</li>" for t in titles)
        list_html_fr = "".join(f"<li>{t}</li>" for t in titles_fr)
        msg_block = f"<p>{payload.message}</p>" if payload.message else ""
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f8fafc;border-radius:12px;">
          <div style="padding:20px;background:white;border-radius:8px;">
            <h2 style="color:#b45309;margin:0 0 12px;">📁 Action Required — Document Upload Needed</h2>
            <p>Please upload the following document(s) by <strong>{payload.deadline}</strong>:</p>
            <ul>{list_html_en}</ul>
            {msg_block}
            <p>You can upload from your <a href="https://www.bidvex.com/settings">Profile Settings</a>.</p>
            <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">
            <h2 style="color:#b45309;margin:0 0 12px;">📁 Action requise — Téléchargement de document nécessaire</h2>
            <p>Veuillez téléverser le(s) document(s) suivant(s) avant le <strong>{payload.deadline}</strong> :</p>
            <ul>{list_html_fr}</ul>
            <p>Téléversez depuis vos <a href="https://www.bidvex.com/settings">Paramètres du profil</a>.</p>
          </div>
        </div>
        """
        await send_email(
            to_email=user_doc["email"],
            subject="Action Required — Document Upload Needed · Action requise",
            html_content=html,
        )
    except Exception as e:
        logger.warning(f"[admin_request_documents] email failed: {e}")

    await _record_admin_action(
        db,
        admin_id=current_user.id,
        admin_email=current_user.email,
        action="request_documents",
        target_user_id=user_id,
        content={
            "document_types": payload.document_types,
            "deadline": payload.deadline,
            "request_id": req_id,
        },
    )

    return {"success": True, "request_id": req_id}


@router.get("/{user_id}/document-requests")
async def admin_list_user_document_requests(
    user_id: str,
    current_user: User = Depends(_require_admin),
):
    """Return all document requests on a user (used by the Overdue badge)."""
    db = get_db()
    rows = await db.user_document_requests.find({"user_id": user_id}, {"_id": 0})\
        .sort("created_at", -1).limit(50).to_list(50)
    today = datetime.now(timezone.utc).date().isoformat()
    out = []
    for r in rows:
        is_overdue = (r.get("status") == "pending") and (r.get("deadline", "") < today)
        out.append({**r, "is_overdue": is_overdue})
    return {"requests": out, "overdue_count": sum(1 for r in out if r["is_overdue"])}
