"""
Tests for Partner Pro email templates.
Validates HTML structure, content, and all 5 template functions.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.partner_pro_emails import (
    trial_started,
    trial_reminder,
    trial_expired,
    subscription_confirmed,
    invoice_ready,
)


class TestTrialStarted:
    def test_returns_subject_and_html(self):
        result = trial_started("Alice", "April 3, 2026")
        assert "subject" in result
        assert "html" in result

    def test_subject_contains_brand(self):
        result = trial_started("Alice", "April 3, 2026")
        assert "BidVex" in result["subject"]
        assert "Partner Pro" in result["subject"]

    def test_html_contains_user_name(self):
        result = trial_started("Alice", "April 3, 2026")
        assert "Alice" in result["html"]

    def test_html_contains_trial_end_date(self):
        result = trial_started("Alice", "April 3, 2026")
        assert "April 3, 2026" in result["html"]

    def test_html_contains_features_list(self):
        result = trial_started("Alice", "April 3, 2026")
        html = result["html"]
        assert "Branded Storefront" in html
        assert "CSV Bulk Listing Import" in html
        assert "Early Auction Access" in html
        assert "Featured Listings" in html
        assert "Analytics Dashboard" in html

    def test_html_contains_cta_link(self):
        result = trial_started("Alice", "April 3, 2026")
        assert "Explore Partner Pro" in result["html"]
        assert "settings/profile" in result["html"]

    def test_valid_html_structure(self):
        result = trial_started("Alice", "April 3, 2026")
        assert result["html"].startswith("<!DOCTYPE html>")
        assert "</html>" in result["html"]


class TestTrialReminder:
    def test_returns_subject_and_html(self):
        result = trial_reminder("Bob", 3)
        assert "subject" in result
        assert "html" in result

    def test_subject_contains_days(self):
        result = trial_reminder("Bob", 3)
        assert "3 days" in result["subject"]

    def test_html_contains_user_name(self):
        result = trial_reminder("Bob", 3)
        assert "Bob" in result["html"]

    def test_html_contains_price(self):
        result = trial_reminder("Bob", 3)
        assert "$240/year" in result["html"]

    def test_html_contains_subscribe_cta(self):
        result = trial_reminder("Bob", 3)
        assert "Subscribe Now" in result["html"]

    def test_custom_days_left(self):
        result = trial_reminder("Bob", 7)
        assert "7 days" in result["html"]


class TestTrialExpired:
    def test_returns_subject_and_html(self):
        result = trial_expired("Carol")
        assert "subject" in result
        assert "html" in result

    def test_subject_indicates_ended(self):
        result = trial_expired("Carol")
        assert "ended" in result["subject"]

    def test_html_contains_reactivate_cta(self):
        result = trial_expired("Carol")
        assert "Reactivate Partner Pro" in result["html"]

    def test_html_mentions_free_tier(self):
        result = trial_expired("Carol")
        assert "Free" in result["html"]


class TestSubscriptionConfirmed:
    def test_returns_subject_and_html(self):
        result = subscription_confirmed("Dave", "Partner Pro", "$240.00 CAD", "March 20, 2027")
        assert "subject" in result
        assert "html" in result

    def test_subject_contains_plan_name(self):
        result = subscription_confirmed("Dave", "Partner Pro", "$240.00 CAD", "March 20, 2027")
        assert "Partner Pro" in result["subject"]

    def test_html_contains_billing_details(self):
        result = subscription_confirmed("Dave", "Partner Pro", "$240.00 CAD", "March 20, 2027")
        html = result["html"]
        assert "Partner Pro" in html
        assert "$240.00 CAD" in html
        assert "March 20, 2027" in html

    def test_html_contains_dashboard_link(self):
        result = subscription_confirmed("Dave", "Partner Pro", "$240.00 CAD", "March 20, 2027")
        assert "Go to Dashboard" in result["html"]


class TestInvoiceReady:
    def test_returns_subject_and_html(self):
        result = invoice_ready("Eve", "INV-2026-001", "https://example.com/dl", "$240.00 CAD")
        assert "subject" in result
        assert "html" in result

    def test_subject_contains_invoice_number(self):
        result = invoice_ready("Eve", "INV-2026-001", "https://example.com/dl", "$240.00 CAD")
        assert "INV-2026-001" in result["subject"]

    def test_html_contains_download_link(self):
        result = invoice_ready("Eve", "INV-2026-001", "https://example.com/dl", "$240.00 CAD")
        assert "https://example.com/dl" in result["html"]
        assert "Download Invoice" in result["html"]

    def test_html_mentions_expiry(self):
        result = invoice_ready("Eve", "INV-2026-001", "https://example.com/dl", "$240.00 CAD")
        assert "expires in 1 hour" in result["html"]

    def test_html_contains_amount(self):
        result = invoice_ready("Eve", "INV-2026-001", "https://example.com/dl", "$240.00 CAD")
        assert "$240.00 CAD" in result["html"]


class TestAllTemplatesCommon:
    """Cross-cutting concerns for all templates."""

    @pytest.mark.parametrize("template_fn,args", [
        (trial_started, ("User", "April 1, 2026")),
        (trial_reminder, ("User", 3)),
        (trial_expired, ("User",)),
        (subscription_confirmed, ("User", "Partner Pro", "$240", "2027-03-20")),
        (invoice_ready, ("User", "INV-001", "https://x.com/dl", "$100")),
    ])
    def test_all_return_dict_with_subject_and_html(self, template_fn, args):
        result = template_fn(*args)
        assert isinstance(result, dict)
        assert "subject" in result
        assert "html" in result
        assert len(result["subject"]) > 0
        assert len(result["html"]) > 100

    @pytest.mark.parametrize("template_fn,args", [
        (trial_started, ("User", "April 1, 2026")),
        (trial_reminder, ("User", 3)),
        (trial_expired, ("User",)),
        (subscription_confirmed, ("User", "Partner Pro", "$240", "2027-03-20")),
        (invoice_ready, ("User", "INV-001", "https://x.com/dl", "$100")),
    ])
    def test_all_contain_brand_name(self, template_fn, args):
        result = template_fn(*args)
        assert "BidVex" in result["html"]

    @pytest.mark.parametrize("template_fn,args", [
        (trial_started, ("User", "April 1, 2026")),
        (trial_reminder, ("User", 3)),
        (trial_expired, ("User",)),
        (subscription_confirmed, ("User", "Partner Pro", "$240", "2027-03-20")),
        (invoice_ready, ("User", "INV-001", "https://x.com/dl", "$100")),
    ])
    def test_all_valid_html(self, template_fn, args):
        result = template_fn(*args)
        assert "<!DOCTYPE html>" in result["html"]
        assert "</html>" in result["html"]
        assert "<body" in result["html"]
        assert "</body>" in result["html"]
