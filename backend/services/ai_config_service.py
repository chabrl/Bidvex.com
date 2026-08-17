"""BidVex AI config service — DB-backed system-instruction store.

Stores the canonical BidVex Gemini system instruction in
``db.ai_config`` with document key ``system_instruction`` so admins can
edit the instruction at runtime (via ``PUT /api/admin/ai-config/system-instruction``)
without a code change.

Design mirrors ``services.tax_rate_config``:
* Single collection (``ai_config``), one row per config key.
* In-memory 5-min cache to keep the Gemini hot path O(1).
* Idempotent bootstrap from the external seed file
  ``/app/memory/BIDVEX_AI_SYSTEM_INSTRUCTION_SEED.md`` — the initial
  value lives in an external markdown file, NOT hardcoded in any .py
  module (per operator's directive).
* Every update snapshots the previous version into
  ``db.ai_config_history`` for audit.

Public surface:
  * ``get_system_instruction(db)`` — async, refreshes cache if stale.
  * ``get_system_instruction_sync()`` — sync cache read + seed fallback.
  * ``set_system_instruction(db, text, updated_by_user_id)`` — admin
    write with audit snapshot.
  * ``refresh_cache_from_db(db)`` — for scheduler heartbeat.

Callers on the Gemini path (``services/genai_direct_client.py``) should
always use ``get_system_instruction(db)`` at request-time so live edits
propagate within the cache TTL.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────
SYSTEM_INSTRUCTION_KEY = "system_instruction"
COLLECTION = "ai_config"
HISTORY_COLLECTION = "ai_config_history"
SEED_FILE_PATH = Path("/app/memory/BIDVEX_AI_SYSTEM_INSTRUCTION_SEED.md")
_CACHE_TTL_SECONDS = 300  # 5 minutes

# ── In-memory cache ────────────────────────────────────────────────
_CACHE: dict[str, str] = {}
_CACHE_TIMESTAMP: float = 0.0


def _load_seed_from_disk() -> str:
    """Read the seed markdown file. If missing, fail fast — an empty
    system instruction is unacceptable in production and silently
    substituting a placeholder would hide the misconfiguration."""
    try:
        text = SEED_FILE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"BidVex AI seed file missing at {SEED_FILE_PATH}. This file is the "
            "idempotent bootstrap for db.ai_config.system_instruction and "
            "MUST exist. Do not deploy without it."
        ) from exc
    if not text.strip():
        raise RuntimeError(
            f"BidVex AI seed file at {SEED_FILE_PATH} is empty. Refusing to "
            "seed a blank system instruction."
        )
    return text


def get_system_instruction_sync() -> str:
    """Return the currently cached instruction. Falls back to the seed
    file on cold cache so callers on the hot path can always resolve
    a non-empty string without an async DB round-trip."""
    v = _CACHE.get(SYSTEM_INSTRUCTION_KEY)
    if v:
        return v
    return _load_seed_from_disk()


async def get_system_instruction(db) -> str:
    """Async accessor — refreshes the cache if stale, then returns the value.

    Every Gemini call path invokes this at request time (not import
    time) so an admin edit propagates within the 5-min cache TTL.
    """
    global _CACHE_TIMESTAMP
    if db is not None:
        now = time.monotonic()
        if now - _CACHE_TIMESTAMP > _CACHE_TTL_SECONDS or not _CACHE:
            await refresh_cache_from_db(db)
    return get_system_instruction_sync()


async def refresh_cache_from_db(db) -> None:
    """Reload the in-memory cache from ``db.ai_config``.

    If the collection has no ``system_instruction`` document, seed it
    from the external markdown file (idempotent — never overwrites an
    existing DB value)."""
    global _CACHE, _CACHE_TIMESTAMP
    try:
        doc = await db[COLLECTION].find_one({"key": SYSTEM_INSTRUCTION_KEY})
        if not doc:
            await seed_bootstrap_system_instruction(db)
            doc = await db[COLLECTION].find_one({"key": SYSTEM_INSTRUCTION_KEY})
        _CACHE[SYSTEM_INSTRUCTION_KEY] = str(doc.get("value", "")) if doc else ""
        if not _CACHE[SYSTEM_INSTRUCTION_KEY]:
            # DB present but value blank — fall back to seed to avoid
            # sending an empty system instruction to Gemini
            logger.warning(
                "[ai_config] db.ai_config.system_instruction present but empty — using seed file fallback"
            )
            _CACHE[SYSTEM_INSTRUCTION_KEY] = _load_seed_from_disk()
        _CACHE_TIMESTAMP = time.monotonic()
        logger.info("[ai_config] cache refreshed — system_instruction %d chars",
                    len(_CACHE[SYSTEM_INSTRUCTION_KEY]))
    except Exception as exc:  # pragma: no cover — defensive
        logger.error("[ai_config] refresh_cache failed: %s — using seed file", exc)
        _CACHE[SYSTEM_INSTRUCTION_KEY] = _load_seed_from_disk()


async def seed_bootstrap_system_instruction(db) -> Optional[dict]:
    """Idempotent seed of ``db.ai_config`` from the on-disk seed file.

    If a ``system_instruction`` document already exists, does nothing
    (respects any admin edit made previously). Returns the seeded
    document or None if a doc already existed.
    """
    existing = await db[COLLECTION].find_one({"key": SYSTEM_INSTRUCTION_KEY})
    if existing:
        return None
    seed_text = _load_seed_from_disk()
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "key": SYSTEM_INSTRUCTION_KEY,
        "value": seed_text,
        "updated_at": now,
        "updated_by_user_id": None,
        "source": "seed_file",
        "seed_file_path": str(SEED_FILE_PATH),
        "char_count": len(seed_text),
    }
    await db[COLLECTION].insert_one(payload)
    logger.info("[ai_config] seeded system_instruction from %s (%d chars)",
                SEED_FILE_PATH, len(seed_text))
    return payload


async def set_system_instruction(
    db,
    value: str,
    *,
    updated_by_user_id: Optional[str] = None,
) -> dict:
    """Upsert the system instruction. Snapshots the previous value into
    ``db.ai_config_history`` before writing so the CRA-style audit trail
    used for tax rates is available for prompt edits too.

    Raises ValueError on empty / whitespace-only input. Refuses updates
    over 200KB to guard against pathological uploads that would break
    the Gemini config builder.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("system_instruction must be a non-empty string")
    if len(value) > 200_000:
        raise ValueError(
            f"system_instruction is {len(value)} chars — refusing writes "
            f">200,000 chars. Gemini's system_instruction ceiling is well "
            f"below this and larger payloads indicate a mis-paste."
        )
    now = datetime.now(timezone.utc).isoformat()
    current = await db[COLLECTION].find_one({"key": SYSTEM_INSTRUCTION_KEY})
    if current:
        await db[HISTORY_COLLECTION].insert_one({
            **{k: v for k, v in current.items() if k != "_id"},
            "superseded_at": now,
            "superseded_by_user_id": updated_by_user_id,
        })
    payload = {
        "key": SYSTEM_INSTRUCTION_KEY,
        "value": value,
        "updated_at": now,
        "updated_by_user_id": updated_by_user_id,
        "source": "admin_edit",
        "char_count": len(value),
    }
    await db[COLLECTION].update_one(
        {"key": SYSTEM_INSTRUCTION_KEY},
        {"$set": payload},
        upsert=True,
    )
    # Update the cache in-place so any subsequent call (sync or async)
    # sees the new value immediately. Also stamp the timestamp so we
    # don't force a redundant DB roundtrip on the next async call.
    global _CACHE_TIMESTAMP
    _CACHE[SYSTEM_INSTRUCTION_KEY] = value
    _CACHE_TIMESTAMP = time.monotonic()
    logger.info("[ai_config] system_instruction updated by user_id=%s (%d chars)",
                updated_by_user_id, len(value))
    return payload
