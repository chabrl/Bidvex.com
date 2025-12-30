#!/usr/bin/env python3
"""
VIP Auto-Promotion Backend Testing for Bazario Multi-Item Listings
Tests the VIP auto-promotion logic in POST /api/multi-item-listings endpoint.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://vscodeshare-1.preview.emergentagent.com/api"

class VIPAutoPromotionTester:
    def __init__(self):
        self.session = None
        self.test_results = {}
        
        # Test users for different subscription tiers
        self.vip_user = {
            "email": f"vip.user.{int(datetime.now().timestamp())}@bazario.com",
            "password": "VIPTest123!",
            "name": "VIP Test User",
            "account_type": "business",
            "phone": "+1234567890",
            "subscription_tier": "vip"
        }
        
        self.premium_user = {
            "email": f"premium.user.{int(datetime.now().timestamp())}@bazario.com", 
            "password": "PremiumTest123!",
            "name": "Premium Test User",
            "account_type": "business",
            "phone": "+1234567891",
            "subscription_tier": "premium"
        }
        
        self.free_user = {
            "email": f"free.user.{int(datetime.now().timestamp())}@bazario.com",
            "password": "FreeTest123!",
            "name": "Free Test User", 
            "account_type": "business",
            "phone": "+1234567892",
            "subscription_tier": "free"
        }
        
        self.no_tier_user = {
            "email": f"notier.user.{int(datetime.now().timestamp())}@bazario.com",
            "password": "NoTierTest123!",
            "name": "No Tier Test User",
            "account_type": "business", 
            "phone": "+1234567893"
            # No subscription_tier field - should default to "free"
        }
        
        # Store tokens and IDs
        self.user_tokens = {}
        self.user_ids = {}
        self.created_listings = []
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def register_and_login_user(self, user_data: Dict[str, Any], user_key: str) -> bool:
        """Register a test user and get auth token"""
        try:
            # Try to register user
            async with self.session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.user_tokens[user_key] = data["access_token"]
                    self.user_ids[user_key] = data["user"]["id"]
                    
                    # Update subscription tier if specified
                    if "subscription_tier" in user_data:
                        await self.update_user_subscription_tier(user_key, user_data["subscription_tier"])
                    
                    print(f"✅ {user_key.upper()} user registered: {self.user_ids[user_key]}")
                    return True
                elif response.status == 400:
                    # User might already exist, try login
                    return await self.login_user(user_data, user_key)
                else:
                    print(f"❌ Failed to register {user_key} user: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error registering {user_key} user: {str(e)}")
            return False
            
    async def login_user(self, user_data: Dict[str, Any], user_key: str) -> bool:
        """Login with user credentials"""
        try:
            login_data = {
                "email": user_data["email"],
                "password": user_data["password"]
            }
            
            async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.user_tokens[user_key] = data["access_token"]
                    self.user_ids[user_key] = data["user"]["id"]
                    
                    # Update subscription tier if specified
                    if "subscription_tier" in user_data:
                        await self.update_user_subscription_tier(user_key, user_data["subscription_tier"])
                    
                    print(f"✅ {user_key.upper()} user logged in: {self.user_ids[user_key]}")
                    return True
                else:
                    print(f"❌ Failed to login {user_key} user: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in {user_key} user: {str(e)}")
            return False
            
    async def update_user_subscription_tier(self, user_key: str, tier: str):
        """Update user's subscription tier via profile update API"""
        try:
            async with self.session.put(
                f"{BASE_URL}/users/me",
                json={"subscription_tier": tier},
                headers=self.get_auth_headers(user_key)
            ) as response:
                if response.status == 200:
                    print(f"   - Updated {user_key} subscription tier to: {tier}")
                    return True
                else:
                    print(f"   - Failed to update {user_key} subscription tier: {response.status}")
                    return False
        except Exception as e:
            print(f"   - Error updating {user_key} subscription tier: {str(e)}")
            return False
        
    def get_auth_headers(self, user_key: str) -> Dict[str, str]:
        """Get authorization headers for a specific user"""
        return {"Authorization": f"Bearer {self.user_tokens[user_key]}"}
        
    def create_sample_listing_data(self) -> Dict[str, Any]:
        """Create sample multi-item listing data"""
        end_date = datetime.now(timezone.utc) + timedelta(days=7)
        
        return {
            "title": f"VIP Test Auction {int(datetime.now().timestamp())}",
            "description": "Test auction for VIP auto-promotion feature testing",
            "category": "Antiques & Collectibles",
            "location": "123 Test Street, Test City, ON",
            "city": "Test City",
            "region": "Ontario",
            "auction_end_date": end_date.isoformat(),
            "lots": [
                {
                    "lot_number": 1,
                    "title": "Vintage Test Item 1",
                    "description": "A beautiful vintage test item for auction testing purposes",
                    "quantity": 1,
                    "starting_price": 50.0,
                    "current_price": 50.0,
                    "condition": "excellent",
                    "images": ["https://example.com/image1.jpg"]
                },
                {
                    "lot_number": 2,
                    "title": "Antique Test Item 2", 
                    "description": "An exquisite antique test item with historical significance",
                    "quantity": 1,
                    "starting_price": 100.0,
                    "current_price": 100.0,
                    "condition": "good",
                    "images": ["https://example.com/image2.jpg"]
                }
            ]
        }
        
    async def test_vip_user_auto_promotion(self) -> bool:
        """Test VIP user creates listing with auto-promotion"""
        print("\n🧪 Testing VIP User Auto-Promotion...")
        
        try:
            listing_data = self.create_sample_listing_data()
            listing_data["title"] = "VIP Auto-Promotion Test Listing"
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_auth_headers("vip")
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    listing_id = data["id"]
                    self.created_listings.append(listing_id)
                    
                    # Verify VIP auto-promotion fields
                    assert data["is_featured"] == True, "VIP listing should be featured"
                    assert data["promotion_expiry"] is not None, "VIP listing should have promotion_expiry"
                    
                    # Verify promotion_expiry is approximately 7 days from now
                    promotion_expiry = datetime.fromisoformat(data["promotion_expiry"].replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    expected_expiry = now + timedelta(days=7)
                    
                    # Allow 1 minute tolerance for processing time
                    time_diff = abs((promotion_expiry - expected_expiry).total_seconds())
                    assert time_diff < 60, f"Promotion expiry should be ~7 days from now, got {time_diff}s difference"
                    
                    print(f"✅ VIP user listing auto-promoted successfully")
                    print(f"   - Listing ID: {listing_id}")
                    print(f"   - is_featured: {data['is_featured']}")
                    print(f"   - promotion_expiry: {data['promotion_expiry']}")
                    print(f"   - Time until expiry: ~{(promotion_expiry - now).days} days")
                    
                    return True
                else:
                    print(f"❌ Failed to create VIP listing: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing VIP auto-promotion: {str(e)}")
            return False
            
    async def test_non_vip_user_no_promotion(self) -> bool:
        """Test non-VIP users (Free, Premium) don't get auto-promotion"""
        print("\n🧪 Testing Non-VIP Users (No Auto-Promotion)...")
        
        success = True
        
        # Test Free user
        try:
            listing_data = self.create_sample_listing_data()
            listing_data["title"] = "Free User Test Listing"
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_auth_headers("free")
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    listing_id = data["id"]
                    self.created_listings.append(listing_id)
                    
                    # Verify NO auto-promotion for free user
                    assert data["is_featured"] == False, "Free user listing should NOT be featured"
                    assert data["promotion_expiry"] is None, "Free user listing should NOT have promotion_expiry"
                    
                    print(f"✅ Free user listing correctly NOT auto-promoted")
                    print(f"   - Listing ID: {listing_id}")
                    print(f"   - is_featured: {data['is_featured']}")
                    print(f"   - promotion_expiry: {data['promotion_expiry']}")
                else:
                    print(f"❌ Failed to create Free user listing: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing Free user: {str(e)}")
            success = False
            
        # Test Premium user
        try:
            listing_data = self.create_sample_listing_data()
            listing_data["title"] = "Premium User Test Listing"
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_auth_headers("premium")
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    listing_id = data["id"]
                    self.created_listings.append(listing_id)
                    
                    # Verify NO auto-promotion for premium user
                    assert data["is_featured"] == False, "Premium user listing should NOT be featured"
                    assert data["promotion_expiry"] is None, "Premium user listing should NOT have promotion_expiry"
                    
                    print(f"✅ Premium user listing correctly NOT auto-promoted")
                    print(f"   - Listing ID: {listing_id}")
                    print(f"   - is_featured: {data['is_featured']}")
                    print(f"   - promotion_expiry: {data['promotion_expiry']}")
                else:
                    print(f"❌ Failed to create Premium user listing: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing Premium user: {str(e)}")
            success = False
            
        return success
        
    async def test_no_subscription_tier_user(self) -> bool:
        """Test user with no subscription_tier field (should default to free)"""
        print("\n🧪 Testing User with No Subscription Tier (Default to Free)...")
        
        try:
            listing_data = self.create_sample_listing_data()
            listing_data["title"] = "No Tier User Test Listing"
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_auth_headers("no_tier")
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    listing_id = data["id"]
                    self.created_listings.append(listing_id)
                    
                    # Verify NO auto-promotion (defaults to free behavior)
                    assert data["is_featured"] == False, "User with no tier should NOT be featured"
                    assert data["promotion_expiry"] is None, "User with no tier should NOT have promotion_expiry"
                    
                    print(f"✅ User with no subscription_tier correctly NOT auto-promoted")
                    print(f"   - Listing ID: {listing_id}")
                    print(f"   - is_featured: {data['is_featured']}")
                    print(f"   - promotion_expiry: {data['promotion_expiry']}")
                    
                    return True
                else:
                    print(f"❌ Failed to create no-tier user listing: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing no-tier user: {str(e)}")
            return False
            
    async def test_vip_listing_retrieval(self) -> bool:
        """Test GET /api/multi-item-listings shows correct featured status"""
        print("\n🧪 Testing VIP Listing Retrieval (GET endpoints)...")
        
        try:
            # Test GET all listings
            async with self.session.get(f"{BASE_URL}/multi-item-listings") as response:
                if response.status == 200:
                    listings = await response.json()
                    
                    # Find our test listings
                    vip_listings = [l for l in listings if l.get("is_featured") == True and "VIP" in l.get("title", "")]
                    non_vip_listings = [l for l in listings if l.get("is_featured") == False and ("Free" in l.get("title", "") or "Premium" in l.get("title", "") or "No Tier" in l.get("title", ""))]
                    
                    print(f"✅ Retrieved listings successfully")
                    print(f"   - Total listings: {len(listings)}")
                    print(f"   - VIP featured listings found: {len(vip_listings)}")
                    print(f"   - Non-VIP listings found: {len(non_vip_listings)}")
                    
                    # Verify VIP listings have proper promotion_expiry serialization
                    for listing in vip_listings:
                        if listing.get("promotion_expiry"):
                            # Verify it's a valid ISO datetime string
                            try:
                                expiry_date = datetime.fromisoformat(listing["promotion_expiry"].replace('Z', '+00:00'))
                                print(f"   - VIP listing {listing['id'][:8]}... expires: {expiry_date.strftime('%Y-%m-%d %H:%M')}")
                            except ValueError:
                                print(f"❌ Invalid promotion_expiry format: {listing['promotion_expiry']}")
                                return False
                    
                    return True
                else:
                    print(f"❌ Failed to retrieve listings: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing listing retrieval: {str(e)}")
            return False
            
    async def test_specific_listing_retrieval(self) -> bool:
        """Test GET /api/multi-item-listings/{id} for specific listings"""
        print("\n🧪 Testing Specific Listing Retrieval...")
        
        try:
            success = True
            
            # Test each created listing
            for listing_id in self.created_listings:
                async with self.session.get(f"{BASE_URL}/multi-item-listings/{listing_id}") as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Verify fields are properly deserialized
                        print(f"✅ Retrieved listing {listing_id[:8]}...")
                        print(f"   - Title: {data['title']}")
                        print(f"   - is_featured: {data['is_featured']}")
                        print(f"   - promotion_expiry: {data.get('promotion_expiry', 'None')}")
                        
                        # Verify datetime fields are properly handled
                        if data.get("promotion_expiry"):
                            try:
                                datetime.fromisoformat(data["promotion_expiry"].replace('Z', '+00:00'))
                            except ValueError:
                                print(f"❌ Invalid promotion_expiry format in specific listing")
                                success = False
                                
                    elif response.status == 404:
                        print(f"⚠️  Listing {listing_id[:8]}... not found (may have been deleted)")
                    else:
                        print(f"❌ Failed to retrieve listing {listing_id[:8]}...: {response.status}")
                        success = False
                        
            return success
            
        except Exception as e:
            print(f"❌ Error testing specific listing retrieval: {str(e)}")
            return False
            
    async def test_edge_cases(self) -> bool:
        """Test edge cases for VIP auto-promotion"""
        print("\n🧪 Testing Edge Cases...")
        
        try:
            success = True
            
            # Test 1: VIP listing with future auction_start_date (should still be promoted)
            future_start = datetime.now(timezone.utc) + timedelta(days=1)
            future_end = datetime.now(timezone.utc) + timedelta(days=8)
            
            listing_data = self.create_sample_listing_data()
            listing_data["title"] = "VIP Future Start Test Listing"
            listing_data["auction_start_date"] = future_start.isoformat()
            listing_data["auction_end_date"] = future_end.isoformat()
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_auth_headers("vip")
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    listing_id = data["id"]
                    self.created_listings.append(listing_id)
                    
                    # Should still be featured even with future start date
                    assert data["is_featured"] == True, "VIP listing with future start should still be featured"
                    assert data["promotion_expiry"] is not None, "VIP listing should have promotion_expiry"
                    assert data["status"] == "upcoming", "Listing with future start should have 'upcoming' status"
                    
                    print(f"✅ VIP listing with future start correctly promoted")
                    print(f"   - Status: {data['status']}")
                    print(f"   - is_featured: {data['is_featured']}")
                else:
                    print(f"❌ Failed to create VIP future start listing: {response.status}")
                    success = False
                    
            # Test 2: Verify promotion_expiry calculation precision
            if success:
                listing_data = self.create_sample_listing_data()
                listing_data["title"] = "VIP Precision Test Listing"
                
                creation_time = datetime.now(timezone.utc)
                
                async with self.session.post(
                    f"{BASE_URL}/multi-item-listings",
                    json=listing_data,
                    headers=self.get_auth_headers("vip")
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        listing_id = data["id"]
                        self.created_listings.append(listing_id)
                        
                        # Verify promotion_expiry is exactly 7 days from creation
                        promotion_expiry = datetime.fromisoformat(data["promotion_expiry"].replace('Z', '+00:00'))
                        expected_expiry = creation_time + timedelta(days=7)
                        
                        # Allow 2 minutes tolerance for processing
                        time_diff = abs((promotion_expiry - expected_expiry).total_seconds())
                        assert time_diff < 120, f"Promotion expiry precision issue: {time_diff}s difference"
                        
                        print(f"✅ VIP promotion expiry calculation precise")
                        print(f"   - Creation time: {creation_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        print(f"   - Expiry time: {promotion_expiry.strftime('%Y-%m-%d %H:%M:%S')}")
                        print(f"   - Difference from expected: {time_diff:.1f}s")
                    else:
                        print(f"❌ Failed to create VIP precision test listing: {response.status}")
                        success = False
                        
            return success
            
        except Exception as e:
            print(f"❌ Error testing edge cases: {str(e)}")
            return False
            
    async def test_mongodb_field_persistence(self) -> bool:
        """Test that promotion fields are correctly stored in MongoDB"""
        print("\n🧪 Testing MongoDB Field Persistence...")
        
        try:
            # Create a VIP listing and immediately retrieve it to verify persistence
            listing_data = self.create_sample_listing_data()
            listing_data["title"] = "VIP MongoDB Persistence Test"
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_auth_headers("vip")
            ) as response:
                if response.status == 200:
                    created_data = await response.json()
                    listing_id = created_data["id"]
                    self.created_listings.append(listing_id)
                    
                    # Immediately retrieve the listing to verify persistence
                    async with self.session.get(f"{BASE_URL}/multi-item-listings/{listing_id}") as get_response:
                        if get_response.status == 200:
                            retrieved_data = await get_response.json()
                            
                            # Verify fields match between creation and retrieval
                            assert created_data["is_featured"] == retrieved_data["is_featured"], "is_featured mismatch"
                            assert created_data["promotion_expiry"] == retrieved_data["promotion_expiry"], "promotion_expiry mismatch"
                            
                            print(f"✅ MongoDB field persistence verified")
                            print(f"   - Created is_featured: {created_data['is_featured']}")
                            print(f"   - Retrieved is_featured: {retrieved_data['is_featured']}")
                            print(f"   - Created promotion_expiry: {created_data['promotion_expiry']}")
                            print(f"   - Retrieved promotion_expiry: {retrieved_data['promotion_expiry']}")
                            
                            return True
                        else:
                            print(f"❌ Failed to retrieve listing for persistence test: {get_response.status}")
                            return False
                else:
                    print(f"❌ Failed to create listing for persistence test: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing MongoDB persistence: {str(e)}")
            return False
            
    async def setup_test_users(self) -> bool:
        """Setup all test users"""
        print("🔧 Setting up test users...")
        
        users = [
            (self.vip_user, "vip"),
            (self.premium_user, "premium"), 
            (self.free_user, "free"),
            (self.no_tier_user, "no_tier")
        ]
        
        for user_data, user_key in users:
            if not await self.register_and_login_user(user_data, user_key):
                print(f"❌ Failed to setup {user_key} user")
                return False
                
        print("✅ All test users setup successfully")
        return True
        
    async def run_all_tests(self):
        """Run all VIP auto-promotion tests"""
        print("🚀 Starting VIP Auto-Promotion Backend Tests")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Setup test users
            if not await self.setup_test_users():
                print("❌ Failed to setup test users")
                return False
            
            # Run tests in logical order
            tests = [
                ("VIP User Auto-Promotion", self.test_vip_user_auto_promotion),
                ("Non-VIP Users (No Promotion)", self.test_non_vip_user_no_promotion),
                ("No Subscription Tier User", self.test_no_subscription_tier_user),
                ("VIP Listing Retrieval", self.test_vip_listing_retrieval),
                ("Specific Listing Retrieval", self.test_specific_listing_retrieval),
                ("Edge Cases", self.test_edge_cases),
                ("MongoDB Field Persistence", self.test_mongodb_field_persistence)
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
            print("📊 VIP AUTO-PROMOTION TEST RESULTS SUMMARY")
            print("=" * 70)
            
            passed = 0
            total = len(results)
            
            for test_name, result in results:
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status} - {test_name}")
                if result:
                    passed += 1
            
            print(f"\nOverall: {passed}/{total} tests passed")
            print(f"Created {len(self.created_listings)} test listings")
            
            if passed == total:
                print("🎉 All VIP auto-promotion tests PASSED!")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = VIPAutoPromotionTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)