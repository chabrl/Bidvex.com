#!/usr/bin/env python3
"""
BidVex Pre-Launch Calibration End-to-End Testing
Tests critical functionality for the BidVex auction platform including:
1. Admin Marketplace Settings API Tests
2. Buy Now Master Toggle Tests  
3. Quota Enforcement Tests
4. Live Controls Integration
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://bid-masters-1.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@bazario.com"
ADMIN_PASSWORD = "Admin123!"
TEST_USER_EMAIL = "calibration.tester@bazario.com"
TEST_USER_PASSWORD = "CalibrationTest123!"

class BidVexCalibrationTester:
    def __init__(self):
        self.session = None
        self.admin_token = None
        self.admin_id = None
        self.user_token = None
        self.user_id = None
        self.test_results = {}
        self.original_settings = None
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def setup_admin_user(self) -> bool:
        """Setup admin user for testing admin endpoints"""
        try:
            # Try to login with existing admin credentials
            login_data = {
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            }
            
            async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.admin_token = data["access_token"]
                    self.admin_id = data["user"]["id"]
                    print(f"✅ Admin user logged in successfully: {self.admin_id}")
                    return True
                else:
                    print(f"❌ Failed to login admin: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error setting up admin user: {str(e)}")
            return False
            
    async def setup_test_user(self) -> bool:
        """Setup regular test user"""
        try:
            # Try to register test user
            user_data = {
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "name": "Calibration Tester",
                "account_type": "personal",
                "phone": "+1234567890",
                "address": "123 Test Street, Test City"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.user_token = data["access_token"]
                    self.user_id = data["user"]["id"]
                    print(f"✅ Test user registered successfully: {self.user_id}")
                    return True
                elif response.status == 400:
                    # User might already exist, try login
                    return await self.login_test_user()
                else:
                    print(f"❌ Failed to register user: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error setting up test user: {str(e)}")
            return False
            
    async def login_test_user(self) -> bool:
        """Login with test user credentials"""
        try:
            login_data = {
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD
            }
            
            async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.user_token = data["access_token"]
                    self.user_id = data["user"]["id"]
                    print(f"✅ Test user logged in successfully: {self.user_id}")
                    return True
                else:
                    print(f"❌ Failed to login user: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in user: {str(e)}")
            return False
            
    def get_admin_headers(self) -> Dict[str, str]:
        """Get admin authorization headers"""
        return {"Authorization": f"Bearer {self.admin_token}"}
        
    def get_user_headers(self) -> Dict[str, str]:
        """Get user authorization headers"""
        return {"Authorization": f"Bearer {self.user_token}"}
        
    async def test_public_feature_flags_endpoint(self) -> bool:
        """Test GET /api/marketplace/feature-flags (PUBLIC) - should work without authentication"""
        print("\n🧪 Testing GET /api/marketplace/feature-flags (PUBLIC)...")
        
        try:
            async with self.session.get(f"{BASE_URL}/marketplace/feature-flags") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify required fields are present
                    required_fields = ["enable_buy_now", "enable_anti_sniping", "anti_sniping_window_minutes", "minimum_bid_increment"]
                    
                    for field in required_fields:
                        assert field in data, f"Missing required field: {field}"
                    
                    # Verify field types
                    assert isinstance(data["enable_buy_now"], bool), "enable_buy_now should be boolean"
                    assert isinstance(data["enable_anti_sniping"], bool), "enable_anti_sniping should be boolean"
                    assert isinstance(data["anti_sniping_window_minutes"], (int, float)), "anti_sniping_window_minutes should be numeric"
                    assert isinstance(data["minimum_bid_increment"], (int, float)), "minimum_bid_increment should be numeric"
                    
                    print(f"✅ Public feature flags endpoint working correctly")
                    print(f"   - enable_buy_now: {data['enable_buy_now']}")
                    print(f"   - enable_anti_sniping: {data['enable_anti_sniping']}")
                    print(f"   - anti_sniping_window_minutes: {data['anti_sniping_window_minutes']}")
                    print(f"   - minimum_bid_increment: {data['minimum_bid_increment']}")
                    
                    return True
                else:
                    print(f"❌ Failed to get public feature flags: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing public feature flags endpoint: {str(e)}")
            return False
            
    async def test_admin_marketplace_settings_get(self) -> bool:
        """Test GET /api/admin/marketplace-settings (ADMIN) - should return full settings with auth"""
        print("\n🧪 Testing GET /api/admin/marketplace-settings (ADMIN)...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/admin/marketplace-settings",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Store original settings for restoration later
                    self.original_settings = data.copy()
                    
                    # Verify comprehensive settings are returned
                    expected_fields = [
                        "allow_all_users_multi_lot", "require_approval_new_sellers", 
                        "max_active_auctions_per_user", "max_lots_per_auction",
                        "minimum_bid_increment", "enable_anti_sniping", 
                        "anti_sniping_window_minutes", "enable_buy_now"
                    ]
                    
                    for field in expected_fields:
                        assert field in data, f"Missing expected field: {field}"
                    
                    print(f"✅ Admin marketplace settings endpoint working correctly")
                    print(f"   - max_lots_per_auction: {data['max_lots_per_auction']}")
                    print(f"   - enable_buy_now: {data['enable_buy_now']}")
                    print(f"   - enable_anti_sniping: {data['enable_anti_sniping']}")
                    
                    return True
                else:
                    print(f"❌ Failed to get admin marketplace settings: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing admin marketplace settings get: {str(e)}")
            return False
            
    async def test_admin_marketplace_settings_put(self) -> bool:
        """Test PUT /api/admin/marketplace-settings (ADMIN) - test toggling enable_buy_now"""
        print("\n🧪 Testing PUT /api/admin/marketplace-settings (ADMIN)...")
        
        try:
            if not self.original_settings:
                print("❌ Original settings not available - run GET test first")
                return False
            
            # Test 1: Toggle enable_buy_now to FALSE
            update_data = {
                "enable_buy_now": False
            }
            
            async with self.session.put(
                f"{BASE_URL}/admin/marketplace-settings",
                json=update_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # The API returns the updated settings directly, not wrapped in a "settings" key
                    assert data["enable_buy_now"] == False, "enable_buy_now should be False"
                    
                    print(f"✅ Successfully disabled Buy Now feature")
                    print(f"   - enable_buy_now: {data['enable_buy_now']}")
                else:
                    print(f"❌ Failed to update marketplace settings: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Toggle enable_buy_now to TRUE
            update_data = {
                "enable_buy_now": True
            }
            
            async with self.session.put(
                f"{BASE_URL}/admin/marketplace-settings",
                json=update_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    assert data["enable_buy_now"] == True, "enable_buy_now should be True"
                    
                    print(f"✅ Successfully enabled Buy Now feature")
                    print(f"   - enable_buy_now: {data['enable_buy_now']}")
                else:
                    print(f"❌ Failed to re-enable Buy Now: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing admin marketplace settings put: {str(e)}")
            return False
            
    async def test_buy_now_master_toggle_enforcement(self) -> bool:
        """Test Buy Now master toggle enforcement - 403 when disabled, works when enabled"""
        print("\n🧪 Testing Buy Now Master Toggle Enforcement...")
        
        try:
            # First, disable Buy Now via admin API
            print("   - Disabling Buy Now feature...")
            update_data = {"enable_buy_now": False}
            
            async with self.session.put(
                f"{BASE_URL}/admin/marketplace-settings",
                json=update_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status != 200:
                    print(f"❌ Failed to disable Buy Now: {response.status}")
                    return False
            
            # Test 1: POST /api/buy-now should return 403 when disabled
            buy_now_data = {
                "auction_id": "test-auction-id",
                "lot_number": 1,
                "quantity": 1
            }
            
            async with self.session.post(
                f"{BASE_URL}/buy-now",
                json=buy_now_data,
                headers=self.get_user_headers()
            ) as response:
                if response.status == 403:
                    data = await response.json()
                    
                    # Verify the specific error message
                    expected_message = "Buy Now feature is currently disabled by admin"
                    if expected_message in data.get("detail", ""):
                        print(f"✅ Correctly returned 403 when Buy Now disabled")
                        print(f"   - Status Code: {response.status}")
                        print(f"   - Message: {data['detail']}")
                    else:
                        print(f"❌ Wrong error message. Expected: '{expected_message}', Got: '{data.get('detail')}'")
                        return False
                else:
                    print(f"❌ Should have returned 403, got: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Re-enable Buy Now for next test
            print("   - Re-enabling Buy Now feature...")
            update_data = {"enable_buy_now": True}
            
            async with self.session.put(
                f"{BASE_URL}/admin/marketplace-settings",
                json=update_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status != 200:
                    print(f"❌ Failed to re-enable Buy Now: {response.status}")
                    return False
            
            # Test 2: POST /api/buy-now should work normally when enabled (will fail for other reasons like invalid auction, but not 403)
            async with self.session.post(
                f"{BASE_URL}/buy-now",
                json=buy_now_data,
                headers=self.get_user_headers()
            ) as response:
                if response.status == 403:
                    data = await response.json()
                    if "Buy Now feature is currently disabled" in data.get("detail", ""):
                        print(f"❌ Buy Now still disabled after re-enabling")
                        return False
                    else:
                        print(f"✅ Buy Now enabled - got different 403 error (expected): {data.get('detail')}")
                elif response.status in [400, 404]:
                    # Expected - auction doesn't exist or other validation error
                    print(f"✅ Buy Now enabled - got expected validation error: {response.status}")
                else:
                    print(f"✅ Buy Now enabled - got status: {response.status}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing Buy Now master toggle enforcement: {str(e)}")
            return False
            
    async def test_quota_enforcement(self) -> bool:
        """Test quota enforcement - max_lots_per_auction should return 400 with clear error"""
        print("\n🧪 Testing Quota Enforcement...")
        
        try:
            # First, set max_lots_per_auction to 2 via admin API
            print("   - Setting max_lots_per_auction to 2...")
            update_data = {"max_lots_per_auction": 2}
            
            async with self.session.put(
                f"{BASE_URL}/admin/marketplace-settings",
                json=update_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status != 200:
                    print(f"❌ Failed to set quota limit: {response.status}")
                    return False
                    
                data = await response.json()
                print(f"   - Quota set to: {data['max_lots_per_auction']}")
            
            # Test: Try to create multi-item listing with 5 lots (exceeds limit of 2)
            lots_data = []
            for i in range(5):  # Create 5 lots (exceeds limit of 2)
                lots_data.append({
                    "lot_number": i + 1,
                    "title": f"Test Lot {i + 1}",
                    "description": f"Description for lot {i + 1}",
                    "quantity": 1,
                    "starting_price": 10.0,
                    "current_price": 10.0,
                    "condition": "new",
                    "images": [],
                    "pricing_mode": "multiplied",
                    "buy_now_enabled": False
                })
            
            multi_item_data = {
                "title": "Test Multi-Item Auction",
                "description": "Test auction with too many lots",
                "category": "Electronics",
                "location": "Test Location",
                "city": "Test City",
                "region": "Test Region",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "lots": lots_data
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=multi_item_data,
                headers=self.get_user_headers()
            ) as response:
                if response.status == 400:
                    data = await response.json()
                    
                    # Verify the specific error message
                    expected_message = "Maximum 2 lots allowed per auction. You submitted 5 lots."
                    if expected_message in data.get("detail", ""):
                        print(f"✅ Correctly enforced quota limit")
                        print(f"   - Status Code: {response.status}")
                        print(f"   - Message: {data['detail']}")
                    else:
                        print(f"❌ Wrong error message. Expected: '{expected_message}', Got: '{data.get('detail')}'")
                        return False
                else:
                    print(f"❌ Should have returned 400 Bad Request, got: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Restore original quota limit
            if self.original_settings and "max_lots_per_auction" in self.original_settings:
                print(f"   - Restoring original quota to: {self.original_settings['max_lots_per_auction']}")
                restore_data = {"max_lots_per_auction": self.original_settings["max_lots_per_auction"]}
                
                async with self.session.put(
                    f"{BASE_URL}/admin/marketplace-settings",
                    json=restore_data,
                    headers=self.get_admin_headers()
                ) as response:
                    if response.status == 200:
                        print(f"✅ Quota restored to original value")
                    else:
                        print(f"⚠️  Failed to restore original quota: {response.status}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing quota enforcement: {str(e)}")
            return False
            
    async def test_live_controls_integration(self) -> bool:
        """Test Live Controls integration - verify admin controls sync with backend"""
        print("\n🧪 Testing Live Controls Integration...")
        
        try:
            # Test 1: Toggle buyNowEnabled and verify it updates enable_buy_now in database
            print("   - Testing buyNowEnabled toggle...")
            
            # Get current state
            async with self.session.get(
                f"{BASE_URL}/admin/marketplace-settings",
                headers=self.get_admin_headers()
            ) as response:
                if response.status != 200:
                    print(f"❌ Failed to get current settings: {response.status}")
                    return False
                    
                current_settings = await response.json()
                current_buy_now = current_settings["enable_buy_now"]
                print(f"   - Current enable_buy_now: {current_buy_now}")
            
            # Toggle to opposite value
            new_buy_now_value = not current_buy_now
            update_data = {"enable_buy_now": new_buy_now_value}
            
            async with self.session.put(
                f"{BASE_URL}/admin/marketplace-settings",
                json=update_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["enable_buy_now"] == new_buy_now_value:
                        print(f"✅ buyNowEnabled toggle working - updated to: {new_buy_now_value}")
                    else:
                        print(f"❌ buyNowEnabled toggle failed - expected: {new_buy_now_value}, got: {data['enable_buy_now']}")
                        return False
                else:
                    print(f"❌ Failed to toggle buyNowEnabled: {response.status}")
                    return False
            
            # Test 2: Toggle antiSnipingEnabled and verify it updates enable_anti_sniping
            print("   - Testing antiSnipingEnabled toggle...")
            
            current_anti_sniping = current_settings["enable_anti_sniping"]
            new_anti_sniping_value = not current_anti_sniping
            update_data = {"enable_anti_sniping": new_anti_sniping_value}
            
            async with self.session.put(
                f"{BASE_URL}/admin/marketplace-settings",
                json=update_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["enable_anti_sniping"] == new_anti_sniping_value:
                        print(f"✅ antiSnipingEnabled toggle working - updated to: {new_anti_sniping_value}")
                    else:
                        print(f"❌ antiSnipingEnabled toggle failed - expected: {new_anti_sniping_value}, got: {data['enable_anti_sniping']}")
                        return False
                else:
                    print(f"❌ Failed to toggle antiSnipingEnabled: {response.status}")
                    return False
            
            # Restore original values
            print("   - Restoring original values...")
            restore_data = {
                "enable_buy_now": current_buy_now,
                "enable_anti_sniping": current_anti_sniping
            }
            
            async with self.session.put(
                f"{BASE_URL}/admin/marketplace-settings",
                json=restore_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    print(f"✅ Original values restored")
                else:
                    print(f"⚠️  Failed to restore original values: {response.status}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing Live Controls integration: {str(e)}")
            return False
            
    async def test_unauthorized_access(self) -> bool:
        """Test that admin endpoints properly reject unauthorized access"""
        print("\n🧪 Testing Unauthorized Access Protection...")
        
        try:
            # Test 1: Admin GET without auth should fail
            async with self.session.get(f"{BASE_URL}/admin/marketplace-settings") as response:
                if response.status == 401:
                    print("✅ Correctly rejected unauthorized GET to admin settings")
                else:
                    print(f"❌ Should have rejected unauthorized GET, got: {response.status}")
                    return False
            
            # Test 2: Admin PUT without auth should fail
            async with self.session.put(
                f"{BASE_URL}/admin/marketplace-settings",
                json={"enable_buy_now": False}
            ) as response:
                if response.status == 401:
                    print("✅ Correctly rejected unauthorized PUT to admin settings")
                else:
                    print(f"❌ Should have rejected unauthorized PUT, got: {response.status}")
                    return False
            
            # Test 3: Regular user trying to access admin endpoint should fail
            async with self.session.get(
                f"{BASE_URL}/admin/marketplace-settings",
                headers=self.get_user_headers()
            ) as response:
                if response.status in [401, 403]:
                    print("✅ Correctly rejected regular user access to admin settings")
                else:
                    print(f"❌ Should have rejected regular user access, got: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing unauthorized access: {str(e)}")
            return False
            
    async def run_all_tests(self):
        """Run all pre-launch calibration tests"""
        print("🚀 Starting BidVex Pre-Launch Calibration Tests")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Setup test users
            if not await self.setup_admin_user():
                print("❌ Failed to setup admin user")
                return False
                
            if not await self.setup_test_user():
                print("❌ Failed to setup test user")
                return False
            
            # Run tests in specific order
            tests = [
                ("Public Feature Flags Endpoint", self.test_public_feature_flags_endpoint),
                ("Admin Marketplace Settings GET", self.test_admin_marketplace_settings_get),
                ("Admin Marketplace Settings PUT", self.test_admin_marketplace_settings_put),
                ("Buy Now Master Toggle Enforcement", self.test_buy_now_master_toggle_enforcement),
                ("Quota Enforcement", self.test_quota_enforcement),
                ("Live Controls Integration", self.test_live_controls_integration),
                ("Unauthorized Access Protection", self.test_unauthorized_access)
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
            print("\n" + "=" * 70)
            print("📊 BIDVEX PRE-LAUNCH CALIBRATION TEST RESULTS")
            print("=" * 70)
            
            passed = 0
            total = len(results)
            
            for test_name, result in results:
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status} - {test_name}")
                if result:
                    passed += 1
            
            print(f"\nOverall: {passed}/{total} tests passed")
            
            if passed == total:
                print("🎉 All pre-launch calibration tests PASSED!")
                print("\n✅ Definition of Done:")
                print("   - All API responses return correct status codes")
                print("   - Feature flags endpoint is publicly accessible")
                print("   - Buy Now toggle enforcement verified (403 when disabled)")
                print("   - Quota enforcement returns 400 with clear error message")
                print("   - Live Controls properly sync with backend")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = BidVexCalibrationTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)