"""BidVex Email Integration — Live E2E Test"""
import asyncio
import sys
import os
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from services.email_service import send_template_email, resolve_template
from services.admin_notifications import notify_admin_new_user

TEST_EMAIL = "charbel911@gmail.com"

async def run_live_test():
    results = {}
    print("\n" + "=" * 60)
    print("BidVex Email Integration — Live Test")
    print(f"Sending to: {TEST_EMAIL}")
    print("=" * 60 + "\n")

    # Test 1 — Welcome email EN
    print("TEST 1: Welcome email (EN template)...")
    tid = resolve_template("welcome", "en")
    print(f"  Template ID: {tid}")
    r = await send_template_email(
        to_email=TEST_EMAIL, to_name="Charbel Test EN", template_id=tid,
        dynamic_data={"first_name": "Charbel", "dashboard_url": "https://www.bidvex.com/dashboard",
                      "marketplace_url": "https://www.bidvex.com/marketplace", "support_url": "https://www.bidvex.com/support"}
    )
    results["welcome_en"] = r
    print(f"  {'PASS' if r else 'FAIL'}\n")

    # Test 2 — Welcome email FR
    print("TEST 2: Welcome email (FR template)...")
    tid = resolve_template("welcome", "fr")
    print(f"  Template ID: {tid}")
    r = await send_template_email(
        to_email=TEST_EMAIL, to_name="Charbel Test FR", template_id=tid,
        dynamic_data={"first_name": "Charbel", "dashboard_url": "https://www.bidvex.com/dashboard",
                      "marketplace_url": "https://www.bidvex.com/marketplace", "support_url": "https://www.bidvex.com/support"}
    )
    results["welcome_fr"] = r
    print(f"  {'PASS' if r else 'FAIL'}\n")

    # Test 3 — Admin notification
    print("TEST 3: Admin notification (raw HTML to info@bidvex.com)...")
    r = await notify_admin_new_user({"email": TEST_EMAIL, "full_name": "Charbel Test", "language_preference": "en"})
    results["admin_notify"] = r
    print(f"  {'PASS' if r else 'FAIL'}\n")

    # Test 4 — Bid confirmed
    print("TEST 4: Bid confirmed email...")
    tid = resolve_template("bid_confirmed", "en")
    print(f"  Template ID: {tid}")
    r = await send_template_email(
        to_email=TEST_EMAIL, to_name="Charbel Test", template_id=tid,
        dynamic_data={"first_name": "Charbel", "auction_id": "TEST-001", "item_name": "Industrial Table",
                      "bid_amount": "$125.00", "current_highest_bid": "$125.00",
                      "auction_end_time": "2026-04-25 18:00 UTC", "auction_url": "https://www.bidvex.com/auctions/TEST-001"}
    )
    results["bid_confirmed"] = r
    print(f"  {'PASS' if r else 'FAIL'}\n")

    # Test 5 — Pickup Code
    print("TEST 5: Pickup code email...")
    tid = resolve_template("pickup_code", "en")
    print(f"  Template ID: {tid}")
    r = await send_template_email(
        to_email=TEST_EMAIL, to_name="Charbel Test", template_id=tid,
        dynamic_data={"first_name": "Charbel", "pickup_code": "BVX7K2", "auction_id": "TEST-002",
                      "seller_name": "Test Seller", "expires_at": "April 25, 2026 2:00 PM UTC",
                      "dashboard_url": "https://www.bidvex.com/dashboard"}
    )
    results["pickup_code"] = r
    print(f"  {'PASS' if r else 'FAIL'}\n")

    # Summary
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    for name, result in results.items():
        print(f"  {'PASS' if result else 'FAIL'} — {name}")
    print(f"\nResult: {passed}/{len(results)} passed")
    print("=" * 60)

asyncio.run(run_live_test())
