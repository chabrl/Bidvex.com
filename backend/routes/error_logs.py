"""
iter306 — Error Tracking & Admin Error Logs
=============================================
Endpoints to capture frontend / backend errors into MongoDB so production
issues surface in the admin Error Logs tab.

Routes:
  POST /api/errors/frontend            — public-ish (auth optional); accepts a single error log
  GET  /api/admin/errors/frontend      — admin only; list with date/user filters
  GET  /api/admin/errors/backend       — admin only; list with date/endpoint filters

The backend exception handler (in server.py) writes to `backend_errors` directly.
"""
from datetime import datetime, timezone, timedelta
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from deps import User, get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["error-logs"])


class FrontendErrorPayload(BaseModel):
    error_message: str = Field(..., max_length=2000)
    component_stack: Optional[str] = Field(None, max_length=10000)
    url: Optional[str] = Field(None, max_length=500)
    user_agent: Optional[str] = Field(None, max_length=500)
    scope: Optional[str] = Field(None, max_length=100)


async def _admin_or_403(current_user: User):
    if getattr(current_user, "role", None) not in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")


async def _try_current_user(request: Request) -> Optional[str]:
    """Best-effort user resolution — frontend error reporter should still
    work for anonymous users (e.g. listing detail crash before login)."""
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    try:
        # Cheap inline JWT decode (avoid re-importing deps machinery here).
        import base64, json as _json
        token = auth.split(" ", 1)[1]
        payload_b64 = token.split(".")[1] + "=="
        payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("sub") or payload.get("user_id")
    except Exception:
        return None


@router.post("/errors/frontend")
async def log_frontend_error(
    payload: FrontendErrorPayload,
    request: Request,
):
    """Public endpoint — anyone (logged in or not) can report a frontend
    error so we can capture pre-login crashes too. Rate-limited at the
    Nginx layer; safe by construction (no user-supplied data is executed)."""
    db = get_db()
    user_id = await _try_current_user(request)
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "error_message": payload.error_message[:2000],
        "component_stack": (payload.component_stack or "")[:10000],
        "url": (payload.url or "")[:500],
        "user_agent": (payload.user_agent or request.headers.get("user-agent", ""))[:500],
        "scope": (payload.scope or "")[:100],
        "ip": request.client.host if request.client else "",
        "timestamp": datetime.now(timezone.utc),
    }
    await db.frontend_errors.insert_one(doc)
    return {"ok": True, "id": doc["id"]}


@router.get("/admin/errors/frontend")
async def list_frontend_errors(
    days: int = Query(7, ge=1, le=90),
    user_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
):
    await _admin_or_403(current_user)
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = {"timestamp": {"$gte": since}}
    if user_id:
        q["user_id"] = user_id
    cursor = db.frontend_errors.find(q, {"_id": 0}).sort("timestamp", -1).limit(limit)
    items = await cursor.to_list(limit)
    total = await db.frontend_errors.count_documents(q)
    return {"items": items, "total": total, "days": days}


@router.get("/admin/errors/backend")
async def list_backend_errors(
    days: int = Query(7, ge=1, le=90),
    endpoint: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
):
    await _admin_or_403(current_user)
    db = get_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = {"timestamp": {"$gte": since}}
    if endpoint:
        q["endpoint"] = {"$regex": endpoint, "$options": "i"}
    cursor = db.backend_errors.find(q, {"_id": 0}).sort("timestamp", -1).limit(limit)
    items = await cursor.to_list(limit)
    total = await db.backend_errors.count_documents(q)
    return {"items": items, "total": total, "days": days}
