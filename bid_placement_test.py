#!/usr/bin/env python3
"""
Quick test for bid placement ObjectId fix
"""

import asyncio
import aiohttp
import json

BASE_URL = "https://bidvault-2.preview.emergentagent.com/api"
TEST_USER_EMAIL = "lots.homepage.tester@bazario.com"
TEST_USER_PASSWORD = "LotsTest123!"

async def test_bid_placement():
    async with aiohttp.ClientSession() as session:
        # Login
        login_data = {
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        }
        
        async with session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
            if response.status != 200:
                print(f"❌ Login failed: {response.status}")
                return False
            
            data = await response.json()
            auth_token = data["access_token"]
            headers = {"Authorization": f"Bearer {auth_token}"}
            print(f"✅ Logged in successfully")
        
        # Get active auction
        async with session.get(f"{BASE_URL}/multi-item-listings?status=active") as response:
            if response.status != 200:
                print(f"❌ Failed to get active auctions: {response.status}")
                return False
            
            auctions = await response.json()
            if not auctions:
                print("❌ No active auctions found")
                return False
            
            auction = auctions[0]
            auction_id = auction["id"]
            print(f"✅ Found active auction: {auction['title']}")
        
        # Test bid placement with proper amount
        async with session.get(f"{BASE_URL}/multi-item-listings/{auction_id}") as response:
            if response.status != 200:
                print(f"❌ Failed to get auction details: {response.status}")
                return False
            
            auction_details = await response.json()
            lots = auction_details.get("lots", [])
            if not lots:
                print("❌ No lots found in auction")
                return False
            
            lot_1 = lots[0]
            current_price = lot_1.get("current_price", 0)
            print(f"✅ Lot 1 current price: ${current_price}")
        
        # Place bid with sufficient amount
        bid_amount = current_price + 100  # Bid well above current price
        bid_data = {
            "amount": bid_amount,
            "bid_type": "normal"
        }
        
        print(f"🧪 Testing bid placement: ${bid_amount}")
        async with session.post(
            f"{BASE_URL}/multi-item-listings/{auction_id}/lots/1/bid",
            json=bid_data,
            headers=headers
        ) as response:
            
            print(f"Response status: {response.status}")
            
            if response.status == 200:
                bid_response = await response.json()
                print(f"✅ SUCCESS: Bid placed without ObjectId error!")
                print(f"   - Bid ID: {bid_response['bid']['id']}")
                print(f"   - Amount: ${bid_response['bid']['amount']}")
                print(f"   - Bid Type: {bid_response['bid']['bid_type']}")
                print(f"   - Message: {bid_response['message']}")
                return True
            elif response.status == 400:
                error_data = await response.json()
                error_detail = error_data.get("detail", "")
                print(f"⚠️  400 Bad Request: {error_detail}")
                
                if "cannot bid on your own listing" in error_detail.lower():
                    print("   - This is expected - user owns the auction")
                    print("   - ObjectId fix is working (no 500 error)")
                    return True
                else:
                    print("   - This may be expected validation")
                    return True
            elif response.status == 500:
                text = await response.text()
                print(f"❌ CRITICAL: 500 Internal Server Error - ObjectId issue still exists")
                print(f"   Error: {text}")
                return False
            else:
                text = await response.text()
                print(f"❌ Unexpected response: {response.status} - {text}")
                return False

async def main():
    success = await test_bid_placement()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    print(f"\n{'✅ PASS' if success else '❌ FAIL'} - Bid Placement ObjectId Fix Test")
    exit(0 if success else 1)