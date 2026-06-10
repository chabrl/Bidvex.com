"""
iter211 — Manual Settlement Service

Off-Stripe payment handling for:
  • Annual subscription renewals (partners, storage facilities, vehicle dealers)
  • Per-auction commissions (partners, storage facilities on cash auctions)

Key collections:
  • admin_financial_ledger — append-only audit log of every manual settlement
  • pending_commissions    — queue of unpaid commissions awaiting admin action

User fields touched:
  • dealer_subscription_active / dealer_subscription_renewal (vehicle dealers)
  • partner_subscription_active / partner_subscription_renewal (partners)
  • storage_subscription_active / storage_subscription_renewal (storage)
  • commission_payout_method    "auto" | "manual"
  • outstanding_manual_commission_cad   denormalised sum for the safety gate

Money safety:
  • Manual subscription settlement VOIDS any open Stripe Draft invoice for the
    same period (Task 3 zero-bug mandate).
  • A user with > MANUAL_COMMISSION_GATE_CAD owed is blocked from creating new
    listings until the admin settles them.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List

import stripe

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────
LEDGER_COLLECTION = "admin_financial_ledger"
PENDING_COMMISSIONS_COLLECTION = "pending_commissions"

# Default threshold to block listing creation when manual commissions are owed
MANUAL_COMMISSION_GATE_CAD = Decimal(os.environ.get("MANUAL_COMMISSION_GATE_CAD", "500"))

# Allowed payment methods for manual settlement
ALLOWED_PAYMENT_METHODS = {"e_transfer", "cheque", "wire", "cash"}

# Subscription field tuples per account kind
SUBSCRIPTION_FIELDS = {
    "vehicle_dealer": {
        "active": "dealer_subscription_active",
        "status": "dealer_subscription_status",
        "renewal": "dealer_subscription_renewal",
        "start": "dealer_subscription_start",
        "manual_method": "dealer_subscription_manual_method",
        "manual_reference": "dealer_subscription_manual_reference",
        "is_manual": "dealer_subscription_is_manual",
    },
    "partner": {
        "active": "partner_subscription_active",
        "status": "partner_subscription_status",
        "renewal": "partner_subscription_renewal",
        "start": "partner_subscription_start",
        "manual_method": "partner_subscription_manual_method",
        "manual_reference": "partner_subscription_manual_reference",
        "is_manual": "partner_subscription_is_manual",
    },
    "storage_facility": {
        "active": "storage_subscription_active",
        "status": "storage_subscription_status",
        "renewal": "storage_subscription_renewal",
        "start": "storage_subscription_start",
        "manual_method": "storage_subscription_manual_method",
        "manual_reference": "storage_subscription_manual_reference",
        "is_manual": "storage_subscription_is_manual",
    },
}

# ── Helpers ──────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _ledger_insert(db, entry: Dict[str, Any]) -> str:
    entry.setdefault("id", str(uuid.uuid4()))
    entry.setdefault("created_at", _now_iso())
    await db[LEDGER_COLLECTION].insert_one(entry)
    return entry["id"]


# ── Stripe draft invoice void (Task 3 zero-bug mandate) ──────────────────


async def _void_open_stripe_subscription_invoices(stripe_subscription_id: Optional[str]) -> List[str]:
    """Void all Draft / Open invoices for a Stripe subscription so they
    don't double-charge after a manual settlement.

    Returns the list of voided invoice IDs (best-effort)."""
    if not stripe_subscription_id:
        return []
    voided: List[str] = []
    try:
        stripe.api_key = os.environ.get("STRIPE_API_KEY")
        # List invoices on this subscription that aren't fully paid
        invs = stripe.Invoice.list(subscription=stripe_subscription_id, limit=20)
        for inv in invs.auto_paging_iter():
            if inv.status in ("draft", "open"):
                try:
                    stripe.Invoice.void_invoice(inv.id)
                    voided.append(inv.id)
                except Exception as exc:
                    logger.warning(f"[manual-settle] void {inv.id} failed: {exc}")
    except Exception as exc:
        logger.warning(f"[manual-settle] list invoices failed for sub {stripe_subscription_id}: {exc}")
    return voided


# ── Manual subscription settle ──────────────────────────────────────────


async def manual_settle_subscription(
    db,
    *,
    target_user_id: str,
    admin_user_id: str,
    account_kind: str,
    payment_method: str,
    reference_number: str,
    amount_cad: float,
    active_until: Optional[str] = None,
    notes: str = "",
) -> Dict[str, Any]:
    """Activate the user's annual subscription off-Stripe.

    Args:
      account_kind:   "vehicle_dealer" | "partner" | "storage_facility"
      payment_method: e_transfer | cheque | wire | cash
      reference_number: human-readable TXN ref (cheque #, e-Transfer reference, etc.)
      amount_cad: amount actually collected (for the ledger)
      active_until: ISO datetime string; defaults to now + 365 days
    """
    if account_kind not in SUBSCRIPTION_FIELDS:
        raise ValueError(f"Unsupported account_kind: {account_kind}")
    pm = (payment_method or "").lower().strip().replace("-", "_")
    if pm not in ALLOWED_PAYMENT_METHODS:
        raise ValueError(f"Unsupported payment_method: {payment_method}")
    if not (reference_number or "").strip():
        raise ValueError("reference_number is required")

    user = await db.users.find_one({"id": target_user_id}, {"_id": 0})
    if not user:
        raise ValueError("user_not_found")

    now = datetime.now(timezone.utc)
    if active_until:
        try:
            renewal_dt = datetime.fromisoformat(active_until.replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"Invalid active_until ISO date: {e}")
    else:
        renewal_dt = now + timedelta(days=365)
    renewal_iso = renewal_dt.isoformat()

    fields = SUBSCRIPTION_FIELDS[account_kind]
    set_payload = {
        fields["active"]: True,
        fields["status"]: "active_manual",
        fields["start"]: now.isoformat(),
        fields["renewal"]: renewal_iso,
        fields["manual_method"]: pm,
        fields["manual_reference"]: reference_number.strip(),
        fields["is_manual"]: True,
    }
    # If this kind has a "suspended" flag, clear it
    if account_kind == "vehicle_dealer":
        set_payload["vehicle_dealer_suspended"] = False

    # iter216 — Backwards-compat field aliases. Each account-type dashboard
    # historically read a different field name; the manual-settle code path
    # only flipped the new normalised `*_subscription_active` field, so the
    # dashboards stayed showing "Annual Payment Required" until someone
    # noticed (Alex Boulanger). Write the legacy aliases too:
    if account_kind == "partner":
        set_payload["platform_fee_paid"] = True
        set_payload["partner_fee_paid_at"] = now.isoformat()
        set_payload["partner_payment_method"] = pm
        set_payload["partner_payment_reference"] = reference_number.strip()
        set_payload["partner_payment_amount"] = float(amount_cad)
        set_payload["partner_payment_confirmed_by"] = admin_user_id
        set_payload["partner_subscription_paid_at"] = now.isoformat()
        set_payload["partner_subscription_renewal_date"] = renewal_iso
    elif account_kind == "vehicle_dealer":
        set_payload["dealer_subscription_paid_at"] = now.isoformat()
        set_payload["dealer_subscription_renewal_date"] = renewal_iso
        set_payload["dealer_payment_method"] = pm
        set_payload["dealer_payment_reference"] = reference_number.strip()
        set_payload["dealer_payment_amount"] = float(amount_cad)
        set_payload["dealer_payment_confirmed_by"] = admin_user_id
    elif account_kind == "storage_facility":
        set_payload["storage_subscription_paid_at"] = now.isoformat()
        set_payload["storage_subscription_renewal_date"] = renewal_iso
        set_payload["storage_payment_method"] = pm
        set_payload["storage_payment_reference"] = reference_number.strip()
        set_payload["storage_payment_amount"] = float(amount_cad)
        set_payload["storage_payment_confirmed_by"] = admin_user_id

    await db.users.update_one({"id": target_user_id}, {"$set": set_payload})

    # iter216 — Persist a normalised payment record so the new
    # `payments` collection is the single source of truth for reporting.
    try:
        import uuid as _u
        await db.payments.insert_one({
            "id": str(_u.uuid4()),
            "user_id": target_user_id,
            "payment_type": "annual_subscription",
            "account_type": account_kind,
            "amount_cad": float(amount_cad),
            "method": pm,
            "reference_number": reference_number.strip(),
            "confirmed_by": admin_user_id,
            "confirmed_at": now.isoformat(),
            "notes": notes,
            "renewal_until": renewal_iso,
        })
    except Exception as e:
        logger.warning(f"[manual-settle] payments insert failed (non-fatal): {e}")

    # iter216 — Send bilingual confirmation email to the user
    try:
        from services.emails.email_system import send_manual_subscription_active_email
        await send_manual_subscription_active_email(
            user=user, account_kind=account_kind,
            amount_cad=float(amount_cad), method=pm,
            renewal_until=renewal_iso, reference=reference_number.strip(),
        )
    except Exception as e:
        logger.warning(f"[manual-settle] confirmation email failed: {e}")

    # Void any open Stripe subscription invoices to avoid double-charge
    sub_id = user.get("dealer_stripe_subscription_id") or user.get("vehicle_dealer_subscription_id")
    voided_invoices = await _void_open_stripe_subscription_invoices(sub_id)

    # Audit
    ledger_id = await _ledger_insert(db, {
        "kind": "manual_subscription_settle",
        "account_kind": account_kind,
        "user_id": target_user_id,
        "user_email": user.get("email"),
        "admin_id": admin_user_id,
        "payment_method": pm,
        "reference_number": reference_number.strip(),
        "amount_cad": float(amount_cad),
        "renewal_until": renewal_iso,
        "notes": notes,
        "stripe_invoices_voided": voided_invoices,
    })

    logger.info(f"[manual-settle] subscription kind={account_kind} user={target_user_id} until={renewal_iso} by={admin_user_id}")
    return {
        "ok": True,
        "ledger_id": ledger_id,
        "renewal_until": renewal_iso,
        "stripe_invoices_voided": voided_invoices,
        "fields_set": set_payload,
    }


# ── Pending commissions queue ───────────────────────────────────────────


async def enqueue_manual_commission(
    db,
    *,
    user_id: str,
    auction_id: Optional[str],
    listing_id: Optional[str],
    listing_title: str,
    commission_amount_cad: float,
    stripe_invoice_id: Optional[str] = None,
    notes: str = "",
) -> Dict[str, Any]:
    """Insert a row into pending_commissions and bump the user's outstanding
    counter so the safety gate can read it cheaply."""
    if commission_amount_cad <= 0:
        return {"ok": False, "reason": "non_positive_amount"}

    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "auction_id": auction_id,
        "listing_id": listing_id,
        "listing_title": listing_title,
        "commission_amount_cad": float(commission_amount_cad),
        "status": "pending",
        "stripe_invoice_id": stripe_invoice_id,
        "notes": notes,
        "created_at": _now_iso(),
        "settled_at": None,
        "settled_by": None,
        "payment_method": None,
        "reference_number": None,
    }
    await db[PENDING_COMMISSIONS_COLLECTION].insert_one(doc)
    await db.users.update_one(
        {"id": user_id},
        {"$inc": {"outstanding_manual_commission_cad": float(commission_amount_cad)}},
    )
    logger.info(f"[manual-commission] enqueued ${commission_amount_cad:.2f} for user={user_id} listing={listing_id}")
    doc.pop("_id", None)
    return {"ok": True, "pending_commission_id": doc["id"], **doc}


async def settle_pending_commission(
    db,
    *,
    pending_id: str,
    admin_user_id: str,
    payment_method: str,
    reference_number: str,
    notes: str = "",
) -> Dict[str, Any]:
    """Mark a pending_commissions row as paid, ledger the receipt, void the
    matching Stripe Draft invoice (if any), and decrement the outstanding total.
    """
    pm = (payment_method or "").lower().strip().replace("-", "_")
    if pm not in ALLOWED_PAYMENT_METHODS:
        raise ValueError(f"Unsupported payment_method: {payment_method}")
    if not (reference_number or "").strip():
        raise ValueError("reference_number is required")

    row = await db[PENDING_COMMISSIONS_COLLECTION].find_one({"id": pending_id}, {"_id": 0})
    if not row:
        raise ValueError("pending_commission_not_found")
    if row["status"] != "pending":
        raise ValueError(f"already_{row['status']}")

    now = _now_iso()
    await db[PENDING_COMMISSIONS_COLLECTION].update_one(
        {"id": pending_id, "status": "pending"},
        {"$set": {
            "status": "paid",
            "settled_at": now,
            "settled_by": admin_user_id,
            "payment_method": pm,
            "reference_number": reference_number.strip(),
        }},
    )
    await db.users.update_one(
        {"id": row["user_id"]},
        {"$inc": {"outstanding_manual_commission_cad": -float(row["commission_amount_cad"])}},
    )

    # Void the matching Stripe Draft invoice (Task 3)
    voided = []
    if row.get("stripe_invoice_id"):
        try:
            stripe.api_key = os.environ.get("STRIPE_API_KEY")
            inv = stripe.Invoice.retrieve(row["stripe_invoice_id"])
            if inv.status in ("draft", "open"):
                stripe.Invoice.void_invoice(inv.id)
                voided.append(inv.id)
        except Exception as exc:
            logger.warning(f"[manual-commission] void invoice {row['stripe_invoice_id']} failed: {exc}")

    # Audit
    ledger_id = await _ledger_insert(db, {
        "kind": "manual_commission_settle",
        "user_id": row["user_id"],
        "admin_id": admin_user_id,
        "auction_id": row.get("auction_id"),
        "listing_id": row.get("listing_id"),
        "amount_cad": float(row["commission_amount_cad"]),
        "payment_method": pm,
        "reference_number": reference_number.strip(),
        "notes": notes,
        "stripe_invoices_voided": voided,
    })

    return {
        "ok": True,
        "ledger_id": ledger_id,
        "voided_invoice_ids": voided,
        "pending_id": pending_id,
    }


# ── Safety gate ─────────────────────────────────────────────────────────


async def user_is_blocked_by_outstanding_commission(db, user_id: str) -> Dict[str, Any]:
    """Returns {blocked: bool, outstanding_cad: float, threshold_cad: float}.

    The safety gate uses the denormalised `users.outstanding_manual_commission_cad`
    counter, fall back to a live sum of pending_commissions if missing.
    """
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "outstanding_manual_commission_cad": 1})
    if user is None:
        return {"blocked": False, "outstanding_cad": 0.0, "threshold_cad": float(MANUAL_COMMISSION_GATE_CAD)}
    outstanding = user.get("outstanding_manual_commission_cad")
    if outstanding is None:
        # Fall back to live sum
        pipeline = [
            {"$match": {"user_id": user_id, "status": "pending"}},
            {"$group": {"_id": None, "total": {"$sum": "$commission_amount_cad"}}},
        ]
        agg = await db[PENDING_COMMISSIONS_COLLECTION].aggregate(pipeline).to_list(1)
        outstanding = float(agg[0]["total"]) if agg else 0.0
    return {
        "blocked": float(outstanding) >= float(MANUAL_COMMISSION_GATE_CAD),
        "outstanding_cad": float(outstanding),
        "threshold_cad": float(MANUAL_COMMISSION_GATE_CAD),
    }
