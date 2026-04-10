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
        assistant = get_assistant(EMERGENT_LLM_KEY, db)

        response = await assistant.chat(
            user_message=request.message,
            user_id=user_id,
            chat_history=request.chat_history,
            language=request.language,
            lot_id=request.lot_number,
            listing_id=request.listing_id
        )

        latency_ms = round((time.time() - start_time) * 1000)
        logger.info(f"[Gemini 2.5 Flash] Chat response — {latency_ms}ms | lang={response.get('language','?')} | user={user_id or 'anon'}")

        if user_id:
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
        return AIChatResponse(
            success=False,
            message="I apologize, but I'm experiencing technical difficulties. Please try again or contact support@bidvex.com.",
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
