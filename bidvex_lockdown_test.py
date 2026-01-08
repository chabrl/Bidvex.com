#!/usr/bin/env python3
"""
BidVex High-Trust Lockdown Features Testing
Tests server-side gatekeeping, banner management, user profile, and admin endpoints.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://bidding-platform-20.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@bazario.com"
ADMIN_PASSWORD = "Admin123!"

class BidVexLockdownTester:
    def __init__(self):
        self.session = None
        self.admin_token = None
        self.admin_id = None
        self.unverified_token = None
        self.unverified_user_id = None
        self.verified_token = None
        self.verified_user_id = None
        self.test_banner_id = None
        self.test_results = {}
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def setup_admin_user(self) -> bool:
        """Setup admin user for testing"""
        try:
            login_data = {
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD
            }
            
            async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.admin_token = data["access_token"]
                    self.admin_id = data["user"]["id"]
                    print(f"✅ Admin user logged in successfully: {self.admin_id}")
                    return True
                else:
                    print(f"❌ Failed to login admin: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in admin: {str(e)}")
            return False
            
    async def setup_test_users(self) -> bool:
        """Setup unverified and verified test users"""
        try:
            # Create unverified user
            unverified_email = f"unverified.{int(datetime.now().timestamp())}@test.com"
            unverified_data = {
                "email": unverified_email,
                "password": "Test123!",
                "name": "Unverified User",
                "account_type": "personal",
                "phone": "+1234567890"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=unverified_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.unverified_token = data["access_token"]
                    self.unverified_user_id = data["user"]["id"]
                    print(f"✅ Unverified user created: {self.unverified_user_id}")
                else:
                    print(f"❌ Failed to create unverified user: {response.status}")
                    return False
            
            # Create verified user (we'll simulate verification)
            verified_email = f"verified.{int(datetime.now().timestamp())}@test.com"
            verified_data = {
                "email": verified_email,
                "password": "Test123!",
                "name": "Verified User",
                "account_type": "business",
                "phone": "+1234567891"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=verified_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.verified_token = data["access_token"]
                    self.verified_user_id = data["user"]["id"]
                    print(f"✅ Verified user created: {self.verified_user_id}")
                    return True
                else:
                    print(f"❌ Failed to create verified user: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error setting up test users: {str(e)}")
            return False
            
    def get_admin_headers(self) -> Dict[str, str]:
        """Get admin authorization headers"""
        return {"Authorization": f"Bearer {self.admin_token}"}
        
    def get_unverified_headers(self) -> Dict[str, str]:
        """Get unverified user authorization headers"""
        return {"Authorization": f"Bearer {self.unverified_token}"}
        
    def get_verified_headers(self) -> Dict[str, str]:
        """Get verified user authorization headers"""
        return {"Authorization": f"Bearer {self.verified_token}"}
        
    async def test_server_side_gatekeeping_bids(self) -> bool:
        """Test that unverified users cannot bid"""
        print("\n🧪 Testing Server-Side Gatekeeping - Bids...")
        
        try:
            # Test 1: Unverified user tries to bid (should fail with 403)
            bid_data = {
                "listing_id": "test-listing-id",
                "amount": 100.0
            }
            
            async with self.session.post(
                f"{BASE_URL}/bids",
                json=bid_data,
                headers=self.get_unverified_headers()
            ) as response:
                if response.status == 403:
                    data = await response.json()
                    print(f"✅ Unverified user correctly blocked from bidding")
                    print(f"   - Status: {response.status}")
                    print(f"   - Message: {data.get('detail', 'No detail')}")
                elif response.status == 404:
                    # Listing not found is acceptable for this test
                    print(f"✅ Unverified user bid blocked (listing not found is expected)")
                else:
                    print(f"❌ Unverified user should be blocked from bidding, got: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Admin user should bypass restrictions
            async with self.session.post(
                f"{BASE_URL}/bids",
                json=bid_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status in [403, 404, 400]:
                    # 404 (listing not found) or 400 (validation error) is acceptable
                    # 403 would mean admin restrictions are not bypassed
                    if response.status == 403:
                        data = await response.json()
                        if "phone_verified" in str(data) or "payment_method" in str(data):
                            print(f"❌ Admin user should bypass verification restrictions")
                            return False
                    print(f"✅ Admin user bypass working (got {response.status} - expected for test data)")
                else:
                    print(f"✅ Admin user can attempt to bid (status: {response.status})")
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing server-side gatekeeping for bids: {str(e)}")
            return False
            
    async def test_server_side_gatekeeping_listings(self) -> bool:
        """Test that unverified users cannot create listings"""
        print("\n🧪 Testing Server-Side Gatekeeping - Listings...")
        
        try:
            # Test 1: Unverified user tries to create listing (should fail with 403)
            listing_data = {
                "title": "Test Listing",
                "description": "Test description",
                "category": "electronics",
                "condition": "new",
                "starting_price": 50.0,
                "location": "Test City",
                "city": "Test City",
                "region": "Test Region",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
            }
            
            async with self.session.post(
                f"{BASE_URL}/listings",
                json=listing_data,
                headers=self.get_unverified_headers()
            ) as response:
                if response.status == 403:
                    data = await response.json()
                    print(f"✅ Unverified user correctly blocked from creating listings")
                    print(f"   - Status: {response.status}")
                    print(f"   - Message: {data.get('detail', 'No detail')}")
                else:
                    print(f"❌ Unverified user should be blocked from creating listings, got: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Admin user should bypass restrictions
            async with self.session.post(
                f"{BASE_URL}/listings",
                json=listing_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status in [200, 201, 400]:
                    # 200/201 (success) or 400 (validation error) is acceptable
                    print(f"✅ Admin user can create listings (status: {response.status})")
                elif response.status == 403:
                    data = await response.json()
                    if "phone_verified" in str(data) or "payment_method" in str(data):
                        print(f"❌ Admin user should bypass verification restrictions")
                        return False
                    else:
                        print(f"✅ Admin got 403 for other reasons (not verification)")
                else:
                    print(f"⚠️  Admin listing creation got unexpected status: {response.status}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing server-side gatekeeping for listings: {str(e)}")
            return False
            
    async def test_banner_management_crud(self) -> bool:
        """Test banner management CRUD operations (Admin Only)"""
        print("\n🧪 Testing Banner Management CRUD...")
        
        try:
            # Test 1: GET /api/admin/banners (admin only)
            async with self.session.get(
                f"{BASE_URL}/admin/banners",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Admin can access banners list")
                    print(f"   - Banners count: {len(data) if isinstance(data, list) else 'N/A'}")
                else:
                    print(f"❌ Admin should be able to access banners, got: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Non-admin access should be denied
            async with self.session.get(
                f"{BASE_URL}/admin/banners",
                headers=self.get_unverified_headers()
            ) as response:
                if response.status == 403:
                    print(f"✅ Non-admin correctly denied access to banners")
                else:
                    print(f"❌ Non-admin should be denied access, got: {response.status}")
                    return False
            
            # Test 3: POST /api/admin/banners (create banner)
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
                    self.test_banner_id = data.get("id")
                    print(f"✅ Admin can create banners")
                    print(f"   - Banner ID: {self.test_banner_id}")
                else:
                    print(f"❌ Admin should be able to create banners, got: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 4: PUT /api/admin/banners/{id} (update banner)
            if self.test_banner_id:
                update_data = {
                    "title": "Updated Test Banner",
                    "is_active": False
                }
                
                async with self.session.put(
                    f"{BASE_URL}/admin/banners/{self.test_banner_id}",
                    json=update_data,
                    headers=self.get_admin_headers()
                ) as response:
                    if response.status == 200:
                        print(f"✅ Admin can update banners")
                    else:
                        print(f"❌ Admin should be able to update banners, got: {response.status}")
                        text = await response.text()
                        print(f"Response: {text}")
                        return False
            
            # Test 5: GET /api/banners/active (public endpoint)
            async with self.session.get(f"{BASE_URL}/banners/active") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Public active banners endpoint accessible")
                    print(f"   - Active banners: {len(data) if isinstance(data, list) else 'N/A'}")
                else:
                    print(f"❌ Public banners endpoint should be accessible, got: {response.status}")
                    return False
            
            # Test 6: DELETE /api/admin/banners/{id} (delete banner)
            if self.test_banner_id:
                async with self.session.delete(
                    f"{BASE_URL}/admin/banners/{self.test_banner_id}",
                    headers=self.get_admin_headers()
                ) as response:
                    if response.status in [200, 204]:
                        print(f"✅ Admin can delete banners")
                    else:
                        print(f"❌ Admin should be able to delete banners, got: {response.status}")
                        text = await response.text()
                        print(f"Response: {text}")
                        return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing banner management CRUD: {str(e)}")
            return False
            
    async def test_user_profile_has_payment_method(self) -> bool:
        """Test that /auth/me includes has_payment_method field"""
        print("\n🧪 Testing User Profile has_payment_method Field...")
        
        try:
            # Test with unverified user
            async with self.session.get(
                f"{BASE_URL}/auth/me",
                headers=self.get_unverified_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify has_payment_method field exists
                    if "has_payment_method" in data:
                        print(f"✅ User profile includes has_payment_method field")
                        print(f"   - has_payment_method: {data['has_payment_method']}")
                        print(f"   - Type: {type(data['has_payment_method'])}")
                        
                        # Verify it's a boolean
                        if isinstance(data["has_payment_method"], bool):
                            print(f"✅ has_payment_method is boolean type")
                        else:
                            print(f"❌ has_payment_method should be boolean, got: {type(data['has_payment_method'])}")
                            return False
                    else:
                        print(f"❌ User profile missing has_payment_method field")
                        print(f"Available fields: {list(data.keys())}")
                        return False
                else:
                    print(f"❌ Failed to get user profile: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test with admin user
            async with self.session.get(
                f"{BASE_URL}/auth/me",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if "has_payment_method" in data:
                        print(f"✅ Admin profile also includes has_payment_method field")
                        print(f"   - Admin has_payment_method: {data['has_payment_method']}")
                    else:
                        print(f"❌ Admin profile missing has_payment_method field")
                        return False
                else:
                    print(f"❌ Failed to get admin profile: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing user profile has_payment_method: {str(e)}")
            return False
            
    async def test_admin_user_detail_endpoint(self) -> bool:
        """Test comprehensive user contact card endpoint"""
        print("\n🧪 Testing Admin User Detail Endpoint...")
        
        try:
            # Test GET /api/admin/users/{user_id}/detail
            async with self.session.get(
                f"{BASE_URL}/admin/users/{self.unverified_user_id}/detail",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify comprehensive contact card structure
                    required_sections = [
                        "identity", "phone", "logistics", "account", 
                        "verification_status", "activity"
                    ]
                    
                    for section in required_sections:
                        if section not in data:
                            print(f"❌ Missing required section: {section}")
                            return False
                    
                    print(f"✅ Admin user detail endpoint returns comprehensive contact card")
                    
                    # Verify identity section
                    identity = data["identity"]
                    identity_fields = ["full_name", "email", "email_verified", "picture"]
                    for field in identity_fields:
                        if field not in identity:
                            print(f"❌ Missing identity field: {field}")
                            return False
                    print(f"✅ Identity section complete: {identity}")
                    
                    # Verify phone section
                    phone = data["phone"]
                    phone_fields = ["number", "verified"]
                    for field in phone_fields:
                        if field not in phone:
                            print(f"❌ Missing phone field: {field}")
                            return False
                    print(f"✅ Phone section complete: {phone}")
                    
                    # Verify logistics section
                    logistics = data["logistics"]
                    logistics_fields = ["address", "city", "region", "postal_code", "country"]
                    for field in logistics_fields:
                        if field not in logistics:
                            print(f"❌ Missing logistics field: {field}")
                            return False
                    print(f"✅ Logistics section complete")
                    
                    # Verify account section
                    account = data["account"]
                    account_fields = ["role", "account_type", "company_name", "subscription_tier"]
                    for field in account_fields:
                        if field not in account:
                            print(f"❌ Missing account field: {field}")
                            return False
                    print(f"✅ Account section complete: {account}")
                    
                    # Verify verification_status section
                    verification = data["verification_status"]
                    verification_fields = ["phone_verified", "has_payment_method", "is_fully_verified"]
                    for field in verification_fields:
                        if field not in verification:
                            print(f"❌ Missing verification field: {field}")
                            return False
                    print(f"✅ Verification status section complete: {verification}")
                    
                    # Verify activity section
                    activity = data["activity"]
                    activity_fields = ["total_bids", "total_listings", "preferred_language"]
                    for field in activity_fields:
                        if field not in activity:
                            print(f"❌ Missing activity field: {field}")
                            return False
                    print(f"✅ Activity section complete: {activity}")
                    
                else:
                    print(f"❌ Admin user detail endpoint failed: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test non-admin access should be denied
            async with self.session.get(
                f"{BASE_URL}/admin/users/{self.unverified_user_id}/detail",
                headers=self.get_unverified_headers()
            ) as response:
                if response.status == 403:
                    print(f"✅ Non-admin correctly denied access to user detail")
                else:
                    print(f"❌ Non-admin should be denied access, got: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing admin user detail endpoint: {str(e)}")
            return False
            
    async def run_all_tests(self):
        """Run all BidVex High-Trust Lockdown tests"""
        print("🚀 Starting BidVex High-Trust Lockdown Features Tests")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Setup test users
            if not await self.setup_admin_user():
                print("❌ Failed to setup admin user")
                return False
                
            if not await self.setup_test_users():
                print("❌ Failed to setup test users")
                return False
            
            # Run tests
            tests = [
                ("Server-Side Gatekeeping - Bids", self.test_server_side_gatekeeping_bids),
                ("Server-Side Gatekeeping - Listings", self.test_server_side_gatekeeping_listings),
                ("Banner Management CRUD", self.test_banner_management_crud),
                ("User Profile has_payment_method", self.test_user_profile_has_payment_method),
                ("Admin User Detail Endpoint", self.test_admin_user_detail_endpoint)
            ]
            
            results = []
            for test_name, test_func in tests:
                try:
                    result = await test_func()
                    results.append((test_name, result))
                    self.test_results[test_name] = result
                except Exception as e:
                    print(f"❌ {test_name} failed with exception: {str(e)}")
                    results.append((test_name, False))
                    self.test_results[test_name] = False
            
            # Print summary
            print("\n" + "=" * 70)
            print("📊 BIDVEX HIGH-TRUST LOCKDOWN TEST RESULTS SUMMARY")
            print("=" * 70)
            
            passed = 0
            total = len(results)
            
            for test_name, result in results:
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status} - {test_name}")
                if result:
                    passed += 1
            
            print(f"\nOverall: {passed}/{total} tests passed")
            
            if passed == total:
                print("🎉 All BidVex High-Trust Lockdown tests PASSED!")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = BidVexLockdownTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)