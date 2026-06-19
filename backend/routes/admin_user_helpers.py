"""
iter310 — Shared admin-user helpers
====================================
Lifted out of `admin_user_actions.py` during the iter310 module split so
`admin_user_management.py` and `admin_user_billing.py` (and any future
sub-modules under the admin/users prefix) can share the same audit /
authorization primitives without circular imports.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException

from deps import User, get_current_user


logger = logging.getLogger(__name__)


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Allow only admins / super_admins through."""
    if getattr(user, "role", None) not in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def record_admin_action(
    db,
    *,
    admin_id: str,
    admin_email: str,
    action: str,
    target_user_id: str,
    content: dict,
) -> None:
    """Append a row to the `admin_actions` audit log. Non-fatal."""
    try:
        await db.admin_actions.insert_one({
            "id": str(uuid.uuid4()),
            "admin_id": admin_id,
            "admin_email": admin_email,
            "action": action,
            "target_user_id": target_user_id,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:  # pragma: no cover — audit must never block
        logger.warning(f"[admin_action_log] failed: {exc}")
