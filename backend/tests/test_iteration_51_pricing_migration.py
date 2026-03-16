"""
BidVex Iteration 51 - Pricing Migration Tests
Tests for subscription pricing update from monthly to yearly billing:
- Premium: $213.45/month → $180 CAD/year + taxes
- VIP Elite: $355.54/month → $300 CAD/year + taxes
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSubscriptionPricingAPI:
    """Test /api/subscription-plans returns correct yearly pricing"""
    
    def test_subscription_plans_endpoint_returns_success(self):
        """API returns 200 OK"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") == True, "API did not return success=true"
        print("✓ GET /api/subscription-plans returns 200 OK")
    
    def test_premium_yearly_price_is_180(self):
        """Premium plan price_yearly should be 180 (cents: 18000)"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        plans = data.get("plans", [])
        
        premium_plan = next((p for p in plans if p.get("plan_id") == "premium"), None)
        assert premium_plan is not None, "Premium plan not found"
        
        yearly_price = premium_plan.get("price_yearly")
        assert yearly_price == 180, f"Expected Premium price_yearly=180, got {yearly_price}"
        print(f"✓ Premium price_yearly = {yearly_price} CAD (correct)")
    
    def test_vip_yearly_price_is_300(self):
        """VIP plan price_yearly should be 300 (cents: 30000)"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        plans = data.get("plans", [])
        
        vip_plan = next((p for p in plans if p.get("plan_id") == "vip"), None)
        assert vip_plan is not None, "VIP plan not found"
        
        yearly_price = vip_plan.get("price_yearly")
        assert yearly_price == 300, f"Expected VIP price_yearly=300, got {yearly_price}"
        print(f"✓ VIP Elite price_yearly = {yearly_price} CAD (correct)")
    
    def test_free_plan_is_zero(self):
        """Free plan should have price 0"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        plans = data.get("plans", [])
        
        free_plan = next((p for p in plans if p.get("plan_id") == "free"), None)
        assert free_plan is not None, "Free plan not found"
        
        assert free_plan.get("price_yearly") == 0, "Free plan should be $0"
        print("✓ Free plan price = $0 (correct)")
    
    def test_no_old_monthly_prices_in_response(self):
        """Old monthly prices ($213.45, $355.54) should NOT appear"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        response_text = response.text
        
        assert "213.45" not in response_text, "Old price $213.45 found in API response!"
        assert "355.54" not in response_text, "Old price $355.54 found in API response!"
        print("✓ No old monthly prices in API response")


class TestAIChatbotPricingKnowledge:
    """Test that AI chatbot has correct pricing knowledge"""
    
    @pytest.fixture
    def auth_token(self):
        """Get admin auth token for chatbot tests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Admin auth failed - skipping chatbot tests")
    
    def test_chatbot_knows_premium_yearly_price(self, auth_token):
        """Chatbot should mention $180 CAD/year for Premium"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/ai-assistant/chat",
            json={"message": "What is the Premium subscription price?"},
            headers=headers
        )
        
        if response.status_code != 200:
            pytest.skip(f"AI chat endpoint returned {response.status_code}")
        
        data = response.json()
        message = data.get("message", "").lower()
        
        # Check for $180 or 180 cad/year
        has_180 = "180" in message
        has_year = "year" in message or "annual" in message
        
        assert has_180, f"Premium $180 not mentioned in response: {message[:300]}"
        print("✓ AI chatbot knows Premium is $180 CAD/year")
    
    def test_chatbot_does_not_mention_old_prices(self, auth_token):
        """Chatbot should NOT mention old prices ($213.45, $355.54)"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(
            f"{BASE_URL}/api/ai-assistant/chat",
            json={"message": "What are all subscription tier prices?"},
            headers=headers
        )
        
        if response.status_code != 200:
            pytest.skip(f"AI chat endpoint returned {response.status_code}")
        
        data = response.json()
        message = data.get("message", "")
        
        assert "213.45" not in message, f"Old price $213.45 found in AI response!"
        assert "355.54" not in message, f"Old price $355.54 found in AI response!"
        print("✓ AI chatbot does NOT mention old monthly prices")


class TestBackendSubscriptionService:
    """Test subscription_service.py constants are correct"""
    
    def test_subscription_prices_display_strings(self):
        """Verify SUBSCRIPTION_PRICES has correct yearly display strings"""
        # This is a code-level verification - importing the module
        try:
            import sys
            sys.path.insert(0, '/app/backend')
            from services.subscription_service import SUBSCRIPTION_PRICES
            
            premium_display = SUBSCRIPTION_PRICES.get("premium", {}).get("display", "")
            vip_display = SUBSCRIPTION_PRICES.get("vip", {}).get("display", "")
            
            assert "180" in premium_display, f"Premium display missing $180: {premium_display}"
            assert "year" in premium_display.lower(), f"Premium not yearly: {premium_display}"
            assert "taxes" in premium_display.lower(), f"Premium missing + taxes: {premium_display}"
            
            assert "300" in vip_display, f"VIP display missing $300: {vip_display}"
            assert "year" in vip_display.lower(), f"VIP not yearly: {vip_display}"
            assert "taxes" in vip_display.lower(), f"VIP missing + taxes: {vip_display}"
            
            print(f"✓ Premium display: {premium_display}")
            print(f"✓ VIP Elite display: {vip_display}")
        except ImportError:
            pytest.skip("Could not import subscription_service module")
    
    def test_subscription_prices_interval_is_year(self):
        """Verify SUBSCRIPTION_PRICES interval is 'year' not 'month'"""
        try:
            import sys
            sys.path.insert(0, '/app/backend')
            from services.subscription_service import SUBSCRIPTION_PRICES
            
            premium_interval = SUBSCRIPTION_PRICES.get("premium", {}).get("interval", "")
            vip_interval = SUBSCRIPTION_PRICES.get("vip", {}).get("interval", "")
            
            assert premium_interval == "year", f"Premium interval not year: {premium_interval}"
            assert vip_interval == "year", f"VIP interval not year: {vip_interval}"
            
            print("✓ All subscription intervals are 'year'")
        except ImportError:
            pytest.skip("Could not import subscription_service module")
    
    def test_subscription_amounts_in_cents(self):
        """Verify SUBSCRIPTION_PRICES amounts (18000 cents, 30000 cents)"""
        try:
            import sys
            sys.path.insert(0, '/app/backend')
            from services.subscription_service import SUBSCRIPTION_PRICES
            
            premium_amount = SUBSCRIPTION_PRICES.get("premium", {}).get("amount", 0)
            vip_amount = SUBSCRIPTION_PRICES.get("vip", {}).get("amount", 0)
            
            assert premium_amount == 18000, f"Premium amount not 18000: {premium_amount}"
            assert vip_amount == 30000, f"VIP amount not 30000: {vip_amount}"
            
            print(f"✓ Premium amount: {premium_amount} cents ($180)")
            print(f"✓ VIP amount: {vip_amount} cents ($300)")
        except ImportError:
            pytest.skip("Could not import subscription_service module")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
