"""
iter460 — Settlement email dedup ledger.

Single source of truth for "have we already sent THIS transactional email
for THIS settlement event to THIS user?" A tiny helper backed by a
`settlement_email_dispatches` collection with a UNIQUE index on
(kind, auction_id, user_id, event_key) so the check is atomic and
race-free.

iter461 — The delivery key includes `event_key` to distinguish two
LEGITIMATELY-separate settlement events of the same kind within one
auction. For once-per-auction kinds callers pass `event_key=""` (or
omit). For per-lot kinds (buyer_receipt, seller_statement, payment_link,
payment_failed, and vehicle-multi-lot auction_won / seller_sold that
close on different timestamps) callers pass `event_key=f"lot:{n}"`. This
does not weaken the retry guarantee: retries of the SAME event resolve
to the SAME event_key and are still blocked by the unique constraint.

Design rules:
  • The ledger controls SEND. It never controls persistence — receipts,
    statements, invoices, and payment rows are still written per-lot.
  • The claim is idempotent per (kind, auction_id, user_id, event_key).
  • Non-blocking: on any DB error the helper degrades to "claim=True" so
    settlement email flow is never broken by ledger unavailability.

Recognised kinds (extend cautiously — every new value is a new dedup
namespace):
    auction_won                 — buyer's "you won" email at auction close
    seller_sold                 — seller's "your auction sold" summary
    buyer_receipt               — buyer's payment-received receipt email
    seller_statement            — seller's payment-received statement email
    payment_link                — buyer's "we could not charge — pay by link"
    payment_failed              — buyer's "charge failed" email
    purchase_confirmation_buyer — webhook checkout completion → buyer email
    purchase_confirmation_seller — webhook checkout completion → seller email
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

COLLECTION = "settlement_email_dispatches"

VALID_KINDS = {
    "auction_won",
    "seller_sold",
    "buyer_receipt",
    "seller_statement",
    "payment_link",
    "payment_failed",
    "purchase_confirmation_buyer",
    "purchase_confirmation_seller",
    # iter468 — Final document delivery for confirmed Stripe auction
    # payments. One secure-link email per side per settlement.
    "final_document_buyer_link",
    "final_document_seller_link",
}


async def ensure_indexes(db) -> None:
    """Create the unique index. Safe to call repeatedly.

    iter461 — the unique key now includes `event_key`. If a pre-iter461
    index exists (`kind, auction_id, user_id`) it is dropped so the new
    four-field composite becomes the enforced constraint. Migration is
    safe because `event_key` defaults to `""` for existing rows.
    """
    try:
        # Ensure any rows without event_key have the empty-string default.
        try:
            await db[COLLECTION].update_many(
                {"event_key": {"$exists": False}},
                {"$set": {"event_key": ""}},
            )
        except Exception:
            pass

        # Drop the legacy three-field index if it exists so the new
        # four-field constraint can take over.
        try:
            info = await db[COLLECTION].index_information()
            for name, spec in info.items():
                keys = [k for k, _ in spec.get("key", [])]
                if keys == ["kind", "auction_id", "user_id"]:
                    await db[COLLECTION].drop_index(name)
        except Exception as inner:  # noqa: BLE001
            logger.info(f"[settlement-email-dedup] legacy index drop skipped: {inner}")

        await db[COLLECTION].create_index(
            [("kind", 1), ("auction_id", 1), ("user_id", 1), ("event_key", 1)],
            unique=True,
            name="uniq_settlement_email_dispatch_v2",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[settlement-email-dedup] ensure_indexes failed: {exc}")


async def claim_settlement_email(
    db,
    *,
    kind: str,
    auction_id: str,
    user_id: str,
    event_key: str = "",
    metadata: Optional[dict] = None,
) -> bool:
    """Attempt to claim the (kind, auction_id, user_id, event_key) slot.

    Returns:
        True  → first claim; caller SHOULD send the email.
        False → a claim already exists; caller MUST skip the send.

    `event_key` (iter461) — stable identity of the distinct settlement
    event within the (kind, auction_id, user_id) namespace. Use `""` for
    once-per-auction kinds and `f"lot:{lot_number}"` for per-lot kinds.
    Retries of the SAME real event share the SAME event_key and remain
    blocked by the unique constraint.

    Never raises. On any non-duplicate DB error, returns True (fail-open).
    """
    if not kind or not auction_id or not user_id:
        return True
    if kind not in VALID_KINDS:
        logger.warning(f"[settlement-email-dedup] unknown kind={kind!r}; allowing send")
        return True

    now_iso = datetime.now(timezone.utc).isoformat()
    row: dict[str, Any] = {
        "kind": kind,
        "auction_id": auction_id,
        "user_id": user_id,
        "event_key": event_key or "",
        "sent_at": now_iso,
        "created_at": now_iso,
    }
    if metadata:
        row["metadata"] = metadata

    try:
        await db[COLLECTION].insert_one(row)
        return True
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "duplicate key" in msg.lower() or "E11000" in msg:
            logger.info(
                f"[settlement-email-dedup] skip duplicate {kind} "
                f"auction={auction_id} user={user_id} event={event_key!r}"
            )
            return False
        logger.warning(
            f"[settlement-email-dedup] insert error (fail-open) {kind} "
            f"auction={auction_id} user={user_id} event={event_key!r}: {exc}"
        )
        return True


__all__ = ["ensure_indexes", "claim_settlement_email", "VALID_KINDS", "COLLECTION"]
