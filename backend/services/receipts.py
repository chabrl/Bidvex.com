"""
services/receipts.py — iter298 BUG 4

Buyer receipts + seller statements, issued on successful payment
collection across all 4 sections (marketplace, lots, vehicles, storage).

Each successful collection produces:
  • db.receipts row  {type: "buyer_receipt"}   → buyer dashboard "Receipts"
  • db.receipts row  {type: "seller_statement"} → seller dashboard "Statements"
  • Itemized bilingual email to each party (EN/FR per platform language).

All amounts CAD. BidVex Inc. letterhead baked into the email templates
(see services/emails/email_system.py).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _first_name(user: Optional[Dict[str, Any]]) -> str:
    raw = ((user or {}).get("name") or (user or {}).get("full_name") or "").strip()
    if raw:
        return raw.split()[0]
    email = (user or {}).get("email") or ""
    return email.split("@")[0] if email else "—"


async def issue_transaction_records(
    db,
    *,
    section: str,                      # marketplace | lots | vehicles | storage
    listing_id: str,
    listing_title: str,
    buyer_id: str,
    seller_id: Optional[str],
    hammer_price: float,
    platform_fee: float,
    taxes: float = 0.0,
    processing_fee: float = 0.0,
    total_charged: float = 0.0,
    currency: str = "CAD",
    payment_method_last4: Optional[str] = None,
    transaction_id: Optional[str] = None,
    net_payout: Optional[float] = None,
    lot_number: Optional[Any] = None,
    pickup_code: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """Create buyer-receipt + seller-statement rows and dispatch both
    emails. Idempotent per (listing_id, lot_number, type). Never raises —
    receipts must not block settlement."""
    out: Dict[str, Optional[str]] = {"receipt_id": None, "statement_id": None}
    now_iso = datetime.now(timezone.utc).isoformat()
    if net_payout is None:
        net_payout = round(float(hammer_price) - float(platform_fee), 2)
    if not total_charged:
        total_charged = round(
            float(hammer_price) + float(platform_fee) + float(taxes) + float(processing_fee), 2
        )

    base = {
        "section": section,
        "listing_id": listing_id,
        "lot_number": lot_number,
        "listing_title": listing_title,
        "hammer_price": round(float(hammer_price), 2),
        "platform_fee": round(float(platform_fee), 2),
        "taxes": round(float(taxes), 2),
        "processing_fee": round(float(processing_fee), 2),
        "total_charged": round(float(total_charged), 2),
        "net_payout": round(float(net_payout), 2),
        "currency": currency.upper(),
        "payment_method_last4": payment_method_last4,
        "transaction_id": transaction_id,
        "pickup_code": pickup_code,
        "created_at": now_iso,
    }

    buyer = await db.users.find_one({"id": buyer_id}, {"_id": 0}) if buyer_id else None
    seller = await db.users.find_one({"id": seller_id}, {"_id": 0}) if seller_id else None

    # iter366 — enrich the receipt dict with seller display name + order
    # number so the redesigned buyer receipt email can render "Item / Seller
    # / Order / Date" without an extra DB round-trip inside the mailer.
    def _display_name(u):
        if not u: return "BidVex Seller"
        raw = (u.get("name") or u.get("business_name") or u.get("full_name") or "").strip()
        if raw: return raw
        email = u.get("email") or ""
        return email.split("@")[0] if email else "BidVex Seller"
    base["seller_name"] = _display_name(seller)
    # Short human-readable order number derived from the listing id — 8 chars
    # (uppercase, no dashes) prefixed with BVX- (e.g. BVX-179B62B9). Falls
    # back to a fresh uuid slice if listing_id is missing.
    _short = (listing_id or str(uuid.uuid4())).replace("-", "")[:8].upper()
    base["order_number"] = f"BVX-{_short}"

    # ── Buyer receipt ──
    try:
        dedup_q = {"listing_id": listing_id, "lot_number": lot_number,
                   "type": "buyer_receipt", "user_id": buyer_id}
        existing = await db.receipts.find_one(dedup_q, {"_id": 0, "id": 1})
        if existing:
            out["receipt_id"] = existing["id"]
        elif buyer_id:
            rid = str(uuid.uuid4())
            await db.receipts.insert_one({**base, "id": rid, "type": "buyer_receipt",
                                          "user_id": buyer_id})
            out["receipt_id"] = rid
            if buyer and buyer.get("email"):
                # iter460 — settlement-email dedup: one buyer_receipt email
                # per (auction, buyer). Per-lot receipt rows are still
                # written above; only the customer-facing email is gated.
                from services.settlement_email_dedup import claim_settlement_email
                claimed = await claim_settlement_email(
                    db, kind="buyer_receipt",
                    auction_id=listing_id, user_id=buyer_id,
                )
                if claimed:
                    try:
                        from services.emails.email_system import send_buyer_receipt_email
                        await send_buyer_receipt_email(
                            buyer=buyer, receipt={**base, "id": rid},
                        )
                    except Exception as e:  # noqa: BLE001
                        logger.warning(f"[receipts] buyer receipt email failed for {listing_id}: {e}")
                else:
                    logger.info(
                        f"[receipts] buyer receipt email suppressed by dedup "
                        f"for {listing_id} lot {lot_number} buyer {buyer_id}"
                    )
    except Exception as e:  # noqa: BLE001
        logger.error(f"[receipts] buyer receipt failed for {listing_id}: {e}")

    # ── Seller statement ──
    try:
        if seller_id:
            dedup_q = {"listing_id": listing_id, "lot_number": lot_number,
                       "type": "seller_statement", "user_id": seller_id}
            existing = await db.receipts.find_one(dedup_q, {"_id": 0, "id": 1})
            if existing:
                out["statement_id"] = existing["id"]
            else:
                sid = str(uuid.uuid4())
                await db.receipts.insert_one({
                    **base, "id": sid, "type": "seller_statement",
                    "user_id": seller_id,
                    "buyer_first_name": _first_name(buyer),
                })
                out["statement_id"] = sid
                if seller and seller.get("email"):
                    # iter460 — settlement-email dedup: one seller_statement
                    # summary email per (auction, seller). Per-lot rows still
                    # persist; only the email is deduped.
                    from services.settlement_email_dedup import claim_settlement_email
                    claimed = await claim_settlement_email(
                        db, kind="seller_statement",
                        auction_id=listing_id, user_id=seller_id,
                    )
                    if claimed:
                        try:
                            from services.emails.email_system import send_seller_statement_email
                            await send_seller_statement_email(
                                seller=seller,
                                statement={**base, "id": sid,
                                           "buyer_first_name": _first_name(buyer)},
                            )
                        except Exception as e:  # noqa: BLE001
                            logger.warning(f"[receipts] seller statement email failed for {listing_id}: {e}")
                    else:
                        logger.info(
                            f"[receipts] seller statement email suppressed by dedup "
                            f"for {listing_id} lot {lot_number} seller {seller_id}"
                        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"[receipts] seller statement failed for {listing_id}: {e}")

    return out
