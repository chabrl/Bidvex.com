"""
Test Suite: Dynamic Pricing Engine and Subscription Plans
Tests the pricing data flow from backend API to frontend display.
Features tested:
- Public subscription plans API returns correct data
- Original prices (for strikethrough display) are included
- Stripe configuration status is exposed
- Admin can update pricing including original prices
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPublicSubscriptionPlansAPI:
    """Tests for GET /api/subscription-plans endpoint - public facing"""
    
    def test_subscription_plans_endpoint_returns_success(self):
        """Test that the subscription plans endpoint returns successfully"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "plans" in data
        print("✅ Subscription plans endpoint returns success")
    
    def test_subscription_plans_contains_three_plans(self):
        """Test that we get free, premium, and vip plans"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        plans = data.get("plans", [])
        
        assert len(plans) == 3, f"Expected 3 plans, got {len(plans)}"
        plan_ids = [p["plan_id"] for p in plans]
        assert "free" in plan_ids, "Free plan missing"
        assert "premium" in plan_ids, "Premium plan missing"
        assert "vip" in plan_ids, "VIP plan missing"
        print("✅ All 3 plans (free, premium, vip) are present")
    
    def test_premium_plan_has_correct_yearly_price(self):
        """Test Premium plan shows $299.99/year current price"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        premium = next((p for p in data["plans"] if p["plan_id"] == "premium"), None)
        
        assert premium is not None, "Premium plan not found"
        assert premium.get("price_yearly") == 299.99, f"Expected $299.99, got {premium.get('price_yearly')}"
        print(f"✅ Premium yearly price: ${premium.get('price_yearly')}")
    
    def test_premium_plan_has_original_price_for_strikethrough(self):
        """Test Premium plan has original_price_yearly for strikethrough display ($599.99)"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        premium = next((p for p in data["plans"] if p["plan_id"] == "premium"), None)
        
        assert premium is not None, "Premium plan not found"
        original_yearly = premium.get("original_price_yearly")
        assert original_yearly == 599.99, f"Expected original price $599.99, got {original_yearly}"
        print(f"✅ Premium original yearly price (strikethrough): ${original_yearly}")
    
    def test_vip_plan_has_correct_yearly_price(self):
        """Test VIP plan shows $599/year current price"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        vip = next((p for p in data["plans"] if p["plan_id"] == "vip"), None)
        
        assert vip is not None, "VIP plan not found"
        assert vip.get("price_yearly") == 599, f"Expected $599, got {vip.get('price_yearly')}"
        print(f"✅ VIP yearly price: ${vip.get('price_yearly')}")
    
    def test_vip_plan_has_original_price_for_strikethrough(self):
        """Test VIP plan has original_price_yearly for strikethrough display ($1999.99)"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        vip = next((p for p in data["plans"] if p["plan_id"] == "vip"), None)
        
        assert vip is not None, "VIP plan not found"
        original_yearly = vip.get("original_price_yearly")
        assert original_yearly == 1999.99, f"Expected original price $1999.99, got {original_yearly}"
        print(f"✅ VIP original yearly price (strikethrough): ${original_yearly}")
    
    def test_discount_percentage_calculation_premium(self):
        """Test that Premium discount calculates to 50% OFF"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        premium = next((p for p in data["plans"] if p["plan_id"] == "premium"), None)
        
        current_price = premium.get("price_yearly", 0)
        original_price = premium.get("original_price_yearly", 0)
        
        if original_price > current_price:
            discount_percent = round((1 - current_price / original_price) * 100)
            assert discount_percent == 50, f"Expected 50% discount, got {discount_percent}%"
            print(f"✅ Premium discount: {discount_percent}% OFF")
        else:
            pytest.fail("Original price not greater than current price")
    
    def test_discount_percentage_calculation_vip(self):
        """Test that VIP discount calculates to approximately 70% OFF"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        vip = next((p for p in data["plans"] if p["plan_id"] == "vip"), None)
        
        current_price = vip.get("price_yearly", 0)
        original_price = vip.get("original_price_yearly", 0)
        
        if original_price > current_price:
            discount_percent = round((1 - current_price / original_price) * 100)
            assert discount_percent == 70, f"Expected ~70% discount, got {discount_percent}%"
            print(f"✅ VIP discount: {discount_percent}% OFF")
        else:
            pytest.fail("Original price not greater than current price")
    
    def test_stripe_price_id_fields_exposed(self):
        """Test that stripe_price_id fields are exposed for Stripe configuration status"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        premium = next((p for p in data["plans"] if p["plan_id"] == "premium"), None)
        
        assert "stripe_price_id_monthly" in premium, "stripe_price_id_monthly field missing"
        assert "stripe_price_id_yearly" in premium, "stripe_price_id_yearly field missing"
        print(f"✅ Stripe price ID fields present - Monthly: {premium.get('stripe_price_id_monthly')}, Yearly: {premium.get('stripe_price_id_yearly')}")
    
    def test_savings_calculation_premium(self):
        """Test savings badge: Premium saves $300 (599.99 - 299.99)"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        premium = next((p for p in data["plans"] if p["plan_id"] == "premium"), None)
        
        current_price = premium.get("price_yearly", 0)
        original_price = premium.get("original_price_yearly", 0)
        savings = original_price - current_price
        
        assert savings == 300, f"Expected savings $300, got ${savings}"
        print(f"✅ Premium savings: Save ${savings}")
    
    def test_savings_calculation_vip(self):
        """Test savings badge: VIP saves $1400.99 (1999.99 - 599)"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        vip = next((p for p in data["plans"] if p["plan_id"] == "vip"), None)
        
        current_price = vip.get("price_yearly", 0)
        original_price = vip.get("original_price_yearly", 0)
        savings = original_price - current_price
        
        expected_savings = 1400.99
        assert abs(savings - expected_savings) < 0.01, f"Expected savings ~${expected_savings}, got ${savings}"
        print(f"✅ VIP savings: Save ${savings}")
    
    def test_monthly_prices_also_have_original_prices(self):
        """Test that monthly original prices are also available"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        premium = next((p for p in data["plans"] if p["plan_id"] == "premium"), None)
        vip = next((p for p in data["plans"] if p["plan_id"] == "vip"), None)
        
        # Check Premium monthly
        assert "original_price_monthly" in premium, "original_price_monthly missing for Premium"
        assert premium.get("original_price_monthly") > 0, "Premium original_price_monthly should be > 0"
        
        # Check VIP monthly
        assert "original_price_monthly" in vip, "original_price_monthly missing for VIP"
        assert vip.get("original_price_monthly") > 0, "VIP original_price_monthly should be > 0"
        
        print(f"✅ Monthly original prices - Premium: ${premium.get('original_price_monthly')}, VIP: ${vip.get('original_price_monthly')}")
    
    def test_free_plan_has_zero_prices(self):
        """Test that Free plan has $0 prices"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        data = response.json()
        free = next((p for p in data["plans"] if p["plan_id"] == "free"), None)
        
        assert free is not None, "Free plan not found"
        assert free.get("price_monthly") == 0, "Free monthly price should be 0"
        assert free.get("price_yearly") == 0, "Free yearly price should be 0"
        assert free.get("original_price_monthly") == 0, "Free original monthly price should be 0"
        assert free.get("original_price_yearly") == 0, "Free original yearly price should be 0"
        print("✅ Free plan has $0 for all prices")


class TestAdminPricingEndpoints:
    """Tests for admin pricing management endpoints"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "charbeladmin@bidvex.com",
            "password": "Admin123!"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin login failed - skipping admin tests")
    
    def test_admin_subscription_plans_endpoint(self, admin_token):
        """Test admin can access subscription plans"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/subscription-plans", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        print("✅ Admin can access subscription plans endpoint")
    
    def test_admin_plans_include_original_price_fields(self, admin_token):
        """Test admin plans include original_price fields for editing"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/subscription-plans", headers=headers)
        
        data = response.json()
        plans = data.get("plans", [])
        
        for plan in plans:
            if plan["plan_id"] != "free":
                assert "original_price_monthly" in plan, f"original_price_monthly missing for {plan['plan_id']}"
                assert "original_price_yearly" in plan, f"original_price_yearly missing for {plan['plan_id']}"
        
        print("✅ Admin plans include original price fields for editing")
    
    def test_pricing_changelog_endpoint(self, admin_token):
        """Test admin can access pricing changelog"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/subscription-plans/changelog", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "changelog" in data
        print(f"✅ Pricing changelog accessible, {len(data.get('changelog', []))} entries")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
