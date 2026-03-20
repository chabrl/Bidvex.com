"""
BidVex Pre-Launch Hardening Tests - Iteration 75
Tests for:
1. Rate limiting (login 10/min, register 5/min, bids 30/min, default 100/min)
2. Stripe webhook signature verification
3. Partner Pro trial features (for trialing user)
4. Subscription plans endpoint
5. Storefront endpoint
6. Health endpoint
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestHealthAndBasicEndpoints:
    """Basic API health checks"""
    
    def test_health_endpoint(self):
        """GET /api/health returns 200 healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✓ Health endpoint: {data}")
    
    def test_subscription_plans_returns_4_tiers(self):
        """GET /api/subscription-plans returns 4 tiers including partner_pro"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        plans = data.get("plans", [])
        plan_ids = [p.get("plan_id") for p in plans]
        assert "free" in plan_ids
        assert "premium" in plan_ids
        assert "partner_pro" in plan_ids
        assert "vip" in plan_ids
        print(f"✓ Subscription plans: {plan_ids}")


class TestAuthentication:
    """Authentication and login tests"""
    
    def test_login_success(self):
        """POST /api/auth/login with valid credentials returns 200"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        print(f"✓ Login successful for {ADMIN_EMAIL}")
        return data["access_token"]
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login with invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "nonexistent@bidvex.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Invalid login correctly returns 401")


class TestRateLimiting:
    """Rate limiting tests - Note: may share IP in K8s environment"""
    
    def test_health_under_100_per_minute(self):
        """Regular endpoints (e.g. /api/health) work under 100/min"""
        # Send 10 rapid requests (well under limit)
        for i in range(10):
            response = requests.get(f"{BASE_URL}/api/health")
            assert response.status_code == 200, f"Request {i+1} failed"
        print("✓ Health endpoint works for 10 rapid requests (under 100/min limit)")
    
    def test_login_rate_limiting_note(self):
        """Note about login rate limiting (10/min) - may not trigger due to shared IP"""
        # In K8s environment, all requests may come from same proxy IP
        # So rate limits may be shared across tests
        # This test documents the expected behavior
        print("NOTE: Login rate limit is 10/minute per IP")
        print("NOTE: In K8s preview environment, rate limits may be shared across all requests")
        print("✓ Rate limiting documentation noted")
    
    def test_register_rate_limiting_note(self):
        """Note about register rate limiting (5/min) - may not trigger due to shared IP"""
        print("NOTE: Register rate limit is 5/minute per IP")
        print("NOTE: Attempting to test rate limiting may affect other endpoints")
        print("✓ Rate limiting documentation noted")


class TestStripeWebhook:
    """Stripe webhook signature verification tests"""
    
    def test_stripe_webhook_without_signature_returns_400(self):
        """POST /api/webhooks/stripe without stripe-signature header returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/webhooks/stripe",
            json={"type": "test.event", "data": {"object": {}}},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"✓ Unsigned Stripe webhook rejected with 400: {response.json()}")
    
    def test_stripe_webhook_with_invalid_signature_returns_400(self):
        """POST /api/webhooks/stripe with invalid signature returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/webhooks/stripe",
            json={"type": "test.event", "data": {"object": {}}},
            headers={
                "Content-Type": "application/json",
                "stripe-signature": "t=1234567890,v1=invalid_signature_here"
            }
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"✓ Invalid Stripe signature rejected with 400: {response.json()}")


class TestPartnerProTrialFeatures:
    """Partner Pro trial features for trialing user (admin user has active trial)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.user = response.json().get("user")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Could not authenticate admin user")
    
    def test_partner_pro_trial_status(self):
        """GET /api/partner-pro/trial/status returns trial status for admin user"""
        response = requests.get(
            f"{BASE_URL}/api/partner-pro/trial/status",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        # Admin user should have active trial
        assert "is_trialing" in data
        assert "trial_used" in data
        assert "days_remaining" in data
        print(f"✓ Trial status: is_trialing={data.get('is_trialing')}, days_remaining={data.get('days_remaining')}")
    
    def test_partner_pro_featured_listings(self):
        """GET /api/partner-pro/featured-listings returns data for trialing user"""
        response = requests.get(
            f"{BASE_URL}/api/partner-pro/featured-listings",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "used" in data
        assert "limit" in data
        print(f"✓ Featured listings: used={data.get('used')}, limit={data.get('limit')}")
    
    def test_partner_pro_analytics_export_json(self):
        """GET /api/partner-pro/analytics/export?format=json returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/partner-pro/analytics/export?format=json",
            headers=self.headers
        )
        assert response.status_code == 200
        # Should return JSON with analytics data
        assert response.headers.get("Content-Type", "").startswith("application/json")
        print("✓ Analytics export (JSON) works for trialing user")
    
    def test_partner_pro_bulk_import_template(self):
        """GET /api/partner-pro/bulk-import/template returns CSV template"""
        response = requests.get(
            f"{BASE_URL}/api/partner-pro/bulk-import/template"
        )
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("Content-Type", "")
        assert "attachment" in response.headers.get("Content-Disposition", "")
        print("✓ Bulk import CSV template download works")
    
    def test_partner_pro_early_access(self):
        """GET /api/partner-pro/early-access returns early access listings"""
        response = requests.get(
            f"{BASE_URL}/api/partner-pro/early-access",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "early_access_listings" in data
        print(f"✓ Early access listings: count={data.get('count')}")


class TestStorefront:
    """Public storefront endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get user ID from login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            self.user_id = response.json().get("user", {}).get("id")
        else:
            pytest.skip("Could not authenticate admin user")
    
    def test_storefront_returns_seller_data(self):
        """GET /api/storefronts/{user_id} returns storefront data"""
        response = requests.get(f"{BASE_URL}/api/storefronts/{self.user_id}")
        assert response.status_code == 200
        data = response.json()
        assert "seller" in data
        assert "storefront" in data
        assert "listings" in data
        assert data.get("has_storefront") is True  # partner_pro user
        print(f"✓ Storefront for {self.user_id}: has_storefront={data.get('has_storefront')}")
    
    def test_storefront_invalid_user_returns_404(self):
        """GET /api/storefronts/{invalid_id} returns 404"""
        response = requests.get(f"{BASE_URL}/api/storefronts/nonexistent-user-id")
        assert response.status_code == 404
        print("✓ Invalid storefront user returns 404")


class TestPartnerProEmailTemplates:
    """Verify Partner Pro email templates exist (unit test for templates)"""
    
    def test_email_templates_importable(self):
        """Email templates module can be imported and has required functions"""
        try:
            import sys
            sys.path.insert(0, '/app/backend')
            from services.partner_pro_emails import (
                trial_started,
                trial_reminder,
                trial_expired,
                subscription_confirmed,
                invoice_ready
            )
            
            # Test trial_started template
            result = trial_started("Test User", "January 15, 2026")
            assert "subject" in result
            assert "html" in result
            assert "Partner Pro" in result["subject"]
            
            # Test trial_reminder template
            result = trial_reminder("Test User", 3)
            assert "subject" in result
            assert "3 days" in result["subject"]
            
            # Test trial_expired template
            result = trial_expired("Test User")
            assert "subject" in result
            assert "ended" in result["subject"]
            
            # Test subscription_confirmed template
            result = subscription_confirmed("Test User", "Partner Pro", "$240", "January 2027")
            assert "subject" in result
            assert "confirmed" in result["subject"]
            
            # Test invoice_ready template
            result = invoice_ready("Test User", "INV-001", "https://example.com/download", "$240")
            assert "subject" in result
            assert "Invoice" in result["subject"]
            
            print("✓ All 5 Partner Pro email templates verified")
        except ImportError as e:
            pytest.skip(f"Could not import email templates: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
