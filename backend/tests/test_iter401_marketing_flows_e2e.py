"""iter401 — End-to-end verification of the 5 marketing-flow triggers.

Runs against the live preview backend/DB with `send_email` monkey-patched
to a no-op counter so we verify the dispatch DECISION logic without
touching SendGrid.

Test matrix:
  Flow 1  — Buyer Interest (real-time)      × 1 scenario
  Flow 2A — Seller draft ≥24h                × 1
  Flow 2B — Seller auction starting 90–150m  × 1
  Flow 2C — Seller unapproved winners ≥24h   × 1
  Flow 1  — Rate limit (1/user/hour)          × 1
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

# Bootstrap env from backend/.env
env = open("/app/backend/.env").read()
for line in env.strip().split("\n"):
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        os.environ.setdefault(k, v.strip())

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


# ─── Monkey-patch send_email to capture calls ─────────────────────
_captured: list = []


async def _fake_send_email(**kwargs):
    _captured.append({
        "to": kwargs.get("to_email"),
        "subject": kwargs.get("subject"),
        "categories": kwargs.get("categories"),
    })
    return {"status": "sent", "to": kwargs.get("to_email")}


import services.emails._email_core as _core  # noqa: E402
_core.send_email = _fake_send_email
# The marketing_flows module imports send_email at call-time via
# `from services.emails._email_core import send_email` inside the wrapper
# helper, so re-patching the module attribute is sufficient.


# ─── Test data helpers ────────────────────────────────────────────
class Ctx:
    seller_id      = f"iter401-seller-{uuid.uuid4().hex[:6]}"
    follower_id    = f"iter401-follower-{uuid.uuid4().hex[:6]}"
    category_id    = f"iter401-cat-{uuid.uuid4().hex[:6]}"
    ineligible_id  = f"iter401-inel-{uuid.uuid4().hex[:6]}"
    listing_id     = f"iter401-listing-{uuid.uuid4().hex[:6]}"
    draft_id       = f"iter401-draft-{uuid.uuid4().hex[:6]}"
    starting_id    = f"iter401-start-{uuid.uuid4().hex[:6]}"
    ended_id       = f"iter401-ended-{uuid.uuid4().hex[:6]}"

CATEGORY = "Test iter401 Widgets"


async def seed(db):
    """Create the fixture users + a historical listing/bid so category
    match works. Cleanup happens in the finally block."""
    users = [
        {"id": Ctx.seller_id,     "email": "iter401-seller@bidvex-qa.com",     "name": "Iter401 Seller"},
        {"id": Ctx.follower_id,   "email": "iter401-follower@bidvex-qa.com",   "name": "Iter401 Follower", "preferred_language": "en"},
        {"id": Ctx.category_id,   "email": "iter401-catbidder@bidvex-qa.com",  "name": "Iter401 Cat Bidder", "preferred_language": "fr"},
        {"id": Ctx.ineligible_id, "email": "iter401-ineligible@bidvex-qa.com", "name": "Iter401 Ineligible"},
    ]
    for u in users:
        await db.users.insert_one({**u, "created_at": datetime.now(timezone.utc).isoformat()})

    # Follower follows seller.
    await db.seller_follows.insert_one({
        "id": f"sf-{uuid.uuid4().hex[:6]}",
        "follower_id": Ctx.follower_id,
        "seller_id":   Ctx.seller_id,
        "created_at":  datetime.now(timezone.utc).isoformat(),
    })

    # Historical listing in the target category (for category-match logic).
    hist_lid = f"iter401-hist-{uuid.uuid4().hex[:6]}"
    await db.multi_item_listings.insert_one({
        "id": hist_lid,
        "seller_id": f"other-seller-{uuid.uuid4().hex[:6]}",
        "title": "Historical iter401 listing",
        "category": CATEGORY,
        "status": "ended",
        "created_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        "lots": [{"lot_number": 1, "starting_price": 10.0}],
    })

    # bidder Ctx.category_id has 1 bid on that historical listing (proves ≥1 bid + same category).
    await db.bids.insert_one({
        "id": f"bid-hist-{uuid.uuid4().hex[:6]}",
        "listing_id": hist_lid,
        "bidder_id":  Ctx.category_id,
        "amount":     15.0,
        "status":     "approved",
        "created_at": (datetime.now(timezone.utc) - timedelta(days=25)).isoformat(),
    })
    # follower_id also has ≥1 bid (required by the eligibility rule).
    await db.bids.insert_one({
        "id": f"bid-follower-{uuid.uuid4().hex[:6]}",
        "listing_id": hist_lid,
        "bidder_id":  Ctx.follower_id,
        "amount":     11.0,
        "status":     "approved",
        "created_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
    })
    # ineligible has NEVER placed a bid — so should be excluded even if
    # they somehow matched category or seller (they don't, but this is
    # extra proof).
    return hist_lid


async def cleanup(db):
    for col in ("users", "seller_follows", "bids", "multi_item_listings",
                "buyer_interest_email_log", "vehicle_listings", "storage_auctions"):
        await db[col].delete_many({"id": {"$regex": "^iter401-"}})
        await db[col].delete_many({"bidder_id": {"$regex": "^iter401-"}})
    # Also clean any test seller_id references
    await db.multi_item_listings.delete_many({"seller_id": {"$regex": "^iter401-"}})
    await db.bids.delete_many({"listing_id": {"$regex": "^iter401-"}})


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    from services.marketing_flows import (
        dispatch_buyer_interest_emails,
        run_seller_draft_reminders,
        run_seller_auction_starting_reminders,
        run_seller_winner_approval_reminders,
        BUYER_INTEREST_RATE_LIMIT_HOURS,
    )
    print(f"Rate limit configured: {BUYER_INTEREST_RATE_LIMIT_HOURS}h/user")

    await cleanup(db)  # start fresh

    try:
        await seed(db)

        # ─── Scenario 1: Flow 1 — Buyer Interest (real-time) ─────
        print("\n=== Scenario 1: Flow 1 Buyer Interest ===")
        listing = {
            "id": Ctx.listing_id,
            "seller_id": Ctx.seller_id,
            "title": "iter401 Auction (Widgets)",
            "category": CATEGORY,
            "status": "active",
            "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "lots": [{"lot_number": 1, "starting_price": 20.0, "lot_end_time": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()}],
            "currency": "CAD",
        }
        await db.multi_item_listings.insert_one(listing)

        _captured.clear()
        counts = await dispatch_buyer_interest_emails(db, listing_id=Ctx.listing_id, listing_type="multi_item")
        print("  counts:", counts)
        print("  emails captured:", len(_captured))
        for c in _captured:
            print("    ->", c["to"], "|", c["subject"])
        recipients = {c["to"] for c in _captured}
        assert "iter401-follower@bidvex-qa.com" in recipients, "FAIL: follower should receive"
        assert "iter401-catbidder@bidvex-qa.com" in recipients, "FAIL: category match should receive"
        assert "iter401-ineligible@bidvex-qa.com" not in recipients, "FAIL: ineligible should NOT receive"
        assert "iter401-seller@bidvex-qa.com" not in recipients, "FAIL: seller should NOT receive"
        # French subject for FR-preferring user
        cat_email = next(c for c in _captured if c["to"] == "iter401-catbidder@bidvex-qa.com")
        assert "Nouvelle" in cat_email["subject"], f"FAIL: FR subject expected, got {cat_email['subject']}"
        assert cat_email["categories"] == ["buyer_interest"]
        print("  ✅ PASS — follower + category bidder received; ineligible + seller excluded; FR user got FR subject")

        # ─── Scenario 5: Rate limit — second dispatch within 1h ──
        print("\n=== Scenario 5: Rate-limit (1/user/hour) ===")
        # Create a second live listing right away — same eligibility pool.
        listing2 = {k: v for k, v in listing.items() if k != "_id"}
        listing2["id"] = Ctx.listing_id + "-2"
        listing2["title"] = "iter401 Second live"
        await db.multi_item_listings.insert_one(listing2)
        _captured.clear()
        counts2 = await dispatch_buyer_interest_emails(db, listing_id=listing2["id"], listing_type="multi_item")
        print("  counts:", counts2)
        print("  emails captured:", len(_captured))
        assert counts2["sent"] == 0, f"FAIL: expected 0 sends (rate limited), got {counts2['sent']}"
        assert counts2["rate_limited"] >= 2, f"FAIL: expected ≥2 rate_limited, got {counts2['rate_limited']}"
        print("  ✅ PASS — no re-sends within the 1-hour window")

        # ─── Scenario 2A: Draft ≥24h ─────────────────────────────
        print("\n=== Scenario 2A: Seller draft ≥24h ===")
        old = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        await db.multi_item_listings.insert_one({
            "id": Ctx.draft_id,
            "seller_id": Ctx.seller_id,
            "title": "iter401 Unfinished draft",
            "category": CATEGORY,
            "status": "draft",
            "created_at": old,
            "lots": [{"lot_number": 1, "starting_price": 5.0}],
        })
        _captured.clear()
        c_draft = await run_seller_draft_reminders(db)
        print("  counts:", c_draft)
        print("  emails captured:", len(_captured))
        recipients_draft = {c["to"] for c in _captured}
        assert "iter401-seller@bidvex-qa.com" in recipients_draft, "FAIL: seller should get draft reminder"
        assert any("Finish" in c["subject"] or "publish" in c["subject"] for c in _captured), "FAIL: unexpected subject"
        # Idempotency
        _captured.clear()
        c_draft2 = await run_seller_draft_reminders(db)
        assert c_draft2["sent"] == 0, f"FAIL: second run should be idempotent, got sent={c_draft2['sent']}"
        print("  ✅ PASS — draft ≥24h emailed the seller; second run idempotent")

        # ─── Scenario 2B: Auction starting in 90–150 min ─────────
        print("\n=== Scenario 2B: Seller auction starting ~2h ===")
        soon = (datetime.now(timezone.utc) + timedelta(minutes=120)).isoformat()
        await db.multi_item_listings.insert_one({
            "id": Ctx.starting_id,
            "seller_id": Ctx.seller_id,
            "title": "iter401 Live auction starts soon",
            "category": CATEGORY,
            "status": "scheduled",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "auction_start_date": soon,
            "lots": [{"lot_number": 1, "starting_price": 40.0}],
        })
        _captured.clear()
        c_start = await run_seller_auction_starting_reminders(db)
        print("  counts:", c_start)
        recipients_start = {c["to"] for c in _captured}
        assert "iter401-seller@bidvex-qa.com" in recipients_start, "FAIL: seller should get starting reminder"
        assert any("starts" in c["subject"].lower() or "commence" in c["subject"].lower() for c in _captured)
        # Idempotency
        _captured.clear()
        c_start2 = await run_seller_auction_starting_reminders(db)
        assert c_start2["sent"] == 0, f"FAIL: second run should be idempotent, got sent={c_start2['sent']}"
        print("  ✅ PASS — starting-soon reminder sent; idempotent on re-run")

        # ─── Scenario 2C: Ended ≥24h w/ unapproved winners ───────
        print("\n=== Scenario 2C: Seller winner-approval ≥24h ===")
        ended_dt = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        await db.multi_item_listings.insert_one({
            "id": Ctx.ended_id,
            "seller_id": Ctx.seller_id,
            "title": "iter401 Ended awaiting approval",
            "category": CATEGORY,
            "status": "ended",
            "created_at": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
            "auction_end_date": ended_dt,
            "lots": [{"lot_number": 1, "starting_price": 10.0, "lot_status": "ended"}],
        })
        # Winning bid on the ended lot, NOT approved.
        await db.bids.insert_one({
            "id": f"bid-winner-{uuid.uuid4().hex[:6]}",
            "listing_id": Ctx.ended_id,
            "lot_number": 1,
            "bidder_id":  Ctx.follower_id,
            "amount":     100.0,
            "status":     "pending",
            "created_at": ended_dt,
        })
        _captured.clear()
        c_win = await run_seller_winner_approval_reminders(db)
        print("  counts:", c_win)
        recipients_win = {c["to"] for c in _captured}
        assert "iter401-seller@bidvex-qa.com" in recipients_win, "FAIL: seller should get winner reminder"
        assert any("approve" in c["subject"].lower() or "approuver" in c["subject"].lower() for c in _captured)
        # Idempotency
        _captured.clear()
        c_win2 = await run_seller_winner_approval_reminders(db)
        assert c_win2["sent"] == 0, f"FAIL: second run should be idempotent, got sent={c_win2['sent']}"
        print("  ✅ PASS — winner-approval reminder sent; idempotent on re-run")

        print("\n" + "="*60)
        print("🎉 ALL 5 SCENARIOS PASSED (Flow1, Flow1 rate-limit, Flow2A, 2B, 2C)")
        print("="*60)
    finally:
        await cleanup(db)


if __name__ == "__main__":
    asyncio.run(main())
