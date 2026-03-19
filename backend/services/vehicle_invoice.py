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
    Generate complete invoice for a won vehicle auction
    
    Creates both buyer and seller invoices with:
    - Full pricing breakdown
    - Tax calculations
    - Subscription-based discounts
    - Payment deadline (14 days)
    """
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(days=PAYMENT_DEADLINE_DAYS)
    
    # Get subscription tiers
    buyer_tier = get_subscription_tier(winner_user)
    seller_tier = get_subscription_tier(seller_user)
    
    # Get buyer's province from their profile or listing location
    buyer_province = winner_user.get("province") or vehicle_listing.get("location_province", "ON")
    
    # Calculate buyer pricing
    buyer_pricing = calculate_buyer_pricing(final_price, buyer_province, buyer_tier)
    
    # Calculate seller pricing
    seller_pricing = calculate_seller_pricing(final_price, seller_tier)
    
    # Generate invoice number
    invoice_number = f"VEH-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    
    # Build line items for buyer invoice
    buyer_line_items = [
        {
            "description": f"Winning Bid - {vehicle_listing['year']} {vehicle_listing['make']} {vehicle_listing['model']}",
            "type": "hammer_price",
            "amount": float(buyer_pricing.hammer_price),
            "taxable": True
        },
        {
            "description": f"Buyer Premium ({float(buyer_pricing.buyer_premium_rate) * 100:.1f}%)",
            "type": "buyer_premium",
            "rate": float(buyer_pricing.buyer_premium_rate),
            "amount": float(buyer_pricing.buyer_premium),
            "taxable": True
        },
        {
            "description": "Platform Fee (2.5%)",
            "type": "platform_fee",
            "rate": 0.025,
            "amount": float(buyer_pricing.platform_fee),
            "taxable": True
        }
    ]
    
    # Add tax line items
    tax_breakdown = buyer_pricing.tax_breakdown
    if tax_breakdown.tax_type == "HST":
        buyer_line_items.append({
            "description": f"HST ({float(tax_breakdown.hst_rate) * 100:.2f}%)",
            "type": "tax_hst",
            "rate": float(tax_breakdown.hst_rate),
            "amount": float(tax_breakdown.hst_amount),
            "taxable": False
        })
    else:
        if tax_breakdown.gst_amount > 0:
            buyer_line_items.append({
                "description": f"GST ({float(tax_breakdown.gst_rate) * 100:.1f}%)",
                "type": "tax_gst",
                "rate": float(tax_breakdown.gst_rate),
                "amount": float(tax_breakdown.gst_amount),
                "taxable": False
            })
        if tax_breakdown.pst_amount > 0:
            buyer_line_items.append({
                "description": f"PST ({float(tax_breakdown.pst_rate) * 100:.1f}%)",
                "type": "tax_pst",
                "rate": float(tax_breakdown.pst_rate),
                "amount": float(tax_breakdown.pst_amount),
                "taxable": False
            })
        if tax_breakdown.qst_amount > 0:
            buyer_line_items.append({
                "description": f"QST ({float(tax_breakdown.qst_rate) * 100:.3f}%)",
                "type": "tax_qst",
                "rate": float(tax_breakdown.qst_rate),
                "amount": float(tax_breakdown.qst_amount),
                "taxable": False
            })
    
    # Add subscription discount note if applicable
    if buyer_pricing.discount_applied > 0:
        buyer_line_items.append({
            "description": f"{buyer_tier.value.replace('_', ' ').title()} Member Discount",
            "type": "discount",
            "amount": 0,  # Already reflected in premium rate
            "savings": float(buyer_pricing.discount_applied),
            "taxable": False
        })
    
    # Create buyer invoice document
    buyer_invoice = {
        "id": str(uuid.uuid4()),
        "invoice_number": invoice_number,
        "invoice_type": "buyer",
        
        # References
        "vehicle_id": vehicle_listing["id"],
        "vehicle_vin": vehicle_listing["vin"],
        "vehicle_title": f"{vehicle_listing['year']} {vehicle_listing['make']} {vehicle_listing['model']}",
        "auction_id": vehicle_listing["id"],
        
        # Parties
        "buyer_id": winner_user["id"],
        "buyer_email": winner_user.get("email"),
        "buyer_name": winner_user.get("full_name", winner_user.get("email")),
        "buyer_province": buyer_province,
        "seller_id": vehicle_listing["seller_user_id"],
        
        # Amounts
        "hammer_price": float(buyer_pricing.hammer_price),
        "buyer_premium": float(buyer_pricing.buyer_premium),
        "buyer_premium_rate": float(buyer_pricing.buyer_premium_rate),
        "platform_fee": float(buyer_pricing.platform_fee),
        
        # Taxes
        "tax_type": tax_breakdown.tax_type,
        "tax_gst": float(tax_breakdown.gst_amount),
        "tax_pst": float(tax_breakdown.pst_amount),
        "tax_qst": float(tax_breakdown.qst_amount),
        "tax_hst": float(tax_breakdown.hst_amount),
        "tax_total": float(tax_breakdown.total_tax),
        "tax_rate": float(tax_breakdown.total_rate),
        
        # Subtotals
        "subtotal_before_tax": float(buyer_pricing.subtotal_before_tax),
        "total_amount": float(buyer_pricing.total_payable),
        
        # Subscription
        "subscription_tier": buyer_tier.value,
        "subscription_discount": float(buyer_pricing.discount_applied),
        
        # Line Items
        "line_items": buyer_line_items,
        
        # Payment
        "payment_status": InvoiceStatus.PENDING,
        "payment_deadline": deadline,
        "payment_method": None,
        "paid_at": None,
        "paid_amount": 0.0,
        
        # Deposit credit (if applicable)
        "deposit_credited": 0.0,
        "deposit_id": None,
        
        # Late payment
        "penalty_amount": 0.0,
        "penalty_applied_at": None,
        
        # Timestamps
        "created_at": now,
        "updated_at": None,
        "sent_at": None,
        "due_at": deadline
    }
    
    # Create seller invoice/settlement document
    seller_invoice = {
        "id": str(uuid.uuid4()),
        "invoice_number": f"SET-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}",
        "invoice_type": "seller_settlement",
        
        # References
        "vehicle_id": vehicle_listing["id"],
        "vehicle_vin": vehicle_listing["vin"],
        "vehicle_title": f"{vehicle_listing['year']} {vehicle_listing['make']} {vehicle_listing['model']}",
        "auction_id": vehicle_listing["id"],
        "buyer_invoice_id": buyer_invoice["id"],
        
        # Parties
        "seller_id": vehicle_listing["seller_user_id"],
        "seller_email": seller_user.get("email"),
        "seller_name": seller_user.get("full_name", seller_user.get("business_name", seller_user.get("email"))),
        "buyer_id": winner_user["id"],
        
        # Amounts
        "hammer_price": float(seller_pricing.hammer_price),
        "seller_commission": float(seller_pricing.seller_commission),
        "seller_commission_rate": float(seller_pricing.seller_commission_rate),
        "net_payout": float(seller_pricing.net_payout),
        
        # Subscription
        "subscription_tier": seller_tier.value,
        "subscription_discount": float(seller_pricing.discount_applied),
        
        # Line Items
        "line_items": [
            {
                "description": f"Sale - {vehicle_listing['year']} {vehicle_listing['make']} {vehicle_listing['model']}",
                "type": "hammer_price",
                "amount": float(seller_pricing.hammer_price)
            },
            {
                "description": f"BidVex Commission ({float(seller_pricing.seller_commission_rate) * 100:.1f}%)",
                "type": "seller_commission",
                "rate": float(seller_pricing.seller_commission_rate),
                "amount": -float(seller_pricing.seller_commission)  # Negative for deduction
            }
        ],
        
        # Settlement
        "settlement_status": "pending_buyer_payment",  # pending_buyer_payment -> ready -> paid -> completed
        "settlement_deadline": deadline + timedelta(days=3),  # 3 days after buyer payment deadline
        "settled_at": None,
        "settlement_method": None,
        
        # Late penalty (if seller fees owed)
        "penalty_amount": 0.0,
        "penalty_applied_at": None,
        
        # Timestamps
        "created_at": now,
        "updated_at": None
    }
    
    # Insert invoices
    await db.vehicle_invoices.insert_one(buyer_invoice)
    await db.vehicle_invoices.insert_one(seller_invoice)
    
    # Log audit
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
            "total_amount": float(buyer_pricing.total_payable)
        },
        "created_at": now
    })
    
    logger.info(f"Generated invoices for vehicle {vehicle_listing['id']}: "
                f"Buyer={buyer_invoice['invoice_number']}, Seller={seller_invoice['invoice_number']}")
    
    # Send email notifications
    try:
        from services.email_notifications import (
            send_invoice_created_email,
            send_auction_won_email,
            send_auction_sold_email
        )
        
        # Send invoice email to buyer
        await send_invoice_created_email(buyer_invoice)
        
        # Send auction won email to buyer
        await send_auction_won_email(
            buyer_email=winner_user.get("email"),
            buyer_name=winner_user.get("full_name", winner_user.get("email")),
            vehicle_title=buyer_invoice["vehicle_title"],
            final_price=float(buyer_pricing.hammer_price),
            invoice_id=buyer_invoice["id"],
            buyers_premium_rate=float(vehicle_listing.get("custom_buyer_premium_rate") or 0.05)
        )
        
        # Send auction sold email to seller
        await send_auction_sold_email(
            seller_email=seller_user.get("email"),
            seller_name=seller_user.get("full_name", seller_user.get("business_name", seller_user.get("email"))),
            vehicle_title=seller_invoice["vehicle_title"],
            final_price=float(seller_pricing.hammer_price),
            commission=float(seller_pricing.seller_commission),
            net_payout=float(seller_pricing.net_payout)
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
            from services.email_notifications import send_payment_confirmation_email
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
