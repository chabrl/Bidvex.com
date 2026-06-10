"""
BidVex Auction Bids Sub-Router
Handles: bid placement (single + lot), buy now, bid history, auto-bid
Extracted from auctions.py for maintainability.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any
from datetime import datetime, timezone, timedelta
from deps import User, get_current_user
from models import Bid, BidCreate, BuyNowPurchase, BuyNowTransaction, AutoBid
from rate_limit import limiter as _limiter
from utils import get_marketplace_settings, get_minimum_increment, get_epoch_timestamp, get_server_timestamp
import logging
import uuid as uuid_mod

logger = logging.getLogger(__name__)

bids_router = APIRouter(tags=["Bids"])

# Shared state — injected from auctions.py
_db = None
_ws_manager = None
_marketplace_ws = None
_sms_service_getter = None


def _init_bids(db, ws_manager, sms_getter, marketplace_ws=None):
    """Initialize shared state from parent module."""
    global _db, _ws_manager, _sms_service_getter, _marketplace_ws
    _db = db
    _ws_manager = ws_manager
    _sms_service_getter = sms_getter
    _marketplace_ws = marketplace_ws


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


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

    # iter211 P4 — Demo-user isolation rules:
    #   • Demo users can bid on OTHER demo listings (simulated, no Stripe).
    #   • Demo users CANNOT bid on real listings.
    #   • Real users CANNOT bid on demo listings (they aren't public anyway).
    from services.demo_filter import is_demo_user
    bidder_is_demo = await is_demo_user(db, current_user.id)
    listing_is_demo = bool(listing.get("is_demo"))
    if bidder_is_demo and not listing_is_demo:
        raise HTTPException(status_code=403, detail={
            "error": "demo_cannot_bid_on_real",
            "message_en": "Demo accounts cannot bid on real auctions. Contact us to activate your account.",
            "message_fr": "Les comptes de démonstration ne peuvent pas enchérir sur de vraies ventes. Contactez-nous pour activer votre compte.",
        })
    if not bidder_is_demo and listing_is_demo:
        raise HTTPException(status_code=403, detail={
            "error": "real_cannot_bid_on_demo",
            "message_en": "This listing is in demo mode and is not available for bidding.",
            "message_fr": "Cette annonce est en mode démonstration et n'est pas disponible pour les enchères.",
        })

    # ===== Section branding (Bug 1): derive from category =====
    _cat = (listing.get("category") or "").lower()
    if any(v in _cat for v in ("vehicle", "car", "auto", "truck", "motorcycle", "suv", "van")):
        _auction_type = "vehicle"
    elif listing.get("is_multi_item") or listing.get("listing_type") == "lots":
        _auction_type = "lots"
    else:
        _auction_type = "marketplace"

    # ===== iter229 — System-Proxy Vehicle Bidding Gateway (LEGAL) =====
    # For vehicle listings, the buyer can place a bid only via the
    # System-Proxy engine: an ACTIVE broker partnership must exist,
    # bid cap (if any) must not be exceeded, and the buyer must have
    # accepted the proxy-bidding legal rider once. The bid is then
    # stamped as legally executed under the broker's license, with
    # full compliance metadata stored alongside the standard bid doc.
    proxy_compliance_stamps = None
    if current_user.role != "admin":
        from services.category_rules import assert_broker_eligible
        bidder_account_type = (current_user.account_type or "individual")
        rel = await db.broker_buyer_relationships.find_one(
            {"buyer_user_id": current_user.id, "status": "active"},
            {"_id": 0},
        )
        has_rel = rel is not None
        ok, err = assert_broker_eligible(
            category=listing.get("category", ""),
            bidder_account_type=bidder_account_type,
            has_active_relationship=has_rel,
        )
        if not ok:
            raise HTTPException(status_code=403, detail=err)

        # If broker is required for this category, enforce the cap + agreement
        if has_rel and _auction_type == "vehicle":
            broker = await db.brokers.find_one(
                {"id": rel["broker_id"], "verification_status": "approved"},
                {"_id": 0},
            )
            if not broker:
                raise HTTPException(status_code=403, detail={
                    "error":      "broker_not_active",
                    "message_en": "Your broker is no longer authorized to place vehicle bids on your behalf.",
                    "message_fr": "Votre courtier n'est plus autorisé à enchérir sur des véhicules en votre nom.",
                })
            # Bid cap gate
            cap = rel.get("bid_cap")
            if cap is not None:
                try:
                    cap_f = float(cap)
                except (TypeError, ValueError):
                    cap_f = None
                if cap_f is not None and float(bid_data.amount) > cap_f:
                    raise HTTPException(status_code=400, detail={
                        "error":      "bid_cap_exceeded",
                        "message_en": f"This bid exceeds your pre-authorized broker bid cap of ${cap_f:.0f} CAD. Update your cap in partnership settings or ask your broker to adjust it.",
                        "message_fr": f"Cette enchère dépasse votre plafond pré-autorisé de {cap_f:.0f} $ CAD. Mettez à jour votre plafond dans les paramètres du partenariat.",
                        "bid_cap":    cap_f,
                    })
            # Proxy rider gate
            if not rel.get("proxy_bid_agreement_accepted", False):
                raise HTTPException(status_code=403, detail={
                    "error":      "proxy_agreement_required",
                    "message_en": "You must accept the proxy bid agreement before placing vehicle bids.",
                    "message_fr": "Vous devez accepter l'accord de procuration avant de placer des enchères sur des véhicules.",
                })
            # Compliance stamps written to the bid document below
            proxy_compliance_stamps = {
                "legal_bidder_of_record_id":     rel["broker_id"],
                "broker_license":                broker.get("broker_license_number"),
                "broker_regulatory_body":        broker.get("regulatory_body"),
                "broker_operating_province":     broker.get("operating_province"),
                "acting_on_behalf_of_buyer_id":  current_user.id,
                "proxy_routing_mode":            "system_proxy_auto",
                "relationship_id":               rel["id"],
                "jurisdiction_verified":         (listing.get("seller_province") or "").upper() or None,
                "bid_cap_at_time_of_bid":        rel.get("bid_cap"),
                "proxy_agreement_accepted_at":   rel.get("proxy_bid_agreement_accepted_at"),
            }

    # ========== HIGH-VALUE DEPOSIT CHECK ($1k hold for >$10k auctions) ==========
    from services.pricing_config import DEPOSIT_THRESHOLD_CAD, DEPOSIT_AMOUNT_DOLLARS
    starting_price = listing.get("starting_price", 0)
    if starting_price >= DEPOSIT_THRESHOLD_CAD and current_user.role != 'admin':
        active_deposit = await db.bidding_deposits.find_one({
            "user_id": current_user.id,
            "listing_id": bid_data.listing_id,
            "status": {"$in": ["requires_capture", "succeeded"]},
        })
        if not active_deposit:
            raise HTTPException(
                status_code=403,
                detail=f"A refundable ${DEPOSIT_AMOUNT_DOLLARS:,} security deposit is required to bid on this high-value auction. Please authorize the hold before placing a bid."
            )
    if isinstance(listing.get("auction_end_date"), str):
        auction_end = datetime.fromisoformat(listing["auction_end_date"])
    else:
        auction_end = listing["auction_end_date"]

    # ========== STRICT BIDDER DEPOSIT (Spec Feature 1) ==========
    # Listing-level requires_deposit (partner-defined). Charged on FIRST bid only.
    if listing.get("requires_deposit") and current_user.role != 'admin':
        existing_dep = await db.bidding_deposits.find_one({
            "auction_id": bid_data.listing_id,
            "user_id": current_user.id,
            "status": {"$in": ["held", "authorized", "succeeded", "applied"]},
        })
        if not existing_dep:
            try:
                from routes.bidder_deposits import _charge_deposit_for_user
                await _charge_deposit_for_user(db, current_user, bid_data.listing_id)
            except HTTPException as exc:
                raise exc
            except Exception as exc:
                logger.exception(f"Deposit charge failed: {exc}")
                raise HTTPException(
                    status_code=402,
                    detail={
                        "error": "deposit_charge_failed",
                        "message_en": "We could not charge your deposit. Please try again.",
                        "message_fr": "Le dépôt n'a pas pu être débité. Veuillez réessayer.",
                    },
                )

    now = datetime.now(timezone.utc)

    # ========== ANTI-SNIPING LOGIC ==========
    anti_sniping_enabled = settings.get("enable_anti_sniping", True)
    anti_sniping_window_minutes = settings.get("anti_sniping_window_minutes", 2)
    ANTI_SNIPE_WINDOW = anti_sniping_window_minutes * 60
    GRACE_PERIOD = 5

    time_remaining = (auction_end - now).total_seconds()
    extension_applied = False
    new_auction_end = None

    # ========== HARD STOP: Server-Side Timestamp Validation ==========
    if time_remaining <= 0:
        raise HTTPException(status_code=403, detail="Auction has already ended")

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
    # iter229 — proxy compliance stamps (vehicle bids only)
    if proxy_compliance_stamps:
        bid_dict["proxy_compliance"]          = proxy_compliance_stamps
        bid_dict["legal_bidder_of_record_id"] = proxy_compliance_stamps["legal_bidder_of_record_id"]
        bid_dict["bidder_type"]               = "broker_proxy"

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

    # Invalidate listing cache after update
    try:
        from routes.listings import _listing_cache
        _listing_cache.pop(bid_data.listing_id, None)
    except ImportError:
        pass

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

    # Broadcast to global marketplace for real-time card updates
    if _marketplace_ws:
        mp_msg = {
            'type': 'LISTING_UPDATE',
            'listing_id': bid_data.listing_id,
            'current_price': bid_data.amount,
            'bid_count': (listing.get('bid_count', 0) or 0) + 1,
            'currency': listing.get('currency', 'CAD'),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        if extension_applied and new_auction_end:
            mp_msg['time_extended'] = True
            mp_msg['new_auction_end'] = new_auction_end.isoformat()
        await _marketplace_ws.broadcast(mp_msg)

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
                from services.emails.email_marketplace import send_outbid_email
                await send_outbid_email(
                    user_email=outbid_user["email"],
                    user_name=outbid_user.get("name", "Bidder"),
                    listing_title=listing.get("title", "Item"),
                    their_bid=previous_highest_bid,
                    new_high_bid=bid_data.amount,
                    listing_id=bid_data.listing_id,
                    auction_end_date=listing.get("auction_end_date", ""),
                    auction_type=_auction_type,
                )
        except Exception as email_error:
            logger.warning(f"Outbid email notification failed: {email_error}")

        # Send push notification
        try:
            from routes.push_notifications import send_push_to_user
            cat = (listing.get("category") or "").lower()
            is_vehicle = any(v in cat for v in ("vehicle", "car", "auto"))
            push_url = f"/vehicle-auctions/{bid_data.listing_id}" if is_vehicle else f"/listing/{bid_data.listing_id}"
            await send_push_to_user(_db, previous_highest_bidder, {
                "title": "You've been outbid!",
                "body": f"Someone bid ${bid_data.amount:,.2f} on '{listing.get('title', 'Item')}'. Tap to counter-bid.",
                "type": "outbid",
                "url": push_url,
                "listing_id": bid_data.listing_id,
                "category": listing.get("category", ""),
            })
        except Exception as push_err:
            logger.warning(f"Push outbid notification failed: {push_err}")

    # Bid placed email confirmation
    try:
        from services.emails.email_marketplace import send_bid_placed_email
        await send_bid_placed_email(
            bidder_email=current_user.email,
            bidder_name=current_user.name or "Bidder",
            listing_title=listing.get("title", "Item"),
            bid_amount=bid_data.amount,
            listing_id=bid_data.listing_id,
            auction_end_date=new_auction_end.isoformat() if extension_applied else listing.get("auction_end_date", ""),
            is_leading=True,
            auction_type=_auction_type,
        )
    except Exception as email_error:
        logger.warning(f"Bid confirmation email failed: {email_error}")

    # Seller: "New Bid on Your Listing" email (Bug 2)
    try:
        seller = await db.users.find_one({"id": listing.get("seller_id")}, {"_id": 0, "email": 1, "name": 1})
        if seller and seller.get("email"):
            from services.emails.email_marketplace import send_seller_bid_received_email
            # Privacy-preserving bidder alias (first name + last initial)
            raw_name = (current_user.name or current_user.email.split("@")[0] or "Bidder").strip()
            parts = raw_name.split()
            alias = f"{parts[0]} {parts[1][0]}." if len(parts) >= 2 else parts[0]
            await send_seller_bid_received_email(
                seller_email=seller["email"],
                seller_name=seller.get("name", "Seller"),
                listing_title=listing.get("title", "Item"),
                listing_id=bid_data.listing_id,
                bid_amount=bid_data.amount,
                bidder_alias=alias,
                auction_end_date=new_auction_end.isoformat() if extension_applied else listing.get("auction_end_date", ""),
                auction_type=_auction_type,
            )
    except Exception as seller_email_err:
        logger.warning(f"Seller bid-received email failed: {seller_email_err}")

    logger.info(f"Bid placed: listing={bid_data.listing_id}, bidder={current_user.id}, amount={bid_data.amount}, extension={extension_applied}")

    # ========== AUTO-BID PROCESSOR: Trigger counter-bids ==========
    try:
        await _process_auto_bids(db, bid_data.listing_id, bid_data.amount, current_user.id)
    except Exception as auto_bid_err:
        logger.warning(f"Auto-bid processing error: {auto_bid_err}")

    response = bid.model_dump()
    response["created_at"] = bid_dict["created_at"]
    response["currency"] = listing.get("currency", "CAD")
    if extension_applied:
        response["extension_applied"] = True
        response["new_auction_end"] = new_auction_end.isoformat()

    return response


async def _process_auto_bids(db, listing_id: str, current_price: float, manual_bidder_id: str):
    """
    Auto-Bid Processor: After a manual bid, check all active auto-bids for this listing.
    If an auto-bid user's max_bid exceeds the current price + min increment, place a counter-bid.
    """
    settings = await get_marketplace_settings(db)
    min_increment = settings.get("minimum_bid_increment", 1.0)

    auto_bids = await db.auto_bids.find({
        "listing_id": listing_id,
        "is_active": True,
        "user_id": {"$ne": manual_bidder_id}  # Don't counter-bid yourself
    }).to_list(100)

    if not auto_bids:
        return

    # Sort by max_bid descending — highest auto-bid wins
    auto_bids.sort(key=lambda x: x.get("max_bid", 0), reverse=True)

    for ab in auto_bids:
        counter_amount = current_price + min_increment
        if counter_amount > ab["max_bid"]:
            # Auto-bid exhausted — deactivate and notify user
            await db.auto_bids.update_one({"id": ab["id"]}, {"$set": {"is_active": False}})
            logger.info(f"Auto-bid {ab['id']} exhausted (max={ab['max_bid']}, needed={counter_amount})")
            
            # Notify user their auto-bid was exceeded
            listing = await db.listings.find_one({"id": listing_id}, {"_id": 0, "title": 1, "auction_end_date": 1})
            exhaustion_notification = {
                "id": str(uuid_mod.uuid4()),
                "user_id": ab["user_id"],
                "type": "auto_bid_exceeded",
                "title": "Your Auto-Bid has been exceeded!",
                "message": f"Someone outbid your max auto-bid of ${ab['max_bid']:.2f} on '{listing.get('title', 'Item') if listing else 'Item'}'. Get back in the game!",
                "data": {"listing_id": listing_id, "max_bid": ab["max_bid"], "current_price": current_price},
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.notifications.insert_one(exhaustion_notification)
            
            # Send outbid email for auto-bid exhaustion
            try:
                outbid_user = await db.users.find_one({"id": ab["user_id"]}, {"_id": 0, "email": 1, "name": 1})
                if outbid_user and outbid_user.get("email"):
                    from services.emails.email_marketplace import send_outbid_email
                    await send_outbid_email(
                        user_email=outbid_user["email"],
                        user_name=outbid_user.get("name", "Bidder"),
                        listing_title=listing.get("title", "Item") if listing else "Item",
                        their_bid=ab["max_bid"],
                        new_high_bid=current_price,
                        listing_id=listing_id,
                        auction_end_date=listing.get("auction_end_date", "") if listing else ""
                    )
            except Exception as email_err:
                logger.warning(f"Auto-bid exhaustion email failed: {email_err}")
            
            # Send WebSocket notification to the user
            if _ws_manager:
                await _ws_manager.send_to_user(ab["user_id"], {
                    "type": "AUTO_BID_EXCEEDED",
                    "listing_id": listing_id,
                    "max_bid": ab["max_bid"],
                    "current_price": current_price,
                    "message": "Someone just outbid your bot! Get back in the game."
                })
            continue

        # Place the counter-bid
        auto_bid_obj = Bid(
            listing_id=listing_id,
            bidder_id=ab["user_id"],
            amount=counter_amount,
            bid_type="auto"
        )
        bid_dict = auto_bid_obj.model_dump()
        bid_dict["created_at"] = bid_dict["created_at"].isoformat()
        await db.bids.insert_one(bid_dict)

        await db.listings.update_one(
            {"id": listing_id},
            {"$set": {"current_price": counter_amount, "highest_bidder_id": ab["user_id"]},
             "$inc": {"bid_count": 1}}
        )

        logger.info(f"Auto-bid triggered: user={ab['user_id']}, amount={counter_amount}, listing={listing_id}")

        # Invalidate listing cache so next fetch returns updated price
        try:
            from routes.listings import _listing_cache
            _listing_cache.pop(listing_id, None)
        except ImportError:
            pass

        # Broadcast the auto-bid via WebSocket
        if _ws_manager:
            listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
            new_bid_count = listing.get("bid_count", 0) if listing else 0
            await _ws_manager.broadcast_bid_update(
                listing_id,
                {'id': bid_dict['id'], 'bidder_id': ab["user_id"],
                 'amount': counter_amount, 'created_at': bid_dict['created_at']},
                {'bid_count': new_bid_count, 'current_price': counter_amount,
                 'currency': listing.get("currency", "CAD") if listing else "CAD"}
            )

        # Only the highest auto-bid wins each round
        break


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

    # Determine payment status based on method
    is_offline = purchase.payment_method in ("cash", "etransfer")
    payment_status = "waiting_for_offline_confirmation" if is_offline else "pending"

    transaction = BuyNowTransaction(
        auction_id=purchase.auction_id,
        lot_number=purchase.lot_number,
        buyer_id=current_user.id,
        quantity_purchased=purchase.quantity,
        price_per_unit=price_per_unit,
        total_amount=total_amount,
        payment_status=payment_status,
        payment_method=purchase.payment_method
    )

    transaction_dict = transaction.model_dump()
    transaction_dict["transaction_date"] = transaction_dict["transaction_date"].isoformat()
    await db.buy_now_transactions.insert_one(transaction_dict)

    # For offline methods, also create an offline order record
    if is_offline:
        seller = await db.users.find_one({"id": auction.get("seller_id")}, {"_id": 0, "email": 1, "name": 1, "interac_email": 1})
        interac_email = seller.get("interac_email", seller.get("email", "")) if seller else ""

        offline_order = {
            "id": str(uuid_mod.uuid4()),
            "listing_id": purchase.auction_id,
            "lot_number": purchase.lot_number,
            "buyer_id": current_user.id,
            "seller_id": auction.get("seller_id"),
            "payment_method": purchase.payment_method,
            "order_status": "reserved",
            "payment_status": "waiting_for_offline_confirmation",
            "amount": total_amount,
            "quantity": purchase.quantity,
            "lot_title": target_lot.get("title", ""),
            "interac_email": interac_email if purchase.payment_method == "etransfer" else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.offline_orders.insert_one(offline_order)

        # Send offline payment instructions email
        try:
            buyer_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0, "email": 1, "name": 1})
            buyer_email = buyer_doc.get("email", current_user.email) if buyer_doc else current_user.email
            buyer_name = buyer_doc.get("name", "Buyer") if buyer_doc else "Buyer"

            if purchase.payment_method == "etransfer":
                email_subject = f"E-Transfer Instructions — Lot #{purchase.lot_number}: {target_lot.get('title', 'Item')}"
                email_body = (
                    f"<h2>E-Transfer Payment Instructions</h2>"
                    f"<p>Hi {buyer_name},</p>"
                    f"<p>Your order for <strong>Lot #{purchase.lot_number}: {target_lot.get('title', 'Item')}</strong> is confirmed.</p>"
                    f"<p><strong>Amount:</strong> ${total_amount:.2f}</p>"
                    f"<p><strong>Send Interac E-Transfer to:</strong> {interac_email}</p>"
                    f"<p>Please include your order reference in the message field.</p>"
                    f"<hr/>"
                    f"<h3>Instructions de virement Interac</h3>"
                    f"<p>Bonjour {buyer_name},</p>"
                    f"<p>Votre commande pour <strong>Lot #{purchase.lot_number}: {target_lot.get('title', 'Item')}</strong> est confirmée.</p>"
                    f"<p><strong>Montant:</strong> ${total_amount:.2f}</p>"
                    f"<p><strong>Envoyer le virement Interac à:</strong> {interac_email}</p>"
                )
            else:
                email_subject = f"Cash Payment — Lot #{purchase.lot_number}: {target_lot.get('title', 'Item')}"
                email_body = (
                    f"<h2>Cash Payment — Pickup Arrangement</h2>"
                    f"<p>Hi {buyer_name},</p>"
                    f"<p>Your order for <strong>Lot #{purchase.lot_number}: {target_lot.get('title', 'Item')}</strong> is confirmed.</p>"
                    f"<p><strong>Amount Due:</strong> ${total_amount:.2f}</p>"
                    f"<p>Please contact the seller to arrange local pickup and cash payment.</p>"
                    f"<hr/>"
                    f"<h3>Paiement comptant — Arrangement de cueillette</h3>"
                    f"<p>Bonjour {buyer_name},</p>"
                    f"<p>Votre commande pour <strong>Lot #{purchase.lot_number}: {target_lot.get('title', 'Item')}</strong> est confirmée.</p>"
                    f"<p><strong>Montant dû:</strong> ${total_amount:.2f}</p>"
                    f"<p>Veuillez contacter le vendeur pour organiser la cueillette locale et le paiement comptant.</p>"
                )

            from services.email_service import get_email_service
            email_svc = get_email_service()
            if email_svc.is_configured():
                await email_svc.send_raw_html(buyer_email, email_subject, email_body)
                logger.info(f"Offline payment email sent to {buyer_email} for lot #{purchase.lot_number}")
            else:
                logger.info(f"Email service not configured — offline payment instructions for lot #{purchase.lot_number} logged only")
        except Exception as email_err:
            logger.warning(f"Failed to send offline payment email: {email_err}")

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

    payment_method_label = {"stripe": "Credit Card", "cash": "Cash", "etransfer": "E-Transfer"}.get(purchase.payment_method, purchase.payment_method)

    return {
        "success": True,
        "transaction_id": transaction.id,
        "total_amount": total_amount,
        "available_quantity": new_available_qty,
        "lot_status": new_lot_status,
        "conversation_id": conversation_id,
        "payment_method": purchase.payment_method,
        "payment_status": payment_status,
        "message": f"Purchase confirmed via {payment_method_label}! A chat with the seller has been created."
            if not is_offline else
            f"Order confirmed via {payment_method_label}. {'E-Transfer instructions sent to your email.' if purchase.payment_method == 'etransfer' else 'Please arrange pickup with the seller.'}"
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
@_limiter.limit("10/minute")
async def bid_on_lot(request: Request, listing_id: str, lot_number: int, data: Dict[str, Any], current_user: User = Depends(get_current_user)):
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
        # Also broadcast to marketplace for real-time card timer sync
        if _marketplace_ws:
            await _marketplace_ws.broadcast({
                'type': 'LISTING_UPDATE',
                'listing_id': listing_id,
                'time_extended': True,
                'new_auction_end': new_end_time.isoformat(),
                'timestamp': now.isoformat(),
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
@_limiter.limit("10/minute")
async def setup_auto_bid(request: Request, listing_id: str, max_bid: float, current_user: User = Depends(get_current_user)):
    """Setup Auto-Bid Bot (Premium/VIP/Partner only)"""
    db = get_db()
    try:
        allowed_tiers = ["premium", "vip", "partner", "business"]
        if current_user.subscription_tier not in allowed_tiers:
            raise HTTPException(
                status_code=403,
                detail="Auto-Bid Bot is a Premium feature. Upgrade to Premium or VIP to use this feature."
            )

        listing = await db.listings.find_one({"id": listing_id})
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")

        current_bid = listing.get("current_price", listing.get("starting_price", 0))
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
