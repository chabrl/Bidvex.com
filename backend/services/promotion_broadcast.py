"""
iter243 Mission 2 — Promotion broadcast pipeline.

When an admin activates a promotion with `notify_users=True`, we
dispatch a one-time mass email to the matching audience (tier / province /
new_users / custom). Unsubscribed + bounced recipients are stripped at
the recipient-resolution layer (mirroring the iter241 Mission 5 strict
gate), so this module never has to worry about deliverability filters.

The actual dispatch runs in a background task (FastAPI BackgroundTasks)
to avoid blocking the admin's `/activate` request.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _build_promo_body(promo: Dict[str, Any], lang: str = "en") -> Dict[str, str]:
    """Return the unified-template data block for a promotion broadcast."""
    is_fr = lang.startswith("fr")
    name = promo.get("name_fr" if is_fr else "name_en") or promo.get("name_en") or "BidVex"
    end_date = (promo.get("end_date") or "").split("T")[0]
    coupon = promo.get("coupon_code") or ""
    cfg = promo.get("config") or {}
    pct = cfg.get("discount_percent")

    discount_line_en = (
        f"<strong>{pct}% off</strong> all qualifying transactions. " if pct else ""
    )
    discount_line_fr = (
        f"<strong>{pct} % de réduction</strong> sur les transactions admissibles. " if pct else ""
    )
    coupon_line_en = f"Use coupon code <code><strong>{coupon}</strong></code> at checkout." if coupon else ""
    coupon_line_fr = f"Utilisez le code promo <code><strong>{coupon}</strong></code> au paiement." if coupon else ""

    if is_fr:
        return {
            "promotion_name": name,
            "promotion_end_date": end_date,
            "coupon_code": coupon,
            "secondary_info": f"{discount_line_fr}{coupon_line_fr} Valide jusqu'au {end_date}.",
        }
    return {
        "promotion_name": name,
        "promotion_end_date": end_date,
        "coupon_code": coupon,
        "secondary_info": f"{discount_line_en}{coupon_line_en} Valid until {end_date}.",
    }


async def _resolve_eligible_emails(
    db,
    promo: Dict[str, Any],
    max_recipients: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Build the recipient list for a promotion broadcast.

    Honors the same `target_config` shape used by the promotion engine
    AND strictly excludes any user with `marketing_unsubscribed=True` or
    that appears in the bounces collection.
    """
    target = (promo.get("target_config") or {})
    target_type = (promo.get("target") or target.get("target") or "all").lower()

    base_q: Dict[str, Any] = {}
    if target_type == "tier" and target.get("target_tier"):
        base_q["subscription_tier"] = target["target_tier"]
    elif target_type == "province" and target.get("target_province"):
        base_q["province"] = target["target_province"]
    elif target_type == "new_users" and target.get("new_user_days"):
        from datetime import timedelta as _td
        cutoff = (datetime.now(timezone.utc) - _td(days=int(target["new_user_days"]))).isoformat()
        base_q["created_at"] = {"$gte": cutoff}
    elif target_type == "custom":
        ids = target.get("custom_user_ids") or []
        emails = [e.lower() for e in (target.get("custom_emails") or [])]
        if not ids and not emails:
            return []
        clauses: List[Dict[str, Any]] = []
        if ids:
            clauses.append({"id": {"$in": ids}})
        if emails:
            clauses.append({"email": {"$in": emails}})
        base_q["$or"] = clauses

    # Strict unsubscribe gate.
    base_q["$and"] = base_q.get("$and", []) + [
        {"$or": [
            {"marketing_unsubscribed": {"$ne": True}},
            {"marketing_unsubscribed": {"$exists": False}},
        ]}
    ]

    cursor = db.users.find(
        base_q,
        {"_id": 0, "id": 1, "email": 1, "first_name": 1, "name": 1, "preferred_language": 1},
    )
    if max_recipients:
        cursor = cursor.limit(int(max_recipients))
    users = await cursor.to_list(length=max_recipients or 10_000)

    # Bounce-list exclusion.
    try:
        bounce_docs = await db.email_unsubscribes.find(
            {"reason": "bounced"}, {"_id": 0, "email": 1}
        ).to_list(length=None)
        bounced_set = {(d.get("email") or "").lower() for d in bounce_docs if d.get("email")}
    except Exception:
        bounced_set = set()

    eligible: List[Dict[str, Any]] = []
    for u in users:
        email = (u.get("email") or "").lower()
        if not email or email in bounced_set:
            continue
        eligible.append({
            "id": u.get("id"),
            "email": email,
            "first_name": u.get("first_name") or u.get("name") or "",
            "lang": u.get("preferred_language") or "en",
        })
    return eligible


async def broadcast_promotion_activation(
    db,
    promotion_id: str,
    *,
    max_recipients: Optional[int] = None,
) -> Dict[str, Any]:
    """Fire-and-forget broadcast for a single promotion.

    Returns a stats dict for log/observability. Idempotency is enforced
    via the `promotion_broadcasts` collection (a doc is inserted ONCE per
    promotion; subsequent calls short-circuit).
    """
    from services.email_notifications import send_unified_email

    promo = await db.promotions.find_one({"id": promotion_id}, {"_id": 0})
    if not promo:
        return {"status": "not_found", "promotion_id": promotion_id}

    if not promo.get("notify_users"):
        return {"status": "skipped_not_notify", "promotion_id": promotion_id}

    # Idempotency — don't broadcast the same promo twice.
    existing = await db.promotion_broadcasts.find_one({"promotion_id": promotion_id}, {"_id": 0})
    if existing:
        return {
            "status": "skipped_already_broadcast",
            "promotion_id": promotion_id,
            "broadcast_at": existing.get("created_at"),
            "recipient_count": existing.get("recipient_count", 0),
        }

    recipients = await _resolve_eligible_emails(db, promo, max_recipients=max_recipients)
    if not recipients:
        await db.promotion_broadcasts.insert_one({
            "promotion_id": promotion_id,
            "recipient_count": 0,
            "sent_count": 0,
            "failure_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "notes": "no_eligible_recipients",
        })
        return {"status": "no_recipients", "promotion_id": promotion_id, "recipient_count": 0}

    # Send sequentially — small audience, acceptable latency. Larger
    # audiences will graduate to the email_marketing campaign worker.
    sent = 0
    failed = 0
    for r in recipients:
        try:
            data = _build_promo_body(promo, lang=r.get("lang") or "en")
            await send_unified_email(
                "new_feature",                       # canonical "announcement" type
                user={"email": r["email"], "first_name": r["first_name"]},
                data=data,
                lang=r.get("lang") or "en",
            )
            sent += 1
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[broadcast {promotion_id}] {r['email']}: {e}")
            failed += 1

    record = {
        "promotion_id": promotion_id,
        "coupon_code": promo.get("coupon_code"),
        "recipient_count": len(recipients),
        "sent_count": sent,
        "failure_count": failed,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.promotion_broadcasts.insert_one(record)
    record.pop("_id", None)
    record["status"] = "ok"
    return record


__all__ = [
    "broadcast_promotion_activation",
    "_resolve_eligible_emails",
    "_build_promo_body",
]
