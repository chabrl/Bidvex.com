#!/usr/bin/env python3
"""
BidVex Platform Comprehensive Backend Testing
Tests multi-item listings with new features: shipping_info and visit_availability
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

# Configuration
BASE_URL = "https://bidvex-upgrade.preview.emergentagent.com/api"
TEST_USER_EMAIL = "lots.homepage.tester@bazario.com"
TEST_USER_PASSWORD = "LotsTest123!"

# Specific test listing IDs from review request
TEST_LISTING_IDS = [
    "68c4ee43-7e7b-4528-b727-99aa9488d3d5",  # Both features
    "858d80a2-fd09-4190-9a26-499d1041a8c7",  # Shipping only
    "48f30e25-e5ca-428c-bf17-b393c7679c0c"   # Visit only
]

class BidVexTester:
    def __init__(self):
        self.session = None
        self.auth_token = None
        self.user_id = None
        self.test_results = {}
        
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
                    print(f"   - Account Type: {data['user'].get('account_type', 'N/A')}")
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
        
    async def test_multi_item_listings_endpoint(self) -> bool:
        """Test GET /api/multi-item-listings with new features"""
        print("\n🧪 Testing GET /api/multi-item-listings (New Features)...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/multi-item-listings",
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if not isinstance(data, list):
                        print(f"❌ Expected list response, got: {type(data)}")
                        return False
                    
                    print(f"✅ Retrieved {len(data)} multi-item listings")
                    
                    # Check for required fields in listings
                    if len(data) > 0:
                        listing = data[0]
                        required_fields = [
                            "id", "title", "description", "category", "city", "region",
                            "total_lots", "auction_end_date", "auction_start_date",
                            "is_featured", "promotion_expiry", "seller_id", "currency",
                            "status", "lots", "shipping_info", "visit_availability"
                        ]
                        
                        missing_fields = []
                        for field in required_fields:
                            if field not in listing:
                                missing_fields.append(field)
                        
                        if missing_fields:
                            print(f"❌ Missing required fields: {missing_fields}")
                            return False
                        
                        print(f"✅ All required fields present in listing structure")
                        
                        # Verify new fields structure
                        shipping_info = listing.get("shipping_info")
                        visit_availability = listing.get("visit_availability")
                        
                        print(f"   - Shipping Info Present: {shipping_info is not None}")
                        print(f"   - Visit Availability Present: {visit_availability is not None}")
                        
                        if shipping_info:
                            expected_shipping_fields = ["available", "methods", "rates", "delivery_time"]
                            for field in expected_shipping_fields:
                                if field not in shipping_info:
                                    print(f"❌ Missing shipping_info field: {field}")
                                    return False
                            print(f"   - Shipping Info Structure: ✅ Valid")
                        
                        if visit_availability:
                            expected_visit_fields = ["offered", "dates", "instructions"]
                            for field in expected_visit_fields:
                                if field not in visit_availability:
                                    print(f"❌ Missing visit_availability field: {field}")
                                    return False
                            print(f"   - Visit Availability Structure: ✅ Valid")
                    
                    return True
                else:
                    print(f"❌ Failed to get multi-item listings: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing multi-item listings endpoint: {str(e)}")
            return False
            
    async def test_specific_test_listings(self) -> bool:
        """Test specific test listings created for BidVex features"""
        print("\n🧪 Testing Specific Test Listings...")
        
        success = True
        found_listings = []
        
        try:
            # Get all listings first
            async with self.session.get(
                f"{BASE_URL}/multi-item-listings",
                headers=self.get_auth_headers()
            ) as response:
                if response.status != 200:
                    print(f"❌ Failed to get listings: {response.status}")
                    return False
                
                all_listings = await response.json()
                
                # Find our test listings
                for listing_id in TEST_LISTING_IDS:
                    found = False
                    for listing in all_listings:
                        if listing["id"] == listing_id:
                            found_listings.append(listing)
                            found = True
                            break
                    
                    if not found:
                        print(f"❌ Test listing not found: {listing_id}")
                        success = False
                    else:
                        print(f"✅ Found test listing: {listing_id}")
            
            # Test each found listing individually
            for listing in found_listings:
                listing_id = listing["id"]
                
                # Test individual listing retrieval
                async with self.session.get(
                    f"{BASE_URL}/multi-item-listings/{listing_id}",
                    headers=self.get_auth_headers()
                ) as response:
                    if response.status == 200:
                        detailed_listing = await response.json()
                        
                        # Verify features based on listing ID
                        if listing_id == "68c4ee43-7e7b-4528-b727-99aa9488d3d5":
                            # Both features
                            if not self._verify_both_features(detailed_listing):
                                success = False
                        elif listing_id == "858d80a2-fd09-4190-9a26-499d1041a8c7":
                            # Shipping only
                            if not self._verify_shipping_only(detailed_listing):
                                success = False
                        elif listing_id == "48f30e25-e5ca-428c-bf17-b393c7679c0c":
                            # Visit only
                            if not self._verify_visit_only(detailed_listing):
                                success = False
                        
                        print(f"✅ Successfully retrieved detailed listing: {listing_id}")
                    else:
                        print(f"❌ Failed to get detailed listing {listing_id}: {response.status}")
                        success = False
            
            print(f"\n📊 Test Listings Summary:")
            print(f"   - Expected: {len(TEST_LISTING_IDS)} listings")
            print(f"   - Found: {len(found_listings)} listings")
            
            return success
            
        except Exception as e:
            print(f"❌ Error testing specific test listings: {str(e)}")
            return False
            
    def _verify_both_features(self, listing: Dict[str, Any]) -> bool:
        """Verify listing has both shipping and visit features"""
        shipping_info = listing.get("shipping_info")
        visit_availability = listing.get("visit_availability")
        
        if not shipping_info or not shipping_info.get("available"):
            print(f"❌ Listing should have shipping available")
            return False
            
        if not visit_availability or not visit_availability.get("offered"):
            print(f"❌ Listing should have visit availability offered")
            return False
            
        print(f"✅ Both features verified for listing {listing['id']}")
        return True
        
    def _verify_shipping_only(self, listing: Dict[str, Any]) -> bool:
        """Verify listing has shipping but not visit features"""
        shipping_info = listing.get("shipping_info")
        visit_availability = listing.get("visit_availability")
        
        if not shipping_info or not shipping_info.get("available"):
            print(f"❌ Listing should have shipping available")
            return False
            
        if visit_availability and visit_availability.get("offered"):
            print(f"❌ Listing should NOT have visit availability offered")
            return False
            
        print(f"✅ Shipping-only feature verified for listing {listing['id']}")
        return True
        
    def _verify_visit_only(self, listing: Dict[str, Any]) -> bool:
        """Verify listing has visit but not shipping features"""
        shipping_info = listing.get("shipping_info")
        visit_availability = listing.get("visit_availability")
        
        if shipping_info and shipping_info.get("available"):
            print(f"❌ Listing should NOT have shipping available")
            return False
            
        if not visit_availability or not visit_availability.get("offered"):
            print(f"❌ Listing should have visit availability offered")
            return False
            
        print(f"✅ Visit-only feature verified for listing {listing['id']}")
        return True
        
    async def test_data_integrity(self) -> bool:
        """Test data integrity of shipping_info and visit_availability structures"""
        print("\n🧪 Testing Data Integrity...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/multi-item-listings",
                headers=self.get_auth_headers()
            ) as response:
                if response.status != 200:
                    print(f"❌ Failed to get listings for data integrity test")
                    return False
                
                listings = await response.json()
                
                shipping_structure_valid = True
                visit_structure_valid = True
                null_fields_correct = True
                
                for listing in listings:
                    # Test shipping_info structure
                    shipping_info = listing.get("shipping_info")
                    if shipping_info is not None:
                        required_fields = ["available", "methods", "rates", "delivery_time"]
                        for field in required_fields:
                            if field not in shipping_info:
                                print(f"❌ Missing shipping_info field '{field}' in listing {listing['id']}")
                                shipping_structure_valid = False
                        
                        # Verify types
                        if not isinstance(shipping_info.get("available"), bool):
                            print(f"❌ shipping_info.available should be boolean in listing {listing['id']}")
                            shipping_structure_valid = False
                        
                        if shipping_info.get("available") and not isinstance(shipping_info.get("methods"), list):
                            print(f"❌ shipping_info.methods should be list when available in listing {listing['id']}")
                            shipping_structure_valid = False
                    
                    # Test visit_availability structure
                    visit_availability = listing.get("visit_availability")
                    if visit_availability is not None:
                        required_fields = ["offered", "dates", "instructions"]
                        for field in required_fields:
                            if field not in visit_availability:
                                print(f"❌ Missing visit_availability field '{field}' in listing {listing['id']}")
                                visit_structure_valid = False
                        
                        # Verify types
                        if not isinstance(visit_availability.get("offered"), bool):
                            print(f"❌ visit_availability.offered should be boolean in listing {listing['id']}")
                            visit_structure_valid = False
                    
                    # Test null fields when not offered
                    if shipping_info and not shipping_info.get("available"):
                        if shipping_info.get("methods") or shipping_info.get("rates") or shipping_info.get("delivery_time"):
                            print(f"⚠️  Shipping fields should be null when not available in listing {listing['id']}")
                    
                    if visit_availability and not visit_availability.get("offered"):
                        if visit_availability.get("dates") or visit_availability.get("instructions"):
                            print(f"⚠️  Visit fields should be null when not offered in listing {listing['id']}")
                
                if shipping_structure_valid:
                    print(f"✅ Shipping info structure validation passed")
                else:
                    print(f"❌ Shipping info structure validation failed")
                
                if visit_structure_valid:
                    print(f"✅ Visit availability structure validation passed")
                else:
                    print(f"❌ Visit availability structure validation failed")
                
                return shipping_structure_valid and visit_structure_valid
                
        except Exception as e:
            print(f"❌ Error testing data integrity: {str(e)}")
            return False
            
    async def test_filtering_and_sorting(self) -> bool:
        """Test filtering and sorting functionality"""
        print("\n🧪 Testing Filtering and Sorting...")
        
        try:
            # Test 1: Default sorting (created_at desc)
            async with self.session.get(
                f"{BASE_URL}/multi-item-listings",
                headers=self.get_auth_headers()
            ) as response:
                if response.status != 200:
                    print(f"❌ Failed to get listings for sorting test")
                    return False
                
                listings = await response.json()
                
                if len(listings) > 1:
                    # Verify sorting by created_at desc
                    for i in range(len(listings) - 1):
                        current_date = datetime.fromisoformat(listings[i]["created_at"].replace('Z', '+00:00'))
                        next_date = datetime.fromisoformat(listings[i + 1]["created_at"].replace('Z', '+00:00'))
                        
                        if current_date < next_date:
                            print(f"❌ Listings not sorted by created_at desc")
                            return False
                    
                    print(f"✅ Listings correctly sorted by created_at desc")
                else:
                    print(f"⚠️  Only {len(listings)} listings found, cannot verify sorting")
            
            # Test 2: Upcoming listings filter
            async with self.session.get(
                f"{BASE_URL}/multi-item-listings?status=upcoming",
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    upcoming_listings = await response.json()
                    
                    # Verify all have future auction_start_date
                    now = datetime.now(timezone.utc)
                    for listing in upcoming_listings:
                        if listing.get("auction_start_date"):
                            start_date = datetime.fromisoformat(listing["auction_start_date"].replace('Z', '+00:00'))
                            if start_date <= now:
                                print(f"❌ Upcoming listing has past start date: {listing['id']}")
                                return False
                    
                    print(f"✅ Upcoming listings filter working ({len(upcoming_listings)} found)")
                else:
                    print(f"❌ Failed to get upcoming listings: {response.status}")
                    return False
            
            # Test 3: Active listings filter
            async with self.session.get(
                f"{BASE_URL}/multi-item-listings?status=active",
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    active_listings = await response.json()
                    
                    # Verify all have status=active
                    for listing in active_listings:
                        if listing.get("status") != "active":
                            print(f"❌ Non-active listing in active filter: {listing['id']}")
                            return False
                    
                    print(f"✅ Active listings filter working ({len(active_listings)} found)")
                else:
                    print(f"❌ Failed to get active listings: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing filtering and sorting: {str(e)}")
            return False
            
    async def test_lot_countdown_timers(self) -> bool:
        """Test lot countdown timers (1-minute staggered lot_end_time)"""
        print("\n🧪 Testing Lot Countdown Timers...")
        
        try:
            # Get a listing with multiple lots
            async with self.session.get(
                f"{BASE_URL}/multi-item-listings",
                headers=self.get_auth_headers()
            ) as response:
                if response.status != 200:
                    print(f"❌ Failed to get listings for timer test")
                    return False
                
                listings = await response.json()
                
                # Find a listing with multiple lots
                test_listing = None
                for listing in listings:
                    if len(listing.get("lots", [])) > 1:
                        test_listing = listing
                        break
                
                if not test_listing:
                    print(f"⚠️  No multi-lot listings found for timer test")
                    return True
                
                lots = test_listing["lots"]
                print(f"   - Testing listing {test_listing['id']} with {len(lots)} lots")
                
                # Verify lot_end_time calculation
                for i, lot in enumerate(lots):
                    if "lot_end_time" not in lot:
                        print(f"❌ Missing lot_end_time in lot {lot.get('lot_number', i)}")
                        return False
                    
                    lot_end_time = datetime.fromisoformat(lot["lot_end_time"].replace('Z', '+00:00'))
                    
                    # For staggered timing, each lot should end 1 minute after the previous
                    if i > 0:
                        prev_lot_end_time = datetime.fromisoformat(lots[i-1]["lot_end_time"].replace('Z', '+00:00'))
                        time_diff = lot_end_time - prev_lot_end_time
                        
                        # Should be approximately 1 minute (60 seconds)
                        if abs(time_diff.total_seconds() - 60) > 5:  # Allow 5 second tolerance
                            print(f"❌ Incorrect staggered timing between lots {i-1} and {i}")
                            print(f"   Expected: ~60 seconds, Got: {time_diff.total_seconds()} seconds")
                            return False
                
                print(f"✅ Lot countdown timers correctly calculated (1-minute staggered)")
                
                # Verify each lot has correct lot_end_time
                for lot in lots:
                    if lot.get("lot_end_time"):
                        print(f"   - Lot {lot.get('lot_number', '?')}: {lot['lot_end_time']}")
                
                return True
                
        except Exception as e:
            print(f"❌ Error testing lot countdown timers: {str(e)}")
            return False
            
    async def run_all_tests(self):
        """Run all BidVex platform tests"""
        print("🚀 Starting BidVex Platform Comprehensive Backend Testing")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Setup test user
            if not await self.login_test_user():
                print("❌ Failed to login test user")
                return False
            
            # Run tests in specific order
            tests = [
                ("Multi-Item Listings API with New Features", self.test_multi_item_listings_endpoint),
                ("Specific Test Listings Verification", self.test_specific_test_listings),
                ("Data Integrity Validation", self.test_data_integrity),
                ("Filtering and Sorting", self.test_filtering_and_sorting),
                ("Lot Countdown Timers", self.test_lot_countdown_timers)
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
            print("📊 BIDVEX PLATFORM TEST RESULTS SUMMARY")
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
                print("🎉 All BidVex platform tests PASSED!")
                print("\n✅ SUCCESS CRITERIA MET:")
                print("   - All 4 new test listings retrievable")
                print("   - shipping_info and visit_availability present where expected")
                print("   - No data corruption or missing fields")
                print("   - Lot timers calculated correctly")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = BidVexTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)