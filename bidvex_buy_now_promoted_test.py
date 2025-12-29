#!/usr/bin/env python3
"""
BidVex Buy Now and Promoted Listings Testing
Tests the Buy Now purchase flow and promoted listings features as specified in the review request.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://auction-house-2.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@bazario.com"
ADMIN_PASSWORD = "Admin123!"
TEST_USER_EMAIL = "buynowtester@bazario.com"
TEST_USER_PASSWORD = "BuyNowTest123!"

class BidVexBuyNowTester:
    def __init__(self):
        self.session = None
        self.admin_token = None
        self.admin_id = None
        self.user_token = None
        self.user_id = None
        self.test_auction_id = None
        self.test_results = {}
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def login_admin(self) -> bool:
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
                    print(f"✅ Admin logged in successfully: {self.admin_id}")
                    return True
                else:
                    print(f"❌ Failed to login admin: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in admin: {str(e)}")
            return False
            
    async def setup_test_user(self) -> bool:
        """Setup test user for Buy Now testing"""
        try:
            # Try to register test user
            user_data = {
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "name": "Buy Now Tester",
                "account_type": "personal",
                "phone": "+1234567890"
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
        
    async def create_test_auction_with_promotion(self) -> bool:
        """Create a test multi-item auction with promotion and Buy Now enabled"""
        print("\n🧪 Creating test auction with promotion and Buy Now...")
        
        try:
            # Create auction with promotion_tier and buy_now enabled lots
            auction_data = {
                "title": "BidVex Buy Now Test Auction",
                "description": "Test auction for Buy Now and promotion features",
                "category": "Electronics",
                "location": "Test Location",
                "city": "Toronto",
                "region": "ON",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "promotion_tier": "premium",
                "is_promoted": True,
                "lots": [
                    {
                        "lot_number": 1,
                        "title": "Test Item 1",
                        "description": "Test item with Buy Now enabled",
                        "quantity": 5,
                        "starting_price": 10.0,
                        "current_price": 10.0,
                        "condition": "new",
                        "images": [],
                        "pricing_mode": "fixed",
                        "buy_now_enabled": True,
                        "buy_now_price": 25.0,
                        "available_quantity": 5,
                        "sold_quantity": 0,
                        "lot_status": "active"
                    },
                    {
                        "lot_number": 2,
                        "title": "Test Item 2",
                        "description": "Test item without Buy Now",
                        "quantity": 3,
                        "starting_price": 15.0,
                        "current_price": 15.0,
                        "condition": "used",
                        "images": [],
                        "pricing_mode": "fixed",
                        "buy_now_enabled": False,
                        "available_quantity": 3,
                        "sold_quantity": 0,
                        "lot_status": "active"
                    }
                ]
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=auction_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_auction_id = data["id"]
                    print(f"✅ Test auction created successfully: {self.test_auction_id}")
                    print(f"   - Promotion tier: {data.get('promotion_tier')}")
                    print(f"   - Is promoted: {data.get('is_promoted')}")
                    print(f"   - Lots with Buy Now: {sum(1 for lot in data.get('lots', []) if lot.get('buy_now_enabled'))}")
                    return True
                else:
                    print(f"❌ Failed to create test auction: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error creating test auction: {str(e)}")
            return False
            
    async def test_buy_now_purchase_flow(self) -> bool:
        """Test the Buy Now purchase endpoint"""
        print("\n🧪 Testing Buy Now Purchase Flow...")
        
        try:
            # Test 1: Purchase with valid auction and lot
            print("   Test 1: Valid Buy Now purchase...")
            purchase_data = {
                "auction_id": self.test_auction_id,
                "lot_number": 1,
                "quantity": 1
            }
            
            async with self.session.post(
                f"{BASE_URL}/buy-now",
                json=purchase_data,
                headers=self.get_user_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    required_fields = ["success", "transaction_id", "total_amount", "available_quantity", "conversation_id"]
                    for field in required_fields:
                        assert field in data, f"Missing required field: {field}"
                    
                    assert data["success"] is True
                    assert data["total_amount"] == 25.0  # buy_now_price * quantity
                    assert data["available_quantity"] == 4  # 5 - 1 purchased
                    assert data["conversation_id"] is not None  # Automated handshake
                    
                    print(f"✅ Valid Buy Now purchase successful")
                    print(f"   - Transaction ID: {data['transaction_id']}")
                    print(f"   - Total amount: ${data['total_amount']}")
                    print(f"   - Remaining quantity: {data['available_quantity']}")
                    print(f"   - Conversation ID: {data['conversation_id']}")
                else:
                    print(f"❌ Valid Buy Now purchase failed: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Purchase with non-existent auction (should return 404)
            print("   Test 2: Non-existent auction...")
            purchase_data = {
                "auction_id": "non-existent-auction",
                "lot_number": 1,
                "quantity": 1
            }
            
            async with self.session.post(
                f"{BASE_URL}/buy-now",
                json=purchase_data,
                headers=self.get_user_headers()
            ) as response:
                if response.status == 404:
                    data = await response.json()
                    assert "Auction not found" in data.get("detail", "")
                    print(f"✅ Correctly returned 404 for non-existent auction")
                else:
                    print(f"❌ Should have returned 404 for non-existent auction, got: {response.status}")
                    return False
            
            # Test 3: Purchase lot without Buy Now enabled
            print("   Test 3: Lot without Buy Now enabled...")
            purchase_data = {
                "auction_id": self.test_auction_id,
                "lot_number": 2,  # This lot has buy_now_enabled: False
                "quantity": 1
            }
            
            async with self.session.post(
                f"{BASE_URL}/buy-now",
                json=purchase_data,
                headers=self.get_user_headers()
            ) as response:
                if response.status == 400:
                    data = await response.json()
                    assert "Buy Now not available for this lot" in data.get("detail", "")
                    print(f"✅ Correctly rejected lot without Buy Now enabled")
                else:
                    print(f"❌ Should have rejected lot without Buy Now, got: {response.status}")
                    return False
            
            # Test 4: Purchase more quantity than available
            print("   Test 4: Excessive quantity...")
            purchase_data = {
                "auction_id": self.test_auction_id,
                "lot_number": 1,
                "quantity": 10  # More than available (4 remaining)
            }
            
            async with self.session.post(
                f"{BASE_URL}/buy-now",
                json=purchase_data,
                headers=self.get_user_headers()
            ) as response:
                if response.status == 400:
                    data = await response.json()
                    assert "units available" in data.get("detail", "")
                    print(f"✅ Correctly rejected excessive quantity")
                else:
                    print(f"❌ Should have rejected excessive quantity, got: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing Buy Now purchase flow: {str(e)}")
            return False
            
    async def test_promoted_listings_endpoints(self) -> bool:
        """Test promoted listings endpoints"""
        print("\n🧪 Testing Promoted Listings Endpoints...")
        
        try:
            # Test 1: GET /api/promoted-listings (public endpoint)
            print("   Test 1: GET /api/promoted-listings...")
            async with self.session.get(f"{BASE_URL}/promoted-listings") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "listings" in data
                    assert "total" in data
                    assert isinstance(data["listings"], list)
                    assert isinstance(data["total"], int)
                    
                    print(f"✅ Promoted listings endpoint working")
                    print(f"   - Total promoted listings: {data['total']}")
                    print(f"   - Listings returned: {len(data['listings'])}")
                    
                    # If we have listings, verify structure
                    if len(data["listings"]) > 0:
                        listing = data["listings"][0]
                        assert "id" in listing
                        assert "title" in listing
                        assert "is_promoted" in listing
                        assert listing["is_promoted"] is True
                        print(f"   - First listing: {listing.get('title', 'N/A')}")
                        print(f"   - Promotion tier: {listing.get('promotion_tier', 'N/A')}")
                else:
                    print(f"❌ Promoted listings endpoint failed: {response.status}")
                    return False
            
            # Test 2: GET /api/promoted-listings with tier filter
            print("   Test 2: GET /api/promoted-listings?tier=premium...")
            async with self.session.get(f"{BASE_URL}/promoted-listings?tier=premium") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify all returned listings have premium tier
                    for listing in data["listings"]:
                        if listing.get("promotion_tier"):
                            assert listing["promotion_tier"] == "premium"
                    
                    print(f"✅ Tier filtering working correctly")
                    print(f"   - Premium listings: {len(data['listings'])}")
                else:
                    print(f"❌ Tier filtering failed: {response.status}")
                    return False
            
            # Test 3: Empty result when no promoted listings
            print("   Test 3: Empty promoted listings response structure...")
            async with self.session.get(f"{BASE_URL}/promoted-listings?tier=nonexistent") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Should return empty structure
                    assert data["listings"] == []
                    assert data["total"] == 0
                    
                    print(f"✅ Empty promoted listings structure correct")
                else:
                    print(f"❌ Empty promoted listings test failed: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing promoted listings endpoints: {str(e)}")
            return False
            
    async def test_admin_listings_promotions(self) -> bool:
        """Test admin listings promotions endpoint"""
        print("\n🧪 Testing Admin Listings Promotions Endpoint...")
        
        try:
            # Test 1: GET /api/admin/listings-promotions (admin only)
            print("   Test 1: Admin access to listings promotions...")
            async with self.session.get(
                f"{BASE_URL}/admin/listings-promotions",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "listings" in data
                    assert "stats" in data
                    assert isinstance(data["listings"], list)
                    assert isinstance(data["stats"], dict)
                    
                    # Verify stats structure
                    stats = data["stats"]
                    required_stats = ["total_promoted", "premium_count", "elite_count", "promotion_revenue"]
                    for stat in required_stats:
                        assert stat in stats, f"Missing stat: {stat}"
                    
                    print(f"✅ Admin listings promotions endpoint working")
                    print(f"   - Total listings: {len(data['listings'])}")
                    print(f"   - Total promoted: {stats['total_promoted']}")
                    print(f"   - Premium count: {stats['premium_count']}")
                    print(f"   - Elite count: {stats['elite_count']}")
                    print(f"   - Promotion revenue: ${stats['promotion_revenue']}")
                    
                    # Verify listing structure if we have listings
                    if len(data["listings"]) > 0:
                        listing = data["listings"][0]
                        expected_fields = ["id", "title", "seller_id", "status", "is_promoted"]
                        for field in expected_fields:
                            assert field in listing, f"Missing listing field: {field}"
                        print(f"   - First listing: {listing.get('title', 'N/A')}")
                        print(f"   - Seller: {listing.get('seller_name', 'N/A')}")
                else:
                    print(f"❌ Admin listings promotions failed: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Non-admin access should be denied
            print("   Test 2: Non-admin access denial...")
            async with self.session.get(
                f"{BASE_URL}/admin/listings-promotions",
                headers=self.get_user_headers()  # Regular user token
            ) as response:
                if response.status == 403:
                    data = await response.json()
                    assert "Admin access required" in data.get("detail", "")
                    print(f"✅ Correctly denied non-admin access")
                else:
                    print(f"❌ Should have denied non-admin access, got: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing admin listings promotions: {str(e)}")
            return False
            
    async def test_multi_item_listing_with_promotion(self) -> bool:
        """Test creating multi-item listing with promotion fields"""
        print("\n🧪 Testing Multi-Item Listing Creation with Promotion...")
        
        try:
            # Test creating listing with promotion_tier and buy_now fields
            listing_data = {
                "title": "Promotion Test Auction",
                "description": "Testing promotion tier and buy now features",
                "category": "Art",
                "location": "Test City",
                "city": "Montreal",
                "region": "QC",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
                "promotion_tier": "elite",
                "is_promoted": True,
                "lots": [
                    {
                        "lot_number": 1,
                        "title": "Elite Promoted Item",
                        "description": "Item with elite promotion",
                        "quantity": 2,
                        "starting_price": 50.0,
                        "current_price": 50.0,
                        "condition": "excellent",
                        "images": [],
                        "pricing_mode": "fixed",
                        "buy_now_enabled": True,
                        "buy_now_price": 100.0,
                        "available_quantity": 2,
                        "sold_quantity": 0,
                        "lot_status": "active"
                    }
                ]
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify promotion fields are set correctly
                    assert data["promotion_tier"] == "elite"
                    assert data["is_promoted"] is True
                    assert data["promotion_start"] is not None
                    assert data["promotion_end"] is not None
                    
                    # Verify lot has buy_now fields
                    lot = data["lots"][0]
                    assert lot["buy_now_enabled"] is True
                    assert lot["buy_now_price"] == 100.0
                    
                    print(f"✅ Multi-item listing with promotion created successfully")
                    print(f"   - Listing ID: {data['id']}")
                    print(f"   - Promotion tier: {data['promotion_tier']}")
                    print(f"   - Promotion start: {data['promotion_start']}")
                    print(f"   - Promotion end: {data['promotion_end']}")
                    print(f"   - Buy Now enabled: {lot['buy_now_enabled']}")
                    print(f"   - Buy Now price: ${lot['buy_now_price']}")
                    
                    return True
                else:
                    print(f"❌ Failed to create listing with promotion: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing multi-item listing with promotion: {str(e)}")
            return False
            
    async def run_all_tests(self):
        """Run all BidVex Buy Now and Promoted Listings tests"""
        print("🚀 Starting BidVex Buy Now and Promoted Listings Tests")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Setup authentication
            if not await self.login_admin():
                print("❌ Failed to login admin")
                return False
                
            if not await self.setup_test_user():
                print("❌ Failed to setup test user")
                return False
            
            # Create test auction for Buy Now testing
            if not await self.create_test_auction_with_promotion():
                print("❌ Failed to create test auction")
                return False
            
            # Run tests in order
            tests = [
                ("Buy Now Purchase Flow", self.test_buy_now_purchase_flow),
                ("Promoted Listings Endpoints", self.test_promoted_listings_endpoints),
                ("Admin Listings Promotions", self.test_admin_listings_promotions),
                ("Multi-Item Listing with Promotion", self.test_multi_item_listing_with_promotion)
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
            print("📊 BIDVEX BUY NOW & PROMOTED LISTINGS TEST RESULTS")
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
                print("🎉 All BidVex Buy Now and Promoted Listings tests PASSED!")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = BidVexBuyNowTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)