"""
BidVex Auctions Router
Handles auction lifecycle management including:
- Auction end processing
- Winner determination
- Automated handshake triggers
- Push notifications for auction events
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

auctions_router = APIRouter(prefix="/auctions", tags=["Auctions"])

# Instances will be injected from main app
_db = None
_notification_manager = None

def set_db(db_instance):
    """Set database instance from main app"""
    global _db
    _db = db_instance

def set_notification_manager(manager):
    """Set notification manager from main app"""
    global _notification_manager
    _notification_manager = manager

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
                    
                    # Update listing status
                    await db.listings.update_one(
                        {"id": listing_id},
                        {"$set": {
                            "status": "ended",
                            "winner_id": winner_id,
                            "final_price": final_price,
                            "ended_at": now_str
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
                            "title": "🎉 Congratulations! You Won!",
                            "message": f"You won the auction for {listing.get('title')} at ${final_price:.2f}",
                            "listing_id": listing_id,
                            "conversation_id": conversation_id,
                            "final_price": final_price
                        })
                        
                        # Also notify seller
                        await notification_manager.send_to_user(seller_id, {
                            "type": "AUCTION_SOLD",
                            "title": "💰 Item Sold!",
                            "message": f"Your item {listing.get('title')} sold for ${final_price:.2f}",
                            "listing_id": listing_id,
                            "winner_id": winner_id,
                            "final_price": final_price
                        })
                    except Exception as e:
                        logger.warning(f"Could not send push notification: {e}")
                    
                    # Create notification records in database
                    await db.notifications.insert_many([
                        {
                            "id": str(uuid4()),
                            "user_id": winner_id,
                            "type": "auction_won",
                            "title": "🎉 Congratulations! You Won!",
                            "message": f"You won the auction for {listing.get('title')} at ${final_price:.2f}",
                            "listing_id": listing_id,
                            "read": False,
                            "created_at": now_str
                        },
                        {
                            "id": str(uuid4()),
                            "user_id": seller_id,
                            "type": "auction_sold",
                            "title": "💰 Item Sold!",
                            "message": f"Your item {listing.get('title')} sold for ${final_price:.2f}",
                            "listing_id": listing_id,
                            "read": False,
                            "created_at": now_str
                        }
                    ])
                    
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
            
            # Count active lots
            active_lots_count = await db.lots.count_documents({
                "auction_id": auction_id,
                "lot_status": "active"
            })
            
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
