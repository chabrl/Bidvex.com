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
_marketplace_ws = None
_sms_service_getter = None


def set_db(db_instance):
    global _db
    _db = db_instance
    _init_bids(db_instance, _ws_manager, _sms_service_getter, _marketplace_ws)


def set_notification_manager(manager):
    global _notification_manager
    _notification_manager = manager


def set_ws_manager(manager):
    global _ws_manager
    _ws_manager = manager
    _init_bids(_db, manager, _sms_service_getter, _marketplace_ws)


def set_marketplace_ws(mws):
    global _marketplace_ws
    _marketplace_ws = mws
    _init_bids(_db, _ws_manager, _sms_service_getter, mws)


def set_sms_service_getter(getter_fn):
    global _sms_service_getter
    _sms_service_getter = getter_fn
    _init_bids(_db, _ws_manager, getter_fn, _marketplace_ws)


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
            # iter296 P0 BUG 1 + 5 — write all dashboard-counter fields
            # atomically with the status transition. `sold_at` and
            # `winner_user_id` let the seller dashboard's "Sold" counter
            # and the "Ended" counter compute correctly from MongoDB
            # without needing a separate denormalised counter table.
            # iter298 BUG 2 — zero-bid auctions get the dedicated
            # `ended_no_sale` status so the relist flow can target them.
            winner_id = listing.get("highest_bidder_id")
            _update_set = {
                "status": "ended" if winner_id else "ended_no_sale",
                "ended_at": now_str,
            }
            if winner_id:
                _update_set["winner_user_id"] = winner_id
                _update_set["sold_at"] = now_str
                _update_set["final_price"] = float(listing.get("current_price") or 0)
            await db.listings.update_one(
                {"id": listing_id, "status": "active"},
                {"$set": _update_set}
            )

            seller_id = listing.get("seller_id")

            # ─── STRICT PAYMENT SYSTEM (Spec Features 1-3) ───
            # 1) Enqueue non-winner deposit refunds (60s SLA)
            try:
                from services.deposit_refund_queue import enqueue_non_winner_refunds
                deposits_cursor = db.bidding_deposits.find(
                    {"auction_id": listing_id, "status": {"$in": ["held", "authorized"]}},
                    {"_id": 0},
                )
                deposits_list = await deposits_cursor.to_list(500)
                if deposits_list:
                    await enqueue_non_winner_refunds(
                        db,
                        auction_id=listing_id,
                        winner_user_id=winner_id,
                        deposits=deposits_list,
                        deposit_collection="bidding_deposits",
                    )
            except Exception as ref_err:
                logger.warning(f"[auction-end] enqueue non-winner refunds failed: {ref_err}")

            # 2) Settle winner via cash-or-stripe fork
            if winner_id and seller_id:
                try:
                    from services.auction_settlement import settle_auction
                    settle_listing = {**listing, "winner_id": winner_id, "seller_id": seller_id}
                    settlement = await settle_auction(db, auction_id=listing_id, listing=settle_listing)
                    logger.info(
                        f"[auction-settle] {listing_id} → {settlement.get('scenario')}: {settlement}"
                    )
                    # iter298 BUG 3/4 — payment lifecycle: stamp
                    # payment_collected / pending_payment(+link) /
                    # payment_failed, flag payout_pending, issue
                    # receipts + statements.
                    try:
                        from services.payment_collection import finalize_auction_payment
                        await finalize_auction_payment(
                            db,
                            listing={**listing, **_update_set, "id": listing_id},
                            collection="listings",
                            settlement=settlement,
                            section="marketplace",
                        )
                    except Exception as fin_err:
                        logger.exception(f"[payment-finalize] failed for {listing_id}: {fin_err}")
                except Exception as settle_err:
                    logger.exception(f"[auction-settle] failed for {listing_id}: {settle_err}")

            # iter214 P1 — Generate pickup code for cash / e-transfer
            # transactions from INDIVIDUAL sellers (not partners / dealers /
            # storage facilities, which manage payments themselves).
            try:
                seller_doc = await db.users.find_one(
                    {"id": seller_id},
                    {"_id": 0, "account_type": 1, "is_licensed_partner": 1, "is_vehicle_dealer": 1, "is_storage_facility": 1},
                ) or {}
                is_individual_seller = not (
                    seller_doc.get("is_licensed_partner")
                    or seller_doc.get("is_vehicle_dealer")
                    or seller_doc.get("is_storage_facility")
                    or (seller_doc.get("account_type") in {"partner", "vehicle_dealer", "storage_facility"})
                )
                pay_method = (listing.get("payment_method") or "").lower()
                if is_individual_seller and pay_method in {"cash", "etransfer", "interac_e_transfer", "interac"}:
                    pm = "cash" if pay_method == "cash" else "etransfer"
                    from routes.transaction_pickup_code import ensure_pickup_code_on_transaction
                    # Find or create the matching transaction record
                    txn = await db.transactions.find_one(
                        {"$or": [{"listing_id": listing_id}, {"auction_id": listing_id}]},
                        {"_id": 0},
                    )
                    if not txn:
                        import uuid as _u
                        txn_id = str(_u.uuid4())
                        await db.transactions.insert_one({
                            "id": txn_id,
                            "auction_id": listing_id,
                            "listing_id": listing_id,
                            "listing_title": listing.get("title", "Item"),
                            "buyer_id": winner_id,
                            "seller_id": seller_id,
                            "hammer_price": float(listing.get("current_price") or 0),
                            "payment_method": pm,
                            "payment_confirmed": False,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        })
                        txn_for_code = {"id": txn_id}
                    else:
                        txn_for_code = txn
                    code = await ensure_pickup_code_on_transaction(
                        db, txn_for_code["id"],
                        payment_method=pm, seller_id=seller_id, listing_id=listing_id,
                    )
                    if code:
                        logger.info(f"[pickup-code] generated {code} for txn {txn_for_code['id']}")
                        # iter214 P1 — Dispatch dedicated bilingual pickup-code emails
                        try:
                            buyer_doc = await db.users.find_one({"id": winner_id}, {"_id": 0}) or {}
                            seller_full = await db.users.find_one({"id": seller_id}, {"_id": 0}) or {}
                            from services.emails.email_marketplace import (
                                send_buyer_pickup_code_email,
                                send_seller_pickup_instructions_email,
                            )
                            await send_buyer_pickup_code_email(
                                buyer=buyer_doc,
                                seller=seller_full,
                                listing_title=listing.get("title", "Item"),
                                hammer_price=float(listing.get("current_price") or 0),
                                pickup_code=code,
                                payment_method=pm,
                                transaction_id=txn_for_code["id"],
                            )
                            await send_seller_pickup_instructions_email(
                                seller=seller_full,
                                listing_title=listing.get("title", "Item"),
                                hammer_price=float(listing.get("current_price") or 0),
                                payment_method=pm,
                                transaction_id=txn_for_code["id"],
                            )
                        except Exception as email_err:
                            logger.warning(f"[pickup-code] email send failed: {email_err}")
            except Exception as pkup_err:
                logger.warning(f"[pickup-code] generation failed for listing {listing_id}: {pkup_err}")

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
                    # iter296 P0 BUG 4 — Bilingual platform notifications.
                    from services.notifications_i18n import create_notification
                    _final = float(listing.get("current_price", 0) or 0)
                    _title_item = listing.get("title", "Item")
                    # Winner notification
                    await create_notification(
                        db,
                        user_id=winner_id,
                        kind="auction_won",
                        params={"title": _title_item, "amount": _final},
                        data={"listing_id": listing_id, "amount": _final,
                              "action_url": f"/listings/{listing_id}"},
                    )

                    # iter306 — Web Push notification
                    try:
                        from services.push_dispatcher import dispatch_push
                        _cat = (listing.get("category") or "").lower()
                        _is_vehicle = any(v in _cat for v in ("vehicle", "car", "auto"))
                        await dispatch_push(
                            db, user_id=winner_id, kind="auction_won",
                            title_item=_title_item, amount=_final,
                            listing_id=listing_id, is_vehicle=_is_vehicle,
                        )
                    except Exception:
                        pass

                    # Persist to Winner's Circle (30-day retention)
                    try:
                        from routes.user_insights import persist_auction_winner
                        await persist_auction_winner(db, listing_id, winner_id, listing.get("current_price", 0), listing)
                    except Exception as winner_err:
                        logger.warning(f"Winner persistence failed: {winner_err}")
                    
                    # Seller notification (bilingual)
                    await create_notification(
                        db,
                        user_id=seller_id,
                        kind="auction_ended",
                        params={"title": _title_item, "amount": _final},
                        data={"listing_id": listing_id, "amount": _final,
                              "action_url": f"/seller/dashboard"},
                    )

                    # ===== BUG 5: POST-AUCTION EMAILS =====
                    # Derive auction_type for consistent branding (Bug 1)
                    _cat = (listing.get("category") or "").lower()
                    if any(v in _cat for v in ("vehicle", "car", "auto", "truck", "motorcycle", "suv", "van")):
                        _auction_type = "vehicle"
                    else:
                        _auction_type = "marketplace"

                    final_price = float(listing.get("current_price", 0) or 0)

                    # Winner email (Bug 5A)
                    try:
                        if winner and winner.get("email"):
                            from services.emails.email_marketplace import send_auction_won_email
                            # Seller-held platform fee estimate (best-effort, non-blocking)
                            _plat_fee = 0.0
                            try:
                                from services.fee_calculator import PricingManager
                                buyer_user = winner if winner else None
                                buyer_tier = (buyer_user or {}).get("subscription_tier", "free") if buyer_user else "free"
                                seller_tier = (seller or {}).get("subscription_tier", "free") if seller else "free"
                                buyer_province = (buyer_user or {}).get("province") if buyer_user else "QC"
                                pr = PricingManager.non_vehicle_stripe(final_price, buyer_province or "QC", buyer_tier, seller_tier)
                                _plat_fee = float(pr.buyer_invoice.fees_subtotal or 0)
                            except Exception:
                                pass
                            await send_auction_won_email(
                                to_email=winner["email"],
                                to_name=winner.get("name", "Winner"),
                                item_name=listing.get("title", "Item"),
                                auction_id=listing_id,
                                hammer_price=final_price,
                                platform_fee=_plat_fee,
                                is_vehicle=(_auction_type == "vehicle"),
                            )
                    except Exception as win_err:
                        logger.warning(f"[auction-end] winner email failed: {win_err}")

                    # Seller sold email (Bug 5B)
                    try:
                        if seller and seller.get("email"):
                            from services.emails.email_vehicles import (
                                send_seller_auction_sold_email,
                            )
                            # Seller commission (best-effort)
                            _commission = 0.0
                            _net_payout = final_price
                            try:
                                from services.fee_calculator import PricingManager
                                seller_tier = (seller or {}).get("subscription_tier", "free") if seller else "free"
                                buyer_province = "QC"
                                pr2 = PricingManager.non_vehicle_stripe(final_price, buyer_province, "free", seller_tier)
                                if pr2.seller_invoice:
                                    _commission = float(pr2.seller_invoice.fees_subtotal or 0)
                                    _net_payout = float(pr2.seller_invoice.total or (final_price - _commission))
                            except Exception:
                                pass
                            # Privacy-preserving bidder alias
                            winner_raw = (winner.get("name") if winner else "") or (winner.get("email", "").split("@")[0] if winner else "") or "Winner"
                            _parts = winner_raw.split()
                            _alias = f"{_parts[0]} {_parts[1][0]}." if len(_parts) >= 2 else _parts[0]
                            await send_seller_auction_sold_email(
                                seller_email=seller["email"],
                                seller_name=seller.get("name", "Seller"),
                                listing_title=listing.get("title", "Item"),
                                listing_id=listing_id,
                                hammer_price=final_price,
                                platform_fee=_commission,
                                net_payout=_net_payout,
                                winning_bidder_alias=_alias,
                                auction_type=_auction_type,
                            )
                    except Exception as sold_err:
                        logger.warning(f"[auction-end] seller-sold email failed: {sold_err}")

                    # Offline Payment Invoice: if seller chose Cash/E-Transfer, create split invoices
                    payment_method = listing.get("payment_method", "stripe")
                    if payment_method in ("cash", "e-transfer"):
                        from services.fee_calculator import PricingManager
                        sale_price = listing.get("current_price", 0)

                        # Resolve tiers from user profiles
                        buyer_user = await db.users.find_one({"id": winner_id}, {"_id": 0, "subscription_tier": 1, "province": 1})
                        seller_user_doc = await db.users.find_one({"id": seller_id}, {"_id": 0, "subscription_tier": 1})
                        buyer_tier = (buyer_user or {}).get("subscription_tier", "free")
                        seller_tier_val = (seller_user_doc or {}).get("subscription_tier", "free")
                        buyer_province = (buyer_user or {}).get("province", "ON")

                        result = PricingManager.non_vehicle_cash(
                            hammer_price=sale_price,
                            buyer_province=buyer_province,
                            buyer_tier=buyer_tier,
                            seller_tier=seller_tier_val,
                        )

                        bi = result.buyer_invoice
                        si = result.seller_invoice

                        await db.buyer_invoices.insert_one({
                            "id": str(_uuid.uuid4()),
                            "buyer_id": winner_id,
                            "listing_id": listing_id,
                            "listing_title": listing.get("title", ""),
                            "hammer_price": sale_price,
                            "payment_method": payment_method,
                            "fees_subtotal": bi.fees_subtotal,
                            "stripe_recovery": bi.stripe_recovery,
                            "tax_amount": bi.tax_amount,
                            "tax_rate": bi.tax_rate,
                            "tax_type": bi.tax_type,
                            "tax_label": bi.tax_label,
                            "total_due": bi.total,
                            "line_items": [ln.description + f": ${ln.amount:,.2f}" for ln in bi.lines],
                            "status": "pending",
                            "created_at": now_str,
                        })
                        if si:
                            await db.seller_invoices.insert_one({
                                "id": str(_uuid.uuid4()),
                                "seller_id": seller_id,
                                "listing_id": listing_id,
                                "listing_title": listing.get("title", ""),
                                "hammer_price": sale_price,
                                "payment_method": payment_method,
                                "fees_subtotal": si.fees_subtotal,
                                "stripe_recovery": si.stripe_recovery,
                                "tax_amount": si.tax_amount,
                                "tax_rate": si.tax_rate,
                                "tax_type": si.tax_type,
                                "tax_label": si.tax_label,
                                "total_due": si.total,
                                "line_items": [ln.description + f": ${ln.amount:,.2f}" for ln in si.lines],
                                "status": "pending",
                                "created_at": now_str,
                            })
                        logger.info(f"Offline sale invoices created: buyer=${bi.total:.2f}, seller=${si.total if si else 0:.2f}")
                    
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
            else:
                # ===== iter298 BUG 2: Zero-bid end → relist email + notification =====
                try:
                    if seller_id:
                        _seller_no_bids = await db.users.find_one(
                            {"id": seller_id}, {"_id": 0, "name": 1, "email": 1}
                        )
                        _cat_nb = (listing.get("category") or "").lower()
                        _at_nb = "vehicle" if any(
                            v in _cat_nb for v in ("vehicle", "car", "auto", "truck", "motorcycle")
                        ) else "marketplace"
                        if _seller_no_bids and _seller_no_bids.get("email"):
                            from services.emails.email_vehicles import (
                                send_seller_auction_no_bids_email,
                            )
                            await send_seller_auction_no_bids_email(
                                seller_email=_seller_no_bids["email"],
                                seller_name=_seller_no_bids.get("name", "Seller"),
                                listing_title=listing.get("title", "Item"),
                                listing_id=listing_id,
                                auction_type=_at_nb,
                                auction_end_time=str(listing.get("auction_end_date") or now_str),
                                bid_count=int(listing.get("bid_count") or 0),
                            )
                        # Bilingual in-platform notification (EN/FR).
                        from services.notifications_i18n import create_notification
                        await create_notification(
                            db, user_id=seller_id, kind="auction_ended_no_winner",
                            params={"title": listing.get("title", "Item")},
                            data={"listing_id": listing_id,
                                  "action_url": "/seller/dashboard?filter=ended"},
                        )
                except Exception as nb_err:
                    logger.warning(f"[auction-end] no-bids seller email failed: {nb_err}")

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
            # iter296 P0 BUG 1 + 5 — write per-lot winner data + sold/ended
            # counters so the seller dashboard reflects this auction
            # within one scheduler tick.
            # iter298 BUG 2 — zero-bid events flip to `ended_no_sale`.
            _has_any_winner = any((lot.get("highest_bidder_id") for lot in auction.get("lots") or []))
            _mi_update = {
                "status": "ended" if _has_any_winner else "ended_no_sale",
                "ended_at": now_str,
            }
            if _has_any_winner:
                _mi_update["sold_at"] = now_str
            await db.multi_item_listings.update_one(
                {"id": auction_id, "status": "active"},
                {"$set": _mi_update}
            )

            seller_id = auction.get("seller_id")

            # iter298 BUG 2 — zero-bid multi-item event → relist email +
            # bilingual notification to the seller.
            if not _has_any_winner and seller_id:
                try:
                    _seller_nb = await db.users.find_one(
                        {"id": seller_id}, {"_id": 0, "name": 1, "email": 1})
                    if _seller_nb and _seller_nb.get("email"):
                        from services.emails.email_vehicles import (
                            send_seller_auction_no_bids_email,
                        )
                        await send_seller_auction_no_bids_email(
                            seller_email=_seller_nb["email"],
                            seller_name=_seller_nb.get("name", "Seller"),
                            listing_title=auction.get("title", "Auction"),
                            listing_id=auction_id,
                            auction_type="lots",
                            auction_end_time=str(auction.get("auction_end_date") or now_str),
                            bid_count=0,
                        )
                    from services.notifications_i18n import create_notification as _cn
                    await _cn(
                        db, user_id=seller_id, kind="auction_ended_no_winner",
                        params={"title": auction.get("title", "Auction")},
                        data={"listing_id": auction_id,
                              "action_url": "/seller/dashboard?filter=ended"},
                    )
                except Exception as nb_err:
                    logger.warning(f"[lots-end] no-bids seller email failed: {nb_err}")
            
            # iter296 P0 BUG 2/3/4 — Lot-level emails + bilingual platform
            # notifications for the multi-item-listing flow. Mirrors the
            # single-listing branch above.
            from services.notifications_i18n import create_notification

            # Process each lot's winner
            for lot in auction.get("lots", []):
                winner_id = lot.get("highest_bidder_id")
                lot_final = float(lot.get("current_price", 0) or 0)
                lot_title = f"{auction.get('title', 'Auction')} — Lot #{lot.get('lot_number','?')}"
                # Persist lot winner on the document for dashboard counters
                try:
                    await db.multi_item_listings.update_one(
                        {"id": auction_id, "lots.lot_number": lot.get("lot_number")},
                        {"$set": {
                            "lots.$.winner_user_id": winner_id,
                            "lots.$.final_price": lot_final,
                            "lots.$.sold_at": now_str if winner_id else None,
                            "lots.$.status": "sold" if winner_id else "ended",
                        }},
                    )
                except Exception as we:
                    logger.warning(f"[lots-end] could not stamp lot winner: {we}")

                if winner_id and seller_id:
                    try:
                        winner = await db.users.find_one({"id": winner_id}, {"_id": 0, "name": 1, "email": 1, "phone": 1, "subscription_tier": 1, "province": 1})
                        seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "name": 1, "email": 1, "phone": 1, "subscription_tier": 1})
                        
                        await create_auction_won_conversation(
                            db=db,
                            listing_id=auction_id,
                            listing_title=lot_title,
                            winner_id=winner_id,
                            seller_id=seller_id,
                            winning_amount=lot_final,
                            winner_info=winner,
                            seller_info=seller,
                            lot_number=lot["lot_number"]
                        )

                        # Bilingual platform notification — winner
                        await create_notification(
                            db, user_id=winner_id, kind="auction_won",
                            params={"title": lot_title, "amount": lot_final},
                            data={"listing_id": auction_id, "lot_number": lot.get("lot_number"),
                                  "amount": lot_final, "action_url": f"/listings/{auction_id}"},
                        )
                        # Bilingual platform notification — seller
                        await create_notification(
                            db, user_id=seller_id, kind="auction_ended",
                            params={"title": lot_title, "amount": lot_final},
                            data={"listing_id": auction_id, "lot_number": lot.get("lot_number"),
                                  "amount": lot_final, "action_url": "/seller/dashboard"},
                        )

                        # Winner + seller emails (best-effort, non-blocking)
                        try:
                            if winner and winner.get("email"):
                                from services.emails.email_marketplace import send_auction_won_email
                                await send_auction_won_email(
                                    to_email=winner["email"],
                                    to_name=winner.get("name", "Winner"),
                                    item_name=lot_title,
                                    auction_id=auction_id,
                                    hammer_price=lot_final,
                                    platform_fee=0.0,
                                    is_vehicle=False,
                                )
                        except Exception as we_err:
                            logger.warning(f"[lots-end] winner email failed: {we_err}")
                        try:
                            if seller and seller.get("email"):
                                from services.emails.email_vehicles import (
                                    send_seller_auction_sold_email,
                                )
                                # Best-effort 2.5% platform fee math
                                _comm = round(lot_final * 0.025, 2)
                                _net  = round(lot_final - _comm, 2)
                                _w_raw = (winner.get("name") if winner else "") or "Winner"
                                _parts = _w_raw.split()
                                _alias = f"{_parts[0]} {_parts[1][0]}." if len(_parts) >= 2 else _parts[0]
                                await send_seller_auction_sold_email(
                                    seller_email=seller["email"],
                                    seller_name=seller.get("name", "Seller"),
                                    listing_title=lot_title,
                                    listing_id=auction_id,
                                    hammer_price=lot_final,
                                    platform_fee=_comm,
                                    net_payout=_net,
                                    winning_bidder_alias=_alias,
                                    auction_type="marketplace",
                                )
                        except Exception as se_err:
                            logger.warning(f"[lots-end] seller-sold email failed: {se_err}")

                        # iter298 BUG 3/4 — Per-lot automatic charge at
                        # lot close + payment lifecycle + receipts.
                        try:
                            from services.auction_settlement import settle_auction
                            from services.payment_collection import finalize_auction_payment
                            _lot_synthetic = {
                                "id": f"{auction_id}:lot{lot.get('lot_number')}",
                                "title": lot_title,
                                "winner_id": winner_id,
                                "seller_id": seller_id,
                                "final_price": lot_final,
                                "current_price": lot_final,
                                "payment_method": auction.get("payment_method", "stripe"),
                                "currency": auction.get("currency", "CAD"),
                                "auction_end_date": auction.get("auction_end_date"),
                                "listing_type": "lots",
                            }
                            lot_settlement = await settle_auction(
                                db,
                                auction_id=_lot_synthetic["id"],
                                listing=_lot_synthetic,
                            )
                            await finalize_auction_payment(
                                db,
                                listing={**_lot_synthetic, "id": auction_id,
                                         "winner_user_id": winner_id},
                                collection="multi_item_listings",
                                settlement=lot_settlement,
                                section="lots",
                                lot_number=lot.get("lot_number"),
                                listing_title=lot_title,
                                hammer_override=lot_final,
                                winner_override=winner_id,
                            )
                        except Exception as lot_settle_err:
                            logger.exception(
                                f"[lots-settle] failed for {auction_id} lot {lot.get('lot_number')}: {lot_settle_err}"
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
