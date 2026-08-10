"""
BidVex Dashboard Router
User-facing dashboard endpoints for buyers and sellers.
"""

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import logging

logger = logging.getLogger(__name__)

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
security = HTTPBearer(auto_error=False)

_db = None
_db_read = None
_get_current_user = None


def set_dashboard_db(db_instance):
    global _db
    _db = db_instance


def set_dashboard_read_db(db_instance):
    global _db_read
    _db_read = db_instance


def set_dashboard_auth(get_current_user_func):
    global _get_current_user

    async def wrapper(credentials):
        class MockRequest:
            cookies = {}
        return await get_current_user_func(MockRequest(), credentials)

    _get_current_user = wrapper


@dashboard_router.get("/seller")
async def get_seller_dashboard(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user(credentials)

    rdb = _db_read if _db_read is not None else _db
    # Fetch single listings
    listings = await rdb.listings.find(
        {"seller_id": current_user.id}, {"_id": 0}
    ).to_list(1000)

    # Fetch multi-item listings
    multi_listings = await rdb.multi_item_listings.find(
        {"seller_id": current_user.id}, {"_id": 0}
    ).to_list(1000)

    all_listings = listings + multi_listings

    # iter454 P0 — Sold (N) blank-tab bug root cause.
    # Historical seller_statement receipts survive listings-collection
    # purges. Prior code incremented counts["sold"] += len(receipts) but
    # never added anything to `all_listings`, so the frontend Sold tab
    # rendered empty while the badge still showed N. Materialize each
    # orphan receipt as a synthetic listing row here so counts and the
    # visible tab feed off the same array.
    seller_receipts = await rdb.receipts.find(
        {"user_id": current_user.id, "type": "seller_statement"},
        {"_id": 0},
    ).sort("created_at", -1).to_list(500)
    known_listing_ids = {l.get("id") for l in all_listings if l.get("id")}
    receipt_only = [
        r for r in seller_receipts
        if r.get("listing_id") and r["listing_id"] not in known_listing_ids
    ]
    synthetic_listings = []
    for r in receipt_only:
        synth = {
            "id":                  r.get("listing_id"),
            "seller_id":           current_user.id,
            "title":               r.get("listing_title") or "Historical sale",
            "status":              "sold",  # by definition — receipt only exists after settlement
            "final_price":         float(r.get("hammer_price") or 0),
            "current_price":       float(r.get("hammer_price") or 0),
            "net_payout_amount":   float(r.get("net_payout") or 0),
            "payment_status":      "payment_collected",
            "payment_collected_at": r.get("created_at"),
            "winner_user_id":      r.get("buyer_id"),
            "auction_end_date":    r.get("created_at"),
            "ended_at":            r.get("created_at"),
            "images":              [],
            "_synthetic_from_receipt": True,
            "receipt_id":          r.get("id"),
        }
        synthetic_listings.append(synth)
    all_listings = all_listings + synthetic_listings
    listings = listings + synthetic_listings  # so the single-listings pane also picks these up

    # iter454 — Single source of truth for dashboard status predicates.
    # Both count badges AND the frontend Sold/Ended split use the SAME
    # logic. Multi-item listings inspect their lot outcomes, not just
    # the parent status.
    _PENDING_STATUSES = ("pending_ai_review", "pending_admin_review", "pending_review")
    _ENDED_STATUSES = ("sold", "ended", "expired", "completed", "ended_no_sale", "unsold")

    def _lots(l):
        return l.get("lots") if isinstance(l.get("lots"), list) else []

    def _has_any_won(l):
        # Parent-level winner (single-item + vehicle convention)
        if l.get("winner_user_id") or l.get("winner_id") or l.get("highest_bidder_id"):
            return True
        # Multi-item: any lot has a winner OR any Buy-Now sold_quantity > 0
        for lot in _lots(l):
            if lot.get("winner_user_id") or lot.get("winner_id") or lot.get("highest_bidder_id"):
                return True
            if int(lot.get("sold_quantity") or 0) > 0:
                return True
        return False

    def _has_any_payment_collected(l):
        if l.get("payment_status") == "payment_collected":
            return True
        for lot in _lots(l):
            if lot.get("payment_status") == "payment_collected":
                return True
        return False

    def _has_any_payment_failed(l):
        # `payment_failed_final` (overdue autocapture) is treated the same
        # as `payment_failed` for the dashboard.
        for status_val in (l.get("payment_status"),):
            if status_val in ("payment_failed", "payment_failed_final"):
                return True
        for lot in _lots(l):
            if lot.get("payment_status") in ("payment_failed", "payment_failed_final"):
                return True
        return False

    def _is_sold(l):
        # A listing is "sold" if the parent status is 'sold' OR the
        # listing is ended AND any winner exists (parent or lot).
        if l.get("status") == "sold":
            return True
        if l.get("status") in ("ended", "expired", "completed") and _has_any_won(l):
            return True
        return False

    def _is_no_sale(l):
        if l.get("status") in ("ended_no_sale", "unsold"):
            return True
        if l.get("status") in ("ended", "expired") and not _has_any_won(l):
            return True
        return False

    def _is_completed(l):
        # Completed = buyer payment collected + pickup confirmed +
        # (settlement finalised, which is the precondition for either flag).
        if l.get("status") == "completed":
            return True
        if l.get("pickup_confirmed") is True and _has_any_payment_collected(l):
            return True
        return False

    active_listings           = [l for l in all_listings if l.get("status") == "active"]
    draft_listings            = [l for l in all_listings if l.get("status") == "draft"]
    pending_review_listings   = [l for l in all_listings if l.get("status") in _PENDING_STATUSES]
    ended_listings            = [l for l in all_listings if l.get("status") in _ENDED_STATUSES]
    sold_listings             = [l for l in all_listings if _is_sold(l)]
    no_sale_listings          = [l for l in ended_listings if _is_no_sale(l)]
    # iter454 — Payment Collected is a SUBSET of Sold. Payment Failed too.
    payment_collected_listings = [l for l in sold_listings if _has_any_payment_collected(l)]
    payment_failed_listings    = [l for l in sold_listings if _has_any_payment_failed(l)]
    completed_listings         = [l for l in all_listings if _is_completed(l)]

    counts = {
        "total":             len(all_listings),
        "active":            len(active_listings),
        "pending_review":    len(pending_review_listings),
        "draft":             len(draft_listings),
        "ended":             len(ended_listings),
        "sold":              len(sold_listings),
        "ended_no_sale":     len(no_sale_listings),
        "payment_collected": len(payment_collected_listings),
        "payment_failed":    len(payment_failed_listings),
        "completed":         len(completed_listings),
    }

    # Post-sale Contact Info — enrich every sold/ended listing with the
    # buyer's contact details so the seller can complete the transaction.
    # Only sold (transaction confirmed) — no info leaked for active listings.
    buyer_ids = {
        l.get("winner_user_id") or l.get("highest_bidder_id") or l.get("winner_id")
        for l in sold_listings
        if l.get("winner_user_id") or l.get("highest_bidder_id") or l.get("winner_id")
    }
    buyer_lookup = {}
    if buyer_ids:
        buyer_docs = await rdb.users.find(
            {"id": {"$in": list(buyer_ids)}},
            {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1},
        ).to_list(len(buyer_ids))
        buyer_lookup = {u["id"]: u for u in buyer_docs}
    for l in sold_listings:
        bid = l.get("winner_user_id") or l.get("highest_bidder_id") or l.get("winner_id")
        b = buyer_lookup.get(bid) if bid else None
        if b:
            l["buyer_contact"] = {
                "name":  b.get("name", ""),
                "email": b.get("email", ""),
                "phone": b.get("phone", ""),
            }

    # iter296 — prefer `final_price` (snapshot at end time) over the
    # live `current_price` so the total doesn't drift if `current_price`
    # is later mutated by an admin tool.
    total_sales = sum(
        float(l.get("final_price") or l.get("current_price") or 0)
        for l in sold_listings
    )

    # iter298 BUG 5 — payment-collected revenue metrics. `total_sales`
    # above remains the legacy all-sold metric; these two only count
    # listings whose payment has actually been collected.
    collected_sales = sum(
        float(l.get("final_price") or l.get("current_price") or 0)
        for l in payment_collected_listings
    )
    net_payout_total = sum(
        float(l.get("net_payout_amount")
              or round(float(l.get("final_price") or l.get("current_price") or 0) * 0.975, 2))
        for l in payment_collected_listings
    )

    # iter367/iter454 — Historical seller_statement receipts.
    # Since iter454, orphan receipts (listing_id purged from
    # listings/multi_item_listings) are materialized as synthetic rows
    # in `all_listings` above. That means sold_listings /
    # payment_collected_listings ALREADY include them, and
    # total_sales / collected_sales / net_payout_total are correct
    # WITHOUT any additive block. We retain the receipts array for the
    # UI and for the dashboard "Statements" pane below.
    receipt_only_sales: list = []

    # iter456 — Per-lot outcome rows for the Ended-tab splits.
    # Each entry represents ONE card to render — a specific lot for
    # multi-item listings, or a single-listing outcome, or a
    # historical settlement (orphan receipt). Frontend uses this array
    # for Sold / No Sale / Payment Collected / Payment Failed /
    # Completed tabs so each lot's real outcome is visible on its own
    # card. Never rely on ambiguous parent-listing rows.
    def _outcome_status(l, lot=None):
        # Effective status for one card.
        parent_status = (l or {}).get("status") or ""
        lot_dict = lot or {}
        parent_won = bool((l or {}).get("winner_user_id")
                          or (l or {}).get("winner_id")
                          or (l or {}).get("highest_bidder_id"))
        lot_won = bool(lot_dict.get("winner_user_id")
                       or lot_dict.get("winner_id")
                       or lot_dict.get("highest_bidder_id")
                       or int(lot_dict.get("sold_quantity") or 0) > 0)
        won = lot_won if lot is not None else parent_won
        if parent_status == "sold" and (lot is None or won):
            return "sold"
        if parent_status == "completed" and (lot is None or won):
            return "completed"
        if parent_status in ("ended", "expired", "completed"):
            return "sold" if won else "no_sale"
        if parent_status in ("ended_no_sale", "unsold"):
            return "no_sale"
        return None  # not an ended outcome

    def _payment_status_for_outcome(l, lot=None):
        candidates = []
        if lot is not None:
            candidates.append(lot.get("payment_status"))
        candidates.append((l or {}).get("payment_status"))
        for c in candidates:
            if c in ("payment_collected", "payment_failed",
                     "payment_failed_final", "payment_pending"):
                return c
        return None

    lot_outcomes = []
    for l in all_listings:
        parent_status = l.get("status") or ""
        is_synth = bool(l.get("_synthetic_from_receipt"))
        is_multi = isinstance(l.get("lots"), list) and len(l["lots"]) > 0
        # A. Historical orphan receipt → one "Historical settlement" card.
        if is_synth:
            lot_outcomes.append({
                "outcome_id": f"hist-{l.get('receipt_id') or l.get('id')}",
                "listing_id": l.get("id"),
                "listing_type": "historical",
                "parent_title": l.get("title") or "Historical settlement",
                "lot_number": None,
                "lot_title": "Historical settlement",
                "lot_description": "",
                "quantity_sold": 1,
                "quantity_remaining": 0,
                "unit_price": float(l.get("final_price") or 0),
                "hammer_total": float(l.get("final_price") or 0),
                "outcome_status": "sold",
                "payment_status": "payment_collected",
                "pickup_confirmed": False,
                "buyer_id": l.get("winner_user_id"),
                "ended_at": l.get("ended_at") or l.get("auction_end_date"),
                "images": [],
                "receipt_id": l.get("receipt_id"),
                "is_historical": True,
                "net_payout_amount": float(l.get("net_payout_amount") or 0),
            })
            continue
        # B. Only listings whose parent is ENDED produce lot outcomes.
        if parent_status not in ("sold", "ended", "expired", "completed",
                                 "ended_no_sale", "unsold"):
            continue
        # C. Single-listing outcome.
        if not is_multi:
            os_status = _outcome_status(l, lot=None)
            if os_status is None:
                continue
            lot_outcomes.append({
                "outcome_id": f"single-{l.get('id')}",
                "listing_id": l.get("id"),
                "listing_type": "single",
                "parent_title": l.get("title") or "",
                "lot_number": None,
                "lot_title": l.get("title") or "",
                "lot_description": l.get("description") or "",
                "quantity_sold": 1 if os_status in ("sold", "completed") else 0,
                "quantity_remaining": 0,
                "unit_price": float(l.get("final_price")
                                    or l.get("current_price") or 0),
                "hammer_total": float(l.get("final_price")
                                      or l.get("current_price") or 0),
                "outcome_status": os_status,
                "payment_status": _payment_status_for_outcome(l),
                "pickup_confirmed": bool(l.get("pickup_confirmed")
                                         or l.get("status") == "completed"),
                "buyer_id": (l.get("winner_user_id") or l.get("winner_id")),
                "ended_at": l.get("ended_at") or l.get("auction_end_date"),
                "images": l.get("images") or [],
                "receipt_id": None,
                "is_historical": False,
                "net_payout_amount": float(l.get("net_payout_amount") or 0),
            })
            continue
        # D. Multi-item: one outcome per lot.
        multiply = bool(l.get("multiply_hammer_by_quantity"))
        for lot in l["lots"]:
            os_status = _outcome_status(l, lot=lot)
            if os_status is None:
                continue
            lot_num = lot.get("lot_number")
            qty_orig = int(lot.get("quantity") or 0) or None
            bn_sold = int(lot.get("sold_quantity") or 0)
            auction_won = int(lot.get("winning_quantity")
                              or lot.get("quantity_won") or 0)
            has_bid_winner = bool(lot.get("winner_user_id")
                                  or lot.get("winner_id")
                                  or lot.get("highest_bidder_id"))
            qty_sold = bn_sold + (auction_won if has_bid_winner else 0)
            qty_remaining = (qty_orig - qty_sold) if qty_orig else None
            unit_price = float(lot.get("winning_unit_price")
                               or lot.get("final_price")
                               or lot.get("current_price") or 0)
            if os_status in ("sold", "completed"):
                if multiply and qty_sold > 1:
                    hammer_total = round(unit_price * qty_sold, 2)
                else:
                    hammer_total = round(unit_price, 2)
            else:
                hammer_total = 0.0
            lot_outcomes.append({
                "outcome_id": f"lot-{l.get('id')}-{lot_num}",
                "listing_id": l.get("id"),
                "listing_type": "multi_item",
                "parent_title": l.get("title") or "",
                "lot_number": lot_num,
                "lot_title": lot.get("title") or "",
                "lot_description": lot.get("description") or "",
                "quantity_sold": qty_sold,
                "quantity_remaining": qty_remaining,
                "unit_price": unit_price,
                "hammer_total": hammer_total,
                "outcome_status": os_status,
                "payment_status": _payment_status_for_outcome(l, lot=lot),
                "pickup_confirmed": bool(lot.get("pickup_confirmed")
                                         or l.get("pickup_confirmed")
                                         or l.get("status") == "completed"),
                "buyer_id": (lot.get("winner_user_id") or lot.get("winner_id")
                             or l.get("winner_user_id")),
                "ended_at": (lot.get("sold_at") or l.get("ended_at")
                             or l.get("auction_end_date")),
                "images": lot.get("images") or l.get("images") or [],
                "receipt_id": None,
                "is_historical": False,
                "net_payout_amount": 0.0,
            })

    # iter456 — Rebuild the Ended-tab counts from outcomes so the badge
    # count and the visible cards can never diverge.
    def _oc_sold(o):
        return o["outcome_status"] in ("sold", "completed")

    def _oc_pc(o):
        return _oc_sold(o) and o.get("payment_status") == "payment_collected"

    def _oc_pf(o):
        return _oc_sold(o) and o.get("payment_status") in (
            "payment_failed", "payment_failed_final")

    def _oc_completed(o):
        return o["outcome_status"] == "completed" or (
            _oc_sold(o) and o.get("pickup_confirmed") and o.get("payment_status")
            == "payment_collected")

    def _oc_ns(o):
        return o["outcome_status"] == "no_sale"

    counts["sold"]              = sum(1 for o in lot_outcomes if _oc_sold(o))
    counts["ended_no_sale"]     = sum(1 for o in lot_outcomes if _oc_ns(o))
    counts["payment_collected"] = sum(1 for o in lot_outcomes if _oc_pc(o))
    counts["payment_failed"]    = sum(1 for o in lot_outcomes if _oc_pf(o))
    counts["completed"]         = sum(1 for o in lot_outcomes if _oc_completed(o))
    counts["ended"]             = sum(1 for o in lot_outcomes)

    return {
        "active_listings": len(active_listings),
        # iter454 — receipts now live inside sold_listings via synthetic
        # rows, so no additional receipt_only_sales adjustment here.
        "sold_listings": len(sold_listings),
        "draft_listings": len(draft_listings),
        "total_sales": round(total_sales, 2),
        # iter298 BUG 5 — payment-collected metrics + statement links.
        "collected_sales": round(collected_sales, 2),
        "net_payout_total": round(net_payout_total, 2),
        "listings": listings,
        "multi_item_listings": multi_listings,
        "all_listings": all_listings,
        # iter456 — Per-lot outcome cards for the Ended-tab splits.
        "lot_outcomes": lot_outcomes,
        # HOTFIX v9.1 / Fix 3 — Filter-tab counts for the seller dashboard.
        "counts": counts,
        # iter367 — Historical sales recovered from receipts.
        "seller_statements": seller_receipts,
    }


@dashboard_router.get("/buyer")
async def get_buyer_dashboard(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user(credentials)

    rdb = _db_read if _db_read is not None else _db
    bids = await rdb.bids.find(
        {"bidder_id": current_user.id}, {"_id": 0}
    ).to_list(1000)

    listing_ids = list(set(bid["listing_id"] for bid in bids))
    listings = await rdb.listings.find(
        {"id": {"$in": listing_ids}}, {"_id": 0}
    ).to_list(1000)

    # iter367 P0 — Dashboard Analytics fix
    # ROOT CAUSE: When listings are purged post-settlement (common in
    # long-lived DBs, and every preview refresh), `listings` returns []
    # for old bid_ids. The old code then rendered every historical bid
    # as "OUTBID $0.00" because it couldn't find the listing.
    #
    # FIX: Also read from `won_auctions` (canonical won-item history)
    # and buyer `receipts` (canonical paid history). Merge both into the
    # dashboard so historical activity survives listings purges.
    won_auctions_docs = await rdb.won_auctions.find(
        {"winner_id": current_user.id, "archived": {"$ne": True}},
        {"_id": 0},
    ).sort("won_at", -1).to_list(200)
    won_by_listing = {w["listing_id"]: w for w in won_auctions_docs if w.get("listing_id")}

    buyer_receipts = await rdb.receipts.find(
        {"user_id": current_user.id, "type": "buyer_receipt"},
        {"_id": 0},
    ).sort("created_at", -1).to_list(200)
    receipts_by_listing = {r["listing_id"]: r for r in buyer_receipts if r.get("listing_id")}

    # Fetch watchlist items
    watchlist_items = await rdb.watchlist.find(
        {"user_id": current_user.id}, {"_id": 0}
    ).to_list(100)
    watchlist_listing_ids = [item["listing_id"] for item in watchlist_items if "listing_id" in item]
    watchlist_listings = await rdb.listings.find(
        {"id": {"$in": watchlist_listing_ids}, "status": {"$ne": "deleted"}},
        {"_id": 0},
    ).to_list(100)

    # Post-sale Contact Info — for each WON listing (user is the winner
    # AND auction has ended), surface the seller's contact details so the
    # buyer can complete the transaction. Pulled from existing user profile;
    # no info leaked for active listings.
    # iter298 BUG 5 — winner detection covers all conventions:
    # `winner_user_id` (canonical since iter296), legacy `winner_id`,
    # and `highest_bidder_id` on ended/sold docs.
    # iter367 — Also consult `won_auctions` fallback: a listing_id in
    # `won_by_listing` means we won it (survives listings-collection purges).
    def _is_won_by_me(l: dict) -> bool:
        if l.get("id") and l["id"] in won_by_listing:
            return True
        if l.get("status") not in ("sold", "ended", "completed"):
            return False
        me = current_user.id
        return (
            l.get("winner_user_id") == me
            or l.get("winner_id") == me
            or l.get("highest_bidder_id") == me
        )

    won_listings = [l for l in listings if _is_won_by_me(l)]
    seller_ids = {l.get("seller_id") for l in won_listings if l.get("seller_id")}
    seller_lookup = {}
    if seller_ids:
        seller_docs = await rdb.users.find(
            {"id": {"$in": list(seller_ids)}},
            {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1},
        ).to_list(len(seller_ids))
        seller_lookup = {u["id"]: u for u in seller_docs}
    for l in won_listings:
        s = seller_lookup.get(l.get("seller_id"))
        if s:
            l["seller_contact"] = {
                "name":  s.get("name", ""),
                "email": s.get("email", ""),
                "phone": s.get("phone", ""),
            }

    # iter298 BUG 5 — attach receipt link + payment/pickup status to won rows.
    won_ids = [l["id"] for l in won_listings]
    receipt_rows = []
    if won_ids:
        receipt_rows = await rdb.receipts.find(
            {"user_id": current_user.id, "type": "buyer_receipt",
             "listing_id": {"$in": won_ids}},
            {"_id": 0, "id": 1, "listing_id": 1},
        ).to_list(200)
    receipt_by_listing = {r["listing_id"]: r["id"] for r in receipt_rows}
    won_items_detail = []
    for l in won_listings:
        won_items_detail.append({
            "listing_id": l["id"],
            "title": l.get("title", "Item"),
            "final_price": l.get("final_price") or l.get("current_price") or 0,
            "payment_status": l.get("payment_status") or ("pending_payment" if not l.get("payment_collected_at") else "payment_collected"),
            "payment_link_url": l.get("payment_link_url"),
            "pickup_confirmed": bool(l.get("pickup_confirmed")),
            "pickup_confirmed_at": l.get("pickup_confirmed_at"),
            # iter302 Directive 2 — winner-only surface (this endpoint only
            # returns listings won by the current user).
            "pickup_code": l.get("pickup_code"),
            "receipt_id": receipt_by_listing.get(l["id"]),
            "sold_at": l.get("sold_at") or l.get("ended_at"),
        })

    # iter298 BUG 5 — winning (live high-bidder), lost, and deposits.
    listings_by_id = {l["id"]: l for l in listings}
    my_max_bid: dict = {}
    for b in bids:
        lid = b.get("listing_id")
        if lid:
            my_max_bid[lid] = max(my_max_bid.get(lid, 0), float(b.get("amount") or 0))

    winning_bid_ids = []
    lost_bid_ids = []
    for lid, my_max in my_max_bid.items():
        l = listings_by_id.get(lid)
        if not l:
            # iter367 — listing purged from DB. Check won_auctions to
            # decide whether the buyer WON or LOST this historical bid.
            if lid in won_by_listing:
                # bid_status handled below via won_by_listing lookup
                continue
            # Not in won_auctions → historical loss.
            lost_bid_ids.append(lid)
            continue
        if l.get("status") == "active":
            is_leader = (
                l.get("highest_bidder_id") == current_user.id
                or float(l.get("current_price") or 0) == my_max
            )
            if is_leader:
                winning_bid_ids.append(lid)
        elif l.get("status") in ("sold", "ended", "completed", "ended_no_sale"):
            if not _is_won_by_me(l):
                lost_bid_ids.append(lid)

    # iter367 — Enrich each bid with a bid_status ('winning'|'won'|'outbid'|
    # 'lost'|'ended_no_listing') and a canonical price so frontend never
    # renders "OUTBID $0.00" for historical activity.
    for b in bids:
        lid = b.get("listing_id")
        l = listings_by_id.get(lid) if lid else None
        won = won_by_listing.get(lid) if lid else None
        receipt = receipts_by_listing.get(lid) if lid else None
        # Attach a stable canonical price and title for the bid card.
        if won:
            b["_won_auction"] = {
                "listing_title": won.get("listing_title") or "Auction item",
                "listing_image": won.get("listing_image"),
                "winning_bid": won.get("winning_bid"),
                "won_at": won.get("won_at"),
                "currency": won.get("currency", "CAD"),
            }
        if receipt:
            b["_receipt"] = {
                "id": receipt.get("id"),
                "hammer_price": receipt.get("hammer_price"),
                "total_charged": receipt.get("total_charged"),
                "pickup_code": receipt.get("pickup_code"),
            }
        if l and l.get("status") == "active":
            is_leader = (
                l.get("highest_bidder_id") == current_user.id
                or float(l.get("current_price") or 0) == float(b.get("amount") or 0)
            )
            b["bid_status"] = "winning" if is_leader else "outbid"
        elif won:
            b["bid_status"] = "won"
        elif l and l.get("status") in ("sold", "ended", "completed") and _is_won_by_me(l):
            b["bid_status"] = "won"
        elif l and l.get("status") in ("sold", "ended", "completed", "ended_no_sale"):
            b["bid_status"] = "lost"
        elif not l:
            # Listing purged but no won_auctions row → treat as ended/lost.
            b["bid_status"] = "ended_no_listing"
        else:
            b["bid_status"] = "outbid"

    # iter367 — Merge historical won_auctions into won_items_detail so
    # they display even when the source listing has been purged.
    seen_ids = {w["listing_id"] for w in won_items_detail}
    for w in won_auctions_docs:
        lid = w.get("listing_id")
        if not lid or lid in seen_ids:
            continue
        receipt = receipts_by_listing.get(lid) or {}
        won_items_detail.append({
            "listing_id": lid,
            "title": w.get("listing_title") or "Auction item",
            "listing_image": w.get("listing_image"),
            "final_price": receipt.get("hammer_price") or w.get("winning_bid") or 0,
            "payment_status": "payment_collected" if receipt.get("id") else "pending_payment",
            "payment_link_url": None,
            "pickup_confirmed": False,
            "pickup_confirmed_at": None,
            "pickup_code": receipt.get("pickup_code"),
            "receipt_id": receipt.get("id"),
            "sold_at": w.get("won_at"),
            "currency": w.get("currency", "CAD"),
        })
        seen_ids.add(lid)

    deposits = await rdb.bidding_deposits.find(
        {"user_id": current_user.id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    storage_deps = await rdb.storage_deposits.find(
        {"user_id": current_user.id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    for d in storage_deps:
        d["deposit_type"] = "storage"
    for d in deposits:
        d.setdefault("deposit_type", "bidding")

    # iter367 — won_items count now includes historical won_auctions
    # entries whose source listings are no longer in the `listings`
    # collection (post-cleanup or preview refresh survivors).
    total_won_items = len(set(
        [l["id"] for l in won_listings if l.get("id")]
        + [w["listing_id"] for w in won_auctions_docs if w.get("listing_id")]
    ))

    return {
        "total_bids": len(bids),
        "active_bids": len(
            [
                b
                for b in bids
                if any(
                    l["status"] == "active"
                    for l in listings
                    if l["id"] == b["listing_id"]
                )
            ]
        ),
        # iter298 BUG 5 — corrected won counter + new winning/lost/deposits.
        # iter367 — total_won_items uses union so purged-listing wins count.
        "won_items": total_won_items,
        "won_items_detail": won_items_detail,
        "won_auctions": won_auctions_docs,
        "winning_bids": len(winning_bid_ids),
        "winning_listing_ids": winning_bid_ids,
        "lost_bids": len(lost_bid_ids),
        "lost_listing_ids": lost_bid_ids,
        "deposits": deposits + storage_deps,
        "bids": bids,
        "listings": listings,
        "watchlist": watchlist_listings,
    }


# iter206 — Seller-facing compliance notifications (pause / approval / rejection)
@dashboard_router.get("/seller/notifications")
async def get_seller_notifications(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user(credentials)
    rdb = _db_read if _db_read is not None else _db
    notifications = await rdb.seller_notifications.find(
        {"seller_id": current_user.id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(50)
    unread = sum(1 for n in notifications if not n.get("read"))
    return {"notifications": notifications, "unread": unread}


@dashboard_router.post("/seller/notifications/{notification_kind}/mark-read")
async def mark_seller_notification_read(
    notification_kind: str,  # "all" or a specific kind
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")
    current_user = await _get_current_user(credentials)
    query = {"seller_id": current_user.id}
    if notification_kind != "all":
        query["kind"] = notification_kind
    res = await _db.seller_notifications.update_many(query, {"$set": {"read": True}})
    return {"ok": True, "marked": res.modified_count}



# iter211 — Pickup-coordination notifications (post-payment winner ↔ seller)
@dashboard_router.get("/pickup-notifications")
async def get_pickup_notifications(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Return pickup-coordination rows for the current user (winner or seller side)."""
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")
    current_user = await _get_current_user(credentials)
    rdb = _db_read if _db_read is not None else _db
    notifications = await rdb.pickup_notifications.find(
        {"user_id": current_user.id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(50)
    unread = sum(1 for n in notifications if not n.get("read"))
    return {"notifications": notifications, "unread": unread}


@dashboard_router.post("/pickup-notifications/{notification_id}/mark-read")
async def mark_pickup_notification_read(
    notification_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")
    current_user = await _get_current_user(credentials)
    query = {"user_id": current_user.id}
    if notification_id != "all":
        query["id"] = notification_id
    res = await _db.pickup_notifications.update_many(query, {"$set": {"read": True}})
    return {"ok": True, "marked": res.modified_count}
