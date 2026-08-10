"""
Multi-Lot Vehicle Auction Scheduler — iter293 Directive 2
=========================================================

Background tick (called every ~15s by APScheduler in server.py) that:
  1. Promotes UPCOMING events whose `start_time` has elapsed to LIVE
     (and activates lot 1 in sequential mode).
  2. Detects ended lots (end_time <= now) and finalises them — sets
     status='sold' (if there's a winner) or 'ended' (no bids).
  3. Activates the next lot in sequential mode (2-minute window
     default, driven by event.lot_duration_seconds).
  4. Closes the event when every lot has ended.

Soft-close is handled inside the bid endpoint by extending the
current lot's `end_time` by +120s. This scheduler picks up the
extended end_time on the next tick so no extra logic needed here.

Constraints honoured:
- No fee math touched.
- No JWT / Stripe / SendGrid wiring changed.
- Idempotent: re-running a tick on the same state is a no-op.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List
import logging

logger = logging.getLogger("vehicle_multi_lot_scheduler")

# Soft-close window (kept in sync with the bid endpoint).
_SOFT_CLOSE_SECONDS = 120


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_dt(v: Any) -> Any:
    """Normalise datetimes pulled from Mongo (which return naïve UTC
    instances) to timezone-aware so they compare cleanly with
    `datetime.now(timezone.utc)`."""
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:
            return None
    if isinstance(v, datetime) and v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    return v


async def tick_once(db) -> Dict[str, int]:
    """Single scheduler tick. Returns counts for observability."""
    now = _now()
    counts = {"events_promoted": 0, "lots_ended": 0, "lots_activated": 0, "events_completed": 0}

    # Promote upcoming events whose start_time has elapsed.
    upcoming_cursor = db.vehicle_multi_lot_auctions.find(
        {"status": "upcoming", "start_time": {"$lte": now}}
    )
    async for event in upcoming_cursor:
        try:
            await _promote_event_to_live(db, event, now)
            counts["events_promoted"] += 1
        except Exception as e:
            logger.exception(f"Failed to promote event {event.get('id')}: {e}")

    # Walk live events and close any ended lots; activate next lot.
    live_cursor = db.vehicle_multi_lot_auctions.find({"status": "live"})
    async for event in live_cursor:
        try:
            ended, activated, completed = await _progress_event(db, event, now)
            counts["lots_ended"]      += ended
            counts["lots_activated"]  += activated
            if completed:
                counts["events_completed"] += 1
        except Exception as e:
            logger.exception(f"Failed to progress event {event.get('id')}: {e}")

    return counts


async def _promote_event_to_live(db, event: Dict[str, Any], now: datetime) -> None:
    """Flip upcoming → live and activate lot 1 (sequential) or all
    pre-staggered lots whose start_time has arrived."""
    lots: List[Dict[str, Any]] = event.get("lots") or []
    timing = event.get("timing_mode") or "sequential"
    duration = int(event.get("lot_duration_seconds") or 120)

    if not lots:
        return

    if timing == "sequential":
        lot0 = lots[0]
        start = _coerce_dt(lot0.get("start_time")) or now
        lot0["start_time"] = start
        lot0["end_time"]   = start + timedelta(seconds=duration)
        lot0["status"]     = "live"
        active_idx = 0
    else:  # staggered
        active_idx = -1
        for i, lot in enumerate(lots):
            ls = _coerce_dt(lot.get("start_time"))
            if ls and ls <= now and lot.get("status") == "upcoming":
                lot["status"] = "live"
                if active_idx < 0:
                    active_idx = i

    await db.vehicle_multi_lot_auctions.update_one(
        {"id": event["id"]},
        {"$set": {
            "status": "live",
            "current_active_lot_index": active_idx,
            "lots": lots,
            "updated_at": now,
        }},
    )


async def _progress_event(db, event: Dict[str, Any], now: datetime) -> tuple[int, int, bool]:
    """End any lots whose end_time has elapsed, activate the next lot
    in sequential mode, and close the event if every lot is done.
    Returns (ended_count, activated_count, completed_bool)."""
    lots: List[Dict[str, Any]] = event.get("lots") or []
    timing = event.get("timing_mode") or "sequential"
    duration = int(event.get("lot_duration_seconds") or 120)

    ended_count = 0
    activated_count = 0
    mutated = False
    just_sold: List[Dict[str, Any]] = []     # iter294 P1 — collect winners for email batch
    just_ended_no_winner: List[Dict[str, Any]] = []  # iter295 P1 — refund deposits even on no-bid lots

    # End all expired LIVE lots.
    for lot in lots:
        if lot.get("status") != "live":
            continue
        end = _coerce_dt(lot.get("end_time"))
        if end and end <= now:
            if lot.get("winner_user_id"):
                lot["status"] = "sold"
                just_sold.append(lot)
            else:
                lot["status"] = "ended"
                just_ended_no_winner.append(lot)
            ended_count += 1
            mutated = True

    # Sequential mode: if no LIVE lot remains and there's a next
    # UPCOMING lot, activate it with a fresh 2-min window.
    if timing == "sequential":
        any_live = any(lt.get("status") == "live" for lt in lots)
        if not any_live:
            for idx, lot in enumerate(lots):
                if lot.get("status") == "upcoming":
                    lot["start_time"] = now
                    lot["end_time"]   = now + timedelta(seconds=duration)
                    lot["status"]     = "live"
                    activated_count += 1
                    mutated = True
                    # Track active index
                    event["current_active_lot_index"] = idx
                    break

    # Staggered mode: activate any UPCOMING lot whose pre-set
    # start_time has arrived.
    if timing == "staggered":
        for idx, lot in enumerate(lots):
            if lot.get("status") == "upcoming":
                ls = _coerce_dt(lot.get("start_time"))
                if ls and ls <= now:
                    lot["status"] = "live"
                    activated_count += 1
                    mutated = True
                    if event.get("current_active_lot_index", -1) < 0:
                        event["current_active_lot_index"] = idx

    # All done?
    completed = all(lt.get("status") in ("ended", "sold") for lt in lots) if lots else False
    new_status = "ended" if completed else "live"

    if mutated or completed:
        await db.vehicle_multi_lot_auctions.update_one(
            {"id": event["id"]},
            {"$set": {
                "status":                   new_status,
                "lots":                     lots,
                "current_active_lot_index": event.get("current_active_lot_index", -1),
                "updated_at":               now,
            }},
        )

    # iter294 P1 — Lot-won notifications. Fire AFTER the write so the
    # buyer-facing page sees status=sold before the email arrives.
    # iter460 — dedup gate: one buyer email per (event, buyer). Settle_lot
    # also fires an auction_won email under the same "auction_won" claim
    # so this fan-out and settle_lot's email cannot both send; whichever
    # runs first wins the claim.
    if just_sold:
        try:
            from services.emails import email_marketplace as _en
            from services.settlement_email_dedup import claim_settlement_email as _sed_claim
            import asyncio as _aio

            async def _sched_email_gated(_slot):
                winner_id = _slot.get("winner_user_id")
                if not winner_id:
                    return
                _w = await db.users.find_one(
                    {"id": winner_id}, {"email": 1, "first_name": 1, "_id": 0}
                )
                if not _w or not _w.get("email"):
                    return
                _claim = await _sed_claim(
                    db, kind="auction_won",
                    auction_id=event["id"], user_id=winner_id,
                )
                if not _claim:
                    return
                await _en.send_auction_won_email(
                    winner_email=_w["email"],
                    winner_name=_w.get("first_name") or "",
                    item_title=f"Lot #{_slot.get('lot_number', '?')} — {_slot.get('title', event.get('title', 'Multi-Lot Auction'))}",
                    final_price=float(_slot.get("current_bid") or 0),
                    listing_id=event["id"],
                    is_vehicle=True,
                )

            for slot in just_sold:
                _aio.create_task(_sched_email_gated(slot))
        except Exception as _e:
            logger.warning(f"multi-lot lot_won email failed: {_e}")

    # iter295 P1 — Per-lot settlement: generate invoices for sold lots
    # and refund deposits (winners' deposit stays applied; losers/
    # unsold get refunded). Settlement is best-effort; errors log but
    # never break the scheduler tick.
    if just_sold or just_ended_no_winner:
        try:
            from services.vehicle_multi_lot_settlement import settle_lot
            # Refresh the event with the post-update lots so winner data
            # is consistent with what we just wrote to Mongo.
            fresh = await db.vehicle_multi_lot_auctions.find_one(
                {"id": event["id"]}, {"_id": 0},
            ) or event
            fresh_lots = fresh.get("lots") or lots
            for slot in just_sold + just_ended_no_winner:
                fresh_lot = next((lt for lt in fresh_lots if lt.get("id") == slot.get("id")), slot)
                try:
                    await settle_lot(db, event=fresh, lot=fresh_lot)
                except Exception as _se:
                    logger.warning(f"[multi_lot_settle] lot {slot.get('id')} failed: {_se}")
        except Exception as _e:
            logger.warning(f"multi-lot settlement init failed: {_e}")

    return ended_count, activated_count, completed
