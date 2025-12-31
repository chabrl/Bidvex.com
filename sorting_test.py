#!/usr/bin/env python3
"""
Test sorting fix - verify GET /api/multi-item-listings sorts by created_at DESC
and shows upcoming auctions by default
"""

import asyncio
import aiohttp
import json
from datetime import datetime

BASE_URL = "https://bidvex-upgrade.preview.emergentagent.com/api"

async def test_sorting_fix():
    async with aiohttp.ClientSession() as session:
        print("🧪 Testing Multi-Lot Auction Sorting Fix")
        print("=" * 60)
        
        # Test default GET /api/multi-item-listings
        async with session.get(f"{BASE_URL}/multi-item-listings") as response:
            if response.status != 200:
                print(f"❌ Failed to fetch listings: {response.status}")
                return False
            
            listings = await response.json()
            print(f"✅ Fetched {len(listings)} total listings")
            
            # Count by status
            active_count = len([l for l in listings if l.get("status") == "active"])
            upcoming_count = len([l for l in listings if l.get("status") == "upcoming"])
            
            print(f"   - Active listings: {active_count}")
            print(f"   - Upcoming listings: {upcoming_count}")
            
            # Verify upcoming auctions are included
            if upcoming_count > 0:
                print(f"✅ SUCCESS: Upcoming auctions are visible in default results")
            else:
                print(f"⚠️  No upcoming auctions found (may be expected)")
            
            # Check sorting by created_at DESC
            created_dates = []
            for listing in listings[:10]:  # Check first 10
                if "created_at" in listing:
                    try:
                        if isinstance(listing["created_at"], str):
                            date_obj = datetime.fromisoformat(listing["created_at"].replace('Z', '+00:00'))
                        else:
                            date_obj = listing["created_at"]
                        created_dates.append(date_obj)
                    except:
                        pass
            
            if len(created_dates) > 1:
                # Check if sorted DESC (newest first)
                is_sorted_desc = all(created_dates[i] >= created_dates[i+1] for i in range(len(created_dates)-1))
                
                if is_sorted_desc:
                    print(f"✅ SUCCESS: Listings are sorted by created_at DESC (newest first)")
                    print(f"   - First listing date: {created_dates[0]}")
                    print(f"   - Last checked date: {created_dates[-1]}")
                else:
                    print(f"❌ FAIL: Listings are NOT sorted by created_at DESC")
                    print(f"   - First 3 dates: {created_dates[:3]}")
                    return False
            else:
                print(f"⚠️  Not enough listings with dates to verify sorting")
            
            return True

async def main():
    success = await test_sorting_fix()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    print(f"\n{'✅ PASS' if success else '❌ FAIL'} - Multi-Lot Auction Sorting Fix Test")
    exit(0 if success else 1)