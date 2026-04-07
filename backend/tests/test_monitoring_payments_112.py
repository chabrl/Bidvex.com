"""
BidVex Iteration 112 - Monitoring System & Payments Refactoring Tests
Tests:
1. Monitoring API endpoints (admin-only)
2. Payments refactoring (no regressions)
3. Fee calculation APIs
4. Tax calculation APIs
5. Subscription tiers API
6. Email credits balance API
7. Deposit status API
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestMonitoringAPIs:
    """Test the new monitoring/alerting system endpoints (admin-only)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.admin_token = token
        else:
            pytest.skip(f"Admin login failed: {login_response.status_code}")
    
    def test_monitoring_dashboard_admin_access(self):
        """GET /api/monitoring/dashboard - admin should get dashboard data"""
        response = self.session.get(f"{BASE_URL}/api/monitoring/dashboard")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "system_status" in data, "Missing system_status"
        assert "errors" in data, "Missing errors"
        assert "webhooks" in data, "Missing webhooks"
        assert "recent_alerts" in data, "Missing recent_alerts"
        assert "recent_webhook_failures" in data, "Missing recent_webhook_failures"
        assert "recent_500s" in data, "Missing recent_500s"
        
        # Verify errors structure
        assert "last_24h" in data["errors"]
        assert "last_7d" in data["errors"]
        assert "unresolved" in data["errors"]
        
        # Verify webhooks structure
        assert "total_24h" in data["webhooks"]
        assert "failures_24h" in data["webhooks"]
        assert "stripe_failures_24h" in data["webhooks"]
        assert "success_rate" in data["webhooks"]
        
        print(f"✓ Monitoring dashboard: system_status={data['system_status']}, errors_24h={data['errors']['last_24h']}")
    
    def test_monitoring_health_check_admin_access(self):
        """GET /api/monitoring/health-check - admin should get health check data"""
        response = self.session.get(f"{BASE_URL}/api/monitoring/health-check")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "overall" in data, "Missing overall status"
        assert "checks" in data, "Missing checks"
        assert "timestamp" in data, "Missing timestamp"
        
        # Verify checks structure
        checks = data["checks"]
        assert "mongodb" in checks, "Missing mongodb check"
        assert "stripe" in checks, "Missing stripe check"
        assert "collections" in checks, "Missing collections check"
        
        # Verify mongodb status
        assert "status" in checks["mongodb"]
        
        print(f"✓ Health check: overall={data['overall']}, mongodb={checks['mongodb']['status']}")
    
    def test_monitoring_errors_endpoint(self):
        """GET /api/monitoring/errors - admin should get error log"""
        response = self.session.get(f"{BASE_URL}/api/monitoring/errors")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total" in data, "Missing total count"
        assert "events" in data, "Missing events list"
        assert isinstance(data["events"], list), "Events should be a list"
        
        print(f"✓ Error log: total={data['total']} events")
    
    def test_monitoring_errors_with_filters(self):
        """GET /api/monitoring/errors with query filters"""
        response = self.session.get(f"{BASE_URL}/api/monitoring/errors?severity=error&limit=10")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total" in data
        assert "events" in data
        assert len(data["events"]) <= 10, "Limit not respected"
        
        print(f"✓ Error log with filters: {len(data['events'])} events returned")
    
    def test_monitoring_webhooks_endpoint(self):
        """GET /api/monitoring/webhooks - admin should get webhook log"""
        response = self.session.get(f"{BASE_URL}/api/monitoring/webhooks")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total" in data, "Missing total count"
        assert "events" in data, "Missing events list"
        assert isinstance(data["events"], list), "Events should be a list"
        
        print(f"✓ Webhook log: total={data['total']} events")
    
    def test_monitoring_webhooks_with_filters(self):
        """GET /api/monitoring/webhooks with query filters"""
        response = self.session.get(f"{BASE_URL}/api/monitoring/webhooks?provider=stripe&limit=10")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "total" in data
        assert "events" in data
        
        print(f"✓ Webhook log with filters: {len(data['events'])} events returned")


class TestMonitoringUnauthorized:
    """Test that monitoring endpoints require admin access"""
    
    def test_monitoring_dashboard_requires_auth(self):
        """GET /api/monitoring/dashboard without auth should fail"""
        response = requests.get(f"{BASE_URL}/api/monitoring/dashboard")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Monitoring dashboard requires authentication")
    
    def test_monitoring_health_check_requires_auth(self):
        """GET /api/monitoring/health-check without auth should fail"""
        response = requests.get(f"{BASE_URL}/api/monitoring/health-check")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Health check requires authentication")


class TestPaymentsFeeCalculation:
    """Test fee calculation APIs (payments.py refactoring - no regressions)"""
    
    def test_fee_calculate_hybrid_vehicle(self):
        """GET /api/payments/fees/calculate-hybrid for vehicle category"""
        response = requests.get(
            f"{BASE_URL}/api/payments/fees/calculate-hybrid",
            params={"price": 10000, "category": "vehicle", "buyer_tier": "basic"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "hammer_price" in data, "Missing hammer_price"
        assert "buyer_premium" in data or "buyer" in data, "Missing buyer premium info"
        
        print(f"✓ Fee calculation (vehicle): hammer_price={data.get('hammer_price', 'N/A')}")
    
    def test_fee_calculate_hybrid_general(self):
        """GET /api/payments/fees/calculate-hybrid for general category"""
        response = requests.get(
            f"{BASE_URL}/api/payments/fees/calculate-hybrid",
            params={"price": 5000, "category": "general", "buyer_tier": "premium", "seller_tier": "basic"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "hammer_price" in data, "Missing hammer_price"
        
        print(f"✓ Fee calculation (general): hammer_price={data.get('hammer_price', 'N/A')}")
    
    def test_fee_structure_endpoint(self):
        """GET /api/payments/fees/structure - get fee documentation"""
        response = requests.get(f"{BASE_URL}/api/payments/fees/structure")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should return fee structure documentation
        assert isinstance(data, dict), "Response should be a dict"
        
        print(f"✓ Fee structure endpoint working")


class TestPaymentsTaxCalculation:
    """Test tax calculation APIs (payments_fees.py sub-router)"""
    
    def test_tax_vehicle_endpoint(self):
        """GET /api/payments/tax/vehicle - vehicle tax calculation"""
        response = requests.get(
            f"{BASE_URL}/api/payments/tax/vehicle",
            params={"price": 25000, "buyer_tier": "premium"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "auction_type" in data, "Missing auction_type"
        assert data["auction_type"] == "vehicle", f"Expected vehicle, got {data['auction_type']}"
        
        print(f"✓ Tax calculation (vehicle): {data.get('auction_type')}")
    
    def test_tax_general_endpoint(self):
        """GET /api/payments/tax/general - general tax calculation"""
        response = requests.get(
            f"{BASE_URL}/api/payments/tax/general",
            params={"price": 1000, "buyer_tier": "basic", "seller_tier": "basic", "seller_is_business": False}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "auction_type" in data, "Missing auction_type"
        assert data["auction_type"] == "general", f"Expected general, got {data['auction_type']}"
        
        print(f"✓ Tax calculation (general): {data.get('auction_type')}")
    
    def test_tax_rates_endpoint(self):
        """GET /api/payments/tax/rates - get Quebec tax rates"""
        response = requests.get(f"{BASE_URL}/api/payments/tax/rates")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "gst" in data, "Missing GST info"
        assert "qst" in data, "Missing QST info"
        assert "combined" in data, "Missing combined rate"
        
        # Verify Quebec rates
        assert data["gst"]["rate"] == 0.05, f"GST rate should be 5%, got {data['gst']['rate']}"
        assert data["qst"]["rate"] == 0.09975, f"QST rate should be 9.975%, got {data['qst']['rate']}"
        
        print(f"✓ Tax rates: GST={data['gst']['rate_display']}, QST={data['qst']['rate_display']}")


class TestPaymentsPricingConfig:
    """Test pricing config API (payments_promotions.py sub-router)"""
    
    def test_pricing_config_endpoint(self):
        """GET /api/payments/pricing-config - public pricing info"""
        response = requests.get(f"{BASE_URL}/api/payments/pricing-config")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "commissions" in data, "Missing commissions"
        assert "buyer_premiums" in data, "Missing buyer_premiums"
        assert "seller_commissions" in data, "Missing seller_commissions"
        assert "subscriptions" in data, "Missing subscriptions"
        assert "deposit" in data, "Missing deposit info"
        
        # Verify deposit threshold
        assert "threshold_cad" in data["deposit"], "Missing deposit threshold"
        assert "amount_dollars" in data["deposit"], "Missing deposit amount"
        
        print(f"✓ Pricing config: deposit threshold=${data['deposit']['threshold_cad']}, amount=${data['deposit']['amount_dollars']}")


class TestPaymentsSubscriptionTiers:
    """Test subscription tiers API"""
    
    def test_subscription_tiers_endpoint(self):
        """GET /api/payments/subscriptions/tiers - get all tiers"""
        response = requests.get(f"{BASE_URL}/api/payments/subscriptions/tiers")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should return tier information
        assert isinstance(data, (dict, list)), "Response should be dict or list"
        
        print(f"✓ Subscription tiers endpoint working")


class TestPaymentsEmailCredits:
    """Test email credits balance API (requires auth)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Admin login failed: {login_response.status_code}")
    
    def test_email_credits_balance(self):
        """GET /api/payments/email-credits/balance - get user's email credits"""
        response = self.session.get(f"{BASE_URL}/api/payments/email-credits/balance")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "credits" in data, "Missing credits field"
        assert isinstance(data["credits"], (int, float)), "Credits should be numeric"
        
        print(f"✓ Email credits balance: {data['credits']} credits")


class TestDepositsAPI:
    """Test deposit status API (requires auth)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login as admin before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Admin login failed: {login_response.status_code}")
    
    def test_deposit_status_nonexistent_listing(self):
        """GET /api/deposits/status/{listing_id} - test with fake listing ID"""
        fake_listing_id = "nonexistent-listing-12345"
        response = self.session.get(f"{BASE_URL}/api/deposits/status/{fake_listing_id}")
        
        # Should return 200 with no deposit or 404
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            # Should indicate no deposit required or no deposit found
            print(f"✓ Deposit status (nonexistent): {data}")
        else:
            print(f"✓ Deposit status returns 404 for nonexistent listing")


class TestProcessingFeeInfo:
    """Test processing fee info endpoint"""
    
    def test_processing_fee_info(self):
        """GET /api/payments/fees/processing - get Stripe fee info"""
        response = requests.get(f"{BASE_URL}/api/payments/fees/processing")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "percentage_rate" in data, "Missing percentage_rate"
        assert "fixed_fee" in data, "Missing fixed_fee"
        assert "description" in data, "Missing description"
        
        # Verify Stripe standard rates
        assert data["percentage_rate"] == 0.029, f"Expected 2.9%, got {data['percentage_rate']}"
        assert data["fixed_fee"] == 0.30, f"Expected $0.30, got {data['fixed_fee']}"
        
        print(f"✓ Processing fee: {data['percentage_display']} + {data['fixed_fee_display']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
