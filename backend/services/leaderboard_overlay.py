"""
iter317 Directive 1 — Weekly Leaderboard Commission Overlay.

Pure rate-math + a Monday 08:00 EST cron that adjusts every contractor's
`leaderboard_overlay_rate` field based on their 7-day commission volume.

Rules (locked by user spec):
  • Top 5 contractors by last-7-day SUM(commission_amount) get +1.0%
    overlay on entry (or stay flat if already in Top 5).
  • Anyone who DROPPED OUT of the Top 5 since the previous run gets
    -1.0% overlay.
  • Hard limits, applied INSIDE `clamp_leaderboard_overlay()`:
      - Effective total rate (base + overlay) cannot dip below 5.0%.
      - Overlay absolute ceiling is +20.0%.
  • Every contractor receives an audit entry in `users.leaderboard_history`
    on every run, even when the delta is 0.0% — so the history is a true
    week-by-week timeline.

Idempotency:
  • The cron is keyed by ISO-week (e.g. "2026-W08"). A second invocation
    in the same calendar week is a no-op (returns the previously
    persisted batch summary).

The pure math lives in `clamp_leaderboard_overlay()` for ergonomic unit
testing — the cron's DB choreography is in `run_weekly_leaderboard_overlay()`.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

logger = logging.getLogger(__name__)


# ─── Constants (locked by Directive 1) ───────────────────────────────────

LEADERBOARD_TOP_N = 5
OVERLAY_DELTA = 0.01            # +1% / -1% per movement event
EFFECTIVE_TOTAL_FLOOR = 0.05    # 5.0% floor on (base + overlay)
OVERLAY_CEILING = 0.20          # 20.0% absolute cap on overlay value
OVERLAY_FLOOR_ABSOLUTE = -1.0   # No symmetric ceiling on the NEGATIVE side
                                # except the implicit (base + overlay) >= 5%
                                # rule which dominates in practice.

# Approximate "Monday 08:00 EST" for the cron registration — APScheduler's
# CronTrigger handles DST automatically when given a tz-aware timezone.
LEADERBOARD_CRON_TZ = "America/Toronto"
LEADERBOARD_CRON_HOUR = 8
LEADERBOARD_CRON_DAY_OF_WEEK = "mon"


def clamp_leaderboard_overlay(
    *,
    base_rate: float,
    current_overlay: float,
    proposed_delta: float,
) -> Tuple[float, float, str]:
    """Pure math — apply the proposed delta to current_overlay and clamp.

    Returns
    -------
    (clamped_overlay, applied_delta, clamp_reason)
        clamped_overlay : final overlay value AFTER clamping.
        applied_delta   : the actual change that took effect
                          (proposed_delta minus anything we had to clamp).
        clamp_reason    : "" if no clamp; otherwise one of:
                          "ceiling_hit"    — overlay would exceed +20%
                          "floor_hit"      — overlay would push total < 5%

    Notes
    -----
    * `current_overlay` is treated as the AUTHORITATIVE prior value. We
      do NOT widen it beyond what's stored; we only clamp the NEW value.
    * Ceiling = OVERLAY_CEILING (absolute cap on overlay).
    * Floor   = whichever brings (base + overlay) up to EFFECTIVE_TOTAL_FLOOR.
    * If both limits hit, ceiling wins (overlay capped at +20%).
    """
    base_rate = float(base_rate or 0.0)
    current_overlay = float(current_overlay or 0.0)
    proposed_delta = float(proposed_delta or 0.0)

    naive_new = current_overlay + proposed_delta

    # Ceiling check first — the absolute overlay cap.
    if naive_new > OVERLAY_CEILING:
        clamped = OVERLAY_CEILING
        return (clamped, clamped - current_overlay, "ceiling_hit")

    # Floor check — overlay can never push effective rate below 5%.
    min_overlay = EFFECTIVE_TOTAL_FLOOR - base_rate
    if naive_new < min_overlay:
        clamped = min_overlay
        return (clamped, clamped - current_overlay, "floor_hit")

    return (naive_new, proposed_delta, "")


# ─── DB helpers ──────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso_week_key(now: Optional[datetime] = None) -> str:
    """Return ISO week key in format YYYY-Www (e.g. '2026-W08'). EST
    timezone for the week boundary so a Monday-morning EST run lands in
    the same logical week regardless of the small UTC offset."""
    if now is None:
        now = datetime.now(timezone.utc)
    if ZoneInfo is not None:
        try:
            now = now.astimezone(ZoneInfo(LEADERBOARD_CRON_TZ))
        except Exception:  # noqa: BLE001
            pass
    year, week, _dow = now.isocalendar()
    return f"{year}-W{week:02d}"


async def _last_7d_volume_by_contractor(db) -> Dict[str, float]:
    """SUM(commission_amount) per contractor over the last 7 calendar
    days (regardless of accrued/paid status — both reflect "active
    work"). Cap returned dict to 500 contractors."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    pipeline = [
        {"$match": {"transaction_date": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$contractor_id",
            "total": {"$sum": "$commission_amount"},
        }},
    ]
    rows = await db.contractor_commission_ledger.aggregate(pipeline).to_list(length=500)
    return {r["_id"]: float(r["total"] or 0.0) for r in rows if r.get("_id")}


async def _all_active_contractor_ids(db) -> List[str]:
    """Return every dialer_contractor id (cap 500)."""
    rows = await db.users.find(
        {"role": "dialer_contractor"},
        {"_id": 0, "id": 1},
    ).limit(500).to_list(length=500)
    return [r["id"] for r in rows if r.get("id")]


def _previous_top_5(history_rows: List[Dict[str, Any]]) -> List[str]:
    """Read the most-recent persisted leaderboard batch and return the
    Top 5 contractor ids from that batch."""
    if not history_rows:
        return []
    return [r.get("contractor_id") for r in history_rows[:LEADERBOARD_TOP_N] if r.get("contractor_id")]


# ─── Cron entrypoint ─────────────────────────────────────────────────────

async def run_weekly_leaderboard_overlay(db) -> Dict[str, Any]:
    """Evaluate every contractor's last-7-day volume, rank, and adjust
    `users.leaderboard_overlay_rate` by ±1% based on Top 5 movement.
    Append a `leaderboard_history` entry on EVERY contractor regardless
    of whether their overlay changed (zero-delta rows still document the
    week).

    Idempotent per ISO-week — re-running in the same week returns the
    previously-persisted batch summary."""
    iso_week = _iso_week_key()

    # Idempotency guard.
    prev_batch = await db.leaderboard_overlay_batches.find_one({"iso_week": iso_week}, {"_id": 0})
    if prev_batch:
        logger.info(f"[leaderboard] week {iso_week} already processed — skipping.")
        return prev_batch

    batch_id = str(uuid.uuid4())
    now_iso = _now_iso()

    volume_by_cid = await _last_7d_volume_by_contractor(db)
    all_cids = await _all_active_contractor_ids(db)

    # Build (contractor_id, volume) for every active contractor (even zero).
    ranked: List[Tuple[str, float]] = sorted(
        ((cid, float(volume_by_cid.get(cid, 0.0))) for cid in all_cids),
        key=lambda x: (-x[1], x[0]),
    )

    current_top_5 = [cid for cid, _v in ranked[:LEADERBOARD_TOP_N]]

    # Read the most recent persisted batch to know who WAS in Top 5.
    prev_batch_doc = await db.leaderboard_overlay_batches.find(
        {}, {"_id": 0, "top_5_ids": 1, "ran_at": 1},
    ).sort("ran_at", -1).limit(1).to_list(length=1)
    prev_top_5 = (prev_batch_doc[0].get("top_5_ids") if prev_batch_doc else []) or []

    entered = [cid for cid in current_top_5 if cid not in prev_top_5]
    dropped = [cid for cid in prev_top_5 if cid not in current_top_5]

    adjustments: List[Dict[str, Any]] = []

    for rank_idx, (cid, volume) in enumerate(ranked):
        proposed_delta = 0.0
        movement = "no_change"
        if cid in entered:
            proposed_delta = OVERLAY_DELTA
            movement = "entered_top_5"
        elif cid in dropped:
            proposed_delta = -OVERLAY_DELTA
            movement = "dropped_top_5"

        # Read contractor's current state.
        cur = await db.users.find_one(
            {"id": cid},
            {"_id": 0, "id": 1, "leaderboard_overlay_rate": 1,
             "commission_default_rate": 1},
        )
        current_overlay = float((cur or {}).get("leaderboard_overlay_rate") or 0.0)

        # Resolve base rate from the contractor's commission-rate config
        # (falls back to global default if unset).
        base_rate = await _get_base_rate_for_contractor(db, cid)

        clamped_overlay, applied_delta, clamp_reason = clamp_leaderboard_overlay(
            base_rate=base_rate,
            current_overlay=current_overlay,
            proposed_delta=proposed_delta,
        )

        history_entry = {
            "id":               str(uuid.uuid4()),
            "batch_id":         batch_id,
            "iso_week":         iso_week,
            "ran_at":           now_iso,
            "rank":             rank_idx + 1,
            "in_top_5":         cid in current_top_5,
            "weekly_volume":    round(volume, 2),
            "movement":         movement,
            "proposed_delta":   round(proposed_delta, 4),
            "applied_delta":    round(applied_delta, 4),
            "clamp_reason":     clamp_reason,
            "base_rate":        round(base_rate, 4),
            "previous_overlay": round(current_overlay, 4),
            "new_overlay":      round(clamped_overlay, 4),
            "effective_total":  round(base_rate + clamped_overlay, 4),
        }

        # Persist on user doc — overlay value + append to history array.
        await db.users.update_one(
            {"id": cid},
            {"$set": {
                "leaderboard_overlay_rate":         round(clamped_overlay, 4),
                "leaderboard_overlay_updated_at":   now_iso,
            },
             "$push": {"leaderboard_history": history_entry}},
        )

        adjustments.append({
            "contractor_id":    cid,
            "rank":             rank_idx + 1,
            "movement":         movement,
            "applied_delta":    round(applied_delta, 4),
            "new_overlay":      round(clamped_overlay, 4),
            "clamp_reason":     clamp_reason,
        })

    summary = {
        "batch_id":             batch_id,
        "iso_week":             iso_week,
        "ran_at":               now_iso,
        "contractors_evaluated": len(ranked),
        "top_5_ids":            current_top_5,
        "previous_top_5_ids":   prev_top_5,
        "entered_top_5":        entered,
        "dropped_top_5":        dropped,
        "adjustments":          adjustments,
    }
    await db.leaderboard_overlay_batches.insert_one(summary)
    logger.info(
        f"[leaderboard] week {iso_week} processed: "
        f"{len(ranked)} contractors, top5={current_top_5}, "
        f"entered={entered}, dropped={dropped}"
    )
    # Strip Mongo _id before returning.
    summary.pop("_id", None)
    return summary


async def _get_base_rate_for_contractor(db, contractor_id: str) -> float:
    """Pick the 'reference' base rate used for the FLOOR check. We use
    the contractor's `default_rate` (the rate applied when no specific
    account-type override exists) as the canonical base. Falls back to
    0.20 (DEFAULT_COMMISSION_RATE) when unconfigured."""
    cfg = await db.contractor_commission_rates.find_one(
        {"contractor_id": contractor_id}, {"_id": 0, "default_rate": 1},
    )
    if cfg and cfg.get("default_rate") is not None:
        return float(cfg["default_rate"])
    return 0.20


__all__ = [
    "LEADERBOARD_TOP_N",
    "OVERLAY_DELTA",
    "EFFECTIVE_TOTAL_FLOOR",
    "OVERLAY_CEILING",
    "LEADERBOARD_CRON_TZ",
    "LEADERBOARD_CRON_HOUR",
    "LEADERBOARD_CRON_DAY_OF_WEEK",
    "clamp_leaderboard_overlay",
    "run_weekly_leaderboard_overlay",
]
