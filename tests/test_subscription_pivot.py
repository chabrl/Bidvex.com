"""
BidVex Subscription Pivot & Power Bids Removal Tests
Tests for:
1. Power Bids API endpoint removal (should return 404)
2. Fee calculation endpoint with correct percentages
3. Subscription benefits endpoint with yearly pricing
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPowerBidsRemoval:
    """Test that Power Bids feature has been completely removed"""
    
    def test_power_bids_endpoint_returns_404(self):
        """Power Bids (monster bids) endpoint should return 404 Not Found"""
        response = requests.post(
            f"{BASE_URL}/api/bids/monster",
            params={"listing_id": "test-listing", "amount": 100}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✅ Power Bids endpoint correctly returns 404")


class TestSubscriptionBenefits:
    """Test subscription benefits endpoint with yearly pricing"""
    
    def test_subscription_benefits_endpoint_success(self):
        """Subscription benefits endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/fees/subscription-benefits")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get("success") is True
        print("✅ Subscription benefits endpoint returns 200")
    
    def test_subscription_benefits_has_all_tiers(self):
        """Should have free, premium, and vip tiers"""
        response = requests.get(f"{BASE_URL}/api/fees/subscription-benefits")
        data = response.json()
        tiers = data.get("tiers", {})
        
        assert "free" in tiers, "Missing 'free' tier"
        assert "premium" in tiers, "Missing 'premium' tier"
        assert "vip" in tiers, "Missing 'vip' tier"
        print("✅ All subscription tiers present (free, premium, vip)")
    
    def test_premium_yearly_pricing(self):
        """Premium tier should show $99.99/year"""
        response = requests.get(f"{BASE_URL}/api/fees/subscription-benefits")
        data = response.json()
        premium = data.get("tiers", {}).get("premium", {})
        
        assert premium.get("price") == "$99.99/year", f"Expected '$99.99/year', got '{premium.get('price')}'"
        assert "year" in premium.get("price_note", "").lower() or "annual" in premium.get("price_note", "").lower(), \
            "Premium price_note should mention yearly/annual billing"
        print("✅ Premium tier shows $99.99/year pricing")
    
    def test_vip_yearly_pricing(self):
        """VIP tier should show $299.99/year"""
        response = requests.get(f"{BASE_URL}/api/fees/subscription-benefits")
        data = response.json()
        vip = data.get("tiers", {}).get("vip", {})
        
        assert vip.get("price") == "$299.99/year", f"Expected '$299.99/year', got '{vip.get('price')}'"
        assert "year" in vip.get("price_note", "").lower() or "annual" in vip.get("price_note", "").lower(), \
            "VIP price_note should mention yearly/annual billing"
        print("✅ VIP tier shows $299.99/year pricing")


class TestFeePercentages:
    """Test fee percentages for each subscription tier"""
    
    def test_free_tier_fees(self):
        """Free tier: 4% seller / 5% buyer"""
        response = requests.get(f"{BASE_URL}/api/fees/subscription-benefits")
        data = response.json()
        free = data.get("tiers", {}).get("free", {})
        
        assert free.get("seller_commission") == "4%", f"Expected '4%' seller, got '{free.get('seller_commission')}'"
        assert free.get("buyer_premium") == "5%", f"Expected '5%' buyer, got '{free.get('buyer_premium')}'"
        print("✅ Free tier fees correct: 4% seller / 5% buyer")
    
    def test_premium_tier_fees(self):
        """Premium tier: 2.5% seller / 3.5% buyer"""
        response = requests.get(f"{BASE_URL}/api/fees/subscription-benefits")
        data = response.json()
        premium = data.get("tiers", {}).get("premium", {})
        
        assert premium.get("seller_commission") == "2.5%", f"Expected '2.5%' seller, got '{premium.get('seller_commission')}'"
        assert premium.get("buyer_premium") == "3.5%", f"Expected '3.5%' buyer, got '{premium.get('buyer_premium')}'"
        print("✅ Premium tier fees correct: 2.5% seller / 3.5% buyer")
    
    def test_vip_tier_fees(self):
        """VIP tier: 2% seller / 3% buyer"""
        response = requests.get(f"{BASE_URL}/api/fees/subscription-benefits")
        data = response.json()
        vip = data.get("tiers", {}).get("vip", {})
        
        assert vip.get("seller_commission") == "2%", f"Expected '2%' seller, got '{vip.get('seller_commission')}'"
        assert vip.get("buyer_premium") == "3%", f"Expected '3%' buyer, got '{vip.get('buyer_premium')}'"
        print("✅ VIP tier fees correct: 2% seller / 3% buyer")


class TestFeeCalculation:
    """Test fee calculation endpoints"""
    
    def test_buyer_fee_calculation_free_tier(self):
        """Test buyer fee calculation for free tier (5%)"""
        response = requests.get(
            f"{BASE_URL}/api/fees/calculate-buyer-cost",
            params={"hammer_price": 1000, "tier": "free"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Free tier: 5% buyer premium
        assert data.get("buyer_premium_percent") == 5.0, f"Expected 5.0%, got {data.get('buyer_premium_percent')}"
        assert data.get("buyer_premium") == 50.0, f"Expected $50 fee, got ${data.get('buyer_premium')}"
        print("✅ Free tier buyer fee calculation correct: 5% = $50 on $1000")
    
    def test_buyer_fee_calculation_premium_tier(self):
        """Test buyer fee calculation for premium tier (3.5%)"""
        response = requests.get(
            f"{BASE_URL}/api/fees/calculate-buyer-cost",
            params={"hammer_price": 1000, "tier": "premium"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Premium tier: 3.5% buyer premium
        assert data.get("buyer_premium_percent") == 3.5, f"Expected 3.5%, got {data.get('buyer_premium_percent')}"
        assert data.get("buyer_premium") == 35.0, f"Expected $35 fee, got ${data.get('buyer_premium')}"
        print("✅ Premium tier buyer fee calculation correct: 3.5% = $35 on $1000")
    
    def test_buyer_fee_calculation_vip_tier(self):
        """Test buyer fee calculation for VIP tier (3%)"""
        response = requests.get(
            f"{BASE_URL}/api/fees/calculate-buyer-cost",
            params={"hammer_price": 1000, "tier": "vip"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # VIP tier: 3% buyer premium
        assert data.get("buyer_premium_percent") == 3.0, f"Expected 3.0%, got {data.get('buyer_premium_percent')}"
        assert data.get("buyer_premium") == 30.0, f"Expected $30 fee, got ${data.get('buyer_premium')}"
        print("✅ VIP tier buyer fee calculation correct: 3% = $30 on $1000")
    
    def test_seller_fee_calculation_free_tier(self):
        """Test seller fee calculation for free tier (4%)"""
        response = requests.get(
            f"{BASE_URL}/api/fees/calculate-seller-net",
            params={"hammer_price": 1000, "tier": "free"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Free tier: 4% seller commission
        assert data.get("seller_commission_percent") == 4.0, f"Expected 4.0%, got {data.get('seller_commission_percent')}"
        assert data.get("seller_commission") == 40.0, f"Expected $40 fee, got ${data.get('seller_commission')}"
        assert data.get("net_payout") == 960.0, f"Expected $960 net payout, got ${data.get('net_payout')}"
        print("✅ Free tier seller fee calculation correct: 4% = $40 on $1000, net $960")
    
    def test_seller_fee_calculation_premium_tier(self):
        """Test seller fee calculation for premium tier (2.5%)"""
        response = requests.get(
            f"{BASE_URL}/api/fees/calculate-seller-net",
            params={"hammer_price": 1000, "tier": "premium"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Premium tier: 2.5% seller commission
        assert data.get("seller_commission_percent") == 2.5, f"Expected 2.5%, got {data.get('seller_commission_percent')}"
        assert data.get("seller_commission") == 25.0, f"Expected $25 fee, got ${data.get('seller_commission')}"
        assert data.get("net_payout") == 975.0, f"Expected $975 net payout, got ${data.get('net_payout')}"
        print("✅ Premium tier seller fee calculation correct: 2.5% = $25 on $1000, net $975")
    
    def test_seller_fee_calculation_vip_tier(self):
        """Test seller fee calculation for VIP tier (2%)"""
        response = requests.get(
            f"{BASE_URL}/api/fees/calculate-seller-net",
            params={"hammer_price": 1000, "tier": "vip"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # VIP tier: 2% seller commission
        assert data.get("seller_commission_percent") == 2.0, f"Expected 2.0%, got {data.get('seller_commission_percent')}"
        assert data.get("seller_commission") == 20.0, f"Expected $20 fee, got ${data.get('seller_commission')}"
        assert data.get("net_payout") == 980.0, f"Expected $980 net payout, got ${data.get('net_payout')}"
        print("✅ VIP tier seller fee calculation correct: 2% = $20 on $1000, net $980")


class TestAutoBidBotAvailability:
    """Test that Auto-Bid Bot is still available for Premium/VIP users"""
    
    def test_premium_has_auto_bid_bot(self):
        """Premium tier should include Auto-Bid Bot feature"""
        response = requests.get(f"{BASE_URL}/api/fees/subscription-benefits")
        data = response.json()
        premium = data.get("tiers", {}).get("premium", {})
        features = premium.get("features", [])
        
        auto_bid_present = any("auto-bid" in f.lower() or "auto bid" in f.lower() for f in features)
        assert auto_bid_present, "Premium tier should include Auto-Bid Bot feature"
        print("✅ Premium tier includes Auto-Bid Bot feature")
    
    def test_vip_has_auto_bid_bot(self):
        """VIP tier should include Auto-Bid Bot feature"""
        response = requests.get(f"{BASE_URL}/api/fees/subscription-benefits")
        data = response.json()
        vip = data.get("tiers", {}).get("vip", {})
        features = vip.get("features", [])
        
        auto_bid_present = any("auto-bid" in f.lower() or "auto bid" in f.lower() for f in features)
        assert auto_bid_present, "VIP tier should include Auto-Bid Bot feature"
        print("✅ VIP tier includes Auto-Bid Bot feature")
    
    def test_free_tier_no_auto_bid_bot(self):
        """Free tier should NOT include Auto-Bid Bot feature"""
        response = requests.get(f"{BASE_URL}/api/fees/subscription-benefits")
        data = response.json()
        free = data.get("tiers", {}).get("free", {})
        features = free.get("features", [])
        
        auto_bid_present = any("auto-bid" in f.lower() or "auto bid" in f.lower() for f in features)
        assert not auto_bid_present, "Free tier should NOT include Auto-Bid Bot feature"
        print("✅ Free tier correctly excludes Auto-Bid Bot feature")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
