"""
repair_alex_boulanger_win_email.py — iter299 production hotfix utility
=======================================================================

WHAT THIS DOES
--------------
Alex Boulanger won an auction in production but may never have received
the "You Won!" email (SendGrid logs inconclusive). This script:

  1. Locates the user (by --email, or by name regex "alex.*boulanger").
  2. Finds every auction they WON across all listing collections
     (`listings`, `multi_item_listings`, `vehicle_listings`,
     `storage_auctions`) — matching `winner_user_id` / `winner_id` /
     `winning_bidder_id` with status sold/ended/completed.
  3. DRY-RUN (default): prints exactly what it found and what it WOULD
     send. No emails, no DB writes.
  4. --execute: re-sends the bilingual "You Won!" email via the same
     `send_auction_won_email` used by the live close flow, and creates
     the bilingual `auction_won` bell notification if it is missing.

HOW TO RUN SAFELY (on the production deployment)
------------------------------------------------
  cd /app/backend

  # Step 1 — ALWAYS dry-run first. Review the output.
  python scripts/repair_alex_boulanger_win_email.py

  # If the default name search finds the wrong/no user, target by email:
  python scripts/repair_alex_boulanger_win_email.py --email alex@example.com

  # Step 2 — only after reviewing the dry-run output, actually send:
  python scripts/repair_alex_boulanger_win_email.py --email alex@example.com --execute

  # Optional: repair only one specific listing
  python scripts/repair_alex_boulanger_win_email.py --email alex@example.com \
      --listing-id <listing_uuid> --execute

NOTES
-----
- Idempotency: the script tags repaired listings with
  `win_email_repaired_at` and skips already-tagged ones unless --force.
- Requires backend/.env (MONGO_URL, DB_NAME, SENDGRID_API_KEY) — it uses
  the production env when run inside the deployed backend container.
"""
import argparse
import asyncio
import os
import re
import sys
from datetime import datetime, timezone

# Run from /app/backend so `services.*` imports resolve.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

_WON_STATUSES = ["sold", "ended", "completed"]
_COLLECTIONS = ["listings", "multi_item_listings", "vehicle_listings", "storage_auctions"]
_WINNER_FIELDS = ["winner_user_id", "winner_id", "winning_bidder_id"]


def _hammer(doc) -> float:
    return float(doc.get("final_price") or doc.get("current_price") or doc.get("current_bid") or 0)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Re-send the win email to Alex Boulanger (or any winner).")
    parser.add_argument("--email", help="Exact user email (overrides the name search).")
    parser.add_argument("--listing-id", help="Repair only this listing id.")
    parser.add_argument("--execute", action="store_true",
                        help="Actually send the email + create the notification. Default is DRY-RUN.")
    parser.add_argument("--force", action="store_true",
                        help="Re-send even if `win_email_repaired_at` is already set.")
    args = parser.parse_args()

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    # ── 1. Locate the user ──
    if args.email:
        user = await db.users.find_one({"email": args.email.strip().lower()}, {"_id": 0})
        if not user:
            user = await db.users.find_one(
                {"email": re.compile(f"^{re.escape(args.email.strip())}$", re.I)}, {"_id": 0})
    else:
        user = await db.users.find_one(
            {"name": re.compile(r"alex.*boulanger", re.I)}, {"_id": 0})

    if not user:
        print("❌ User not found. Use --email <their-exact-email> and retry.")
        return 1

    print(f"👤 User: {user.get('name')} <{user.get('email')}> (id={user.get('id')})")

    # ── 2. Find their won auctions ──
    winner_query = {"$or": [{f: user["id"]} for f in _WINNER_FIELDS],
                    "status": {"$in": _WON_STATUSES}}
    if args.listing_id:
        winner_query["id"] = args.listing_id

    found = []
    for coll in _COLLECTIONS:
        docs = await db[coll].find(winner_query, {"_id": 0}).to_list(100)
        for d in docs:
            found.append((coll, d))

    if not found:
        print("❌ No won auctions found for this user. Nothing to repair.")
        return 1

    print(f"\n🏆 Found {len(found)} won auction(s):")
    for coll, d in found:
        repaired = d.get("win_email_repaired_at")
        print(f"  • [{coll}] {d.get('title', d.get('id'))} — "
              f"hammer ${_hammer(d):,.2f} — status={d.get('status')}"
              f"{' — ALREADY REPAIRED ' + str(repaired) if repaired else ''}")

    if not args.execute:
        print("\nℹ️  DRY-RUN complete. Re-run with --execute to send the email(s).")
        return 0

    # ── 3. Send the win email + ensure the bell notification ──
    from services.emails.email_marketplace import send_auction_won_email
    from services.notifications_i18n import create_notification

    sent = 0
    for coll, d in found:
        if d.get("win_email_repaired_at") and not args.force:
            print(f"  ⏭️  Skipping '{d.get('title')}' (already repaired; use --force to override).")
            continue
        is_vehicle = coll == "vehicle_listings"
        final_price = _hammer(d)
        try:
            await send_auction_won_email(
                to_email=user["email"],
                to_name=user.get("name", "Winner"),
                item_name=d.get("title", "Item"),
                auction_id=d.get("id", ""),
                hammer_price=final_price,
                platform_fee=0.0,
                is_vehicle=is_vehicle,
            )
            print(f"  ✅ Win email re-sent for '{d.get('title')}' → {user['email']}")
            sent += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ❌ Email send FAILED for '{d.get('title')}': {e}")
            continue

        # Bell notification (only if one doesn't exist for this listing)
        existing = await db.notifications.find_one({
            "user_id": user["id"], "type": "auction_won",
            "$or": [{"data.listing_id": d.get("id")}, {"listing_id": d.get("id")}],
        })
        if not existing:
            try:
                await create_notification(
                    db, user_id=user["id"], kind="auction_won",
                    params={"title": d.get("title", "Item"), "amount": final_price,
                            "listing_id": d.get("id")},
                    data={"listing_id": d.get("id")},
                )
                print("     🔔 auction_won notification created.")
            except Exception as e:  # noqa: BLE001
                print(f"     ⚠️ notification create failed (email still sent): {e}")

        await db[coll].update_one(
            {"id": d.get("id")},
            {"$set": {"win_email_repaired_at": datetime.now(timezone.utc).isoformat()}})

    print(f"\n🎉 Done — {sent} email(s) sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
