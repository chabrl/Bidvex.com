#!/usr/bin/env python3
"""
Unified Watchlist System Backend API Testing
Tests the complete watchlist functionality including add, remove, and fetch operations
for listings, auctions, and lots.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

# Configuration
BASE_URL = "https://bidding-platform-14.preview.emergentagent.com/api"
TEST_USER_EMAIL = "lots.homepage.tester@bazario.com"
TEST_USER_PASSWORD = "LotsTest123!"

class WatchlistTester:
    def __init__(self):
        self.session = None
        self.auth_token = None
        self.user_id = None
        self.test_results = {}
        self.test_listing_id = None
        self.test_auction_id = None
        self.test_lot_id = None
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
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
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in user: {str(e)}")
            return False
            
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers"""
        return {"Authorization": f"Bearer {self.auth_token}"}
        
    async def find_test_data(self) -> bool:
        """Find active marketplace listing and multi-lot auction for testing"""
        print("\n🔍 Finding test data...")
        
        try:
            # Find an active marketplace listing
            async with self.session.get(f"{BASE_URL}/listings?limit=1") as response:
                if response.status == 200:
                    listings = await response.json()
                    if listings:
                        self.test_listing_id = listings[0]["id"]
                        print(f"✅ Found test listing: {self.test_listing_id}")
                    else:
                        print("⚠️  No active listings found")
                else:
                    print(f"❌ Failed to fetch listings: {response.status}")
                    return False
            
            # Find an active multi-lot auction
            async with self.session.get(f"{BASE_URL}/multi-item-listings?limit=1") as response:
                if response.status == 200:
                    auctions = await response.json()
                    if auctions:
                        auction = auctions[0]
                        self.test_auction_id = auction["id"]
                        # Use the first lot for lot testing
                        if auction.get("lots") and len(auction["lots"]) > 0:
                            lot_number = auction["lots"][0]["lot_number"]
                            self.test_lot_id = f"{self.test_auction_id}:{lot_number}"
                            print(f"✅ Found test auction: {self.test_auction_id}")
                            print(f"✅ Found test lot: {self.test_lot_id}")
                        else:
                            print("⚠️  Auction has no lots")
                    else:
                        print("⚠️  No active auctions found")
                else:
                    print(f"❌ Failed to fetch auctions: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error finding test data: {str(e)}")
            return False
    
    async def test_add_listing_to_watchlist(self) -> bool:
        """Test POST /api/watchlist/add - Add marketplace listing"""
        print("\n🧪 Testing POST /api/watchlist/add (marketplace listing)...")
        
        if not self.test_listing_id:
            print("⏭️  Skipping - no test listing available")
            return True
            
        try:
            # Test adding a marketplace listing
            async with self.session.post(
                f"{BASE_URL}/watchlist/add",
                params={
                    "item_id": self.test_listing_id,
                    "item_type": "listing"
                },
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    assert "success" in data
                    assert data["success"] is True
                    print(f"✅ Successfully added listing to watchlist")
                    print(f"   - Message: {data.get('message', 'N/A')}")
                    return True
                else:
                    print(f"❌ Failed to add listing to watchlist: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing add listing to watchlist: {str(e)}")
            return False
    
    async def test_add_auction_to_watchlist(self) -> bool:
        """Test POST /api/watchlist/add - Add multi-lot auction"""
        print("\n🧪 Testing POST /api/watchlist/add (multi-lot auction)...")
        
        if not self.test_auction_id:
            print("⏭️  Skipping - no test auction available")
            return True
            
        try:
            # Test adding a multi-lot auction
            async with self.session.post(
                f"{BASE_URL}/watchlist/add",
                params={
                    "item_id": self.test_auction_id,
                    "item_type": "auction"
                },
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    assert "success" in data
                    assert data["success"] is True
                    print(f"✅ Successfully added auction to watchlist")
                    print(f"   - Message: {data.get('message', 'N/A')}")
                    return True
                else:
                    print(f"❌ Failed to add auction to watchlist: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing add auction to watchlist: {str(e)}")
            return False
    
    async def test_add_lot_to_watchlist(self) -> bool:
        """Test POST /api/watchlist/add - Add individual lot"""
        print("\n🧪 Testing POST /api/watchlist/add (individual lot)...")
        
        if not self.test_lot_id:
            print("⏭️  Skipping - no test lot available")
            return True
            
        try:
            # Test adding an individual lot
            async with self.session.post(
                f"{BASE_URL}/watchlist/add",
                params={
                    "item_id": self.test_lot_id,
                    "item_type": "lot"
                },
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    assert "success" in data
                    assert data["success"] is True
                    print(f"✅ Successfully added lot to watchlist")
                    print(f"   - Message: {data.get('message', 'N/A')}")
                    return True
                else:
                    print(f"❌ Failed to add lot to watchlist: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing add lot to watchlist: {str(e)}")
            return False
    
    async def test_duplicate_prevention(self) -> bool:
        """Test duplicate prevention - adding same item twice"""
        print("\n🧪 Testing duplicate prevention...")
        
        if not self.test_listing_id:
            print("⏭️  Skipping - no test listing available")
            return True
            
        try:
            # Try to add the same listing again
            async with self.session.post(
                f"{BASE_URL}/watchlist/add",
                params={
                    "item_id": self.test_listing_id,
                    "item_type": "listing"
                },
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("already_added") is True:
                        print(f"✅ Correctly detected duplicate item")
                        print(f"   - Message: {data.get('message', 'N/A')}")
                        return True
                    else:
                        print(f"❌ Should have detected duplicate, got: {data}")
                        return False
                else:
                    print(f"❌ Failed duplicate prevention test: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing duplicate prevention: {str(e)}")
            return False
    
    async def test_authentication_requirement(self) -> bool:
        """Test authentication requirement (401 without token)"""
        print("\n🧪 Testing authentication requirement...")
        
        try:
            # Try to add to watchlist without authentication
            async with self.session.post(
                f"{BASE_URL}/watchlist/add",
                params={
                    "item_id": "test-id",
                    "item_type": "listing"
                }
            ) as response:
                if response.status == 401:
                    print(f"✅ Correctly rejected unauthenticated request")
                    return True
                else:
                    print(f"❌ Should have returned 401, got: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing authentication requirement: {str(e)}")
            return False
    
    async def test_validation_errors(self) -> bool:
        """Test validation (invalid item_type, non-existent items)"""
        print("\n🧪 Testing validation errors...")
        
        success = True
        
        try:
            # Test invalid item_type
            async with self.session.post(
                f"{BASE_URL}/watchlist/add",
                params={
                    "item_id": "test-id",
                    "item_type": "invalid_type"
                },
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 400:
                    data = await response.json()
                    if "Invalid item_type" in data.get("detail", ""):
                        print(f"✅ Correctly rejected invalid item_type")
                    else:
                        print(f"❌ Wrong error message for invalid item_type: {data.get('detail')}")
                        success = False
                else:
                    print(f"❌ Should have returned 400 for invalid item_type, got: {response.status}")
                    success = False
            
            # Test non-existent listing
            async with self.session.post(
                f"{BASE_URL}/watchlist/add",
                params={
                    "item_id": "non-existent-listing-id",
                    "item_type": "listing"
                },
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 404:
                    data = await response.json()
                    if "not found" in data.get("detail", "").lower():
                        print(f"✅ Correctly rejected non-existent listing")
                    else:
                        print(f"❌ Wrong error message for non-existent listing: {data.get('detail')}")
                        success = False
                else:
                    print(f"❌ Should have returned 404 for non-existent listing, got: {response.status}")
                    success = False
            
            # Test non-existent auction
            async with self.session.post(
                f"{BASE_URL}/watchlist/add",
                params={
                    "item_id": "non-existent-auction-id",
                    "item_type": "auction"
                },
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 404:
                    data = await response.json()
                    if "not found" in data.get("detail", "").lower():
                        print(f"✅ Correctly rejected non-existent auction")
                    else:
                        print(f"❌ Wrong error message for non-existent auction: {data.get('detail')}")
                        success = False
                else:
                    print(f"❌ Should have returned 404 for non-existent auction, got: {response.status}")
                    success = False
            
            return success
                    
        except Exception as e:
            print(f"❌ Error testing validation errors: {str(e)}")
            return False
    
    async def test_remove_from_watchlist(self) -> bool:
        """Test POST /api/watchlist/remove - Remove items from watchlist"""
        print("\n🧪 Testing POST /api/watchlist/remove...")
        
        success = True
        
        try:
            # Remove listing if we have one
            if self.test_listing_id:
                async with self.session.post(
                    f"{BASE_URL}/watchlist/remove",
                    params={
                        "item_id": self.test_listing_id,
                        "item_type": "listing"
                    },
                    headers=self.get_auth_headers()
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        assert "success" in data
                        assert data["success"] is True
                        print(f"✅ Successfully removed listing from watchlist")
                    else:
                        print(f"❌ Failed to remove listing: {response.status}")
                        success = False
            
            # Remove auction if we have one
            if self.test_auction_id:
                async with self.session.post(
                    f"{BASE_URL}/watchlist/remove",
                    params={
                        "item_id": self.test_auction_id,
                        "item_type": "auction"
                    },
                    headers=self.get_auth_headers()
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        assert "success" in data
                        assert data["success"] is True
                        print(f"✅ Successfully removed auction from watchlist")
                    else:
                        print(f"❌ Failed to remove auction: {response.status}")
                        success = False
            
            # Remove lot if we have one
            if self.test_lot_id:
                async with self.session.post(
                    f"{BASE_URL}/watchlist/remove",
                    params={
                        "item_id": self.test_lot_id,
                        "item_type": "lot"
                    },
                    headers=self.get_auth_headers()
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        assert "success" in data
                        assert data["success"] is True
                        print(f"✅ Successfully removed lot from watchlist")
                    else:
                        print(f"❌ Failed to remove lot: {response.status}")
                        success = False
            
            # Test removing non-existent item (should return success: false)
            async with self.session.post(
                f"{BASE_URL}/watchlist/remove",
                params={
                    "item_id": "non-existent-item",
                    "item_type": "listing"
                },
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success") is False:
                        print(f"✅ Correctly returned success: false for non-existent item")
                    else:
                        print(f"❌ Should have returned success: false, got: {data}")
                        success = False
                else:
                    print(f"❌ Failed to handle non-existent item removal: {response.status}")
                    success = False
            
            return success
                    
        except Exception as e:
            print(f"❌ Error testing remove from watchlist: {str(e)}")
            return False
    
    async def test_get_empty_watchlist(self) -> bool:
        """Test GET /api/watchlist - Fetch empty watchlist"""
        print("\n🧪 Testing GET /api/watchlist (empty watchlist)...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/watchlist",
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify structure
                    required_fields = ["listings", "auctions", "lots", "total"]
                    for field in required_fields:
                        assert field in data, f"Missing field: {field}"
                    
                    # Should be empty
                    assert isinstance(data["listings"], list)
                    assert isinstance(data["auctions"], list)
                    assert isinstance(data["lots"], list)
                    assert data["total"] == 0
                    
                    print(f"✅ Empty watchlist structure correct")
                    print(f"   - Listings: {len(data['listings'])}")
                    print(f"   - Auctions: {len(data['auctions'])}")
                    print(f"   - Lots: {len(data['lots'])}")
                    print(f"   - Total: {data['total']}")
                    
                    return True
                else:
                    print(f"❌ Failed to get watchlist: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing empty watchlist: {str(e)}")
            return False
    
    async def test_get_mixed_watchlist(self) -> bool:
        """Test GET /api/watchlist - Fetch watchlist with mixed items"""
        print("\n🧪 Testing GET /api/watchlist (mixed items)...")
        
        try:
            # First, add items back to watchlist for testing
            items_added = []
            
            if self.test_listing_id:
                async with self.session.post(
                    f"{BASE_URL}/watchlist/add",
                    params={"item_id": self.test_listing_id, "item_type": "listing"},
                    headers=self.get_auth_headers()
                ) as response:
                    if response.status == 200:
                        items_added.append("listing")
            
            if self.test_auction_id:
                async with self.session.post(
                    f"{BASE_URL}/watchlist/add",
                    params={"item_id": self.test_auction_id, "item_type": "auction"},
                    headers=self.get_auth_headers()
                ) as response:
                    if response.status == 200:
                        items_added.append("auction")
            
            if self.test_lot_id:
                async with self.session.post(
                    f"{BASE_URL}/watchlist/add",
                    params={"item_id": self.test_lot_id, "item_type": "lot"},
                    headers=self.get_auth_headers()
                ) as response:
                    if response.status == 200:
                        items_added.append("lot")
            
            # Now fetch the watchlist
            async with self.session.get(
                f"{BASE_URL}/watchlist",
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify structure
                    required_fields = ["listings", "auctions", "lots", "total"]
                    for field in required_fields:
                        assert field in data, f"Missing field: {field}"
                    
                    print(f"✅ Mixed watchlist retrieved successfully")
                    print(f"   - Listings: {len(data['listings'])}")
                    print(f"   - Auctions: {len(data['auctions'])}")
                    print(f"   - Lots: {len(data['lots'])}")
                    print(f"   - Total: {data['total']}")
                    
                    # Verify data structure for each type
                    success = True
                    
                    # Check listings structure
                    for listing in data["listings"]:
                        required_listing_fields = ["id", "title", "images", "category", "current_price", "auction_end_date", "city", "region", "watchlist_added_at"]
                        for field in required_listing_fields:
                            if field not in listing:
                                print(f"❌ Missing field in listing: {field}")
                                success = False
                    
                    # Check auctions structure
                    for auction in data["auctions"]:
                        required_auction_fields = ["id", "title", "total_lots", "lots", "category", "auction_end_date", "city", "region", "is_featured", "watchlist_added_at"]
                        for field in required_auction_fields:
                            if field not in auction:
                                print(f"❌ Missing field in auction: {field}")
                                print(f"   Available fields: {list(auction.keys())}")
                                success = False
                    
                    # Check lots structure
                    for lot_item in data["lots"]:
                        required_lot_fields = ["auction_id", "auction_title", "lot", "watchlist_added_at"]
                        for field in required_lot_fields:
                            if field not in lot_item:
                                print(f"❌ Missing field in lot: {field}")
                                success = False
                        
                        # Check lot object structure
                        if "lot" in lot_item:
                            lot = lot_item["lot"]
                            required_lot_object_fields = ["lot_number", "title", "images", "quantity", "current_price", "condition"]
                            for field in required_lot_object_fields:
                                if field not in lot:
                                    print(f"❌ Missing field in lot object: {field}")
                                    success = False
                    
                    if success:
                        print(f"✅ All data structures are correct")
                    
                    return success
                else:
                    print(f"❌ Failed to get mixed watchlist: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing mixed watchlist: {str(e)}")
            return False
    
    async def run_all_tests(self):
        """Run all watchlist API tests"""
        print("🚀 Starting Unified Watchlist System Backend API Tests")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Setup test user
            if not await self.login_test_user():
                print("❌ Failed to login test user")
                return False
            
            # Find test data
            if not await self.find_test_data():
                print("❌ Failed to find test data")
                return False
            
            # Run tests in specific order
            tests = [
                ("Add Listing to Watchlist", self.test_add_listing_to_watchlist),
                ("Add Auction to Watchlist", self.test_add_auction_to_watchlist),
                ("Add Lot to Watchlist", self.test_add_lot_to_watchlist),
                ("Duplicate Prevention", self.test_duplicate_prevention),
                ("Authentication Requirement", self.test_authentication_requirement),
                ("Validation Errors", self.test_validation_errors),
                ("Remove from Watchlist", self.test_remove_from_watchlist),
                ("Get Empty Watchlist", self.test_get_empty_watchlist),
                ("Get Mixed Watchlist", self.test_get_mixed_watchlist)
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
            print("📊 UNIFIED WATCHLIST SYSTEM TEST RESULTS SUMMARY")
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
                print("🎉 All watchlist API tests PASSED!")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = WatchlistTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)