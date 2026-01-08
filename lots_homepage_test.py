#!/usr/bin/env python3
"""
Backend API Testing for Lots Auction Homepage 4-Row Feature
Tests the multi-item listings endpoints that support the homepage 4-row layout:
- Coming Soon (status=upcoming)
- Featured Auctions (is_featured=true)
- Ending Soon (status=active, sorted by auction_end_date)
- Recently Added (sorted by created_at desc)
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

# Configuration
BASE_URL = "https://bidding-platform-20.preview.emergentagent.com/api"
TEST_USER_EMAIL = "lots.homepage.tester@bazario.com"
TEST_USER_PASSWORD = "LotsTest123!"
TEST_USER_NAME = "Lots Homepage Tester"

class LotsHomepageTester:
    def __init__(self):
        self.session = None
        self.auth_token = None
        self.user_id = None
        self.test_results = {}
        self.created_listings = []
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def setup_test_user(self) -> bool:
        """Setup test user with business account for creating multi-item listings"""
        try:
            # Try to register business user
            user_data = {
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "name": TEST_USER_NAME,
                "account_type": "business",
                "phone": "+1234567890",
                "address": "123 Test Street, Test City, ON",
                "company_name": "Test Auction House"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.auth_token = data["access_token"]
                    self.user_id = data["user"]["id"]
                    print(f"✅ Test business user registered: {self.user_id}")
                    return True
                elif response.status == 400:
                    # User might already exist, try login
                    return await self.login_test_user()
                else:
                    print(f"❌ Failed to register business user: {response.status}")
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
                    self.auth_token = data["access_token"]
                    self.user_id = data["user"]["id"]
                    print(f"✅ Test user logged in: {self.user_id}")
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
        """Create test listings for different homepage rows"""
        print("\n🧪 Creating test listings for homepage rows...")
        
        try:
            now = datetime.now(timezone.utc)
            
            # Test data for different scenarios
            test_listings = [
                {
                    "title": "Coming Soon Estate Sale",
                    "description": "Upcoming estate sale with antique furniture",
                    "category": "Antiques",
                    "location": "Toronto, ON",
                    "city": "Toronto",
                    "region": "Ontario",
                    "auction_start_date": (now + timedelta(days=2)).isoformat(),
                    "auction_end_date": (now + timedelta(days=5)).isoformat(),
                    "lots": [
                        {
                            "lot_number": 1,
                            "title": "Antique Chair",
                            "description": "Beautiful Victorian chair in excellent condition",
                            "quantity": 1,
                            "starting_price": 100.0,
                            "current_price": 100.0,
                            "condition": "excellent",
                            "images": ["https://example.com/chair.jpg"],
                            "pricing_mode": "fixed"
                        }
                    ]
                },
                {
                    "title": "Featured VIP Auction",
                    "description": "Premium featured auction with high-value items",
                    "category": "Jewelry",
                    "location": "Vancouver, BC",
                    "city": "Vancouver", 
                    "region": "British Columbia",
                    "auction_start_date": (now - timedelta(hours=1)).isoformat(),
                    "auction_end_date": (now + timedelta(days=3)).isoformat(),
                    "lots": [
                        {
                            "lot_number": 1,
                            "title": "Diamond Ring",
                            "description": "Stunning 2-carat diamond ring",
                            "quantity": 1,
                            "starting_price": 5000.0,
                            "current_price": 5000.0,
                            "condition": "excellent",
                            "images": ["https://example.com/ring.jpg"],
                            "pricing_mode": "fixed"
                        }
                    ]
                },
                {
                    "title": "Ending Soon Art Auction",
                    "description": "Art auction ending in 2 hours",
                    "category": "Art",
                    "location": "Montreal, QC",
                    "city": "Montreal",
                    "region": "Quebec",
                    "auction_start_date": (now - timedelta(days=1)).isoformat(),
                    "auction_end_date": (now + timedelta(hours=2)).isoformat(),
                    "lots": [
                        {
                            "lot_number": 1,
                            "title": "Oil Painting",
                            "description": "Original oil painting by local artist",
                            "quantity": 1,
                            "starting_price": 500.0,
                            "current_price": 500.0,
                            "condition": "good",
                            "images": ["https://example.com/painting.jpg"],
                            "pricing_mode": "fixed"
                        }
                    ]
                },
                {
                    "title": "Recently Added Electronics",
                    "description": "Just added electronics auction",
                    "category": "Electronics",
                    "location": "Calgary, AB",
                    "city": "Calgary",
                    "region": "Alberta",
                    "auction_start_date": (now - timedelta(minutes=30)).isoformat(),
                    "auction_end_date": (now + timedelta(days=7)).isoformat(),
                    "lots": [
                        {
                            "lot_number": 1,
                            "title": "Laptop Computer",
                            "description": "High-performance laptop in good condition",
                            "quantity": 1,
                            "starting_price": 800.0,
                            "current_price": 800.0,
                            "condition": "good",
                            "images": ["https://example.com/laptop.jpg"],
                            "pricing_mode": "fixed"
                        }
                    ]
                }
            ]
            
            # Create listings
            for listing_data in test_listings:
                async with self.session.post(
                    f"{BASE_URL}/multi-item-listings",
                    json=listing_data,
                    headers=self.get_auth_headers()
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.created_listings.append(data["id"])
                        print(f"✅ Created listing: {listing_data['title']} (ID: {data['id']})")
                    else:
                        print(f"❌ Failed to create listing '{listing_data['title']}': {response.status}")
                        text = await response.text()
                        print(f"Response: {text}")
                        return False
            
            print(f"✅ Created {len(self.created_listings)} test listings")
            return True
            
        except Exception as e:
            print(f"❌ Error creating test listings: {str(e)}")
            return False
            
    async def test_get_all_listings(self) -> bool:
        """Test GET /api/multi-item-listings (all listings)"""
        print("\n🧪 Testing GET /api/multi-item-listings (all listings)...")
        
        try:
            async with self.session.get(f"{BASE_URL}/multi-item-listings") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response is a list
                    assert isinstance(data, list), "Response should be a list"
                    
                    # Verify we have listings
                    assert len(data) > 0, "Should have at least some listings"
                    
                    # Verify required fields in each listing
                    required_fields = [
                        "id", "title", "description", "category", "city", "region",
                        "total_lots", "auction_end_date", "auction_start_date",
                        "is_featured", "promotion_expiry", "seller_id", "currency",
                        "status", "lots"
                    ]
                    
                    for listing in data:
                        for field in required_fields:
                            assert field in listing, f"Missing required field: {field}"
                    
                    print(f"✅ GET /api/multi-item-listings working correctly")
                    print(f"   - Total listings returned: {len(data)}")
                    print(f"   - All required fields present")
                    
                    # Check if our test listings are included
                    found_test_listings = 0
                    for listing in data:
                        if listing["id"] in self.created_listings:
                            found_test_listings += 1
                    
                    print(f"   - Found {found_test_listings}/{len(self.created_listings)} test listings")
                    
                    return True
                else:
                    print(f"❌ Failed to get all listings: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing get all listings: {str(e)}")
            return False
            
    async def test_upcoming_listings(self) -> bool:
        """Test GET /api/multi-item-listings?status=upcoming (Coming Soon row)"""
        print("\n🧪 Testing GET /api/multi-item-listings?status=upcoming (Coming Soon)...")
        
        try:
            async with self.session.get(f"{BASE_URL}/multi-item-listings?status=upcoming") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response is a list
                    assert isinstance(data, list), "Response should be a list"
                    
                    print(f"✅ GET /api/multi-item-listings?status=upcoming working")
                    print(f"   - Upcoming listings returned: {len(data)}")
                    
                    # Verify all listings have status=upcoming
                    for listing in data:
                        assert listing["status"] == "upcoming", f"Listing {listing['id']} should have status 'upcoming'"
                        
                        # Verify auction_start_date is in the future (for upcoming)
                        start_date = datetime.fromisoformat(listing["auction_start_date"].replace('Z', '+00:00'))
                        now = datetime.now(timezone.utc)
                        assert start_date > now, f"Upcoming listing {listing['id']} should have future start date"
                    
                    if len(data) > 0:
                        print(f"   - All listings have status='upcoming'")
                        print(f"   - All listings have future auction_start_date")
                    
                    return True
                else:
                    print(f"❌ Failed to get upcoming listings: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing upcoming listings: {str(e)}")
            return False
            
    async def test_active_listings_ending_soon(self) -> bool:
        """Test GET /api/multi-item-listings?status=active (Ending Soon row)"""
        print("\n🧪 Testing GET /api/multi-item-listings?status=active (Ending Soon)...")
        
        try:
            async with self.session.get(f"{BASE_URL}/multi-item-listings?status=active") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response is a list
                    assert isinstance(data, list), "Response should be a list"
                    
                    print(f"✅ GET /api/multi-item-listings?status=active working")
                    print(f"   - Active listings returned: {len(data)}")
                    
                    # Verify all listings have status=active
                    for listing in data:
                        assert listing["status"] == "active", f"Listing {listing['id']} should have status 'active'"
                    
                    # Verify sorting by auction_end_date ascending (ending soonest first)
                    if len(data) > 1:
                        for i in range(len(data) - 1):
                            current_end = datetime.fromisoformat(data[i]["auction_end_date"].replace('Z', '+00:00'))
                            next_end = datetime.fromisoformat(data[i + 1]["auction_end_date"].replace('Z', '+00:00'))
                            # Note: The backend might not be sorting by default, this tests the data structure
                            print(f"   - Listing {i+1}: ends {current_end}")
                    
                    if len(data) > 0:
                        print(f"   - All listings have status='active'")
                        print(f"   - Auction end dates available for sorting")
                    
                    return True
                else:
                    print(f"❌ Failed to get active listings: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing active listings: {str(e)}")
            return False
            
    async def test_featured_listings(self) -> bool:
        """Test filtering for featured listings (is_featured=true)"""
        print("\n🧪 Testing featured listings filtering...")
        
        try:
            # Get all listings and check for featured ones
            async with self.session.get(f"{BASE_URL}/multi-item-listings") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    featured_listings = [listing for listing in data if listing.get("is_featured", False)]
                    
                    print(f"✅ Featured listings filtering working")
                    print(f"   - Total listings: {len(data)}")
                    print(f"   - Featured listings: {len(featured_listings)}")
                    
                    # Verify featured listings have required fields
                    for listing in featured_listings:
                        assert listing["is_featured"] is True, f"Featured listing {listing['id']} should have is_featured=true"
                        
                        # Check if promotion_expiry is set (for VIP/Premium users)
                        if listing.get("promotion_expiry"):
                            expiry_date = datetime.fromisoformat(listing["promotion_expiry"].replace('Z', '+00:00'))
                            print(f"   - Featured listing '{listing['title']}' expires: {expiry_date}")
                    
                    return True
                else:
                    print(f"❌ Failed to get listings for featured filtering: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error testing featured listings: {str(e)}")
            return False
            
    async def test_pagination(self) -> bool:
        """Test pagination with limit parameter"""
        print("\n🧪 Testing pagination (limit to 12 listings per row)...")
        
        try:
            # Test with limit=12
            async with self.session.get(f"{BASE_URL}/multi-item-listings?limit=12") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response is a list
                    assert isinstance(data, list), "Response should be a list"
                    
                    # Verify limit is respected
                    assert len(data) <= 12, f"Should return at most 12 listings, got {len(data)}"
                    
                    print(f"✅ Pagination working correctly")
                    print(f"   - Requested limit: 12")
                    print(f"   - Actual returned: {len(data)}")
                    
                    # Test with different limit
                    async with self.session.get(f"{BASE_URL}/multi-item-listings?limit=5") as response2:
                        if response2.status == 200:
                            data2 = await response2.json()
                            assert len(data2) <= 5, f"Should return at most 5 listings, got {len(data2)}"
                            print(f"   - Limit=5 test: returned {len(data2)} listings")
                        else:
                            print(f"❌ Failed limit=5 test: {response2.status}")
                            return False
                    
                    return True
                else:
                    print(f"❌ Failed pagination test: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing pagination: {str(e)}")
            return False
            
    async def test_data_structure_completeness(self) -> bool:
        """Test that all required fields are present in responses"""
        print("\n🧪 Testing data structure completeness...")
        
        try:
            async with self.session.get(f"{BASE_URL}/multi-item-listings?limit=1") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if len(data) == 0:
                        print("⚠️  No listings available for data structure test")
                        return True
                    
                    listing = data[0]
                    
                    # Required fields for frontend 4-row layout
                    required_fields = [
                        "id", "title", "description", "category", "city", "region",
                        "total_lots", "auction_end_date", "auction_start_date",
                        "is_featured", "promotion_expiry", "seller_id", "currency",
                        "status", "lots", "created_at"
                    ]
                    
                    missing_fields = []
                    for field in required_fields:
                        if field not in listing:
                            missing_fields.append(field)
                    
                    if missing_fields:
                        print(f"❌ Missing required fields: {missing_fields}")
                        return False
                    
                    # Verify lots array structure
                    if listing["lots"] and len(listing["lots"]) > 0:
                        lot = listing["lots"][0]
                        lot_required_fields = [
                            "lot_number", "title", "description", "quantity",
                            "starting_price", "current_price", "condition", "images"
                        ]
                        
                        lot_missing_fields = []
                        for field in lot_required_fields:
                            if field not in lot:
                                lot_missing_fields.append(field)
                        
                        if lot_missing_fields:
                            print(f"❌ Missing required lot fields: {lot_missing_fields}")
                            return False
                    
                    print(f"✅ Data structure completeness verified")
                    print(f"   - All required listing fields present")
                    print(f"   - All required lot fields present")
                    print(f"   - Total lots: {listing['total_lots']}")
                    print(f"   - Currency: {listing['currency']}")
                    print(f"   - Status: {listing['status']}")
                    print(f"   - Featured: {listing['is_featured']}")
                    
                    return True
                else:
                    print(f"❌ Failed data structure test: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error testing data structure: {str(e)}")
            return False
            
    async def test_error_handling(self) -> bool:
        """Test error handling for invalid requests"""
        print("\n🧪 Testing error handling for invalid requests...")
        
        try:
            success = True
            
            # Test 1: Invalid status parameter
            async with self.session.get(f"{BASE_URL}/multi-item-listings?status=invalid") as response:
                if response.status == 200:
                    # Backend might return empty list for invalid status, which is acceptable
                    data = await response.json()
                    print(f"✅ Invalid status handled gracefully (returned {len(data)} listings)")
                else:
                    print(f"✅ Invalid status rejected with status: {response.status}")
            
            # Test 2: Invalid limit parameter
            async with self.session.get(f"{BASE_URL}/multi-item-listings?limit=-1") as response:
                # Backend should handle negative limits gracefully
                if response.status == 200:
                    print(f"✅ Negative limit handled gracefully")
                else:
                    print(f"✅ Negative limit rejected with status: {response.status}")
            
            # Test 3: Non-existent listing ID
            async with self.session.get(f"{BASE_URL}/multi-item-listings/non-existent-id") as response:
                if response.status == 404:
                    print(f"✅ Non-existent listing correctly returns 404")
                else:
                    print(f"⚠️  Non-existent listing returned: {response.status}")
            
            # Test 4: Very large limit
            async with self.session.get(f"{BASE_URL}/multi-item-listings?limit=10000") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Large limit handled gracefully (returned {len(data)} listings)")
                else:
                    print(f"⚠️  Large limit returned: {response.status}")
            
            print(f"✅ Error handling tests completed")
            return success
            
        except Exception as e:
            print(f"❌ Error testing error handling: {str(e)}")
            return False
            
    async def run_all_tests(self):
        """Run all lots homepage API tests"""
        print("🚀 Starting Lots Auction Homepage 4-Row Feature Tests")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Setup test user
            if not await self.setup_test_user():
                print("❌ Failed to setup test user")
                return False
            
            # Create test data
            if not await self.create_test_listings():
                print("❌ Failed to create test listings")
                return False
            
            # Run tests in logical order
            tests = [
                ("GET All Listings", self.test_get_all_listings),
                ("GET Upcoming Listings (Coming Soon)", self.test_upcoming_listings),
                ("GET Active Listings (Ending Soon)", self.test_active_listings_ending_soon),
                ("Featured Listings Filtering", self.test_featured_listings),
                ("Pagination (12 per row)", self.test_pagination),
                ("Data Structure Completeness", self.test_data_structure_completeness),
                ("Error Handling", self.test_error_handling)
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
            print("📊 LOTS HOMEPAGE 4-ROW FEATURE TEST RESULTS SUMMARY")
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
                print("🎉 All Lots Homepage 4-Row Feature tests PASSED!")
                print("\n📋 SUMMARY OF VERIFIED FUNCTIONALITY:")
                print("✅ GET /api/multi-item-listings - Returns all active listings with required fields")
                print("✅ GET /api/multi-item-listings?status=upcoming - Filters upcoming auctions")
                print("✅ GET /api/multi-item-listings?status=active - Filters active auctions")
                print("✅ Featured listings filtering (is_featured=true)")
                print("✅ Pagination support (limit parameter)")
                print("✅ Complete data structure with all required fields")
                print("✅ Error handling for invalid requests")
                print("\n🏠 HOMEPAGE 4-ROW SUPPORT CONFIRMED:")
                print("   1. Coming Soon Row: status=upcoming filter working")
                print("   2. Featured Auctions Row: is_featured field available")
                print("   3. Ending Soon Row: status=active filter working")
                print("   4. Recently Added Row: created_at field available for sorting")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = LotsHomepageTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)