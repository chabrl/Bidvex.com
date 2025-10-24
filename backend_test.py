#!/usr/bin/env python3
"""
Backend API Testing for Bazario Watchlist Features
Tests the complete watchlist functionality including add, remove, get, check status endpoints.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://bid-bazaar-4.preview.emergentagent.com/api"
TEST_USER_EMAIL = "watchlist.tester@bazario.com"
TEST_USER_PASSWORD = "WatchlistTest123!"
TEST_USER_NAME = "Watchlist Tester"

class BazarioWatchlistTester:
    def __init__(self):
        self.session = None
        self.auth_token = None
        self.user_id = None
        self.test_listing_ids = []
        self.test_results = {}
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def register_test_user(self) -> bool:
        """Register a test user for watchlist testing"""
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
                    return True
                elif response.status == 400:
                    # User might already exist, try login
                    return await self.login_test_user()
                else:
                    print(f"❌ Failed to register user: {response.status}")
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
            
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers"""
        return {"Authorization": f"Bearer {self.auth_token}"}
        
    async def create_test_listings(self) -> bool:
        """Create multiple test listings for watchlist testing"""
        try:
            listings_data = [
                {
                    "title": "Vintage Rolex Submariner - Collector's Dream",
                    "description": "Authentic vintage Rolex Submariner from 1970s. Excellent condition with original box and papers.",
                    "category": "Watches",
                    "condition": "excellent",
                    "starting_price": 8500.00,
                    "buy_now_price": 12000.00,
                    "images": ["https://example.com/rolex1.jpg", "https://example.com/rolex2.jpg"],
                    "location": "Downtown Vancouver",
                    "city": "Vancouver",
                    "region": "British Columbia",
                    "latitude": 49.2827,
                    "longitude": -123.1207,
                    "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
                },
                {
                    "title": "MacBook Pro 16-inch M2 Max - Like New",
                    "description": "Barely used MacBook Pro with M2 Max chip, 32GB RAM, 1TB SSD. Perfect for professionals.",
                    "category": "Electronics",
                    "condition": "like_new",
                    "starting_price": 2800.00,
                    "buy_now_price": 3200.00,
                    "images": ["https://example.com/macbook1.jpg", "https://example.com/macbook2.jpg"],
                    "location": "Midtown Toronto",
                    "city": "Toronto",
                    "region": "Ontario",
                    "latitude": 43.6532,
                    "longitude": -79.3832,
                    "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
                },
                {
                    "title": "Antique Persian Rug - Hand Woven Masterpiece",
                    "description": "Beautiful hand-woven Persian rug from the 1920s. Excellent condition with vibrant colors.",
                    "category": "Home & Garden",
                    "condition": "good",
                    "starting_price": 1200.00,
                    "buy_now_price": 2500.00,
                    "images": ["https://example.com/rug1.jpg", "https://example.com/rug2.jpg"],
                    "location": "Old Montreal",
                    "city": "Montreal",
                    "region": "Quebec",
                    "latitude": 45.5017,
                    "longitude": -73.5673,
                    "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
                }
            ]
            
            for i, listing_data in enumerate(listings_data):
                async with self.session.post(
                    f"{BASE_URL}/listings", 
                    json=listing_data,
                    headers=self.get_auth_headers()
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.test_listing_ids.append(data["id"])
                        print(f"✅ Test listing {i+1} created successfully: {data['id']}")
                    else:
                        print(f"❌ Failed to create listing {i+1}: {response.status}")
                        text = await response.text()
                        print(f"Response: {text}")
                        return False
            
            print(f"✅ All {len(self.test_listing_ids)} test listings created successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error creating test listings: {str(e)}")
            return False
            
    async def test_add_to_watchlist(self) -> bool:
        """Test POST /api/watchlist/add endpoint"""
        print("\n🧪 Testing POST /api/watchlist/add...")
        
        try:
            # Test adding valid listing to watchlist
            listing_id = self.test_listing_ids[0]
            
            async with self.session.post(
                f"{BASE_URL}/watchlist/add",
                json={"listing_id": listing_id},
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
                        f"{BASE_URL}/watchlist/add",
                        json={"listing_id": listing_id},
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
            
    async def test_authorization_validation(self) -> bool:
        """Test authorization and validation scenarios"""
        print("\n🧪 Testing authorization and validation...")
        
        success = True
        
        # Test 1: Missing promotion_id in payment request
        try:
            payment_data = {
                "amount": 24.99,
                "origin_url": "https://bid-bazaar-4.preview.emergentagent.com"
            }
            
            async with self.session.post(
                f"{BASE_URL}/payments/promote",
                json=payment_data,
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 400:
                    print("✅ Correctly rejected payment request with missing promotion_id")
                else:
                    print(f"❌ Should have rejected missing promotion_id, got: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing missing promotion_id: {str(e)}")
            success = False
            
        # Test 2: Missing amount in payment request
        try:
            payment_data = {
                "promotion_id": self.test_promotion_id,
                "origin_url": "https://bid-bazaar-4.preview.emergentagent.com"
            }
            
            async with self.session.post(
                f"{BASE_URL}/payments/promote",
                json=payment_data,
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 400:
                    print("✅ Correctly rejected payment request with missing amount")
                else:
                    print(f"❌ Should have rejected missing amount, got: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing missing amount: {str(e)}")
            success = False
            
        # Test 3: Non-existent promotion_id
        try:
            payment_data = {
                "promotion_id": "non-existent-promotion-id",
                "amount": 24.99,
                "origin_url": "https://bid-bazaar-4.preview.emergentagent.com"
            }
            
            async with self.session.post(
                f"{BASE_URL}/payments/promote",
                json=payment_data,
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 404:
                    print("✅ Correctly rejected payment for non-existent promotion")
                else:
                    print(f"❌ Should have rejected non-existent promotion, got: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing non-existent promotion: {str(e)}")
            success = False
            
        return success
        
    async def run_all_tests(self):
        """Run all promotion payment tests"""
        print("🚀 Starting Bazario Promotion Payment API Tests")
        print("=" * 60)
        
        await self.setup_session()
        
        try:
            # Setup test data
            if not await self.register_test_user():
                print("❌ Failed to setup test user")
                return False
                
            if not await self.create_test_listing():
                print("❌ Failed to create test listing")
                return False
            
            # Run tests
            tests = [
                ("Create Promotion", self.test_create_promotion),
                ("Promotion Payment Endpoint", self.test_promotion_payment_endpoint),
                ("Get My Promotions", self.test_get_my_promotions),
                ("Authorization & Validation", self.test_authorization_validation)
            ]
            
            results = []
            for test_name, test_func in tests:
                try:
                    result = await test_func()
                    results.append((test_name, result))
                except Exception as e:
                    print(f"❌ {test_name} failed with exception: {str(e)}")
                    results.append((test_name, False))
            
            # Print summary
            print("\n" + "=" * 60)
            print("📊 TEST RESULTS SUMMARY")
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
                print("🎉 All promotion payment tests PASSED!")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = BazarioAPITester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)