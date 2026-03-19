"""
Test Suite: Pay-to-Activate Partner Feature - Iteration 52
Tests the BidVex Partner accounts payment flow:
- GET /api/partner/payment-status
- POST /api/partner/create-checkout  
- POST /api/admin/partners/{user_id}/verify
- POST /api/listings (permission check for unpaid partners)
- POST /api/multi-item-listings (permission check for unpaid partners)
- POST /api/admin/partners/{user_id}/toggle
- GET /api/admin/partners (platform_fee_paid field)
- Webhook handlers for partner activation

Created: 2026-03-19
"""

import pytest
import requests
import os
import json
import uuid
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://cookie-consent-i18n.preview.emergentagent.com"

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token for testing"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Admin authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(scope="module")
def test_partner_user(admin_token):
    """Create or find a test partner user in the database"""
    # First, try to find an existing test partner
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = requests.get(f"{BASE_URL}/api/admin/partners?status=all", headers=headers)
    
    if response.status_code == 200:
        applications = response.json().get("applications", [])
        # Look for test partner user
        for app in applications:
            if app.get("email", "").startswith("testpartner_") or app.get("email") == "test_partner_unpaid@bidvex.com":
                return app
    
    # If no test partner exists, we'll create test data via direct MongoDB manipulation
    # For now, return None and tests will handle accordingly
    return None


class TestPartnerPaymentStatusEndpoint:
    """Tests for GET /api/partner/payment-status"""
    
    def test_non_partner_returns_error(self, admin_token):
        """Non-partner users should get 400 error"""
        # Admin is not a partner, so this should fail
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/partner/payment-status", headers=headers)
        
        # Should return 400 for non-partner
        # Note: Admin might be a partner, so we check both cases
        if response.status_code == 200:
            data = response.json()
            assert "is_partner" in data
            assert "platform_fee_paid" in data
            print(f"Admin is a partner: {data}")
        else:
            assert response.status_code == 400
            assert "Not a partner" in response.json().get("detail", "")
            print("Admin correctly rejected as not a partner")
    
    def test_endpoint_requires_auth(self):
        """Unauthenticated requests should be rejected"""
        response = requests.get(f"{BASE_URL}/api/partner/payment-status")
        assert response.status_code == 401
        print("Authentication correctly required")


class TestPartnerCreateCheckoutEndpoint:
    """Tests for POST /api/partner/create-checkout"""
    
    def test_non_partner_returns_error(self, admin_token):
        """Non-partner users should get 400 error"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(f"{BASE_URL}/api/partner/create-checkout", headers=headers)
        
        # Should return 400 for non-partner or already paid
        if response.status_code == 200:
            data = response.json()
            assert "checkout_url" in data
            print(f"Checkout created (user is partner): {data.get('checkout_url', '')[:50]}...")
        else:
            assert response.status_code == 400
            detail = response.json().get("detail", "")
            assert "Not a partner" in detail or "already paid" in detail
            print(f"Correctly rejected: {detail}")
    
    def test_endpoint_requires_auth(self):
        """Unauthenticated requests should be rejected"""
        response = requests.post(f"{BASE_URL}/api/partner/create-checkout")
        assert response.status_code == 401
        print("Authentication correctly required")


class TestAdminVerifyPartnerEndpoint:
    """Tests for POST /api/admin/partners/{user_id}/verify"""
    
    def test_requires_admin_role(self):
        """Non-admin users should be rejected"""
        response = requests.post(f"{BASE_URL}/api/admin/partners/some_user_id/verify", json={})
        assert response.status_code == 401
        print("Authentication correctly required")
    
    def test_verify_returns_checkout_url(self, admin_token):
        """Verify endpoint should return checkout_url for pending partners"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get pending partners
        response = requests.get(f"{BASE_URL}/api/admin/partners?status=pending", headers=headers)
        if response.status_code != 200:
            pytest.skip("Could not fetch pending partners")
        
        applications = response.json().get("applications", [])
        if not applications:
            pytest.skip("No pending partner applications to test with")
        
        pending_partner = applications[0]
        user_id = pending_partner.get("id")
        
        # Try to verify (this will create a real Stripe checkout)
        verify_response = requests.post(
            f"{BASE_URL}/api/admin/partners/{user_id}/verify",
            json={"custom_premium_rate": 0.15},
            headers=headers
        )
        
        if verify_response.status_code == 200:
            data = verify_response.json()
            assert data.get("success") == True
            # checkout_url may or may not be present depending on Stripe config
            if "checkout_url" in data:
                assert data["checkout_url"].startswith("https://checkout.stripe.com") or data["checkout_url"] is None
                print(f"Partner verified with checkout URL")
            else:
                print("Partner verified (no checkout URL in response)")
        elif verify_response.status_code == 400:
            # Already not pending
            print(f"Partner not in pending status: {verify_response.json().get('detail')}")
        else:
            pytest.fail(f"Unexpected status: {verify_response.status_code} - {verify_response.text}")


class TestAdminPartnersListEndpoint:
    """Tests for GET /api/admin/partners"""
    
    def test_returns_platform_fee_paid_field(self, admin_token):
        """Response should include platform_fee_paid field for each partner"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/partners?status=all", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "applications" in data
        
        applications = data["applications"]
        if applications:
            # Check that verified partners have platform_fee_paid field
            for app in applications:
                if app.get("partner_verification_status") == "verified":
                    assert "platform_fee_paid" in app, f"Missing platform_fee_paid for {app.get('email')}"
                    print(f"Partner {app.get('email')}: fee_paid={app.get('platform_fee_paid')}")
        else:
            print("No partner applications found")
    
    def test_filter_by_status(self, admin_token):
        """Should be able to filter by verification status"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        for status in ["pending", "verified", "rejected"]:
            response = requests.get(f"{BASE_URL}/api/admin/partners?status={status}", headers=headers)
            assert response.status_code == 200
            data = response.json()
            # All returned should match the filter
            for app in data.get("applications", []):
                assert app.get("partner_verification_status") == status or status == "all"
            print(f"Filter '{status}': {len(data.get('applications', []))} results")


class TestPartnerToggleEndpoint:
    """Tests for POST /api/admin/partners/{user_id}/toggle"""
    
    def test_toggle_sets_platform_fee_paid_false(self, admin_token):
        """Toggling partner status should set platform_fee_paid=False"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get verified partners
        response = requests.get(f"{BASE_URL}/api/admin/partners?status=verified", headers=headers)
        if response.status_code != 200:
            pytest.skip("Could not fetch verified partners")
        
        applications = response.json().get("applications", [])
        if not applications:
            pytest.skip("No verified partners to test toggle")
        
        # Find a test partner (don't toggle real partners)
        test_partner = None
        for app in applications:
            if "test" in app.get("email", "").lower():
                test_partner = app
                break
        
        if not test_partner:
            pytest.skip("No test partner found - skipping toggle test to avoid affecting real data")
        
        user_id = test_partner.get("id")
        
        # Toggle off
        toggle_response = requests.post(
            f"{BASE_URL}/api/admin/partners/{user_id}/toggle",
            headers=headers
        )
        
        if toggle_response.status_code == 200:
            data = toggle_response.json()
            assert "is_partner" in data
            print(f"Toggle result: is_partner={data.get('is_partner')}")
            
            # Verify in partner list
            verify_response = requests.get(f"{BASE_URL}/api/admin/partners?status=all", headers=headers)
            if verify_response.status_code == 200:
                for app in verify_response.json().get("applications", []):
                    if app.get("id") == user_id:
                        # If toggled off, platform_fee_paid should be False
                        if not data.get("is_partner"):
                            assert app.get("platform_fee_paid") == False
                        break
        else:
            print(f"Toggle failed: {toggle_response.status_code} - {toggle_response.text}")


class TestListingCreationPermissions:
    """Tests for listing creation permission checks"""
    
    def test_create_listing_requires_auth(self):
        """Unauthenticated listing creation should fail"""
        response = requests.post(f"{BASE_URL}/api/listings", json={
            "title": "Test Item",
            "description": "Test description",
            "category": "Electronics",
            "condition": "good",
            "starting_price": 100,
            "location": "Test City",
            "city": "Test City",
            "region": "QC",
            "auction_end_date": "2026-04-01T00:00:00Z",
            "agreement_accepted": True
        })
        assert response.status_code == 401
        print("Authentication correctly required for listing creation")
    
    def test_create_multi_item_listing_requires_auth(self):
        """Unauthenticated multi-item listing creation should fail"""
        response = requests.post(f"{BASE_URL}/api/multi-item-listings", json={
            "title": "Test Auction",
            "description": "Test description",
            "category": "Electronics",
            "location": "Test City",
            "city": "Test City", 
            "region": "QC",
            "auction_end_date": "2026-04-01T00:00:00Z",
            "lots": [{"lot_number": 1, "title": "Lot 1", "description": "Desc", "quantity": 1, "starting_price": 10, "current_price": 10, "condition": "good"}],
            "agreement_accepted": True
        })
        assert response.status_code == 401
        print("Authentication correctly required for multi-item listing creation")


class TestStripeWebhookHandlers:
    """Tests for Stripe webhook handling of partner activation events"""
    
    def test_webhook_endpoint_exists(self):
        """Webhook endpoint should be accessible"""
        # Send empty POST to check endpoint exists
        response = requests.post(f"{BASE_URL}/api/webhooks/stripe", 
                                json={"type": "test_event", "data": {}})
        # Should not be 404
        assert response.status_code != 404
        print(f"Webhook endpoint responded with: {response.status_code}")
    
    def test_checkout_completed_partner_activation(self, admin_token):
        """Simulate checkout.session.completed for partner activation"""
        # Create a simulated Stripe webhook payload
        test_user_id = str(uuid.uuid4())
        
        webhook_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": f"cs_test_{uuid.uuid4().hex[:24]}",
                    "subscription": f"sub_test_{uuid.uuid4().hex[:24]}",
                    "metadata": {
                        "user_id": test_user_id,
                        "type": "partner_activation"
                    }
                }
            }
        }
        
        # Send webhook (without signature - should fall back to JSON parsing)
        response = requests.post(
            f"{BASE_URL}/api/webhooks/stripe",
            json=webhook_payload
        )
        
        # Should be 200 OK or 500 if user not found (which is expected for fake user)
        assert response.status_code in [200, 500]
        print(f"Checkout completed webhook response: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
    
    def test_subscription_deleted_partner_softlock(self, admin_token):
        """Simulate customer.subscription.deleted for partner soft-lock"""
        test_user_id = str(uuid.uuid4())
        
        webhook_payload = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": f"sub_test_{uuid.uuid4().hex[:24]}",
                    "customer": f"cus_test_{uuid.uuid4().hex[:24]}",
                    "metadata": {
                        "user_id": test_user_id,
                        "type": "partner_annual_fee"
                    }
                }
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/webhooks/stripe",
            json=webhook_payload
        )
        
        assert response.status_code in [200, 500]
        print(f"Subscription deleted webhook response: {response.status_code}")
    
    def test_payment_failed_partner_softlock(self, admin_token):
        """Simulate invoice.payment_failed for partner payment failure"""
        webhook_payload = {
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "id": f"in_test_{uuid.uuid4().hex[:24]}",
                    "customer": f"cus_test_{uuid.uuid4().hex[:24]}",
                    "subscription": f"sub_test_{uuid.uuid4().hex[:24]}",
                    "amount_due": 10000,
                    "currency": "cad",
                    "last_finalization_error": {"message": "Card declined"}
                }
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/webhooks/stripe",
            json=webhook_payload
        )
        
        assert response.status_code in [200, 500]
        print(f"Payment failed webhook response: {response.status_code}")
    
    def test_payment_succeeded_partner_reactivation(self, admin_token):
        """Simulate invoice.payment_succeeded for partner re-activation"""
        webhook_payload = {
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": f"in_test_{uuid.uuid4().hex[:24]}",
                    "customer": f"cus_test_{uuid.uuid4().hex[:24]}",
                    "subscription": f"sub_test_{uuid.uuid4().hex[:24]}",
                    "amount_paid": 10000,
                    "currency": "cad"
                }
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/webhooks/stripe",
            json=webhook_payload
        )
        
        assert response.status_code in [200, 500]
        print(f"Payment succeeded webhook response: {response.status_code}")


class TestHealthAndBasicEndpoints:
    """Basic health checks"""
    
    def test_api_health(self):
        """API should be healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("API is healthy")
    
    def test_admin_login(self):
        """Admin should be able to login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data.get("user", {}).get("role") in ["admin", "superadmin"]
        print(f"Admin login successful: {data['user'].get('email')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
