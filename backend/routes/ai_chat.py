"""
AI Chat routes - Claude Sonnet 4.5 chatbot endpoints
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timezone
from jose import jwt
import os
import logging

logger = logging.getLogger(__name__)

ai_chat_router = APIRouter(tags=["AI Chat"])
security = HTTPBearer(auto_error=False)
jwt_secret = os.environ.get('JWT_SECRET', 'dev-secret-key-change-in-production')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# iter200 — Ring buffer of recent chat-endpoint errors (in-process, last 10)
# Used by /ai-chat/diagnostics to surface real production failure context.
from collections import deque
_recent_chat_errors: "deque[Dict]" = deque(maxlen=10)


def _record_error(stage: str, exc: Exception, latency_ms: int):
    """Append one error to the in-process ring buffer."""
    try:
        _recent_chat_errors.append({
            "stage": stage,
            "type": type(exc).__name__,
            "message": str(exc)[:600],
            "latency_ms": latency_ms,
            "at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

db = None

def set_ai_chat_db(database):
    global db
    db = database


class AIChatRequest(BaseModel):
    message: str
    chat_history: Optional[List[Dict]] = None
    language: Optional[str] = "en"
    listing_id: Optional[str] = None
    lot_number: Optional[str] = None

class AIChatResponse(BaseModel):
    success: bool
    message: str
    language: str
    rich_content: Optional[Dict] = None
    usage: Optional[Dict] = None
    error: Optional[str] = None


@ai_chat_router.post("/ai-chat/message", response_model=AIChatResponse)
async def ai_chat_message(
    request: AIChatRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Send message to AI Assistant and get response"""
    import time
    start_time = time.time()
    try:
        user_id = None
        if credentials:
            try:
                payload = jwt.decode(credentials.credentials, jwt_secret, algorithms=["HS256"])
                user_id = payload.get("sub")
            except Exception:
                pass

        from services.ai_assistant_v2 import get_assistant
        from services.api_cache import ChatCache
        assistant = get_assistant(EMERGENT_LLM_KEY, db)

        # Load chat history from Redis cache (or memory fallback) if user is authenticated
        chat_history = request.chat_history or []
        if user_id and not chat_history:
            chat_history = await ChatCache.get_history(user_id)

        response = await assistant.chat(
            user_message=request.message,
            user_id=user_id,
            chat_history=chat_history,
            language=request.language,
            lot_id=request.lot_number,
            listing_id=request.listing_id
        )

        latency_ms = round((time.time() - start_time) * 1000)
        # iter200 — Track upstream LLM failures even when route returns 200
        if not response.get("success", True):
            err_msg = response.get("error") or response.get("message") or "unknown LLM error"
            logger.warning(f"[Gemini 2.5 Flash] Chat upstream-failure — {latency_ms}ms | {err_msg}")
            _record_error("upstream_llm", RuntimeError(err_msg), latency_ms)
        else:
            logger.info(f"[Gemini 2.5 Flash] Chat response — {latency_ms}ms | lang={response.get('language','?')} | user={user_id or 'anon'}")

        # Persist turn to Redis ChatCache and MongoDB
        if user_id:
            await ChatCache.append_turn(user_id, request.message, response["message"])
            await db.ai_chat_history.insert_one({
                "user_id": user_id,
                "message": request.message,
                "response": response["message"],
                "language": response["language"],
                "latency_ms": latency_ms,
                "model": "gemini-2.5-flash",
                "created_at": datetime.utcnow()
            })

        return AIChatResponse(**response)

    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000)
        logger.error(f"[Gemini 2.5 Flash] Chat ERROR — {latency_ms}ms | {e}", exc_info=True)
        _record_error("route", e, latency_ms)
        return AIChatResponse(
            success=False,
            message="I apologize, but I'm experiencing technical difficulties. Please try again or contact service@bidvex.com.",
            language=request.language or "en",
            error=str(e)
        )


@ai_chat_router.get("/ai-chat/history")
async def get_ai_chat_history(
    limit: int = 50,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get chat history for current user"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        history = await db.ai_chat_history.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit).to_list(length=limit)
        return {
            "success": True,
            "history": [
                {
                    "message": h["message"],
                    "response": h["response"],
                    "language": h.get("language", "en"),
                    "created_at": h["created_at"].isoformat()
                }
                for h in history
            ]
        }
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chat history")


@ai_chat_router.post("/ai-chat/clear-history")
async def clear_ai_chat_history(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Clear chat history for current user"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        # Clear Redis/memory chat session cache
        from services.api_cache import ChatCache
        await ChatCache.clear(user_id)
        # Clear MongoDB persistent history
        result = await db.ai_chat_history.delete_many({"user_id": user_id})
        return {"success": True, "message": f"Deleted {result.deleted_count} chat messages"}
    except Exception as e:
        logger.error(f"Error clearing chat history: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear chat history")


@ai_chat_router.get("/ai-chat/knowledge-base/status")
async def get_knowledge_base_status():
    """Get status of AI knowledge base (public endpoint)"""
    try:
        from services.ai_knowledge_base_v2 import get_knowledge_base
        kb = get_knowledge_base()
        doc_count = kb.get_all_documents()
        return {
            "success": True,
            "status": "operational" if doc_count > 0 else "empty",
            "document_count": doc_count,
            "last_updated": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting KB status: {e}")
        return {"success": False, "status": "error", "error": str(e)}


@ai_chat_router.post("/admin/ai-chat/reload-knowledge-base")
async def reload_knowledge_base(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Reload AI knowledge base from documents (Admin only)"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, jwt_secret, algorithms=["HS256"])
        user_doc = await db.users.find_one({"id": payload.get("sub")})
        if not user_doc or user_doc.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")

        from services.ai_knowledge_base_v2 import get_knowledge_base
        kb = get_knowledge_base()
        kb.clear_and_reload()

        await db.admin_logs.insert_one({
            "action": "ai_knowledge_base_reload",
            "admin_id": payload.get("sub"),
            "admin_email": user_doc.get("email"),
            "created_at": datetime.utcnow()
        })
        return {"success": True, "message": f"Knowledge base reloaded with {kb.get_all_documents()} documents"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reloading knowledge base: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload knowledge base")


# iter200 — Production diagnostics for the Master Concierge AI chatbot.
# Admin-only. Hit this URL on a live deployment to find out exactly why the chat is failing.
@ai_chat_router.get("/ai-chat/diagnostics")
async def ai_chat_diagnostics(
    test: bool = True,
    force_reload: bool = False,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Admin-only health probe for the BidVex Master Concierge.

    Query params:
      • `test=true` (default) — run a one-shot 1-token live LLM test call.
      • `force_reload=true` — drop the cached assistant singleton and rebuild from
        current env vars (use after you've updated EMERGENT_LLM_KEY/GEMINI_API_KEY
        in production env, so you don't need to restart the whole backend).
    """
    # Auth — admin-only
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, jwt_secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    user_doc = await db.users.find_one({"id": payload.get("sub")})
    if not user_doc or user_doc.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    def _mask(v: str) -> str:
        if not v:
            return ""
        return v[:14] + "…" + v[-4:] if len(v) > 22 else v[:6] + "…"

    emergent_key = os.environ.get("EMERGENT_LLM_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    proxy_url = os.environ.get("INTEGRATION_PROXY_URL", "https://integrations.emergentagent.com")

    # Optional singleton refresh — picks up new env vars without a full backend restart
    if force_reload:
        try:
            import services.ai_assistant_v2 as _a2
            _a2._assistant = None
        except Exception:
            pass

    env_state = {
        "EMERGENT_LLM_KEY": {
            "present": bool(emergent_key),
            "looks_valid": emergent_key.startswith("sk-emergent-") if emergent_key else False,
            "preview": _mask(emergent_key),
        },
        "GEMINI_API_KEY": {
            "present": bool(gemini_key),
            "preview": _mask(gemini_key),
        },
        "INTEGRATION_PROXY_URL": proxy_url,
        "AI_MODEL_ID": os.environ.get("AI_MODEL_ID", "gemini-2.5-flash"),
        "APP_URL": os.environ.get("APP_URL") or os.environ.get("REACT_APP_BACKEND_URL", ""),
    }

    # Boot-state of the singleton
    boot_state = {}
    try:
        from services.ai_assistant_v2 import get_assistant
        a = get_assistant(emergent_key, db)
        boot_state = {
            "model_name": a.model_name,
            "is_emergent_key": a.is_emergent_key,
            "gemini_fallback_enabled": bool(a.gemini_api_key),
            "kb_loaded": a.kb is not None,
        }
    except Exception as e:
        boot_state = {"error": f"{type(e).__name__}: {e}"}

    # Live test call — 1 message, tiny token budget
    test_result: Dict = {"ran": False}
    if test:
        import time
        try:
            from services.ai_assistant_v2 import get_assistant
            a = get_assistant(emergent_key, db)
            start = time.time()
            messages = [
                {"role": "system", "content": "Reply with exactly: pong"},
                {"role": "user", "content": "ping"},
            ]
            try:
                text = await a._call_llm(messages)
                test_result = {
                    "ran": True,
                    "ok": True,
                    "latency_ms": round((time.time() - start) * 1000),
                    "preview": (text or "")[:80],
                }
            except Exception as e:
                test_result = {
                    "ran": True,
                    "ok": False,
                    "latency_ms": round((time.time() - start) * 1000),
                    "error_type": type(e).__name__,
                    "error": str(e)[:600],
                }
                _record_error("diagnostics_test", e, test_result["latency_ms"])
        except Exception as e:
            test_result = {"ran": True, "ok": False, "error_type": type(e).__name__, "error": str(e)[:600]}

    return {
        "ok": bool(test_result.get("ok")) if test else None,
        "env": env_state,
        "boot": boot_state,
        "live_test": test_result,
        "recent_errors": list(_recent_chat_errors),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
