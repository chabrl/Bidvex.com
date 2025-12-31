#!/usr/bin/env python3
"""
BidVex Fee Calculator API and Seller Tax Status Testing
Tests the fee calculation logic for Individual vs Business sellers and seller commission calculations.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://bidvex-upgrade.preview.emergentagent.com/api"

# Test credentials from review request
TEST_USERS = {
    "pioneer": {"email": "pioneer@bidvextest.com", "password": "TestPass123!"},
    "individual": {"email": "individual@bidvextest.com", "password": "TestPass123!"},
    "business": {"email": "business@bidvextest.com", "password": "TestPass123!"},
    "admin": {"email": "admin@bazario.com", "password": "Admin123!"}
}

class BidVexFeeCalculatorTester:
    def __init__(self):
        self.session = None
        self.tokens = {}
        self.user_data = {}
        self.test_results = {}
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def login_user(self, user_type: str) -> bool:
        """Login with specific user credentials"""
        try:
            user_creds = TEST_USERS[user_type]
            login_data = {
                "email": user_creds["email"],
                "password": user_creds["password"]
            }
            
            async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.tokens[user_type] = data["access_token"]
                    self.user_data[user_type] = data["user"]
                    print(f"✅ {user_type.title()} user logged in successfully: {data['user']['id']}")
                    return True
                else:
                    print(f"❌ Failed to login {user_type} user: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in {user_type} user: {str(e)}")
            return False
            
    def get_auth_headers(self, user_type: str) -> Dict[str, str]:
        """Get authorization headers for specific user"""
        return {"Authorization": f"Bearer {self.tokens[user_type]}"}
        
    async def test_user_tax_status_fields(self) -> bool:
        """Test that users have correct is_tax_registered values"""
        print("\n🧪 Testing User Tax Status Fields...")
        
        try:
            # Test individual user (should have is_tax_registered=false)
            async with self.session.get(
                f"{BASE_URL}/auth/me",
                headers=self.get_auth_headers("individual")
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify tax fields exist
                    required_fields = ["is_tax_registered", "gst_number", "qst_number"]
                    for field in required_fields:
                        assert field in data, f"Missing required field: {field}"
                    
                    # Individual user should not be tax registered
                    assert data["is_tax_registered"] == False, "Individual user should not be tax registered"
                    assert data["gst_number"] is None, "Individual user should not have GST number"
                    assert data["qst_number"] is None, "Individual user should not have QST number"
                    
                    print(f"✅ Individual user tax status correct:")
                    print(f"   - is_tax_registered: {data['is_tax_registered']}")
                    print(f"   - gst_number: {data['gst_number']}")
                    print(f"   - qst_number: {data['qst_number']}")
                else:
                    print(f"❌ Failed to get individual user info: {response.status}")
                    return False
            
            # Test business user (should have is_tax_registered=true)
            async with self.session.get(
                f"{BASE_URL}/auth/me",
                headers=self.get_auth_headers("business")
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Business user should be tax registered
                    assert data["is_tax_registered"] == True, "Business user should be tax registered"
                    assert data["gst_number"] is not None, "Business user should have GST number"
                    assert data["qst_number"] is not None, "Business user should have QST number"
                    
                    print(f"✅ Business user tax status correct:")
                    print(f"   - is_tax_registered: {data['is_tax_registered']}")
                    print(f"   - gst_number: {data['gst_number']}")
                    print(f"   - qst_number: {data['qst_number']}")
                else:
                    print(f"❌ Failed to get business user info: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing user tax status fields: {str(e)}")
            return False
            
    async def test_fee_calculator_individual_seller(self) -> bool:
        """Test fee calculator for Individual Seller (Private Sale)"""
        print("\n🧪 Testing Fee Calculator API - Individual Seller (Private Sale)...")
        
        try:
            # Test with $1000 amount, QC region, individual seller
            params = {
                "amount": 1000,
                "region": "QC",
                "seller_is_business": "false"
            }
            
            async with self.session.get(
                f"{BASE_URL}/fees/calculate-buyer-cost",
                params=params,
                headers=self.get_auth_headers("individual")
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    required_fields = ["hammer_price", "buyer_premium", "tax_on_hammer", "tax_on_premium", "total"]
                    for field in required_fields:
                        assert field in data, f"Missing required field: {field}"
                    
                    # For individual seller (private sale), tax_on_hammer should be 0
                    assert data["tax_on_hammer"] == 0.0, f"Individual seller should have tax_on_hammer=0, got {data['tax_on_hammer']}"
                    
                    # Tax should only be on premium
                    assert data["tax_on_premium"] > 0, f"Individual seller should have tax on premium, got {data['tax_on_premium']}"
                    
                    # Calculate expected values
                    hammer_price = data["hammer_price"]
                    buyers_premium = data["buyer_premium"]
                    tax_on_premium = data["tax_on_premium"]
                    total_cost = data["total"]
                    
                    print(f"✅ Individual Seller Fee Calculation:")
                    print(f"   - Hammer Price: ${hammer_price:.2f}")
                    print(f"   - Buyer's Premium: ${buyers_premium:.2f}")
                    print(f"   - Tax on Hammer: ${data['tax_on_hammer']:.2f} (should be $0.00)")
                    print(f"   - Tax on Premium: ${tax_on_premium:.2f}")
                    print(f"   - Total Cost: ${total_cost:.2f}")
                    print(f"   - Tax Savings: ${data.get('tax_savings', 0):.2f}")
                    
                    # Store for comparison
                    self.test_results["individual_seller"] = data
                    
                    return True
                else:
                    print(f"❌ Failed to calculate fees for individual seller: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing individual seller fee calculation: {str(e)}")
            return False
            
    async def test_fee_calculator_business_seller(self) -> bool:
        """Test fee calculator for Business Seller"""
        print("\n🧪 Testing Fee Calculator API - Business Seller...")
        
        try:
            # Test with $1000 amount, QC region, business seller
            params = {
                "amount": 1000,
                "region": "QC",
                "seller_is_business": "true"
            }
            
            async with self.session.get(
                f"{BASE_URL}/fees/calculate-buyer-cost",
                params=params,
                headers=self.get_auth_headers("business")
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    required_fields = ["hammer_price", "buyer_premium", "tax_on_hammer", "tax_on_premium", "total"]
                    for field in required_fields:
                        assert field in data, f"Missing required field: {field}"
                    
                    # For business seller, both hammer and premium should be taxed
                    assert data["tax_on_hammer"] > 0, f"Business seller should have tax on hammer, got {data['tax_on_hammer']}"
                    assert data["tax_on_premium"] > 0, f"Business seller should have tax on premium, got {data['tax_on_premium']}"
                    
                    # Calculate expected values
                    hammer_price = data["hammer_price"]
                    buyers_premium = data["buyer_premium"]
                    tax_on_hammer = data["tax_on_hammer"]
                    tax_on_premium = data["tax_on_premium"]
                    total_cost = data["total"]
                    
                    print(f"✅ Business Seller Fee Calculation:")
                    print(f"   - Hammer Price: ${hammer_price:.2f}")
                    print(f"   - Buyer's Premium: ${buyers_premium:.2f}")
                    print(f"   - Tax on Hammer: ${tax_on_hammer:.2f}")
                    print(f"   - Tax on Premium: ${tax_on_premium:.2f}")
                    print(f"   - Total Cost: ${total_cost:.2f}")
                    
                    # Store for comparison
                    self.test_results["business_seller"] = data
                    
                    return True
                else:
                    print(f"❌ Failed to calculate fees for business seller: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing business seller fee calculation: {str(e)}")
            return False
            
    async def test_tax_savings_comparison(self) -> bool:
        """Compare tax savings between individual and business sellers"""
        print("\n🧪 Testing Tax Savings Comparison...")
        
        try:
            if "individual_seller" not in self.test_results or "business_seller" not in self.test_results:
                print("❌ Missing fee calculation data for comparison")
                return False
            
            individual_data = self.test_results["individual_seller"]
            business_data = self.test_results["business_seller"]
            
            individual_total = individual_data["total"]
            business_total = business_data["total"]
            
            tax_savings = business_total - individual_total
            savings_percentage = (tax_savings / business_total) * 100
            
            print(f"✅ Tax Savings Analysis:")
            print(f"   - Individual Seller Total: ${individual_total:.2f}")
            print(f"   - Business Seller Total: ${business_total:.2f}")
            print(f"   - Tax Savings: ${tax_savings:.2f}")
            print(f"   - Savings Percentage: {savings_percentage:.1f}%")
            
            # Verify savings exist
            assert tax_savings > 0, f"Individual seller should cost less than business seller"
            
            # The savings should be approximately 15% (tax on hammer price)
            # For $1000 hammer price with QC tax rates (GST 5% + QST 9.975% = 14.975%)
            expected_savings = 1000 * 0.14975  # Tax on hammer price
            tolerance = 5.0  # Allow $5 tolerance
            
            assert abs(tax_savings - expected_savings) < tolerance, f"Tax savings should be approximately ${expected_savings:.2f}, got ${tax_savings:.2f}"
            
            print(f"✅ Tax savings verification passed - Individual sellers save approximately 15% on taxes")
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing tax savings comparison: {str(e)}")
            return False
            
    async def test_seller_commission_calculation(self) -> bool:
        """Test seller commission calculation for different subscription tiers"""
        print("\n🧪 Testing Seller Commission Calculation...")
        
        try:
            # Test free tier commission (4.5%)
            params = {
                "amount": 1000,
                "subscription_tier": "free"
            }
            
            async with self.session.get(
                f"{BASE_URL}/fees/calculate-seller-net",
                params=params,
                headers=self.get_auth_headers("individual")
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    required_fields = ["hammer_price", "seller_commission", "seller_commission_percent", "net_payout"]
                    for field in required_fields:
                        assert field in data, f"Missing required field: {field}"
                    
                    # Verify free tier commission (4.5%)
                    expected_commission = 1000 * 0.045  # 4.5%
                    expected_net = 1000 - expected_commission
                    
                    assert abs(data["seller_commission"] - expected_commission) < 0.01, f"Free tier commission should be ${expected_commission:.2f}, got ${data['seller_commission']:.2f}"
                    assert abs(data["net_payout"] - expected_net) < 0.01, f"Free tier net should be ${expected_net:.2f}, got ${data['net_payout']:.2f}"
                    
                    print(f"✅ Free Tier Commission Calculation:")
                    print(f"   - Gross Amount: ${data['hammer_price']:.2f}")
                    print(f"   - Commission Rate: {data['seller_commission_percent']:.1f}%")
                    print(f"   - Commission Amount: ${data['seller_commission']:.2f}")
                    print(f"   - Net Amount: ${data['net_payout']:.2f}")
                else:
                    print(f"❌ Failed to calculate seller net for free tier: {response.status}")
                    return False
            
            # Test premium tier commission (4.0%)
            params = {
                "amount": 1000,
                "subscription_tier": "premium"
            }
            
            async with self.session.get(
                f"{BASE_URL}/fees/calculate-seller-net",
                params=params,
                headers=self.get_auth_headers("individual")
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify premium tier commission (4.0%)
                    expected_commission = 1000 * 0.040  # 4.0%
                    expected_net = 1000 - expected_commission
                    
                    assert abs(data["seller_commission"] - expected_commission) < 0.01, f"Premium tier commission should be ${expected_commission:.2f}, got ${data['seller_commission']:.2f}"
                    assert abs(data["net_payout"] - expected_net) < 0.01, f"Premium tier net should be ${expected_net:.2f}, got ${data['net_payout']:.2f}"
                    
                    print(f"✅ Premium Tier Commission Calculation:")
                    print(f"   - Gross Amount: ${data['hammer_price']:.2f}")
                    print(f"   - Commission Rate: {data['seller_commission_percent']:.1f}%")
                    print(f"   - Commission Amount: ${data['seller_commission']:.2f}")
                    print(f"   - Net Amount: ${data['net_payout']:.2f}")
                    
                    # Calculate premium savings
                    free_commission = 1000 * 0.045
                    premium_commission = data['seller_commission']
                    savings = free_commission - premium_commission
                    
                    print(f"✅ Premium Subscription Savings: ${savings:.2f} (0.5% reduction)")
                else:
                    print(f"❌ Failed to calculate seller net for premium tier: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing seller commission calculation: {str(e)}")
            return False
            
    async def test_fee_calculator_edge_cases(self) -> bool:
        """Test fee calculator edge cases and validation"""
        print("\n🧪 Testing Fee Calculator Edge Cases...")
        
        try:
            # Test invalid amount
            params = {
                "amount": -100,
                "region": "QC",
                "seller_is_business": "false"
            }
            
            async with self.session.get(
                f"{BASE_URL}/fees/calculate-buyer-cost",
                params=params,
                headers=self.get_auth_headers("individual")
            ) as response:
                if response.status == 400:
                    print("✅ Correctly rejected negative amount")
                else:
                    print(f"❌ Should have rejected negative amount, got: {response.status}")
                    return False
            
            # Test invalid region
            params = {
                "amount": 1000,
                "region": "INVALID",
                "seller_is_business": "false"
            }
            
            async with self.session.get(
                f"{BASE_URL}/fees/calculate-buyer-cost",
                params=params,
                headers=self.get_auth_headers("individual")
            ) as response:
                if response.status in [400, 422]:
                    print("✅ Correctly rejected invalid region")
                else:
                    print(f"❌ Should have rejected invalid region, got: {response.status}")
                    return False
            
            # Test missing parameters
            async with self.session.get(
                f"{BASE_URL}/fees/calculate-buyer-cost",
                params={"amount": 1000},  # Missing region and seller_is_business
                headers=self.get_auth_headers("individual")
            ) as response:
                if response.status in [400, 422]:
                    print("✅ Correctly rejected missing parameters")
                else:
                    print(f"❌ Should have rejected missing parameters, got: {response.status}")
                    return False
            
            # Test unauthorized access
            async with self.session.get(
                f"{BASE_URL}/fees/calculate-buyer-cost",
                params={
                    "amount": 1000,
                    "region": "QC",
                    "seller_is_business": "false"
                }
            ) as response:
                if response.status == 401:
                    print("✅ Correctly rejected unauthorized access")
                else:
                    print(f"❌ Should have rejected unauthorized access, got: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing fee calculator edge cases: {str(e)}")
            return False
            
    async def run_all_tests(self):
        """Run all BidVex fee calculator and tax status tests"""
        print("🚀 Starting BidVex Fee Calculator API and Seller Tax Status Tests")
        print("=" * 80)
        
        await self.setup_session()
        
        try:
            # Login test users (skip admin for now)
            for user_type in ["individual", "business"]:
                if not await self.login_user(user_type):
                    print(f"❌ Failed to login {user_type} user")
                    return False
            
            # Run tests in specific order
            tests = [
                ("User Tax Status Fields", self.test_user_tax_status_fields),
                ("Fee Calculator - Individual Seller", self.test_fee_calculator_individual_seller),
                ("Fee Calculator - Business Seller", self.test_fee_calculator_business_seller),
                ("Tax Savings Comparison", self.test_tax_savings_comparison),
                ("Seller Commission Calculation", self.test_seller_commission_calculation),
                ("Fee Calculator Edge Cases", self.test_fee_calculator_edge_cases)
            ]
            
            results = []
            for test_name, test_func in tests:
                try:
                    result = await test_func()
                    results.append((test_name, result))
                    self.test_results[test_name] = result
                except Exception as e:
                    print(f"❌ {test_name} failed with exception: {str(e)}")
                    results.append((test_name, False))
                    self.test_results[test_name] = False
            
            # Print summary
            print("\n" + "=" * 80)
            print("📊 BIDVEX FEE CALCULATOR API TEST RESULTS SUMMARY")
            print("=" * 80)
            
            passed = 0
            total = len(results)
            
            for test_name, result in results:
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status} - {test_name}")
                if result:
                    passed += 1
            
            print(f"\nOverall: {passed}/{total} tests passed")
            
            if passed == total:
                print("🎉 All BidVex fee calculator API tests PASSED!")
                print("\n📋 KEY FINDINGS:")
                print("• Individual sellers (Private Sale) save 15% on taxes - only premium is taxed")
                print("• Business sellers have tax on both hammer price and premium")
                print("• Premium subscription reduces seller commission from 4.5% to 4.0%")
                print("• User tax status fields (is_tax_registered, gst_number, qst_number) working correctly")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = BidVexFeeCalculatorTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)