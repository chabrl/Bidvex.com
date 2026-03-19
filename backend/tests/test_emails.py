"""
BidVex SendGrid Email Template Validation
Triggers real SendGrid API calls for:
  1. Welcome (auth_welcome)
  2. Winning Bid (bid_winning)
  3. Invoice Issued (fin_invoice_issued)

For both lang='en' and lang='fr'.
Logs the SendGrid API response status. Flags 400 (Invalid Template ID) immediately.
"""

import asyncio
import os
import sys
import json
from datetime import datetime

# Ensure backend modules are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To

# ── Configuration ─────────────────────────────────────────────────────
API_KEY = os.environ.get("SENDGRID_API_KEY")
FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "info@bidvex.com")
FROM_NAME = os.environ.get("SENDGRID_FROM_NAME", "BidVex")
# Send to verified sender so we don't trigger bounce; sink address is fine for validation
TEST_RECIPIENT = FROM_EMAIL

# Template IDs are loaded from DEFAULT_EMAIL_TEMPLATES in server.py.
# Re-declaring here to keep the test self-contained.
TEMPLATES = {
    "auth_welcome_en": "d-db7d296ad54247138f3f210a1fb52e0a",
    "auth_welcome_fr": "d-256f3801670441808730c4cfb259d9a2",
    "bid_winning_en": "d-27a3e1edafe24fa09437ab929eeab070",
    "bid_winning_fr": "d-a790684646d0430b91686923b46bf697",
    "fin_invoice_issued_en": "d-d25445886edb4cc08cc8107b07cb343f",
    "fin_invoice_issued_fr": "d-780daa32909e438aad5ee459cb21703a",
}

# Dynamic data payloads that SendGrid templates typically expect
DYNAMIC_DATA = {
    "auth_welcome": {
        "user_name": "QA Test User",
        "email": TEST_RECIPIENT,
        "login_url": "https://bidvex.com/auth",
        "current_year": datetime.now().year,
    },
    "bid_winning": {
        "user_name": "QA Test User",
        "item_title": "2019 John Deere 310SL Backhoe",
        "winning_amount": "$12,500.00",
        "auction_id": "test-auction-001",
        "listing_url": "https://bidvex.com/auction/test-auction-001",
        "current_year": datetime.now().year,
    },
    "fin_invoice_issued": {
        "user_name": "QA Test User",
        "invoice_number": "BV-TEST-20260319",
        "amount": "$1,250.00",
        "due_date": "April 2, 2026",
        "invoice_url": "https://bidvex.com/invoices/test",
        "current_year": datetime.now().year,
    },
}


def send_template_email(sg_client, template_key: str, lang: str) -> dict:
    """Send a single template email and return {key, lang, status_code, error}."""
    full_key = f"{template_key}_{lang}"
    template_id = TEMPLATES.get(full_key)
    if not template_id:
        return {"key": full_key, "lang": lang, "status_code": None, "error": "TEMPLATE_ID_NOT_FOUND"}

    base_key = template_key  # e.g. "auth_welcome"
    data = {**DYNAMIC_DATA.get(base_key, {}), "language": lang}

    message = Mail(
        from_email=Email(FROM_EMAIL, FROM_NAME),
        to_emails=To(TEST_RECIPIENT),
    )
    message.template_id = template_id
    message.dynamic_template_data = data

    try:
        response = sg_client.send(message)
        return {
            "key": full_key,
            "lang": lang,
            "status_code": response.status_code,
            "error": None,
        }
    except Exception as e:
        status = getattr(e, "status_code", None)
        body = ""
        try:
            body = e.body.decode() if hasattr(e, "body") else str(e)
        except Exception:
            body = str(e)
        return {
            "key": full_key,
            "lang": lang,
            "status_code": status,
            "error": body,
        }


def main():
    if not API_KEY:
        print("SENDGRID_API_KEY not set. Aborting.")
        sys.exit(1)

    sg = SendGridAPIClient(api_key=API_KEY)
    template_keys = ["auth_welcome", "bid_winning", "fin_invoice_issued"]
    languages = ["en", "fr"]

    results = []
    flagged = []

    print("=" * 72)
    print("  BidVex SendGrid Template Validation")
    print("=" * 72)
    print(f"  Recipient : {TEST_RECIPIENT}")
    print(f"  Templates : {len(template_keys)} x {len(languages)} langs = {len(template_keys)*len(languages)} emails")
    print("=" * 72)

    for tpl_key in template_keys:
        for lang in languages:
            result = send_template_email(sg, tpl_key, lang)
            results.append(result)

            status = result["status_code"]
            err = result["error"]
            label = f"  [{result['key']}]"

            if status and 200 <= status < 300:
                print(f"  PASS  {label:50s}  HTTP {status}")
            elif status == 400:
                msg = "INVALID TEMPLATE ID" if "template" in (err or "").lower() else err[:80]
                print(f"  FAIL  {label:50s}  HTTP 400 — {msg}")
                flagged.append(result)
            else:
                short_err = (err or "unknown")[:80]
                print(f"  FAIL  {label:50s}  HTTP {status} — {short_err}")
                flagged.append(result)

    print("=" * 72)
    passed = sum(1 for r in results if r["status_code"] and 200 <= r["status_code"] < 300)
    failed = len(results) - passed
    print(f"  Results: {passed} passed, {failed} failed out of {len(results)} total")

    if flagged:
        print("\n  FLAGGED TEMPLATES:")
        for f in flagged:
            print(f"    {f['key']}  →  HTTP {f['status_code']}  |  {(f['error'] or '')[:120]}")

    print("=" * 72)

    # Write machine-readable report
    report = {
        "timestamp": datetime.now().isoformat(),
        "recipient": TEST_RECIPIENT,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "results": results,
        "flagged": flagged,
    }
    report_path = os.path.join(os.path.dirname(__file__), "email_test_report.json")
    with open(report_path, "w") as fp:
        json.dump(report, fp, indent=2)
    print(f"  Report written to {report_path}")

    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    main()
