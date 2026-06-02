"""
iter264 Mission 6 — User notification preferences.

Each user can toggle which transactional notifications they receive
via EMAIL. Bell notifications are always written (so the user never
misses anything in-app).

The legacy `email_preferences.py` flow uses signed tokens for
unsubscribe links — that's preserved for marketing email compliance.
This module adds the IN-APP settings endpoint behind JWT auth.

  GET   /api/users/me/notification-preferences
  PATCH /api/users/me/notification-preferences

Stored on the user doc under `notification_prefs`. Defaults default-on
(except `marketing`) so existing users get the spec-defined baseline
without any migration.
"""
from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_db, get_current_user, User


notification_prefs_router = APIRouter(prefix="/users/me", tags=["Notification Preferences"])


_DEFAULTS: Dict[str, bool] = {
    "outbid":            True,
    "auction_ending":    True,
    "auction_won":       True,
    "notify_nearby":     True,
    "payment_requests":  True,
    "messages":          True,
    "marketing":         False,
}


class NotificationPrefsPatch(BaseModel):
    outbid:            bool | None = None
    auction_ending:    bool | None = None
    auction_won:       bool | None = None
    notify_nearby:     bool | None = None
    payment_requests:  bool | None = None
    messages:          bool | None = None
    marketing:         bool | None = None


def _merge_with_defaults(stored: Dict[str, bool] | None) -> Dict[str, bool]:
    out = dict(_DEFAULTS)
    if isinstance(stored, dict):
        for k, v in stored.items():
            if k in out and isinstance(v, bool):
                out[k] = v
    return out


@notification_prefs_router.get("/notification-preferences")
async def get_notification_prefs(current_user: User = Depends(get_current_user)):
    db = get_db()
    me = await db.users.find_one({"id": current_user.id}, {"_id": 0, "notification_prefs": 1})
    return {"preferences": _merge_with_defaults((me or {}).get("notification_prefs"))}


@notification_prefs_router.patch("/notification-preferences")
async def patch_notification_prefs(
    body: NotificationPrefsPatch,
    current_user: User = Depends(get_current_user),
):
    db = get_db()
    me = await db.users.find_one({"id": current_user.id}, {"_id": 0, "notification_prefs": 1})
    # `me` is either the projected doc (possibly `{}`) or None. Empty
    # dict is falsy in Python — guard explicitly against `None` only.
    if me is None:
        raise HTTPException(status_code=404, detail="User not found")
    existing = _merge_with_defaults(me.get("notification_prefs"))
    incoming = body.model_dump(exclude_none=True)
    existing.update(incoming)
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"notification_prefs": existing}},
    )
    return {"preferences": existing}


async def user_wants_email(db, user_id: str, pref_key: str) -> bool:
    """Helper for email senders. Returns True (allow send) when the
    user explicitly opted in OR didn't customize that key — and False
    only when the user explicitly opted out."""
    if not user_id or pref_key not in _DEFAULTS:
        return True
    doc = await db.users.find_one({"id": user_id}, {"_id": 0, "notification_prefs": 1})
    if not doc:
        return True
    return _merge_with_defaults(doc.get("notification_prefs")).get(pref_key, True)


__all__ = ["notification_prefs_router", "user_wants_email"]
