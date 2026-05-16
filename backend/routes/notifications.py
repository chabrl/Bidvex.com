"""
Notification routes - user notification CRUD
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from datetime import datetime, timezone
from deps import get_current_user, get_db, User
import uuid
import logging

logger = logging.getLogger(__name__)

notifications_router = APIRouter(tags=["Notifications"])


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


@notifications_router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(current_user: User = Depends(get_current_user)):
    """Mark all notifications as read"""
    db = get_db()
    result = await db.notifications.update_many(
        {"user_id": current_user.id, "read": False},
        {"$set": {"read": True}}
    )
    return {"success": True, "updated_count": result.modified_count}


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
