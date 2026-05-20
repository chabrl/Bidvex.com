"""
iter217 Phase 5 — Day-21 broker-onboarding retention reminder.

Daily job that finds users who:
  • Created an account ≥ 21 days ago
  • Have NEVER created a broker_buyer_relationships row
  • Have NEVER received the day21_broker_reminder before (idempotency)
  • Are still active and email-verified
  • Are not themselves a broker/dealer/admin

It enqueues a bilingual reminder into `email_outbox`. Honors the user's
preferred language; defaults to English when none is set.

The email payload explains the v8.1 7-step broker proxy flow and deep-
links to /brokers (EN) or /brokers?lang=fr to reduce friction.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def queue_day21_broker_reminders(db: Any) -> dict:
    """Returns a summary dict for audit / tests."""
    cutoff_start = _utcnow() - timedelta(days=30)   # window cap (don't spam very old users)
    cutoff_end   = _utcnow() - timedelta(days=21)

    queued     = 0
    skipped    = 0
    seen_users: set[str] = set()

    cursor = db.users.find({
        "created_at": {"$gte": cutoff_start, "$lte": cutoff_end},
        "is_active":  True,
        "account_type": {"$nin": ["broker", "dealer", "admin", "vehicle_dealer"]},
    }, {"_id": 0, "id": 1, "email": 1, "name": 1, "full_name": 1,
          "language": 1, "preferred_language": 1, "email_verified": 1})

    async for u in cursor:
        if not u.get("email_verified") or not u.get("email") or not u.get("id"):
            skipped += 1
            continue

        # Skip users who already started a broker partnership
        has_rel = await db.broker_buyer_relationships.count_documents({"buyer_user_id": u["id"]}) > 0
        if has_rel:
            skipped += 1
            continue

        # Idempotency — don't re-queue if we've already sent this kind to this user
        already = await db.email_outbox.count_documents({
            "kind":       "day21_broker_reminder",
            "to_user_id": u["id"],
        })
        if already > 0:
            skipped += 1
            continue

        lang = (u.get("language") or u.get("preferred_language") or "en")[:2].lower()
        if lang not in ("en", "fr"):
            lang = "en"

        await db.email_outbox.insert_one({
            "id":         str(uuid.uuid4()),
            "kind":       "day21_broker_reminder",
            "to_user_id": u["id"],
            "to_email":   u["email"],
            "context": {
                "user_name": u.get("full_name") or u.get("name"),
                "lang":      lang,
            },
            "queued_at":  _utcnow(),
        })
        queued += 1
        seen_users.add(u["id"])

    summary = {
        "ran_at":     _utcnow().isoformat(),
        "queued":     queued,
        "skipped":    skipped,
        "users":      len(seen_users),
    }
    if queued:
        logger.info("[day21_reminder] queued %s reminder(s) for %s user(s)", queued, len(seen_users))
    return summary
