"""
BidVex Auctions Router (Core)
Handles auction lifecycle: end processing, status checks, anti-sniping extensions.
Bid-related endpoints are in auctions_bids.py.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any
from datetime import datetime, timezone, timedelta
from deps import User, get_current_user
from utils import get_marketplace_settings
import logging

logger = logging.getLogger(__name__)

auctions_router = APIRouter(prefix="/auctions", tags=["Auctions"])

# Re-export bids_router for backwards compatibility with server.py
from routes.auctions_bids import bids_router, _init_bids  # noqa: E402, F401

# Instances will be injected from main app
_db = None
_notification_manager = None
_ws_manager = None
_sms_service_getter = None


def set_db(db_instance):
    global _db
    _db = db_instance
    _init_bids(db_instance, _ws_manager, _sms_service_getter)


def set_notification_manager(manager):
    global _notification_manager
    _notification_manager = manager


def set_ws_manager(manager):
    global _ws_manager
    _ws_manager = manager
    _init_bids(_db, manager, _sms_service_getter)


def set_sms_service_getter(getter_fn):
    global _sms_service_getter
    _sms_service_getter = getter_fn
    _init_bids(_db, _ws_manager, getter_fn)


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


def get_notification_manager():
    return _notification_manager


# ========== PROCESS ENDED AUCTIONS ==========
async def process_ended_auctions():
    """
    Background task to process all auctions that have ended.
    Called by the scheduler every minute.
    
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
        # ========== SINGLE LISTINGS ==========
        active_listings = await db.listings.find({
            "status": "active"
        }, {"_id": 0}).to_list(500)

        for listing in active_listings:
            end_date_raw = listing.get("auction_end_date")
            if not end_date_raw:
                continue
                
            if isinstance(end_date_raw, str):
                try:
                    end_date = datetime.fromisoformat(end_date_raw)
                except ValueError:
                    continue
            else:
                end_date = end_date_raw

            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

            if end_date > now:
                continue

            listing_id = listing["id"]
            await db.listings.update_one(
                {"id": listing_id, "status": "active"},
                {"$set": {"status": "ended", "ended_at": now_str}}
            )

            winner_id = listing.get("highest_bidder_id")
            seller_id = listing.get("seller_id")
            
            if winner_id and seller_id:
                try:
                    winner = await db.users.find_one({"id": winner_id}, {"_id": 0, "name": 1, "email": 1, "phone": 1})
                    seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "name": 1, "email": 1, "phone": 1})
                    
                    await create_auction_won_conversation(
                        db=db,
                        listing_id=listing_id,
                        listing_title=listing.get("title", "Item"),
                        winner_id=winner_id,
                        seller_id=seller_id,
                        winning_amount=listing.get("current_price", 0),
                        winner_info=winner,
                        seller_info=seller,
                    )
                    
                    import uuid as _uuid
                    # Winner notification
                    await db.notifications.insert_one({
                        "id": str(_uuid.uuid4()),
                        "user_id": winner_id,
                        "type": "auction_won",
                        "title": "You Won!",
                        "message": f"Congratulations! You won '{listing.get('title', 'Item')}' for ${listing.get('current_price', 0):.2f}",
                        "data": {"listing_id": listing_id, "amount": listing.get("current_price", 0)},
                        "read": False,
                        "created_at": now_str
                    })
                    
                    # Persist to Winner's Circle (30-day retention)
                    try:
                        from routes.user_insights import persist_auction_winner
                        await persist_auction_winner(db, listing_id, winner_id, listing.get("current_price", 0), listing)
                    except Exception as winner_err:
                        logger.warning(f"Winner persistence failed: {winner_err}")
                    
                    # Seller notification  
                    await db.notifications.insert_one({
                        "id": str(_uuid.uuid4()),
                        "user_id": seller_id,
                        "type": "auction_ended",
                        "title": "Auction Ended",
                        "message": f"'{listing.get('title', 'Item')}' sold for ${listing.get('current_price', 0):.2f}",
                        "data": {"listing_id": listing_id, "amount": listing.get("current_price", 0)},
                        "read": False,
                        "created_at": now_str
                    })

                    # Offline Payment Invoice: if seller chose Cash/E-Transfer, create admin invoice
                    payment_method = listing.get("payment_method", "stripe")
                    if payment_method in ("cash", "e-transfer"):
                        bp_rate = listing.get("buyers_premium_percent", 15) / 100
                        sale_price = listing.get("current_price", 0)
                        platform_fee = sale_price * 0.025  # 2.5% platform fee
                        bp_amount = sale_price * bp_rate
                        tax_rate = 0.13  # HST default
                        taxes = (platform_fee + bp_amount) * tax_rate
                        total_invoice = platform_fee + bp_amount + taxes
                        
                        await db.seller_invoices.insert_one({
                            "id": str(_uuid.uuid4()),
                            "seller_id": seller_id,
                            "listing_id": listing_id,
                            "listing_title": listing.get("title", ""),
                            "sale_price": sale_price,
                            "payment_method": payment_method,
                            "platform_fee": round(platform_fee, 2),
                            "buyers_premium": round(bp_amount, 2),
                            "taxes": round(taxes, 2),
                            "total_due": round(total_invoice, 2),
                            "status": "pending",
                            "created_at": now_str
                        })
                        logger.info(f"Offline sale invoice created: seller={seller_id}, total=${total_invoice:.2f}")
                    
                    # Send SMS notifications
                    try:
                        if _sms_service_getter:
                            sms_service = _sms_service_getter(db)
                            await sms_service.notify_auction_won(
                                user_id=winner_id,
                                listing_title=listing.get("title", "Item"),
                                winning_amount=listing.get("current_price", 0),
                                listing_id=listing_id
                            )
                    except Exception as sms_err:
                        logger.warning(f"SMS auction won notification failed: {sms_err}")
                        
                except Exception as e:
                    logger.error(f"Failed to process winner for listing {listing_id}: {e}")
            
            processed_count += 1

        # ========== MULTI-ITEM LISTINGS ==========
        active_multi = await db.multi_item_listings.find({
            "status": "active"
        }, {"_id": 0}).to_list(500)
        
        for auction in active_multi:
            end_date_raw = auction.get("auction_end_date")
            if not end_date_raw:
                continue
            
            if isinstance(end_date_raw, str):
                try:
                    end_date = datetime.fromisoformat(end_date_raw)
                except ValueError:
                    continue
            else:
                end_date = end_date_raw
                
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)

            # Check if ALL lots have ended
            all_lots_ended = True
            if auction.get("lots"):
                for lot in auction["lots"]:
                    lot_end = lot.get("lot_end_time")
                    if lot_end:
                        lot_end_dt = datetime.fromisoformat(lot_end) if isinstance(lot_end, str) else lot_end
                        if lot_end_dt.tzinfo is None:
                            lot_end_dt = lot_end_dt.replace(tzinfo=timezone.utc)
                        if lot_end_dt > now:
                            all_lots_ended = False
                            break
                    elif end_date > now:
                        all_lots_ended = False
                        break
            elif end_date > now:
                all_lots_ended = False
            
            if not all_lots_ended:
                continue

            auction_id = auction["id"]
            await db.multi_item_listings.update_one(
                {"id": auction_id, "status": "active"},
                {"$set": {"status": "ended", "ended_at": now_str}}
            )

            seller_id = auction.get("seller_id")
            
            # Process each lot's winner
            for lot in auction.get("lots", []):
                winner_id = lot.get("highest_bidder_id")
                if winner_id and seller_id:
                    try:
                        winner = await db.users.find_one({"id": winner_id}, {"_id": 0, "name": 1, "email": 1, "phone": 1})
                        seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "name": 1, "email": 1, "phone": 1})
                        
                        await create_auction_won_conversation(
                            db=db,
                            listing_id=auction_id,
                            listing_title=f"{auction.get('title', 'Auction')} - Lot #{lot['lot_number']}",
                            winner_id=winner_id,
                            seller_id=seller_id,
                            winning_amount=lot.get("current_price", 0),
                            winner_info=winner,
                            seller_info=seller,
                            lot_number=lot["lot_number"]
                        )
                    except Exception as e:
                        logger.error(f"Failed to process winner for {auction_id} lot {lot['lot_number']}: {e}")

            processed_count += 1

        if processed_count > 0:
            logger.info(f"Processed {processed_count} ended auctions")
            # Invalidate marketplace cache after processing
            from services.api_cache import invalidate_listing_caches
            invalidate_listing_caches()
            
    except Exception as e:
        logger.error(f"Error processing ended auctions: {e}")


# ========== MANUAL TRIGGER ENDPOINT ==========
@auctions_router.post("/process-ended")
async def trigger_process_ended(background_tasks: BackgroundTasks):
    """Admin trigger to manually process ended auctions."""
    background_tasks.add_task(process_ended_auctions)
    return {"message": "Processing triggered"}


# ========== GET AUCTION END STATUS ==========
@auctions_router.get("/end-status/{auction_id}")
async def get_auction_end_status(auction_id: str):
    """Get the current end time + extension status for a listing or multi-item auction."""
    db = get_db()
    
    # Check single listing first
    listing = await db.listings.find_one({"id": auction_id}, {"_id": 0})
    if listing:
        end_date = listing.get("auction_end_date")
        return {
            "auction_id": auction_id,
            "type": "single",
            "auction_end_date": end_date,
            "extension_count": listing.get("extension_count", 0),
            "status": listing.get("status", "active"),
            "server_time": datetime.now(timezone.utc).isoformat()
        }

    # Check multi-item
    multi = await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0, "auction_end_date": 1, "status": 1, "lots": 1})
    if multi:
        lots_status = []
        for lot in multi.get("lots", []):
            lots_status.append({
                "lot_number": lot["lot_number"],
                "lot_end_time": lot.get("lot_end_time"),
                "extension_count": lot.get("extension_count", 0),
                "lot_status": lot.get("lot_status", "active")
            })
        return {
            "auction_id": auction_id,
            "type": "multi",
            "auction_end_date": multi.get("auction_end_date"),
            "status": multi.get("status", "active"),
            "lots": lots_status,
            "server_time": datetime.now(timezone.utc).isoformat()
        }

    raise HTTPException(status_code=404, detail="Auction/Lot not found")


# ========== EXTEND AUCTION (ANTI-SNIPING) ==========
@auctions_router.post("/extend/{auction_id}")
async def extend_auction(auction_id: str, data: Dict[str, Any]):
    """Manually extend an auction (admin or anti-sniping system)."""
    db = get_db()
    extension_minutes = data.get("extension_minutes", 2)
    lot_number = data.get("lot_number")

    if lot_number is not None:
        # Extend specific lot in multi-item
        auction = await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0})
        if not auction:
            raise HTTPException(status_code=404, detail="Auction not found")
        
        lot_idx = next((i for i, l in enumerate(auction["lots"]) if l["lot_number"] == lot_number), None)
        if lot_idx is None:
            raise HTTPException(status_code=404, detail="Lot not found")

        current_end = auction["lots"][lot_idx].get("lot_end_time")
        if current_end:
            end_dt = datetime.fromisoformat(current_end) if isinstance(current_end, str) else current_end
        else:
            end_dt = datetime.now(timezone.utc)

        new_end = end_dt + timedelta(minutes=extension_minutes)
        ext_count = auction["lots"][lot_idx].get("extension_count", 0) + 1

        await db.multi_item_listings.update_one(
            {"id": auction_id},
            {"$set": {
                f"lots.{lot_idx}.lot_end_time": new_end.isoformat(),
                f"lots.{lot_idx}.extension_count": ext_count,
            }}
        )

        return {
            "success": True,
            "new_end_time": new_end.isoformat(),
            "extension_count": ext_count
        }
    else:
        # Extend single listing
        listing = await db.listings.find_one({"id": auction_id}, {"_id": 0})
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")

        current_end = listing.get("auction_end_date")
        end_dt = datetime.fromisoformat(current_end) if isinstance(current_end, str) else (current_end or datetime.now(timezone.utc))
        new_end = end_dt + timedelta(minutes=extension_minutes)
        ext_count = listing.get("extension_count", 0) + 1

        await db.listings.update_one(
            {"id": auction_id},
            {"$set": {
                "auction_end_date": new_end.isoformat(),
                "extension_count": ext_count,
            }}
        )

        return {
            "success": True,
            "new_end_time": new_end.isoformat(),
            "extension_count": ext_count
        }
