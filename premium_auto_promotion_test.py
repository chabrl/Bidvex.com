#!/usr/bin/env python3
"""
Premium Auto-Promotion Testing Suite
Tests the Premium (3-day) and VIP (7-day) auto-promotion logic for multi-item listings.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import uuid

# Configuration
BASE_URL = "https://vscodeshare-1.preview.emergentagent.com/api"

class PremiumAutoPromotionTester:
    def __init__(self):
        self.session = None
        self.test_users = {}  # Store user tokens and IDs by tier
        self.test_listings = []  # Store created listings for cleanup
        self.test_results = {}
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def create_test_user(self, tier: str, account_type: str = "business") -> Dict[str, Any]:
        """Create a test user with specific subscription tier"""
        timestamp = int(datetime.now().timestamp())
        email = f"{tier}.user.{timestamp}@bazario.com"
        
        user_data = {
            "email": email,
            "password": f"{tier.title()}Test123!",
            "name": f"{tier.title()} Test User",
            "account_type": account_type,
            "phone": f"+123456789{len(self.test_users)}"
        }
        
        try:
            # Register user
            async with self.session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
                if response.status == 200:
                    data = await response.json()
                    user_info = {
                        "token": data["access_token"],
                        "user_id": data["user"]["id"],
                        "email": email,
                        "tier": tier,
                        "account_type": account_type
                    }
                    
                    # Update subscription tier if not free
                    if tier != "free":
                        await self.update_user_subscription_tier(user_info["token"], tier)
                    
                    print(f"✅ Created {tier} user: {email}")
                    return user_info
                else:
                    print(f"❌ Failed to create {tier} user: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return None
        except Exception as e:
            print(f"❌ Error creating {tier} user: {str(e)}")
            return None
            
    async def update_user_subscription_tier(self, token: str, tier: str) -> bool:
        """Update user's subscription tier"""
        try:
            async with self.session.put(
                f"{BASE_URL}/users/me",
                json={"subscription_tier": tier},
                headers={"Authorization": f"Bearer {token}"}
            ) as response:
                if response.status == 200:
                    print(f"   - Updated subscription tier to: {tier}")
                    return True
                else:
                    print(f"❌ Failed to update subscription tier: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error updating subscription tier: {str(e)}")
            return False
            
    async def setup_test_users(self) -> bool:
        """Setup all test users (Free, Premium, VIP)"""
        print("\n🔧 Setting up test users...")
        
        tiers = ["free", "premium", "vip"]
        
        for tier in tiers:
            # Create business account user
            user_info = await self.create_test_user(tier, "business")
            if user_info:
                self.test_users[tier] = user_info
            else:
                print(f"❌ Failed to create {tier} user")
                return False
                
        # Create personal account VIP user for edge case testing
        personal_vip = await self.create_test_user("vip_personal", "personal")
        if personal_vip:
            personal_vip["tier"] = "vip"  # Set tier to vip for subscription update
            await self.update_user_subscription_tier(personal_vip["token"], "vip")
            self.test_users["vip_personal"] = personal_vip
        
        print(f"✅ Created {len(self.test_users)} test users")
        return True
        
    def get_auth_headers(self, tier: str) -> Dict[str, str]:
        """Get authorization headers for specific user tier"""
        return {"Authorization": f"Bearer {self.test_users[tier]['token']}"}
        
    async def create_test_listing(self, tier: str, title_suffix: str = "", future_start: bool = False) -> Optional[Dict[str, Any]]:
        """Create a multi-item listing for testing"""
        now = datetime.now(timezone.utc)
        
        # Set auction dates
        auction_start_date = None
        if future_start:
            auction_start_date = (now + timedelta(hours=1)).isoformat()
            
        auction_end_date = (now + timedelta(days=7)).isoformat()
        
        listing_data = {
            "title": f"{tier.title()} Auto-Promotion Test{title_suffix}",
            "description": f"Testing {tier} tier auto-promotion functionality with 3 sample lots",
            "category": "Electronics",
            "location": "123 Test Street",
            "city": "Toronto",
            "region": "Ontario",
            "auction_end_date": auction_end_date,
            "auction_start_date": auction_start_date,
            "lots": [
                {
                    "lot_number": 1,
                    "title": "Vintage Camera",
                    "description": "Classic film camera in excellent condition",
                    "quantity": 1,
                    "starting_price": 150.0,
                    "current_price": 150.0,
                    "condition": "excellent",
                    "images": ["https://example.com/camera1.jpg"]
                },
                {
                    "lot_number": 2,
                    "title": "Antique Watch",
                    "description": "Rare pocket watch from the 1920s",
                    "quantity": 1,
                    "starting_price": 300.0,
                    "current_price": 300.0,
                    "condition": "good",
                    "images": ["https://example.com/watch1.jpg"]
                },
                {
                    "lot_number": 3,
                    "title": "Collectible Coins",
                    "description": "Set of rare Canadian coins",
                    "quantity": 5,
                    "starting_price": 75.0,
                    "current_price": 75.0,
                    "condition": "mint",
                    "images": ["https://example.com/coins1.jpg"]
                }
            ]
        }
        
        try:
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_auth_headers(tier)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_listings.append(data["id"])
                    return data
                else:
                    print(f"❌ Failed to create {tier} listing: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return None
        except Exception as e:
            print(f"❌ Error creating {tier} listing: {str(e)}")
            return None
            
    async def test_premium_user_auto_promotion(self) -> bool:
        """Test 1: Premium User Creates Listing (3-Day Auto-Promotion)"""
        print("\n🧪 Test 1: Premium User Creates Listing (3-Day Auto-Promotion)...")
        
        try:
            creation_time = datetime.now(timezone.utc)
            listing = await self.create_test_listing("premium", " - 3 Day Test")
            
            if not listing:
                return False
                
            # Verify promotion fields
            assert listing["is_featured"] == True, "Premium listing should be featured"
            assert listing["promotion_expiry"] is not None, "Premium listing should have promotion_expiry"
            
            # Parse and verify promotion expiry (should be 3 days from creation)
            expiry_time = datetime.fromisoformat(listing["promotion_expiry"].replace('Z', '+00:00'))
            expected_expiry = creation_time + timedelta(days=3)
            time_diff = abs((expiry_time - expected_expiry).total_seconds())
            
            assert time_diff <= 2, f"Promotion expiry should be 3 days from creation (±2s), got {time_diff}s difference"
            
            print(f"✅ Premium listing auto-promoted successfully")
            print(f"   - Listing ID: {listing['id']}")
            print(f"   - Is Featured: {listing['is_featured']}")
            print(f"   - Promotion Expiry: {listing['promotion_expiry']}")
            print(f"   - Time Accuracy: ±{time_diff:.2f}s")
            
            # Verify MongoDB persistence by retrieving the listing
            async with self.session.get(
                f"{BASE_URL}/multi-item-listings/{listing['id']}"
            ) as response:
                if response.status == 200:
                    retrieved_listing = await response.json()
                    assert retrieved_listing["is_featured"] == True
                    assert retrieved_listing["promotion_expiry"] == listing["promotion_expiry"]
                    print(f"✅ MongoDB persistence verified")
                else:
                    print(f"❌ Failed to retrieve listing for verification: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error in premium user auto-promotion test: {str(e)}")
            return False
            
    async def test_free_user_no_promotion(self) -> bool:
        """Test 2: Free User Creates Listing (No Promotion)"""
        print("\n🧪 Test 2: Free User Creates Listing (No Promotion)...")
        
        try:
            listing = await self.create_test_listing("free", " - No Promotion Test")
            
            if not listing:
                return False
                
            # Verify no promotion
            assert listing["is_featured"] == False, "Free listing should not be featured"
            assert listing["promotion_expiry"] is None, "Free listing should not have promotion_expiry"
            
            print(f"✅ Free listing correctly not promoted")
            print(f"   - Listing ID: {listing['id']}")
            print(f"   - Is Featured: {listing['is_featured']}")
            print(f"   - Promotion Expiry: {listing['promotion_expiry']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in free user no promotion test: {str(e)}")
            return False
            
    async def test_vip_user_regression(self) -> bool:
        """Test 3: VIP User Creates Listing (7-Day Auto-Promotion - Regression Test)"""
        print("\n🧪 Test 3: VIP User Creates Listing (7-Day Auto-Promotion - Regression Test)...")
        
        try:
            creation_time = datetime.now(timezone.utc)
            listing = await self.create_test_listing("vip", " - 7 Day Regression Test")
            
            if not listing:
                return False
                
            # Verify promotion fields
            assert listing["is_featured"] == True, "VIP listing should be featured"
            assert listing["promotion_expiry"] is not None, "VIP listing should have promotion_expiry"
            
            # Parse and verify promotion expiry (should be 7 days from creation)
            expiry_time = datetime.fromisoformat(listing["promotion_expiry"].replace('Z', '+00:00'))
            expected_expiry = creation_time + timedelta(days=7)
            time_diff = abs((expiry_time - expected_expiry).total_seconds())
            
            assert time_diff <= 2, f"Promotion expiry should be 7 days from creation (±2s), got {time_diff}s difference"
            
            print(f"✅ VIP listing auto-promoted successfully (regression test passed)")
            print(f"   - Listing ID: {listing['id']}")
            print(f"   - Is Featured: {listing['is_featured']}")
            print(f"   - Promotion Expiry: {listing['promotion_expiry']}")
            print(f"   - Time Accuracy: ±{time_diff:.2f}s")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in VIP user regression test: {str(e)}")
            return False
            
    async def test_premium_vs_vip_comparison(self) -> bool:
        """Test 4: Premium vs VIP Comparison"""
        print("\n🧪 Test 4: Premium vs VIP Comparison...")
        
        try:
            # Create both listings at nearly the same time
            creation_time = datetime.now(timezone.utc)
            
            premium_listing = await self.create_test_listing("premium", " - Comparison Test")
            await asyncio.sleep(0.1)  # Small delay to ensure different timestamps
            vip_listing = await self.create_test_listing("vip", " - Comparison Test")
            
            if not premium_listing or not vip_listing:
                return False
                
            # Parse expiry times
            premium_expiry = datetime.fromisoformat(premium_listing["promotion_expiry"].replace('Z', '+00:00'))
            vip_expiry = datetime.fromisoformat(vip_listing["promotion_expiry"].replace('Z', '+00:00'))
            
            # Calculate difference (should be approximately 4 days: 7 - 3 = 4)
            expiry_diff = (vip_expiry - premium_expiry).total_seconds()
            expected_diff = 4 * 24 * 60 * 60  # 4 days in seconds
            diff_tolerance = 5  # ±5 seconds tolerance
            
            assert abs(expiry_diff - expected_diff) <= diff_tolerance, f"VIP expiry should be 4 days later than Premium, got {expiry_diff/86400:.2f} days difference"
            
            # Verify both are featured
            assert premium_listing["is_featured"] == True, "Premium listing should be featured"
            assert vip_listing["is_featured"] == True, "VIP listing should be featured"
            
            print(f"✅ Premium vs VIP comparison successful")
            print(f"   - Premium Expiry: {premium_listing['promotion_expiry']}")
            print(f"   - VIP Expiry: {vip_listing['promotion_expiry']}")
            print(f"   - Difference: {expiry_diff/86400:.2f} days (expected: 4.0 days)")
            print(f"   - Both Featured: Premium={premium_listing['is_featured']}, VIP={vip_listing['is_featured']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in premium vs VIP comparison test: {str(e)}")
            return False
            
    async def test_listing_retrieval_mixed_tiers(self) -> bool:
        """Test 5: Listing Retrieval with Mixed Tiers"""
        print("\n🧪 Test 5: Listing Retrieval with Mixed Tiers...")
        
        try:
            # Get all listings
            async with self.session.get(f"{BASE_URL}/multi-item-listings") as response:
                if response.status == 200:
                    listings = await response.json()
                    
                    # Find our test listings
                    test_listings = [l for l in listings if "Auto-Promotion Test" in l["title"]]
                    
                    if len(test_listings) < 3:
                        print(f"⚠️  Expected at least 3 test listings, found {len(test_listings)}")
                        return False
                    
                    # Categorize by tier based on title
                    premium_listings = [l for l in test_listings if "Premium" in l["title"]]
                    vip_listings = [l for l in test_listings if "VIP" in l["title"] or "Vip" in l["title"]]
                    free_listings = [l for l in test_listings if "Free" in l["title"]]
                    
                    print(f"✅ Retrieved listings from all tiers")
                    print(f"   - Total test listings: {len(test_listings)}")
                    print(f"   - Premium listings: {len(premium_listings)}")
                    print(f"   - VIP listings: {len(vip_listings)}")
                    print(f"   - Free listings: {len(free_listings)}")
                    
                    # Verify Premium listings
                    for listing in premium_listings:
                        assert listing["is_featured"] == True, f"Premium listing {listing['id']} should be featured"
                        assert listing["promotion_expiry"] is not None, f"Premium listing {listing['id']} should have promotion_expiry"
                        
                        # Verify it's approximately 3 days
                        expiry = datetime.fromisoformat(listing["promotion_expiry"].replace('Z', '+00:00'))
                        created = datetime.fromisoformat(listing["created_at"].replace('Z', '+00:00'))
                        duration = (expiry - created).total_seconds() / 86400  # Convert to days
                        assert abs(duration - 3) < 0.1, f"Premium promotion should be ~3 days, got {duration:.2f}"
                    
                    # Verify VIP listings
                    for listing in vip_listings:
                        assert listing["is_featured"] == True, f"VIP listing {listing['id']} should be featured"
                        assert listing["promotion_expiry"] is not None, f"VIP listing {listing['id']} should have promotion_expiry"
                        
                        # Verify it's approximately 7 days
                        expiry = datetime.fromisoformat(listing["promotion_expiry"].replace('Z', '+00:00'))
                        created = datetime.fromisoformat(listing["created_at"].replace('Z', '+00:00'))
                        duration = (expiry - created).total_seconds() / 86400  # Convert to days
                        assert abs(duration - 7) < 0.1, f"VIP promotion should be ~7 days, got {duration:.2f}"
                    
                    # Verify Free listings
                    for listing in free_listings:
                        assert listing["is_featured"] == False, f"Free listing {listing['id']} should not be featured"
                        assert listing["promotion_expiry"] is None, f"Free listing {listing['id']} should not have promotion_expiry"
                    
                    print(f"✅ All tier-specific promotion rules verified in retrieval")
                    
                    return True
                else:
                    print(f"❌ Failed to retrieve listings: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error in listing retrieval test: {str(e)}")
            return False
            
    async def test_premium_future_start_date(self) -> bool:
        """Test 6: Premium Listing with Future Start Date"""
        print("\n🧪 Test 6: Premium Listing with Future Start Date...")
        
        try:
            creation_time = datetime.now(timezone.utc)
            listing = await self.create_test_listing("premium", " - Future Start Test", future_start=True)
            
            if not listing:
                return False
                
            # Verify listing status is 'upcoming'
            assert listing["status"] == "upcoming", f"Future start listing should have status 'upcoming', got '{listing['status']}'"
            
            # Verify promotion still applies
            assert listing["is_featured"] == True, "Premium listing with future start should still be featured"
            assert listing["promotion_expiry"] is not None, "Premium listing with future start should have promotion_expiry"
            
            # Verify promotion expiry is calculated from creation time, not start time
            expiry_time = datetime.fromisoformat(listing["promotion_expiry"].replace('Z', '+00:00'))
            expected_expiry = creation_time + timedelta(days=3)
            time_diff = abs((expiry_time - expected_expiry).total_seconds())
            
            assert time_diff <= 2, f"Promotion expiry should be 3 days from creation (±2s), got {time_diff}s difference"
            
            print(f"✅ Premium listing with future start date promoted correctly")
            print(f"   - Listing ID: {listing['id']}")
            print(f"   - Status: {listing['status']}")
            print(f"   - Is Featured: {listing['is_featured']}")
            print(f"   - Promotion Expiry: {listing['promotion_expiry']}")
            print(f"   - Auction Start: {listing['auction_start_date']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in premium future start date test: {str(e)}")
            return False
            
    async def test_no_subscription_tier_edge_case(self) -> bool:
        """Test 7: Edge Case - User with No Subscription Tier Field"""
        print("\n🧪 Test 7: Edge Case - User with No Subscription Tier Field...")
        
        try:
            # Create a user without setting subscription_tier (should default to free behavior)
            user_info = await self.create_test_user("no_tier", "business")
            if not user_info:
                return False
                
            # Don't update subscription tier - leave it as default
            self.test_users["no_tier"] = user_info
            
            listing = await self.create_test_listing("no_tier", " - No Tier Test")
            
            if not listing:
                return False
                
            # Should behave like free tier (no promotion)
            assert listing["is_featured"] == False, "User without subscription_tier should not get promotion"
            assert listing["promotion_expiry"] is None, "User without subscription_tier should not have promotion_expiry"
            
            print(f"✅ User without subscription_tier defaults to free behavior")
            print(f"   - Listing ID: {listing['id']}")
            print(f"   - Is Featured: {listing['is_featured']}")
            print(f"   - Promotion Expiry: {listing['promotion_expiry']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in no subscription tier test: {str(e)}")
            return False
            
    async def test_personal_account_vip_blocked(self) -> bool:
        """Test 8: Personal Account VIP User Blocked from Multi-Item Listings"""
        print("\n🧪 Test 8: Personal Account VIP User Blocked from Multi-Item Listings...")
        
        try:
            # Try to create listing with personal account VIP user
            listing_data = {
                "title": "Personal VIP Test - Should Fail",
                "description": "This should fail because personal accounts can't create multi-item listings",
                "category": "Electronics",
                "location": "123 Test Street",
                "city": "Toronto",
                "region": "Ontario",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "lots": [
                    {
                        "lot_number": 1,
                        "title": "Test Item",
                        "description": "Test description",
                        "quantity": 1,
                        "starting_price": 100.0,
                        "current_price": 100.0,
                        "condition": "good",
                        "images": []
                    }
                ]
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_auth_headers("vip_personal")
            ) as response:
                if response.status == 403:
                    data = await response.json()
                    assert "Only business accounts can create multi-item listings" in data["detail"]
                    print(f"✅ Personal account VIP user correctly blocked from creating multi-item listings")
                    print(f"   - Status: {response.status}")
                    print(f"   - Message: {data['detail']}")
                    return True
                else:
                    print(f"❌ Should have blocked personal account, got status: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error in personal account VIP test: {str(e)}")
            return False
            
    async def run_all_tests(self):
        """Run all premium auto-promotion tests"""
        print("🚀 Starting Premium Auto-Promotion Testing Suite")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Setup test users
            if not await self.setup_test_users():
                print("❌ Failed to setup test users")
                return False
            
            # Run tests in specific order
            tests = [
                ("Premium User Auto-Promotion (3 Days)", self.test_premium_user_auto_promotion),
                ("Free User No Promotion", self.test_free_user_no_promotion),
                ("VIP User Regression (7 Days)", self.test_vip_user_regression),
                ("Premium vs VIP Comparison", self.test_premium_vs_vip_comparison),
                ("Listing Retrieval Mixed Tiers", self.test_listing_retrieval_mixed_tiers),
                ("Premium Future Start Date", self.test_premium_future_start_date),
                ("No Subscription Tier Edge Case", self.test_no_subscription_tier_edge_case),
                ("Personal Account VIP Blocked", self.test_personal_account_vip_blocked)
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
            print("📊 PREMIUM AUTO-PROMOTION TEST RESULTS SUMMARY")
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
                print("🎉 All Premium Auto-Promotion tests PASSED!")
                print("\n🔍 SUCCESS CRITERIA VERIFIED:")
                print("✅ Premium users' listings automatically featured for 3 days")
                print("✅ VIP users' listings still featured for 7 days (regression)")
                print("✅ Free users' listings not featured by default")
                print("✅ promotion_expiry correctly calculated (3 days for Premium, 7 days for VIP)")
                print("✅ No backend errors or crashes")
                print("✅ MongoDB fields properly serialized/deserialized")
                print("✅ GET endpoints return correct featured status for all tiers")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = PremiumAutoPromotionTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)