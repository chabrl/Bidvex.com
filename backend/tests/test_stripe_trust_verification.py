"""
BidVex Stripe Trust Verification Tests
Tests for Stripe payment integration including:
- SetupIntent creation for trust verification
- Trust status retrieval
- SetupIntent confirmation
- Webhook security (signature validation)
- Subscription status
- Fee structure and calculation
- Tax calculation
"""

import pytest
import requests
import os
import hmac
import hashlib
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
TEST_EMAIL = "charbeladmin@bidvex.com"
TEST_PASSWORD = "Admin123!"


class TestAuthentication:
    """Test authentication flow to get access_token"""
    
    def test_login_returns_access_token(self):
        """Login should return access_token field (not token)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        # Verify access_token field exists (not 'token')
        assert "access_token" in data, f"Expected 'access_token' in response, got: {data.keys()}"
        assert len(data["access_token"]) > 0, "access_token should not be empty"
        assert "user" in data, "Response should contain user object"
        
        print(f"✓ Login successful, access_token received: {data['access_token'][:30]}...")


@pytest.fixture
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.text}")
    
    data = response.json()
    return data.get("access_token")


@pytest.fixture
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestSetupIntent:
    """Test POST /api/payments/setup-intent - Creates Stripe SetupIntent for trust verification"""
    
    def test_setup_intent_requires_auth(self):
        """SetupIntent endpoint should require authentication"""
        response = requests.post(f"{BASE_URL}/api/payments/setup-intent")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ SetupIntent requires authentication")
    
    def test_setup_intent_returns_required_fields(self, auth_headers):
        """SetupIntent should return client_secret, setup_intent_id, customer_id"""
        response = requests.post(
            f"{BASE_URL}/api/payments/setup-intent",
            headers=auth_headers,
            json={}
        )
        
        assert response.status_code == 200, f"SetupIntent failed: {response.text}"
        data = response.json()
        
        # Verify all required fields are present
        assert "client_secret" in data, f"Missing client_secret, got: {data.keys()}"
        assert "setup_intent_id" in data, f"Missing setup_intent_id, got: {data.keys()}"
        assert "customer_id" in data, f"Missing customer_id, got: {data.keys()}"
        
        # Validate field formats
        assert data["client_secret"].startswith("seti_"), f"Invalid client_secret format: {data['client_secret'][:20]}"
        assert data["setup_intent_id"].startswith("seti_"), f"Invalid setup_intent_id format: {data['setup_intent_id']}"
        assert data["customer_id"].startswith("cus_"), f"Invalid customer_id format: {data['customer_id']}"
        
        print(f"✓ SetupIntent created successfully:")
        print(f"  - client_secret: {data['client_secret'][:30]}...")
        print(f"  - setup_intent_id: {data['setup_intent_id']}")
        print(f"  - customer_id: {data['customer_id']}")


class TestTrustStatus:
    """Test GET /api/payments/trust-status - Returns user's trust verification status"""
    
    def test_trust_status_requires_auth(self):
        """Trust status endpoint should require authentication"""
        response = requests.get(f"{BASE_URL}/api/payments/trust-status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Trust status requires authentication")
    
    def test_trust_status_returns_required_fields(self, auth_headers):
        """Trust status should return all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/payments/trust-status",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Trust status failed: {response.text}"
        data = response.json()
        
        # Verify all required fields
        required_fields = ["trust_status", "is_verified", "has_payment_method", "can_bid"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Validate types
        assert isinstance(data["trust_status"], str), "trust_status should be string"
        assert isinstance(data["is_verified"], bool), "is_verified should be boolean"
        assert isinstance(data["has_payment_method"], bool), "has_payment_method should be boolean"
        assert isinstance(data["can_bid"], bool), "can_bid should be boolean"
        
        print(f"✓ Trust status retrieved successfully:")
        print(f"  - trust_status: {data['trust_status']}")
        print(f"  - is_verified: {data['is_verified']}")
        print(f"  - has_payment_method: {data['has_payment_method']}")
        print(f"  - can_bid: {data['can_bid']}")


class TestSetupIntentConfirm:
    """Test POST /api/payments/setup-intent/confirm - Confirms SetupIntent and updates trust status"""
    
    def test_confirm_requires_auth(self):
        """Confirm endpoint should require authentication"""
        response = requests.post(f"{BASE_URL}/api/payments/setup-intent/confirm", json={
            "setup_intent_id": "seti_test123"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Setup intent confirm requires authentication")
    
    def test_confirm_requires_setup_intent_id(self, auth_headers):
        """Confirm endpoint should require setup_intent_id"""
        response = requests.post(
            f"{BASE_URL}/api/payments/setup-intent/confirm",
            headers=auth_headers,
            json={}
        )
        
        # Should return 400 for missing setup_intent_id
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print("✓ Setup intent confirm validates required fields")


class TestStripeWebhookSecurity:
    """Test POST /api/webhook/stripe/connect - Webhook security validation"""
    
    def test_webhook_rejects_invalid_signature(self):
        """Webhook should reject requests without valid Stripe signature"""
        # Send request with invalid/missing signature
        response = requests.post(
            f"{BASE_URL}/api/webhook/stripe/connect",
            headers={
                "Content-Type": "application/json",
                "Stripe-Signature": "invalid_signature"
            },
            json={
                "type": "customer.subscription.created",
                "data": {"object": {}}
            }
        )
        
        # Should return 400 for invalid signature
        assert response.status_code == 400, f"Expected 400 for invalid signature, got {response.status_code}"
        print("✓ Webhook rejects invalid Stripe signature")
    
    def test_webhook_rejects_missing_signature(self):
        """Webhook should reject requests without Stripe signature header"""
        response = requests.post(
            f"{BASE_URL}/api/webhook/stripe/connect",
            headers={"Content-Type": "application/json"},
            json={
                "type": "test.event",
                "data": {"object": {}}
            }
        )
        
        # Should return 400 for missing signature
        assert response.status_code == 400, f"Expected 400 for missing signature, got {response.status_code}"
        print("✓ Webhook rejects missing Stripe signature")


class TestSubscriptionStatus:
    """Test GET /api/payments/subscription/status - Returns user subscription details"""
    
    def test_subscription_status_requires_auth(self):
        """Subscription status should require authentication"""
        response = requests.get(f"{BASE_URL}/api/payments/subscription/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Subscription status requires authentication")
    
    def test_subscription_status_returns_tier_info(self, auth_headers):
        """Subscription status should return tier and status info"""
        response = requests.get(
            f"{BASE_URL}/api/payments/subscription/status",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Subscription status failed: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "tier" in data, "Response should contain tier"
        assert "status" in data, "Response should contain status"
        
        print(f"✓ Subscription status retrieved:")
        print(f"  - tier: {data.get('tier')}")
        print(f"  - status: {data.get('status')}")


class TestFeeStructure:
    """Test GET /api/payments/fees/structure - Returns fee structure documentation"""
    
    def test_fee_structure_accessible(self):
        """Fee structure endpoint should be publicly accessible"""
        response = requests.get(f"{BASE_URL}/api/payments/fees/structure")
        
        assert response.status_code == 200, f"Fee structure failed: {response.text}"
        data = response.json()
        
        # Verify structure contains expected data
        assert data is not None, "Fee structure should return data"
        
        print(f"✓ Fee structure retrieved successfully")
        print(f"  Keys: {list(data.keys())[:5]}...")


class TestHybridFeeCalculation:
    """Test GET /api/payments/fees/calculate-hybrid - Calculates fees correctly"""
    
    def test_fee_calculation_with_defaults(self):
        """Fee calculation with default parameters"""
        response = requests.get(
            f"{BASE_URL}/api/payments/fees/calculate-hybrid",
            params={"price": 1000}
        )
        
        assert response.status_code == 200, f"Fee calculation failed: {response.text}"
        data = response.json()
        
        # Verify calculation results are present
        assert "hammer_price" in data or "base_price" in data, f"Missing price field: {data.keys()}"
        
        print(f"✓ Fee calculation for $1000:")
        print(f"  Response: {data}")
    
    def test_fee_calculation_for_vehicle(self):
        """Fee calculation for vehicle category"""
        response = requests.get(
            f"{BASE_URL}/api/payments/fees/calculate-hybrid",
            params={
                "price": 10000,
                "category": "vehicle",
                "buyer_tier": "basic",
                "seller_tier": "basic"
            }
        )
        
        assert response.status_code == 200, f"Vehicle fee calculation failed: {response.text}"
        data = response.json()
        
        print(f"✓ Vehicle fee calculation for $10,000:")
        print(f"  Response: {data}")
    
    def test_fee_calculation_for_premium_tiers(self):
        """Fee calculation for premium subscription tier"""
        response = requests.get(
            f"{BASE_URL}/api/payments/fees/calculate-hybrid",
            params={
                "price": 5000,
                "category": "general",
                "buyer_tier": "premium",
                "seller_tier": "premium"
            }
        )
        
        assert response.status_code == 200, f"Premium fee calculation failed: {response.text}"
        data = response.json()
        
        print(f"✓ Premium tier fee calculation for $5,000:")
        print(f"  Response: {data}")


class TestTaxCalculation:
    """Test POST /api/payments/tax/calculate - Returns tax breakdown"""
    
    def test_tax_calculation_general(self):
        """Tax calculation for general auction"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 1000,
                "category": "general",
                "buyer_tier": "basic",
                "seller_tier": "basic",
                "seller_is_business": False
            }
        )
        
        assert response.status_code == 200, f"Tax calculation failed: {response.text}"
        data = response.json()
        
        # Verify tax calculation fields
        assert "payment_type" in data, "Response should contain payment_type"
        
        print(f"✓ Tax calculation for $1000 general auction:")
        print(f"  Payment type: {data.get('payment_type')}")
        print(f"  Response keys: {list(data.keys())[:5]}...")
    
    def test_tax_calculation_vehicle(self):
        """Tax calculation for vehicle auction"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 25000,
                "category": "vehicle",
                "buyer_tier": "basic"
            }
        )
        
        assert response.status_code == 200, f"Vehicle tax calculation failed: {response.text}"
        data = response.json()
        
        assert data.get("payment_type") == "vehicle", f"Expected vehicle payment type"
        
        print(f"✓ Vehicle tax calculation for $25,000:")
        print(f"  Payment type: {data.get('payment_type')}")
    
    def test_tax_calculation_with_business_seller(self):
        """Tax calculation with business seller (tax registered)"""
        response = requests.post(
            f"{BASE_URL}/api/payments/tax/calculate",
            json={
                "hammer_price": 2000,
                "category": "general",
                "buyer_tier": "basic",
                "seller_tier": "basic",
                "seller_is_business": True,
                "seller_gst_number": "123456789RT0001",
                "seller_qst_number": "1234567890TQ0001"
            }
        )
        
        assert response.status_code == 200, f"Business seller tax calculation failed: {response.text}"
        data = response.json()
        
        print(f"✓ Business seller tax calculation for $2,000:")
        print(f"  Response: {data}")


class TestAdditionalPaymentEndpoints:
    """Test additional payment-related endpoints"""
    
    def test_subscription_tiers_endpoint(self):
        """Test subscription tiers listing"""
        response = requests.get(f"{BASE_URL}/api/payments/subscriptions/tiers")
        
        assert response.status_code == 200, f"Subscription tiers failed: {response.text}"
        data = response.json()
        
        print(f"✓ Subscription tiers retrieved:")
        print(f"  Response: {data}")
    
    def test_processing_fee_info(self):
        """Test processing fee info endpoint"""
        response = requests.get(f"{BASE_URL}/api/payments/fees/processing")
        
        assert response.status_code == 200, f"Processing fee info failed: {response.text}"
        data = response.json()
        
        # Verify Stripe processing fee details
        assert "percentage_rate" in data or "percentage_display" in data
        
        print(f"✓ Processing fee info:")
        print(f"  Response: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
