#!/usr/bin/env python3
"""
BidVex Debug Test - Investigate specific issues
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

# Configuration
BASE_URL = "https://bidvex-sync.preview.emergentagent.com/api"
TEST_USER_EMAIL = "lots.homepage.tester@bazario.com"
TEST_USER_PASSWORD = "LotsTest123!"

# Specific test listing IDs from review request
TEST_LISTING_IDS = [
    "68c4ee43-7e7b-4528-b727-99aa9488d3d5",  # Both features
    "858d80a2-fd09-4190-9a26-499d1041a8c7",  # Shipping only
    "48f30e25-e5ca-428c-bf17-b393c7679c0c"   # Visit only
]

class BidVexDebugTester:
    def __init__(self):
        self.session = None
        self.auth_token = None
        self.user_id = None
        
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
        
    async def debug_specific_listings(self):
        """Debug specific test listings"""
        print("\n🔍 Debugging Specific Test Listings...")
        
        try:
            # First, get all listings and check their IDs
            async with self.session.get(
                f"{BASE_URL}/multi-item-listings",
                headers=self.get_auth_headers()
            ) as response:
                if response.status != 200:
                    print(f"❌ Failed to get listings: {response.status}")
                    return
                
                all_listings = await response.json()
                print(f"📊 Total listings found: {len(all_listings)}")
                
                # Print first few listing IDs for reference
                print("\n🔍 First 10 listing IDs:")
                for i, listing in enumerate(all_listings[:10]):
                    print(f"   {i+1}. {listing['id']}")
                
                # Check if our test IDs exist
                found_ids = []
                for listing in all_listings:
                    if listing["id"] in TEST_LISTING_IDS:
                        found_ids.append(listing["id"])
                        print(f"\n✅ FOUND TEST LISTING: {listing['id']}")
                        print(f"   - Title: {listing.get('title', 'N/A')}")
                        print(f"   - Shipping Info: {listing.get('shipping_info')}")
                        print(f"   - Visit Availability: {listing.get('visit_availability')}")
                
                # Try to access each test listing individually
                for listing_id in TEST_LISTING_IDS:
                    print(f"\n🔍 Testing individual access to: {listing_id}")
                    async with self.session.get(
                        f"{BASE_URL}/multi-item-listings/{listing_id}",
                        headers=self.get_auth_headers()
                    ) as detail_response:
                        if detail_response.status == 200:
                            detail_data = await detail_response.json()
                            print(f"✅ Successfully retrieved: {listing_id}")
                            print(f"   - Title: {detail_data.get('title', 'N/A')}")
                            print(f"   - Shipping Info: {detail_data.get('shipping_info')}")
                            print(f"   - Visit Availability: {detail_data.get('visit_availability')}")
                        else:
                            print(f"❌ Failed to retrieve {listing_id}: {detail_response.status}")
                            text = await detail_response.text()
                            print(f"   Response: {text}")
                
        except Exception as e:
            print(f"❌ Error debugging specific listings: {str(e)}")
            
    async def debug_sorting_issue(self):
        """Debug sorting issue"""
        print("\n🔍 Debugging Sorting Issue...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/multi-item-listings",
                headers=self.get_auth_headers()
            ) as response:
                if response.status != 200:
                    print(f"❌ Failed to get listings for sorting debug")
                    return
                
                listings = await response.json()
                
                print(f"📊 Checking sorting of {len(listings)} listings...")
                
                # Check first 5 listings for sorting
                for i, listing in enumerate(listings[:5]):
                    created_at = listing.get("created_at")
                    print(f"   {i+1}. ID: {listing['id'][:8]}... Created: {created_at}")
                    
                    if i > 0:
                        prev_created = listings[i-1].get("created_at")
                        curr_created = created_at
                        
                        if prev_created and curr_created:
                            try:
                                prev_date = datetime.fromisoformat(prev_created.replace('Z', '+00:00'))
                                curr_date = datetime.fromisoformat(curr_created.replace('Z', '+00:00'))
                                
                                if prev_date < curr_date:
                                    print(f"❌ SORTING ERROR: Item {i} is newer than item {i-1}")
                                    print(f"   Previous: {prev_created}")
                                    print(f"   Current:  {curr_created}")
                                else:
                                    print(f"✅ Sorting OK between items {i-1} and {i}")
                            except Exception as e:
                                print(f"❌ Error parsing dates: {str(e)}")
                
        except Exception as e:
            print(f"❌ Error debugging sorting: {str(e)}")
            
    async def debug_lot_timers(self):
        """Debug lot timer issue"""
        print("\n🔍 Debugging Lot Timer Issue...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/multi-item-listings",
                headers=self.get_auth_headers()
            ) as response:
                if response.status != 200:
                    print(f"❌ Failed to get listings for timer debug")
                    return
                
                listings = await response.json()
                
                # Find a listing with multiple lots
                for listing in listings:
                    lots = listing.get("lots", [])
                    if len(lots) > 1:
                        print(f"\n🔍 Examining listing {listing['id']} with {len(lots)} lots:")
                        
                        for i, lot in enumerate(lots[:3]):  # Check first 3 lots
                            print(f"   Lot {i+1}:")
                            print(f"     - Lot Number: {lot.get('lot_number', 'N/A')}")
                            print(f"     - Title: {lot.get('title', 'N/A')}")
                            print(f"     - Lot End Time: {lot.get('lot_end_time', 'N/A')}")
                            
                            # Check if lot_end_time is None
                            if lot.get('lot_end_time') is None:
                                print(f"❌ lot_end_time is None for lot {i+1}")
                            else:
                                try:
                                    lot_end_time = datetime.fromisoformat(lot["lot_end_time"].replace('Z', '+00:00'))
                                    print(f"     - Parsed Time: {lot_end_time}")
                                except Exception as e:
                                    print(f"❌ Error parsing lot_end_time: {str(e)}")
                        
                        break  # Only check first multi-lot listing
                
        except Exception as e:
            print(f"❌ Error debugging lot timers: {str(e)}")
            
    async def run_debug_tests(self):
        """Run all debug tests"""
        print("🔍 Starting BidVex Debug Tests")
        print("=" * 50)
        
        await self.setup_session()
        
        try:
            # Setup test user
            if not await self.login_test_user():
                print("❌ Failed to login test user")
                return
            
            # Run debug tests
            await self.debug_specific_listings()
            await self.debug_sorting_issue()
            await self.debug_lot_timers()
                
        finally:
            await self.cleanup_session()

async def main():
    """Main debug runner"""
    tester = BidVexDebugTester()
    await tester.run_debug_tests()

if __name__ == "__main__":
    asyncio.run(main())