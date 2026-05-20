"""
iter217 Phase 5 Hotfix v8.1 — Title transfer enforcement cron.

Daily worker that finds invoices released > 14 days ago without a
provincial title transfer reference logged, then:
  1. Flags the broker's auto-approval as revoked
  2. Queues a critical dashboard banner notification
  3. Queues a system email to the broker ("ACTION REQUIRED")
  4. Audits the enforcement action to the broker_invoice_audit collection

Idempotent: only flags invoices that have NOT yet had a previous
"title_transfer_overdue" enforcement event logged. Safe to run many
times per day.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def enforce_title_transfer_overdue_job(db: Any) -> dict:
    """Scan + enforce. Returns a summary dict (used by audit + tests)."""
    cutoff = _utcnow() - timedelta(days=14)

    enforced  = 0
    skipped   = 0
    brokers_flagged: set[str] = set()

    cursor = db.broker_invoices.find({
        "released_at":              {"$ne": None, "$lt": cutoff},
        "title_transfer_logged_at": None,
        "title_transfer_enforced_at": None,           # idempotency guard
    }, {"_id": 0})

    async for inv in cursor:
        try:
            now = _utcnow()
            broker = await db.brokers.find_one({"id": inv["broker_id"]}, {"_id": 0})
            if not broker:
                skipped += 1
                continue

            # 1) Revoke auto-approval on the broker
            await db.brokers.update_one(
                {"id": broker["id"]},
                {"$set": {
                    "auto_approval_revoked":           True,
                    "auto_approval_revoked_at":        now,
                    "auto_approval_revoked_reason":    "title_transfer_overdue",
                }},
            )

            # 2) Mark the invoice as enforced
            await db.broker_invoices.update_one(
                {"id": inv["id"]},
                {"$set": {
                    "title_transfer_enforced_at":      now,
                    "title_transfer_enforcement_kind": "overdue_14d",
                }},
            )

            # 3) Dashboard banner notification
            await db.broker_notifications.insert_one({
                "id":          str(uuid.uuid4()),
                "broker_id":   broker["id"],
                "level":       "critical",
                "kind":        "title_transfer_overdue",
                "title_en":    "Title transfer overdue",
                "title_fr":    "Transfert de propriété en retard",
                "body_en":     (f"Invoice {inv.get('invoice_number')} was released over 14 days ago and "
                                f"is missing a provincial title transfer reference. File it now to avoid "
                                f"account suspension."),
                "body_fr":     (f"La facture {inv.get('invoice_number')} a été remise il y a plus de 14 jours "
                                f"et il manque un numéro de référence de transfert provincial. "
                                f"Veuillez consigner le transfert immédiatement pour éviter la suspension."),
                "invoice_id":  inv["id"],
                "created_at":  now,
                "read_at":     None,
            })

            # 4) Email to broker
            broker_user = await db.users.find_one({"id": broker.get("user_id")}, {"_id": 0, "email": 1, "name": 1})
            rel_at = inv.get("released_at")
            if isinstance(rel_at, datetime) and rel_at.tzinfo is None:
                rel_at = rel_at.replace(tzinfo=timezone.utc)
            days_overdue = (now - rel_at).days - 14 if rel_at else None
            await db.email_outbox.insert_one({
                "id":           str(uuid.uuid4()),
                "kind":         "title_transfer_overdue",
                "to_user_id":   broker.get("user_id"),
                "to_email":     (broker_user or {}).get("email"),
                "context": {
                    "broker_name":    broker.get("legal_business_name"),
                    "invoice_id":     inv["id"],
                    "invoice_number": inv.get("invoice_number"),
                    "released_at":    inv.get("released_at"),
                    "days_overdue":   days_overdue,
                },
                "queued_at":    now,
            })

            # 5) Audit row
            await db.broker_invoice_audit.insert_one({
                "id":          str(uuid.uuid4()),
                "invoice_id":  inv["id"],
                "broker_id":   broker["id"],
                "action":      "title_transfer_overdue_enforced",
                "actor":       "system_cron",
                "at":          now,
            })

            enforced += 1
            brokers_flagged.add(broker["id"])
        except Exception as e:
            logger.error("title_transfer_overdue: failed on invoice %s: %s", inv.get("id"), e, exc_info=True)
            skipped += 1

    summary = {
        "ran_at":           _utcnow().isoformat(),
        "enforced_count":   enforced,
        "skipped_count":    skipped,
        "brokers_flagged":  len(brokers_flagged),
    }
    if enforced:
        logger.warning("title_transfer_overdue: enforced %s invoice(s) across %s broker(s)",
                       enforced, len(brokers_flagged))
    return summary
