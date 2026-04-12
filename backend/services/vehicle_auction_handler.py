"""
BidVex Vehicle Auction - Auction End Handler
Automated auction closing, winner determination, and invoice generation
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import uuid
import logging
import asyncio

from services.vehicle_invoice import generate_vehicle_invoice, InvoiceStatus
from services.vehicle_pricing import get_subscription_tier

logger = logging.getLogger(__name__)


class AuctionEndResult:
    """Result of auction end processing"""
    def __init__(self):
        self.vehicle_id: str = None
        self.status: str = None  # sold, reserve_not_met, no_bids, cancelled
        self.winner_id: str = None
        self.final_price: float = 0
        self.buyer_invoice_id: str = None
        self.seller_invoice_id: str = None
        self.error: str = None


async def process_ended_auction(db, vehicle_listing: dict) -> AuctionEndResult:
    """
    Process a single ended auction
    
    Steps:
    1. Lock auction (prevent more bids)
    2. Determine winner
    3. Check reserve
    4. Generate invoices
    5. Update listing status
    6. Notify parties
    """
    result = AuctionEndResult()
    result.vehicle_id = vehicle_listing["id"]
    
    now = datetime.now(timezone.utc)
    
    try:
        # Get highest bid
        highest_bid = await db.vehicle_bids.find_one(
            {
                "vehicle_id": vehicle_listing["id"],
                "status": {"$in": ["active", "winning"]}
            },
            sort=[("amount", -1)]
        )
        
        if not highest_bid:
            # No bids - auction ended without winner
            result.status = "no_bids"
            
            await db.vehicle_listings.update_one(
                {"id": vehicle_listing["id"]},
                {
                    "$set": {
                        "status": "ended",
                        "end_reason": "no_bids",
                        "updated_at": now
                    }
                }
            )
            
            logger.info(f"Auction {vehicle_listing['id']} ended with no bids")
            return result
        
        final_price = highest_bid["amount"]
        winner_id = highest_bid["bidder_id"]
        
        # Check reserve price
        reserve_price = vehicle_listing.get("reserve_price")
        reserve_met = vehicle_listing.get("reserve_met", False)
        
        if reserve_price and not reserve_met and final_price < reserve_price:
            # Reserve not met
            result.status = "reserve_not_met"
            result.final_price = final_price
            
            await db.vehicle_listings.update_one(
                {"id": vehicle_listing["id"]},
                {
                    "$set": {
                        "status": "ended",
                        "end_reason": "reserve_not_met",
                        "final_price": final_price,
                        "updated_at": now
                    }
                }
            )
            
            # Update bid status
            await db.vehicle_bids.update_one(
                {"id": highest_bid["id"]},
                {"$set": {"status": "reserve_not_met"}}
            )
            
            logger.info(f"Auction {vehicle_listing['id']} ended - reserve not met "
                       f"(bid: ${final_price}, reserve: ${reserve_price})")
            return result
        
        # Get winner and seller user records
        winner_user = await db.users.find_one({"id": winner_id})
        seller_user = await db.users.find_one({"id": vehicle_listing["seller_user_id"]})
        
        if not winner_user or not seller_user:
            result.status = "error"
            result.error = "Could not find winner or seller user"
            logger.error(f"Auction {vehicle_listing['id']}: Missing user records")
            return result
        
        # Generate invoices
        invoices = await generate_vehicle_invoice(
            db,
            vehicle_listing,
            winner_user,
            seller_user,
            final_price
        )
        
        # Update listing as SOLD
        await db.vehicle_listings.update_one(
            {"id": vehicle_listing["id"]},
            {
                "$set": {
                    "status": "sold",
                    "winner_id": winner_id,
                    "final_price": final_price,
                    "sold_at": now,
                    "buyer_invoice_id": invoices["buyer_invoice"]["id"],
                    "seller_invoice_id": invoices["seller_invoice"]["id"],
                    "updated_at": now
                }
            }
        )
        
        # Update winning bid status
        await db.vehicle_bids.update_one(
            {"id": highest_bid["id"]},
            {"$set": {"status": "won"}}
        )
        
        # Mark other bids as lost
        await db.vehicle_bids.update_many(
            {
                "vehicle_id": vehicle_listing["id"],
                "id": {"$ne": highest_bid["id"]},
                "status": {"$in": ["active", "outbid"]}
            },
            {"$set": {"status": "lost"}}
        )
        
        # Update seller stats
        await db.vehicle_sellers.update_one(
            {"id": vehicle_listing["seller_id"]},
            {
                "$inc": {
                    "total_sold": 1,
                    "total_revenue": final_price
                }
            }
        )
        
        # Credit deposit if applicable
        if vehicle_listing.get("requires_deposit"):
            deposit = await db.vehicle_bid_deposits.find_one({
                "vehicle_id": vehicle_listing["id"],
                "bidder_id": winner_id,
                "status": "paid"
            })
            
            if deposit:
                # Apply deposit as credit to invoice
                from services.vehicle_invoice import apply_deposit_credit
                await apply_deposit_credit(
                    db,
                    invoices["buyer_invoice"]["id"],
                    deposit["amount"]
                )
                
                # Mark deposit as applied
                await db.vehicle_bid_deposits.update_one(
                    {"id": deposit["id"]},
                    {"$set": {"status": "applied", "applied_at": now}}
                )
        
        # Refund deposits to non-winners
        await db.vehicle_bid_deposits.update_many(
            {
                "vehicle_id": vehicle_listing["id"],
                "bidder_id": {"$ne": winner_id},
                "status": "paid"
            },
            {
                "$set": {
                    "status": "refunded",
                    "refunded_at": now,
                    "refund_reason": "non_winning_bidder"
                }
            }
        )
        
        result.status = "sold"
        result.winner_id = winner_id
        result.final_price = final_price
        result.buyer_invoice_id = invoices["buyer_invoice"]["id"]
        result.seller_invoice_id = invoices["seller_invoice"]["id"]
        
        logger.info(f"Auction {vehicle_listing['id']} SOLD to {winner_id} for ${final_price}")
        
        # ── AUTO-CHARGE: Platform Fee (2.5% + Stripe recovery) ──
        try:
            from services.vehicle_fee_service import create_vehicle_fee_charge
            fee_result = await create_vehicle_fee_charge(
                db,
                auction_id=vehicle_listing["id"],
                buyer_id=winner_id,
                hammer_price=final_price,
            )
            if fee_result.get("success"):
                logger.info(f"Platform fee charged for auction {vehicle_listing['id']}: PI={fee_result['payment_intent_id']}")
            else:
                logger.error(f"Platform fee charge FAILED for auction {vehicle_listing['id']}: {fee_result.get('error')}")
        except Exception as fee_err:
            logger.error(f"Platform fee charge exception for auction {vehicle_listing['id']}: {fee_err}")
        
        # Log audit
        await db.vehicle_audit_logs.insert_one({
            "id": str(uuid.uuid4()),
            "entity_type": "vehicle",
            "entity_id": vehicle_listing["id"],
            "action": "auction_ended_sold",
            "performed_by": "system",
            "performed_by_role": "system",
            "new_value": {
                "winner_id": winner_id,
                "final_price": final_price,
                "buyer_invoice": invoices["buyer_invoice"]["invoice_number"],
                "seller_invoice": invoices["seller_invoice"]["invoice_number"]
            },
            "created_at": now
        })
        
        return result
        
    except Exception as e:
        result.status = "error"
        result.error = str(e)
        logger.exception(f"Error processing auction {vehicle_listing['id']}: {e}")
        return result


async def process_all_ended_auctions(db) -> List[AuctionEndResult]:
    """
    Process all auctions that have ended but not yet processed
    Should be run by cron/scheduler every minute
    """
    now = datetime.now(timezone.utc)
    
    # Find all active auctions that have ended
    ended_auctions = await db.vehicle_listings.find({
        "status": "active",
        "end_time": {"$lte": now}
    }).to_list(length=100)
    
    results = []
    
    for listing in ended_auctions:
        result = await process_ended_auction(db, listing)
        results.append(result)
        
        # Small delay to prevent overwhelming the database
        await asyncio.sleep(0.1)
    
    if results:
        logger.info(f"Processed {len(results)} ended auctions: "
                   f"{sum(1 for r in results if r.status == 'sold')} sold, "
                   f"{sum(1 for r in results if r.status == 'no_bids')} no bids, "
                   f"{sum(1 for r in results if r.status == 'reserve_not_met')} reserve not met")
    
    return results


async def activate_scheduled_auctions(db) -> int:
    """
    Activate approved auctions that have reached their start time
    Should be run by cron/scheduler every minute
    """
    now = datetime.now(timezone.utc)
    
    result = await db.vehicle_listings.update_many(
        {
            "status": "approved",
            "start_time": {"$lte": now}
        },
        {
            "$set": {
                "status": "active",
                "activated_at": now,
                "updated_at": now
            }
        }
    )
    
    if result.modified_count > 0:
        logger.info(f"Activated {result.modified_count} scheduled auctions")
    
    return result.modified_count


async def run_auction_scheduler(db):
    """
    Main scheduler function - runs all periodic tasks
    Call this from a background worker or cron job
    """
    logger.info("Running auction scheduler...")
    
    # 1. Activate scheduled auctions
    activated = await activate_scheduled_auctions(db)
    
    # 2. Process ended auctions
    ended_results = await process_all_ended_auctions(db)
    
    # 3. Check and apply late penalties (run daily, but safe to run more often)
    from services.vehicle_invoice import check_and_apply_late_penalties
    penalties = await check_and_apply_late_penalties(db)
    
    return {
        "auctions_activated": activated,
        "auctions_ended": len(ended_results),
        "auctions_sold": sum(1 for r in ended_results if r.status == "sold"),
        "penalties_applied": len(penalties)
    }
