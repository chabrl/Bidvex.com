"""
BidVex Vehicle Auction - Stripe Payment Service
Handles invoice payments, deposit processing, and refunds
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from decimal import Decimal
import uuid
import stripe

logger = logging.getLogger(__name__)

# Payment types for vehicle auctions
class PaymentType:
    INVOICE = "vehicle_invoice"
    DEPOSIT = "vehicle_deposit"
    LATE_PENALTY = "late_penalty"


class PaymentService:
    """Stripe payment service for vehicle auctions"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("STRIPE_API_KEY")
        stripe.api_key = self.api_key
    
    async def create_invoice_checkout(
        self,
        db,
        invoice_id: str,
        user_id: str,
        base_url: str,
        origin_url: str
    ) -> Dict[str, Any]:
        """
        Create Stripe checkout session for invoice payment
        Amount is determined server-side from invoice
        """
        # Get invoice from database
        invoice = await db.vehicle_invoices.find_one({"id": invoice_id})
        if not invoice:
            raise ValueError("Invoice not found")
        
        # Verify user owns this invoice
        if invoice.get("buyer_id") != user_id:
            raise ValueError("Not authorized to pay this invoice")
        
        # Check if already paid
        if invoice.get("payment_status") == "paid":
            raise ValueError("Invoice already paid")
        
        # Calculate amount due (including any penalties)
        amount_due = (
            invoice.get("total_amount", 0) + 
            invoice.get("penalty_amount", 0) - 
            invoice.get("paid_amount", 0)
        )
        
        if amount_due <= 0:
            raise ValueError("No amount due")
        
        # Create checkout instance
        webhook_url = f"{base_url}api/webhook/stripe"
        
        # Build URLs from frontend origin
        success_url = f"{origin_url}/vehicle-auctions/invoices/{invoice_id}?session_id={{CHECKOUT_SESSION_ID}}&status=success"
        cancel_url = f"{origin_url}/vehicle-auctions/invoices/{invoice_id}?status=cancelled"
        
        # Create Stripe checkout session directly
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "cad",
                    "unit_amount": int(float(amount_due) * 100),
                    "product_data": {"name": f"Invoice {invoice.get('invoice_number', invoice_id)}"},
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "payment_type": PaymentType.INVOICE,
                "invoice_id": invoice_id,
                "invoice_number": invoice.get("invoice_number", ""),
                "user_id": user_id,
                "vehicle_id": invoice.get("vehicle_id", "")
            },
        )
        
        # Record transaction in database
        transaction_id = str(uuid.uuid4())
        await db.payment_transactions.insert_one({
            "id": transaction_id,
            "session_id": session.id,
            "payment_type": PaymentType.INVOICE,
            "invoice_id": invoice_id,
            "user_id": user_id,
            "amount": amount_due,
            "currency": "CAD",
            "payment_status": "initiated",
            "metadata": {
                "payment_type": PaymentType.INVOICE,
                "invoice_id": invoice_id,
                "user_id": user_id,
            },
            "created_at": datetime.now(timezone.utc)
        })
        
        logger.info(f"Created checkout session {session.id} for invoice {invoice_id}")
        
        return {
            "checkout_url": session.url,
            "session_id": session.id,
            "amount": amount_due,
            "currency": "CAD",
            "invoice_number": invoice.get("invoice_number")
        }
    
    async def create_deposit_checkout(
        self,
        db,
        vehicle_id: str,
        user_id: str,
        deposit_amount: float,
        base_url: str,
        origin_url: str
    ) -> Dict[str, Any]:
        """
        Create Stripe checkout session for bid deposit
        Amount is fixed per vehicle listing (not user-controllable)
        """
        # Get vehicle listing to verify deposit amount
        listing = await db.vehicle_listings.find_one({"id": vehicle_id})
        if not listing:
            raise ValueError("Vehicle not found")
        
        if not listing.get("requires_deposit"):
            raise ValueError("This vehicle does not require a deposit")
        
        # Use server-side deposit amount (never trust frontend)
        amount = listing.get("deposit_amount", 500)
        
        # Check if deposit already paid
        existing_deposit = await db.vehicle_bid_deposits.find_one({
            "vehicle_id": vehicle_id,
            "bidder_id": user_id,
            "status": {"$in": ["paid", "pending"]}
        })
        
        if existing_deposit:
            raise ValueError("Deposit already paid or pending")
        
        # Create checkout session
        webhook_url = f"{base_url}api/webhook/stripe"
        
        # Build URLs from frontend origin
        success_url = f"{origin_url}/vehicle-auctions/{vehicle_id}?session_id={{CHECKOUT_SESSION_ID}}&deposit=success"
        cancel_url = f"{origin_url}/vehicle-auctions/{vehicle_id}?deposit=cancelled"
        
        # Create Stripe checkout session directly
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "cad",
                    "unit_amount": int(float(amount) * 100),
                    "product_data": {"name": f"Bid Deposit - Vehicle {vehicle_id[:8]}"},
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "payment_type": PaymentType.DEPOSIT,
                "vehicle_id": vehicle_id,
                "user_id": user_id
            },
        )
        
        # Create pending deposit record
        deposit_id = str(uuid.uuid4())
        await db.vehicle_bid_deposits.insert_one({
            "id": deposit_id,
            "vehicle_id": vehicle_id,
            "bidder_id": user_id,
            "amount": amount,
            "status": "pending",
            "session_id": session.id,
            "created_at": datetime.now(timezone.utc)
        })
        
        # Record transaction
        await db.payment_transactions.insert_one({
            "id": str(uuid.uuid4()),
            "session_id": session.id,
            "payment_type": PaymentType.DEPOSIT,
            "vehicle_id": vehicle_id,
            "deposit_id": deposit_id,
            "user_id": user_id,
            "amount": amount,
            "currency": "CAD",
            "payment_status": "initiated",
            "metadata": {
                "payment_type": PaymentType.DEPOSIT,
                "vehicle_id": vehicle_id,
                "user_id": user_id
            },
            "created_at": datetime.now(timezone.utc)
        })
        
        logger.info(f"Created deposit checkout {session.id} for vehicle {vehicle_id}")
        
        return {
            "checkout_url": session.url,
            "session_id": session.id,
            "amount": amount,
            "currency": "CAD",
            "deposit_id": deposit_id
        }
    
    async def check_payment_status(
        self,
        db,
        session_id: str,
        base_url: str
    ) -> Dict[str, Any]:
        """Check Stripe checkout session status and update database"""
        # Get transaction record
        transaction = await db.payment_transactions.find_one({"session_id": session_id})
        if not transaction:
            raise ValueError("Transaction not found")
        
        # Check if already processed
        if transaction.get("payment_status") == "paid":
            return {
                "status": "paid",
                "already_processed": True,
                "payment_type": transaction.get("payment_type")
            }
        
        # Get status from Stripe directly
        stripe_session = stripe.checkout.Session.retrieve(session_id)
        payment_status = "paid" if stripe_session.payment_status == "paid" else stripe_session.payment_status
        
        now = datetime.now(timezone.utc)
        
        # Update transaction status
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "payment_status": payment_status,
                    "stripe_status": stripe_session.status,
                    "updated_at": now
                }
            }
        )
        
        # If payment successful, update related records
        if payment_status == "paid":
            payment_type = transaction.get("payment_type")
            
            if payment_type == PaymentType.INVOICE:
                # Update invoice as paid
                invoice_id = transaction.get("invoice_id")
                amount = transaction.get("amount", 0)
                
                await db.vehicle_invoices.update_one(
                    {"id": invoice_id},
                    {
                        "$set": {
                            "payment_status": "paid",
                            "paid_amount": amount,
                            "payment_method": "stripe",
                            "paid_at": now,
                            "stripe_session_id": session_id,
                            "updated_at": now
                        }
                    }
                )
                
                # Update seller settlement status
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
                
                # Clear overdue flags from user
                invoice = await db.vehicle_invoices.find_one({"id": invoice_id})
                if invoice:
                    await db.users.update_one(
                        {"id": invoice.get("buyer_id")},
                        {
                            "$pull": {"overdue_invoice_ids": invoice_id},
                            "$set": {"has_overdue_invoices": False}
                        }
                    )
                
                logger.info(f"Invoice {invoice_id} marked as paid via session {session_id}")
                
            elif payment_type == PaymentType.DEPOSIT:
                # Update deposit as paid
                deposit_id = transaction.get("deposit_id")
                vehicle_id = transaction.get("vehicle_id")
                
                await db.vehicle_bid_deposits.update_one(
                    {"id": deposit_id},
                    {
                        "$set": {
                            "status": "paid",
                            "paid_at": now,
                            "stripe_session_id": session_id
                        }
                    }
                )
                
                logger.info(f"Deposit {deposit_id} marked as paid for vehicle {vehicle_id}")
        
        return {
            "status": stripe_session.status,
            "payment_status": payment_status,
            "amount": stripe_session.amount_total / 100 if stripe_session.amount_total else transaction.get("amount"),
            "currency": stripe_session.currency.upper() if stripe_session.currency else "CAD",
            "payment_type": transaction.get("payment_type"),
            "metadata": dict(stripe_session.metadata) if stripe_session.metadata else {}
        }
    
    async def process_deposit_refund(
        self,
        db,
        deposit_id: str,
        reason: str = "non_winning_bidder"
    ) -> Dict[str, Any]:
        """
        Process refund for a bid deposit
        Note: In production, this would call Stripe Refund API
        For now, we mark the deposit as refunded
        """
        deposit = await db.vehicle_bid_deposits.find_one({"id": deposit_id})
        if not deposit:
            raise ValueError("Deposit not found")
        
        if deposit.get("status") != "paid":
            raise ValueError(f"Cannot refund deposit with status: {deposit.get('status')}")
        
        now = datetime.now(timezone.utc)
        
        # Mark deposit as refunded
        await db.vehicle_bid_deposits.update_one(
            {"id": deposit_id},
            {
                "$set": {
                    "status": "refunded",
                    "refunded_at": now,
                    "refund_reason": reason
                }
            }
        )
        
        # Log audit
        await db.vehicle_audit_logs.insert_one({
            "id": str(uuid.uuid4()),
            "entity_type": "deposit",
            "entity_id": deposit_id,
            "action": "deposit_refunded",
            "performed_by": "system",
            "performed_by_role": "system",
            "new_value": {
                "amount": deposit.get("amount"),
                "reason": reason
            },
            "created_at": now
        })
        
        logger.info(f"Deposit {deposit_id} refunded: {reason}")
        
        return {
            "deposit_id": deposit_id,
            "amount_refunded": deposit.get("amount"),
            "reason": reason,
            "status": "refunded"
        }


# Export singleton-like function
_payment_service = None

def get_payment_service() -> PaymentService:
    global _payment_service
    if _payment_service is None:
        _payment_service = PaymentService()
    return _payment_service
