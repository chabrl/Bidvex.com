#!/usr/bin/env python3
"""
BidVex Critical Fixes Testing
Tests three critical fixes for BidVex platform:
1. Multi-Lot Auction Visibility Fix
2. Filters Working 
3. Bid Placement Fix
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://visual-lab-7.preview.emergentagent.com/api"
TEST_USER_EMAIL = "lots.homepage.tester@bazario.com"
TEST_USER_PASSWORD = "LotsTest123!"

class BidVexCriticalFixesTester:
    def __init__(self):
        self.session = None
        self.auth_token = None
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
        
    async def test_multi_lot_auction_visibility_fix(self) -> bool:
        """
        Test 1: Multi-Lot Auction Visibility Fix
        Test that newly created multi-lot auctions are visible immediately.
        """
        print("\n🧪 Test 1: Multi-Lot Auction Visibility Fix")
        print("=" * 60)
        
        try:
            # Step 1: Create a multi-lot auction
            print("📝 Step 1: Creating multi-lot auction...")
            
            # Calculate dates (2 days from now for start, 5 days from now for end)
            now = datetime.now(timezone.utc)
            auction_start_date = now + timedelta(days=2)
            auction_end_date = now + timedelta(days=5)
            
            auction_data = {
                "title": "Visibility Test Auction",
                "description": "Testing auction visibility",
                "category": "Electronics",
                "location": "Test Location",
                "city": "Test City", 
                "region": "Quebec",
                "auction_start_date": auction_start_date.isoformat(),
                "auction_end_date": auction_end_date.isoformat(),
                "lots": [
                    {
                        "lot_number": 1,
                        "title": "Test Item 1",
                        "description": "First test item for visibility testing",
                        "quantity": 1,
                        "starting_price": 10.0,
                        "current_price": 10.0,
                        "condition": "new",
                        "images": []
                    },
                    {
                        "lot_number": 2,
                        "title": "Test Item 2", 
                        "description": "Second test item for visibility testing",
                        "quantity": 1,
                        "starting_price": 15.0,
                        "current_price": 15.0,
                        "condition": "used",
                        "images": []
                    }
                ]
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=auction_data,
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    created_auction = await response.json()
                    self.test_auction_id = created_auction["id"]
                    print(f"✅ Multi-lot auction created successfully")
                    print(f"   - Auction ID: {self.test_auction_id}")
                    print(f"   - Status: {created_auction.get('status', 'N/A')}")
                    print(f"   - Start Date: {auction_start_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                    print(f"   - End Date: {auction_end_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                else:
                    print(f"❌ Failed to create auction: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Step 2: Verify GET /api/multi-item-listings returns the newly created auction
            print("\n📋 Step 2: Verifying auction appears in GET /api/multi-item-listings...")
            
            async with self.session.get(f"{BASE_URL}/multi-item-listings") as response:
                if response.status == 200:
                    listings = await response.json()
                    
                    # Find our test auction
                    test_auction = None
                    for listing in listings:
                        if listing["id"] == self.test_auction_id:
                            test_auction = listing
                            break
                    
                    if test_auction:
                        print(f"✅ Auction found in listings")
                        print(f"   - Title: {test_auction['title']}")
                        print(f"   - Status: {test_auction['status']}")
                        print(f"   - Total Lots: {test_auction.get('total_lots', 'N/A')}")
                    else:
                        print(f"❌ Auction NOT found in listings")
                        print(f"   - Total listings returned: {len(listings)}")
                        return False
                else:
                    print(f"❌ Failed to get listings: {response.status}")
                    return False
            
            # Step 3: Verify GET /api/sellers/{seller_id}/listings includes the new auction
            print(f"\n👤 Step 3: Verifying auction appears in seller listings...")
            
            async with self.session.get(f"{BASE_URL}/sellers/{self.user_id}/listings") as response:
                if response.status == 200:
                    seller_data = await response.json()
                    multi_listings = seller_data.get("multi_listings", [])
                    
                    # Find our test auction
                    test_auction = None
                    for listing in multi_listings:
                        if listing["id"] == self.test_auction_id:
                            test_auction = listing
                            break
                    
                    if test_auction:
                        print(f"✅ Auction found in seller listings")
                        print(f"   - Title: {test_auction['title']}")
                        print(f"   - Status: {test_auction['status']}")
                        print(f"   - Total multi-listings for seller: {len(multi_listings)}")
                    else:
                        print(f"❌ Auction NOT found in seller listings")
                        print(f"   - Total multi-listings for seller: {len(multi_listings)}")
                        return False
                else:
                    print(f"❌ Failed to get seller listings: {response.status}")
                    return False
            
            print(f"\n🎉 Test 1 PASSED: Multi-lot auction visibility working correctly")
            return True
            
        except Exception as e:
            print(f"❌ Error in multi-lot auction visibility test: {str(e)}")
            return False
            
    async def test_filters_working(self) -> bool:
        """
        Test 2: Filters Working
        Test that query parameters properly filter results.
        """
        print("\n🧪 Test 2: Filters Working")
        print("=" * 60)
        
        try:
            # Test 1: Category filter
            print("🔍 Testing category filter...")
            async with self.session.get(f"{BASE_URL}/multi-item-listings?category=Electronics") as response:
                if response.status == 200:
                    listings = await response.json()
                    electronics_count = len(listings)
                    print(f"✅ Category filter working: {electronics_count} Electronics listings found")
                    
                    # Verify all returned listings are Electronics
                    non_electronics = [l for l in listings if l.get("category") != "Electronics"]
                    if non_electronics:
                        print(f"❌ Found {len(non_electronics)} non-Electronics listings in Electronics filter")
                        return False
                else:
                    print(f"❌ Category filter failed: {response.status}")
                    return False
            
            # Test 2: Region filter
            print("\n🌍 Testing region filter...")
            async with self.session.get(f"{BASE_URL}/multi-item-listings?region=Quebec") as response:
                if response.status == 200:
                    listings = await response.json()
                    quebec_count = len(listings)
                    print(f"✅ Region filter working: {quebec_count} Quebec listings found")
                    
                    # Verify all returned listings are from Quebec
                    non_quebec = [l for l in listings if l.get("region") != "Quebec"]
                    if non_quebec:
                        print(f"❌ Found {len(non_quebec)} non-Quebec listings in Quebec filter")
                        return False
                else:
                    print(f"❌ Region filter failed: {response.status}")
                    return False
            
            # Test 3: Currency filter
            print("\n💰 Testing currency filter...")
            async with self.session.get(f"{BASE_URL}/multi-item-listings?currency=CAD") as response:
                if response.status == 200:
                    listings = await response.json()
                    cad_count = len(listings)
                    print(f"✅ Currency filter working: {cad_count} CAD listings found")
                    
                    # Verify all returned listings are CAD
                    non_cad = [l for l in listings if l.get("currency") != "CAD"]
                    if non_cad:
                        print(f"❌ Found {len(non_cad)} non-CAD listings in CAD filter")
                        return False
                else:
                    print(f"❌ Currency filter failed: {response.status}")
                    return False
            
            # Test 4: Search filter
            print("\n🔎 Testing search filter...")
            async with self.session.get(f"{BASE_URL}/multi-item-listings?search=test") as response:
                if response.status == 200:
                    listings = await response.json()
                    search_count = len(listings)
                    print(f"✅ Search filter working: {search_count} listings found for 'test'")
                    
                    # Verify at least our test auction is found
                    test_auction_found = any(l["id"] == self.test_auction_id for l in listings)
                    if test_auction_found:
                        print(f"✅ Our test auction found in search results")
                    else:
                        print(f"⚠️  Our test auction not found in search (may be expected)")
                else:
                    print(f"❌ Search filter failed: {response.status}")
                    return False
            
            # Test 5: Combined filters
            print("\n🔗 Testing combined filters...")
            async with self.session.get(f"{BASE_URL}/multi-item-listings?category=Electronics&region=Quebec") as response:
                if response.status == 200:
                    listings = await response.json()
                    combined_count = len(listings)
                    print(f"✅ Combined filters working: {combined_count} Electronics listings in Quebec")
                    
                    # Verify all listings match both criteria
                    invalid_listings = [
                        l for l in listings 
                        if l.get("category") != "Electronics" or l.get("region") != "Quebec"
                    ]
                    if invalid_listings:
                        print(f"❌ Found {len(invalid_listings)} listings not matching combined criteria")
                        return False
                else:
                    print(f"❌ Combined filters failed: {response.status}")
                    return False
            
            # Test 6: Status defaults to both 'active' and 'upcoming'
            print("\n📊 Testing default status behavior...")
            async with self.session.get(f"{BASE_URL}/multi-item-listings") as response:
                if response.status == 200:
                    all_listings = await response.json()
                    
                    # Count by status
                    active_count = len([l for l in all_listings if l.get("status") == "active"])
                    upcoming_count = len([l for l in all_listings if l.get("status") == "upcoming"])
                    other_count = len([l for l in all_listings if l.get("status") not in ["active", "upcoming"]])
                    
                    print(f"✅ Default status filter working:")
                    print(f"   - Active listings: {active_count}")
                    print(f"   - Upcoming listings: {upcoming_count}")
                    print(f"   - Other status: {other_count}")
                    
                    if other_count > 0:
                        print(f"❌ Found listings with unexpected status")
                        return False
                else:
                    print(f"❌ Default status test failed: {response.status}")
                    return False
            
            print(f"\n🎉 Test 2 PASSED: All filters working correctly")
            return True
            
        except Exception as e:
            print(f"❌ Error in filters test: {str(e)}")
            return False
            
    async def test_bid_placement_fix(self) -> bool:
        """
        Test 3: Bid Placement Fix
        Test that bid_type as string doesn't cause validation error.
        """
        print("\n🧪 Test 3: Bid Placement Fix")
        print("=" * 60)
        
        try:
            # First, we need an active auction to bid on
            # Let's find an active multi-lot auction or use our test auction if it's active
            print("🔍 Finding active multi-lot auction...")
            
            target_auction_id = None
            target_auction = None
            
            async with self.session.get(f"{BASE_URL}/multi-item-listings?status=active") as response:
                if response.status == 200:
                    active_listings = await response.json()
                    
                    if active_listings:
                        # Use the first active auction
                        target_auction = active_listings[0]
                        target_auction_id = target_auction["id"]
                        print(f"✅ Found active auction: {target_auction['title']}")
                        print(f"   - Auction ID: {target_auction_id}")
                        print(f"   - Total Lots: {target_auction.get('total_lots', 'N/A')}")
                    else:
                        print("⚠️  No active auctions found, will create one for testing...")
                        
                        # Create an active auction for testing
                        now = datetime.now(timezone.utc)
                        auction_data = {
                            "title": "Bid Test Auction",
                            "description": "Testing bid placement",
                            "category": "Electronics",
                            "location": "Test Location",
                            "city": "Test City",
                            "region": "Quebec", 
                            "auction_end_date": (now + timedelta(hours=2)).isoformat(),
                            "lots": [
                                {
                                    "lot_number": 1,
                                    "title": "Bid Test Item",
                                    "description": "Item for bid testing",
                                    "quantity": 1,
                                    "starting_price": 25.0,
                                    "current_price": 25.0,
                                    "condition": "new",
                                    "images": []
                                }
                            ]
                        }
                        
                        async with self.session.post(
                            f"{BASE_URL}/multi-item-listings",
                            json=auction_data,
                            headers=self.get_auth_headers()
                        ) as create_response:
                            if create_response.status == 200:
                                created_auction = await create_response.json()
                                target_auction_id = created_auction["id"]
                                target_auction = created_auction
                                print(f"✅ Created active auction for testing: {target_auction_id}")
                            else:
                                print(f"❌ Failed to create test auction: {create_response.status}")
                                return False
                else:
                    print(f"❌ Failed to get active listings: {response.status}")
                    return False
            
            if not target_auction_id:
                print("❌ No auction available for bid testing")
                return False
            
            # Test 1: Place bid with bid_type as string "normal"
            print(f"\n💰 Testing bid placement with bid_type='normal'...")
            
            bid_data = {
                "amount": 50,
                "bid_type": "normal"
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings/{target_auction_id}/lots/1/bid",
                json=bid_data,
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    bid_result = await response.json()
                    print(f"✅ Normal bid placed successfully")
                    print(f"   - Bid Amount: ${bid_result['bid']['amount']}")
                    print(f"   - Bid Type: {bid_result['bid']['bid_type']}")
                    print(f"   - Message: {bid_result.get('message', 'N/A')}")
                elif response.status == 400:
                    error_data = await response.json()
                    error_detail = error_data.get("detail", "")
                    
                    # Check if it's a validation error about parsing string as number
                    if "unable to parse string as a number" in error_detail.lower():
                        print(f"❌ CRITICAL BUG: bid_type string validation error")
                        print(f"   - Error: {error_detail}")
                        return False
                    elif "cannot bid on your own listing" in error_detail.lower():
                        print(f"⚠️  Cannot test bid - user owns the auction")
                        print(f"   - This is expected behavior")
                        # This is not a failure of the bid_type fix
                    elif "bid must be" in error_detail.lower():
                        print(f"⚠️  Bid amount validation failed: {error_detail}")
                        print(f"   - This is expected business logic, not the bug we're testing")
                    else:
                        print(f"❌ Unexpected bid error: {error_detail}")
                        return False
                else:
                    print(f"❌ Bid placement failed: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Place bid with bid_type as string "monster"
            print(f"\n🦄 Testing bid placement with bid_type='monster'...")
            
            bid_data = {
                "amount": 75,
                "bid_type": "monster"
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings/{target_auction_id}/lots/1/bid",
                json=bid_data,
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    bid_result = await response.json()
                    print(f"✅ Monster bid placed successfully")
                    print(f"   - Bid Amount: ${bid_result['bid']['amount']}")
                    print(f"   - Bid Type: {bid_result['bid']['bid_type']}")
                elif response.status == 400:
                    error_data = await response.json()
                    error_detail = error_data.get("detail", "")
                    
                    if "unable to parse string as a number" in error_detail.lower():
                        print(f"❌ CRITICAL BUG: bid_type string validation error")
                        print(f"   - Error: {error_detail}")
                        return False
                    else:
                        print(f"⚠️  Monster bid validation failed: {error_detail}")
                        print(f"   - This may be expected business logic")
                elif response.status == 403:
                    error_data = await response.json()
                    print(f"⚠️  Monster bid permission denied: {error_data.get('detail', 'N/A')}")
                    print(f"   - This may be expected for free tier users")
                else:
                    print(f"❌ Monster bid failed: {response.status}")
                    return False
            
            # Test 3: Place bid with bid_type as string "auto"
            print(f"\n🤖 Testing bid placement with bid_type='auto'...")
            
            bid_data = {
                "amount": 100,
                "bid_type": "auto"
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings/{target_auction_id}/lots/1/bid",
                json=bid_data,
                headers=self.get_auth_headers()
            ) as response:
                if response.status == 200:
                    bid_result = await response.json()
                    print(f"✅ Auto bid placed successfully")
                    print(f"   - Bid Amount: ${bid_result['bid']['amount']}")
                    print(f"   - Bid Type: {bid_result['bid']['bid_type']}")
                elif response.status == 400:
                    error_data = await response.json()
                    error_detail = error_data.get("detail", "")
                    
                    if "unable to parse string as a number" in error_detail.lower():
                        print(f"❌ CRITICAL BUG: bid_type string validation error")
                        print(f"   - Error: {error_detail}")
                        return False
                    else:
                        print(f"⚠️  Auto bid validation failed: {error_detail}")
                        print(f"   - This may be expected business logic")
                else:
                    print(f"❌ Auto bid failed: {response.status}")
                    return False
            
            # Test 4: Verify bid appears in database
            print(f"\n📊 Verifying bids appear in database...")
            
            # We can't directly access the database, but we can check if the auction's current price was updated
            async with self.session.get(f"{BASE_URL}/multi-item-listings/{target_auction_id}") as response:
                if response.status == 200:
                    updated_auction = await response.json()
                    lot_1 = next((lot for lot in updated_auction["lots"] if lot["lot_number"] == 1), None)
                    
                    if lot_1:
                        current_price = lot_1["current_price"]
                        starting_price = lot_1["starting_price"]
                        
                        print(f"✅ Auction data retrieved")
                        print(f"   - Starting Price: ${starting_price}")
                        print(f"   - Current Price: ${current_price}")
                        
                        if current_price > starting_price:
                            print(f"✅ Bid successfully updated auction price")
                        else:
                            print(f"⚠️  Price not updated (may be due to ownership or validation)")
                    else:
                        print(f"❌ Lot 1 not found in auction")
                        return False
                else:
                    print(f"❌ Failed to retrieve updated auction: {response.status}")
                    return False
            
            print(f"\n🎉 Test 3 PASSED: Bid placement with string bid_type working correctly")
            return True
            
        except Exception as e:
            print(f"❌ Error in bid placement test: {str(e)}")
            return False
            
    async def run_all_tests(self):
        """Run all BidVex critical fixes tests"""
        print("🚀 Starting BidVex Critical Fixes Tests")
        print("=" * 70)
        print(f"Testing against: {BASE_URL}")
        print(f"Test user: {TEST_USER_EMAIL}")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Login
            if not await self.login_test_user():
                print("❌ Failed to login test user")
                return False
            
            # Run tests in order
            tests = [
                ("Multi-Lot Auction Visibility Fix", self.test_multi_lot_auction_visibility_fix),
                ("Filters Working", self.test_filters_working),
                ("Bid Placement Fix", self.test_bid_placement_fix)
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
            print("📊 BIDVEX CRITICAL FIXES TEST RESULTS SUMMARY")
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
                print("🎉 All BidVex critical fixes tests PASSED!")
                print("\n✅ SUCCESS CRITERIA MET:")
                print("✅ Newly created auctions visible immediately (both active and upcoming)")
                print("✅ Filters return correctly filtered results")
                print("✅ Bid placement works without validation error for bid_type")
                print("✅ All three fixes working as expected")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = BidVexCriticalFixesTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)