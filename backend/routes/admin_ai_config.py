"""iter497 — Admin endpoints for the BidVex Gemini system instruction.

Backed by ``services.ai_config_service`` which stores the canonical
system instruction in ``db.ai_config`` (with an on-disk seed file at
``/app/memory/BIDVEX_AI_SYSTEM_INSTRUCTION_SEED.md`` as the idempotent
bootstrap fallback).

Endpoints (all admin-only, prefixed with ``/api/admin/ai-config``):
  * ``GET  /system-instruction`` — read the current value + metadata
  * ``PUT  /system-instruction`` — replace the value (audit-logged)

Why these live in a dedicated router:
  * The instruction is a high-blast-radius knob (it drives every Gemini
    call in the platform), so we want a very small, easy-to-audit
    surface with strict admin gating.
  * The service layer handles the DB write, cache invalidation, and
    history snapshotting — this router only wires the HTTP boundary.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import get_db, require_admin, User
from services import ai_config_service

logger = logging.getLogger(__name__)

admin_ai_config_router = APIRouter(
    prefix="/admin/ai-config",
    tags=["Admin — AI Config"],
)


class SystemInstructionResponse(BaseModel):
    key: str
    value: str
    char_count: int
    updated_at: Optional[str] = None
    updated_by_user_id: Optional[str] = None
    source: Optional[str] = None
    seed_file_path: Optional[str] = None


class SystemInstructionUpdate(BaseModel):
    value: str = Field(
        ...,
        min_length=1,
        max_length=200_000,
        description="Full replacement text for the system instruction.",
    )


@admin_ai_config_router.get(
    "/system-instruction",
    response_model=SystemInstructionResponse,
    summary="Read the current BidVex Gemini system instruction",
)
async def get_system_instruction(
    current_user: User = Depends(require_admin),
) -> SystemInstructionResponse:
    """Return the current system instruction stored in ``db.ai_config``.

    If no document exists yet, seed-bootstrap runs first so the response
    is never empty (returns the on-disk seed file contents).
    """
    db = get_db()
    # Refresh the cache (also handles the initial seed if the collection is empty)
    await ai_config_service.refresh_cache_from_db(db)
    doc = await db[ai_config_service.COLLECTION].find_one(
        {"key": ai_config_service.SYSTEM_INSTRUCTION_KEY},
        {"_id": 0},
    )
    if not doc:
        # Fallback that should never trigger since refresh seeds — kept for safety
        seed_text = ai_config_service.get_system_instruction_sync()
        return SystemInstructionResponse(
            key=ai_config_service.SYSTEM_INSTRUCTION_KEY,
            value=seed_text,
            char_count=len(seed_text),
            updated_at=None,
            updated_by_user_id=None,
            source="seed_file_fallback",
            seed_file_path=str(ai_config_service.SEED_FILE_PATH),
        )
    value = str(doc.get("value") or "")
    return SystemInstructionResponse(
        key=str(doc.get("key") or ai_config_service.SYSTEM_INSTRUCTION_KEY),
        value=value,
        char_count=int(doc.get("char_count") or len(value)),
        updated_at=doc.get("updated_at"),
        updated_by_user_id=doc.get("updated_by_user_id"),
        source=doc.get("source"),
        seed_file_path=doc.get("seed_file_path"),
    )


@admin_ai_config_router.put(
    "/system-instruction",
    response_model=SystemInstructionResponse,
    summary="Replace the BidVex Gemini system instruction (audit-logged)",
)
async def put_system_instruction(
    payload: SystemInstructionUpdate,
    current_user: User = Depends(require_admin),
) -> SystemInstructionResponse:
    """Replace the system instruction. The previous value is snapshotted
    into ``db.ai_config_history`` for CRA-style traceability. The in-memory
    cache used by the Gemini hot path is refreshed immediately so the next
    request sees the new instruction."""
    db = get_db()
    try:
        payload_out = await ai_config_service.set_system_instruction(
            db,
            payload.value,
            updated_by_user_id=getattr(current_user, "id", None),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Best-effort audit trail on the shared admin_logs collection
    try:
        await db.admin_logs.insert_one({
            "admin_id": getattr(current_user, "id", None),
            "admin_email": getattr(current_user, "email", None),
            "action": "ai_config.system_instruction.update",
            "timestamp": datetime.now(timezone.utc),
            "details": {
                "char_count": payload_out.get("char_count"),
                "source": payload_out.get("source"),
            },
        })
    except Exception as exc:  # pragma: no cover — audit best-effort
        logger.warning("[admin_ai_config] admin_logs insert failed: %s", exc)

    value = str(payload_out.get("value") or "")
    return SystemInstructionResponse(
        key=str(payload_out.get("key") or ai_config_service.SYSTEM_INSTRUCTION_KEY),
        value=value,
        char_count=int(payload_out.get("char_count") or len(value)),
        updated_at=payload_out.get("updated_at"),
        updated_by_user_id=payload_out.get("updated_by_user_id"),
        source=payload_out.get("source"),
    )


__all__ = ["admin_ai_config_router"]
