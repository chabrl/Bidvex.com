"""
Backend API Tests for Subscription Pricing & Coupon Management System
Tests: subscription plans, admin pricing, coupon CRUD, coupon validation
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://seller-verify-7.preview.emergentagent.com').rstrip('/')

# Admin credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestPublicSubscriptionPlans:
    """Test public subscription plan endpoints - no auth required"""

    def test_get_subscription_plans_returns_success(self):
        """GET /api/subscription-plans should return success"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Response should indicate success"
        assert "plans" in data, "Response should contain plans array"
        print(f"✓ Public subscription plans returned {len(data['plans'])} plans")

    def test_subscription_plans_contains_three_plans(self):
        """GET /api/subscription-plans should return free, premium, vip plans"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200
        
        data = response.json()
        plans = data.get("plans", [])
        plan_ids = [p.get("plan_id") for p in plans]
        
        assert "free" in plan_ids, "Should contain 'free' plan"
        assert "premium" in plan_ids, "Should contain 'premium' plan"
        assert "vip" in plan_ids, "Should contain 'vip' plan"
        print(f"✓ Found all 3 plans: {plan_ids}")

    def test_plans_have_dynamic_pricing(self):
        """Plans should have pricing fields"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200
        
        data = response.json()
        plans = data.get("plans", [])
        
        for plan in plans:
            assert "price_monthly" in plan, f"Plan {plan.get('plan_id')} missing price_monthly"
            assert "price_yearly" in plan, f"Plan {plan.get('plan_id')} missing price_yearly"
            assert "features" in plan, f"Plan {plan.get('plan_id')} missing features"
            
            # Verify pricing values are numeric
            assert isinstance(plan.get("price_monthly"), (int, float)), "price_monthly should be numeric"
            assert isinstance(plan.get("price_yearly"), (int, float)), "price_yearly should be numeric"
            
            print(f"✓ Plan '{plan['plan_id']}': ${plan['price_monthly']}/mo, ${plan['price_yearly']}/yr")

    def test_premium_and_vip_have_discounts(self):
        """Premium and VIP plans should have fee discounts"""
        response = requests.get(f"{BASE_URL}/api/subscription-plans")
        assert response.status_code == 200
        
        data = response.json()
        plans = {p.get("plan_id"): p for p in data.get("plans", [])}
        
        # Free plan should have 0 discounts
        free = plans.get("free", {})
        assert free.get("buyer_premium_discount", 0) == 0, "Free plan should have 0 buyer discount"
        
        # Premium and VIP should have discounts > 0
        premium = plans.get("premium", {})
        vip = plans.get("vip", {})
        
        assert premium.get("buyer_premium_discount", 0) > 0, "Premium should have buyer discount"
        assert vip.get("buyer_premium_discount", 0) > 0, "VIP should have buyer discount"
        assert vip.get("buyer_premium_discount", 0) >= premium.get("buyer_premium_discount", 0), \
            "VIP discount should be >= Premium discount"
        
        print(f"✓ Discounts verified: Free=0%, Premium={premium.get('buyer_premium_discount')}%, VIP={vip.get('buyer_premium_discount')}%")


class TestAdminSubscriptionPlans:
    """Test admin subscription plan endpoints - requires admin auth"""

    @pytest.fixture
    def admin_token(self):
        """Login as admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
        
        data = response.json()
        return data.get("access_token")

    def test_admin_get_plans_requires_auth(self):
        """GET /api/admin/subscription-plans should require authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/subscription-plans")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Admin endpoint correctly requires authentication")

    def test_admin_get_plans_success(self, admin_token):
        """GET /api/admin/subscription-plans with admin auth should return plans"""
        response = requests.get(
            f"{BASE_URL}/api/admin/subscription-plans",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert "plans" in data
        
        # Admin endpoint should return more details
        plans = data.get("plans", [])
        assert len(plans) >= 3, "Should have at least 3 plans"
        print(f"✓ Admin got {len(plans)} plans with full details")

    def test_admin_update_plan_pricing(self, admin_token):
        """PUT /api/admin/subscription-plans/{plan_id} should update pricing"""
        # First get current premium plan pricing
        get_response = requests.get(
            f"{BASE_URL}/api/admin/subscription-plans",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert get_response.status_code == 200
        
        plans = get_response.json().get("plans", [])
        premium = next((p for p in plans if p.get("plan_id") == "premium"), None)
        if not premium:
            pytest.skip("Premium plan not found")
        
        original_monthly = premium.get("price_monthly", 29.99)
        
        # Update with same value (to avoid breaking pricing)
        update_response = requests.put(
            f"{BASE_URL}/api/admin/subscription-plans/premium",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "price_monthly": original_monthly,
                "reason": "Automated test - no change"
            }
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        data = update_response.json()
        assert data.get("success") == True
        assert data.get("plan", {}).get("price_monthly") == original_monthly
        print(f"✓ Plan update endpoint working (verified with price: ${original_monthly})")

    def test_admin_get_changelog(self, admin_token):
        """GET /api/admin/subscription-plans/changelog should return change history"""
        response = requests.get(
            f"{BASE_URL}/api/admin/subscription-plans/changelog?limit=10",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert "changelog" in data
        
        changelog = data.get("changelog", [])
        print(f"✓ Changelog returned {len(changelog)} entries")


class TestCouponValidation:
    """Test public coupon validation endpoint"""

    def test_validate_coupon_invalid_code(self):
        """POST /api/validate-coupon with invalid code should return invalid"""
        response = requests.post(f"{BASE_URL}/api/validate-coupon", json={
            "code": "INVALIDCODE123",
            "plan_id": "premium",
            "billing_period": "yearly"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("valid") == False, "Invalid coupon should return valid=False"
        assert "message" in data, "Should include error message"
        print(f"✓ Invalid coupon correctly rejected: {data.get('message')}")

    def test_validate_coupon_empty_code(self):
        """POST /api/validate-coupon without code should return 400"""
        response = requests.post(f"{BASE_URL}/api/validate-coupon", json={
            "plan_id": "premium",
            "billing_period": "yearly"
        })
        # Empty code should return 400
        assert response.status_code == 400, f"Expected 400 for empty code, got {response.status_code}"
        print("✓ Empty coupon code correctly rejected with 400")

    def test_validate_coupon_launch20(self):
        """POST /api/validate-coupon with LAUNCH20 should calculate discount"""
        response = requests.post(f"{BASE_URL}/api/validate-coupon", json={
            "code": "LAUNCH20",
            "plan_id": "premium",
            "billing_period": "yearly"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # The coupon may or may not exist - check the structure
        if data.get("valid"):
            assert "discount_amount" in data, "Valid coupon should have discount_amount"
            assert "new_total" in data, "Valid coupon should have new_total"
            assert "original_total" in data, "Valid coupon should have original_total"
            assert data.get("new_total") < data.get("original_total"), "Discount should reduce total"
            print(f"✓ LAUNCH20 valid: ${data.get('original_total')} - ${data.get('discount_amount')} = ${data.get('new_total')}")
        else:
            print(f"⚠ LAUNCH20 not found or inactive: {data.get('message')}")


class TestAdminCoupons:
    """Test admin coupon CRUD operations"""

    @pytest.fixture
    def admin_token(self):
        """Login as admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
        
        data = response.json()
        return data.get("access_token")

    def test_admin_get_coupons_requires_auth(self):
        """GET /api/admin/coupons should require authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/coupons")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Admin coupons endpoint correctly requires authentication")

    def test_admin_get_coupons_success(self, admin_token):
        """GET /api/admin/coupons with admin auth should return coupons"""
        response = requests.get(
            f"{BASE_URL}/api/admin/coupons",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert "coupons" in data
        
        coupons = data.get("coupons", [])
        print(f"✓ Admin got {len(coupons)} coupons")
        
        # Check LAUNCH20 exists
        launch20 = next((c for c in coupons if c.get("code") == "LAUNCH20"), None)
        if launch20:
            print(f"  Found LAUNCH20: {launch20.get('discount_type')}={launch20.get('value')}, usage={launch20.get('usage_count')}")

    def test_admin_create_coupon(self, admin_token):
        """POST /api/admin/coupons should create a new coupon"""
        # Create a test coupon with unique code
        import time
        test_code = f"TEST{int(time.time()) % 10000}"
        
        response = requests.post(
            f"{BASE_URL}/api/admin/coupons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "code": test_code,
                "discount_type": "percentage",
                "value": 15,
                "usage_limit": 5,
                "min_purchase_amount": 0,
                "applicable_plans": ["premium", "vip"]
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True
        assert data.get("coupon", {}).get("code") == test_code.upper()
        
        coupon_id = data.get("coupon", {}).get("id")
        print(f"✓ Created coupon '{test_code}' with id: {coupon_id}")
        
        return coupon_id

    def test_admin_update_coupon(self, admin_token):
        """PUT /api/admin/coupons/{coupon_id} should update coupon"""
        # First get existing coupons
        get_response = requests.get(
            f"{BASE_URL}/api/admin/coupons?include_inactive=true",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert get_response.status_code == 200
        
        coupons = get_response.json().get("coupons", [])
        if not coupons:
            pytest.skip("No coupons to update")
        
        # Find a test coupon or use the first one
        test_coupon = next((c for c in coupons if "TEST" in c.get("code", "")), coupons[0])
        coupon_id = test_coupon.get("id")
        
        # Update usage_limit
        update_response = requests.put(
            f"{BASE_URL}/api/admin/coupons/{coupon_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "usage_limit": 100
            }
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        data = update_response.json()
        assert data.get("success") == True
        print(f"✓ Updated coupon {test_coupon.get('code')} usage_limit to 100")

    def test_admin_delete_coupon(self, admin_token):
        """DELETE /api/admin/coupons/{coupon_id} should deactivate coupon"""
        # Create a temp coupon to delete
        import time
        temp_code = f"DEL{int(time.time()) % 10000}"
        
        create_response = requests.post(
            f"{BASE_URL}/api/admin/coupons",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "code": temp_code,
                "discount_type": "fixed",
                "value": 5,
                "applicable_plans": ["premium"]
            }
        )
        
        if create_response.status_code != 200:
            pytest.skip("Could not create temp coupon for delete test")
        
        coupon_id = create_response.json().get("coupon", {}).get("id")
        
        # Delete (deactivate) the coupon
        delete_response = requests.delete(
            f"{BASE_URL}/api/admin/coupons/{coupon_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        
        data = delete_response.json()
        assert data.get("success") == True
        print(f"✓ Deactivated coupon '{temp_code}'")


class TestCouponIntegration:
    """Test coupon validation with different scenarios"""

    @pytest.fixture
    def admin_token(self):
        """Login as admin and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code}")
        
        return response.json().get("access_token")

    def test_coupon_not_valid_for_free_plan(self, admin_token):
        """Coupons should not be valid for free plan"""
        # First check if LAUNCH20 exists
        get_response = requests.get(
            f"{BASE_URL}/api/admin/coupons",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        coupons = get_response.json().get("coupons", [])
        launch20 = next((c for c in coupons if c.get("code") == "LAUNCH20" and c.get("is_active")), None)
        
        if not launch20:
            pytest.skip("LAUNCH20 coupon not found or inactive")
        
        # Try to validate for free plan (should fail)
        response = requests.post(f"{BASE_URL}/api/validate-coupon", json={
            "code": "LAUNCH20",
            "plan_id": "free",
            "billing_period": "yearly"
        })
        
        data = response.json()
        # Free plan has $0 price, coupon should be invalid for it
        assert data.get("valid") == False, "Coupon should not be valid for free plan"
        print(f"✓ Coupon correctly invalid for free plan: {data.get('message')}")

    def test_coupon_monthly_vs_yearly_pricing(self):
        """Coupon discount should differ based on billing period"""
        # Test for premium plan (if LAUNCH20 exists)
        monthly_response = requests.post(f"{BASE_URL}/api/validate-coupon", json={
            "code": "LAUNCH20",
            "plan_id": "premium",
            "billing_period": "monthly"
        })
        
        yearly_response = requests.post(f"{BASE_URL}/api/validate-coupon", json={
            "code": "LAUNCH20",
            "plan_id": "premium",
            "billing_period": "yearly"
        })
        
        monthly_data = monthly_response.json()
        yearly_data = yearly_response.json()
        
        if monthly_data.get("valid") and yearly_data.get("valid"):
            # Yearly original total should be higher than monthly
            assert yearly_data.get("original_total") > monthly_data.get("original_total"), \
                "Yearly price should be higher than monthly"
            print(f"✓ Monthly: ${monthly_data.get('original_total')} → ${monthly_data.get('new_total')}")
            print(f"✓ Yearly: ${yearly_data.get('original_total')} → ${yearly_data.get('new_total')}")
        else:
            print(f"⚠ LAUNCH20 validation failed - monthly valid: {monthly_data.get('valid')}, yearly valid: {yearly_data.get('valid')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
