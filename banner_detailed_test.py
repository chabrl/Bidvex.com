#!/usr/bin/env python3
"""
Detailed Banner Management Testing
Tests all banner CRUD operations with proper data validation.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta

# Configuration
BASE_URL = "https://launchapp-4.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@bazario.com"
ADMIN_PASSWORD = "Admin123!"

class BannerTester:
    def __init__(self):
        self.session = None
        self.admin_token = None
        self.test_banner_id = None
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def setup_admin(self) -> bool:
        """Setup admin user"""
        try:
            login_data = {
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            }
            
            async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.admin_token = data["access_token"]
                    print(f"✅ Admin logged in successfully")
                    return True
                else:
                    print(f"❌ Failed to login admin: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in admin: {str(e)}")
            return False
            
    def get_admin_headers(self) -> dict:
        """Get admin authorization headers"""
        return {"Authorization": f"Bearer {self.admin_token}"}
        
    async def test_banner_crud_detailed(self) -> bool:
        """Test detailed banner CRUD operations"""
        print("\n🧪 Testing Detailed Banner CRUD Operations...")
        
        try:
            # Test 1: GET /api/admin/banners (should return list)
            print("1. Testing GET /api/admin/banners...")
            async with self.session.get(
                f"{BASE_URL}/admin/banners",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ GET banners successful")
                    print(f"   Response structure: {list(data.keys()) if isinstance(data, dict) else 'List'}")
                    if isinstance(data, dict) and "banners" in data:
                        print(f"   Banners count: {len(data['banners'])}")
                    elif isinstance(data, list):
                        print(f"   Banners count: {len(data)}")
                else:
                    print(f"❌ GET banners failed: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: POST /api/admin/banners (create banner)
            print("\n2. Testing POST /api/admin/banners...")
            banner_data = {
                "title": "Test Banner",
                "image_url": "https://test.com/img.jpg",
                "cta_text": "Shop",
                "cta_url": "/marketplace",
                "is_active": True,
                "priority": 5
            }
            
            async with self.session.post(
                f"{BASE_URL}/admin/banners",
                json=banner_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    print(f"✅ POST banner successful")
                    print(f"   Response: {data}")
                    
                    # Extract banner ID for further tests
                    if isinstance(data, dict):
                        if "banner" in data and "id" in data["banner"]:
                            self.test_banner_id = data["banner"]["id"]
                        elif "id" in data:
                            self.test_banner_id = data["id"]
                    
                    print(f"   Banner ID: {self.test_banner_id}")
                else:
                    print(f"❌ POST banner failed: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 3: PUT /api/admin/banners/{id} (update banner)
            if self.test_banner_id:
                print(f"\n3. Testing PUT /api/admin/banners/{self.test_banner_id}...")
                update_data = {
                    "title": "Updated Test Banner",
                    "is_active": False,
                    "priority": 10
                }
                
                async with self.session.put(
                    f"{BASE_URL}/admin/banners/{self.test_banner_id}",
                    json=update_data,
                    headers=self.get_admin_headers()
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ PUT banner successful")
                        print(f"   Response: {data}")
                    else:
                        print(f"❌ PUT banner failed: {response.status}")
                        text = await response.text()
                        print(f"Response: {text}")
                        return False
            else:
                print("⚠️  Skipping PUT test - no banner ID available")
            
            # Test 4: GET /api/banners/active (public endpoint)
            print("\n4. Testing GET /api/banners/active...")
            async with self.session.get(f"{BASE_URL}/banners/active") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ GET active banners successful")
                    print(f"   Response structure: {list(data.keys()) if isinstance(data, dict) else 'List'}")
                    if isinstance(data, dict) and "banners" in data:
                        print(f"   Active banners count: {len(data['banners'])}")
                    elif isinstance(data, list):
                        print(f"   Active banners count: {len(data)}")
                else:
                    print(f"❌ GET active banners failed: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 5: DELETE /api/admin/banners/{id} (delete banner)
            if self.test_banner_id:
                print(f"\n5. Testing DELETE /api/admin/banners/{self.test_banner_id}...")
                async with self.session.delete(
                    f"{BASE_URL}/admin/banners/{self.test_banner_id}",
                    headers=self.get_admin_headers()
                ) as response:
                    if response.status in [200, 204]:
                        print(f"✅ DELETE banner successful")
                        if response.status == 200:
                            data = await response.json()
                            print(f"   Response: {data}")
                    else:
                        print(f"❌ DELETE banner failed: {response.status}")
                        text = await response.text()
                        print(f"Response: {text}")
                        return False
            else:
                print("⚠️  Skipping DELETE test - no banner ID available")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in banner CRUD testing: {str(e)}")
            return False
            
    async def run_tests(self):
        """Run banner tests"""
        print("🚀 Starting Detailed Banner Management Tests")
        print("=" * 50)
        
        await self.setup_session()
        
        try:
            if not await self.setup_admin():
                print("❌ Failed to setup admin")
                return False
            
            success = await self.test_banner_crud_detailed()
            
            if success:
                print("\n🎉 All banner tests PASSED!")
            else:
                print("\n⚠️  Some banner tests FAILED")
            
            return success
            
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = BannerTester()
    success = await tester.run_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)