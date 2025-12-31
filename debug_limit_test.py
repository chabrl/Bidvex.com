#!/usr/bin/env python3
"""
Debug script to test if limit is causing the visibility issue
"""

import asyncio
import aiohttp

BASE_URL = "https://bidvex-upgrade.preview.emergentagent.com/api"

async def debug_limit():
    async with aiohttp.ClientSession() as session:
        print("=== Testing limit parameter ===")
        
        # Test with higher limit
        async with session.get(f"{BASE_URL}/multi-item-listings?limit=100") as response:
            if response.status == 200:
                listings = await response.json()
                print(f"Limit 100: {len(listings)} listings")
                statuses = {}
                for listing in listings:
                    status = listing.get("status", "unknown")
                    statuses[status] = statuses.get(status, 0) + 1
                print(f"Status breakdown: {statuses}")
            else:
                print(f"Limit 100 failed: {response.status}")
        
        # Test with no limit (should default to 50)
        async with session.get(f"{BASE_URL}/multi-item-listings") as response:
            if response.status == 200:
                listings = await response.json()
                print(f"Default limit: {len(listings)} listings")
                statuses = {}
                for listing in listings:
                    status = listing.get("status", "unknown")
                    statuses[status] = statuses.get(status, 0) + 1
                print(f"Status breakdown: {statuses}")
            else:
                print(f"Default limit failed: {response.status}")

if __name__ == "__main__":
    asyncio.run(debug_limit())