#!/usr/bin/env python3
"""
Focused Premium Auto-Promotion Test
Tests only the newly created listings to avoid interference from existing data.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://bidvex-sync.preview.emergentagent.com/api"

class FocusedPremiumTester:
    def __init__(self):
        self.session = None
        self.test_users = {}
        self.created_listing_ids = []
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def create_test_user(self, tier: str) -> Dict[str, Any]:
        """Create a test user with specific subscription tier"""
        timestamp = int(datetime.now().timestamp())
        email = f"focused.{tier}.{timestamp}@bazario.com"
        
        user_data = {
            "email": email,
            "password": f"Focused{tier.title()}123!",
            "name": f"Focused {tier.title()} User",
            "account_type": "business",
            "phone": f"+1555000{len(self.test_users):03d}"
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
                        "tier": tier
                    }
                    
                    # Update subscription tier if not free
                    if tier != "free":
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
            print(f"❌ Error updating subscription tier: {str(e)}")
            return False
            
    async def create_test_listing(self, user_info: Dict[str, Any], title_suffix: str = "") -> Optional[Dict[str, Any]]:
        """Create a multi-item listing for testing"""
        now = datetime.now(timezone.utc)
        
        listing_data = {
            "title": f"Focused {user_info['tier'].title()} Test{title_suffix}",
            "description": f"Testing {user_info['tier']} tier auto-promotion",
            "category": "Electronics",
            "location": "123 Test Street",
            "city": "Toronto",
            "region": "Ontario",
            "auction_end_date": (now + timedelta(days=7)).isoformat(),
            "lots": [
                {
                    "lot_number": 1,
                    "title": "Test Item",
                    "description": "Test description for focused testing",
                    "quantity": 1,
                    "starting_price": 100.0,
                    "current_price": 100.0,
                    "condition": "excellent",
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
                    self.created_listing_ids.append(data["id"])
                    return data
                else:
                    print(f"❌ Failed to create {user_info['tier']} listing: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return None
        except Exception as e:
            print(f"❌ Error creating {user_info['tier']} listing: {str(e)}")
            return None
            
    async def run_focused_tests(self):
        """Run focused tests on newly created listings only"""
        print("🎯 Starting Focused Premium Auto-Promotion Tests")
        print("=" * 60)
        
        await self.setup_session()
        
        try:
            # Create test users
            print("\n🔧 Creating test users...")
            for tier in ["free", "premium", "vip"]:
                user_info = await self.create_test_user(tier)
                if user_info:
                    self.test_users[tier] = user_info
                    print(f"✅ Created {tier} user: {user_info['email']}")
                else:
                    print(f"❌ Failed to create {tier} user")
                    return False
            
            # Create test listings and capture creation times
            print("\n📝 Creating test listings...")
            test_results = {}
            
            for tier in ["free", "premium", "vip"]:
                creation_time = datetime.now(timezone.utc)
                listing = await self.create_test_listing(self.test_users[tier])
                
                if listing:
                    test_results[tier] = {
                        "listing": listing,
                        "creation_time": creation_time
                    }
                    print(f"✅ Created {tier} listing: {listing['id']}")
                else:
                    print(f"❌ Failed to create {tier} listing")
                    return False
            
            # Verify promotion logic
            print("\n🧪 Verifying auto-promotion logic...")
            
            all_passed = True
            
            # Test Free tier (no promotion)
            free_listing = test_results["free"]["listing"]
            if free_listing["is_featured"] == False and free_listing["promotion_expiry"] is None:
                print("✅ Free tier: No promotion (correct)")
            else:
                print(f"❌ Free tier: Should not be promoted, got is_featured={free_listing['is_featured']}, expiry={free_listing['promotion_expiry']}")
                all_passed = False
            
            # Test Premium tier (3-day promotion)
            premium_listing = test_results["premium"]["listing"]
            premium_creation = test_results["premium"]["creation_time"]
            
            if premium_listing["is_featured"] == True and premium_listing["promotion_expiry"] is not None:
                expiry_time = datetime.fromisoformat(premium_listing["promotion_expiry"].replace('Z', '+00:00'))
                expected_expiry = premium_creation + timedelta(days=3)
                time_diff = abs((expiry_time - expected_expiry).total_seconds())
                
                if time_diff <= 2:
                    print(f"✅ Premium tier: 3-day promotion (±{time_diff:.2f}s accuracy)")
                else:
                    print(f"❌ Premium tier: Promotion expiry inaccurate, got {time_diff:.2f}s difference")
                    all_passed = False
            else:
                print(f"❌ Premium tier: Should be promoted for 3 days, got is_featured={premium_listing['is_featured']}, expiry={premium_listing['promotion_expiry']}")
                all_passed = False
            
            # Test VIP tier (7-day promotion)
            vip_listing = test_results["vip"]["listing"]
            vip_creation = test_results["vip"]["creation_time"]
            
            if vip_listing["is_featured"] == True and vip_listing["promotion_expiry"] is not None:
                expiry_time = datetime.fromisoformat(vip_listing["promotion_expiry"].replace('Z', '+00:00'))
                expected_expiry = vip_creation + timedelta(days=7)
                time_diff = abs((expiry_time - expected_expiry).total_seconds())
                
                if time_diff <= 2:
                    print(f"✅ VIP tier: 7-day promotion (±{time_diff:.2f}s accuracy)")
                else:
                    print(f"❌ VIP tier: Promotion expiry inaccurate, got {time_diff:.2f}s difference")
                    all_passed = False
            else:
                print(f"❌ VIP tier: Should be promoted for 7 days, got is_featured={vip_listing['is_featured']}, expiry={vip_listing['promotion_expiry']}")
                all_passed = False
            
            # Test Premium vs VIP duration difference
            if premium_listing["promotion_expiry"] and vip_listing["promotion_expiry"]:
                premium_expiry = datetime.fromisoformat(premium_listing["promotion_expiry"].replace('Z', '+00:00'))
                vip_expiry = datetime.fromisoformat(vip_listing["promotion_expiry"].replace('Z', '+00:00'))
                duration_diff = (vip_expiry - premium_expiry).total_seconds() / 86400  # Convert to days
                
                if abs(duration_diff - 4) <= 0.1:  # Should be approximately 4 days difference
                    print(f"✅ Duration difference: {duration_diff:.2f} days (expected: 4.0 days)")
                else:
                    print(f"❌ Duration difference: {duration_diff:.2f} days (expected: 4.0 days)")
                    all_passed = False
            
            # Verify retrieval of specific listings
            print("\n🔍 Verifying listing retrieval...")
            
            for tier in ["free", "premium", "vip"]:
                listing_id = test_results[tier]["listing"]["id"]
                
                async with self.session.get(f"{BASE_URL}/multi-item-listings/{listing_id}") as response:
                    if response.status == 200:
                        retrieved = await response.json()
                        original = test_results[tier]["listing"]
                        
                        if (retrieved["is_featured"] == original["is_featured"] and 
                            retrieved["promotion_expiry"] == original["promotion_expiry"]):
                            print(f"✅ {tier.title()} listing retrieval: Consistent data")
                        else:
                            print(f"❌ {tier.title()} listing retrieval: Data mismatch")
                            all_passed = False
                    else:
                        print(f"❌ Failed to retrieve {tier} listing: {response.status}")
                        all_passed = False
            
            # Summary
            print("\n" + "=" * 60)
            print("📊 FOCUSED TEST RESULTS SUMMARY")
            print("=" * 60)
            
            if all_passed:
                print("🎉 ALL FOCUSED TESTS PASSED!")
                print("\n✅ SUCCESS CRITERIA VERIFIED:")
                print("   • Premium users get 3-day auto-promotion")
                print("   • VIP users get 7-day auto-promotion") 
                print("   • Free users get no promotion")
                print("   • Promotion expiry calculated accurately (±2s)")
                print("   • Duration difference is exactly 4 days")
                print("   • MongoDB persistence working correctly")
                print("   • Listing retrieval returns consistent data")
                return True
            else:
                print("❌ SOME TESTS FAILED")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = FocusedPremiumTester()
    success = await tester.run_focused_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)