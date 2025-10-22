#!/usr/bin/env python3
"""
Debug script to test promotion creation directly
"""

import asyncio
import aiohttp
import json

BASE_URL = "https://bazario-mvp.preview.emergentagent.com/api"

async def test_promotion_creation():
    async with aiohttp.ClientSession() as session:
        # Login first
        login_data = {
            "email": "promotion.tester@bazario.com",
            "password": "PromotionTest123!"
        }
        
        async with session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
            if response.status != 200:
                print(f"Login failed: {response.status}")
                return
            
            data = await response.json()
            auth_token = data["access_token"]
            headers = {"Authorization": f"Bearer {auth_token}"}
            
        # Get user's listings
        async with session.get(f"{BASE_URL}/dashboard/seller", headers=headers) as response:
            if response.status != 200:
                print(f"Failed to get dashboard: {response.status}")
                return
            
            data = await response.json()
            listings = data.get("listings", [])
            if not listings:
                print("No listings found")
                return
            
            listing_id = listings[0]["id"]
            print(f"Using listing: {listing_id}")
            
        # Try to create promotion with minimal data
        promotion_data = {
            "listing_id": listing_id,
            "promotion_type": "basic",
            "price": 9.99
        }
        
        print(f"Creating promotion with data: {promotion_data}")
        
        async with session.post(f"{BASE_URL}/promotions", json=promotion_data, headers=headers) as response:
            print(f"Response status: {response.status}")
            text = await response.text()
            print(f"Response text: {text}")

if __name__ == "__main__":
    asyncio.run(test_promotion_creation())