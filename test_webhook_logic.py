#!/usr/bin/env python3
"""
Test webhook logic for promotion activation
"""

import asyncio
import aiohttp
import json

BASE_URL = "https://bazario-mvp.preview.emergentagent.com/api"

async def test_webhook_logic():
    """Test that webhook properly activates promotions"""
    async with aiohttp.ClientSession() as session:
        # Login
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
            
        # Get user's promotions to find one to test
        async with session.get(f"{BASE_URL}/promotions/my", headers=headers) as response:
            if response.status != 200:
                print(f"Failed to get promotions: {response.status}")
                return
            
            promotions = await response.json()
            if not promotions:
                print("No promotions found")
                return
            
            # Find a pending promotion
            pending_promotion = None
            for promo in promotions:
                if promo.get("status") == "pending":
                    pending_promotion = promo
                    break
            
            if not pending_promotion:
                print("No pending promotions found")
                return
            
            print(f"Found pending promotion: {pending_promotion['id']}")
            print(f"Current status: {pending_promotion['status']}")
            print(f"Payment status: {pending_promotion.get('payment_status', 'N/A')}")
            
            # Check if listing is promoted
            listing_id = pending_promotion['listing_id']
            async with session.get(f"{BASE_URL}/listings/{listing_id}") as response:
                if response.status == 200:
                    listing = await response.json()
                    print(f"Listing is_promoted: {listing.get('is_promoted', False)}")
                else:
                    print(f"Failed to get listing: {response.status}")

if __name__ == "__main__":
    asyncio.run(test_webhook_logic())