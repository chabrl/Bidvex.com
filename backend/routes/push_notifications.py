"""
BidVex Web Push Notification Service
Self-hosted VAPID push — no Firebase dependency.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from deps import get_current_user, User
from pywebpush import webpush, WebPushException
import os
import json
import logging
import uuid as uuid_mod

logger = logging.getLogger(__name__)

push_router = APIRouter(tags=["Push Notifications"])

_db = None
_vapid_private_key = None
_vapid_claims = None


def set_push_db(db_instance):
    global _db
    _db = db_instance


def _get_vapid():
    global _vapid_private_key, _vapid_claims
    if _vapid_private_key is None:
        # Priority 1: Direct key content from env var (Railway / cloud deploys)
        key_content = os.environ.get("VAPID_PRIVATE_KEY_CONTENT", "")
        if key_content:
            # Handle escaped newlines from env vars
            key_content = key_content.replace("\\n", "\n")
            import tempfile
            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False)
            tmp.write(key_content)
            tmp.flush()
            tmp.close()
            _vapid_private_key = tmp.name
            logger.info("[Push] VAPID key loaded from VAPID_PRIVATE_KEY_CONTENT env var")
        else:
            # Priority 2: File path fallback (local dev)
            key_path = os.environ.get("VAPID_PRIVATE_KEY_PATH", "vapid_private.pem")
            if os.path.isfile(key_path):
                _vapid_private_key = key_path
                logger.info(f"[Push] VAPID key loaded from file: {key_path}")
            else:
                logger.warning("[Push] VAPID private key not found (set VAPID_PRIVATE_KEY_CONTENT or VAPID_PRIVATE_KEY_PATH)")
    if _vapid_claims is None:
        _vapid_claims = {"sub": os.environ.get("VAPID_CLAIMS_EMAIL", "mailto:push@bidvex.ca")}
    return _vapid_private_key, _vapid_claims


def get_db():
    if _db is None:
        raise RuntimeError("Push DB not initialized")
    return _db


# ---------- Models ----------

class PushSubscription(BaseModel):
    endpoint: str
    keys: dict  # {p256dh, auth}


class PushPayload(BaseModel):
    title: str
    body: str
    type: str = "default"
    url: str = "/"
    listing_id: Optional[str] = None
    category: Optional[str] = None


# ---------- Routes ----------

@push_router.post("/push/subscribe")
async def subscribe_push(sub: PushSubscription, current_user: User = Depends(get_current_user)):
    db = get_db()
    # Upsert subscription for this user+endpoint
    await db.push_subscriptions.update_one(
        {"user_id": current_user.id, "endpoint": sub.endpoint},
        {"$set": {
            "user_id": current_user.id,
            "endpoint": sub.endpoint,
            "keys": sub.keys,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"success": True}


@push_router.delete("/push/unsubscribe")
async def unsubscribe_push(sub: PushSubscription, current_user: User = Depends(get_current_user)):
    db = get_db()
    await db.push_subscriptions.delete_one({"user_id": current_user.id, "endpoint": sub.endpoint})
    return {"success": True}


@push_router.get("/push/status")
async def push_status(current_user: User = Depends(get_current_user)):
    db = get_db()
    count = await db.push_subscriptions.count_documents({"user_id": current_user.id})
    return {"subscribed": count > 0, "device_count": count}


@push_router.get("/push/vapid-public-key")
async def get_vapid_public_key():
    key = os.environ.get("VAPID_PUBLIC_KEY", "")
    return {"public_key": key}


# ---------- Send helpers (called from other modules) ----------

async def send_push_to_user(db, user_id: str, payload: dict):
    """Send a push notification to all of a user's subscribed devices."""
    private_key, claims = _get_vapid()
    if not private_key:
        return 0

    subs = await db.push_subscriptions.find({"user_id": user_id}, {"_id": 0}).to_list(10)
    sent = 0
    for sub in subs:
        subscription_info = {
            "endpoint": sub["endpoint"],
            "keys": sub["keys"],
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=private_key,
                vapid_claims=claims,
                ttl=86400,
            )
            sent += 1
        except WebPushException as e:
            status = getattr(e, 'response', None)
            code = status.status_code if status else 0
            if code in (404, 410):
                # Subscription expired/invalid — clean up
                await db.push_subscriptions.delete_one({"endpoint": sub["endpoint"]})
                logger.info(f"[Push] Removed stale subscription for user={user_id}")
            else:
                logger.error(f"[Push] Error sending to user={user_id}: {e}")
        except Exception as e:
            logger.error(f"[Push] Unexpected error: {e}")
    return sent
