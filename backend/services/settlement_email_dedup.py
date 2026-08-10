"""
iter460 — Settlement email dedup ledger.

Single source of truth for "have we already sent THIS transactional email
for THIS settlement event to THIS user?" A tiny helper backed by a
`settlement_email_dispatches` collection with a UNIQUE index on
(kind, auction_id, user_id) so the check is atomic and race-free.

Design rules:
  • The ledger controls SEND. It never controls persistence — receipts,
    statements, invoices, and payment rows are still written per-lot.
  • The claim is idempotent per (kind, auction_id, user_id). Cross-lot
    triggers for the same buyer or seller on the same auction resolve
    to the same claim key, so only the first trigger sends the email.
  • Retries (scheduler tick #2, webhook retry, admin re-drive) reuse the
    existing claim and skip the send. This does NOT prevent the admin's
    explicit `resend_winner_notification` endpoint (see routes/settlement.py)
    which uses its own rate-limited path.
  • Non-blocking: on any DB error the helper degrades to "claim=True" so
    settlement email flow is never broken by ledger unavailability. The
    downside — potential duplicate on a very rare DB blip — is preferred
    over silently dropping a real settlement email.

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

The ledger lives in the primary MongoDB DB. Create the unique index once
at process start via `ensure_indexes()` — safe to call repeatedly.
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
}


async def ensure_indexes(db) -> None:
    """Create the unique compound index. Safe to call repeatedly."""
    try:
        await db[COLLECTION].create_index(
            [("kind", 1), ("auction_id", 1), ("user_id", 1)],
            unique=True,
            name="uniq_settlement_email_dispatch",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[settlement-email-dedup] ensure_indexes failed: {exc}")


async def claim_settlement_email(
    db,
    *,
    kind: str,
    auction_id: str,
    user_id: str,
    metadata: Optional[dict] = None,
) -> bool:
    """Attempt to claim the (kind, auction_id, user_id) send slot.

    Returns:
        True  → first claim; caller SHOULD send the email.
        False → a claim already exists; caller MUST skip the send.

    Never raises. On any DB error, returns True (fail-open) so real
    settlement notifications are not lost due to ledger issues. This
    matches the platform's existing pattern of "receipts must not block
    settlement" (see services/payment_collection.py comments).
    """
    if not kind or not auction_id or not user_id:
        # Missing identifiers — cannot dedup, allow send (fail-open).
        return True
    if kind not in VALID_KINDS:
        logger.warning(f"[settlement-email-dedup] unknown kind={kind!r}; allowing send")
        return True

    now_iso = datetime.now(timezone.utc).isoformat()
    row: dict[str, Any] = {
        "kind": kind,
        "auction_id": auction_id,
        "user_id": user_id,
        "sent_at": now_iso,
        "created_at": now_iso,
    }
    if metadata:
        row["metadata"] = metadata

    try:
        await db[COLLECTION].insert_one(row)
        return True
    except Exception as exc:  # noqa: BLE001
        # DuplicateKeyError → claim already exists → skip send.
        msg = str(exc)
        if "duplicate key" in msg.lower() or "E11000" in msg:
            logger.info(
                f"[settlement-email-dedup] skip duplicate {kind} "
                f"auction={auction_id} user={user_id}"
            )
            return False
        # Any other error — fail-open (don't drop real settlement emails).
        logger.warning(
            f"[settlement-email-dedup] insert error (fail-open) {kind} "
            f"auction={auction_id} user={user_id}: {exc}"
        )
        return True


__all__ = ["ensure_indexes", "claim_settlement_email", "VALID_KINDS", "COLLECTION"]
