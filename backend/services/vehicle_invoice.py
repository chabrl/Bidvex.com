"""
BidVex Vehicle Auction - Invoice Generation Service
Handles invoice creation, management, and payment tracking
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import uuid
import logging

from services.vehicle_pricing import (
    calculate_buyer_pricing,
    calculate_seller_pricing,
    calculate_late_penalty,
    get_subscription_tier,
    SubscriptionTier,
    PAYMENT_DEADLINE_DAYS,
)

logger = logging.getLogger(__name__)


class InvoiceStatus:
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


async def generate_vehicle_invoice(
    db,
    vehicle_listing: dict,
    winner_user: dict,
    seller_user: dict,
    final_price: float
) -> dict:
    """
    Generate invoice for a won VEHICLE auction (Rule 2 — Non-custodial).
    Buyer pays: 2.5% platform fee + stripe recovery + tax on fees.
    Seller pays: $0. Hammer settled directly buyer↔seller.
    """
    from services.fee_calculator import PricingManager

    now = datetime.now(timezone.utc)
    deadline = now + timedelta(days=PAYMENT_DEADLINE_DAYS)

    buyer_province = winner_user.get("province") or vehicle_listing.get("location_province", "ON")
    buyer_tier_raw = winner_user.get("subscription_tier", "free")

    # Use PricingManager for correct vehicle pricing
    pricing = PricingManager.vehicle_auction(
        hammer_price=final_price,
        buyer_province=buyer_province,
        buyer_tier=buyer_tier_raw,
    )
    bi = pricing.buyer_invoice
    invoice_number = f"VEH-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

    buyer_line_items = [{"description": ln.description, "type": ln.line_type,
                         "amount": ln.amount, "rate": ln.rate} for ln in bi.lines]

    buyer_invoice = {
        "id": str(uuid.uuid4()),
        "invoice_number": invoice_number,
        "invoice_type": "buyer_vehicle_fee",

        "vehicle_id": vehicle_listing["id"],
        "vehicle_vin": vehicle_listing.get("vin", ""),
        "vehicle_title": f"{vehicle_listing.get('year','')} {vehicle_listing.get('make','')} {vehicle_listing.get('model','')}",
        "auction_id": vehicle_listing["id"],

        "buyer_id": winner_user["id"],
        "buyer_email": winner_user.get("email"),
        "buyer_name": winner_user.get("full_name", winner_user.get("name", winner_user.get("email"))),
        "buyer_province": buyer_province,
        "seller_id": vehicle_listing.get("seller_user_id"),

        "hammer_price": final_price,
        "platform_fee": bi.fees_subtotal,
        "stripe_recovery": bi.stripe_recovery,

        "tax_type": bi.tax_type,
        "tax_label": bi.tax_label,
        "tax_rate": bi.tax_rate,
        "tax_total": bi.tax_amount,
        # Granular tax fields for receipt display
        "tax_gst": next((ln.amount for ln in bi.lines if "GST" in ln.description and "QST" not in ln.description), 0.0),
        "tax_qst": next((ln.amount for ln in bi.lines if "QST" in ln.description), 0.0),
        "tax_hst": next((ln.amount for ln in bi.lines if "HST" in ln.description), 0.0),

        "subtotal_before_tax": bi.fees_subtotal + bi.stripe_recovery,
        "total_amount": bi.total,

        "subscription_tier": buyer_tier_raw,
        "line_items": buyer_line_items,

        "payment_status": InvoiceStatus.PENDING,
        "payment_deadline": deadline,
        "paid_at": None,
        "paid_amount": 0.0,
        "deposit_credited": 0.0,
        "penalty_amount": 0.0,
        "created_at": now,
        "updated_at": None,
        "due_at": deadline,

        "note_en": "BidVex charges a 2.5% platform fee only. The vehicle hammer price is settled directly between buyer and seller.",
        "note_fr": "BidVex facture uniquement des frais de plateforme de 2,5 %. Le prix d'adjudication du véhicule est réglé directement entre l'acheteur et le vendeur.",
    }

    # Seller invoice — $0 for vehicles (Rule 2)
    seller_invoice = {
        "id": str(uuid.uuid4()),
        "invoice_number": f"SET-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}",
        "invoice_type": "seller_vehicle_settlement",

        "vehicle_id": vehicle_listing["id"],
        "vehicle_vin": vehicle_listing.get("vin", ""),
        "vehicle_title": buyer_invoice["vehicle_title"],
        "auction_id": vehicle_listing["id"],
        "buyer_invoice_id": buyer_invoice["id"],

        "seller_id": vehicle_listing.get("seller_user_id"),
        "seller_email": seller_user.get("email"),
        "seller_name": seller_user.get("full_name", seller_user.get("business_name", seller_user.get("email"))),
        "buyer_id": winner_user["id"],

        "hammer_price": final_price,
        "seller_commission": 0.0,
        "seller_commission_rate": 0.0,
        "net_payout": final_price,  # seller receives full hammer from buyer directly

        "line_items": [
            {"description": "Vehicle hammer price — settled directly with buyer", "type": "info", "amount": final_price},
            {"description": "BidVex commission on vehicles", "type": "deduction", "amount": 0.0},
        ],

        "settlement_status": "pending_buyer_payment",
        "settlement_deadline": deadline + timedelta(days=3),
        "settled_at": None,
        "created_at": now,
        "updated_at": None,

        "note_en": "Vehicle sales: seller receives full hammer price directly from buyer. BidVex does not collect or hold vehicle sale funds.",
        "note_fr": "Ventes de véhicules : le vendeur reçoit le prix d'adjudication complet directement de l'acheteur. BidVex ne collecte ni ne détient les fonds de vente de véhicules.",
    }

    await db.vehicle_invoices.insert_one(buyer_invoice)
    await db.vehicle_invoices.insert_one(seller_invoice)

    await db.vehicle_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "entity_type": "invoice",
        "entity_id": buyer_invoice["id"],
        "action": "invoice_generated",
        "performed_by": "system",
        "performed_by_role": "system",
        "new_value": {
            "buyer_invoice": buyer_invoice["invoice_number"],
            "seller_invoice": seller_invoice["invoice_number"],
            "buyer_total": bi.total,
            "seller_charge": 0.0,
            "transaction_type": "vehicle",
        },
        "created_at": now,
    })

    logger.info(f"Vehicle invoices generated: buyer={buyer_invoice['invoice_number']} "
                f"total=${bi.total:.2f}, seller={seller_invoice['invoice_number']} charge=$0.00")

    # Send email notifications
    try:
        from services.emails.email_marketplace import (
            send_auction_won_email,
            send_auction_sold_email,
        )
        from services.emails.email_system import send_invoice_created_email
        
        # Send invoice email to buyer
        await send_invoice_created_email(buyer_invoice)
        
        # Send auction won email to buyer (VEHICLE branch with EN/FR legal notice)
        seller_contact = (
            seller_user.get("phone")
            or seller_user.get("email")
            or "Available in your BidVex dashboard"
        )
        seller_display_name = seller_user.get("full_name") or seller_user.get(
            "business_name"
        ) or seller_user.get("name") or seller_user.get("email") or "Seller"

        is_cross_border = bool(
            vehicle_listing.get("is_cross_border")
            or vehicle_listing.get("cross_border_availability")
            or (vehicle_listing.get("country", "CA") not in ("CA", "Canada"))
        )

        await send_auction_won_email(
            to_email=winner_user.get("email"),
            to_name=winner_user.get("full_name", winner_user.get("email")),
            auction_id=buyer_invoice["id"],
            item_name=buyer_invoice["vehicle_title"],
            hammer_price=final_price,
            platform_fee=bi.fees_subtotal,
            seller_name=seller_display_name,
            seller_contact=seller_contact,
            is_vehicle=True,
            is_cross_border=is_cross_border,
            buyer_province=buyer_province,
            payment_deadline=deadline.isoformat() if hasattr(deadline, "isoformat") else str(deadline),
        )
        
        # Send auction sold email to seller
        await send_auction_sold_email(
            seller_email=seller_user.get("email"),
            seller_name=seller_user.get("full_name", seller_user.get("business_name", seller_user.get("email"))),
            vehicle_title=seller_invoice["vehicle_title"],
            final_price=final_price,
            commission=0.0,  # Vehicle: seller pays $0
            net_payout=final_price  # Seller receives full hammer directly
        )
        
        logger.info(f"Sent invoice and auction notification emails for vehicle {vehicle_listing['id']}")
    except Exception as e:
        logger.error(f"Failed to send invoice emails: {e}")
    
    return {
        "buyer_invoice": buyer_invoice,
        "seller_invoice": seller_invoice
    }


async def apply_deposit_credit(db, invoice_id: str, deposit_amount: float) -> dict:
    """Apply bid deposit as credit toward invoice"""
    invoice = await db.vehicle_invoices.find_one({"id": invoice_id})
    if not invoice:
        raise ValueError("Invoice not found")
    
    new_credited = invoice.get("deposit_credited", 0) + deposit_amount
    new_total = invoice["total_amount"] - deposit_amount
    
    await db.vehicle_invoices.update_one(
        {"id": invoice_id},
        {
            "$set": {
                "deposit_credited": new_credited,
                "total_amount": max(0, new_total),
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    return {
        "deposit_credited": new_credited,
        "new_total": max(0, new_total)
    }


async def process_invoice_payment(
    db,
    invoice_id: str,
    payment_amount: float,
    payment_method: str,
    transaction_id: str = None
) -> dict:
    """Process payment for an invoice"""
    invoice = await db.vehicle_invoices.find_one({"id": invoice_id})
    if not invoice:
        raise ValueError("Invoice not found")
    
    now = datetime.now(timezone.utc)
    
    # Calculate total due including any penalties
    total_due = invoice["total_amount"] + invoice.get("penalty_amount", 0)
    paid_so_far = invoice.get("paid_amount", 0) + payment_amount
    
    # Determine new status
    if paid_so_far >= total_due:
        new_status = InvoiceStatus.PAID
    else:
        new_status = invoice["payment_status"]
    
    await db.vehicle_invoices.update_one(
        {"id": invoice_id},
        {
            "$set": {
                "payment_status": new_status,
                "paid_amount": paid_so_far,
                "payment_method": payment_method,
                "paid_at": now if new_status == InvoiceStatus.PAID else None,
                "updated_at": now
            },
            "$push": {
                "payments": {
                    "id": str(uuid.uuid4()),
                    "amount": payment_amount,
                    "method": payment_method,
                    "transaction_id": transaction_id,
                    "processed_at": now
                }
            }
        }
    )
    
    # If buyer invoice is paid, update seller settlement status
    if invoice["invoice_type"] == "buyer" and new_status == InvoiceStatus.PAID:
        await db.vehicle_invoices.update_many(
            {
                "buyer_invoice_id": invoice_id,
                "invoice_type": "seller_settlement"
            },
            {
                "$set": {
                    "settlement_status": "ready",
                    "updated_at": now
                }
            }
        )
    
    # Log audit
    await db.vehicle_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "entity_type": "invoice",
        "entity_id": invoice_id,
        "action": "payment_processed",
        "performed_by": invoice.get("buyer_id") or "system",
        "performed_by_role": "buyer" if invoice["invoice_type"] == "buyer" else "system",
        "new_value": {
            "payment_amount": payment_amount,
            "total_paid": paid_so_far,
            "new_status": new_status
        },
        "created_at": now
    })
    
    # Send payment confirmation email if fully paid
    if new_status == InvoiceStatus.PAID and invoice["invoice_type"] == "buyer":
        try:
            from services.emails.email_system import send_payment_confirmation_email
            # Update invoice with paid_at for the email
            updated_invoice = await db.vehicle_invoices.find_one({"id": invoice_id}, {"_id": 0})
            await send_payment_confirmation_email(updated_invoice)
            logger.info(f"Sent payment confirmation email for invoice {invoice_id}")
        except Exception as e:
            logger.error(f"Failed to send payment confirmation email: {e}")
    
    return {
        "invoice_id": invoice_id,
        "payment_amount": payment_amount,
        "total_paid": paid_so_far,
        "total_due": total_due,
        "status": new_status,
        "fully_paid": new_status == InvoiceStatus.PAID
    }


async def check_and_apply_late_penalties(db) -> List[dict]:
    """
    Check for overdue invoices and apply late penalties
    Should be run daily by cron/scheduler
    """
    now = datetime.now(timezone.utc)
    
    # Find overdue buyer invoices
    overdue_invoices = await db.vehicle_invoices.find({
        "invoice_type": "buyer",
        "payment_status": {"$in": [InvoiceStatus.PENDING, InvoiceStatus.OVERDUE]},
        "payment_deadline": {"$lt": now}
    }).to_list(length=1000)
    
    updated = []
    
    for invoice in overdue_invoices:
        days_overdue = (now - invoice["payment_deadline"]).days
        
        # Calculate penalty
        penalty_info = calculate_late_penalty(
            invoice["total_amount"],
            days_overdue
        )
        
        # Update invoice
        await db.vehicle_invoices.update_one(
            {"id": invoice["id"]},
            {
                "$set": {
                    "payment_status": InvoiceStatus.OVERDUE,
                    "penalty_amount": penalty_info["penalty_amount"],
                    "penalty_applied_at": now,
                    "days_overdue": days_overdue,
                    "updated_at": now
                }
            }
        )
        
        # Flag user account for suspension consideration
        await db.users.update_one(
            {"id": invoice["buyer_id"]},
            {
                "$set": {
                    "has_overdue_invoices": True,
                    "overdue_amount": penalty_info["total_due"]
                },
                "$addToSet": {
                    "overdue_invoice_ids": invoice["id"]
                }
            }
        )
        
        updated.append({
            "invoice_id": invoice["id"],
            "invoice_number": invoice["invoice_number"],
            "days_overdue": days_overdue,
            "penalty_applied": penalty_info["penalty_amount"],
            "total_due": penalty_info["total_due"]
        })
        
        logger.warning(f"Applied late penalty to invoice {invoice['invoice_number']}: "
                      f"${penalty_info['penalty_amount']:.2f} ({days_overdue} days overdue)")
    
    return updated


async def get_invoice_by_id(db, invoice_id: str) -> Optional[dict]:
    """Get invoice by ID"""
    return await db.vehicle_invoices.find_one({"id": invoice_id}, {"_id": 0})


async def get_invoices_for_user(
    db,
    user_id: str,
    invoice_type: str = None,
    status: str = None
) -> List[dict]:
    """Get all invoices for a user (as buyer or seller)"""
    query = {
        "$or": [
            {"buyer_id": user_id},
            {"seller_id": user_id}
        ]
    }
    
    if invoice_type:
        query["invoice_type"] = invoice_type
    if status:
        query["payment_status"] = status
    
    cursor = db.vehicle_invoices.find(query, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=100)


async def get_invoice_summary(db, invoice_id: str) -> dict:
    """Get formatted invoice summary for display"""
    invoice = await get_invoice_by_id(db, invoice_id)
    if not invoice:
        return None
    
    # Calculate time remaining or overdue
    now = datetime.now(timezone.utc)
    deadline = invoice.get("payment_deadline") or invoice.get("due_at")
    
    if deadline:
        if isinstance(deadline, str):
            deadline = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
        
        time_diff = deadline - now
        if time_diff.total_seconds() > 0:
            days_remaining = time_diff.days
            hours_remaining = time_diff.seconds // 3600
            time_status = {
                "status": "pending",
                "days_remaining": days_remaining,
                "hours_remaining": hours_remaining,
                "message": f"{days_remaining} days, {hours_remaining} hours remaining"
            }
        else:
            days_overdue = abs(time_diff.days)
            time_status = {
                "status": "overdue",
                "days_overdue": days_overdue,
                "message": f"{days_overdue} days overdue"
            }
    else:
        time_status = {"status": "unknown"}
    
    return {
        **invoice,
        "time_status": time_status,
        "amount_due": invoice["total_amount"] + invoice.get("penalty_amount", 0) - invoice.get("paid_amount", 0),
        "is_paid": invoice.get("payment_status") == InvoiceStatus.PAID
    }
