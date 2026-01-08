#!/usr/bin/env python3
"""
Debug Marketplace Settings API Testing
"""

import asyncio
import aiohttp
import json
import traceback

BASE_URL = "https://bidding-platform-20.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@bazario.com"
ADMIN_PASSWORD = "Admin123!"

async def debug_test():
    async with aiohttp.ClientSession() as session:
        # Login as admin
        print("🔐 Logging in as admin...")
        login_data = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        
        async with session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
            if response.status != 200:
                print(f"❌ Login failed: {response.status}")
                text = await response.text()
                print(f"Response: {text}")
                return
            
            data = await response.json()
            admin_token = data["access_token"]
            print(f"✅ Admin logged in successfully")
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Test GET marketplace settings
        print("\n🧪 Testing GET /api/admin/marketplace-settings...")
        async with session.get(f"{BASE_URL}/admin/marketplace-settings", headers=headers) as response:
            print(f"Status: {response.status}")
            if response.status == 200:
                data = await response.json()
                print(f"✅ GET successful")
                print(f"Settings: {json.dumps(data, indent=2)}")
            else:
                text = await response.text()
                print(f"❌ GET failed: {text}")
                return
        
        # Test PUT with invalid value
        print("\n🧪 Testing PUT with invalid max_active_auctions_per_user (150)...")
        try:
            async with session.put(
                f"{BASE_URL}/admin/marketplace-settings",
                json={"max_active_auctions_per_user": 150},
                headers=headers
            ) as response:
                print(f"Status: {response.status}")
                text = await response.text()
                print(f"Response: {text}")
                
                if response.status == 400:
                    data = await response.json()
                    print(f"✅ Correctly rejected invalid value")
                    print(f"Error: {data.get('detail')}")
                else:
                    print(f"❌ Expected 400, got {response.status}")
        except Exception as e:
            print(f"❌ Exception in PUT test: {str(e)}")
            traceback.print_exc()
        
        # Test valid PUT
        print("\n🧪 Testing PUT with valid values...")
        try:
            async with session.put(
                f"{BASE_URL}/admin/marketplace-settings",
                json={"max_active_auctions_per_user": 25, "enable_buy_now": False},
                headers=headers
            ) as response:
                print(f"Status: {response.status}")
                text = await response.text()
                print(f"Response: {text}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Valid PUT successful")
                    print(f"Updated settings: {json.dumps(data, indent=2)}")
                else:
                    print(f"❌ Valid PUT failed")
        except Exception as e:
            print(f"❌ Exception in valid PUT test: {str(e)}")
            traceback.print_exc()
        
        # Test restore defaults
        print("\n🧪 Testing POST /api/admin/marketplace-settings/restore-defaults...")
        try:
            async with session.post(
                f"{BASE_URL}/admin/marketplace-settings/restore-defaults",
                headers=headers
            ) as response:
                print(f"Status: {response.status}")
                text = await response.text()
                print(f"Response: {text}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Restore defaults successful")
                    print(f"Default settings: {json.dumps(data, indent=2)}")
                else:
                    print(f"❌ Restore defaults failed")
        except Exception as e:
            print(f"❌ Exception in restore defaults test: {str(e)}")
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_test())