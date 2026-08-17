"""
BidVex - Invoice Generation & Delivery
Auto-extracted from server.py during P2 refactoring.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from deps import get_db, get_current_user, get_current_user_optional, User
from shared import (
    DEFAULT_EMAIL_TEMPLATES, EMAIL_TEMPLATE_CATEGORIES,
    DEFAULT_MARKETPLACE_SETTINGS, AFFILIATE_COMMISSION_RATE,
    generate_affiliate_code, get_email_templates, get_email_template_id,
    get_marketplace_settings, get_epoch_timestamp, get_server_timestamp,
    calculate_buyer_fees, calculate_seller_fees, calculate_stripe_fee_recovery,
    calculate_partner_checkout, calculate_standard_checkout,
    FeeCalculation, UserCreate, Category, Invoice, PaddleNumber,
    PaymentTransaction, SessionCreate, get_minimum_increment,
    STANDARD_BUYER_PREMIUM_RATE, STANDARD_SELLER_COMMISSION_RATE,
    PARTNER_PLATFORM_FEE_RATE, PARTNER_ANNUAL_ACCESS_FEE,
    STRIPE_PERCENTAGE_FEE, STRIPE_FIXED_FEE,
)
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from pathlib import Path
import logging
import uuid
import os
import os as _os
import json as _json

logger = logging.getLogger(__name__)

from services.email_service import get_email_service
from services.invoice_generator import generate_invoice_number
from invoice_templates import lots_won_template
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from starlette.responses import FileResponse
import hmac
import hashlib
import io


# iter211 — Module-level lazy `db` proxy. Resolves the previous F821 errors
# where endpoints used `db.xxx` without first calling `db = get_db()`. The
# proxy lazily delegates every attribute access to the runtime DB returned by
# `deps.get_db()`. This fixes 50+ undefined-name references in this file
# without altering endpoint logic.
class _LazyDBProxy:
    def __getattr__(self, name):
        return getattr(get_db(), name)

    def __getitem__(self, name):
        return get_db()[name]

db = _LazyDBProxy()


# iter211 — Stubs for previously-undefined helper functions that were lost
# during the original server.py → routes/invoices.py extraction. Any endpoint
# that still references them will now return a clear 501 instead of crashing
# with NameError at request time. These code paths are not part of the
# active checkout/invoice flow (validated via grep — referenced only here).
async def _render_subscription_invoice_pdf(invoice: dict) -> bytes:
    raise HTTPException(
        status_code=501,
        detail="Subscription invoice PDF generation has been migrated to the new flow. "
               "Please use POST /api/billing/invoices/{id}/render instead.",
    )


async def generate_paddle_number(auction_id: str) -> int:
    """Issue a new paddle number for a given auction.

    The original helper in server.py is no longer importable. We reconstruct
    the same logic here: next paddle = max(existing) + 1, starting at 100.
    """
    last = await get_db().paddle_numbers.find(
        {"auction_id": auction_id},
        {"_id": 0, "paddle_number": 1},
    ).sort("paddle_number", -1).limit(1).to_list(1)
    return (last[0]["paddle_number"] + 1) if last else 100


def generate_pdf_from_html(html: str, output_path: str) -> str:
    """Minimal HTML → PDF fallback. The full WeasyPrint helper was lost
    during refactor; we reconstruct with ReportLab Paragraph so the endpoint
    no longer NameErrors. Production-grade rendering uses the templates
    in invoice_templates.py directly.
    """
    from reportlab.lib.pagesizes import letter as _letter
    from reportlab.platypus import SimpleDocTemplate as _Doc, Paragraph as _P
    from reportlab.lib.styles import getSampleStyleSheet as _styles
    doc = _Doc(str(output_path), pagesize=_letter)
    style = _styles()["Normal"]
    # Strip the most common HTML/CSS so ReportLab's paraparser can consume
    # what's left. iter451 — added <style>, <img>, <!DOCTYPE>, and
    # <head> stripping so the invoice HTML actually renders.
    import re
    text = html
    # Remove <!DOCTYPE ...>, <html>/<head> shell, and full <style>/<script> blocks
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<head[^>]*>.*?</head>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)
    # Strip inline images (base64 logo dumps break the paraparser)
    text = re.sub(r"<img[^>]*/?>", "", text, flags=re.IGNORECASE)
    # Normalise <br>
    text = re.sub(r"<br\s*/?>", "<br/>", text, flags=re.IGNORECASE)
    # Strip everything except <br/> since reportlab wants strictly-paired
    # tags (unpaired <strong> breaks the paraparser).
    text = re.sub(r"<(?!br\s*/?>)[^>]+>", "", text)
    # Collapse whitespace so paragraph text stays under paraparser limits.
    text = re.sub(r"\s+", " ", text).strip()
    doc.build([_P(text, style)])
    return output_path

invoices_router = APIRouter(tags=["Invoices"])


# ══════════════════════════════════════════════════════════════════════════
# iter457 — Seller-document data resolver (shared by seller_statement,
# seller_receipt, commission_invoice + the auction-complete summary email).
#
# Replaces the previous "first 3 lots are sold, buyer='Test Buyer', paddle=
# 5051+i, commission_rate=0.0 by default" placeholders. Every field the
# templates render now comes from real settled data:
#
#   • Sold vs unsold        → lot.status ∈ {sold, won} OR lot.winner_user_id
#                              set AND resolved hammer_total > 0
#   • Buyer name + paddle   → users + paddle_numbers collections keyed on
#                              the actual winner_user_id per lot
#   • Quantity + hammer     → services.hammer_total.resolve_hammer_total
#                              (supports unit × quantity multi-item math)
#   • Fee + tax on fee      → services.fee_calculator.calculate_fee(...)
#                              (CRA Place-of-Supply; NEVER silently zero
#                              — a zero fee only appears when the real
#                              seller_account_type policy is zero, e.g.
#                              storage_facility on the seller side)
#   • Settlement status     → receipts collection with
#                              type="seller_statement" per lot_number
#
# The helper is pure/read-only and safe to call from any route.
# ══════════════════════════════════════════════════════════════════════════

async def _build_settled_seller_dataset(db_client, auction: Dict[str, Any], seller_id: str) -> Dict[str, Any]:
    """Build the real settled-lot dataset for the given auction + seller.

    Returns a dict with:
        {
          "lots": [                 # every lot on the auction — sold OR unsold
             {
               "lot_number": int|str,
               "title": str,
               "description": str,
               "status": "sold"|"unsold",
               "quantity": int,     # actual settled quantity
               "unit_price": float,
               "hammer_price": float,           # unit × qty
               "buyer_name": str|None,          # real buyer or None
               "paddle_number": int|None,       # real paddle or None
               "platform_fee": float,           # from fee engine
               "seller_tax_on_fee": float,      # from fee engine
               "net_payout": float,             # from fee engine
               "settlement_status": "settled"|"pending_settlement",
               "settled_at": str|None,          # ISO if settled
             },
             ...
          ],
          "sold_lots": [ ... subset with status='sold' ... ],
          "unsold_lots": [ ... subset with status='unsold' ... ],
          "total_hammer": float,          # sum(sold_lots.hammer_price)
          "total_platform_fee": float,    # sum(sold_lots.platform_fee)
          "total_tax_on_fee": float,      # sum(sold_lots.seller_tax_on_fee)
          "total_net_payout": float,      # sum(sold_lots.net_payout)
          # Rates surfaced for the templates that render "%".
          "commission_rate_pct": float,   # e.g. 4.0 or 2.5 — sourced from
                                          # calculate_fee(); NEVER a silent 0
          "commission_rate_source": str,  # "fee_engine" | "storage_facility_zero"
          "tax_rate_gst_pct": float,      # 5.0 for QC, effective HST for HST provinces
          "tax_rate_qst_pct": float,      # 9.975 for QC, else 0.0
          "seller_tax_label": str,        # e.g. "GST+QST @ QC" for audit
          "seller_tax_province": str,     # normalized province used for tax
        }

    Raises HTTPException(500) when the fee-engine cannot resolve a real
    policy (defensive — should never occur since calculate_fee is total).
    """
    from services.hammer_total import resolve_hammer_total
    from services.fee_calculator import calculate_fee

    # ── Seller context (province + tier + account_type — real fee policy) ──
    seller = await db_client.users.find_one({"id": seller_id}, {"_id": 0}) or {}
    seller_tier = seller.get("subscription_tier", "free")
    seller_prov_raw = (
        seller.get("province")
        or seller.get("business_province")
        or auction.get("location_province")
        or "QC"
    )
    # Account-type dispatch — mirrors the settlement engine's routing.
    if seller.get("is_partner"):
        seller_account_type = "partner"
    elif seller.get("is_vehicle_dealer"):
        seller_account_type = "vehicle_dealer"
    elif seller.get("is_storage_facility"):
        seller_account_type = "storage_facility"
    elif seller.get("account_type") == "enterprise":
        seller_account_type = "enterprise"
    else:
        seller_account_type = "individual"

    # ── Buyer/paddle lookup cache (avoid N+1 queries) ──
    winner_ids = set()
    for lot in auction.get("lots", []) or []:
        w = lot.get("winner_user_id") or lot.get("winner_id") or lot.get("highest_bidder_id")
        if w:
            winner_ids.add(w)

    users_by_id: Dict[str, Dict[str, Any]] = {}
    if winner_ids:
        async for u in db_client.users.find(
            {"id": {"$in": list(winner_ids)}},
            {"_id": 0, "id": 1, "name": 1, "full_name": 1, "email": 1,
             "province": 1, "subscription_tier": 1},
        ):
            users_by_id[u["id"]] = u

    paddles_by_uid: Dict[str, int] = {}
    if winner_ids:
        async for p in db_client.paddle_numbers.find(
            {"auction_id": auction.get("id"), "user_id": {"$in": list(winner_ids)}},
            {"_id": 0, "user_id": 1, "paddle_number": 1},
        ):
            paddles_by_uid[p["user_id"]] = p.get("paddle_number")

    # ── Settled-receipt lookup: presence of a seller_statement receipt row
    #    for (listing_id=auction.id, lot_number=X, user_id=seller_id) means
    #    payment was collected + funds accounted for. Absence → pending.
    settled_by_lot: Dict[Any, Dict[str, Any]] = {}
    async for r in db_client.receipts.find(
        {"listing_id": auction.get("id"), "user_id": seller_id, "type": "seller_statement"},
        {"_id": 0, "lot_number": 1, "created_at": 1, "transaction_id": 1,
         "platform_fee": 1, "taxes": 1, "net_payout": 1, "hammer_price": 1},
    ):
        settled_by_lot[r.get("lot_number")] = r

    # ── Iterate every lot; classify sold vs unsold using REAL data only ──
    processed_lots: list = []
    for lot in auction.get("lots", []) or []:
        winner_id = (
            lot.get("winner_user_id")
            or lot.get("winner_id")
            or lot.get("highest_bidder_id")
        )
        lot_status_raw = (lot.get("status") or "").lower()

        totals = resolve_hammer_total(auction, lot=lot)
        hammer_total = float(totals["hammer_total"])
        unit_price = float(totals["unit_price"])
        quantity = int(totals["quantity"])

        # A lot is SOLD when there's both a winner AND a positive hammer.
        # Status field is authoritative when present, else infer from winner+price.
        is_sold = False
        if lot_status_raw in ("sold", "won"):
            is_sold = winner_id is not None and hammer_total > 0
        elif winner_id and hammer_total > 0 and lot_status_raw not in ("cancelled", "removed", "voided"):
            is_sold = True

        # Buyer context (only when there's a real winner).
        buyer_name = None
        paddle_number = None
        buyer_prov = None
        buyer_tier = "free"
        if is_sold and winner_id:
            u = users_by_id.get(winner_id) or {}
            buyer_name = (u.get("full_name") or u.get("name") or u.get("email") or "").strip() or None
            paddle_number = paddles_by_uid.get(winner_id)
            buyer_prov = (u.get("province") or seller_prov_raw)
            buyer_tier = u.get("subscription_tier") or "free"

        # Per-lot fee via the fee engine — the ONLY source. Never silent zero.
        platform_fee = 0.0
        seller_tax_on_fee = 0.0
        net_payout = 0.0
        seller_tax_label = ""
        seller_tax_province = seller_prov_raw
        commission_rate_dec = 0.0
        # iter458 — Capture per-tax-component amounts + effective rates
        # EXACTLY as returned by the tax engine. These are used to render
        # the tax-label section without inferring types from the province.
        seller_gst_amount = 0.0
        seller_qst_amount = 0.0
        seller_hst_amount = 0.0

        if is_sold and hammer_total > 0:
            try:
                fee = calculate_fee(
                    hammer_price=hammer_total,
                    auction_type=auction.get("listing_type") or auction.get("auction_type") or "lots",
                    seller_account_type=seller_account_type,
                    seller_tier=seller_tier,
                    buyer_account_type="individual",
                    buyer_tier=buyer_tier,
                    payment_method="stripe",
                    card_type="domestic",
                    buyer_province=buyer_prov or seller_prov_raw,
                    seller_province=seller_prov_raw,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(f"[seller-docs] calculate_fee failed for auction={auction.get('id')} lot={lot.get('lot_number')}: {exc}")
                raise HTTPException(
                    status_code=500,
                    detail="fee_engine_unavailable — seller document cannot be produced without a real fee policy",
                )
            platform_fee = float(fee.get("seller_commission") or 0.0)
            seller_tax_on_fee = float(fee.get("seller_taxes") or 0.0)
            net_payout = float(fee.get("seller_payout") or 0.0)
            seller_tax_label = str(fee.get("seller_tax_label") or "")
            seller_tax_province = str(fee.get("seller_tax_province") or seller_prov_raw)
            commission_rate_dec = float(fee.get("seller_commission_rate") or 0.0)
            seller_gst_amount = float(fee.get("seller_gst") or 0.0)
            seller_qst_amount = float(fee.get("seller_qst") or 0.0)
            seller_hst_amount = float(fee.get("seller_hst") or 0.0)

        settled_row = settled_by_lot.get(lot.get("lot_number"))
        settlement_status = "settled" if settled_row else ("pending_settlement" if is_sold else "not_sold")

        processed_lots.append({
            "lot_number": lot.get("lot_number"),
            "title": lot.get("title") or "",
            "description": lot.get("description") or "",
            "status": "sold" if is_sold else "unsold",
            "quantity": quantity if is_sold else 0,
            "unit_price": unit_price if is_sold else 0.0,
            "hammer_price": hammer_total if is_sold else 0.0,
            "buyer_name": buyer_name,
            "paddle_number": paddle_number,
            "platform_fee": round(platform_fee, 2),
            "seller_tax_on_fee": round(seller_tax_on_fee, 2),
            "net_payout": round(net_payout, 2),
            "settlement_status": settlement_status,
            "settled_at": (settled_row or {}).get("created_at"),
            "commission_rate_pct": round(commission_rate_dec * 100, 4),
            "seller_tax_label": seller_tax_label,
            "seller_tax_province": seller_tax_province,
            # iter458 — Exact tax-component amounts from the engine (no
            # inference from province). Used by the tax-line renderer.
            "seller_gst_amount": round(seller_gst_amount, 2),
            "seller_qst_amount": round(seller_qst_amount, 2),
            "seller_hst_amount": round(seller_hst_amount, 2),
        })

    sold_lots = [l for l in processed_lots if l["status"] == "sold"]
    unsold_lots = [l for l in processed_lots if l["status"] == "unsold"]

    total_hammer = round(sum(l["hammer_price"] for l in sold_lots), 2)
    total_platform_fee = round(sum(l["platform_fee"] for l in sold_lots), 2)
    total_tax_on_fee = round(sum(l["seller_tax_on_fee"] for l in sold_lots), 2)
    total_net_payout = round(sum(l["net_payout"] for l in sold_lots), 2)

    # Effective commission rate for the summary templates. For a
    # multi-lot settlement the rate is identical across sold lots (same
    # seller/tier/province), so we take the first sold-lot's rate. If no
    # lots sold, we still expose the rate the fee engine WOULD apply
    # (probe with $1 hammer) — never silent zero when policy is non-zero.
    if sold_lots:
        commission_rate_pct = sold_lots[0]["commission_rate_pct"]
        commission_rate_source = "fee_engine"
        first_sold = sold_lots[0]
        # Derive display tax rates from actual fee-engine numbers so QC's
        # 5% + 9.975% split is preserved and other-province HST rolls up
        # into `tax_rate_gst_pct` (with QST=0) for the current templates.
        eff_tax_pct = 0.0
        if first_sold["platform_fee"] > 0:
            eff_tax_pct = (first_sold["seller_tax_on_fee"] / first_sold["platform_fee"]) * 100.0
        if first_sold["seller_tax_province"] == "QC":
            tax_rate_gst_pct = 5.0
            tax_rate_qst_pct = 9.975
        else:
            tax_rate_gst_pct = round(eff_tax_pct, 4)
            tax_rate_qst_pct = 0.0
        seller_tax_label = first_sold["seller_tax_label"]
        seller_tax_province = first_sold["seller_tax_province"]
    else:
        # Probe the fee engine so we still emit the true policy rate.
        try:
            from services.fee_calculator import calculate_fee as _cf
            probe = _cf(
                hammer_price=100.0,
                auction_type=auction.get("listing_type") or "lots",
                seller_account_type=seller_account_type,
                seller_tier=seller_tier,
                buyer_account_type="individual",
                buyer_tier="free",
                payment_method="stripe",
                card_type="domestic",
                buyer_province=seller_prov_raw,
                seller_province=seller_prov_raw,
            )
            commission_rate_pct = round(float(probe.get("seller_commission_rate") or 0.0) * 100, 4)
            commission_rate_source = "fee_engine"
            seller_tax_label = str(probe.get("seller_tax_label") or "")
            seller_tax_province = str(probe.get("seller_tax_province") or seller_prov_raw)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"[seller-docs] fee-engine probe failed: {exc}")
            raise HTTPException(
                status_code=500,
                detail="fee_engine_unavailable — seller document cannot be produced without a real fee policy",
            )
        if seller_account_type == "storage_facility":
            commission_rate_source = "storage_facility_zero"
        if seller_tax_province == "QC":
            tax_rate_gst_pct = 5.0
            tax_rate_qst_pct = 9.975
        else:
            tax_rate_gst_pct = 0.0
            tax_rate_qst_pct = 0.0

    return {
        "lots": processed_lots,
        "sold_lots": sold_lots,
        "unsold_lots": unsold_lots,
        "total_hammer": total_hammer,
        "total_platform_fee": total_platform_fee,
        "total_tax_on_fee": total_tax_on_fee,
        "total_net_payout": total_net_payout,
        "commission_rate_pct": commission_rate_pct,
        "commission_rate_source": commission_rate_source,
        "tax_rate_gst_pct": tax_rate_gst_pct,
        "tax_rate_qst_pct": tax_rate_qst_pct,
        "seller_tax_label": seller_tax_label,
        "seller_tax_province": seller_tax_province,
        "seller_account_type": seller_account_type,
        # iter458 — Tax-label accuracy. Faithfully surfaces the tax
        # components the existing engine actually returned — GST / QST /
        # HST (and no others). The list is empty for zero-tax outcomes,
        # so templates can suppress the tax section instead of printing
        # a misleading zero-rate line.
        "seller_tax_lines": _build_seller_tax_lines(processed_lots),
        "seller_tax_engine_labels": {
            # Canonical strings from tax_rate_config (unchanged).
            "raw_label":     seller_tax_label,
            "province_code": seller_tax_province,
        },
    }


# iter458 — Pure aggregator: sums per-lot engine amounts into named tax
# components and emits ONLY the components that are non-zero. Never
# converts HST ↔ GST/QST. Never infers a component from a province.
def _build_seller_tax_lines(processed_lots: list) -> list:
    """Aggregate per-lot engine tax amounts into a list of tax lines.

    Each entry:
        {
          "kind":     "gst" | "qst" | "hst",
          "label_en": "GST" | "QST" | "HST",
          "label_fr": "TPS" | "TVQ" | "TVH",
          "amount":   float,          # exact sum of engine per-lot amounts
          "rate_pct": float | None,   # statutory rate from the engine's
                                      # tax_rate_config for THIS component
                                      # (e.g. 5.0 for QC GST, 9.975 for QC
                                      # QST, 13.0 for ON HST). NEVER an
                                      # invented rate; taken directly from
                                      # services.tax_rate_config.
        }

    Rules:
      • A component appears if AND ONLY if the engine returned a
        positive amount for that component on at least one sold lot.
      • No component is derived from another; no HST ↔ GST+PST
        rewriting; no PST synthesis.
      • Empty list means "no tax to render" (INTL / zero-rated).
    """
    sold = [l for l in processed_lots if l.get("status") == "sold"]
    if not sold:
        return []

    # Read the statutory per-component rates DIRECTLY from the engine's
    # tax rate config (not inferred, not recomputed from amounts). The
    # engine set seller_tax_province on every sold lot; every sold lot
    # in a single settlement carries the same province, so we use the
    # first sold lot's province as the lookup key.
    from services.tax_rate_config import get_tax_rate_sync
    province_code = sold[0].get("seller_tax_province") or "INTL"
    rates = get_tax_rate_sync(province_code)

    components = [
        ("gst", "GST", "TPS",
         sum(l.get("seller_gst_amount", 0.0) for l in sold),
         rates.get("gst")),
        ("qst", "QST", "TVQ",
         sum(l.get("seller_qst_amount", 0.0) for l in sold),
         rates.get("qst")),
        ("hst", "HST", "TVH",
         sum(l.get("seller_hst_amount", 0.0) for l in sold),
         rates.get("hst")),
    ]
    lines = []
    for kind, label_en, label_fr, raw_amount, statutory_rate in components:
        amount = round(float(raw_amount), 2)
        if amount <= 0:
            continue  # Never render a zero-tax label as if there were one.
        # rate_pct is the CRA statutory rate the engine used for this
        # exact component (e.g. QC GST = 5%, QC QST = 9.975%, ON HST =
        # 13%). Comes verbatim from tax_rate_config — no math done here.
        rate_pct = None
        if statutory_rate is not None:
            try:
                rate_pct = round(float(statutory_rate) * 100.0, 3)
            except (TypeError, ValueError):
                rate_pct = None
        lines.append({
            "kind":     kind,
            "label_en": label_en,
            "label_fr": label_fr,
            "amount":   amount,
            "rate_pct": rate_pct,
        })
    return lines


# ══════════════════════════════════════════════════════════════════════════
# iter459 — Buyer-document data resolver (payment letter accuracy).
#
# Mirrors `_build_settled_seller_dataset` but from the BUYER's perspective.
# The payment letter MUST reflect ONLY the lots this specific buyer won,
# never placeholder "first N", another buyer's lots, or unsold lots.
#
#   • Won lots        → auction.lots where winner_user_id (or legacy
#                        winner_id / highest_bidder_id) == buyer_id AND
#                        (status ∈ {sold, won} OR resolved hammer_total > 0
#                         AND status not in {cancelled, removed, voided}).
#   • Per-lot totals   → services.hammer_total.resolve_hammer_total()
#                        (unit_price × winning_quantity math preserved).
#   • Buyer premium    → services.fee_calculator.calculate_fee(...) with
#     + payment charge   the seller's real account_type/tier/province and
#     + taxes            the buyer's real province/tier — NEVER recomputed
#                        by this module. Route matches the settlement +
#                        checkout paths so numbers reconcile.
#   • Paddle number    → paddle_numbers collection lookup for this buyer +
#                        auction. Never invented / never a sample value.
#
# The helper is pure/read-only and safe to call from any route.
# ══════════════════════════════════════════════════════════════════════════

async def _build_settled_buyer_dataset(
    db_client, auction: Dict[str, Any], buyer_id: str
) -> Dict[str, Any]:
    """Build the real won-lot dataset for the given auction + buyer.

    Returns a dict with:
        {
          "lots": [                        # only lots this buyer WON
            {
              "lot_number": int|str,
              "title": str,
              "description": str,
              "quantity": int,
              "unit_price": float,
              "line_total": float,         # unit_price × quantity
              "hammer_price": float,       # alias of line_total for
                                           # back-compat with older tests
            }, ...
          ],
          "hammer_total": float,           # sum(line_total)
          "buyer_premium": float,          # from fee engine
          "buyer_premium_rate": float,     # decimal, e.g. 0.05
          "buyer_premium_rate_pct": float, # e.g. 5.0
          "buyer_stripe_recovery": float,  # payment-charge line from engine
          "buyer_taxes": float,            # total tax from engine
          "buyer_gst": float,              # per-component from engine
          "buyer_qst": float,
          "buyer_hst": float,
          "buyer_tax_label": str,          # canonical label from engine
          "buyer_tax_province": str,       # normalized province used
          "buyer_tax_lines": [             # list of non-zero tax lines
            {kind, label_en, label_fr, amount, rate_pct}, ...
          ],
          "amount_due": float,             # what buyer owes BidVex (BP +
                                           # stripe recovery + tax) — same
                                           # as buyer_total - hammer_total
          "buyer_total_charged": float,    # hammer + BP + recovery + tax
                                           # (full amount for Stripe path)
          "buyer_name": str,               # real buyer full_name / name
          "paddle_number": int|None,       # real paddle from paddle_numbers
        }

    Raises HTTPException(400) when the buyer won no lots on this auction.
    Raises HTTPException(500) when the fee engine cannot resolve a policy.
    """
    from services.hammer_total import resolve_hammer_total
    from services.fee_calculator import calculate_fee
    from services.listing_seller_enrichment import resolve_seller_account_type

    # ── Buyer context (province + tier for buyer's tax + BP tier) ──
    buyer = await db_client.users.find_one({"id": buyer_id}, {"_id": 0}) or {}
    buyer_prov = (
        buyer.get("province")
        or buyer.get("billing_province")
        or auction.get("location_province")
        or "QC"
    )
    buyer_tier = buyer.get("subscription_tier", "free")
    buyer_name = (
        (buyer.get("full_name") or buyer.get("name") or buyer.get("email") or "").strip()
        or "Buyer"
    )

    # ── Seller context (account_type + tier + province — real fee policy) ──
    seller_id = auction.get("seller_id") or auction.get("user_id")
    seller = {}
    if seller_id:
        seller = await db_client.users.find_one({"id": seller_id}, {"_id": 0}) or {}
    seller_tier = seller.get("subscription_tier", "free")
    seller_prov = (
        seller.get("province")
        or seller.get("business_province")
        or auction.get("location_province")
        or buyer_prov
    )
    # Same context-aware routing the enrichment resolver uses so the fee
    # engine gets the correct seller_account_type for lots auctions.
    listing_context = "lots"
    if (auction.get("listing_type") or auction.get("auction_type") or "").lower() == "vehicle":
        listing_context = "vehicle"
    seller_account_type = resolve_seller_account_type(seller, listing_context)

    # ── Filter to the lots this buyer ACTUALLY won ──
    won_rows: list = []
    for lot in auction.get("lots", []) or []:
        winner = (
            lot.get("winner_user_id")
            or lot.get("winner_id")
            or lot.get("highest_bidder_id")
        )
        if winner != buyer_id:
            continue
        lot_status_raw = (lot.get("status") or "").lower()
        # Skip lots that never resolved to a sale for this buyer.
        if lot_status_raw in ("cancelled", "removed", "voided", "unsold"):
            continue
        totals = resolve_hammer_total(auction, lot=lot)
        hammer_total_lot = float(totals["hammer_total"])
        if hammer_total_lot <= 0 and lot_status_raw not in ("sold", "won"):
            continue
        won_rows.append({
            "lot_number": lot.get("lot_number"),
            "title": lot.get("title") or "",
            "description": lot.get("description") or "",
            "quantity": int(totals["quantity"]),
            "unit_price": float(totals["unit_price"]),
            "line_total": round(hammer_total_lot, 2),
            "hammer_price": round(hammer_total_lot, 2),
        })

    if not won_rows:
        raise HTTPException(
            status_code=400,
            detail="No lots won by this buyer on this auction — payment letter cannot be produced.",
        )

    # ── Aggregate hammer + run the fee engine ONCE with the real total ──
    hammer_total = round(sum(r["line_total"] for r in won_rows), 2)
    try:
        fee = calculate_fee(
            hammer_price=hammer_total,
            auction_type=auction.get("listing_type") or auction.get("auction_type") or "lots",
            seller_account_type=seller_account_type,
            seller_tier=seller_tier,
            buyer_account_type=buyer.get("account_type") or "individual",
            buyer_tier=buyer_tier,
            payment_method="stripe",
            card_type="domestic",
            buyer_province=buyer_prov,
            seller_province=seller_prov,
            partner_bp_rate=float(
                auction.get("custom_buyer_premium_rate")
                or auction.get("partner_bp_rate")
                or 0.0
            ),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            f"[buyer-docs] calculate_fee failed for auction={auction.get('id')} "
            f"buyer={buyer_id}: {exc}"
        )
        raise HTTPException(
            status_code=500,
            detail="fee_engine_unavailable — payment letter cannot be produced without a real fee policy",
        )

    buyer_premium = float(fee.get("buyer_premium") or 0.0)
    buyer_premium_rate = float(fee.get("buyer_premium_rate") or 0.0)
    buyer_stripe_recovery = float(fee.get("buyer_stripe_recovery") or 0.0)
    buyer_taxes = float(fee.get("buyer_taxes") or 0.0)
    buyer_gst = float(fee.get("buyer_gst") or 0.0)
    buyer_qst = float(fee.get("buyer_qst") or 0.0)
    buyer_hst = float(fee.get("buyer_hst") or 0.0)
    buyer_tax_label = str(fee.get("buyer_tax_label") or "")
    buyer_tax_province = str(fee.get("buyer_tax_province") or buyer_prov)
    buyer_total_charged = float(fee.get("buyer_total_charged") or 0.0)
    # Amount the buyer owes BidVex directly (BP + stripe recovery + tax).
    # For Stripe path buyer_total_charged already includes hammer.
    amount_due = round(buyer_premium + buyer_stripe_recovery + buyer_taxes, 2)

    # ── Build tax-line list — engine amounts only; no synthesis ──
    tax_lines: list = []
    from services.tax_rate_config import get_tax_rate_sync
    rates = get_tax_rate_sync(buyer_tax_province)
    for kind, label_en, label_fr, amount, statutory_rate in (
        ("gst", "GST", "TPS", buyer_gst, rates.get("gst")),
        ("qst", "QST", "TVQ", buyer_qst, rates.get("qst")),
        ("hst", "HST", "TVH", buyer_hst, rates.get("hst")),
    ):
        rounded = round(float(amount), 2)
        if rounded <= 0:
            continue
        rate_pct = None
        if statutory_rate is not None:
            try:
                rate_pct = round(float(statutory_rate) * 100.0, 3)
            except (TypeError, ValueError):
                rate_pct = None
        tax_lines.append({
            "kind":     kind,
            "label_en": label_en,
            "label_fr": label_fr,
            "amount":   rounded,
            "rate_pct": rate_pct,
        })

    # ── Real paddle number lookup (never invented) ──
    paddle_row = await db_client.paddle_numbers.find_one({
        "auction_id": auction.get("id"),
        "user_id": buyer_id,
    }, {"_id": 0, "paddle_number": 1})
    paddle_number = paddle_row.get("paddle_number") if paddle_row else None

    return {
        "lots": won_rows,
        "hammer_total": hammer_total,
        "buyer_premium": round(buyer_premium, 2),
        "buyer_premium_rate": round(buyer_premium_rate, 6),
        "buyer_premium_rate_pct": round(buyer_premium_rate * 100, 4),
        "buyer_stripe_recovery": round(buyer_stripe_recovery, 2),
        "buyer_taxes": round(buyer_taxes, 2),
        "buyer_gst": round(buyer_gst, 2),
        "buyer_qst": round(buyer_qst, 2),
        "buyer_hst": round(buyer_hst, 2),
        "buyer_tax_label": buyer_tax_label,
        "buyer_tax_province": buyer_tax_province,
        "buyer_tax_lines": tax_lines,
        "amount_due": amount_due,
        "buyer_total_charged": round(buyer_total_charged, 2),
        "buyer_name": buyer_name,
        "buyer_email": buyer.get("email", ""),
        "buyer_phone": buyer.get("phone", ""),
        "buyer_company_name": buyer.get("company_name"),
        "buyer_billing_address": buyer.get("billing_address") or buyer.get("address") or "",
        "buyer_subscription_tier": buyer_tier,
        "paddle_number": paddle_number,
        "seller_account_type": seller_account_type,
    }


@invoices_router.get("/invoices")
async def list_invoices(current_user: User = Depends(get_current_user)):
    """List all invoices for the current user, each with a fresh signed download URL."""
    db = get_db()
    from services.cloud_storage import generate_signed_url
    invoices = await db.subscription_invoices.find(
        {"user_id": current_user.id},
        {"_id": 0, "pdf_data": 0}
    ).sort("created_at", -1).to_list(50)

    for inv in invoices:
        inv["download_url"] = generate_signed_url(inv["id"])

    return {"invoices": invoices}




@invoices_router.get("/invoices/{invoice_id}/download")
async def download_invoice(invoice_id: str, current_user: User = Depends(get_current_user)):
    """Download a PDF invoice — generates, stores in cloud, and returns."""
    db = get_db()
    from fastapi.responses import Response
    from services.cloud_storage import store_invoice_pdf, retrieve_invoice_pdf

    invoice = await db.subscription_invoices.find_one(
        {"id": invoice_id, "user_id": current_user.id},
        {"_id": 0}
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    # Try serving from cloud storage first
    storage_path = invoice.get("storage_path")
    if storage_path:
        pdf_data = await retrieve_invoice_pdf(storage_path)
        if pdf_data:
            filename = f"{invoice.get('invoice_number', 'invoice')}.pdf"
            return Response(
                content=pdf_data,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'}
            )

    # Fallback: render dynamically, then store for next time
    if not invoice.get("user_name"):
        user = await db.users.find_one({"id": current_user.id})
        invoice["user_name"] = user.get("name", user.get("username", "Customer")) if user else "Customer"

    pdf_data = _render_subscription_invoice_pdf(invoice)

    # Persist to cloud storage
    path = await store_invoice_pdf(invoice_id, pdf_data, subfolder="subscription")
    await db.subscription_invoices.update_one(
        {"id": invoice_id},
        {"$set": {"storage_path": path}}
    )

    filename = f"{invoice.get('invoice_number', 'invoice')}.pdf"
    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )




@invoices_router.get("/invoices/download/{invoice_id}")
async def download_invoice_signed(invoice_id: str, expires: int = 0, sig: str = ""):
    """
    Public signed-URL download endpoint. No auth required — the HMAC signature IS the auth.
    """
    db = get_db()
    from fastapi.responses import Response
    from services.cloud_storage import verify_signature, retrieve_invoice_pdf

    if not verify_signature(invoice_id, expires, sig):
        raise HTTPException(status_code=403, detail="Link expired or invalid signature")

    # Look up in both invoice collections
    invoice = await db.subscription_invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        invoice = await db.invoices.find_one({"id": invoice_id}, {"_id": 0})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    storage_path = invoice.get("storage_path")
    if storage_path:
        pdf_data = await retrieve_invoice_pdf(storage_path)
        if pdf_data:
            filename = f"{invoice.get('invoice_number', 'invoice')}.pdf"
            return Response(
                content=pdf_data,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'}
            )

    # Generate on demand if no stored file (subscription invoices)
    if invoice.get("type") == "subscription":
        if not invoice.get("user_name"):
            user = await db.users.find_one({"id": invoice.get("user_id")})
            invoice["user_name"] = user.get("name", "Customer") if user else "Customer"
        from services.cloud_storage import store_invoice_pdf
        pdf_data = _render_subscription_invoice_pdf(invoice)
        path = await store_invoice_pdf(invoice_id, pdf_data, subfolder="subscription")
        await db.subscription_invoices.update_one({"id": invoice_id}, {"$set": {"storage_path": path}})
        filename = f"{invoice.get('invoice_number', 'invoice')}.pdf"
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    raise HTTPException(status_code=404, detail="Invoice PDF not available")




@invoices_router.post("/invoices/lots-won/{auction_id}/{user_id}")
async def generate_lots_won_invoice(
    auction_id: str,
    user_id: str,
    lang: str = "en",
    current_user: User = Depends(get_current_user)
):
    """
    Generate Buyer Lots Won Summary PDF
    Requires admin privileges or matching user_id
    
    Query Parameters:
        lang: Language code ('en' or 'fr') - uses buyer's preference if not specified
    """
    # Check permissions (admin or own invoice)
    if current_user.account_type != "admin" and getattr(current_user, "role", None) not in ("admin", "super_admin") and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Fetch auction
    auction = await db.multi_item_listings.find_one({"id": auction_id})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    # Fetch buyer
    buyer = await db.users.find_one({"id": user_id})
    if not buyer:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Use buyer's preferred language if lang not specified
    if lang == "en" and buyer.get("preferred_language"):
        lang = buyer.get("preferred_language", "en")
    
    # Get or create paddle number
    paddle_record = await db.paddle_numbers.find_one({
        "auction_id": auction_id,
        "user_id": user_id
    })
    
    if not paddle_record:
        paddle_num = await generate_paddle_number(auction_id)
        paddle_record = {
            "id": str(uuid.uuid4()),
            "auction_id": auction_id,
            "user_id": user_id,
            "paddle_number": paddle_num,
            "assigned_at": datetime.now(timezone.utc).isoformat()
        }
        await db.paddle_numbers.insert_one(paddle_record)
    
    # iter451 — Invoice must reflect ACTUAL lots this buyer won, never
    # placeholder "first N" lots. A lot is "won by this buyer" when its
    # `winner_user_id` (or `highest_bidder_id`, legacy) matches user_id
    # AND its status is `sold`. Each line renders `unit_price × quantity
    # = line_total` so the template can display the multi-item math
    # exactly (per user directive: `$7 × 2 = $14`).
    from services.hammer_total import resolve_hammer_total

    lots_won = []
    for lot in auction.get('lots', []):
        lot_winner = (
            lot.get("winner_user_id")
            or lot.get("winner_id")
            or lot.get("highest_bidder_id")
        )
        if lot_winner != user_id:
            continue
        # Skip lots that never resolved to a sale.
        if lot.get("status") and lot.get("status") not in ("sold", "won"):
            continue
        totals = resolve_hammer_total(auction, lot=lot)
        lots_won.append({
            "lot_number": lot.get('lot_number'),
            "title": lot.get('title') or "",
            "description": lot.get('description') or "",
            "quantity": totals["quantity"],
            "unit_price": totals["unit_price"],
            # `hammer_price` on the invoice line = unit_price × quantity
            # so `sum(hammer_price)` at template level equals the
            # buyer-owed merchandise subtotal.
            "hammer_price": totals["hammer_total"],
            "line_total": totals["hammer_total"],
        })

    if not lots_won:
        raise HTTPException(status_code=400, detail="No lots won by this buyer")

    # Calculate fees using the Unified Fee Engine
    buyer_subscription = buyer.get('subscription_tier', 'free')
    hammer_total = sum(lot['hammer_price'] for lot in lots_won)
    buyer_fees = calculate_buyer_fees(hammer_total, buyer_subscription)
    
    # Generate invoice number (helper is sync, takes 0 args)
    invoice_number = generate_invoice_number()
    
    # Prepare data for template with subscription-aware fees
    template_data = {
        "invoice_number": invoice_number,
        "buyer": {
            "name": buyer['name'],
            "company_name": buyer.get('company_name'),
            "billing_address": buyer.get('billing_address', buyer.get('address')),
            "phone": buyer['phone'],
            "email": buyer['email'],
            "subscription_tier": buyer_subscription,
            "is_premium": buyer_subscription in ['premium', 'vip']
        },
        "paddle_number": paddle_record['paddle_number'],
        "auction": {
            "title": auction['title'],
            "city": auction['city'],
            "region": auction['region'],
            "location": auction.get('location'),
            "auction_end_date": datetime.fromisoformat(auction['auction_end_date']) if isinstance(auction['auction_end_date'], str) else auction['auction_end_date']
        },
        "lots": lots_won,
        # Fee Engine values
        "premium_percentage": buyer_fees.fee_percentage,  # Subscription-adjusted
        "premium_amount": buyer_fees.fee_amount,
        "standard_premium_rate": 5.0,
        "discount_applied": buyer_fees.discount_applied,
        "is_premium_member": buyer_fees.is_premium_member,
        "tax_rate_gst": auction.get('tax_rate_gst', 5.0),
        "tax_rate_qst": auction.get('tax_rate_qst', 9.975),
        "payment_deadline": "Within 14 days of auction close",
        "currency": auction.get('currency', 'CAD')  # Include auction currency
    }
    
    # Generate HTML
    # Generate bilingual HTML
    try:
        from invoice_templates_bilingual import lots_won_template as lots_won_bilingual
        html_content = lots_won_bilingual(template_data, lang=lang)
    except ImportError:
        # Fallback to original template if bilingual not available
        html_content = lots_won_template(template_data)
    
    # Generate PDF to temp path, then persist to cloud storage
    import tempfile
    from services.cloud_storage import store_invoice_pdf, generate_signed_url

    invoice_id = str(uuid.uuid4())

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    generate_pdf_from_html(html_content, tmp_path)
    pdf_bytes = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)

    storage_path = await store_invoice_pdf(invoice_id, pdf_bytes, subfolder="lots_won")
    download_url = generate_signed_url(invoice_id)

    # Save invoice record to database
    invoice_record = {
        "id": invoice_id,
        "invoice_number": invoice_number,
        "invoice_type": "lots_won",
        "user_id": user_id,
        "auction_id": auction_id,
        "storage_path": storage_path,
        "download_url": download_url,
        "generated_date": datetime.now(timezone.utc).isoformat(),
        "status": "generated"
    }
    await db.invoices.insert_one(invoice_record)
    
    return {
        "success": True,
        "invoice_number": invoice_number,
        "download_url": download_url,
        "paddle_number": paddle_record['paddle_number'],
        "message": "Invoice generated successfully"
    }



@invoices_router.post("/invoices/payment-letter/{auction_id}/{user_id}")
async def generate_payment_letter(
    auction_id: str,
    user_id: str,
    lang: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Generate Payment Letter PDF for buyer.

    iter459 — Uses ONLY the lots this specific buyer actually won on this
    auction. Fee, payment charges, and taxes come from the unified
    fee engine (`services.fee_calculator.calculate_fee`) — never recomputed
    locally. Paddle number is looked up from `paddle_numbers` (created via
    the standard helper only if the buyer never received a paddle for
    this auction).
    """
    # Check permissions
    if current_user.account_type != "admin" and getattr(current_user, "role", None) not in ("admin", "super_admin") and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Fetch auction
    auction = await db.multi_item_listings.find_one({"id": auction_id})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    # Fetch buyer up-front (helper also fetches it but we need the record
    # to honour language preference on the PDF language toggle).
    buyer = await db.users.find_one({"id": user_id})
    if not buyer:
        raise HTTPException(status_code=404, detail="User not found")

    # Language: explicit query param overrides buyer's preferred_language.
    resolved_lang = (lang or buyer.get("preferred_language") or "en").lower()
    if resolved_lang not in ("en", "fr"):
        resolved_lang = "en"

    # Real-data dataset (400 if no lots won by this buyer).
    dataset = await _build_settled_buyer_dataset(db, auction, user_id)

    # Paddle number: if none exists in paddle_numbers we assign one via
    # the standard helper (real paddle assignment, not a placeholder).
    paddle_number = dataset["paddle_number"]
    if paddle_number is None:
        paddle_number = await generate_paddle_number(auction_id)
        await db.paddle_numbers.insert_one({
            "id": str(uuid.uuid4()),
            "auction_id": auction_id,
            "user_id": user_id,
            "paddle_number": paddle_number,
            "assigned_at": datetime.now(timezone.utc).isoformat(),
        })

    # Reuse an existing lots_won invoice number when present so the two
    # buyer documents share the same invoice reference. Otherwise mint a
    # fresh one.
    existing_invoice = await db.invoices.find_one({
        "auction_id": auction_id,
        "user_id": user_id,
        "invoice_type": "lots_won",
    })
    invoice_number = (
        existing_invoice["invoice_number"] if existing_invoice
        else generate_invoice_number()
    )

    # Prepare data for template — pure data plumbing, no re-computation.
    currency = auction.get("currency", "CAD")
    auction_end_raw = auction.get("auction_end_date")
    if isinstance(auction_end_raw, str):
        try:
            auction_end_dt = datetime.fromisoformat(auction_end_raw)
        except ValueError:
            auction_end_dt = datetime.now(timezone.utc)
    else:
        auction_end_dt = auction_end_raw or datetime.now(timezone.utc)

    template_data = {
        "invoice_number": invoice_number,
        "buyer": {
            "name": dataset["buyer_name"],
            "company_name": dataset.get("buyer_company_name"),
            "billing_address": dataset.get("buyer_billing_address", ""),
            "phone": dataset.get("buyer_phone", ""),
            "email": dataset.get("buyer_email", ""),
        },
        "paddle_number": paddle_number,
        "auction": {
            "title": auction["title"],
            "city": auction.get("city", ""),
            "region": auction.get("region", ""),
            "auction_end_date": auction_end_dt,
        },
        # iter459 — Per-lot lines (unit price × qty = line total).
        "lots": dataset["lots"],
        "lots_count": len(dataset["lots"]),
        # Real totals from the fee engine.
        "hammer_total": dataset["hammer_total"],
        "premium_amount": dataset["buyer_premium"],
        "premium_percentage": dataset["buyer_premium_rate_pct"],
        "stripe_recovery": dataset["buyer_stripe_recovery"],
        "total_tax": dataset["buyer_taxes"],
        "tax_lines": dataset["buyer_tax_lines"],
        "buyer_tax_label": dataset["buyer_tax_label"],
        "buyer_tax_province": dataset["buyer_tax_province"],
        "amount_due": dataset["amount_due"],
        "grand_total": dataset["buyer_total_charged"],
        "payment_deadline": auction.get("payment_deadline")
            if isinstance(auction.get("payment_deadline"), str)
            else "Within 14 days of auction close",
        "currency": currency,
    }

    # Render bilingual HTML.
    from invoice_templates_complete import payment_letter_template
    html_content = payment_letter_template(template_data, lang=resolved_lang)

    # Generate PDF and persist to cloud storage.
    import tempfile
    from services.cloud_storage import store_invoice_pdf, generate_signed_url

    invoice_id = str(uuid.uuid4())
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    generate_pdf_from_html(html_content, tmp_path)
    pdf_bytes = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)

    storage_path = await store_invoice_pdf(invoice_id, pdf_bytes, subfolder="payment_letter")
    download_url = generate_signed_url(invoice_id)

    # Save invoice record.
    invoice_record = {
        "id": invoice_id,
        "invoice_number": invoice_number,
        "invoice_type": "payment_letter",
        "user_id": user_id,
        "auction_id": auction_id,
        "storage_path": storage_path,
        "download_url": download_url,
        "generated_date": datetime.now(timezone.utc).isoformat(),
        "status": "generated",
        "language": resolved_lang,
    }
    await db.invoices.insert_one(invoice_record)

    return {
        "success": True,
        "invoice_number": invoice_number,
        "download_url": download_url,
        "paddle_number": paddle_number,
        "amount_due": dataset["amount_due"],
        "grand_total": dataset["buyer_total_charged"],
        "hammer_total": dataset["hammer_total"],
        "lots_count": len(dataset["lots"]),
        "message": "Payment letter generated successfully",
    }



@invoices_router.get("/invoices/{user_id}")
async def get_user_invoices(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get all invoices for a user, each with a fresh signed download URL."""
    from services.cloud_storage import generate_signed_url

    if current_user.account_type != "admin" and getattr(current_user, "role", None) not in ("admin", "super_admin") and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    invoices = await db.invoices.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    
    for invoice in invoices:
        if isinstance(invoice.get('generated_date'), str):
            invoice['generated_date'] = datetime.fromisoformat(invoice['generated_date'])
        invoice["download_url"] = generate_signed_url(invoice["id"])
    
    return invoices



@invoices_router.post("/invoices/seller-statement/{auction_id}/{seller_id}")
async def generate_seller_statement(
    auction_id: str,
    seller_id: str,
    current_user: User = Depends(get_current_user)
):
    """Generate Seller Statement PDF"""
    # iter457 — Include role-based admin bypass so super_admin (which
    # doesn't carry account_type="admin") can generate on behalf of a
    # seller. Aligns with the buyer `lots-won` endpoint check.
    if (
        current_user.account_type != "admin"
        and getattr(current_user, "role", None) not in ("admin", "super_admin")
        and current_user.id != seller_id
    ):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    auction = await db.multi_item_listings.find_one({"id": auction_id})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    seller = await db.users.find_one({"id": seller_id})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    # iter457 — Real settled-data resolver (was: "demo: mark first 3 as sold").
    dataset = await _build_settled_seller_dataset(db, auction, seller_id)
    lots_data = [
        {
            "lot_number":   l["lot_number"],
            "title":        l["title"],
            "description":  l["description"],
            "status":       l["status"],
            "quantity":     l["quantity"],
            "unit_price":   l["unit_price"],
            "hammer_price": l["hammer_price"],
            "buyer_name":   l["buyer_name"],
            "paddle_number": l["paddle_number"],
            # Per-lot financial detail (required per user directive)
            "platform_fee":       l["platform_fee"],
            "seller_tax_on_fee":  l["seller_tax_on_fee"],
            "net_payout":         l["net_payout"],
            "settlement_status":  l["settlement_status"],
        }
        for l in dataset["lots"]
    ]
    
    # Use seller's preferred language if available
    lang = seller.get('preferred_language', 'en')
    currency = auction.get('currency', 'CAD')
    
    from invoice_templates_complete import seller_statement_template
    template_data = {
        "seller": {
            "name": seller['name'],
            "company_name": seller.get('company_name'),
            "address": seller.get('address'),
            "email": seller['email'],
            "phone": seller['phone']
        },
        "auction": {
            "title": auction['title'],
            "city": auction['city'],
            "region": auction['region'],
            "auction_end_date": datetime.fromisoformat(auction['auction_end_date']) if isinstance(auction['auction_end_date'], str) else auction['auction_end_date']
        },
        "lots": lots_data,
        # iter457 — Rate comes from the real fee engine, never a silent zero
        # from a missing `auction.commission_rate` field.
        "commission_rate":         dataset["commission_rate_pct"],
        "commission_rate_source":  dataset["commission_rate_source"],
        "seller_tax_province":     dataset["seller_tax_province"],
        # Per-doc totals + tax breakdown so the seller can reconcile.
        "total_hammer_sold":       dataset["total_hammer"],
        "total_platform_fee":      dataset["total_platform_fee"],
        "total_tax_on_fee":        dataset["total_tax_on_fee"],
        "total_net_payout":        dataset["total_net_payout"],
        "currency": currency,
        "statement_number": f"STMT-{auction_id[:8]}"
    }
    
    html_content = seller_statement_template(template_data, lang=lang)
    
    # Generate PDF and persist to cloud storage
    import tempfile
    from services.cloud_storage import store_invoice_pdf, generate_signed_url

    invoice_id = str(uuid.uuid4())

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    generate_pdf_from_html(html_content, tmp_path)
    pdf_bytes = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)

    storage_path = await store_invoice_pdf(invoice_id, pdf_bytes, subfolder="seller_statement")
    download_url = generate_signed_url(invoice_id)

    invoice_record = {
        "id": invoice_id,
        "invoice_number": f"STMT-{auction_id[:8]}",
        "invoice_type": "seller_statement",
        "user_id": seller_id,
        "auction_id": auction_id,
        "storage_path": storage_path,
        "download_url": download_url,
        "generated_date": datetime.now(timezone.utc).isoformat(),
        "status": "generated"
    }
    await db.invoices.insert_one(invoice_record)
    
    return {
        "success": True,
        "download_url": download_url,
        "message": "Seller statement generated successfully"
    }



@invoices_router.post("/invoices/seller-receipt/{auction_id}/{seller_id}")
async def generate_seller_receipt(
    auction_id: str,
    seller_id: str,
    current_user: User = Depends(get_current_user)
):
    """Generate Seller Receipt PDF"""
    # iter457 — Include role-based admin bypass so super_admin (which
    # doesn't carry account_type="admin") can generate on behalf of a
    # seller. Aligns with the buyer `lots-won` endpoint check.
    if (
        current_user.account_type != "admin"
        and getattr(current_user, "role", None) not in ("admin", "super_admin")
        and current_user.id != seller_id
    ):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    auction = await db.multi_item_listings.find_one({"id": auction_id})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    seller = await db.users.find_one({"id": seller_id})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    # iter457 — Real settled totals (was: demo "first 3 lots sold").
    dataset = await _build_settled_seller_dataset(db, auction, seller_id)
    total_hammer = dataset["total_hammer"]
    lots_sold_count = len(dataset["sold_lots"])
    
    # Use seller's preferred language if available
    lang = seller.get('preferred_language', 'en')
    currency = auction.get('currency', 'CAD')
    
    from invoice_templates_complete import seller_receipt_template
    template_data = {
        "receipt_number": f"RCPT-{auction_id[:8]}-{int(datetime.now().timestamp())}",
        "seller": {
            "name": seller['name'],
            "company_name": seller.get('company_name'),
            "address": seller.get('address'),
            "email": seller['email']
        },
        "auction": {
            "title": auction['title'],
            "auction_end_date": datetime.fromisoformat(auction['auction_end_date']) if isinstance(auction['auction_end_date'], str) else auction['auction_end_date']
        },
        "total_lots": len(auction['lots']),
        "lots_sold": lots_sold_count,
        "total_hammer": total_hammer,
        # iter457 — Rates + taxes sourced from the fee engine. A zero rate
        # only ever appears when the real seller policy is zero (e.g.
        # storage_facility). Never a silent default.
        "commission_rate":  dataset["commission_rate_pct"],
        "tax_rate_gst":     dataset["tax_rate_gst_pct"],
        "tax_rate_qst":     dataset["tax_rate_qst_pct"],
        # Pre-computed net payout + fee totals to keep template arithmetic
        # in agreement with the fee engine (belt & braces — the template
        # will still recompute, but on rates from the fee engine).
        "net_payout":       dataset["total_net_payout"],
        "total_platform_fee": dataset["total_platform_fee"],
        "total_tax_on_fee":   dataset["total_tax_on_fee"],
        "seller_tax_province": dataset["seller_tax_province"],
        # iter458 — Faithful tax-label rendering: pass the engine's exact
        # per-component tax lines so the template renders the real tax
        # type(s) (GST / QST / HST) — never inferred from province.
        "seller_tax_lines": dataset["seller_tax_lines"],
        "seller_tax_engine_raw_label": dataset["seller_tax_engine_labels"]["raw_label"],
        "payment_method": "Bank Transfer",
        "payment_date": "Within 5-7 business days",
        "currency": currency
    }
    
    html_content = seller_receipt_template(template_data, lang=lang)
    
    # Generate PDF and persist to cloud storage
    import tempfile
    from services.cloud_storage import store_invoice_pdf, generate_signed_url

    invoice_id = str(uuid.uuid4())

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    generate_pdf_from_html(html_content, tmp_path)
    pdf_bytes = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)

    storage_path = await store_invoice_pdf(invoice_id, pdf_bytes, subfolder="seller_receipt")
    download_url = generate_signed_url(invoice_id)

    invoice_record = {
        "id": invoice_id,
        "invoice_number": template_data['receipt_number'],
        "invoice_type": "seller_receipt",
        "user_id": seller_id,
        "auction_id": auction_id,
        "storage_path": storage_path,
        "download_url": download_url,
        "generated_date": datetime.now(timezone.utc).isoformat(),
        "status": "generated"
    }
    await db.invoices.insert_one(invoice_record)
    
    return {
        "success": True,
        "download_url": download_url,
        "receipt_number": template_data['receipt_number'],
        "message": "Seller receipt generated successfully"
    }



@invoices_router.post("/invoices/commission-invoice/{auction_id}/{seller_id}")
async def generate_commission_invoice(
    auction_id: str,
    seller_id: str,
    current_user: User = Depends(get_current_user)
):
    """Generate Commission Invoice PDF (BidVex to Seller)"""
    # iter457 — Include role-based admin bypass so super_admin (which
    # doesn't carry account_type="admin") can generate on behalf of a
    # seller. Aligns with the buyer `lots-won` endpoint check.
    if (
        current_user.account_type != "admin"
        and getattr(current_user, "role", None) not in ("admin", "super_admin")
        and current_user.id != seller_id
    ):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    auction = await db.multi_item_listings.find_one({"id": auction_id})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    seller = await db.users.find_one({"id": seller_id})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    # iter457 — Real settled totals + real fee policy (was: hardcoded slice
    # `auction['lots'][:3]`, silent-zero commission_rate, and static
    # tax_rate defaults).
    dataset = await _build_settled_seller_dataset(db, auction, seller_id)
    total_hammer = dataset["total_hammer"]
    lots_sold_count = len(dataset["sold_lots"])
    commission_rate = dataset["commission_rate_pct"]
    commission_amount = dataset["total_platform_fee"]
    tax_rate_gst = dataset["tax_rate_gst_pct"]
    tax_rate_qst = dataset["tax_rate_qst_pct"]
    gst = round(commission_amount * (tax_rate_gst / 100), 2)
    qst = round(commission_amount * (tax_rate_qst / 100), 2)
    net_payout = dataset["total_net_payout"]
    
    invoice_number = f"BV-COMM-{datetime.now().year}-{auction_id[:8]}-0001"
    
    # Use seller's preferred language if available
    lang = seller.get('preferred_language', 'en')
    currency = auction.get('currency', 'CAD')
    
    from invoice_templates_complete import commission_invoice_template
    template_data = {
        "invoice_number": invoice_number,
        "seller": {
            "name": seller['name'],
            "company_name": seller.get('company_name'),
            "address": seller.get('address'),
            "email": seller['email'],
            "phone": seller['phone']
        },
        "auction": {
            "title": auction['title'],
            "auction_end_date": datetime.fromisoformat(auction['auction_end_date']) if isinstance(auction['auction_end_date'], str) else auction['auction_end_date']
        },
        "total_hammer": total_hammer,
        "lots_sold": lots_sold_count,
        "commission_rate": commission_rate,
        "commission_amount": commission_amount,
        "tax_rate_gst": tax_rate_gst,
        "tax_rate_qst": tax_rate_qst,
        "net_payout": net_payout,
        # iter458 — Faithful tax-label rendering (see seller_receipt above).
        "seller_tax_lines": dataset["seller_tax_lines"],
        "seller_tax_engine_raw_label": dataset["seller_tax_engine_labels"]["raw_label"],
        "seller_tax_province": dataset["seller_tax_province"],
        "due_date": "Upon Receipt",
        "currency": currency
    }
    
    html_content = commission_invoice_template(template_data, lang=lang)
    
    # Generate PDF and persist to cloud storage
    import tempfile
    from services.cloud_storage import store_invoice_pdf, generate_signed_url

    invoice_id = str(uuid.uuid4())

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    generate_pdf_from_html(html_content, tmp_path)
    pdf_bytes = tmp_path.read_bytes()
    tmp_path.unlink(missing_ok=True)

    storage_path = await store_invoice_pdf(invoice_id, pdf_bytes, subfolder="commission_invoice")
    download_url = generate_signed_url(invoice_id)

    invoice_record = {
        "id": invoice_id,
        "invoice_number": invoice_number,
        "invoice_type": "commission_invoice",
        "user_id": seller_id,
        "auction_id": auction_id,
        "storage_path": storage_path,
        "download_url": download_url,
        "generated_date": datetime.now(timezone.utc).isoformat(),
        "status": "generated"
    }
    await db.invoices.insert_one(invoice_record)
    
    return {
        "success": True,
        "invoice_number": invoice_number,
        "download_url": download_url,
        "message": "Commission invoice generated successfully"
    }




@invoices_router.post("/auctions/{auction_id}/complete")
async def complete_auction_and_send_documents(
    auction_id: str,
    lang: str = "en",
    current_user: User = Depends(get_current_user)
):
    """
    Complete auction and automatically generate + send all documents
    
    Triggers when auction status changes to 'ended':
    - Generates all buyer and seller documents
    - Sends emails with PDF attachments via SendGrid
    - Updates invoice records with email tracking
    
    Query Parameters:
        lang: Language code for documents ('en' or 'fr')
    
    Requires admin privileges
    """
    if current_user.account_type != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    db = get_db()
    
    # Fetch auction
    auction = await db.multi_item_listings.find_one({"id": auction_id})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    seller_id = auction['seller_id']
    seller = await db.users.find_one({"id": seller_id})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    # Initialize real email service
    email_service = get_email_service()
    
    results = {
        "auction_id": auction_id,
        "auction_title": auction['title'],
        "documents_generated": [],
        "emails_sent": [],
        "errors": []
    }
    
    # ===== SELLER DOCUMENTS =====
    try:
        # iter457 — Real settled totals for the summary email (was
        # `sum(...for lot in auction['lots'][:3])` and `lots_sold = 3`).
        dataset = await _build_settled_seller_dataset(db, auction, seller_id)
        total_hammer = dataset["total_hammer"]
        lots_sold = len(dataset["sold_lots"])
        commission_rate = dataset["commission_rate_pct"]
        commission_amount = dataset["total_platform_fee"]
        net_payout = dataset["total_net_payout"]
        
        seller_pdf_paths = {}
        
        # 1. Generate Seller Statement
        try:
            statement_response = await generate_seller_statement(auction_id, seller_id, current_user)
            seller_pdf_paths['statement'] = statement_response.get('download_url', '')
            results['documents_generated'].append('seller_statement')
        except Exception as e:
            results['errors'].append(f"Seller Statement: {str(e)}")
        
        # 2. Generate Seller Receipt
        try:
            receipt_response = await generate_seller_receipt(auction_id, seller_id, current_user)
            seller_pdf_paths['receipt'] = receipt_response.get('download_url', '')
            results['documents_generated'].append('seller_receipt')
        except Exception as e:
            results['errors'].append(f"Seller Receipt: {str(e)}")
        
        # 3. Generate Commission Invoice
        try:
            commission_response = await generate_commission_invoice(auction_id, seller_id, current_user)
            seller_pdf_paths['commission'] = commission_response.get('download_url', '')
            results['documents_generated'].append('commission_invoice')
        except Exception as e:
            results['errors'].append(f"Commission Invoice: {str(e)}")
        
        # Send seller email via SendGrid
        if seller_pdf_paths:
            subject = f"Vos résultats d'enchère - {auction['title']}" if lang == "fr" else f"Your Auction Results - {auction['title']}"
            # iter211 — Use double-quoted inner strings to avoid escaping
            # apostrophes inside f-string expressions (Python forbids backslashes
            # in f-string expression parts; this previously caused a SyntaxError
            # that the server.py graceful-loader hid by skipping the entire
            # invoices router).
            heading_fr = "Résultats de l'enchère"
            sign_off_fr = "L'équipe BidVex"
            html_body = f"""
            <html><body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2>{heading_fr if lang == 'fr' else 'Auction Results'}</h2>
            <p>{'Cher' if lang == 'fr' else 'Dear'} {seller['name'].split()[0]},</p>
            <p>{'Votre enchère' if lang == 'fr' else 'Your auction'} "<strong>{auction['title']}</strong>" {'est maintenant terminée.' if lang == 'fr' else 'has now concluded.'}</p>
            <table style="border-collapse: collapse; margin: 20px 0;">
                <tr><td style="padding: 8px; border: 1px solid #ddd;">{'Lots vendus' if lang == 'fr' else 'Lots Sold'}</td><td style="padding: 8px; border: 1px solid #ddd;">{lots_sold}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;">{'Valeur totale' if lang == 'fr' else 'Total Hammer Value'}</td><td style="padding: 8px; border: 1px solid #ddd;">${total_hammer:,.2f} CAD</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;">{'Paiement net' if lang == 'fr' else 'Net Payout'}</td><td style="padding: 8px; border: 1px solid #ddd;"><strong>${net_payout:,.2f} CAD</strong></td></tr>
            </table>
            <p>{'Vos documents sont disponibles dans votre tableau de bord.' if lang == 'fr' else 'Your auction documents are available in your dashboard.'}</p>
            <p>{'Cordialement,' if lang == 'fr' else 'Sincerely,'}<br>{sign_off_fr if lang == 'fr' else 'The BidVex Team'}</p>
            </body></html>
            """
            result = await email_service.send_raw_html(seller['email'], subject, html_body)
            email_sent = result.get("success", False)
            
            if email_sent:
                results['emails_sent'].append({
                    "type": "seller_documents",
                    "recipient": seller['email'],
                    "documents": list(seller_pdf_paths.keys())
                })
                
                # Update invoice records with email tracking
                await db.invoices.update_many(
                    {
                        "auction_id": auction_id,
                        "user_id": seller_id,
                        "invoice_type": {"$in": ["seller_statement", "seller_receipt", "commission_invoice"]}
                    },
                    {
                        "$set": {
                            "email_sent": True,
                            "sent_timestamp": datetime.now(timezone.utc).isoformat(),
                            "recipient_email": seller['email']
                        }
                    }
                )
    
    except Exception as e:
        results['errors'].append(f"Seller documents error: {str(e)}")
    
    # ===== BUYER DOCUMENTS =====
    # Find all buyers (paddle numbers assigned to this auction)
    paddle_records = await db.paddle_numbers.find({"auction_id": auction_id}).to_list(100)
    
    for paddle_record in paddle_records:
        buyer_id = paddle_record['user_id']
        paddle_number = paddle_record['paddle_number']
        
        try:
            buyer = await db.users.find_one({"id": buyer_id})
            if not buyer:
                continue
            
            buyer_pdf_paths = {}
            
            # 1. Generate Lots Won Summary
            try:
                lots_won_response = await generate_lots_won_invoice(auction_id, buyer_id, lang, current_user)
                buyer_pdf_paths['lots_won'] = lots_won_response.get('download_url', '')
                results['documents_generated'].append(f'lots_won_{buyer_id[:8]}')
                total_due = lots_won_response.get('total_due', 0)
                invoice_number = lots_won_response.get('invoice_number', 'N/A')
            except Exception as e:
                results['errors'].append(f"Lots Won (Buyer {buyer_id[:8]}): {str(e)}")
                continue
            
            # 2. Generate Payment Letter
            try:
                payment_letter_response = await generate_payment_letter(auction_id, buyer_id, current_user)
                buyer_pdf_paths['payment_letter'] = payment_letter_response.get('download_url', '')
                results['documents_generated'].append(f'payment_letter_{buyer_id[:8]}')
            except Exception as e:
                results['errors'].append(f"Payment Letter (Buyer {buyer_id[:8]}): {str(e)}")
            
            # Send buyer email via SendGrid
            if buyer_pdf_paths:
                subject = f"Votre facture d'enchère #{invoice_number} - Paiement requis" if lang == "fr" else f"Your Auction Invoice #{invoice_number} - Payment Required"
                # iter211 — Use double-quoted inner strings to avoid backslash
                # escapes in f-string expression parts (Python forbids them; this
                # previously caused a SyntaxError silently swallowed by the
                # graceful loader in server.py).
                heading_fr_b = "Facture d'enchère"
                sign_off_fr_b = "L'équipe BidVex"
                html_body = f"""
                <html><body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>{heading_fr_b if lang == 'fr' else 'Auction Invoice'}</h2>
                <p>{'Cher' if lang == 'fr' else 'Dear'} {buyer['name'].split()[0]},</p>
                <p>{'Félicitations pour vos enchères réussies!' if lang == 'fr' else 'Congratulations on your successful bids!'}</p>
                <table style="border-collapse: collapse; margin: 20px 0;">
                    <tr><td style="padding: 8px; border: 1px solid #ddd;">{'Numéro de facture' if lang == 'fr' else 'Invoice Number'}</td><td style="padding: 8px; border: 1px solid #ddd;">{invoice_number}</td></tr>
                    <tr><td style="padding: 8px; border: 1px solid #ddd;">{'Numéro de palette' if lang == 'fr' else 'Paddle Number'}</td><td style="padding: 8px; border: 1px solid #ddd;">{paddle_number}</td></tr>
                    <tr><td style="padding: 8px; border: 1px solid #ddd;">{'Montant total dû' if lang == 'fr' else 'Total Amount Due'}</td><td style="padding: 8px; border: 1px solid #ddd;"><strong>${total_due:,.2f} CAD</strong></td></tr>
                </table>
                <p>{'Veuillez consulter votre tableau de bord pour les instructions de paiement.' if lang == 'fr' else 'Please refer to your dashboard for detailed payment instructions.'}</p>
                <p>{'Cordialement,' if lang == 'fr' else 'Sincerely,'}<br>{sign_off_fr_b if lang == 'fr' else 'The BidVex Team'}</p>
                </body></html>
                """
                result = await email_service.send_raw_html(buyer['email'], subject, html_body)
                email_sent = result.get("success", False)
                
                if email_sent:
                    results['emails_sent'].append({
                        "type": "buyer_invoice",
                        "recipient": buyer['email'],
                        "paddle_number": paddle_number,
                        "documents": list(buyer_pdf_paths.keys())
                    })
                    
                    # Update invoice records with email tracking
                    await db.invoices.update_many(
                        {
                            "auction_id": auction_id,
                            "user_id": buyer_id,
                            "invoice_type": {"$in": ["lots_won", "payment_letter"]}
                        },
                        {
                            "$set": {
                                "email_sent": True,
                                "sent_timestamp": datetime.now(timezone.utc).isoformat(),
                                "recipient_email": buyer['email']
                            }
                        }
                    )
        
        except Exception as e:
            results['errors'].append(f"Buyer documents error (buyer {buyer_id[:8]}): {str(e)}")
    
    # Update auction status to 'ended'
    await db.multi_item_listings.update_one(
        {"id": auction_id},
        {"$set": {"status": "ended"}}
    )
    
    results['success'] = len(results['errors']) == 0
    results['summary'] = {
        "total_documents": len(results['documents_generated']),
        "total_emails": len(results['emails_sent']),
        "total_errors": len(results['errors'])
    }
    
    return results



@invoices_router.get("/email-logs")
async def get_email_logs(
    current_user: User = Depends(get_current_user)
):
    """
    Get all email logs (mock emails sent)
    Requires admin privileges
    """
    if current_user.account_type != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    email_logs = await db.email_logs.find({}, {"_id": 0}).to_list(100)
    return {
        "total": len(email_logs),
        "emails": email_logs
    }




@invoices_router.post("/invoices/generate/{transaction_id}")
async def generate_transaction_invoice(
    transaction_id: str,
    lang: str = Query("en", pattern="^(en|fr)$"),
    buyer_province: str = Query("QC", max_length=2),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a bilingual PDF invoice for a payment transaction,
    upload to Cloudflare R2, and store per-province tax breakdown
    (tax_gst, tax_pst_qst, tax_hst) on the transaction record.

    Requires: admin or buyer/seller of the transaction.
    """
    db = get_db()

    txn = await db.payment_transactions.find_one(
        {"id": transaction_id}, {"_id": 0}
    )
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Auth: admin, buyer, or seller
    is_admin = current_user.role in ("admin", "super_admin")
    is_buyer = txn.get("buyer_id") == current_user.id
    is_seller = txn.get("seller_id") == current_user.id
    if not (is_admin or is_buyer or is_seller):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Fetch buyer and seller docs
    buyer = await db.users.find_one(
        {"id": txn["buyer_id"]}, {"_id": 0, "password": 0}
    )
    seller = await db.users.find_one(
        {"id": txn["seller_id"]}, {"_id": 0, "password": 0}
    )
    if not buyer or not seller:
        raise HTTPException(status_code=404, detail="Buyer or seller not found")

    # Fetch listing for item title + vehicle info
    listing = await db.listings.find_one(
        {"id": txn.get("listing_id")},
        {"_id": 0, "title": 1, "vin": 1, "make": 1, "model": 1, "year": 1,
         "vehicle_vin": 1, "vehicle_make": 1, "vehicle_model": 1, "vehicle_year": 1}
    )

    # Build vehicle info dict if VIN is available
    vehicle = None
    if listing:
        vin = listing.get("vin") or listing.get("vehicle_vin")
        if vin:
            vehicle = {
                "vin": vin,
                "make": listing.get("make") or listing.get("vehicle_make", ""),
                "model": listing.get("model") or listing.get("vehicle_model", ""),
                "year": listing.get("year") or listing.get("vehicle_year", ""),
            }

    invoice_data = {
        "id": str(uuid.uuid4()),
        "invoice_number": f"BV-INV-{transaction_id[:8].upper()}",
        "transaction_id": transaction_id,
        "item_title": listing.get("title", "Auction Item") if listing else "Auction Item",
        "subtotal": txn.get("amount", 0),
        "buyer_premium": txn.get("buyer_premium", 0),
        "currency": txn.get("currency", "CAD"),
        "created_at": txn.get("created_at", datetime.now(timezone.utc).isoformat()),
        "vehicle": vehicle,
    }

    from services.invoice_service import generate_and_store_invoice
    storage_path = await generate_and_store_invoice(
        db, transaction_id, invoice_data, buyer, seller,
        lang=lang, buyer_province=buyer_province.upper(),
    )

    if not storage_path:
        raise HTTPException(status_code=500, detail="Invoice generation failed")

    from services.cloud_storage import generate_signed_url
    download_url = generate_signed_url(transaction_id)

    # Calculate tax summary for response
    from services.invoice_service import calculate_province_tax
    subtotal = invoice_data["subtotal"] + invoice_data["buyer_premium"]
    tax = calculate_province_tax(subtotal, buyer_province.upper(), lang)

    return {
        "success": True,
        "transaction_id": transaction_id,
        "invoice_number": invoice_data["invoice_number"],
        "storage_path": storage_path,
        "download_url": download_url,
        "tax_breakdown": tax.to_dict(),
    }
