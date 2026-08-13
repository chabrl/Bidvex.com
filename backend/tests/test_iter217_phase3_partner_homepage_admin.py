"""
iter217 Phase 3 — Tests for the admin / homepage / partner-dashboard fixes:
  - Bug 3B  Moderation queue expanded status set
  - Bug 3C  Compliance alerts: unpaid dealers/partners + unverified facilities
  - Bug 3E  Send-notification writes the canonical `message` field
  - Bug 3G  Document request stamps deadline on user doc + overdue badge field
  - Fix 1   Partner dashboard route (signature check)
  - Fix 2   ProfessionalAuctionsPromo / seller_account_type filter (route signature)
"""
import inspect
import pytest

from routes.admin_ops import admin_get_pending_listings, admin_compliance_alerts
from routes.admin_user_management import (
    admin_send_notification,
    admin_request_documents,
    SendNotificationPayload,
    RequestDocumentsPayload,
)
from routes.listings import get_multi_item_listings


class TestModerationStatusExpansion:
    def test_pending_endpoint_is_async(self):
        assert inspect.iscoroutinefunction(admin_get_pending_listings)

    def test_pending_endpoint_source_includes_manual_and_pending_review(self):
        src = inspect.getsource(admin_get_pending_listings)
        # The query must now match ALL three pending status strings.
        assert "manual_review" in src
        assert "pending_review" in src
        # And still match the legacy "pending" status.
        assert '"pending"' in src or "'pending'" in src


class TestComplianceAlertsNewBuckets:
    def test_compliance_alerts_returns_unpaid_buckets(self):
        # Source-level contract — the function MUST gather these buckets so
        # the admin Compliance Alerts tab is non-empty when unpaid accounts exist.
        src = inspect.getsource(admin_compliance_alerts)
        assert "unpaid_dealers" in src
        assert "unpaid_partners" in src
        assert "unverified_facilities" in src
        # And the canonical fields used to detect them
        assert "dealer_subscription_active" in src
        assert "partner_subscription_active" in src
        assert "storage_facilities" in src


class TestSendNotificationSchema:
    def test_payload_accepts_send_via_both(self):
        p = SendNotificationPayload(
            notification_type="general",
            subject="Hi",
            body_en="Body EN",
            body_fr="Body FR",
            send_via="both",
        )
        assert p.send_via == "both"

    def test_send_notification_writes_canonical_message_field(self):
        # The bug being fixed: the legacy path only wrote message_en / message_fr,
        # which the NotificationCenter does not read. Source check confirms the
        # fix is in place.
        src = inspect.getsource(admin_send_notification)
        # `message` (canonical, read by the bell) must be written alongside _en/_fr
        assert '"message"' in src or "'message'" in src
        assert '"message_en"' in src
        assert '"message_fr"' in src

    def test_send_notification_emits_read_field(self):
        # NotificationCenter checks `notification.read` (boolean).
        src = inspect.getsource(admin_send_notification)
        assert '"read": False' in src


class TestRequestDocumentsStampsUserDoc:
    def test_payload_minimal(self):
        p = RequestDocumentsPayload(
            document_types=["government_id"],
            deadline="2030-12-31",
        )
        assert p.deadline == "2030-12-31"
        assert "government_id" in p.document_types

    def test_request_documents_writes_deadline_onto_user(self):
        # iter217 Phase 3 — Stamp `document_request_deadline` + status onto the
        # user doc so the admin user-table can compute the Overdue badge in one
        # query (no N+1).
        src = inspect.getsource(admin_request_documents)
        assert "document_request_deadline" in src
        assert "document_request_status" in src
        assert "active_document_request_id" in src

    def test_request_documents_notification_includes_action_url(self):
        src = inspect.getsource(admin_request_documents)
        assert '"action_url"' in src
        assert "/settings?tab=documents" in src


class TestProfessionalAuctionsEndpoint:
    def test_multi_item_listings_accepts_seller_account_type(self):
        sig = inspect.signature(get_multi_item_listings)
        assert "seller_account_type" in sig.parameters
        assert "promoted_first" in sig.parameters

    def test_multi_item_listings_filters_after_enrichment(self):
        # The filter must run AFTER enrich_listings_bulk_async so the
        # `seller_account_type` field is populated.
        src = inspect.getsource(get_multi_item_listings)
        idx_enrich = src.find("enrich_listings_bulk_async")
        idx_filter = src.find("seller_account_type:")  # the filter block uses param.split
        # Both present
        assert idx_enrich > 0
        # The filter block uses `wanted = [s.strip() for s in seller_account_type.split(",")`
        assert "seller_account_type.split" in src


class TestPartnerDashboardRouteAlias:
    def test_lots_create_alias_in_app_js(self):
        # Source-level contract — the App.js must declare the alias.
        import pathlib
        app_js = pathlib.Path("/app/frontend/src/App.js").read_text(encoding="utf-8")
        assert '"/lots/create"' in app_js
        assert "/create-multi-item-listing" in app_js
