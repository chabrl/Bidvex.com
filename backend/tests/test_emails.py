"""
BidVex — Full SendGrid Template Validation
Fires one real API call per template ID (EN + FR) and logs the status.
Any HTTP 400 (Invalid Template ID) is flagged immediately.

Run: cd /app/backend && set -a && source .env && set +a && python tests/test_emails.py
"""

import os
import sys
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To

API_KEY = os.environ.get("SENDGRID_API_KEY")
FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "office@bidvex.com")
FROM_NAME = os.environ.get("SENDGRID_FROM_NAME", "BidVex")
TEST_RECIPIENT = FROM_EMAIL  # safe: send to ourselves

# ── Complete template registry (matches DEFAULT_EMAIL_TEMPLATES + 2 new) ──
TEMPLATES = {
    # Authentication
    "auth_password_reset_en":          "d-dbfba723dd5e4895a579b462b19c56fb",
    "auth_password_reset_fr":          "d-9084b4478e024056a9fa5207fdfc91e6",
    "auth_password_changed_en":        "d-1e018cb66df54ee58616f9abd0720b0f",
    "auth_password_changed_fr":        "d-16ad9371e1c54f2996f4ff453dfc2b82",
    "auth_email_verification_en":      "d-79352dd5a50849c7bb4cbe93e726051f",
    "auth_email_verification_fr":      "d-48d6d49961ab439f89d55b890bc84b8a",
    "auth_welcome_en":                 "d-db7d296ad54247138f3f210a1fb52e0a",
    "auth_welcome_fr":                 "d-256f3801670441808730c4cfb259d9a2",
    "auth_two_factor_en":              "d-7fe6f17a934f491ca91aa36534be85e2",
    "auth_two_factor_fr":              "d-ec1e531f92bc4d01bf24dc47620cabed",
    "auth_login_alert_en":             "d-2cbb18036b9e44e4ba67ac3ee614e339",
    "auth_login_alert_fr":             "d-2e3509d0a8c3480e83cd0d6b6ffc8c25",
    # Admin
    "admin_account_suspended_en":      "d-cf2d8fb5bad74d4ab00b85236a93755d",
    "admin_account_suspended_fr":      "d-89596fbe221f4740aa29cff3d09d6754",
    "admin_report_received_en":        "d-539a4d89254f42baa38de4f139e7a36b",
    "admin_report_received_fr":        "d-1e6b72f9301c49949b9a5cb21f0a39d5",
    # Communication
    "comm_announcement_en":            "d-877f77c6623b4ed3879e4a7fcab2f8a5",
    "comm_announcement_fr":            "d-b1fd6b2e096d47bb95c96fc9ca93af68",
    "comm_support_ack_en":             "d-5a4bdee8c66041ba8d44ba0d7fc0244a",
    "comm_support_ack_fr":             "d-7ecc0e3ab5c24c8283416a0e1ef4c9eb",
    "comm_platform_updates_en":        "d-268de17d00514f3bb674e688d414b157",
    "comm_platform_updates_fr":        "d-3dc15879450146dd9e1d48e59dc8cccc",
    # Financial
    "fin_invoice_issued_en":           "d-d25445886edb4cc08cc8107b07cb343f",
    "fin_invoice_issued_fr":           "d-780daa32909e438aad5ee459cb21703a",
    "fin_payment_receipt_en":          "d-5f88411aa2584e63afccbbe6603b3b3a",
    "fin_payment_receipt_fr":          "d-110c93dfaea74c439488cdbe89985bf3",
    "fin_payout_sent_en":              "d-36b5f93ff1064b8c815253aa60c02829",
    "fin_payout_sent_fr":              "d-73eae4ffc4e9404f9aa931493a4f2724",
    # Seller
    "seller_new_bid_en":               "d-da5049e2aac143aa937c4dd113d9fb96",
    "seller_new_bid_fr":               "d-5e45290634c648d5aa818a733a94f13d",
    "seller_listing_approved_en":      "d-e65e2943cc6d4b0b968fb0f877357fc0",
    "seller_listing_approved_fr":      "d-2d34d8977ef84acaad852ddf73cf8fb7",
    "seller_listing_rejected_en":      "d-57976d80ab25467cad32db22cd11d06b",
    "seller_listing_rejected_fr":      "d-168a20ae972845658e166bc442904136",
    # Auction
    "auction_announcement_en":         "d-e525a2ab091a42049f75fb9d102b9cde",
    "auction_announcement_fr":         "d-7a20775199774c5b84e0c3c12c1721a6",
    "auction_reminder_en":             "d-7ae5b7a394494823b16e71a1029e1e6e",
    "auction_reminder_fr":             "d-8c5efdf9cd2449a7b288bc8d3be54885",
    "auction_results_en":              "d-4c519ffa806f41729c07b5c9feca09ab",
    "auction_results_fr":              "d-284252b173364ddab13854da54c70a87",
    # Bidding
    "bid_outbid_en":                   "d-89c95108533249aaa1659e258f11dd90",
    "bid_outbid_fr":                   "d-94110d612e1243a58fc28c99872cfce6",
    "bid_confirmed_en":                "d-fde06627d9dc4b79a250123604efb39c",
    "bid_confirmed_fr":                "d-e1fec1eab388405cb172f71c7b6e7879",
    "bid_winning_en":                  "d-27a3e1edafe24fa09437ab929eeab070",
    "bid_winning_fr":                  "d-a790684646d0430b91686923b46bf697",
    # Affiliate
    "affiliate_monthly_earnings_en":   "d-bacce34b0273477f8e7e4df61b737512",
    "affiliate_monthly_earnings_fr":   "d-7e4e67d882ad490fac384ab166e7f89b",
    "affiliate_commission_earned_en":  "d-60618f4cb6d54a579fe4cc82052ea41d",
    "affiliate_commission_earned_fr":  "d-df3d97fe87b34060b5b6dee14977efcd",
    "affiliate_referral_notification_en": "d-da95ceff24c54d39b15a29e56d804ee9",
    "affiliate_referral_notification_fr": "d-32a08f1a11a7441186944747602cfd53",
    "affiliate_program_summary_en":    "d-ea4ab5b49ce9448fa552303fa5e9e2cd",
    "affiliate_program_summary_fr":    "d-b7e970f39ce748c0bc3773a5a5606a91",
}

# Generic dynamic data that satisfies most templates
GENERIC_DATA = {
    "user_name": "QA Tester",
    "email": TEST_RECIPIENT,
    "current_year": datetime.now().year,
    "item_title": "2019 John Deere 310SL Backhoe",
    "winning_amount": "$12,500.00",
    "bid_amount": "$11,000.00",
    "auction_id": "test-auction-001",
    "listing_url": "https://bidvex.com/auction/test",
    "login_url": "https://bidvex.com/auth",
    "invoice_number": "BV-TEST-20260319",
    "amount": "$1,250.00",
    "due_date": "April 2, 2026",
    "invoice_url": "https://bidvex.com/invoices/test",
    "reset_link": "https://bidvex.com/reset-password?token=test",
    "verification_link": "https://bidvex.com/verify?token=test",
    "code": "483927",
    "ip_address": "192.168.1.1",
    "device": "Chrome on macOS",
    "location": "Montreal, QC",
    "reason": "Terms of service violation (test)",
    "ticket_id": "SUP-00001",
    "subject": "Test support ticket",
    "announcement_title": "Platform Update",
    "announcement_body": "This is a test announcement.",
    "listing_title": "2019 Cat 320 Excavator",
    "rejection_reason": "Incomplete listing details (test)",
    "payout_amount": "$8,500.00",
    "payment_method": "Direct Deposit",
    "receipt_number": "REC-20260319",
    "total_amount": "$13,250.00",
    "referral_name": "Jane Doe",
    "commission_amount": "$25.00",
    "monthly_total": "$150.00",
    "earnings_period": "February 2026",
    "update_title": "New Feature: Auto-Bid Bot",
    "update_body": "We have launched the Auto-Bid Bot for Premium subscribers.",
    "auction_title": "Heavy Equipment Auction - March 2026",
    "auction_date": "March 25, 2026",
    "auction_url": "https://bidvex.com/auction/test",
    "results_url": "https://bidvex.com/auction/test/results",
    "reminder_time": "2 hours",
    "report_type": "Fraudulent listing",
    "report_details": "Test report for validation",
    "program_name": "BidVex Affiliates",
    "summary_period": "Q1 2026",
    "total_referrals": "12",
    "total_earnings": "$300.00",
}


def fire_one(sg_client, key: str, template_id: str) -> dict:
    """Send one email and return the result dict."""
    lang = key.rsplit("_", 1)[-1]  # 'en' or 'fr'
    data = {**GENERIC_DATA, "language": lang}

    message = Mail(from_email=Email(FROM_EMAIL, FROM_NAME), to_emails=To(TEST_RECIPIENT))
    message.template_id = template_id
    message.dynamic_template_data = data

    try:
        resp = sg_client.send(message)
        return {"key": key, "template_id": template_id, "status_code": resp.status_code, "error": None}
    except Exception as e:
        status = getattr(e, "status_code", None)
        body = ""
        try:
            body = e.body.decode() if hasattr(e, "body") else str(e)
        except Exception:
            body = str(e)
        return {"key": key, "template_id": template_id, "status_code": status, "error": body}


def main():
    if not API_KEY:
        print("SENDGRID_API_KEY not set. Aborting.")
        sys.exit(1)

    sg = SendGridAPIClient(api_key=API_KEY)
    total = len(TEMPLATES)

    print("=" * 78)
    print("  BidVex — Full SendGrid Template Validation")
    print(f"  {total} templates  |  Recipient: {TEST_RECIPIENT}")
    print("=" * 78)

    results = []
    flagged = []
    batch = 0

    for key, tid in sorted(TEMPLATES.items()):
        r = fire_one(sg, key, tid)
        results.append(r)

        status = r["status_code"]
        err = r["error"]
        label = f"[{key}]"

        if status and 200 <= status < 300:
            print(f"  PASS  {label:50s}  HTTP {status}")
        elif status == 400:
            tag = "INVALID TEMPLATE ID" if "template" in (err or "").lower() else (err or "")[:60]
            print(f"  FAIL  {label:50s}  HTTP 400 — {tag}")
            flagged.append(r)
        else:
            print(f"  FAIL  {label:50s}  HTTP {status} — {(err or '')[:60]}")
            flagged.append(r)

        batch += 1
        # SendGrid rate limit: ~100 msg/s; small pause every 10 to be safe
        if batch % 10 == 0:
            time.sleep(0.5)

    # ── Summary ──────────────────────────────────────────────────────
    passed = sum(1 for r in results if r["status_code"] and 200 <= r["status_code"] < 300)
    failed = total - passed

    print("=" * 78)
    print(f"  RESULTS: {passed} passed, {failed} failed out of {total}")

    if flagged:
        print()
        print("  FLAGGED TEMPLATES:")
        for f in flagged:
            print(f"    {f['key']:50s}  HTTP {f['status_code']}  |  {(f['error'] or '')[:80]}")
    else:
        print("  No flagged templates. All IDs are valid.")

    print("=" * 78)

    report = {
        "timestamp": datetime.now().isoformat(),
        "recipient": TEST_RECIPIENT,
        "total": total,
        "passed": passed,
        "failed": failed,
        "results": results,
        "flagged": flagged,
    }
    report_path = os.path.join(os.path.dirname(__file__), "email_test_report.json")
    with open(report_path, "w") as fp:
        json.dump(report, fp, indent=2)
    print(f"  Report: {report_path}")

    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    main()
