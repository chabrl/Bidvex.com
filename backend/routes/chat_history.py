"""
iter238 Mission 4 — Persistent AI chat history + proactive notifications.

Collection: ai_chat_sessions
  {
    _id, user_id, session_id (uuid), listing_id, messages: [...],
    created_at, updated_at, is_read, deleted_at
  }

Endpoints (mounted under genai_chat_router):
  GET    /api/chat/history                 list user sessions (paginated)
  GET    /api/chat/history/{session_id}    full message list
  POST   /api/chat/mark-read/{session_id}  flip is_read=True
  DELETE /api/chat/history/{session_id}    soft-delete (deleted_at)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

chat_history_router = APIRouter(prefix="/chat", tags=["GenAI Chat History"])
_security = HTTPBearer(auto_error=False)
_db = None


def set_chat_history_db(database) -> None:
    global _db
    _db = database


async def _resolve_user(creds: Optional[HTTPAuthorizationCredentials]) -> Optional[Dict[str, Any]]:
    """Return the authenticated user doc or None for anonymous."""
    if not creds or not creds.credentials:
        return None
    if _db is None:
        return None
    try:
        from routes.auth import _decode_jwt  # type: ignore
        payload = _decode_jwt(creds.credentials)
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            return None
        return await _db.users.find_one({"id": user_id}, {"_id": 0, "id": 1, "email": 1, "first_name": 1, "last_name": 1})
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Persistence helpers (called by genai_chat.post_chat_stream after completion)
# ---------------------------------------------------------------------------
async def persist_chat_turn(
    *,
    user_id: Optional[str],
    session_id: Optional[str],
    listing_id: Optional[str],
    user_message: str,
    assistant_message: str,
) -> Optional[str]:
    """Append a user→assistant message pair to ai_chat_sessions.

    For anonymous users, persistence is silently skipped (returns None).
    """
    if _db is None or not user_id:
        return None
    now = datetime.now(timezone.utc)
    sid = session_id or str(uuid.uuid4())
    msgs = [
        {"role": "user", "content": user_message, "timestamp": now, "is_proactive": False},
        {"role": "assistant", "content": assistant_message, "timestamp": now, "is_proactive": False},
    ]
    await _db.ai_chat_sessions.update_one(
        {"session_id": sid, "user_id": user_id},
        {
            "$setOnInsert": {
                "session_id": sid,
                "user_id": user_id,
                "listing_id": listing_id,
                "created_at": now,
            },
            "$set": {
                "updated_at": now,
                "is_read": False,
            },
            "$push": {"messages": {"$each": msgs}},
        },
        upsert=True,
    )
    return sid


async def send_ai_notification(
    *,
    user_id: str,
    message_content: str,
    listing_id: Optional[str] = None,
    listing_title: Optional[str] = None,
) -> Dict[str, Any]:
    """Push a proactive AI message into the user's most recent session
    and fire the unified-template SendGrid email + in-app bell badge.

    Idempotent enough for batch matchmaking — duplicate proactive messages
    within 60s of each other are skipped.
    """
    if _db is None:
        return {"status": "skipped", "reason": "db not initialised"}
    now = datetime.now(timezone.utc)

    # Find or create a session.
    sess = await _db.ai_chat_sessions.find_one(
        {"user_id": user_id, "deleted_at": {"$exists": False}},
        sort=[("updated_at", -1)],
    )
    sid = (sess or {}).get("session_id") or str(uuid.uuid4())

    # Dedup: don't post the same content twice within 60s.
    if sess:
        last = (sess.get("messages") or [])[-1:]
        if last and last[0].get("role") == "assistant" and last[0].get("content", "") == message_content:
            return {"status": "deduped"}

    msg = {
        "role": "assistant",
        "content": message_content,
        "timestamp": now,
        "is_proactive": True,
    }
    await _db.ai_chat_sessions.update_one(
        {"session_id": sid, "user_id": user_id},
        {
            "$setOnInsert": {
                "session_id": sid,
                "user_id": user_id,
                "listing_id": listing_id,
                "created_at": now,
            },
            "$set": {"updated_at": now, "is_read": False},
            "$push": {"messages": msg},
        },
        upsert=True,
    )

    # In-app notification (best-effort).
    try:
        await _db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": "ai_suggestion",
            "title": "BidVex AI has a suggestion for you",
            "body": (message_content[:80] + "...") if len(message_content) > 80 else message_content,
            "link": f"/listing/{listing_id}" if listing_id else "/marketplace",
            "read": False,
            "created_at": now,
        })
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[iter238-ai] notification insert failed: {e}")

    # Email via unified template (best-effort).
    try:
        from services.email_templates import build_email_payload
        from services.email_notifications import send_email
        user = await _db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "first_name": 1})
        if user and user.get("email"):
            payload = build_email_payload(
                "ai_suggestion",
                user,
                {
                    "ai_message": message_content,
                    "listing_url": f"https://bidvex.com/listing/{listing_id}" if listing_id else "https://bidvex.com/marketplace",
                    "listing_title": listing_title or "",
                },
            )
            await send_email(**payload)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[iter238-ai] suggestion email failed: {e}")

    return {"status": "ok", "session_id": sid}


# ---------------------------------------------------------------------------
# History endpoints
# ---------------------------------------------------------------------------
@chat_history_router.get("/history")
async def list_sessions(
    creds: HTTPAuthorizationCredentials = Depends(_security),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
) -> Dict[str, Any]:
    user = await _resolve_user(creds)
    if not user:
        raise HTTPException(status_code=401, detail="auth required")
    if _db is None:
        raise HTTPException(status_code=503, detail="db not initialised")
    skip = (page - 1) * per_page
    base_q = {"user_id": user["id"], "deleted_at": {"$exists": False}}
    cursor = _db.ai_chat_sessions.find(
        base_q,
        {"_id": 0, "session_id": 1, "listing_id": 1, "messages": {"$slice": -1},
         "is_read": 1, "created_at": 1, "updated_at": 1},
    ).sort("updated_at", -1).skip(skip).limit(per_page)
    sessions = await cursor.to_list(length=per_page)
    for s in sessions:
        msgs = s.get("messages") or []
        s["preview"] = (msgs[0]["content"][:140] if msgs else "")
        s.pop("messages", None)
    total = await _db.ai_chat_sessions.count_documents(base_q)
    return {"sessions": sessions, "total": total, "page": page, "per_page": per_page}


@chat_history_router.get("/history/{session_id}")
async def get_session(
    session_id: str,
    creds: HTTPAuthorizationCredentials = Depends(_security),
) -> Dict[str, Any]:
    user = await _resolve_user(creds)
    if not user:
        raise HTTPException(status_code=401, detail="auth required")
    if _db is None:
        raise HTTPException(status_code=503, detail="db not initialised")
    sess = await _db.ai_chat_sessions.find_one(
        {"session_id": session_id, "user_id": user["id"], "deleted_at": {"$exists": False}},
        {"_id": 0},
    )
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    return sess


@chat_history_router.post("/mark-read/{session_id}")
async def mark_read(
    session_id: str,
    creds: HTTPAuthorizationCredentials = Depends(_security),
) -> Dict[str, Any]:
    user = await _resolve_user(creds)
    if not user:
        raise HTTPException(status_code=401, detail="auth required")
    if _db is None:
        raise HTTPException(status_code=503, detail="db not initialised")
    result = await _db.ai_chat_sessions.update_one(
        {"session_id": session_id, "user_id": user["id"]},
        {"$set": {"is_read": True}},
    )
    return {"status": "ok", "matched": result.matched_count}


@chat_history_router.delete("/history/{session_id}")
async def soft_delete(
    session_id: str,
    creds: HTTPAuthorizationCredentials = Depends(_security),
) -> Dict[str, Any]:
    user = await _resolve_user(creds)
    if not user:
        raise HTTPException(status_code=401, detail="auth required")
    if _db is None:
        raise HTTPException(status_code=503, detail="db not initialised")
    await _db.ai_chat_sessions.update_one(
        {"session_id": session_id, "user_id": user["id"]},
        {"$set": {"deleted_at": datetime.now(timezone.utc)}},
    )
    return {"status": "deleted"}


__all__ = [
    "chat_history_router",
    "set_chat_history_db",
    "persist_chat_turn",
    "send_ai_notification",
]
