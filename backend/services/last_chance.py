"""
services/last_chance.py — iter299 P1

"Last Chance — ends in under 1 hour" nudge.

Every 10 minutes the scheduler scans all 4 sections (marketplace,
lots, vehicles, storage — plus PER-LOT for multi-lot vehicle events)
for active auctions ending within the next hour and notifies:

  • everyone who watchlisted the listing
  • everyone who bid but is NOT the current highest bidder

NEVER the current leader (they're already winning). One send per
(user, listing[, lot]) — tracked in `db.last_chance_log` and a
listing-level `last_chance_sent` flag so the job is idempotent.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

WINDOW = timedelta(hours=1)


def _parse_dt(v) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def _in_window(end_raw, now: datetime) -> bool:
    end = _parse_dt(end_raw)
    return bool(end and now < end <= now + WINDOW)


async def _watchers(db, listing_id: str) -> Set[str]:
    rows = await db.watchlist.find(
        {"item_id": listing_id}, {"_id": 0, "user_id": 1}).to_list(2000)
    return {r["user_id"] for r in rows if r.get("user_id")}


async def _notify_user(db, *, user_id: str, listing_id: str, title: str,
                       section: str, dedup_key: str, action_url: str) -> bool:
    """Send email + platform notification once per (user, dedup_key)."""
    already = await db.last_chance_log.find_one(
        {"dedup_key": dedup_key, "user_id": user_id}, {"_id": 0})
    if already:
        return False
    await db.last_chance_log.insert_one({
        "dedup_key": dedup_key,
        "user_id": user_id,
        "listing_id": listing_id,
        "section": section,
        "last_chance_notified_at": datetime.now(timezone.utc).isoformat(),
    })
    user = await db.users.find_one({"id": user_id}, {"_id": 0}) or {}
    if user.get("email"):
        try:
            from services.emails.email_marketplace import send_last_chance_email
            await send_last_chance_email(
                user=user, listing_title=title, listing_id=listing_id,
                action_url=action_url,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[last-chance] email failed for {user_id}/{listing_id}: {e}")
    try:
        from services.notifications_i18n import create_notification
        await create_notification(
            db, user_id=user_id, kind="last_chance",
            params={"title": title},
            data={"listing_id": listing_id, "section": section,
                  "action_url": action_url},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[last-chance] notification failed for {user_id}: {e}")
    return True


async def _dispatch(db, *, listing_id: str, title: str, section: str,
                    bidders: Set[str], leader_ids: Set[str],
                    action_url: str, lot_key: Optional[str] = None) -> int:
    watchers = await _watchers(db, listing_id)
    recipients = (watchers | bidders) - {l for l in leader_ids if l}
    dedup_key = f"{listing_id}:{lot_key}" if lot_key else listing_id
    sent = 0
    for uid in recipients:
        try:
            if await _notify_user(db, user_id=uid, listing_id=listing_id,
                                  title=title, section=section,
                                  dedup_key=dedup_key, action_url=action_url):
                sent += 1
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[last-chance] notify {uid} failed: {e}")
    return sent


async def process_last_chance_nudges(db) -> Dict[str, Any]:
    """Scheduler entrypoint — runs every 10 minutes."""
    now = datetime.now(timezone.utc)
    out = {"marketplace": 0, "lots": 0, "vehicles": 0, "storage": 0,
           "vehicle_multi_lot": 0, "listings_flagged": 0}

    # ── 1. Marketplace listings ─────────────────────────────────────
    cur = db.listings.find(
        {"status": "active", "last_chance_sent": {"$ne": True}},
        {"_id": 0, "id": 1, "title": 1, "auction_end_date": 1, "highest_bidder_id": 1},
    )
    async for l in cur:
        if not _in_window(l.get("auction_end_date"), now):
            continue
        bid_rows = await db.bids.find(
            {"listing_id": l["id"]}, {"_id": 0, "bidder_id": 1}).to_list(2000)
        bidders = {b["bidder_id"] for b in bid_rows if b.get("bidder_id")}
        out["marketplace"] += await _dispatch(
            db, listing_id=l["id"], title=l.get("title", "Item"),
            section="marketplace", bidders=bidders,
            leader_ids={l.get("highest_bidder_id")},
            action_url=f"/listing/{l['id']}",
        )
        await db.listings.update_one(
            {"id": l["id"]}, {"$set": {"last_chance_sent": True}})
        out["listings_flagged"] += 1

    # ── 2. Lots (multi-item events) ─────────────────────────────────
    cur = db.multi_item_listings.find(
        {"status": "active", "last_chance_sent": {"$ne": True}},
        {"_id": 0, "id": 1, "title": 1, "auction_end_date": 1, "lots": 1},
    )
    async for ev in cur:
        if not _in_window(ev.get("auction_end_date"), now):
            continue
        bid_rows = await db.bids.find(
            {"listing_id": ev["id"]}, {"_id": 0, "bidder_id": 1}).to_list(5000)
        bidders = {b["bidder_id"] for b in bid_rows if b.get("bidder_id")}
        leaders = {lot.get("highest_bidder_id") for lot in (ev.get("lots") or [])}
        out["lots"] += await _dispatch(
            db, listing_id=ev["id"], title=ev.get("title", "Auction"),
            section="lots", bidders=bidders, leader_ids=leaders,
            action_url=f"/lots/{ev['id']}",
        )
        await db.multi_item_listings.update_one(
            {"id": ev["id"]}, {"$set": {"last_chance_sent": True}})
        out["listings_flagged"] += 1

    # ── 3. Vehicle auctions (single) ────────────────────────────────
    cur = db.vehicle_listings.find(
        {"status": "active", "last_chance_sent": {"$ne": True}},
        {"_id": 0, "id": 1, "title": 1, "year": 1, "make": 1, "model": 1, "end_time": 1},
    )
    async for v in cur:
        if not _in_window(v.get("end_time"), now):
            continue
        bid_rows = await db.vehicle_bids.find(
            {"listing_id": v["id"]},
            {"_id": 0, "bidder_id": 1, "amount": 1},
        ).sort("amount", -1).to_list(2000)
        bidders = {b["bidder_id"] for b in bid_rows if b.get("bidder_id")}
        leader = bid_rows[0]["bidder_id"] if bid_rows else None
        title = v.get("title") or f"{v.get('year','')} {v.get('make','')} {v.get('model','')}".strip() or "Vehicle"
        out["vehicles"] += await _dispatch(
            db, listing_id=v["id"], title=title, section="vehicles",
            bidders=bidders, leader_ids={leader},
            action_url=f"/vehicle-auctions/{v['id']}",
        )
        await db.vehicle_listings.update_one(
            {"id": v["id"]}, {"$set": {"last_chance_sent": True}})
        out["listings_flagged"] += 1

    # ── 4. Storage auctions ─────────────────────────────────────────
    cur = db.storage_auctions.find(
        {"status": "active", "last_chance_sent": {"$ne": True}},
        {"_id": 0, "id": 1, "title": 1, "unit_label": 1, "unit_number": 1,
         "end_time": 1, "bids": 1},
    )
    async for s in cur:
        if not _in_window(s.get("end_time"), now):
            continue
        embedded = s.get("bids") or []
        bidders = {b.get("bidder_id") for b in embedded if b.get("bidder_id")}
        leader = None
        if embedded:
            leader = max(embedded, key=lambda b: float(b.get("amount") or 0)).get("bidder_id")
        title = s.get("title") or s.get("unit_label") or s.get("unit_number") or "Storage Unit"
        out["storage"] += await _dispatch(
            db, listing_id=s["id"], title=title, section="storage",
            bidders=bidders, leader_ids={leader},
            action_url=f"/storage-auctions/{s['id']}",
        )
        await db.storage_auctions.update_one(
            {"id": s["id"]}, {"$set": {"last_chance_sent": True}})
        out["listings_flagged"] += 1

    # ── 5. Multi-lot vehicle events — PER ACTIVE LOT ────────────────
    cur = db.vehicle_multi_lot_auctions.find(
        {"status": {"$in": ["live", "active"]}},
        {"_id": 0, "id": 1, "title": 1, "lots": 1, "bids": 1},
    )
    async for ev in cur:
        ev_bids = ev.get("bids") or []
        for lot in ev.get("lots") or []:
            if lot.get("last_chance_sent"):
                continue
            if str(lot.get("status") or "").lower() not in ("live", "active", "scheduled"):
                continue
            if not _in_window(lot.get("end_time"), now):
                continue
            lot_id = lot.get("id")
            lot_bids = [b for b in ev_bids if b.get("lot_id") == lot_id]
            bidders = {b.get("bidder_id") for b in lot_bids if b.get("bidder_id")}
            leader = None
            if lot_bids:
                leader = max(lot_bids, key=lambda b: float(b.get("amount") or 0)).get("bidder_id")
            title = lot.get("title") or f"Lot #{lot.get('lot_number')}"
            out["vehicle_multi_lot"] += await _dispatch(
                db, listing_id=ev["id"], title=title, section="vehicles",
                bidders=bidders, leader_ids={leader},
                action_url=f"/vehicle-multi-lot/{ev['id']}",
                lot_key=str(lot_id),
            )
            await db.vehicle_multi_lot_auctions.update_one(
                {"id": ev["id"], "lots.id": lot_id},
                {"$set": {"lots.$.last_chance_sent": True}})
            out["listings_flagged"] += 1

    total = sum(v for k, v in out.items() if k != "listings_flagged")
    if total:
        logger.info(f"[last-chance] sent {total} nudges: {out}")
    return out
