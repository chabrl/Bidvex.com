"""P0 Email QA Test — sends test emails for all 5 P0 templates EN+FR."""
import asyncio
import sys
import os
sys.path.insert(0, "/app/backend")

# Ensure env is loaded
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from services.email_service import (
    send_pickup_code_email,
    send_escrow_released_email,
    send_cancellation_penalty_email,
    send_auto_release_email,
    send_sticky_card_locked_email,
)

# Use the admin's email for testing (real deliverable)
TEST_EMAIL = "charbel911@gmail.com"

TEST_USER_EN = {
    "email": TEST_EMAIL,
    "full_name": "QA Tester EN",
    "first_name": "QA",
    "name": "QA Tester EN",
    "language_preference": "en",
}

TEST_USER_FR = {
    "email": TEST_EMAIL,
    "full_name": "Testeur AQ FR",
    "first_name": "Testeur",
    "name": "Testeur AQ FR",
    "language_preference": "fr",
}


async def run_qa():
    results = []

    # 1. Pickup Code — EN + FR
    for user in [TEST_USER_EN, TEST_USER_FR]:
        result = await send_pickup_code_email(
            buyer=user,
            seller={"full_name": "Test Seller", "name": "Test Seller", "email": "seller@test.com"},
            pickup_code="BVX7K2",
            auction_id="TEST-001",
            expires_at="April 20, 2026 at 02:00 PM UTC",
        )
        results.append(("pickup_code", user["language_preference"], result))

    # 2. Escrow Released — EN + FR
    for user in [TEST_USER_EN, TEST_USER_FR]:
        result = await send_escrow_released_email(
            seller=user,
            buyer={"full_name": "Test Buyer", "name": "Test Buyer"},
            escrow={
                "auction_id": "TEST-001",
                "total_charged_cents": 5488,
                "application_fee_cents": 488,
                "stripe_transfer_id": "tr_test_123",
            },
        )
        results.append(("escrow_released", user["language_preference"], result))

    # 3. Cancellation Penalty — EN + FR
    for user in [TEST_USER_EN, TEST_USER_FR]:
        result = await send_cancellation_penalty_email(
            seller=user,
            listing_id="LIST-001",
            penalty_amount="$50.00 CAD",
            reason="Seller reported unable to deliver after auction close.",
        )
        results.append(("cancellation_penalty", user["language_preference"], result))

    # 4. Auto-Release — EN + FR
    for user in [TEST_USER_EN, TEST_USER_FR]:
        result = await send_auto_release_email(
            buyer=user,
            seller={"full_name": "Test Seller", "name": "Test Seller"},
            escrow={
                "auction_id": "TEST-001",
                "total_charged_cents": 5488,
                "application_fee_cents": 488,
            },
        )
        results.append(("auto_release", user["language_preference"], result))

    # 5. Sticky Card Locked — EN + FR
    for user in [TEST_USER_EN, TEST_USER_FR]:
        result = await send_sticky_card_locked_email(
            seller=user,
            active_listing_count=3,
        )
        results.append(("sticky_card_locked", user["language_preference"], result))

    # Print results
    print("\n── EMAIL QA RESULTS ──────────────────────")
    all_passed = True
    for name, lang, result in results:
        status = "PASS" if result else "FAIL"
        if not result:
            all_passed = False
        print(f"{'✅' if result else '❌'} {status} | {name} [{lang.upper()}]")

    print("─────────────────────────────────────────")
    print(f"{'✅ ALL PASSED' if all_passed else '❌ FAILURES FOUND'}")
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_qa())
    sys.exit(0 if success else 1)
