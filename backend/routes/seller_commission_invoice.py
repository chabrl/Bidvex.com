"""
iter482 P5 — Seller Commission Invoice API
==========================================

Individual/Business sellers pay a 4% BidVex commission (Partner pays 3%,
Storage/Dealer follow their existing rates).  When the seller pays their
commission via Stripe, they bear the Stripe processing recovery — BidVex
does NOT silently absorb it.

Endpoints
---------

    GET  /api/seller/commission-invoice/{listing_id}
        Returns the canonical seller-commission invoice:
        {
            "hammer_cents": ...,
            "seller_commission_rate": 0.04,
            "seller_commission_cents": ...,
            "taxes": { "gst_cents": ..., "qst_cents": ..., "hst_cents": ... },
            "tax_total_cents": ...,
            "stripe_recovery_cents_by_method": {
                "stripe":  <int>,          # gross-up on (commission + tax)
                "cash":     0,
                "etransfer": 0,
                "cheque":    0,
            },
            "total_cents_by_method": { ... },
            "seller_type": "individual" | "business" | "partner" | ...,
            "payment_status": "unpaid" | "paid",
            "listing": { id, title, hammer_price, ... },
        }

    POST /api/seller/commission-invoice/{listing_id}/pay-now
        Body:  { "payment_method": "stripe" | "cash" | "etransfer" | "cheque",
                 "return_url": "..." }
        For Stripe: returns Stripe Checkout Session URL (destination=platform).
        For offline: records a pending invoice, sends bilingual email
        instructions and returns the invoice id.

Both endpoints require the caller to be the listing owner (or admin).
"""

from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import os
import uuid

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from services.payment_cost_engine import estimate as pce_estimate, PayerRole
from routes.payments import _auth  # reuse existing auth helper

router = APIRouter(prefix="/api/seller/commission-invoice", tags=["seller-commission"])
security = HTTPBearer(auto_error=False)

_db_ref = {"db": None}


def set_db(db):
    _db_ref["db"] = db


def _db():
    return _db_ref["db"]


# ─── Commission-rate resolver ─────────────────────────────────────────
#
# iter482 P5 canonical rates:
#   Individual / Business    → 4.00% of hammer
#   Partner                  → 3.00% of hammer  (Model A₁ preserved)
#   Vehicle dealer / Storage → REQUIRES_BUSINESS_REVIEW (do NOT invent)
#
# Fall-back to REQUIRES_BUSINESS_REVIEW rather than silently applying 4%.

_INDIVIDUAL_BUSINESS_RATE = Decimal("0.04")
_PARTNER_RATE = Decimal("0.03")


def _resolve_seller_commission_rate(seller_type: str) -> Decimal:
    s = (seller_type or "").lower()
    if s in ("individual", "business"):
        return _INDIVIDUAL_BUSINESS_RATE
    if s in ("partner", "partner_pro"):
        return _PARTNER_RATE
    # Storage / Vehicle dealer → not covered by this endpoint today
    raise HTTPException(status_code=422, detail={
        "error": "REQUIRES_BUSINESS_REVIEW",
        "reason": f"Seller commission rate for seller_type={seller_type!r} not defined. Configure canonical rate before invoicing.",
    })


def _tax_on(amount_cents: int, province: str) -> Dict[str, int]:
    """Return per-line CRA/RQ-rounded GST/QST/HST on amount_cents."""
    amount = Decimal(amount_cents) / Decimal(100)
    province = (province or "").upper()
    gst_qst_provs = {"QC"}
    hst_provs = {"ON": Decimal("0.13"), "NS": Decimal("0.15"), "NB": Decimal("0.15"),
                 "NL": Decimal("0.15"), "PE": Decimal("0.15")}

    def _q(x: Decimal) -> int:
        cents = (x * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return int(cents)

    if province in gst_qst_provs:
        gst = _q(amount * Decimal("0.05"))
        qst = _q(amount * Decimal("0.09975"))
        return {"gst_cents": gst, "qst_cents": qst, "hst_cents": 0}
    if province in hst_provs:
        return {"gst_cents": 0, "qst_cents": 0, "hst_cents": _q(amount * hst_provs[province])}
    # Others: GST 5% only
    return {"gst_cents": _q(amount * Decimal("0.05")), "qst_cents": 0, "hst_cents": 0}


async def _load_listing(listing_id: str):
    """Look up a listing across all four collections."""
    db = _db()
    for coll in ("listings", "multi_item_listings", "vehicle_listings", "storage_auctions"):
        row = await db[coll].find_one({"id": listing_id}, {"_id": 0})
        if row:
            row["_collection"] = coll
            return row
    return None


async def _resolve_seller_type(listing: Dict[str, Any]) -> str:
    """Determine the seller-type slug for commission calc."""
    db = _db()
    seller = await db.users.find_one({"id": listing.get("seller_id")}, {"_id": 0}) or {}
    if seller.get("is_partner") and seller.get("platform_fee_paid"):
        return "partner"
    if seller.get("account_type") == "business":
        return "business"
    if listing.get("_collection") == "vehicle_listings":
        return "vehicle_dealer"
    if listing.get("_collection") == "storage_auctions":
        return "storage_facility"
    return "individual"


def _build_invoice_body(
    *,
    listing: Dict[str, Any],
    seller_type: str,
    seller_province: str,
) -> Dict[str, Any]:
    """Build the canonical invoice payload (no persistence)."""
    # iter482 P5.1 — for multi_item_listings the hammer_price is the
    # SUM of sold sub-lot hammers.  Fall back to the top-level
    # hammer/current if no lots present.
    hammer = Decimal(str(listing.get("hammer_price") or listing.get("current_price") or 0))
    if listing.get("_collection") == "multi_item_listings":
        lots = listing.get("lots") or listing.get("items") or []
        sold_sum = Decimal(0)
        for lot in lots:
            if lot.get("winner_id") or lot.get("winning_bidder_id"):
                sold_sum += Decimal(str(lot.get("hammer_price") or lot.get("winning_bid") or 0))
        if sold_sum > 0:
            hammer = sold_sum
    if hammer <= 0:
        raise HTTPException(status_code=422, detail={
            "error": "invalid_hammer_price",
            "reason": "Listing has no hammer_price yet; cannot compute commission.",
        })
    rate = _resolve_seller_commission_rate(seller_type)
    commission = (hammer * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    commission_cents = int(commission * 100)
    hammer_cents = int(hammer * 100)

    # Tax on the commission
    taxes = _tax_on(commission_cents, seller_province)
    tax_total = taxes["gst_cents"] + taxes["qst_cents"] + taxes["hst_cents"]

    # Base for the Stripe recovery gross-up = commission + tax
    base_for_recovery = commission_cents + tax_total

    # Compute per-method breakdown
    breakdown: Dict[str, Dict[str, int]] = {}
    for method in ("stripe", "cash", "etransfer", "cheque"):
        # Route "stripe" through payment_cost_engine.  Offline methods
        # always $0 recovery (via _ZERO_METHODS in the canonical engine).
        est = pce_estimate(
            payment_method="stripe_card" if method == "stripe" else method,
            amount_cents=base_for_recovery,
            currency="CAD",
            payer_role=PayerRole.SELLER,
            jurisdiction=seller_province or "QC",
            card_class="domestic",
            mode="gross_up",
        )
        recovery = int(est.recovery_cents)
        breakdown[method] = {
            "commission_cents": commission_cents,
            "gst_cents": taxes["gst_cents"],
            "qst_cents": taxes["qst_cents"],
            "hst_cents": taxes["hst_cents"],
            "tax_total_cents": tax_total,
            "stripe_recovery_cents": recovery,
            "estimated_stripe_fee_cents": int(est.estimated_cents),
            "total_cents": commission_cents + tax_total + recovery,
            "legal_gate_status": est.legal_gate_status.value,
            "reason_code": est.reason_code,
        }

    return {
        "listing_id": listing["id"],
        "listing_title": listing.get("title") or "",
        "hammer_cents": hammer_cents,
        "seller_type": seller_type,
        "seller_commission_rate": str(rate),
        "seller_commission_cents": commission_cents,
        "seller_province": seller_province,
        "taxes": taxes,
        "tax_total_cents": tax_total,
        "breakdown_by_method": breakdown,
        "engine_version": "iter482-P5-v1",
    }


# ─── GET /api/seller/commission-invoice/{listing_id} ─────────────────
@router.get("/{listing_id}")
async def get_commission_invoice(
    listing_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = await _auth(credentials)
    db = _db()

    listing = await _load_listing(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.get("seller_id") != user.id and getattr(user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Only the listing seller can view its commission invoice")

    seller_type = await _resolve_seller_type(listing)
    seller_user = await db.users.find_one({"id": listing.get("seller_id")}, {"_id": 0}) or {}
    seller_province = (seller_user.get("province") or listing.get("region") or "QC").upper()

    # Check whether the invoice is already paid
    paid = await db.seller_commission_invoices.find_one(
        {"listing_id": listing_id, "status": "paid"}, {"_id": 0}
    )

    invoice = _build_invoice_body(
        listing=listing,
        seller_type=seller_type,
        seller_province=seller_province,
    )
    invoice["payment_status"] = "paid" if paid else "unpaid"
    invoice["paid_at"] = (paid or {}).get("paid_at")
    invoice["accepted_offline_methods"] = ["cash", "etransfer", "cheque", "stripe"]

    # iter482 P5.1 — Attach sold-lots table when this is a multi-item
    # listing (Partner or Individual multi-lot batch).  Enables the
    # Partner PAY NOW page to show the full breakdown of sold items.
    if listing.get("_collection") == "multi_item_listings":
        lots = listing.get("lots") or listing.get("items") or []
        sold_lots = [
            {
                "lot_number": lot.get("lot_number") or lot.get("index"),
                "title": lot.get("title") or lot.get("name") or "",
                "hammer_cents": int(round(float(lot.get("hammer_price") or lot.get("winning_bid") or 0) * 100)),
                "winner_id": lot.get("winner_id") or lot.get("winning_bidder_id"),
                "status": lot.get("status") or ("sold" if (lot.get("winner_id") or lot.get("winning_bidder_id")) else "unsold"),
            }
            for lot in lots
            if lot.get("status") in (None, "sold", "won", "closed", "ended")
            and (lot.get("winner_id") or lot.get("winning_bidder_id") or lot.get("hammer_price"))
        ]
        invoice["sold_lots"] = sold_lots
        invoice["sold_lots_count"] = len(sold_lots)
    return invoice


class PayNowRequest(BaseModel):
    payment_method: str = Field(..., description="stripe | cash | etransfer | cheque")
    return_url: Optional[str] = ""


# ─── POST /api/seller/commission-invoice/{listing_id}/pay-now ────────
@router.post("/{listing_id}/pay-now")
async def pay_commission_invoice(
    listing_id: str,
    payload: PayNowRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = await _auth(credentials)
    db = _db()

    listing = await _load_listing(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.get("seller_id") != user.id and getattr(user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Only the listing seller can pay this commission")

    seller_type = await _resolve_seller_type(listing)
    seller_user = await db.users.find_one({"id": listing.get("seller_id")}, {"_id": 0}) or {}
    seller_province = (seller_user.get("province") or listing.get("region") or "QC").upper()

    invoice = _build_invoice_body(
        listing=listing,
        seller_type=seller_type,
        seller_province=seller_province,
    )
    method = payload.payment_method.lower().replace("-", "").replace(" ", "")
    if method not in ("stripe", "cash", "etransfer", "cheque"):
        raise HTTPException(status_code=400, detail="Invalid payment method")

    method_row = invoice["breakdown_by_method"][method]

    # Persist as pending
    inv_id = f"sci_{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc).isoformat()
    invoice_doc = {
        "id": inv_id,
        "listing_id": listing_id,
        "seller_id": listing.get("seller_id"),
        "seller_type": seller_type,
        "seller_province": seller_province,
        "commission_cents": invoice["seller_commission_cents"],
        "commission_rate": invoice["seller_commission_rate"],
        "tax_total_cents": invoice["tax_total_cents"],
        "stripe_recovery_cents": method_row["stripe_recovery_cents"],
        "total_cents": method_row["total_cents"],
        "payment_method": method,
        "status": "pending",
        "created_at": now,
        "engine_version": "iter482-P5-v1",
    }
    await db.seller_commission_invoices.insert_one(invoice_doc)

    if method == "stripe":
        # Direct-charge to the platform account (BidVex).  The buyer/seller
        # relationship here is: SELLER pays BidVex.  Standard direct
        # charge with metadata for reconciliation.
        try:
            import stripe
            stripe.api_key = os.environ.get("STRIPE_TEST_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
            success_url = f"{payload.return_url or ''}?status=success&invoice={inv_id}"
            cancel_url = f"{payload.return_url or ''}?status=cancelled&invoice={inv_id}"
            session = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "cad",
                        "product_data": {
                            "name": f"BidVex Seller Commission — {invoice['listing_title'] or listing_id}",
                            "description": f"Commission {invoice['seller_commission_rate']} × hammer + taxes + Stripe recovery",
                        },
                        "unit_amount": method_row["total_cents"],
                    },
                    "quantity": 1,
                }],
                metadata={
                    "type": "seller_commission_invoice",
                    "transaction_type": "seller_commission_invoice",
                    "invoice_id": inv_id,
                    "listing_id": listing_id,
                    "seller_id": str(listing.get("seller_id")),
                    "commission_cents": str(invoice["seller_commission_cents"]),
                    "tax_total_cents": str(invoice["tax_total_cents"]),
                    "stripe_recovery_cents": str(method_row["stripe_recovery_cents"]),
                    "total_cents": str(method_row["total_cents"]),
                    # iter482 P5.1 canonical reconciliation metadata
                    "payment_processing_estimated_cents": str(int(method_row.get("estimated_stripe_fee_cents", 0))),
                    "payment_processing_recovery_cents": str(int(method_row["stripe_recovery_cents"])),
                    "payment_processing_payer_role": "seller",
                    "payment_processing_jurisdiction": seller_province or "QC",
                    "payment_method": "stripe",
                },
                success_url=success_url,
                cancel_url=cancel_url,
            )
            await db.seller_commission_invoices.update_one(
                {"id": inv_id},
                {"$set": {"stripe_checkout_session_id": session.id}},
            )
            return {
                "invoice_id": inv_id,
                "payment_method": "stripe",
                "checkout_url": session.url,
                "total_cents": method_row["total_cents"],
                "breakdown": method_row,
            }
        except Exception as exc:  # pragma: no cover — Stripe test env
            await db.seller_commission_invoices.update_one(
                {"id": inv_id}, {"$set": {"status": "failed", "error": str(exc)}}
            )
            raise HTTPException(status_code=502, detail={
                "error": "stripe_error", "reason": str(exc),
            }) from exc

    # Offline methods: record and return the pay-later instructions
    return {
        "invoice_id": inv_id,
        "payment_method": method,
        "total_cents": method_row["total_cents"],
        "breakdown": method_row,
        "instructions": {
            "cash":     "Contact BidVex support to arrange in-person cash payment.",
            "etransfer": "Send an Interac E-Transfer to payments@bidvex.com quoting the invoice id.",
            "cheque":    "Mail a bank cheque payable to 'BidVex Inc.' quoting the invoice id.",
        }[method],
    }
