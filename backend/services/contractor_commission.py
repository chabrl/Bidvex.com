"""
iter316 Mission 4 — Contractor Commission Engine + Stripe Connect Payout.

Generic, account-type-agnostic commission accrual triggered by the
SHARED platform-fee capture path (services.payment_collection +
services.vehicle_fee_service). When a seller account carries a
referred_by_contractor_id stamp, every successful platform-fee
collection accrues a commission ledger entry for that contractor.

Monthly payout is delivered via the EXISTING Stripe Connect
infrastructure built for sellers (services.seller_payouts):
contractors are mapped as standard Connect transfer recipients —
their stripe_connect_account_id field on the users collection is
read using the same mechanism as the seller payout flow, so we
inherit onboarding, payout enablement, and admin alerts without
forking the regulatory/physical-asset workflows the seller path
already implements.

Reuses (do NOT fork):
  • Stripe.Transfer.create pattern from services.seller_payouts
  • stripe_connect_account_id / stripe_connect_onboarding_complete
    fields on the users collection
  • emails.email_marketplace.send_email helper for confirmations
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


DEFAULT_COMMISSION_RATE = 0.20  # 20% — fallback if admin hasn't set a rate

# Full set of account types tracked by the COMMISSION ENGINE.
# Brokers + liquidators are platform-wide account types (see /backend/models/broker_models.py),
# registered through dedicated flows. The contractor's "Add a Client" shortcut
# (iter323 — see CONTRACTOR_CREATABLE_ACCOUNT_TYPES below) intentionally omits
# them, but the engine MUST still pay commission on them.
ACCOUNT_TYPES = (
    "individual_seller",
    "liquidator",
    "partner",
    "broker",
    "vehicle_dealer",
    "storage_facility",  # iter323 — match StorageFooterBanner.js + DEMO_ACCOUNT_TYPES
    "business",          # iter323 — generic business client (not vehicle/storage specific)
)

# iter323 — Subset that contractors are allowed to create via the
# "Add a Client" dropdown in their dashboard. Brokers + liquidators are
# excluded here because they have dedicated registration flows
# (broker license verification, OPC permits, etc.) and cannot be quickly
# spawned from the contractor dialer shortcut.
CONTRACTOR_CREATABLE_ACCOUNT_TYPES = (
    "individual_seller",   # "Individual"   / "Particulier"
    "business",            # "Business"     / "Entreprise"
    "partner",             # "Partner"      / "Partenaire"
    "vehicle_dealer",      # "Vehicle Dealer" / "Marchand de véhicules"
    "storage_facility",    # "Storage Facility" / "Centre d'entreposage"
)


# ─── Commission rate config ─────────────────────────────────────────────

async def get_contractor_commission_rate(db, contractor_id: str, account_type: str) -> float:
    """Look up the per-account-type rate for this contractor. Falls back
    to default_rate, then DEFAULT_COMMISSION_RATE."""
    cfg = await db.contractor_commission_rates.find_one(
        {"contractor_id": contractor_id}, {"_id": 0},
    )
    if not cfg:
        return DEFAULT_COMMISSION_RATE
    rates = cfg.get("rates_by_account_type") or {}
    rate = rates.get(account_type)
    if rate is not None:
        return float(rate)
    return float(cfg.get("default_rate") or DEFAULT_COMMISSION_RATE)


async def upsert_contractor_commission_rates(
    db, *,
    contractor_id: str,
    rates_by_account_type: Optional[Dict[str, float]] = None,
    default_rate: Optional[float] = None,
    updated_by_admin_id: str,
) -> Dict[str, Any]:
    """Admin-only setter. Rate changes apply going FORWARD only — the
    accrue function captures the rate IN the ledger row at accrual time,
    so historical settlements are immutable."""
    existing = await db.contractor_commission_rates.find_one({"contractor_id": contractor_id}, {"_id": 0})
    rates = dict(existing.get("rates_by_account_type") or {}) if existing else {}
    if rates_by_account_type:
        for k, v in rates_by_account_type.items():
            if k not in ACCOUNT_TYPES:
                raise ValueError(f"unknown account_type: {k}")
            rates[k] = float(v)
    new_default = float(default_rate) if default_rate is not None else \
                    (float(existing.get("default_rate")) if existing else DEFAULT_COMMISSION_RATE)
    payload = {
        "contractor_id":          contractor_id,
        "rates_by_account_type":  rates,
        "default_rate":           new_default,
        "updated_by_admin_id":    updated_by_admin_id,
        "updated_at":             _now_iso(),
    }
    if existing:
        await db.contractor_commission_rates.update_one(
            {"contractor_id": contractor_id}, {"$set": payload},
        )
    else:
        payload["id"] = str(uuid.uuid4())
        payload["created_at"] = _now_iso()
        await db.contractor_commission_rates.insert_one(payload)
    return payload


# ─── Commission accrual (called by the shared fee-capture hook) ─────────

async def maybe_accrue_contractor_commission(
    db, *,
    seller_id: str,
    listing_id: str,
    platform_fee_amount: float,
    transaction_id: Optional[str] = None,
    section: str = "marketplace",
) -> Optional[Dict[str, Any]]:
    """Called once per successful platform-fee collection. If the seller
    has a referred_by_contractor_id stamp, accrue a commission ledger
    entry. Idempotent: a unique combo of (contractor_id, source_listing_id,
    transaction_id) prevents double-accrual if the fee capture path is
    retried."""
    if not seller_id or not platform_fee_amount or platform_fee_amount <= 0:
        return None
    seller = await db.users.find_one(
        {"id": seller_id},
        {"_id": 0, "referred_by_contractor_id": 1, "account_type": 1,
         "seller_type": 1, "is_partner": 1, "is_broker": 1,
         "is_vehicle_dealer": 1, "is_liquidator": 1},
    )
    if not seller:
        return None
    contractor_id = seller.get("referred_by_contractor_id")
    if not contractor_id:
        return None

    account_type = _derive_account_type(seller)
    rate = await get_contractor_commission_rate(db, contractor_id, account_type)
    commission_amount = round(float(platform_fee_amount) * float(rate), 2)
    if commission_amount <= 0:
        return None

    # Idempotency guard.
    dedupe = {
        "contractor_id":      contractor_id,
        "source_listing_id":  listing_id,
        "transaction_id":     transaction_id or None,
    }
    existing = await db.contractor_commission_ledger.find_one(dedupe, {"_id": 0, "id": 1})
    if existing:
        logger.info(f"[commission] dup skipped contractor={contractor_id} listing={listing_id}")
        return existing

    entry = {
        "id":                       str(uuid.uuid4()),
        "contractor_id":            contractor_id,
        "source_account_id":        seller_id,
        "source_listing_id":        listing_id,
        "section":                  section,
        "transaction_id":           transaction_id,
        "account_type":             account_type,
        "platform_fee_amount":      round(float(platform_fee_amount), 2),
        "commission_rate_applied":  float(rate),
        "commission_amount":        commission_amount,
        "status":                   "accrued",
        "transaction_date":         _now_iso(),
        "payout_batch_id":          None,
        "created_at":               _now_iso(),
    }
    await db.contractor_commission_ledger.insert_one(entry)
    logger.info(f"[commission] +${commission_amount} accrued for "
                f"contractor={contractor_id} listing={listing_id} "
                f"({account_type} @ {rate:.2%})")
    return entry


def _derive_account_type(seller: Dict[str, Any]) -> str:
    """Resolve a seller doc's account type, defaulting to vehicle_dealer
    when the account carries the dealer flag (Phase A scope constraint).
    Order of precedence: explicit account_type field → role flags →
    vehicle_dealer fallback when is_vehicle_dealer=True → individual_seller."""
    explicit = seller.get("account_type")
    if explicit in ACCOUNT_TYPES:
        return explicit
    if seller.get("is_vehicle_dealer"):
        return "vehicle_dealer"
    if seller.get("is_partner"):
        return "partner"
    if seller.get("is_broker"):
        return "broker"
    if seller.get("is_liquidator"):
        return "liquidator"
    if seller.get("seller_type") == "dealer":
        return "vehicle_dealer"
    return "individual_seller"


# ─── Admin override: remove referral attribution ────────────────────────

async def remove_referral_attribution(db, *, account_id: str,
                                       admin_id: str, reason: str) -> Dict[str, Any]:
    """Admin-only manual action. Removes the permanent referral stamp
    from a given account so future commissions stop accruing. Existing
    accrued/paid ledger rows are preserved (history is immutable)."""
    res = await db.users.update_one(
        {"id": account_id, "referred_by_contractor_id": {"$exists": True}},
        {"$set": {
            "referred_by_contractor_id_removed_by": admin_id,
            "referred_by_contractor_id_removed_reason": reason,
            "referred_by_contractor_id_removed_at": _now_iso(),
        },
         "$unset": {"referred_by_contractor_id": ""}},
    )
    return {"removed": res.modified_count == 1, "account_id": account_id}


# ─── Monthly payout ─────────────────────────────────────────────────────

async def run_monthly_contractor_payouts(db) -> Dict[str, Any]:
    """Aggregate every contractor's accrued balance and pay it out via
    Stripe Connect. Contractors without a connected Stripe account: rows
    stay 'accrued' and the contractor dashboard surfaces a banner.

    Reuses the SAME stripe_connect_account_id field + Transfer.create
    pattern from services.seller_payouts — contractors are standard
    Connect destinations, not a separate payout class. We deliberately
    do NOT touch the seller-specific listing-stamping or admin-pending
    flows (those are physical-asset / regulatory paths that don't apply
    to contractor commissions)."""
    batch_id = str(uuid.uuid4())
    out: Dict[str, Any] = {"batch_id": batch_id, "paid": [], "skipped_no_connect": [], "errors": []}

    # Group accrued entries by contractor_id.
    pipeline = [
        {"$match": {"status": "accrued"}},
        {"$group": {"_id": "$contractor_id",
                    "total": {"$sum": "$commission_amount"},
                    "entry_ids": {"$push": "$id"},
                    "count": {"$sum": 1}}},
    ]
    grouped = await db.contractor_commission_ledger.aggregate(pipeline).to_list(length=1000)

    for g in grouped:
        contractor_id = g["_id"]
        total_amount  = round(float(g["total"] or 0), 2)
        entry_ids     = g["entry_ids"]
        if total_amount <= 0:
            continue

        contractor = await db.users.find_one(
            {"id": contractor_id},
            {"_id": 0, "id": 1, "email": 1, "first_name": 1, "name": 1,
             "stripe_connect_account_id": 1,
             "stripe_connect_payouts_enabled": 1,
             "stripe_connect_onboarding_complete": 1,
             "preferred_language": 1},
        )
        if not contractor:
            out["errors"].append({"contractor_id": contractor_id, "reason": "user_missing"})
            continue

        acct = contractor.get("stripe_connect_account_id")
        connect_ready = bool(
            acct and (contractor.get("stripe_connect_payouts_enabled")
                      or contractor.get("stripe_connect_onboarding_complete"))
        )
        if not connect_ready:
            out["skipped_no_connect"].append({
                "contractor_id": contractor_id,
                "accrued_total": total_amount,
                "entries":       len(entry_ids),
            })
            continue

        # Transfer via Stripe Connect — same pattern as services.seller_payouts.
        try:
            import stripe
            stripe.api_key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
            transfer = stripe.Transfer.create(
                amount=int(round(total_amount * 100)),
                currency="cad",
                destination=acct,
                metadata={
                    "kind":          "contractor_commission",
                    "contractor_id": contractor_id,
                    "batch_id":      batch_id,
                    "entry_count":   len(entry_ids),
                },
                idempotency_key=f"contractor-payout-{contractor_id}-{batch_id}",
            )
            transfer_id = transfer.id
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[contractor_payout] Transfer failed for {contractor_id}: {e}")
            out["errors"].append({"contractor_id": contractor_id, "reason": str(e)[:200]})
            continue

        # Mark every entry in this batch as paid.
        await db.contractor_commission_ledger.update_many(
            {"id": {"$in": entry_ids}, "status": "accrued"},
            {"$set": {
                "status":          "paid",
                "payout_batch_id": batch_id,
                "stripe_transfer_id": transfer_id,
                "paid_at":          _now_iso(),
            }},
        )

        out["paid"].append({
            "contractor_id":   contractor_id,
            "amount":          total_amount,
            "entries":         len(entry_ids),
            "transfer_id":     transfer_id,
        })

        # Confirmation email — best effort, never blocks.
        try:
            from services.emails._email_core import send_email
            fr = (contractor.get("preferred_language") or "en") == "fr"
            subj = (f"BidVex — Paiement de commission {total_amount:.2f} $ CAD"
                    if fr else f"BidVex — Commission payout ${total_amount:.2f} CAD")
            body = _build_payout_email_html(total_amount, len(entry_ids), transfer_id, fr)
            await send_email(to_email=contractor["email"], subject=subj, html_content=body,
                             categories=["contractor_payout"])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[contractor_payout] mail failed: {e}")

    out["batch_total"] = round(sum(p["amount"] for p in out["paid"]), 2)
    out["paid_count"]  = len(out["paid"])
    return out


def _build_payout_email_html(amount: float, n_entries: int, transfer_id: str, fr: bool) -> str:
    if fr:
        return (
            f"<h2>Paiement de commission BidVex</h2>"
            f"<p>Vous avez reçu un paiement de <b>{amount:.2f} $ CAD</b> "
            f"couvrant <b>{n_entries}</b> transactions de commission accrues.</p>"
            f"<p>ID de transfert Stripe : <code>{transfer_id}</code></p>"
            f"<p>Connectez-vous au tableau de bord du contractant pour voir le détail.</p>"
        )
    return (
        f"<h2>BidVex Commission Payout</h2>"
        f"<p>You've been paid <b>${amount:.2f} CAD</b> covering "
        f"<b>{n_entries}</b> accrued commission transactions.</p>"
        f"<p>Stripe transfer id: <code>{transfer_id}</code></p>"
        f"<p>Log in to your contractor dashboard for the breakdown.</p>"
    )


# ─── Dashboard helpers ──────────────────────────────────────────────────

async def contractor_earnings_summary(db, contractor_id: str) -> Dict[str, Any]:
    """Aggregate accrued (this month) + lifetime paid + lifetime accrued."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    cursor = db.contractor_commission_ledger.aggregate([
        {"$match": {"contractor_id": contractor_id}},
        {"$group": {
            "_id": "$status",
            "total": {"$sum": "$commission_amount"},
            "count": {"$sum": 1},
        }},
    ])
    rows = await cursor.to_list(length=10)
    by_status = {r["_id"]: r for r in rows}
    accrued = by_status.get("accrued") or {"total": 0, "count": 0}
    paid    = by_status.get("paid") or {"total": 0, "count": 0}

    this_month_accrued = await db.contractor_commission_ledger.aggregate([
        {"$match": {"contractor_id": contractor_id, "status": "accrued",
                    "transaction_date": {"$gte": month_start}}},
        {"$group": {"_id": None, "total": {"$sum": "$commission_amount"}}},
    ]).to_list(length=2)
    tm_total = round(float(this_month_accrued[0]["total"]) if this_month_accrued else 0.0, 2)

    return {
        "this_month_accrued": tm_total,
        "lifetime_accrued":   round(float(accrued["total"]), 2),
        "lifetime_paid":      round(float(paid["total"]), 2),
        "entries_count":      int(accrued["count"]) + int(paid["count"]),
    }


async def contractor_referred_accounts(db, contractor_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    """All accounts permanently stamped to this contractor."""
    rows = await db.users.find(
        {"referred_by_contractor_id": contractor_id},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "first_name": 1,
         "last_name": 1, "business_name": 1,
         "account_type": 1, "is_partner": 1, "is_broker": 1,
         "is_vehicle_dealer": 1, "is_liquidator": 1,
         "seller_type": 1, "created_at": 1,
         "contractor_demo_account": 1, "contractor_demo_expires_at": 1},
    ).sort("created_at", -1).limit(limit).to_list(length=limit)
    out = []
    for r in rows:
        out.append({
            "id":              r.get("id"),
            "name":            r.get("business_name") or r.get("name") or
                                f"{r.get('first_name','')} {r.get('last_name','')}".strip() or
                                r.get("email"),
            "account_type":    _derive_account_type(r),
            "is_demo":         bool(r.get("contractor_demo_account")),
            "demo_expires_at": r.get("contractor_demo_expires_at"),
            "created_at":      r.get("created_at"),
        })
    return out


async def contractor_commission_history(db, contractor_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    rows = await db.contractor_commission_ledger.find(
        {"contractor_id": contractor_id},
        {"_id": 0},
    ).sort("transaction_date", -1).limit(limit).to_list(length=limit)
    return rows


__all__ = [
    "ACCOUNT_TYPES",
    "DEFAULT_COMMISSION_RATE",
    "get_contractor_commission_rate",
    "upsert_contractor_commission_rates",
    "maybe_accrue_contractor_commission",
    "remove_referral_attribution",
    "run_monthly_contractor_payouts",
    "contractor_earnings_summary",
    "contractor_referred_accounts",
    "contractor_commission_history",
]
