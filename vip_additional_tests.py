#!/usr/bin/env python3
"""
Additional VIP Auto-Promotion Edge Case Tests
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta

BASE_URL = "https://launchapp-4.preview.emergentagent.com/api"

async def test_personal_account_vip():
    """Test that personal account VIP users cannot create multi-item listings"""
    print("🧪 Testing Personal Account VIP User (Should be blocked)...")
    
    async with aiohttp.ClientSession() as session:
        # Create VIP user with personal account
        test_email = f"personal.vip.{int(datetime.now().timestamp())}@bazario.com"
        user_data = {
            "email": test_email,
            "password": "PersonalVIP123!",
            "name": "Personal VIP User",
            "account_type": "personal",  # Personal account
            "phone": "+1234567890"
        }
        
        async with session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
            if response.status == 200:
                data = await response.json()
                token = data["access_token"]
                
                # Update to VIP
                headers = {"Authorization": f"Bearer {token}"}
                async with session.put(f"{BASE_URL}/users/me", json={"subscription_tier": "vip"}, headers=headers) as update_response:
                    if update_response.status == 200:
                        print("   - VIP personal user created successfully")
                        
                        # Try to create multi-item listing (should fail)
                        listing_data = {
                            "title": "Personal VIP Test Listing",
                            "description": "Should not be allowed",
                            "category": "Test",
                            "location": "Test Location",
                            "city": "Test City",
                            "region": "Test Region",
                            "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                            "lots": [{
                                "lot_number": 1,
                                "title": "Test Item",
                                "description": "Test description",
                                "quantity": 1,
                                "starting_price": 50.0,
                                "current_price": 50.0,
                                "condition": "good",
                                "images": []
                            }]
                        }
                        
                        async with session.post(f"{BASE_URL}/multi-item-listings", json=listing_data, headers=headers) as listing_response:
                            if listing_response.status == 403:
                                print("✅ Correctly blocked personal account from creating multi-item listing")
                                return True
                            else:
                                print(f"❌ Should have blocked personal account, got: {listing_response.status}")
                                return False
                    else:
                        print("❌ Failed to update to VIP")
                        return False
            else:
                print("❌ Failed to create personal VIP user")
                return False

async def test_vip_promotion_expiry_precision():
    """Test that VIP promotion expiry is calculated precisely"""
    print("🧪 Testing VIP Promotion Expiry Precision...")
    
    async with aiohttp.ClientSession() as session:
        # Create VIP business user
        test_email = f"precision.vip.{int(datetime.now().timestamp())}@bazario.com"
        user_data = {
            "email": test_email,
            "password": "PrecisionVIP123!",
            "name": "Precision VIP User",
            "account_type": "business",
            "phone": "+1234567890"
        }
        
        async with session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
            if response.status == 200:
                data = await response.json()
                token = data["access_token"]
                
                # Update to VIP
                headers = {"Authorization": f"Bearer {token}"}
                async with session.put(f"{BASE_URL}/users/me", json={"subscription_tier": "vip"}, headers=headers) as update_response:
                    if update_response.status == 200:
                        # Record time before creating listing
                        before_creation = datetime.now(timezone.utc)
                        
                        listing_data = {
                            "title": "Precision Test Listing",
                            "description": "Testing promotion expiry precision",
                            "category": "Test",
                            "location": "Test Location",
                            "city": "Test City", 
                            "region": "Test Region",
                            "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                            "lots": [{
                                "lot_number": 1,
                                "title": "Test Item",
                                "description": "Test description",
                                "quantity": 1,
                                "starting_price": 50.0,
                                "current_price": 50.0,
                                "condition": "good",
                                "images": []
                            }]
                        }
                        
                        async with session.post(f"{BASE_URL}/multi-item-listings", json=listing_data, headers=headers) as listing_response:
                            if listing_response.status == 200:
                                after_creation = datetime.now(timezone.utc)
                                listing_data = await listing_response.json()
                                
                                # Parse promotion expiry
                                promotion_expiry = datetime.fromisoformat(listing_data["promotion_expiry"].replace('Z', '+00:00'))
                                
                                # Calculate expected range (7 days from creation time)
                                expected_min = before_creation + timedelta(days=7)
                                expected_max = after_creation + timedelta(days=7)
                                
                                # Verify expiry is within expected range
                                if expected_min <= promotion_expiry <= expected_max:
                                    time_diff = (promotion_expiry - (before_creation + timedelta(days=7))).total_seconds()
                                    print(f"✅ VIP promotion expiry calculated precisely")
                                    print(f"   - Expected: ~{expected_min.strftime('%Y-%m-%d %H:%M:%S')}")
                                    print(f"   - Actual: {promotion_expiry.strftime('%Y-%m-%d %H:%M:%S')}")
                                    print(f"   - Difference: {time_diff:.2f} seconds")
                                    return True
                                else:
                                    print(f"❌ Promotion expiry outside expected range")
                                    print(f"   - Expected range: {expected_min} to {expected_max}")
                                    print(f"   - Actual: {promotion_expiry}")
                                    return False
                            else:
                                print(f"❌ Failed to create listing: {listing_response.status}")
                                return False
                    else:
                        print("❌ Failed to update to VIP")
                        return False
            else:
                print("❌ Failed to create precision VIP user")
                return False

async def test_multiple_vip_listings():
    """Test that multiple VIP listings all get promoted correctly"""
    print("🧪 Testing Multiple VIP Listings...")
    
    async with aiohttp.ClientSession() as session:
        # Create VIP business user
        test_email = f"multi.vip.{int(datetime.now().timestamp())}@bazario.com"
        user_data = {
            "email": test_email,
            "password": "MultiVIP123!",
            "name": "Multi VIP User",
            "account_type": "business",
            "phone": "+1234567890"
        }
        
        async with session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
            if response.status == 200:
                data = await response.json()
                token = data["access_token"]
                
                # Update to VIP
                headers = {"Authorization": f"Bearer {token}"}
                async with session.put(f"{BASE_URL}/users/me", json={"subscription_tier": "vip"}, headers=headers) as update_response:
                    if update_response.status == 200:
                        # Create 3 listings
                        created_listings = []
                        
                        for i in range(3):
                            listing_data = {
                                "title": f"Multi VIP Test Listing {i+1}",
                                "description": f"Testing multiple VIP listings - #{i+1}",
                                "category": "Test",
                                "location": "Test Location",
                                "city": "Test City",
                                "region": "Test Region", 
                                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                                "lots": [{
                                    "lot_number": 1,
                                    "title": f"Test Item {i+1}",
                                    "description": f"Test description {i+1}",
                                    "quantity": 1,
                                    "starting_price": 50.0 + (i * 10),
                                    "current_price": 50.0 + (i * 10),
                                    "condition": "good",
                                    "images": []
                                }]
                            }
                            
                            async with session.post(f"{BASE_URL}/multi-item-listings", json=listing_data, headers=headers) as listing_response:
                                if listing_response.status == 200:
                                    listing_result = await listing_response.json()
                                    created_listings.append(listing_result)
                                else:
                                    print(f"❌ Failed to create listing {i+1}: {listing_response.status}")
                                    return False
                        
                        # Verify all listings are promoted
                        all_promoted = True
                        for i, listing in enumerate(created_listings):
                            if not listing["is_featured"] or not listing["promotion_expiry"]:
                                print(f"❌ Listing {i+1} not promoted correctly")
                                all_promoted = False
                            else:
                                print(f"   - Listing {i+1}: ✅ Featured until {listing['promotion_expiry'][:10]}")
                        
                        if all_promoted:
                            print(f"✅ All {len(created_listings)} VIP listings promoted correctly")
                            return True
                        else:
                            return False
                    else:
                        print("❌ Failed to update to VIP")
                        return False
            else:
                print("❌ Failed to create multi VIP user")
                return False

async def run_additional_tests():
    """Run all additional VIP tests"""
    print("🚀 Starting Additional VIP Auto-Promotion Tests")
    print("=" * 60)
    
    tests = [
        ("Personal Account VIP Block", test_personal_account_vip),
        ("VIP Promotion Expiry Precision", test_vip_promotion_expiry_precision),
        ("Multiple VIP Listings", test_multiple_vip_listings)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 ADDITIONAL VIP TESTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} additional tests passed")
    
    if passed == total:
        print("🎉 All additional VIP tests PASSED!")
        return True
    else:
        print("⚠️  Some additional tests FAILED")
        return False

if __name__ == "__main__":
    success = asyncio.run(run_additional_tests())
    exit(0 if success else 1)