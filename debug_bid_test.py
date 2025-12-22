#!/usr/bin/env python3
"""
Debug script to investigate the bid placement 500 error
"""

import asyncio
import aiohttp
import json

BASE_URL = "https://auction-house-2.preview.emergentagent.com/api"
TEST_USER_EMAIL = "lots.homepage.tester@bazario.com"
TEST_USER_PASSWORD = "LotsTest123!"

async def debug_bid_placement():
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
        
        print("=== Finding auction to bid on ===")
        
        # Get active auctions
        async with session.get(f"{BASE_URL}/multi-item-listings?status=active") as response:
            if response.status != 200:
                print("Failed to get active listings")
                return
            
            listings = await response.json()
            print(f"Found {len(listings)} active listings")
            
            # Find an auction not owned by the test user
            target_auction = None
            for listing in listings:
                if listing["seller_id"] != user_id:
                    target_auction = listing
                    break
            
            if not target_auction:
                print("No suitable auction found (all owned by test user)")
                return
            
            print(f"Target auction: {target_auction['title']}")
            print(f"Auction ID: {target_auction['id']}")
            print(f"Seller ID: {target_auction['seller_id']}")
            print(f"Test User ID: {user_id}")
            
            # Get auction details to see lots
            async with session.get(f"{BASE_URL}/multi-item-listings/{target_auction['id']}") as response:
                if response.status != 200:
                    print(f"Failed to get auction details: {response.status}")
                    return
                
                auction_details = await response.json()
                lots = auction_details.get("lots", [])
                print(f"Auction has {len(lots)} lots")
                
                if lots:
                    lot_1 = lots[0]
                    print(f"Lot 1: {lot_1['title']}")
                    print(f"Current price: ${lot_1['current_price']}")
                    print(f"Lot number: {lot_1['lot_number']}")
                    
                    # Try to place a bid
                    bid_amount = lot_1['current_price'] + 10  # Add $10 to current price
                    bid_data = {
                        "amount": bid_amount,
                        "bid_type": "normal"
                    }
                    
                    print(f"\n=== Attempting to place bid ===")
                    print(f"Bid amount: ${bid_amount}")
                    print(f"Bid type: normal")
                    
                    async with session.post(
                        f"{BASE_URL}/multi-item-listings/{target_auction['id']}/lots/{lot_1['lot_number']}/bid",
                        json=bid_data,
                        headers=headers
                    ) as bid_response:
                        print(f"Bid response status: {bid_response.status}")
                        
                        if bid_response.status == 200:
                            result = await bid_response.json()
                            print("✅ Bid placed successfully!")
                            print(f"Result: {json.dumps(result, indent=2)}")
                        else:
                            print(f"❌ Bid failed: {bid_response.status}")
                            try:
                                error_text = await bid_response.text()
                                print(f"Error response: {error_text}")
                            except:
                                print("Could not read error response")

if __name__ == "__main__":
    asyncio.run(debug_bid_placement())