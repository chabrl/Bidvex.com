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
        
    async def create_test_listing(self) -> bool:
        """Create a test listing for promotion testing"""
        try:
            listing_data = {
                "title": "Premium Vintage Watch for Promotion Testing",
                "description": "A beautiful vintage watch perfect for testing promotion features. High-quality timepiece with leather strap.",
                "category": "Fashion",
                "condition": "excellent",
                "starting_price": 299.99,
                "buy_now_price": 499.99,
                "images": ["https://example.com/watch1.jpg", "https://example.com/watch2.jpg"],
                "location": "Downtown Toronto",
                "city": "Toronto",
                "region": "Ontario",
                "latitude": 43.6532,
                "longitude": -79.3832,
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
            }
            
            async with self.session.post(
                f"{BASE_URL}/listings", 
                json=listing_data,
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_listing_id = data["id"]
                    print(f"✅ Test listing created successfully: {self.test_listing_id}")
                    return True
                else:
                    print(f"❌ Failed to create listing: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error creating listing: {str(e)}")
            return False
            
    async def test_create_promotion(self) -> bool:
        """Test POST /api/promotions endpoint"""
        print("\n🧪 Testing POST /api/promotions...")
        
        try:
            promotion_data = {
                "listing_id": self.test_listing_id,
                "promotion_type": "standard",
                "price": 24.99,
                "end_date": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
                "targeting": {
                    "location": "Toronto",
                    "age_range": "25-45",
                    "interests": ["fashion", "watches", "luxury"]
                }
            }
            
            async with self.session.post(
                f"{BASE_URL}/promotions",
                json=promotion_data,
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_promotion_id = data["id"]
                    
                    # Verify promotion data
                    assert data["listing_id"] == self.test_listing_id
                    assert data["seller_id"] == self.user_id
                    assert data["promotion_type"] == "standard"
                    assert data["price"] == 24.99
                    assert data["status"] == "pending"
                    assert data["payment_status"] == "pending"
                    assert "id" in data
                    
                    print(f"✅ Promotion created successfully: {self.test_promotion_id}")
                    print(f"   - Status: {data['status']}")
                    print(f"   - Price: ${data['price']}")
                    print(f"   - Type: {data['promotion_type']}")
                    return True
                else:
                    print(f"❌ Failed to create promotion: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing promotion creation: {str(e)}")
            return False
            
    async def test_promotion_payment_endpoint(self) -> bool:
        """Test POST /api/payments/promote endpoint"""
        print("\n🧪 Testing POST /api/payments/promote...")
        
        try:
            payment_data = {
                "promotion_id": self.test_promotion_id,
                "amount": 24.99,
                "origin_url": "https://bid-bazaar-4.preview.emergentagent.com"
            }
            
            async with self.session.post(
                f"{BASE_URL}/payments/promote",
                json=payment_data,
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "url" in data
                    assert "session_id" in data
                    assert data["url"].startswith("https://checkout.stripe.com")
                    
                    print(f"✅ Promotion payment checkout created successfully")
                    print(f"   - Session ID: {data['session_id']}")
                    print(f"   - Checkout URL: {data['url'][:50]}...")
                    return True
                else:
                    print(f"❌ Failed to create promotion payment: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing promotion payment: {str(e)}")
            return False
            
    async def test_get_my_promotions(self) -> bool:
        """Test GET /api/promotions/my endpoint"""
        print("\n🧪 Testing GET /api/promotions/my...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/promotions/my",
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response is a list
                    assert isinstance(data, list)
                    
                    # Find our test promotion
                    test_promotion = None
                    for promotion in data:
                        if promotion["id"] == self.test_promotion_id:
                            test_promotion = promotion
                            break
                    
                    assert test_promotion is not None, "Test promotion not found in user's promotions"
                    assert test_promotion["seller_id"] == self.user_id
                    assert test_promotion["listing_id"] == self.test_listing_id
                    
                    print(f"✅ My promotions retrieved successfully")
                    print(f"   - Total promotions: {len(data)}")
                    print(f"   - Test promotion found: {test_promotion['id']}")
                    return True
                else:
                    print(f"❌ Failed to get my promotions: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing my promotions: {str(e)}")
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