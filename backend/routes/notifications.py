"""
Notification routes - user notification CRUD
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from starlette.websockets import WebSocket, WebSocketDisconnect
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from deps import get_current_user, get_db, User
import asyncio
import uuid
import os
import mimetypes
import logging

logger = logging.getLogger(__name__)

notifications_router = APIRouter(tags=["Notifications"])
admin_notifications_router = APIRouter(prefix="/admin/notifications", tags=["Admin Notifications"])

# iter266 Mission 3C / iter267 Mission 3 — upload config + base dir.
NOTIFICATION_UPLOAD_DIR = "/app/uploads/notification_attachments"
NOTIFICATION_UPLOAD_BASE = "/app/uploads"
DEFAULT_ALLOWED_EXT = {"pdf", "jpg", "jpeg", "png", "doc", "docx"}
DEFAULT_MAX_MB = 5.0


def _is_admin(user: User) -> bool:
    return bool(getattr(user, "is_admin", False)) or getattr(user, "role", None) == "admin"


# ─── iter267 Mission 4 — Notification WebSocket bus ──────────────────


class NotificationConnectionManager:
    """Tracks active WebSocket connections per user_id. Multiple
    connections per user (laptop + phone) are supported via a list."""

    def __init__(self):
        self.active: Dict[str, list] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        self.active.setdefault(user_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        conns = self.active.get(user_id) or []
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self.active.pop(user_id, None)

    async def send_to_user(self, user_id: str, message: Dict[str, Any]) -> int:
        conns = list(self.active.get(user_id) or [])
        if not conns:
            return 0
        delivered = 0
        for ws in conns:
            try:
                await ws.send_json(message)
                delivered += 1
            except Exception:  # noqa: BLE001
                self.disconnect(ws, user_id)
        return delivered


notification_manager = NotificationConnectionManager()


async def broadcast_notification_to_user(user_id: str, notification: Dict[str, Any]) -> None:
    """iter267 Mission 4 — Fire-and-forget broadcaster used by code that
    inserts a notification. Recomputes the unread_count so the bell
    badge updates instantly without a full re-fetch."""
    try:
        db = get_db()
        unread = await db.notifications.count_documents({"user_id": user_id, "read": False})
        payload_notif = {k: v for k, v in (notification or {}).items() if k != "_id"}
        await notification_manager.send_to_user(user_id, {
            "type":         "new_notification",
            "notification": payload_notif,
            "unread_count": unread,
        })
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"[notif-broadcast] silently skipped: {exc}")


@notifications_router.websocket("/ws/notifications/{user_id}")
async def notifications_websocket(websocket: WebSocket, user_id: str, token: Optional[str] = Query(None)):
    """iter267 Mission 4 — WebSocket bell stream. Auth via `?token=`
    query param (since WS handshakes can't read Authorization headers
    in browsers). Validates that the JWT belongs to `user_id`."""
    # Verify the token corresponds to user_id BEFORE accepting.
    authorized = False
    try:
        if token:
            import jwt
            import os as _os
            jwt_secret = _os.environ.get("JWT_SECRET", "")
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
            authorized = (payload.get("user_id") == user_id or payload.get("sub") == user_id)
    except Exception:
        authorized = False
    if not authorized:
        await websocket.close(code=4401)
        return

    await notification_manager.connect(websocket, user_id)
    try:
        # Send an initial hello + current unread count.
        try:
            db = get_db()
            unread = await db.notifications.count_documents({"user_id": user_id, "read": False})
        except Exception:
            unread = 0
        await websocket.send_json({"type": "connected", "unread_count": unread})

        # Keep the socket alive with periodic pings.
        while True:
            await asyncio.sleep(30)
            try:
                await websocket.send_json({"type": "ping"})
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        notification_manager.disconnect(websocket, user_id)


@notifications_router.get("/notifications")
async def get_notifications(limit: int = 15, current_user: User = Depends(get_current_user)):
    """Get user notifications for the Notification Center"""
    db = get_db()
    notifications = await db.notifications.find(
        {"user_id": current_user.id}, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)

    unread_count = await db.notifications.count_documents({
        "user_id": current_user.id, "read": False
    })

    return {"notifications": notifications, "unread_count": unread_count}


@notifications_router.get("/notifications/unread-count")
async def get_unread_count(current_user: User = Depends(get_current_user)):
    """iter239 Mission 4 — Lightweight polling endpoint for the navbar bell
    badge. Returns `{unread_count: int, ai_unread_count: int}` so the
    frontend can drive the Bell indicator + the AI-chat history pulse
    without re-downloading the full notification list every minute.
    """
    db = get_db()
    unread_count = await db.notifications.count_documents({
        "user_id": current_user.id, "read": False,
    })
    ai_unread_count = await db.ai_chat_sessions.count_documents({
        "user_id": current_user.id,
        "is_read": False,
        "deleted_at": {"$exists": False},
    })
    return {"unread_count": unread_count, "ai_unread_count": ai_unread_count}


@notifications_router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(current_user: User = Depends(get_current_user)):
    """Mark all notifications as read.

    iter266 Mission 4 — Returns both `updated` (spec-aligned) and
    `updated_count` (legacy) so existing callers keep working.
    """
    db = get_db()
    result = await db.notifications.update_many(
        {"user_id": current_user.id, "read": False},
        {"$set": {"read": True, "is_read": True}}
    )
    return {
        "success": True,
        "updated": result.modified_count,
        "updated_count": result.modified_count,
    }


@notifications_router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: User = Depends(get_current_user)):
    """Mark a single notification as read"""
    db = get_db()
    result = await db.notifications.update_one(
        {"id": notification_id, "user_id": current_user.id},
        {"$set": {"read": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}


@notifications_router.delete("/notifications/{notification_id}")
async def delete_notification(notification_id: str, current_user: User = Depends(get_current_user)):
    """Delete a notification"""
    db = get_db()
    result = await db.notifications.delete_one({
        "id": notification_id, "user_id": current_user.id
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}


@notifications_router.post("/notifications/create")
async def create_notification(
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    data: Optional[dict] = None,
    action_url: Optional[str] = None,
    action_type: Optional[str] = None,
):
    """Create a notification (internal use / admin).

    iter217 — `action_url` is the click-through destination (relative SPA
    path like `/lots/<id>` or an absolute URL). `action_type` is a hint
    (e.g. "navigate", "external", "modal") used by the NotificationCenter.
    """
    db = get_db()
    notification = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "data": data or {},
        "action_url": action_url,
        "action_type": action_type or ("navigate" if action_url else None),
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.notifications.insert_one(notification)
    notification.pop("_id", None)
    return notification


# ─── iter266 Mission 3 — Admin: send notification with optional attachment request ──

@notifications_router.post("/notifications/admin/send")
async def admin_send_notification(
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    """iter266 Mission 3D — Admin endpoint to send a rich notification.

    Body:
      {
        "user_id":   "<recipient>",
        "user_ids":  ["<u1>", "<u2>"],   # batch (optional, alt to user_id)
        "type":      "admin_general",     # default
        "title":     "...",
        "title_fr":  "...",
        "body":      "...",                # spec-aligned name
        "body_fr":   "...",
        "message":   "..." (legacy alias for body),
        "cta_label": "...",
        "cta_url":   "/path-or-https-url",
        "color_type":"info"|"warning"|"action_required"|"success",
        "notification_icon": "📎",
        "sender_name": "BidVex Admin",
        "requires_attachment": True,
        "attachment_request_label":     "Please upload your NEQ certificate",
        "attachment_request_label_fr":  "Veuillez téléverser votre certificat NEQ",
        "attachment_types": "PDF, JPG, PNG",
        "attachment_max_mb": 1.0
      }
    """
    if not getattr(current_user, "is_admin", False) and getattr(current_user, "role", None) != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    db = get_db()
    user_id = (payload.get("user_id") or "").strip()
    user_ids = payload.get("user_ids") or ([user_id] if user_id else [])
    if not user_ids:
        raise HTTPException(status_code=400, detail="user_id or user_ids required")

    title = (payload.get("title") or "").strip()
    body = (payload.get("body") or payload.get("message") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title required")

    requires_attachment = bool(payload.get("requires_attachment"))
    color_type = payload.get("color_type") or ("action_required" if requires_attachment else "info")

    base_doc = {
        "type":        payload.get("type") or "admin_general",
        "title":       title,
        "title_fr":    (payload.get("title_fr") or "").strip() or None,
        "body":        body,
        "message":     body,  # legacy alias
        "body_fr":     (payload.get("body_fr") or "").strip() or None,
        "cta_label":   payload.get("cta_label"),
        "cta_url":     payload.get("cta_url") or payload.get("action_url"),
        "action_url":  payload.get("cta_url") or payload.get("action_url"),
        "color_type":  color_type,
        "notification_icon": payload.get("notification_icon"),
        "sender_name": payload.get("sender_name") or "BidVex Admin",
        "requires_attachment":         requires_attachment,
        "attachment_request_label":    payload.get("attachment_request_label") or "",
        "attachment_request_label_fr": payload.get("attachment_request_label_fr") or "",
        "attachment_types":            payload.get("attachment_types") or "PDF, JPG, PNG",
        "attachment_max_mb":           float(payload.get("attachment_max_mb") or DEFAULT_MAX_MB),
        "attachment_submitted":        False,
        "attachment_url":              None,
        "attachment_submitted_at":     None,
        "read":                        False,
        "is_read":                     False,
        "created_by_admin":            current_user.id,
    }

    docs = []
    for uid in user_ids:
        d = dict(base_doc)
        d["id"] = str(uuid.uuid4())
        d["user_id"] = uid
        d["created_at"] = datetime.now(timezone.utc).isoformat()
        docs.append(d)

    if docs:
        await db.notifications.insert_many(docs)
        # iter267 Mission 4 — Push to WebSocket subscribers.
        for d in docs:
            try:
                await broadcast_notification_to_user(d["user_id"], d)
            except Exception:  # noqa: BLE001
                pass
    return {"success": True, "sent_count": len(docs)}


@notifications_router.post("/notifications/{notification_id}/submit-attachment")
async def submit_notification_attachment(
    notification_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """iter266 Mission 3C — Upload a file in response to a notification
    that has `requires_attachment=True`. Validates size + extension,
    stores under `/uploads/notification_attachments/{notification_id}/`,
    then fans out a follow-up admin notification."""
    db = get_db()
    notif = await db.notifications.find_one(
        {"id": notification_id, "user_id": current_user.id},
        {"_id": 0},
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    if not notif.get("requires_attachment"):
        raise HTTPException(status_code=400, detail="This notification does not request an attachment")
    if notif.get("attachment_submitted"):
        # iter267 Mission 2 — re-upload blocked after submission (spec requirement).
        raise HTTPException(
            status_code=400,
            detail="Already submitted — contact support if you need to resubmit",
        )

    # Resolve max size + allowed extensions from the notif config.
    max_mb = float(notif.get("attachment_max_mb") or DEFAULT_MAX_MB)
    allowed_raw = str(notif.get("attachment_types") or "").lower()
    allowed = {
        e.strip().lstrip(".").lower()
        for e in allowed_raw.replace(",", " ").split()
        if e.strip()
    } or DEFAULT_ALLOWED_EXT

    filename = file.filename or "upload"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '.{ext}'. Allowed: {sorted(allowed)}",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > max_mb:
        raise HTTPException(
            status_code=400,
            detail=f"File too large: {size_mb:.2f} MB (max {max_mb} MB)",
        )

    target_dir = os.path.join(NOTIFICATION_UPLOAD_DIR, notification_id)
    os.makedirs(target_dir, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex[:8]}_{filename.replace('/', '_').replace(' ', '_')}"
    fpath = os.path.join(target_dir, safe_name)
    with open(fpath, "wb") as fh:
        fh.write(contents)
    attachment_url = f"/uploads/notification_attachments/{notification_id}/{safe_name}"

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.notifications.update_one(
        {"id": notification_id},
        {"$set": {
            "attachment_submitted":    True,
            "attachment_url":          attachment_url,
            "attachment_submitted_at": now_iso,
            "attachment_size_mb":      round(size_mb, 3),
            "attachment_filename":     filename,
        }},
    )

    # Fan-out admin alert. Find the admin who created the notification first.
    admin_id = notif.get("created_by_admin")
    if not admin_id:
        admin_user = await db.users.find_one(
            {"$or": [{"role": "admin"}, {"is_admin": True}]},
            {"_id": 0, "id": 1},
        )
        admin_id = admin_user["id"] if admin_user else None
    if admin_id:
        try:
            user_name = getattr(current_user, "name", None) or getattr(current_user, "email", "User")
            await db.notifications.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": admin_id,
                "type": "admin_attachment_received",
                "title": f"📎 {user_name} submitted an attachment",
                "message": (
                    f"User {user_name} responded to notification "
                    f"'{(notif.get('title') or '')[:80]}' with a file "
                    f"({filename}, {size_mb:.2f} MB)."
                ),
                "data": {
                    "source_notification_id": notification_id,
                    "attachment_url": attachment_url,
                    "responder_user_id": current_user.id,
                },
                "cta_label": "View attachment",
                "cta_url":   attachment_url,
                "action_url": attachment_url,
                "sender_name": "BidVex System",
                "color_type": "success",
                "read": False,
                "is_read": False,
                "created_at": now_iso,
            })
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[notification-attachment] admin notify failed: {exc}")

    return {
        "success": True,
        "attachment_url": attachment_url,
        "submitted_at": now_iso,
        "size_mb": round(size_mb, 3),
    }


@notifications_router.post("/notifications/admin/cleanup-empty")
async def admin_cleanup_empty_notifications(current_user: User = Depends(get_current_user)):
    """iter217 — Admin-only janitor that purges notifications with
    empty title AND empty message. These slip in from test prompts and
    surface to real users as un-clickable bell entries.
    """
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin only")
    db = get_db()
    result = await db.notifications.delete_many({
        "$and": [
            {"$or": [{"title": ""}, {"title": None}, {"title": {"$exists": False}}]},
            {"$or": [{"message": ""}, {"message": None}, {"message": {"$exists": False}}]},
        ]
    })
    return {"deleted_count": result.deleted_count}


# ─── iter267 Mission 2 — Admin attachment download ───────────────────


@admin_notifications_router.get("/{notification_id}/attachment")
async def admin_download_notification_attachment(
    notification_id: str,
    current_user: User = Depends(get_current_user),
):
    """iter267 Mission 2 — Stream the file the user uploaded in response
    to an attachment-request notification. Path-traversal protected:
    the resolved absolute path must stay under `NOTIFICATION_UPLOAD_BASE`.
    """
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin only")

    db = get_db()
    notif = await db.notifications.find_one({"id": notification_id}, {"_id": 0})
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    if not notif.get("attachment_submitted"):
        raise HTTPException(status_code=404, detail="No attachment submitted for this notification")

    attachment_url = (notif.get("attachment_url") or "").strip()
    if not attachment_url:
        raise HTTPException(status_code=404, detail="Attachment URL missing")

    # Strip the public /uploads prefix to map to the on-disk path.
    rel = attachment_url.lstrip("/")
    if rel.startswith("uploads/"):
        rel = rel[len("uploads/") :]

    target = os.path.join(NOTIFICATION_UPLOAD_BASE, rel)

    # ── Path-traversal guard ──
    resolved = os.path.realpath(target)
    base_resolved = os.path.realpath(NOTIFICATION_UPLOAD_BASE)
    if not resolved.startswith(base_resolved + os.sep) and resolved != base_resolved:
        logger.warning(f"[admin-attachment-download] traversal blocked: {target} → {resolved}")
        raise HTTPException(status_code=403, detail="Access denied")
    if not os.path.isfile(resolved):
        raise HTTPException(status_code=404, detail="File not found on disk")

    filename = (notif.get("attachment_filename") or os.path.basename(resolved))
    media_type, _ = mimetypes.guess_type(filename)
    return FileResponse(
        path=resolved,
        media_type=media_type or "application/octet-stream",
        filename=filename,
    )
