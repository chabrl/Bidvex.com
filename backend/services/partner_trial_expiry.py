"""
iter379 — Partner-trial expiry job.

Confirmed bug from the iter379 audit: `POST /api/partner-trial` and the
trial-coupon redemption path both stamp:

    user.partner_trial_active = True
    user.partner_trial_expires_at = <ISO>
    user.is_broker_partner = True   # if partner_type == "broker"
    user.partner_type = "<partner_type>"
    partner_trials doc  with status="active" + trial_expires_at

…but the ONLY existing trial-expiry scheduler (`expire_partner_pro_trials`)
queries a different pair of fields (`subscription_source='trial'` +
`partner_pro_trial_end`) and therefore never touches these records.

This module ships the missing expiry pipeline:

  1. Find `partner_trials` where `status='active'` AND
     `trial_expires_at <= now`.
  2. Flip the row to `status='expired'`, stamp `expired_at`.
  3. Clear the four user flags (`partner_trial_active`,
     `is_broker_partner`, `partner_type`, `partner_trial_expires_at`).
  4. Fire the existing bilingual `trial_revoked` email via the unified
     email pipeline.
  5. Log one row per expiry in `partner_trial_expiry_log` for audit.

Idempotency:
  • Step 1's query is naturally idempotent — once flipped to `expired`,
    the record no longer matches.
  • The user-flag update is a `$set` so re-running is a no-op.
  • The email dispatcher is guarded by the audit log (`sent_email=True`
    stamped on first success) so re-runs don't re-email the same user.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)


BATCH_CAP = 500  # safety per-run ceiling


async def run_partner_trial_expiry(db) -> Dict[str, int]:
    """Expire every partner_trial whose `trial_expires_at` is in the past.

    Returns a small stats dict so the scheduler and pytest can assert
    on outcomes.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    stats = {
        "scanned": 0,
        "expired": 0,
        "user_flags_cleared": 0,
        "emails_sent": 0,
        "errors": 0,
    }

    query = {
        "status": "active",
        "trial_expires_at": {"$lte": now_iso},
    }
    cursor = db.partner_trials.find(query, {"_id": 0}).limit(BATCH_CAP)
    rows = await cursor.to_list(length=BATCH_CAP)
    stats["scanned"] = len(rows)
    if not rows:
        return stats

    for row in rows:
        try:
            # 1. Flip the trial row to expired.
            r = await db.partner_trials.update_one(
                {"id": row["id"], "status": "active"},  # extra guard vs race
                {"$set": {
                    "status": "expired",
                    "expired_at": now_iso,
                }},
            )
            if r.modified_count == 0:
                # Another worker already flipped it.
                continue
            stats["expired"] += 1

            # 2. Clear the user's four trial flags.
            uid = row.get("user_id")
            if uid:
                u = await db.users.update_one(
                    {"id": uid},
                    {"$set": {
                        "partner_trial_active": False,
                        "partner_trial_expires_at": None,
                        "is_broker_partner": False,
                        "partner_type": None,
                        "updated_at": now_iso,
                    }},
                )
                if u.modified_count:
                    stats["user_flags_cleared"] += 1

                # 3. Fire the bilingual "trial ended" email.
                already = await db.partner_trial_expiry_log.find_one(
                    {"trial_id": row["id"], "sent_email": True},
                    {"_id": 1},
                )
                if not already:
                    email_ok = await _send_trial_ended_email(
                        db, uid, row.get("partner_type") or "partner",
                    )
                    if email_ok:
                        stats["emails_sent"] += 1

                    # 4. Audit row (one per expiry attempt).
                    await db.partner_trial_expiry_log.insert_one({
                        "trial_id": row["id"],
                        "user_id": uid,
                        "partner_type": row.get("partner_type"),
                        "expired_at": now_iso,
                        "sent_email": bool(email_ok),
                    })
        except Exception as e:  # noqa: BLE001
            stats["errors"] += 1
            logger.warning(
                "partner_trial_expiry: failed for trial=%s user=%s: %s",
                row.get("id"), row.get("user_id"), e,
            )

    logger.info(f"partner_trial_expiry complete: {stats}")
    return stats


async def _send_trial_ended_email(db, user_id: str, partner_type: str) -> bool:
    """Send the pre-existing `trial_revoked` template via the unified
    email pipeline. Returns True on any status other than a hard error
    (skip/suppressed still counts as "attempted" so we don't retry)."""
    try:
        user = await db.users.find_one(
            {"id": user_id},
            {"_id": 0, "id": 1, "email": 1, "name": 1, "first_name": 1,
             "preferred_language": 1, "language_preference": 1},
        )
        if not user or not user.get("email"):
            return False
        from services.emails._email_core import send_unified_email
        await send_unified_email(
            user=dict(user),
            email_type="trial_revoked",
            data={"partner_type": partner_type},
        )
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"trial_revoked email failed for user {user_id}: {e}")
        return False


__all__ = ["run_partner_trial_expiry"]
