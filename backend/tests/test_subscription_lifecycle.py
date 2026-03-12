"""
Test Subscription Lifecycle Features - BidVex
Tests: GET /api/subscriptions/status, POST /api/subscriptions/cancel, POST /api/subscriptions/create
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_EMAIL = "charbeladmin@bidvex.com"
TEST_PASSWORD = "Admin123!"

class TestAuthentication:
    """Authentication tests - login to get token for authenticated requests"""
    
    def test_login_returns_access_token(self):
        """Test login returns access_token field"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "Response missing access_token"
        assert len(data["access_token"]) > 0, "access_token is empty"
        print(f"✅ Login successful, got access_token")

@pytest.fixture(scope="class")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping authenticated tests")

@pytest.fixture
def authenticated_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestSubscriptionStatus:
    """Test GET /api/subscriptions/status endpoint"""
    
    def test_subscription_status_requires_auth(self):
        """Test that subscription status requires authentication"""
        response = requests.get(f"{BASE_URL}/api/subscriptions/status")
        assert response.status_code == 401, "Endpoint should require auth"
        print("✅ Subscription status requires authentication")
    
    def test_subscription_status_returns_required_fields(self, authenticated_client):
        """Test subscription status returns tier, status, cancel_at_period_end, dates"""
        response = authenticated_client.get(f"{BASE_URL}/api/subscriptions/status")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Required fields from the implementation
        assert "tier" in data, "Response missing tier field"
        assert "status" in data, "Response missing status field"
        assert "cancel_at_period_end" in data, "Response missing cancel_at_period_end field"
        assert "start_date" in data, "Response missing start_date field"
        assert "end_date" in data, "Response missing end_date field"
        assert "stripe_subscription_id" in data, "Response missing stripe_subscription_id field"
        assert "has_payment_method" in data, "Response missing has_payment_method field"
        
        print(f"✅ Subscription status returns all required fields")
        print(f"   tier: {data.get('tier')}")
        print(f"   status: {data.get('status')}")
        print(f"   cancel_at_period_end: {data.get('cancel_at_period_end')}")
        print(f"   stripe_subscription_id: {data.get('stripe_subscription_id')}")
        print(f"   has_payment_method: {data.get('has_payment_method')}")
    
    def test_subscription_status_tier_valid_value(self, authenticated_client):
        """Test subscription tier is one of free, premium, vip"""
        response = authenticated_client.get(f"{BASE_URL}/api/subscriptions/status")
        assert response.status_code == 200
        data = response.json()
        
        tier = data.get("tier", "")
        assert tier in ["free", "premium", "vip"], f"Invalid tier value: {tier}"
        print(f"✅ Subscription tier is valid: {tier}")


class TestSubscriptionCreate:
    """Test POST /api/subscriptions/create endpoint"""
    
    def test_subscription_create_requires_auth(self):
        """Test that subscription create requires authentication"""
        response = requests.post(f"{BASE_URL}/api/subscriptions/create", json={"plan_id": "premium"})
        assert response.status_code == 401, "Endpoint should require auth"
        print("✅ Subscription create requires authentication")
    
    def test_subscription_create_invalid_plan(self, authenticated_client):
        """Test subscription create rejects invalid plan_id"""
        response = authenticated_client.post(f"{BASE_URL}/api/subscriptions/create", json={"plan_id": "invalid"})
        assert response.status_code == 400, f"Should reject invalid plan: {response.text}"
        print("✅ Subscription create rejects invalid plan_id")
    
    def test_subscription_create_requires_plan_id(self, authenticated_client):
        """Test subscription create requires plan_id"""
        response = authenticated_client.post(f"{BASE_URL}/api/subscriptions/create", json={})
        assert response.status_code == 400, f"Should require plan_id: {response.text}"
        print("✅ Subscription create requires plan_id")
    
    def test_subscription_create_premium_plan_structure(self, authenticated_client):
        """Test subscription create returns proper response structure (may fail due to IP restrictions)"""
        response = authenticated_client.post(f"{BASE_URL}/api/subscriptions/create", json={"plan_id": "premium"})
        
        # May get 400 due to Stripe IP restrictions, but should be a proper error not 500
        assert response.status_code in [200, 400], f"Unexpected status code: {response.status_code}, {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "subscription_id" in data or "tier" in data
            print(f"✅ Subscription create returned success response")
        else:
            data = response.json()
            # Should be a proper error message, not a 500 crash
            assert "detail" in data, "Error response should have detail"
            print(f"✅ Subscription create returned proper error (expected due to Stripe IP restriction): {data.get('detail')}")


class TestSubscriptionCancel:
    """Test POST /api/subscriptions/cancel endpoint"""
    
    def test_subscription_cancel_requires_auth(self):
        """Test that subscription cancel requires authentication"""
        response = requests.post(f"{BASE_URL}/api/subscriptions/cancel", json={})
        assert response.status_code == 401, "Endpoint should require auth"
        print("✅ Subscription cancel requires authentication")
    
    def test_subscription_cancel_structure(self, authenticated_client):
        """Test subscription cancel returns proper response structure"""
        response = authenticated_client.post(f"{BASE_URL}/api/subscriptions/cancel")
        
        # May get 400 if no subscription or Stripe IP restrictions
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}, {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "success" in data, "Response missing success field"
            assert "message" in data, "Response missing message field"
            assert "access_until" in data, "Response missing access_until date"
            print(f"✅ Subscription cancel response structure correct")
            print(f"   message: {data.get('message')}")
            print(f"   access_until: {data.get('access_until')}")
        else:
            data = response.json()
            assert "detail" in data
            print(f"✅ Subscription cancel returned proper error: {data.get('detail')}")


class TestSubscriptionPlans:
    """Test GET /api/subscription-plans endpoint (public)"""
    
    def test_subscription_plans_returns_data(self):
        """Test subscription plans endpoint returns plans"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "success" in data or "plans" in data, "Response missing expected fields"
        if "plans" in data:
            plans = data["plans"]
            assert isinstance(plans, list), "Plans should be a list"
            assert len(plans) > 0, "Should have at least one plan"
            
            # Check plan structure
            for plan in plans:
                assert "plan_id" in plan, "Plan missing plan_id"
                assert "name" in plan, "Plan missing name"
            
            plan_ids = [p.get("plan_id") for p in plans]
            print(f"✅ Subscription plans returned: {plan_ids}")


class TestUserProfileSubscriptionData:
    """Test that user profile includes subscription data"""
    
    def test_auth_me_includes_subscription_tier(self, authenticated_client):
        """Test /api/auth/me includes subscription_tier"""
        response = authenticated_client.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "subscription_tier" in data, "User profile missing subscription_tier"
        assert "subscription_status" in data, "User profile missing subscription_status"
        assert "has_payment_method" in data, "User profile missing has_payment_method"
        
        print(f"✅ User profile includes subscription data")
        print(f"   subscription_tier: {data.get('subscription_tier')}")
        print(f"   subscription_status: {data.get('subscription_status')}")
        print(f"   has_payment_method: {data.get('has_payment_method')}")
