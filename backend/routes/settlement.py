"""
routes/settlement.py — iter302 DIRECTIVES 1 + 2

Seller-facing Winner & Settlement Panel + buyer-facing Settle Payment flow.

Endpoints (all under /api/settlement):
  GET  /panel/{listing_id}            seller/admin — winner contact, amounts,
                                      payment status, reminder cooldown
  POST /panel/{listing_id}/remind     seller/admin — manual payment reminder
                                      email to the buyer (24h cooldown)
  GET  /settle-context/{listing_id}   winner — itemized invoice + saved-card
                                      last4 for the Settle Payment modal
  POST /settle/{listing_id}           winner — charge the saved card
                                      off-session NOW and finalize settlement
"""
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from deps import User, get_current_user, get_db

logger = logging.getLogger(__name__)

settlement_router = APIRouter(prefix="/settlement", tags=["settlement"])

PLATFORM_FEE_RATE = 0.025

_COLLECTIONS = [
    ("listings", "marketplace"),
    ("multi_item_listings", "lots"),
    ("storage_auctions", "storage"),
    ("vehicle_listings", "vehicles"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


async def _find_listing(db, listing_id: str):
    for coll, section in _COLLECTIONS:
        doc = await db[coll].find_one({"id": listing_id}, {"_id": 0})
        if doc:
            return doc, coll, section
    return None, None, None


def _winner_id(doc: Dict) -> Optional[str]:
    return doc.get("winner_id") or doc.get("winner_user_id") or doc.get("highest_bidder_id")


def _seller_id(doc: Dict) -> Optional[str]:
    return doc.get("seller_id") or doc.get("user_id") or doc.get("facility_id")


def _hammer(doc: Dict) -> float:
    return float(doc.get("final_price") or doc.get("current_price")
                 or doc.get("current_bid") or doc.get("winning_bid") or 0)


def _amounts(doc: Dict) -> Dict[str, float]:
    hammer = _hammer(doc)
    platform_fee = round(hammer * PLATFORM_FEE_RATE, 2)
    taxes = float(doc.get("buyer_taxes") or 0)
    total = round(hammer + platform_fee + taxes, 2)
    return {
        "hammer_price": round(hammer, 2),
        "platform_fee": platform_fee,
        "taxes": round(taxes, 2),
        "total_due": total,
        "net_payout": round(hammer - platform_fee, 2),
    }


def _payment_status(doc: Dict) -> str:
    return doc.get("payment_status") or "pending_payment"


# ────────────────────────────────────────────────────────────────────
# DIRECTIVE 1 — Winner & Settlement Panel (seller view)
# ────────────────────────────────────────────────────────────────────

@settlement_router.get("/panel/{listing_id}")
async def get_settlement_panel(listing_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    doc, _coll, section = await _find_listing(db, listing_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")

    seller_id = _seller_id(doc)
    is_admin = getattr(current_user, "role", None) in ("admin", "super_admin")
    if current_user.id != seller_id and not is_admin:
        raise HTTPException(status_code=403, detail="Only the seller can view the settlement panel")

    winner_id = _winner_id(doc)
    if not winner_id:
        raise HTTPException(status_code=400, detail="This listing has no winner")

    winner = await db.users.find_one(
        {"id": winner_id},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1, "phone_number": 1},
    ) or {}

    ended_at = _parse_dt(doc.get("ended_at") or doc.get("end_time") or doc.get("auction_end_date"))
    days_since_end = max(0, (_now() - ended_at).days) if ended_at else None

    reminder_at = _parse_dt(doc.get("manual_payment_reminder_sent_at"))
    reminder_hours_ago = None
    if reminder_at:
        reminder_hours_ago = round((_now() - reminder_at).total_seconds() / 3600, 1)

    return {
        "listing_id": listing_id,
        "section": section,
        "title": doc.get("title"),
        "winner": {
            "id": winner.get("id"),
            "name": winner.get("name"),
            "email": winner.get("email"),
            "phone": winner.get("phone") or winner.get("phone_number"),
        },
        **_amounts(doc),
        "payment_status": _payment_status(doc),
        "payment_deadline": doc.get("payment_deadline"),
        "payment_collected_at": doc.get("payment_collected_at"),
        "payout_status": doc.get("payout_status"),
        "pickup_code_confirmed": bool(doc.get("pickup_confirmed_at")),
        "days_since_end": days_since_end,
        "reminder_sent_hours_ago": reminder_hours_ago,
        "reminder_available": reminder_hours_ago is None or reminder_hours_ago >= 24,
        "buyer_receipt_id": doc.get("buyer_receipt_id"),
        "seller_statement_id": doc.get("seller_statement_id"),
    }


@settlement_router.post("/panel/{listing_id}/remind")
async def send_manual_payment_reminder(listing_id: str, current_user: User = Depends(get_current_user)):
    """Manual 'Send Payment Reminder' — 24h cooldown, seller/admin only."""
    db = get_db()
    doc, coll, _section = await _find_listing(db, listing_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")

    seller_id = _seller_id(doc)
    is_admin = getattr(current_user, "role", None) in ("admin", "super_admin")
    if current_user.id != seller_id and not is_admin:
        raise HTTPException(status_code=403, detail="Only the seller can send a reminder")

    if _payment_status(doc) in ("payment_collected", "paid"):
        raise HTTPException(status_code=400, detail="Payment already collected")

    winner_id = _winner_id(doc)
    if not winner_id:
        raise HTTPException(status_code=400, detail="This listing has no winner")

    last = _parse_dt(doc.get("manual_payment_reminder_sent_at"))
    if last and (_now() - last).total_seconds() < 24 * 3600:
        hours_ago = round((_now() - last).total_seconds() / 3600, 1)
        raise HTTPException(status_code=429, detail={
            "code": "reminder_cooldown",
            "hours_ago": hours_ago,
            "message_en": f"Reminder already sent {hours_ago:.0f} hours ago. You can send another in {24 - hours_ago:.0f}h.",
            "message_fr": f"Rappel déjà envoyé il y a {hours_ago:.0f} heures. Vous pourrez en envoyer un autre dans {24 - hours_ago:.0f} h.",
        })

    winner = await db.users.find_one({"id": winner_id}, {"_id": 0, "email": 1, "name": 1, "preferred_language": 1})
    if not winner or not winner.get("email"):
        raise HTTPException(status_code=400, detail="Winner has no email on file")

    amounts = _amounts(doc)
    deadline = doc.get("payment_deadline") or ""
    try:
        from services.emails.email_system import send_payment_reminder_email
        await send_payment_reminder_email(
            winner_email=winner["email"],
            winner_name=winner.get("name", "Winner"),
            item_title=doc.get("title", "Item"),
            final_price=amounts["hammer_price"],
            listing_id=listing_id,
            days_remaining=0,
            payment_deadline=deadline,
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"[settlement] manual reminder email failed for {listing_id}: {e}")
        raise HTTPException(status_code=502, detail="Failed to send the reminder email")

    now_iso = _now().isoformat()
    await db[coll].update_one(
        {"id": listing_id},
        {"$set": {"manual_payment_reminder_sent_at": now_iso}},
    )

    # Bell notification to buyer (best-effort)
    try:
        from services.notifications_i18n import create_notification
        await create_notification(
            db, user_id=winner_id, kind="payment_reminder",
            params={"title": doc.get("title", "Item"), "amount": amounts["total_due"]},
            data={"listing_id": listing_id, "action_url": "/buyer/dashboard"},
        )
    except Exception:  # noqa: BLE001
        pass

    return {"success": True, "sent_at": now_iso}


# ────────────────────────────────────────────────────────────────────
# DIRECTIVE 2 — buyer Settle Payment flow
# ────────────────────────────────────────────────────────────────────

@settlement_router.get("/settle-context/{listing_id}")
async def get_settle_context(listing_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    doc, _coll, section = await _find_listing(db, listing_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    if _winner_id(doc) != current_user.id:
        raise HTTPException(status_code=403, detail="Only the winning buyer can settle this payment")

    status = _payment_status(doc)
    if status in ("payment_collected", "paid"):
        return {"already_paid": True, "payment_status": status,
                "pickup_code": doc.get("pickup_code"),
                "buyer_receipt_id": doc.get("buyer_receipt_id")}

    # Saved card lookup (default PM on the Stripe customer)
    saved_card = None
    try:
        from services.auction_settlement import _get_default_pm
        pm = await _get_default_pm(db, current_user.id)
        if pm and pm.get("stripe_payment_method_id"):
            saved_card = {"last4": pm.get("last4") or pm.get("card_last4"),
                          "brand": pm.get("brand") or pm.get("card_brand")}
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[settlement] PM lookup failed for {current_user.id}: {e}")

    return {
        "already_paid": False,
        "listing_id": listing_id,
        "section": section,
        "title": doc.get("title"),
        **_amounts(doc),
        "payment_status": status,
        "payment_deadline": doc.get("payment_deadline"),
        "saved_card": saved_card,
    }


@settlement_router.post("/settle/{listing_id}")
async def settle_payment(listing_id: str, current_user: User = Depends(get_current_user)):
    """Charge the buyer's saved card off-session right now and finalize."""
    db = get_db()
    doc, coll, section = await _find_listing(db, listing_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    if _winner_id(doc) != current_user.id:
        raise HTTPException(status_code=403, detail="Only the winning buyer can settle this payment")

    status = _payment_status(doc)
    if status in ("payment_collected", "paid"):
        return {"success": True, "already_paid": True,
                "pickup_code": doc.get("pickup_code")}

    from services.payment_collection import finalize_auction_payment
    from services.auction_settlement import _get_default_pm, _charge_card, _to_cents

    buyer = await db.users.find_one({"id": current_user.id}, {"_id": 0, "stripe_customer_id": 1})
    pm = None
    try:
        pm = await _get_default_pm(db, current_user.id)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[settlement] PM lookup failed: {e}")
    if not pm or not pm.get("stripe_payment_method_id") or not (buyer or {}).get("stripe_customer_id"):
        raise HTTPException(status_code=400, detail={
            "code": "no_payment_method",
            "message_en": "No saved payment method. Please add a card first.",
            "message_fr": "Aucun moyen de paiement enregistré. Veuillez d'abord ajouter une carte.",
        })

    amounts = _amounts(doc)
    try:
        pi = await _charge_card(
            db,
            customer_id=buyer["stripe_customer_id"],
            payment_method_id=pm["stripe_payment_method_id"],
            amount_cents=_to_cents(amounts["total_due"]),
            currency="cad",
            description=f"BidVex settle — {doc.get('title', 'Item')} ({listing_id})",
            statement_descriptor=None,
            metadata={"listing_id": listing_id, "section": section,
                      "buyer_id": current_user.id, "flow": "manual_settle"},
            idempotency_key=f"settle-{listing_id}-{current_user.id}",
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"[settlement] settle charge failed for {listing_id}: {e}")
        raise HTTPException(status_code=402, detail={
            "code": "charge_failed",
            "message_en": "Your card was declined. Please try a different card or contact your bank.",
            "message_fr": "Votre carte a été refusée. Essayez une autre carte ou contactez votre banque.",
        })

    pi_status = getattr(pi, "status", None) or (pi.get("status") if isinstance(pi, dict) else None)
    pi_id = getattr(pi, "id", None) or (pi.get("id") if isinstance(pi, dict) else None)
    if pi_status not in ("succeeded", "requires_capture"):
        raise HTTPException(status_code=402, detail={
            "code": "charge_failed",
            "message_en": "Payment could not be completed. Please retry.",
            "message_fr": "Le paiement n'a pas pu être complété. Veuillez réessayer.",
        })

    last4 = pm.get("last4") or pm.get("card_last4")
    settlement = {
        "buyer_charge": {
            "stripe_pi": pi_id,
            "amount": amounts["total_due"],
            "payment_method_last4": last4,
        },
        "fee_breakdown": {
            "hammer_price": amounts["hammer_price"],
            "buyer_premium": amounts["platform_fee"],
            "buyer_taxes": amounts["taxes"],
            "buyer_total_charged": amounts["total_due"],
            "seller_commission": amounts["platform_fee"],
        },
        "warnings": [],
    }
    result = await finalize_auction_payment(
        db, listing=doc, collection=coll, settlement=settlement, section=section,
    )

    fresh, _c, _s = await _find_listing(db, listing_id)
    return {
        "success": True,
        "payment_status": (result or {}).get("payment_status", "payment_collected"),
        "pickup_code": (result or {}).get("pickup_code") or (fresh or {}).get("pickup_code"),
        "receipt_id": (result or {}).get("receipt_id"),
        "total_charged": amounts["total_due"],
    }


# ────────────────────────────────────────────────────────────────────
# DIRECTIVE 2 — Seller Stripe Connect onboarding (instant payouts)
# ────────────────────────────────────────────────────────────────────

def _stripe_client():
    import stripe
    stripe.api_key = os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
    return stripe


@settlement_router.post("/connect/onboard")
async def seller_connect_onboard(current_user: User = Depends(get_current_user)):
    """Create (or reuse) the seller's Stripe Connect Express account and
    return an onboarding link the seller dashboard redirects to."""
    stripe = _stripe_client()
    db = get_db()
    user = await db.users.find_one(
        {"id": current_user.id}, {"_id": 0, "stripe_connect_account_id": 1}
    )
    acct = (user or {}).get("stripe_connect_account_id")
    try:
        if not acct:
            account = stripe.Account.create(
                type="express",
                country="CA",
                email=current_user.email,
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers": {"requested": True},
                },
                business_type="individual",
                metadata={
                    "user_id": current_user.id,
                    "platform": "bidvex",
                    "source": "seller_payouts",
                },
            )
            acct = account.id
            await db.users.update_one(
                {"id": current_user.id},
                {"$set": {
                    "stripe_connect_account_id": acct,
                    "stripe_connect_onboarding_complete": False,
                    "updated_at": _now().isoformat(),
                }},
            )
        base_url = os.environ.get("REACT_APP_BACKEND_URL", "")
        link = stripe.AccountLink.create(
            account=acct,
            refresh_url=f"{base_url}/seller/dashboard?stripe_refresh=true",
            return_url=f"{base_url}/seller/dashboard?stripe=connected",
            type="account_onboarding",
            collection_options={"fields": "eventually_due"},
        )
        return {"success": True, "connect_account_id": acct, "onboarding_url": link.url}
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[settlement] connect onboard failed for {current_user.id}: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@settlement_router.get("/connect/status")
async def seller_connect_status(current_user: User = Depends(get_current_user)):
    """Connect readiness for the seller dashboard banner. Also syncs the
    payouts_enabled flag onto the user doc so process_seller_payout can
    route instant transfers."""
    db = get_db()
    user = await db.users.find_one(
        {"id": current_user.id},
        {"_id": 0, "stripe_connect_account_id": 1, "stripe_connect_onboarding_complete": 1},
    )
    acct = (user or {}).get("stripe_connect_account_id")
    if not acct:
        return {"connected": False, "account_id": None,
                "onboarding_complete": False, "payouts_enabled": False}
    try:
        stripe = _stripe_client()
        account = stripe.Account.retrieve(acct)
        onboarding_complete = bool(account.details_submitted)
        payouts_enabled = bool(account.payouts_enabled)
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {
                "stripe_connect_onboarding_complete": onboarding_complete,
                "stripe_connect_payouts_enabled": payouts_enabled,
            }},
        )
        return {"connected": True, "account_id": acct,
                "onboarding_complete": onboarding_complete,
                "payouts_enabled": payouts_enabled}
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[settlement] connect status failed for {current_user.id}: {exc}")
        return {"connected": True, "account_id": acct,
                "onboarding_complete": bool((user or {}).get("stripe_connect_onboarding_complete")),
                "payouts_enabled": False, "error": str(exc)}
