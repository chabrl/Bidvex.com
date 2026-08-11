"""
services/receipts.py — iter298 BUG 4

Buyer receipts + seller statements, issued on successful payment
collection across all 4 sections (marketplace, lots, vehicles, storage).

Each successful collection produces:
  • db.receipts row  {type: "buyer_receipt"}   → buyer dashboard "Receipts"
  • db.receipts row  {type: "seller_statement"} → seller dashboard "Statements"
  • Itemized bilingual email to each party (EN/FR per platform language).

iter476 — the receipt row now also persists an ITEMIZED financial
breakdown when the calling settlement path provides one (see
``issue_transaction_records(itemized=...)``).  The itemized keys are
strictly the ones the settlement pipeline authoritatively computed —
never a synthetic split of aggregate values.

All amounts CAD. BidVex Inc. letterhead baked into the email templates
(see services/emails/email_system.py).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# iter476 — canonical itemized keys.  When any of these are supplied by
# the caller we persist them verbatim onto the receipt row.  Absent keys
# are stored as `None` so historical rows remain distinguishable from
# newly-itemized ones.
ITEMIZED_KEYS = (
    "hammer_gst", "hammer_qst",
    "buyer_premium", "buyer_premium_gst", "buyer_premium_qst",
    "service_fee", "service_fee_gst", "service_fee_qst",
    "stripe_fee", "stripe_fee_charged_to",
    "seller_commission", "seller_commission_gst", "seller_commission_qst",
    "other_deductions",
    # meta
    "buyer_premium_rate", "seller_commission_rate",
    "seller_is_tax_registered",
    # canonical bidvex tax numbers snapshot at issuance (helps audit
    # reconciliation on the exact rates applied)
    "bidvex_gst_number", "bidvex_qst_number",
    # ── iter480 Phase 3 canonical BidVex Platform Fee split ──
    # For Partner sales the BidVex 3% platform fee historically lived
    # inside `seller_commission`.  Those fields carry the same numeric
    # value AS `seller_commission*` for partner receipts and 0 for
    # every other route.  Reconciliation is UNCHANGED — the new fields
    # are additive metadata used only by PDF renderers to distinguish
    # BidVex-owned revenue from seller-owned deductions.
    "bidvex_platform_fee_rate",
    "bidvex_platform_fee_amount",
    "bidvex_platform_fee_gst",
    "bidvex_platform_fee_qst",
    "fee_schedule_version",
)


def _d(v) -> Decimal:
    """Safe Decimal coercion — treats None / '' / 0 uniformly."""
    if v is None or v == "":
        return Decimal("0")
    try:
        return Decimal(str(v))
    except Exception:  # noqa: BLE001
        return Decimal("0")


def reconcile_itemized(
    *,
    hammer_price: Any,
    itemized: Dict[str, Any],
    total_charged: Any,
    net_payout: Any,
    tolerance_cents: int = 1,
) -> Dict[str, Any]:
    """Verify the itemized breakdown reconciles with the settled
    ``total_charged`` and ``net_payout`` figures.

    Returns::

        {"ok": bool, "buyer_delta_cents": int, "seller_delta_cents": int,
         "buyer_sum": Decimal, "seller_sum": Decimal,
         "reasons": [str, ...]}

    A ``tolerance_cents`` of 1 permits a single-cent rounding drift
    (Decimal quantize on 3 GST/QST components can accumulate a 1¢
    difference vs. Stripe's cents-only totals).
    """
    reasons: list[str] = []

    hammer = _d(hammer_price)
    # Buyer side (must equal total_charged)
    buyer_sum = (
        hammer
        + _d(itemized.get("hammer_gst"))
        + _d(itemized.get("hammer_qst"))
        + _d(itemized.get("buyer_premium"))
        + _d(itemized.get("buyer_premium_gst"))
        + _d(itemized.get("buyer_premium_qst"))
        + _d(itemized.get("service_fee"))
        + _d(itemized.get("service_fee_gst"))
        + _d(itemized.get("service_fee_qst"))
    )
    # Stripe fee is added only if the buyer bears it.
    if str(itemized.get("stripe_fee_charged_to") or "").lower() == "buyer":
        buyer_sum += _d(itemized.get("stripe_fee"))

    buyer_target = _d(total_charged)
    buyer_delta = (buyer_sum - buyer_target).quantize(Decimal("0.01"))
    buyer_delta_cents = int((buyer_delta * 100).to_integral_value())
    if abs(buyer_delta_cents) > tolerance_cents:
        reasons.append(
            f"buyer_sum={buyer_sum} vs total_charged={buyer_target} "
            f"delta={buyer_delta}"
        )

    # Seller side (must equal net_payout)
    # Net payout = hammer  +  hammer_gst/qst (collected on behalf of a
    # tax-registered seller for their remittance)  −  seller_commission
    # −  taxes on commission  −  stripe_fee (only if charged to seller)
    #  −  other_deductions.
    seller_sum = (
        hammer
        + _d(itemized.get("hammer_gst")) + _d(itemized.get("hammer_qst"))
        - _d(itemized.get("seller_commission"))
        - _d(itemized.get("seller_commission_gst"))
        - _d(itemized.get("seller_commission_qst"))
        - _d(itemized.get("other_deductions"))
    )
    if str(itemized.get("stripe_fee_charged_to") or "").lower() == "seller":
        seller_sum -= _d(itemized.get("stripe_fee"))
    if not bool(itemized.get("seller_is_tax_registered")):
        # If the seller is NOT tax-registered we didn't collect hammer
        # tax on their behalf, so back it out.
        seller_sum -= _d(itemized.get("hammer_gst"))
        seller_sum -= _d(itemized.get("hammer_qst"))

    seller_target = _d(net_payout)
    seller_delta = (seller_sum - seller_target).quantize(Decimal("0.01"))
    seller_delta_cents = int((seller_delta * 100).to_integral_value())
    if abs(seller_delta_cents) > tolerance_cents:
        reasons.append(
            f"seller_sum={seller_sum} vs net_payout={seller_target} "
            f"delta={seller_delta}"
        )

    return {
        "ok": len(reasons) == 0,
        "buyer_delta_cents": buyer_delta_cents,
        "seller_delta_cents": seller_delta_cents,
        "buyer_sum": buyer_sum,
        "seller_sum": seller_sum,
        "reasons": reasons,
    }


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
    itemized: Optional[Dict[str, Any]] = None,
) -> Dict[str, Optional[str]]:
    """Create buyer-receipt + seller-statement rows and dispatch both
    emails. Idempotent per (listing_id, lot_number, type). Never raises —
    receipts must not block settlement.

    iter476 — When ``itemized`` is supplied, the values are persisted on
    the receipt row and pre-reconciled against ``total_charged`` /
    ``net_payout``.  On a reconciliation failure the itemized block is
    dropped and a WARNING is logged (the aggregate row is still stored
    so the user's dashboard doesn't break) — silent financial change is
    never made.  Historical receipts written without ``itemized`` remain
    aggregate-only.
    """
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

    # iter476 — attach itemized block after reconciliation
    if itemized:
        rec = reconcile_itemized(
            hammer_price=hammer_price, itemized=itemized,
            total_charged=total_charged, net_payout=net_payout,
        )
        if rec["ok"]:
            for key in ITEMIZED_KEYS:
                v = itemized.get(key)
                if v is None or v == "":
                    base[key] = None
                elif key.endswith("_rate") or key.endswith("_registered") or key.startswith("bidvex_") or key == "stripe_fee_charged_to":
                    base[key] = v
                else:
                    base[key] = round(float(_d(v)), 2)
            base["itemized_reconciled"] = True
            base["itemized_version"] = 1
        else:
            logger.error(
                "[receipts] iter476 reconciliation FAILED for "
                f"listing={listing_id} lot={lot_number} — dropping "
                f"itemized block. reasons={rec['reasons']}"
            )
            base["itemized_reconciled"] = False
            base["itemized_reconcile_reasons"] = rec["reasons"]

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
                # per (auction, buyer, lot). Per-lot receipt rows are still
                # written above; each legitimate per-lot settlement email
                # (iter461) fires once, but retries of the SAME lot's SAME
                # settlement are still blocked by the ledger.
                from services.settlement_email_dedup import claim_settlement_email
                _lot_key = f"lot:{lot_number}" if lot_number is not None else ""
                claimed = await claim_settlement_email(
                    db, kind="buyer_receipt",
                    auction_id=listing_id, user_id=buyer_id,
                    event_key=_lot_key,
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
                    # summary email per (auction, seller, lot). Per-lot
                    # rows still persist; each legitimate per-lot
                    # settlement (iter461) fires once, retries blocked.
                    from services.settlement_email_dedup import claim_settlement_email
                    _lot_key = f"lot:{lot_number}" if lot_number is not None else ""
                    claimed = await claim_settlement_email(
                        db, kind="seller_statement",
                        auction_id=listing_id, user_id=seller_id,
                        event_key=_lot_key,
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
