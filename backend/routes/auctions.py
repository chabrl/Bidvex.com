"""
BidVex Auctions Router
Handles auction lifecycle management including:
- Auction end processing
- Winner determination
- Automated handshake triggers
- Push notifications for auction events
- Bid placement with anti-sniping
- Bid history & auto-bid
- Buy Now purchases
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from deps import User, get_current_user
from models import Bid, BidCreate, BuyNowPurchase, BuyNowTransaction, AutoBid
from rate_limit import limiter as _limiter
from utils import (
    get_marketplace_settings,
    get_minimum_increment,
    get_epoch_timestamp,
    get_server_timestamp,
)
import logging
import uuid as uuid_mod

logger = logging.getLogger(__name__)

auctions_router = APIRouter(prefix="/auctions", tags=["Auctions"])

# We also register bid routes on a separate router (no prefix) for /bids, /buy-now
bids_router = APIRouter(tags=["Bids"])

# Instances will be injected from main app
_db = None
_notification_manager = None
_ws_manager = None  # WebSocket ConnectionManager for bid broadcasts
_sms_service_getter = None  # function to get SMS service


def set_db(db_instance):
    """Set database instance from main app"""
    global _db
    _db = db_instance


def set_notification_manager(manager):
    """Set notification manager from main app"""
    global _notification_manager
    _notification_manager = manager


def set_ws_manager(manager):
    """Set WebSocket connection manager for bid broadcasts"""
    global _ws_manager
    _ws_manager = manager


def set_sms_service_getter(getter_fn):
    """Set SMS notification service getter"""
    global _sms_service_getter
    _sms_service_getter = getter_fn


def get_db():
    """Get database instance"""
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


def get_notification_manager():
    """Get notification WebSocket manager"""
    return _notification_manager


# ========== PROCESS ENDED AUCTIONS ==========
async def process_ended_auctions():
    """
    Background task to process all auctions that have ended.
    This is called by the scheduler every minute.
    
    For each ended auction:
    1. Determine the winner (highest bidder)
    2. Update auction status to 'ended'
    3. Create automated handshake conversation
    4. Send push notifications
    5. Update seller analytics
    """
    from routes.messages import create_auction_won_conversation
    
    db = get_db()
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    
    processed_count = 0
    
    try:
        # ========== PROCESS SINGLE-ITEM LISTINGS ==========
        ended_listings = await db.listings.find({
            "status": "active",
            "auction_end_date": {"$lte": now_str}
        }).to_list(100)
        
        for listing in ended_listings:
            try:
                listing_id = listing["id"]
                seller_id = listing["seller_id"]
                
                # Get highest bid
                highest_bid = await db.bids.find_one(
                    {"listing_id": listing_id},
                    sort=[("amount", -1)]
                )
                
                if highest_bid:
                    winner_id = highest_bid["bidder_id"]
                    final_price = highest_bid["amount"]
                    
                    # Payment deadline: 14 days from auction close
                    payment_deadline = (now + timedelta(days=14)).isoformat()
                    
                    # Update listing status with payment tracking
                    await db.listings.update_one(
                        {"id": listing_id},
                        {"$set": {
                            "status": "ended",
                            "winner_id": winner_id,
                            "final_price": final_price,
                            "ended_at": now_str,
                            "payment_status": "pending_payment",
                            "payment_deadline": payment_deadline,
                            "reminder_sent": False,
                            "overdue_notified": False,
                        }}
                    )
                    
                    # Create automated handshake conversation
                    conversation_id = await create_auction_won_conversation(
                        db=db,
                        listing_id=listing_id,
                        seller_id=seller_id,
                        winner_id=winner_id,
                        final_price=final_price,
                        item_title=listing.get("title", "Unknown Item")
                    )
                    
                    if conversation_id:
                        logger.info(f"✅ Created handshake for listing {listing_id}, winner: {winner_id}")
                    
                    # Send push notification to winner
                    try:
                        notification_manager = get_notification_manager()
                        await notification_manager.send_to_user(winner_id, {
                            "type": "AUCTION_WON",
                            "title": "Congratulations! You Won!",
                            "message": f"You won the auction for {listing.get('title')} at ${final_price:.2f}",
                            "listing_id": listing_id,
                            "conversation_id": conversation_id,
                            "final_price": final_price
                        })
                        
                        # Also notify seller
                        await notification_manager.send_to_user(seller_id, {
                            "type": "AUCTION_SOLD",
                            "title": "Item Sold!",
                            "message": f"Your item {listing.get('title')} sold for ${final_price:.2f}",
                            "listing_id": listing_id,
                            "winner_id": winner_id,
                            "final_price": final_price
                        })
                    except Exception as e:
                        logger.warning(f"Could not send push notification: {e}")
                    
                    # Create notification records with checkout CTA
                    await db.notifications.insert_many([
                        {
                            "id": str(uuid4()),
                            "user_id": winner_id,
                            "type": "auction_won",
                            "title": "Congratulations! You Won!",
                            "message": f"You won the auction for {listing.get('title')} at ${final_price:.2f}. Complete payment within 14 days.",
                            "listing_id": listing_id,
                            "data": {
                                "checkout_url": f"/checkout/{listing_id}",
                                "payment_deadline": payment_deadline,
                            },
                            "read": False,
                            "created_at": now_str
                        },
                        {
                            "id": str(uuid4()),
                            "user_id": seller_id,
                            "type": "auction_sold",
                            "title": "Item Sold!",
                            "message": f"Your item {listing.get('title')} sold for ${final_price:.2f}",
                            "listing_id": listing_id,
                            "read": False,
                            "created_at": now_str
                        }
                    ])
                    
                    # Send "You Won!" email via SendGrid
                    try:
                        winner_user = await db.users.find_one({"id": winner_id}, {"_id": 0, "email": 1, "name": 1})
                        if winner_user and winner_user.get("email"):
                            from services.email_notifications import send_auction_won_email
                            await send_auction_won_email(
                                winner_email=winner_user["email"],
                                winner_name=winner_user.get("name", "Winner"),
                                item_title=listing.get("title", "Item"),
                                final_price=final_price,
                                listing_id=listing_id,
                                payment_deadline=payment_deadline,
                            )
                            logger.info(f"Sent 'You Won' email to {winner_user['email']} for listing {listing_id}")
                    except Exception as email_err:
                        logger.warning(f"Failed to send winner email for listing {listing_id}: {email_err}")
                    
                    processed_count += 1
                    
                else:
                    # No bids - auction ended without winner
                    await db.listings.update_one(
                        {"id": listing_id},
                        {"$set": {
                            "status": "ended_no_bids",
                            "ended_at": now_str
                        }}
                    )
                    
                    # Notify seller
                    await db.notifications.insert_one({
                        "id": str(uuid4()),
                        "user_id": seller_id,
                        "type": "auction_ended_no_bids",
                        "title": "Auction Ended",
                        "message": f"Your auction for {listing.get('title')} ended without any bids.",
                        "listing_id": listing_id,
                        "read": False,
                        "created_at": now_str
                    })
                    
            except Exception as e:
                logger.error(f"Error processing ended listing {listing.get('id')}: {e}")
        
        # ========== PROCESS MULTI-ITEM AUCTION LOTS ==========
        # Check for individual lots that have ended
        ended_lots = await db.lots.find({
            "lot_status": "active",
            "auction_end_date": {"$lte": now_str}
        }).to_list(500)
        
        for lot in ended_lots:
            try:
                lot_id = lot["id"]
                auction_id = lot["auction_id"]
                
                # Get auction details
                auction = await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0})
                if not auction:
                    continue
                
                seller_id = auction["seller_id"]
                
                # Get highest bid for this lot
                highest_bid = await db.lot_bids.find_one(
                    {"lot_id": lot_id},
                    sort=[("amount", -1)]
                )
                
                if highest_bid:
                    winner_id = highest_bid["bidder_id"]
                    final_price = highest_bid["amount"]
                    
                    # Update lot status
                    await db.lots.update_one(
                        {"id": lot_id},
                        {"$set": {
                            "lot_status": "sold",
                            "winner_id": winner_id,
                            "final_price": final_price,
                            "ended_at": now_str
                        }}
                    )
                    
                    # Create automated handshake
                    lot_title = f"{auction.get('title')} - Lot #{lot.get('lot_number', '')}"
                    conversation_id = await create_auction_won_conversation(
                        db=db,
                        listing_id=lot_id,
                        seller_id=seller_id,
                        winner_id=winner_id,
                        final_price=final_price,
                        item_title=lot_title
                    )
                    
                    if conversation_id:
                        logger.info(f"✅ Created handshake for lot {lot_id}, winner: {winner_id}")
                    
                    # Create notifications
                    await db.notifications.insert_many([
                        {
                            "id": str(uuid4()),
                            "user_id": winner_id,
                            "type": "lot_won",
                            "title": "🎉 You Won a Lot!",
                            "message": f"You won {lot_title} at ${final_price:.2f}",
                            "lot_id": lot_id,
                            "auction_id": auction_id,
                            "read": False,
                            "created_at": now_str
                        },
                        {
                            "id": str(uuid4()),
                            "user_id": seller_id,
                            "type": "lot_sold",
                            "title": "💰 Lot Sold!",
                            "message": f"{lot_title} sold for ${final_price:.2f}",
                            "lot_id": lot_id,
                            "read": False,
                            "created_at": now_str
                        }
                    ])
                    
                    processed_count += 1
                    
                else:
                    # No bids on lot
                    await db.lots.update_one(
                        {"id": lot_id},
                        {"$set": {
                            "lot_status": "ended_no_bids",
                            "ended_at": now_str
                        }}
                    )
                    
            except Exception as e:
                logger.error(f"Error processing ended lot {lot.get('id')}: {e}")
        
        # ========== UPDATE MULTI-ITEM AUCTION STATUS ==========
        # Check if all lots in an auction have ended
        active_auctions = await db.multi_item_listings.find({
            "status": "active"
        }).to_list(100)
        
        for auction in active_auctions:
            auction_id = auction["id"]
            
            # First check if lots are in separate collection
            active_lots_count = await db.lots.count_documents({
                "auction_id": auction_id,
                "lot_status": "active"
            })
            
            # If no separate lots exist, check embedded lots array
            if active_lots_count == 0:
                embedded_lots = auction.get("lots", [])
                active_lots_count = sum(1 for lot in embedded_lots if lot.get("lot_status") == "active")
            
            if active_lots_count == 0:
                # All lots have ended - close the auction
                await db.multi_item_listings.update_one(
                    {"id": auction_id},
                    {"$set": {
                        "status": "ended",
                        "ended_at": now_str
                    }}
                )
                logger.info(f"✅ Auction {auction_id} fully ended - all lots processed")
        
        if processed_count > 0:
            logger.info(f"✅ Processed {processed_count} ended auctions/lots")
            
    except Exception as e:
        logger.error(f"❌ Error in process_ended_auctions: {e}")


# ========== MANUAL TRIGGER ENDPOINT ==========
@auctions_router.post("/process-ended")
async def trigger_process_ended(background_tasks: BackgroundTasks):
    """
    Manually trigger processing of ended auctions
    Admin endpoint for testing or immediate processing
    """
    background_tasks.add_task(process_ended_auctions)
    return {"status": "processing", "message": "Auction end processing triggered"}


# ========== GET AUCTION END STATUS ==========
@auctions_router.get("/end-status/{auction_id}")
async def get_auction_end_status(auction_id: str):
    """
    Get the end status of an auction including winner info
    """
    db = get_db()
    
    # Check listings
    listing = await db.listings.find_one({"id": auction_id}, {"_id": 0})
    if listing:
        return {
            "type": "single_listing",
            "id": auction_id,
            "status": listing.get("status"),
            "winner_id": listing.get("winner_id"),
            "final_price": listing.get("final_price"),
            "ended_at": listing.get("ended_at"),
            "title": listing.get("title")
        }
    
    # Check multi-item listings
    auction = await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0})
    if auction:
        # Get lot summaries
        lots = await db.lots.find(
            {"auction_id": auction_id},
            {"_id": 0, "id": 1, "lot_number": 1, "lot_status": 1, "winner_id": 1, "final_price": 1}
        ).to_list(1000)
        
        return {
            "type": "multi_item_auction",
            "id": auction_id,
            "status": auction.get("status"),
            "title": auction.get("title"),
            "ended_at": auction.get("ended_at"),
            "lots": lots,
            "total_lots": len(lots),
            "sold_lots": len([l for l in lots if l.get("lot_status") == "sold"])
        }
    
    raise HTTPException(status_code=404, detail="Auction not found")


# ========== EXTEND AUCTION (ANTI-SNIPING) ==========
@auctions_router.post("/extend/{auction_id}")
async def extend_auction(auction_id: str, data: Dict[str, Any]):
    """
    Extend an auction's end time (anti-sniping feature)
    """
    db = get_db()
    
    extension_minutes = data.get("extension_minutes", 2)
    reason = data.get("reason", "anti_sniping")
    
    # Update listing
    listing = await db.listings.find_one({"id": auction_id})
    if listing:
        current_end = datetime.fromisoformat(listing["auction_end_date"])
        new_end = current_end + timedelta(minutes=extension_minutes)
        
        await db.listings.update_one(
            {"id": auction_id},
            {"$set": {
                "auction_end_date": new_end.isoformat(),
                "extended": True,
                "extension_reason": reason
            }}
        )
        
        return {
            "status": "extended",
            "new_end_date": new_end.isoformat(),
            "extension_minutes": extension_minutes
        }
    
    # Check lots
    lot = await db.lots.find_one({"id": auction_id})
    if lot:
        current_end = datetime.fromisoformat(lot["auction_end_date"])
        new_end = current_end + timedelta(minutes=extension_minutes)
        
        await db.lots.update_one(
            {"id": auction_id},
            {"$set": {
                "auction_end_date": new_end.isoformat(),
                "extended": True,
                "extension_reason": reason
            }}
        )
        
        return {
            "status": "extended",
            "new_end_date": new_end.isoformat(),
            "extension_minutes": extension_minutes
        }
    
    raise HTTPException(status_code=404, detail="Auction/Lot not found")


# ========== BID PLACEMENT (Single-Item) ==========

@bids_router.post("/bids")
@_limiter.limit("30/minute")
async def place_bid(request: Request, bid_data: BidCreate, current_user: User = Depends(get_current_user)):
    db = get_db()

    # ========== HIGH-TRUST GATEKEEPING ==========
    if current_user.role != 'admin':
        if not current_user.phone_verified:
            raise HTTPException(
                status_code=403,
                detail="Phone verification required. Please verify your phone number before placing bids."
            )
        payment_methods = await db.payment_methods.count_documents({"user_id": current_user.id})
        if payment_methods == 0:
            raise HTTPException(
                status_code=403,
                detail="Payment method required. Please add a payment card before placing bids."
            )

    # ========== LOAD MARKETPLACE SETTINGS ==========
    settings = await get_marketplace_settings(db)

    listing = await db.listings.find_one({"id": bid_data.listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_id"] == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot bid on your own listing")
    if listing["status"] != "active":
        raise HTTPException(status_code=400, detail="Listing is not active")
    if isinstance(listing.get("auction_end_date"), str):
        auction_end = datetime.fromisoformat(listing["auction_end_date"])
    else:
        auction_end = listing["auction_end_date"]

    now = datetime.now(timezone.utc)

    # ========== ANTI-SNIPING LOGIC ==========
    anti_sniping_enabled = settings.get("enable_anti_sniping", True)
    anti_sniping_window_minutes = settings.get("anti_sniping_window_minutes", 2)
    ANTI_SNIPE_WINDOW = anti_sniping_window_minutes * 60
    GRACE_PERIOD = 5

    time_remaining = (auction_end - now).total_seconds()
    extension_applied = False
    new_auction_end = None

    if time_remaining < -GRACE_PERIOD:
        raise HTTPException(status_code=400, detail="Auction has ended")

    if anti_sniping_enabled and time_remaining <= ANTI_SNIPE_WINDOW:
        new_auction_end = now + timedelta(seconds=ANTI_SNIPE_WINDOW)
        extension_applied = True
        logger.info(f"Anti-sniping triggered: listing={bid_data.listing_id}, time_remaining={time_remaining:.1f}s")

    min_increment = settings.get("minimum_bid_increment", 1.0)
    min_bid = listing["current_price"] + min_increment

    if bid_data.amount <= listing["current_price"]:
        raise HTTPException(
            status_code=400,
            detail=f"Your bid must be at least ${min_bid:.2f} to lead."
        )

    if bid_data.amount < min_bid:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum bid increment is ${min_increment:.2f}. Your bid must be at least ${min_bid:.2f}."
        )

    bid = Bid(listing_id=bid_data.listing_id, bidder_id=current_user.id, amount=bid_data.amount)
    bid_dict = bid.model_dump()
    bid_dict["created_at"] = bid_dict["created_at"].isoformat()

    await db.bids.insert_one(bid_dict)
    new_bid_count = listing.get("bid_count", 0) + 1

    update_fields = {
        "current_price": bid_data.amount,
        "highest_bidder_id": current_user.id
    }

    if extension_applied and new_auction_end:
        update_fields["auction_end_date"] = new_auction_end.isoformat()
        update_fields["extension_count"] = listing.get("extension_count", 0) + 1

    await db.listings.update_one(
        {"id": bid_data.listing_id},
        {
            "$set": update_fields,
            "$inc": {"bid_count": 1}
        }
    )

    # Real-time broadcast
    broadcast_data = {
        'bid_count': new_bid_count,
        'current_price': bid_data.amount,
        'currency': listing.get("currency", "CAD"),
    }

    if extension_applied and new_auction_end:
        broadcast_data['time_extended'] = True
        broadcast_data['new_auction_end'] = new_auction_end.isoformat()
        broadcast_data['new_auction_end_epoch'] = get_epoch_timestamp(new_auction_end)
        broadcast_data['server_time_epoch'] = get_server_timestamp()
        broadcast_data['extension_reason'] = 'anti_sniping'

    if _ws_manager:
        await _ws_manager.broadcast_bid_update(
            bid_data.listing_id,
            {
                'id': bid_dict['id'],
                'bidder_id': current_user.id,
                'amount': bid_data.amount,
                'created_at': bid_dict['created_at']
            },
            broadcast_data
        )

    # ========== OUTBID NOTIFICATION ==========
    previous_highest_bidder = listing.get("highest_bidder_id")
    previous_highest_bid = listing.get("current_price", 0)

    if previous_highest_bidder and previous_highest_bidder != current_user.id:
        outbid_notification = {
            "id": str(uuid_mod.uuid4()),
            "user_id": previous_highest_bidder,
            "type": "outbid",
            "title": "You've been outbid!",
            "message": f"Someone placed a higher bid of ${bid_data.amount:.2f} on '{listing.get('title', 'Item')}'. Tap to bid again.",
            "data": {
                "listing_id": bid_data.listing_id,
                "current_bid": bid_data.amount,
                "listing_title": listing.get("title")
            },
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.notifications.insert_one(outbid_notification)

        # Send SMS notification
        try:
            if _sms_service_getter:
                sms_service = _sms_service_getter(db)
                await sms_service.notify_outbid(
                    user_id=previous_highest_bidder,
                    listing_title=listing.get("title", "Item"),
                    new_bid_amount=bid_data.amount,
                    previous_bid_amount=previous_highest_bid,
                    listing_id=bid_data.listing_id
                )
        except Exception as sms_error:
            logger.warning(f"SMS outbid notification failed: {sms_error}")

        # Send outbid email
        try:
            outbid_user = await db.users.find_one({"id": previous_highest_bidder}, {"_id": 0, "email": 1, "name": 1})
            if outbid_user and outbid_user.get("email"):
                from services.email_notifications import send_outbid_email
                await send_outbid_email(
                    user_email=outbid_user["email"],
                    user_name=outbid_user.get("name", "Bidder"),
                    listing_title=listing.get("title", "Item"),
                    their_bid=previous_highest_bid,
                    new_high_bid=bid_data.amount,
                    listing_id=bid_data.listing_id,
                    auction_end_date=listing.get("auction_end_date", "")
                )
        except Exception as email_error:
            logger.warning(f"Outbid email notification failed: {email_error}")

    # Bid placed email confirmation
    try:
        from services.email_notifications import send_bid_placed_email
        await send_bid_placed_email(
            bidder_email=current_user.email,
            bidder_name=current_user.name or "Bidder",
            listing_title=listing.get("title", "Item"),
            bid_amount=bid_data.amount,
            listing_id=bid_data.listing_id,
            auction_end_date=new_auction_end.isoformat() if extension_applied else listing.get("auction_end_date", ""),
            is_leading=True
        )
    except Exception as email_error:
        logger.warning(f"Bid confirmation email failed: {email_error}")

    logger.info(f"Bid placed: listing={bid_data.listing_id}, bidder={current_user.id}, amount={bid_data.amount}, extension={extension_applied}")

    response = bid.model_dump()
    response["created_at"] = bid_dict["created_at"]
    response["currency"] = listing.get("currency", "CAD")
    if extension_applied:
        response["extension_applied"] = True
        response["new_auction_end"] = new_auction_end.isoformat()

    return response


# ========== BUY NOW ==========

@bids_router.post("/buy-now")
async def purchase_buy_now(
    purchase: BuyNowPurchase,
    current_user: User = Depends(get_current_user)
):
    """Process Buy Now purchase for multi-item lots."""
    db = get_db()

    settings = await get_marketplace_settings(db)
    if not settings.get("enable_buy_now", True):
        raise HTTPException(
            status_code=403,
            detail="Buy Now feature is currently disabled by admin. Please place a bid instead."
        )

    auction = await db.multi_item_listings.find_one({"id": purchase.auction_id}, {"_id": 0})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    if auction["status"] != "active":
        raise HTTPException(status_code=400, detail="Auction is not active")

    lot_index = None
    target_lot = None
    for idx, lot in enumerate(auction["lots"]):
        if lot["lot_number"] == purchase.lot_number:
            lot_index = idx
            target_lot = lot
            break

    if not target_lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    if not target_lot.get("buy_now_enabled", False):
        raise HTTPException(status_code=400, detail="Buy Now not available for this lot")
    if not target_lot.get("buy_now_price"):
        raise HTTPException(status_code=400, detail="Buy Now price not set")

    available_qty = target_lot.get("available_quantity", target_lot["quantity"])
    if available_qty <= 0:
        raise HTTPException(status_code=400, detail="Item sold out")
    if purchase.quantity > available_qty:
        raise HTTPException(status_code=400, detail=f"Only {available_qty} units available")

    price_per_unit = target_lot["buy_now_price"]
    total_amount = price_per_unit * purchase.quantity
    new_available_qty = available_qty - purchase.quantity
    new_sold_qty = target_lot.get("sold_quantity", 0) + purchase.quantity

    if new_available_qty == 0:
        new_lot_status = "sold_out"
    elif new_sold_qty > 0:
        new_lot_status = "partially_sold"
    else:
        new_lot_status = target_lot.get("lot_status", "active")

    update_fields = {
        f"lots.{lot_index}.available_quantity": new_available_qty,
        f"lots.{lot_index}.sold_quantity": new_sold_qty,
        f"lots.{lot_index}.lot_status": new_lot_status
    }

    if new_available_qty == 0:
        update_fields[f"lots.{lot_index}.lot_status"] = "sold_out"

    result = await db.multi_item_listings.update_one(
        {"id": purchase.auction_id},
        {"$set": update_fields}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update inventory")

    transaction = BuyNowTransaction(
        auction_id=purchase.auction_id,
        lot_number=purchase.lot_number,
        buyer_id=current_user.id,
        quantity_purchased=purchase.quantity,
        price_per_unit=price_per_unit,
        total_amount=total_amount,
        payment_status="pending"
    )

    transaction_dict = transaction.model_dump()
    transaction_dict["transaction_date"] = transaction_dict["transaction_date"].isoformat()
    await db.buy_now_transactions.insert_one(transaction_dict)

    if _ws_manager:
        await _ws_manager.broadcast(
            purchase.auction_id,
            {
                "type": "BUY_NOW_PURCHASE",
                "auction_id": purchase.auction_id,
                "lot_number": purchase.lot_number,
                "quantity_purchased": purchase.quantity,
                "available_quantity": new_available_qty,
                "lot_status": new_lot_status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

    logger.info(
        f"Buy Now purchase: auction={purchase.auction_id}, "
        f"lot={purchase.lot_number}, buyer={current_user.id}, "
        f"qty={purchase.quantity}, total=${total_amount}"
    )

    # ========== AUTOMATED HANDSHAKE ==========
    conversation_id = None
    try:
        seller_id = auction.get("seller_id")
        if seller_id and seller_id != current_user.id:
            seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "name": 1, "email": 1, "phone": 1})
            buyer = await db.users.find_one({"id": current_user.id}, {"_id": 0, "name": 1, "email": 1, "phone": 1})

            conversation_id = str(uuid_mod.uuid4())
            conversation = {
                "id": conversation_id,
                "participants": [seller_id, current_user.id],
                "listing_id": purchase.auction_id,
                "lot_number": purchase.lot_number,
                "type": "buy_now_purchase",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "last_message": None,
                "unread_count": {seller_id: 1, current_user.id: 0}
            }
            await db.conversations.insert_one(conversation)

            system_message = {
                "id": str(uuid_mod.uuid4()),
                "conversation_id": conversation_id,
                "sender_id": "system",
                "content": f"""**Buy Now Purchase Complete!**

**Lot #{purchase.lot_number}: {target_lot.get('title', 'Item')}**
**Amount:** ${total_amount:.2f}

---

**Buyer:** {buyer.get('name', 'Buyer') if buyer else 'Buyer'}
- Email: {buyer.get('email', 'Not provided') if buyer else 'Not provided'}
- Phone: {buyer.get('phone', 'Not provided') if buyer else 'Not provided'}

**Seller:** {seller.get('name', 'Seller') if seller else 'Seller'}
- Email: {seller.get('email', 'Not provided') if seller else 'Not provided'}
- Phone: {seller.get('phone', 'Not provided') if seller else 'Not provided'}

---

Please coordinate pickup/delivery directly. Thank you for using BidVex!
""",
                "message_type": "system_card",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "read": False
            }
            await db.messages.insert_one(system_message)

            seller_notification = {
                "id": str(uuid_mod.uuid4()),
                "user_id": seller_id,
                "type": "buy_now_purchase",
                "title": "Buy Now Purchase!",
                "message": f"Lot #{purchase.lot_number} - {target_lot.get('title', 'Item')} was purchased for ${total_amount:.2f}",
                "data": {
                    "auction_id": purchase.auction_id,
                    "lot_number": purchase.lot_number,
                    "buyer_id": current_user.id,
                    "amount": total_amount,
                    "conversation_id": conversation_id
                },
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.notifications.insert_one(seller_notification)
            logger.info(f"Buy Now handshake created: conversation={conversation_id}")
    except Exception as e:
        logger.error(f"Failed to create handshake for Buy Now: {e}")

    return {
        "success": True,
        "transaction_id": transaction.id,
        "total_amount": total_amount,
        "available_quantity": new_available_qty,
        "lot_status": new_lot_status,
        "conversation_id": conversation_id,
        "message": "Purchase successful! A chat with the seller has been created."
    }


# ========== BID HISTORY ==========

@bids_router.get("/bids/listing/{listing_id}")
async def get_listing_bids(listing_id: str, limit: int = 20):
    """Get bids for a listing with bidder information."""
    db = get_db()
    bids = await db.bids.find({"listing_id": listing_id}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)

    enriched_bids = []
    for bid in bids:
        bidder = await db.users.find_one({"id": bid["bidder_id"]}, {"_id": 0, "name": 1, "picture": 1})
        if isinstance(bid.get("created_at"), str):
            bid["created_at"] = datetime.fromisoformat(bid["created_at"])

        enriched_bids.append({
            **bid,
            "bidder_name": bidder.get("name") if bidder else "Anonymous",
            "bidder_avatar": bidder.get("picture") if bidder else None,
            "created_at": bid["created_at"].isoformat() if isinstance(bid["created_at"], datetime) else bid["created_at"]
        })

    return enriched_bids


# ========== LOT BIDDING (Multi-Item) ==========

@bids_router.post("/multi-item-listings/{listing_id}/lots/{lot_number}/bid")
async def bid_on_lot(listing_id: str, lot_number: int, data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    db = get_db()
    listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing["seller_id"] == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot bid on your own listing")

    amount = data.get("amount")
    bid_type = data.get("bid_type", "normal")
    lots = listing["lots"]

    lot_index = next((i for i, lot in enumerate(lots) if lot["lot_number"] == lot_number), None)
    if lot_index is None:
        raise HTTPException(status_code=404, detail="Lot not found")

    lot = lots[lot_index]
    current_price = lots[lot_index]["current_price"]
    previous_bid = current_price

    min_increment = get_minimum_increment(listing, current_price)
    if amount < current_price + min_increment:
        raise HTTPException(
            status_code=400,
            detail=f"Bid must be at least ${current_price + min_increment:.2f} (minimum increment: ${min_increment:.2f})"
        )

    min_bid = current_price + min_increment
    if amount <= current_price:
        raise HTTPException(
            status_code=400,
            detail=f"Your bid must be at least ${min_bid:.2f} to lead."
        )

    previous_highest_bidder = lot.get("highest_bidder_id")

    lots[lot_index]["current_price"] = amount
    lots[lot_index]["highest_bidder_id"] = current_user.id

    # ========== ANTI-SNIPING LOGIC ==========
    ANTI_SNIPE_WINDOW = 120
    now = datetime.now(timezone.utc)
    lot_end_time_str = lots[lot_index].get("lot_end_time")
    extension_applied = False
    new_end_time = None
    extension_count = lots[lot_index].get("extension_count", 0)

    if lot_end_time_str:
        lot_end_time = datetime.fromisoformat(lot_end_time_str) if isinstance(lot_end_time_str, str) else lot_end_time_str
        time_remaining = (lot_end_time - now).total_seconds()

        if 0 < time_remaining <= ANTI_SNIPE_WINDOW:
            new_end_time = now + timedelta(seconds=ANTI_SNIPE_WINDOW)
            lots[lot_index]["lot_end_time"] = new_end_time.isoformat()
            lots[lot_index]["extension_count"] = extension_count + 1
            extension_applied = True
            logger.info(f"Anti-sniping triggered: listing={listing_id}, lot={lot_number}, extensions={extension_count + 1}")

    await db.multi_item_listings.update_one(
        {"id": listing_id},
        {"$set": {"lots": lots}}
    )

    if extension_applied and new_end_time and _ws_manager:
        await _ws_manager.broadcast(listing_id, {
            'type': 'TIME_EXTENSION',
            'listing_id': listing_id,
            'lot_number': lot_number,
            'new_end_time': new_end_time.isoformat(),
            'extension_count': extension_count + 1,
            'reason': 'anti_sniping',
            'timestamp': now.isoformat()
        })

    bid = {
        "id": str(uuid_mod.uuid4()),
        "listing_id": listing_id,
        "lot_number": lot_number,
        "bidder_id": current_user.id,
        "amount": amount,
        "bid_type": bid_type,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    bid_for_db = bid.copy()
    await db.lot_bids.insert_one(bid_for_db)

    # ========== OUTBID NOTIFICATION ==========
    if previous_highest_bidder and previous_highest_bidder != current_user.id:
        outbid_notification = {
            "id": str(uuid_mod.uuid4()),
            "user_id": previous_highest_bidder,
            "type": "outbid",
            "title": "You've been outbid!",
            "message": f"Someone placed a higher bid of ${amount:.2f} on Lot #{lot_number} - {lot.get('title', 'Item')}. Tap to bid again.",
            "data": {
                "auction_id": listing_id,
                "lot_number": lot_number,
                "current_bid": amount,
                "listing_title": listing.get("title")
            },
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.notifications.insert_one(outbid_notification)

        try:
            if _sms_service_getter:
                sms_service = _sms_service_getter(db)
                await sms_service.notify_outbid(
                    user_id=previous_highest_bidder,
                    listing_title=f"{listing.get('title', 'Item')} - Lot #{lot_number}",
                    new_bid_amount=amount,
                    previous_bid_amount=previous_bid,
                    listing_id=listing_id
                )
        except Exception as sms_error:
            logger.warning(f"SMS outbid notification failed: {sms_error}")

    response = {
        "message": "Bid placed successfully",
        "bid": bid,
        "minimum_next_bid": current_price + get_minimum_increment(listing, amount),
        "extension_applied": extension_applied,
        "extension_count": lots[lot_index].get("extension_count", 0)
    }

    if extension_applied and new_end_time:
        response["new_lot_end_time"] = new_end_time.isoformat()
        response["anti_sniping_message"] = "Auction extended by 2 minutes due to last-minute bidding activity."

    return response


# ========== AUTO-BID ==========

@bids_router.post("/bids/auto-bid")
async def setup_auto_bid(listing_id: str, max_bid: float, current_user: User = Depends(get_current_user)):
    """Setup Auto-Bid Bot (Premium/VIP only)"""
    db = get_db()
    try:
        if current_user.subscription_tier == "free":
            raise HTTPException(
                status_code=403,
                detail="Auto-Bid Bot is a Premium feature. Upgrade to Premium or VIP to use this feature."
            )

        listing = await db.listings.find_one({"id": listing_id})
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")

        current_bid = listing.get("current_bid", listing.get("starting_price", 0))
        if max_bid <= current_bid:
            raise HTTPException(status_code=400, detail="Max bid must be higher than current bid")

        existing = await db.auto_bids.find_one({
            "user_id": current_user.id,
            "listing_id": listing_id,
            "is_active": True
        })

        if existing:
            await db.auto_bids.update_one(
                {"id": existing["id"]},
                {"$set": {"max_bid": max_bid}}
            )
            return {"message": "Auto-Bid updated", "auto_bid_id": existing["id"]}
        else:
            auto_bid = AutoBid(
                user_id=current_user.id,
                listing_id=listing_id,
                max_bid=max_bid
            )
            await db.auto_bids.insert_one(auto_bid.model_dump())
            return {"message": "Auto-Bid activated", "auto_bid_id": auto_bid.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@bids_router.delete("/bids/auto-bid/{listing_id}")
async def deactivate_auto_bid(listing_id: str, current_user: User = Depends(get_current_user)):
    """Deactivate Auto-Bid Bot for a listing"""
    db = get_db()
    try:
        result = await db.auto_bids.update_one(
            {"user_id": current_user.id, "listing_id": listing_id, "is_active": True},
            {"$set": {"is_active": False}}
        )

        if result.modified_count > 0:
            return {"message": "Auto-Bid deactivated"}
        else:
            raise HTTPException(status_code=404, detail="No active Auto-Bid found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@bids_router.get("/bids/auto-bid")
async def get_user_auto_bids(current_user: User = Depends(get_current_user)):
    """Get user's active auto-bids"""
    db = get_db()
    try:
        auto_bids = await db.auto_bids.find({
            "user_id": current_user.id,
            "is_active": True
        }).to_list(100)

        return {"auto_bids": auto_bids, "total": len(auto_bids)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

