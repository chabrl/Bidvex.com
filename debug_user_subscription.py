#!/usr/bin/env python3
"""
Debug script to check user subscription tiers
"""

import asyncio
import aiohttp
import json
from datetime import datetime

BASE_URL = "https://auction-house-2.preview.emergentagent.com/api"

async def debug_user_subscription():
    """Debug user subscription tier setting"""
    
    async with aiohttp.ClientSession() as session:
        # Create a test user
        test_email = f"debug.user.{int(datetime.now().timestamp())}@bazario.com"
        user_data = {
            "email": test_email,
            "password": "DebugTest123!",
            "name": "Debug Test User",
            "account_type": "business",
            "phone": "+1234567890"
        }
        
        print(f"Creating user: {test_email}")
        
        async with session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
            if response.status == 200:
                data = await response.json()
                user = data["user"]
                token = data["access_token"]
                
                print(f"✅ User created successfully")
                print(f"User ID: {user['id']}")
                print(f"Subscription Tier: {user.get('subscription_tier', 'NOT SET')}")
                print(f"Account Type: {user.get('account_type')}")
                
                # Try to get user info via /auth/me
                headers = {"Authorization": f"Bearer {token}"}
                async with session.get(f"{BASE_URL}/auth/me", headers=headers) as me_response:
                    if me_response.status == 200:
                        me_data = await me_response.json()
                        print(f"\nFrom /auth/me:")
                        print(f"Subscription Tier: {me_data.get('subscription_tier', 'NOT SET')}")
                        print(f"Account Type: {me_data.get('account_type')}")
                        
                        # Try to update subscription tier via profile update
                        update_data = {"subscription_tier": "vip"}
                        async with session.put(f"{BASE_URL}/users/me", json=update_data, headers=headers) as update_response:
                            print(f"\nTrying to update subscription_tier to 'vip'...")
                            print(f"Update response status: {update_response.status}")
                            if update_response.status != 200:
                                text = await update_response.text()
                                print(f"Update response: {text}")
                            else:
                                print("✅ Update successful")
                                
                                # Check again
                                async with session.get(f"{BASE_URL}/auth/me", headers=headers) as final_response:
                                    if final_response.status == 200:
                                        final_data = await final_response.json()
                                        print(f"Final subscription_tier: {final_data.get('subscription_tier', 'NOT SET')}")
                    
            else:
                print(f"❌ Failed to create user: {response.status}")
                text = await response.text()
                print(f"Response: {text}")

if __name__ == "__main__":
    asyncio.run(debug_user_subscription())