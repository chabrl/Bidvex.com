"""
iter377 — Bid notification email coverage test.

Purpose: prove that outbid AND bid-placed emails fire on ALL four bid paths
by asserting the `send_outbid_email` / `send_bid_placed_email` helpers are
imported and invoked in each route.

This is a static check (no live SendGrid dispatch) — the actual send is
already covered by iter239 email unit tests. What we're guarding against
is regressions where the wiring goes missing (as it did on the multi-lot
listing and vehicle-multi-lot paths pre-iter377).
"""

import re
from pathlib import Path

ROUTES_DIR = Path("/app/backend/routes")


def _read(path: str) -> str:
    return (ROUTES_DIR / path).read_text(encoding="utf-8")


def _count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text))


# ─── (1) Single marketplace / vehicle listings ────────────────────────

def test_single_listing_bid_path_fires_outbid_and_bid_placed_emails():
    src = _read("auctions_bids.py")
    # Outbid path — must import and call send_outbid_email
    assert "from services.emails.email_marketplace import send_outbid_email" in src
    assert _count(r"await send_outbid_email\(", src) >= 2, (
        "Expected outbid email on both normal + auto-bid exhaustion paths"
    )
    # Bid-placed path — must import and call send_bid_placed_email
    assert "from services.emails.email_marketplace import send_bid_placed_email" in src
    assert _count(r"await send_bid_placed_email\(", src) >= 2, (
        "Expected send_bid_placed_email on single-item + multi-lot bid paths "
        "(regression guard: iter377 added the multi-lot call)"
    )


# ─── (2) Multi-lot listing bids ───────────────────────────────────────

def test_multi_lot_listing_bid_fires_outbid_and_bid_placed_emails():
    """iter377 regression: multi-lot listing bids never sent outbid or
    bid-placed emails — only SMS + in-app notif. Guard both were added."""
    src = _read("auctions_bids.py")
    # The multi-lot endpoint lives after the sentinel comment
    marker = "# ========== OUTBID NOTIFICATION =========="
    assert marker in src, "Marker for multi-lot outbid block missing"
    _after_marker = src.split(marker, 1)[1]
    assert "send_outbid_email" in _after_marker, (
        "Multi-lot outbid email wiring missing (iter377 regression guard)"
    )
    assert "Multi-lot outbid email failed" in _after_marker, (
        "iter377 outbid try/except comment missing"
    )
    assert "send_bid_placed_email" in _after_marker, (
        "Multi-lot bid-placed email wiring missing (iter377 regression guard)"
    )
    assert "Multi-lot bid-placed email failed" in _after_marker, (
        "iter377 bid-placed try/except comment missing"
    )


# ─── (3) Vehicle multi-lot bids ──────────────────────────────────────

def test_vehicle_multi_lot_bid_fires_outbid_and_bid_placed_emails():
    src = _read("vehicle_multi_lot.py")
    # Outbid was already there
    assert "send_outbid_email" in src, "Vehicle multi-lot outbid missing"
    # iter377 added the bid-placed
    assert "send_bid_placed_email" in src, (
        "Vehicle multi-lot bid-placed email wiring missing (iter377 regression guard)"
    )
    assert "vehicle multi-lot bid-placed email failed" in src, (
        "iter377 bid-placed try/except comment missing"
    )


# ─── (4) Storage facility bids ───────────────────────────────────────

def test_storage_bid_fires_outbid_and_bid_placed_emails():
    src = _read("storage_auctions.py")
    assert "send_storage_bid_placed_email" in src, (
        "Storage bid-placed email wiring missing"
    )
    assert "send_storage_outbid_email" in src, (
        "Storage outbid email wiring missing"
    )
    # Both must be added to background_tasks so response stays snappy
    assert "background_tasks.add_task(send_storage_bid_placed_email" in src
    assert "background_tasks.add_task(send_storage_outbid_email" in src


# ─── (5) Scheduler: unawaited-coroutine bug fixed ────────────────────

def test_server_schedulers_use_async_wrappers_not_sync_lambdas():
    """iter377 — `lambda: safe_run(...)` on an AsyncIOScheduler returns
    a coroutine the executor never awaits (RuntimeWarning + job silently
    never runs). Ensure NO scheduler entry uses that anti-pattern anymore."""
    src = Path("/app/backend/server.py").read_text(encoding="utf-8")
    # Only allow the doc comment mention; no actual scheduler.add_job wiring
    lines = src.splitlines()
    bad = []
    for i, ln in enumerate(lines):
        if "lambda: safe_run" in ln:
            # Skip if inside a docstring/comment
            stripped = ln.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'"):
                continue
            # If the previous non-blank line is a `scheduler.add_job(`, it's the bug.
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            if j >= 0 and "scheduler.add_job" in lines[j]:
                bad.append((i + 1, ln.rstrip()))
    assert not bad, f"Found broken `lambda: safe_run(...)` scheduler entries: {bad}"

    # And the six specific fixes must have async wrappers
    for wrapper in (
        "_watchlist_expiry_alerts_tick",
        "_watchlist_1h_nudge_tick",
        "_bill96_autosuspend_tick",
        "_sitemap_regen_tick",
        "_promotion_expiry_sweep_tick",
        "_fb_feed_cache_warm_scheduler_tick",
    ):
        assert f"async def {wrapper}" in src, f"Missing async wrapper `{wrapper}`"
        assert f"scheduler.add_job(\n    {wrapper}," in src or f"scheduler.add_job({wrapper}," in src, (
            f"Wrapper `{wrapper}` not registered with scheduler.add_job"
        )
