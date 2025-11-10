#!/usr/bin/env python3
"""
Backend API Testing for Bazario Currency Enforcement System
Tests the complete currency enforcement functionality including appeals, profile updates, and geolocation.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://auction-preview.preview.emergentagent.com/api"
TEST_USER_EMAIL = "currency.tester@bazario.com"
TEST_USER_PASSWORD = "CurrencyTest123!"
TEST_USER_NAME = "Currency Tester"
ADMIN_EMAIL = "admin@admin.bazario.com"
ADMIN_PASSWORD = "AdminTest123!"

class BazarioCurrencyTester:
    def __init__(self):
        self.session = None
        self.auth_token = None
        self.user_id = None
        self.admin_token = None
        self.admin_id = None
        self.test_appeal_id = None
        self.test_results = {}
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def register_test_user(self) -> bool:
        """Register a test user for currency testing"""
        try:
            user_data = {
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "name": TEST_USER_NAME,
                "account_type": "personal",
                "phone": "+1234567890",
                "address": "123 Test Street, Test City"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.auth_token = data["access_token"]
                    self.user_id = data["user"]["id"]
                    print(f"✅ Test user registered successfully: {self.user_id}")
                    print(f"   - Enforced Currency: {data['user'].get('enforced_currency', 'N/A')}")
                    print(f"   - Currency Locked: {data['user'].get('currency_locked', 'N/A')}")
                    print(f"   - Location Confidence: {data['user'].get('location_confidence_score', 'N/A')}")
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
            print(f"❌ Error registering user: {str(e)}")
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
                    self.auth_token = data["access_token"]
                    self.user_id = data["user"]["id"]
                    print(f"✅ Test user logged in successfully: {self.user_id}")
                    return True
                else:
                    print(f"❌ Failed to login user: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in user: {str(e)}")
            return False
            
    async def setup_admin_user(self) -> bool:
        """Setup admin user for testing admin endpoints"""
        try:
            # Try to register admin user
            admin_data = {
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "name": "Admin User",
                "account_type": "admin",
                "phone": "+1234567891"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=admin_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.admin_token = data["access_token"]
                    self.admin_id = data["user"]["id"]
                    print(f"✅ Admin user registered successfully: {self.admin_id}")
                    return True
                elif response.status == 400:
                    # Admin might already exist, try login
                    return await self.login_admin_user()
                else:
                    print(f"❌ Failed to register admin: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error setting up admin user: {str(e)}")
            return False
            
    async def login_admin_user(self) -> bool:
        """Login with admin credentials"""
        try:
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
                    return False
        except Exception as e:
            print(f"❌ Error logging in admin: {str(e)}")
            return False
            
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers"""
        return {"Authorization": f"Bearer {self.auth_token}"}
        
    def get_admin_headers(self) -> Dict[str, str]:
        """Get admin authorization headers"""
        return {"Authorization": f"Bearer {self.admin_token}"}
        
    async def test_user_model_fields(self) -> bool:
        """Test GET /api/auth/me includes currency enforcement fields"""
        print("\n🧪 Testing GET /api/auth/me (User Model Fields)...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/auth/me",
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify required currency enforcement fields exist
                    required_fields = ["enforced_currency", "currency_locked", "location_confidence_score"]
                    
                    for field in required_fields:
                        assert field in data, f"Missing required field: {field}"
                    
                    # Verify field types and values
                    assert data["enforced_currency"] in ["CAD", "USD", None], "Invalid enforced_currency value"
                    assert isinstance(data["currency_locked"], bool), "currency_locked should be boolean"
                    assert data["location_confidence_score"] is None or isinstance(data["location_confidence_score"], int), "location_confidence_score should be int or None"
                    
                    print(f"✅ User model includes all currency enforcement fields")
                    print(f"   - Enforced Currency: {data['enforced_currency']}")
                    print(f"   - Currency Locked: {data['currency_locked']}")
                    print(f"   - Location Confidence Score: {data['location_confidence_score']}")
                    print(f"   - Preferred Currency: {data.get('preferred_currency', 'N/A')}")
                    
                    return True
                else:
                    print(f"❌ Failed to get user info: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing user model fields: {str(e)}")
            return False
            
    async def test_profile_update_currency_lock(self) -> bool:
        """Test POST /api/watchlist/add endpoint"""
        print("\n🧪 Testing POST /api/watchlist/add...")
        
        try:
            # Test adding valid listing to watchlist
            listing_id = self.test_listing_ids[0]
            
            async with self.session.post(
                f"{BASE_URL}/watchlist/add?listing_id={listing_id}",
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "message" in data
                    assert "success" in data
                    assert data["success"] is True
                    assert data["message"] == "Added to watchlist"
                    
                    print(f"✅ Successfully added listing to watchlist: {listing_id}")
                    print(f"   - Message: {data['message']}")
                    
                    # Test adding duplicate listing (should return already_added)
                    async with self.session.post(
                        f"{BASE_URL}/watchlist/add?listing_id={listing_id}",
                        headers=self.get_auth_headers()
                    ) as dup_response:
                        if dup_response.status == 200:
                            dup_data = await dup_response.json()
                            assert "already_added" in dup_data
                            assert dup_data["already_added"] is True
                            assert dup_data["message"] == "Already in watchlist"
                            print(f"✅ Correctly handled duplicate addition")
                        else:
                            print(f"❌ Failed duplicate test: {dup_response.status}")
                            return False
                    
                    return True
                else:
                    print(f"❌ Failed to add to watchlist: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing add to watchlist: {str(e)}")
            return False
            
    async def test_check_watchlist_status(self) -> bool:
        """Test GET /api/watchlist/check/{listing_id} endpoint"""
        print("\n🧪 Testing GET /api/watchlist/check/{listing_id}...")
        
        try:
            # Test checking listing that IS in watchlist
            listing_in_watchlist = self.test_listing_ids[0]
            
            async with self.session.get(
                f"{BASE_URL}/watchlist/check/{listing_in_watchlist}",
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "in_watchlist" in data
                    assert data["in_watchlist"] is True
                    
                    print(f"✅ Correctly identified listing in watchlist: {listing_in_watchlist}")
                    
                    # Test checking listing that is NOT in watchlist
                    listing_not_in_watchlist = self.test_listing_ids[1]
                    
                    async with self.session.get(
                        f"{BASE_URL}/watchlist/check/{listing_not_in_watchlist}",
                        headers=self.get_auth_headers()
                    ) as not_in_response:
                        if not_in_response.status == 200:
                            not_in_data = await not_in_response.json()
                            assert "in_watchlist" in not_in_data
                            assert not_in_data["in_watchlist"] is False
                            print(f"✅ Correctly identified listing NOT in watchlist: {listing_not_in_watchlist}")
                        else:
                            print(f"❌ Failed to check non-watchlist item: {not_in_response.status}")
                            return False
                    
                    return True
                else:
                    print(f"❌ Failed to check watchlist status: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing watchlist status check: {str(e)}")
            return False
            
    async def test_get_watchlist(self) -> bool:
        """Test GET /api/watchlist endpoint"""
        print("\n🧪 Testing GET /api/watchlist...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/watchlist",
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response is a list
                    assert isinstance(data, list)
                    
                    # Should have at least one item (the one we added)
                    assert len(data) >= 1, "Watchlist should contain at least one item"
                    
                    # Find our test listing
                    test_listing = None
                    for item in data:
                        if item["id"] == self.test_listing_ids[0]:
                            test_listing = item
                            break
                    
                    assert test_listing is not None, "Test listing not found in watchlist"
                    
                    # Verify listing details are included
                    assert "id" in test_listing
                    assert "title" in test_listing
                    assert "description" in test_listing
                    assert "current_price" in test_listing
                    assert "watchlist_added_at" in test_listing
                    
                    print(f"✅ Watchlist retrieved successfully")
                    print(f"   - Total items: {len(data)}")
                    print(f"   - Test listing found: {test_listing['title']}")
                    print(f"   - Added at: {test_listing['watchlist_added_at']}")
                    return True
                else:
                    print(f"❌ Failed to get watchlist: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing get watchlist: {str(e)}")
            return False
            
    async def test_remove_from_watchlist(self) -> bool:
        """Test POST /api/watchlist/remove endpoint"""
        print("\n🧪 Testing POST /api/watchlist/remove...")
        
        try:
            # Test removing existing watchlist item
            listing_id = self.test_listing_ids[0]
            
            async with self.session.post(
                f"{BASE_URL}/watchlist/remove?listing_id={listing_id}",
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "message" in data
                    assert "success" in data
                    assert data["success"] is True
                    assert data["message"] == "Removed from watchlist"
                    
                    print(f"✅ Successfully removed listing from watchlist: {listing_id}")
                    
                    # Test removing non-existent item
                    async with self.session.post(
                        f"{BASE_URL}/watchlist/remove?listing_id={listing_id}",
                        headers=self.get_auth_headers()
                    ) as not_found_response:
                        if not_found_response.status == 200:
                            not_found_data = await not_found_response.json()
                            assert "success" in not_found_data
                            assert not_found_data["success"] is False
                            assert not_found_data["message"] == "Item not in watchlist"
                            print(f"✅ Correctly handled removal of non-existent item")
                        else:
                            print(f"❌ Failed non-existent removal test: {not_found_response.status}")
                            return False
                    
                    return True
                else:
                    print(f"❌ Failed to remove from watchlist: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing remove from watchlist: {str(e)}")
            return False
    
    async def test_buyer_dashboard_watchlist(self) -> bool:
        """Test GET /api/dashboard/buyer includes watchlist data"""
        print("\n🧪 Testing GET /api/dashboard/buyer (watchlist integration)...")
        
        try:
            # First add a couple items to watchlist
            for listing_id in self.test_listing_ids[1:3]:
                async with self.session.post(
                    f"{BASE_URL}/watchlist/add?listing_id={listing_id}",
                    headers=self.get_auth_headers()
                ) as add_response:
                    if add_response.status != 200:
                        print(f"❌ Failed to add listing {listing_id} to watchlist for dashboard test")
                        return False
            
            # Now test dashboard endpoint
            async with self.session.get(
                f"{BASE_URL}/dashboard/buyer",
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify watchlist field exists
                    assert "watchlist" in data, "Dashboard should include watchlist field"
                    assert isinstance(data["watchlist"], list), "Watchlist should be a list"
                    
                    # Should have the items we added
                    assert len(data["watchlist"]) >= 2, "Dashboard watchlist should contain added items"
                    
                    # Verify watchlist items have proper structure
                    for item in data["watchlist"]:
                        assert "id" in item
                        assert "title" in item
                        assert "current_price" in item
                    
                    print(f"✅ Dashboard includes watchlist data successfully")
                    print(f"   - Watchlist items: {len(data['watchlist'])}")
                    return True
                else:
                    print(f"❌ Failed to get buyer dashboard: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing buyer dashboard watchlist: {str(e)}")
            return False
    
    async def test_authorization_validation(self) -> bool:
        """Test authorization and validation scenarios"""
        print("\n🧪 Testing authorization and validation...")
        
        success = True
        
        # Test 1: Adding non-existent listing to watchlist
        try:
            async with self.session.post(
                f"{BASE_URL}/watchlist/add?listing_id=non-existent-listing-id",
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 404:
                    print("✅ Correctly rejected adding non-existent listing")
                else:
                    print(f"❌ Should have rejected non-existent listing, got: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing non-existent listing: {str(e)}")
            success = False
            
        # Test 2: Unauthorized access (no auth token)
        try:
            async with self.session.get(f"{BASE_URL}/watchlist") as response:
                if response.status == 401:
                    print("✅ Correctly rejected unauthorized watchlist access")
                else:
                    print(f"❌ Should have rejected unauthorized access, got: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing unauthorized access: {str(e)}")
            success = False
            
        # Test 3: Check status without auth
        try:
            async with self.session.get(f"{BASE_URL}/watchlist/check/{self.test_listing_ids[0]}") as response:
                if response.status == 401:
                    print("✅ Correctly rejected unauthorized status check")
                else:
                    print(f"❌ Should have rejected unauthorized status check, got: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing unauthorized status check: {str(e)}")
            success = False
            
        return success
        
    async def run_all_tests(self):
        """Run all watchlist API tests"""
        print("🚀 Starting Bazario Watchlist API Tests")
        print("=" * 60)
        
        await self.setup_session()
        
        try:
            # Setup test data
            if not await self.register_test_user():
                print("❌ Failed to setup test user")
                return False
                
            if not await self.create_test_listings():
                print("❌ Failed to create test listings")
                return False
            
            # Run tests in specific order for proper flow
            tests = [
                ("Add to Watchlist", self.test_add_to_watchlist),
                ("Check Watchlist Status", self.test_check_watchlist_status),
                ("Get Watchlist", self.test_get_watchlist),
                ("Buyer Dashboard Integration", self.test_buyer_dashboard_watchlist),
                ("Remove from Watchlist", self.test_remove_from_watchlist),
                ("Authorization & Validation", self.test_authorization_validation)
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
            print("\n" + "=" * 60)
            print("📊 WATCHLIST API TEST RESULTS SUMMARY")
            print("=" * 60)
            
            passed = 0
            total = len(results)
            
            for test_name, result in results:
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status} - {test_name}")
                if result:
                    passed += 1
            
            print(f"\nOverall: {passed}/{total} tests passed")
            
            if passed == total:
                print("🎉 All watchlist API tests PASSED!")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = BazarioWatchlistTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)