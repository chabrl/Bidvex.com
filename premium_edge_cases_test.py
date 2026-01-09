#!/usr/bin/env python3
"""
Premium Auto-Promotion Edge Cases Test
Tests edge cases and additional scenarios for the Premium auto-promotion feature.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://launchapp-4.preview.emergentagent.com/api"

class EdgeCasesTester:
    def __init__(self):
        self.session = None
        self.test_users = {}
        
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
        email = f"edge.{tier}.{timestamp}@bazario.com"
        
        user_data = {
            "email": email,
            "password": f"Edge{tier.title()}123!",
            "name": f"Edge {tier.title()} User",
            "account_type": account_type,
            "phone": f"+1666000{len(self.test_users):03d}"
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
                    
                    # Update subscription tier if not free and not no_tier
                    if tier not in ["free", "no_tier"]:
                        await self.update_user_subscription_tier(user_info["token"], tier)
                    
                    return user_info
                else:
                    print(f"❌ Failed to create {tier} user: {response.status}")
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
                return response.status == 200
        except Exception as e:
            return False
            
    async def create_test_listing(self, user_info: Dict[str, Any], future_start: bool = False, title_suffix: str = "") -> Optional[Dict[str, Any]]:
        """Create a multi-item listing for testing"""
        now = datetime.now(timezone.utc)
        
        # Set auction dates
        auction_start_date = None
        if future_start:
            auction_start_date = (now + timedelta(hours=2)).isoformat()
            
        listing_data = {
            "title": f"Edge {user_info['tier'].title()} Test{title_suffix}",
            "description": f"Testing {user_info['tier']} tier edge cases",
            "category": "Electronics",
            "location": "123 Edge Street",
            "city": "Toronto",
            "region": "Ontario",
            "auction_end_date": (now + timedelta(days=7)).isoformat(),
            "auction_start_date": auction_start_date,
            "lots": [
                {
                    "lot_number": 1,
                    "title": "Edge Test Item",
                    "description": "Edge case testing item",
                    "quantity": 1,
                    "starting_price": 50.0,
                    "current_price": 50.0,
                    "condition": "good",
                    "images": []
                }
            ]
        }
        
        try:
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers={"Authorization": f"Bearer {user_info['token']}"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    print(f"❌ Failed to create {user_info['tier']} listing: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return None
        except Exception as e:
            print(f"❌ Error creating {user_info['tier']} listing: {str(e)}")
            return None
            
    async def test_future_start_date_premium(self) -> bool:
        """Test Premium listing with future start date"""
        print("\n🧪 Edge Case 1: Premium Listing with Future Start Date...")
        
        try:
            creation_time = datetime.now(timezone.utc)
            listing = await self.create_test_listing(self.test_users["premium"], future_start=True, title_suffix=" - Future Start")
            
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
            
            print(f"✅ Premium future start listing promoted correctly")
            print(f"   - Status: {listing['status']}")
            print(f"   - Is Featured: {listing['is_featured']}")
            print(f"   - Promotion Expiry: {listing['promotion_expiry']}")
            print(f"   - Auction Start: {listing['auction_start_date']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in future start date test: {str(e)}")
            return False
            
    async def test_no_subscription_tier(self) -> bool:
        """Test user without subscription_tier field"""
        print("\n🧪 Edge Case 2: User with No Subscription Tier Field...")
        
        try:
            listing = await self.create_test_listing(self.test_users["no_tier"], title_suffix=" - No Tier")
            
            if not listing:
                return False
            
            # Should behave like free tier (no promotion)
            assert listing["is_featured"] == False, "User without subscription_tier should not get promotion"
            assert listing["promotion_expiry"] is None, "User without subscription_tier should not have promotion_expiry"
            
            print(f"✅ User without subscription_tier defaults to free behavior")
            print(f"   - Is Featured: {listing['is_featured']}")
            print(f"   - Promotion Expiry: {listing['promotion_expiry']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in no subscription tier test: {str(e)}")
            return False
            
    async def test_personal_account_blocked(self) -> bool:
        """Test personal account users blocked from multi-item listings"""
        print("\n🧪 Edge Case 3: Personal Account Users Blocked...")
        
        try:
            # Try to create listing with personal account user
            listing_data = {
                "title": "Personal Account Test - Should Fail",
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
                headers={"Authorization": f"Bearer {self.test_users['personal']['token']}"}
            ) as response:
                if response.status == 403:
                    data = await response.json()
                    assert "Only business accounts can create multi-item listings" in data["detail"]
                    print(f"✅ Personal account correctly blocked from creating multi-item listings")
                    return True
                else:
                    print(f"❌ Should have blocked personal account, got status: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error in personal account test: {str(e)}")
            return False
            
    async def test_mongodb_field_persistence(self) -> bool:
        """Test MongoDB field persistence by direct retrieval"""
        print("\n🧪 Edge Case 4: MongoDB Field Persistence...")
        
        try:
            # Create a premium listing
            creation_time = datetime.now(timezone.utc)
            listing = await self.create_test_listing(self.test_users["premium"], title_suffix=" - Persistence Test")
            
            if not listing:
                return False
            
            # Retrieve the listing multiple times to verify persistence
            for i in range(3):
                async with self.session.get(f"{BASE_URL}/multi-item-listings/{listing['id']}") as response:
                    if response.status == 200:
                        retrieved = await response.json()
                        
                        # Verify fields are consistently stored and retrieved
                        assert retrieved["is_featured"] == listing["is_featured"], "is_featured field not persistent"
                        assert retrieved["promotion_expiry"] == listing["promotion_expiry"], "promotion_expiry field not persistent"
                        
                        # Verify promotion_expiry is properly formatted ISO string
                        if retrieved["promotion_expiry"]:
                            expiry_time = datetime.fromisoformat(retrieved["promotion_expiry"].replace('Z', '+00:00'))
                            assert isinstance(expiry_time, datetime), "promotion_expiry should be valid datetime"
                        
                    else:
                        print(f"❌ Failed to retrieve listing on attempt {i+1}: {response.status}")
                        return False
            
            print(f"✅ MongoDB field persistence verified")
            print(f"   - is_featured: {retrieved['is_featured']} (boolean)")
            print(f"   - promotion_expiry: {retrieved['promotion_expiry']} (ISO string)")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in MongoDB persistence test: {str(e)}")
            return False
            
    async def test_multiple_premium_listings(self) -> bool:
        """Test multiple Premium listings from same user"""
        print("\n🧪 Edge Case 5: Multiple Premium Listings from Same User...")
        
        try:
            listings = []
            creation_times = []
            
            # Create 3 premium listings
            for i in range(3):
                creation_time = datetime.now(timezone.utc)
                listing = await self.create_test_listing(
                    self.test_users["premium"], 
                    title_suffix=f" - Multiple Test {i+1}"
                )
                
                if listing:
                    listings.append(listing)
                    creation_times.append(creation_time)
                    await asyncio.sleep(0.1)  # Small delay between creations
                else:
                    print(f"❌ Failed to create listing {i+1}")
                    return False
            
            # Verify all listings are promoted correctly
            for i, (listing, creation_time) in enumerate(zip(listings, creation_times)):
                assert listing["is_featured"] == True, f"Listing {i+1} should be featured"
                assert listing["promotion_expiry"] is not None, f"Listing {i+1} should have promotion_expiry"
                
                # Verify promotion expiry
                expiry_time = datetime.fromisoformat(listing["promotion_expiry"].replace('Z', '+00:00'))
                expected_expiry = creation_time + timedelta(days=3)
                time_diff = abs((expiry_time - expected_expiry).total_seconds())
                
                assert time_diff <= 2, f"Listing {i+1} promotion expiry inaccurate: {time_diff}s difference"
            
            print(f"✅ Multiple Premium listings all promoted correctly")
            print(f"   - Created {len(listings)} listings")
            print(f"   - All featured: {all(l['is_featured'] for l in listings)}")
            print(f"   - All have expiry: {all(l['promotion_expiry'] for l in listings)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error in multiple listings test: {str(e)}")
            return False
            
    async def run_edge_case_tests(self):
        """Run all edge case tests"""
        print("🔬 Starting Premium Auto-Promotion Edge Cases Tests")
        print("=" * 65)
        
        await self.setup_session()
        
        try:
            # Create test users
            print("\n🔧 Creating edge case test users...")
            
            user_configs = [
                ("premium", "business"),
                ("no_tier", "business"),  # User without subscription_tier
                ("personal", "personal")   # Personal account user
            ]
            
            for tier, account_type in user_configs:
                user_info = await self.create_test_user(tier, account_type)
                if user_info:
                    self.test_users[tier] = user_info
                    print(f"✅ Created {tier} ({account_type}) user: {user_info['email']}")
                else:
                    print(f"❌ Failed to create {tier} user")
                    return False
            
            # Run edge case tests
            tests = [
                ("Future Start Date Premium", self.test_future_start_date_premium),
                ("No Subscription Tier", self.test_no_subscription_tier),
                ("Personal Account Blocked", self.test_personal_account_blocked),
                ("MongoDB Field Persistence", self.test_mongodb_field_persistence),
                ("Multiple Premium Listings", self.test_multiple_premium_listings)
            ]
            
            results = []
            for test_name, test_func in tests:
                try:
                    result = await test_func()
                    results.append((test_name, result))
                except Exception as e:
                    print(f"❌ {test_name} failed with exception: {str(e)}")
                    results.append((test_name, False))
            
            # Summary
            print("\n" + "=" * 65)
            print("📊 EDGE CASES TEST RESULTS SUMMARY")
            print("=" * 65)
            
            passed = 0
            total = len(results)
            
            for test_name, result in results:
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status} - {test_name}")
                if result:
                    passed += 1
            
            print(f"\nOverall: {passed}/{total} edge case tests passed")
            
            if passed == total:
                print("🎉 ALL EDGE CASE TESTS PASSED!")
                return True
            else:
                print("⚠️  Some edge case tests FAILED")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = EdgeCasesTester()
    success = await tester.run_edge_case_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)