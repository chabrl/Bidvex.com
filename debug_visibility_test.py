#!/usr/bin/env python3
"""
Debug script to investigate the visibility issue
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta

BASE_URL = "https://highstakes-auction.preview.emergentagent.com/api"
TEST_USER_EMAIL = "lots.homepage.tester@bazario.com"
TEST_USER_PASSWORD = "LotsTest123!"

async def debug_visibility():
    async with aiohttp.ClientSession() as session:
        # Login
        login_data = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        }
        
        async with session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
            if response.status != 200:
                print("Failed to login")
                return
            
            data = await response.json()
            auth_token = data["access_token"]
            user_id = data["user"]["id"]
            headers = {"Authorization": f"Bearer {auth_token}"}
        
        print("=== Testing different status filters ===")
        
        # Test 1: Default (should show active + upcoming)
        async with session.get(f"{BASE_URL}/multi-item-listings") as response:
            if response.status == 200:
                listings = await response.json()
                print(f"Default filter: {len(listings)} listings")
                statuses = {}
                for listing in listings:
                    status = listing.get("status", "unknown")
                    statuses[status] = statuses.get(status, 0) + 1
                print(f"Status breakdown: {statuses}")
            else:
                print(f"Default filter failed: {response.status}")
        
        # Test 2: Explicit upcoming filter
        async with session.get(f"{BASE_URL}/multi-item-listings?status=upcoming") as response:
            if response.status == 200:
                listings = await response.json()
                print(f"Upcoming filter: {len(listings)} listings")
                for listing in listings:
                    print(f"  - {listing['title']} (ID: {listing['id']}, Status: {listing['status']})")
            else:
                print(f"Upcoming filter failed: {response.status}")
        
        # Test 3: Explicit active filter
        async with session.get(f"{BASE_URL}/multi-item-listings?status=active") as response:
            if response.status == 200:
                listings = await response.json()
                print(f"Active filter: {len(listings)} listings")
            else:
                print(f"Active filter failed: {response.status}")
        
        # Test 4: Check seller listings
        async with session.get(f"{BASE_URL}/sellers/{user_id}/listings") as response:
            if response.status == 200:
                seller_data = await response.json()
                multi_listings = seller_data.get("multi_listings", [])
                print(f"Seller multi-listings: {len(multi_listings)} listings")
                for listing in multi_listings:
                    print(f"  - {listing['title']} (ID: {listing['id']}, Status: {listing['status']})")
            else:
                print(f"Seller listings failed: {response.status}")

if __name__ == "__main__":
    asyncio.run(debug_visibility())