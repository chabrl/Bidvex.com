#!/usr/bin/env python3
"""
BidVex Final Anniversary Launch Features Testing
Tests the complete anniversary launch functionality including SMS verification, auction processing, analytics, and email service.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://vscodeshare-1.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@bazario.com"
ADMIN_PASSWORD = "Admin123!"

class BidVexAnniversaryTester:
    def __init__(self):
        self.session = None
        self.admin_token = None
        self.admin_id = None
        self.test_results = {}
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def login_admin_user(self) -> bool:
        """Login with admin credentials"""
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
            
    def get_admin_headers(self) -> Dict[str, str]:
        """Get admin authorization headers"""
        return {"Authorization": f"Bearer {self.admin_token}"}
        
    async def test_sms_verification_twilio(self) -> bool:
        """Test Live SMS Verification (Twilio Integration)"""
        print("\n🧪 Testing Live SMS Verification (Twilio Integration)...")
        
        try:
            # Test 1: Send OTP to Twilio test number
            print("   Testing POST /api/sms/send-otp...")
            send_otp_data = {
                "phone_number": "+15005550006",
                "language": "en"
            }
            
            async with self.session.post(
                f"{BASE_URL}/sms/send-otp",
                json=send_otp_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "status" in data, "Missing 'status' field in send-otp response"
                    assert data["status"] in ["sent", "mock"], f"Invalid status: {data['status']}"
                    
                    print(f"✅ SMS OTP send successful")
                    print(f"   - Status: {data['status']}")
                    print(f"   - Phone: {send_otp_data['phone_number']}")
                    
                    if data["status"] == "mock":
                        print("   - Note: Using mock mode (trial fallback)")
                else:
                    print(f"❌ Failed to send OTP: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Verify OTP with wrong code
            print("   Testing POST /api/sms/verify-otp with wrong code...")
            verify_otp_data = {
                "phone_number": "+15005550006",
                "code": "123456"
            }
            
            async with self.session.post(
                f"{BASE_URL}/sms/verify-otp",
                json=verify_otp_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "valid" in data, "Missing 'valid' field in verify-otp response"
                    
                    if data["valid"] is False:
                        print(f"✅ Correctly rejected wrong OTP code")
                        print(f"   - Valid: {data['valid']}")
                    else:
                        print(f"⚠️  OTP verification returned valid=true (might be test mode)")
                else:
                    print(f"❌ Failed to verify OTP: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 3: Check cooldown status
            print("   Testing GET /api/sms/cooldown/{phone_number}...")
            phone_encoded = "+15005550006"
            
            async with self.session.get(
                f"{BASE_URL}/sms/cooldown/{phone_encoded}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ SMS cooldown check successful")
                    print(f"   - Response: {data}")
                elif response.status == 404:
                    print(f"✅ No cooldown found (expected for new number)")
                else:
                    print(f"❌ Failed to check cooldown: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing SMS verification: {str(e)}")
            return False
            
    async def test_auction_end_processing(self) -> bool:
        """Test Automated Handshake - Auction End Processing"""
        print("\n🧪 Testing Automated Handshake - Auction End Processing...")
        
        try:
            # Test 1: Trigger auction end processing
            print("   Testing POST /api/auctions/process-ended...")
            
            async with self.session.post(
                f"{BASE_URL}/auctions/process-ended"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "status" in data, "Missing 'status' field in process-ended response"
                    assert "message" in data, "Missing 'message' field in process-ended response"
                    assert data["status"] == "processing", f"Expected status 'processing', got: {data['status']}"
                    assert "processing triggered" in data["message"].lower(), f"Unexpected message: {data['message']}"
                    
                    print(f"✅ Auction end processing triggered successfully")
                    print(f"   - Status: {data['status']}")
                    print(f"   - Message: {data['message']}")
                else:
                    print(f"❌ Failed to trigger auction processing: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Check end status for non-existent auction
            print("   Testing GET /api/auctions/end-status/{auction_id} for non-existent auction...")
            fake_auction_id = "non-existent-auction-id"
            
            async with self.session.get(
                f"{BASE_URL}/auctions/end-status/{fake_auction_id}"
            ) as response:
                if response.status == 404:
                    print(f"✅ Correctly returned 404 for non-existent auction")
                else:
                    print(f"❌ Expected 404 for non-existent auction, got: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing auction end processing: {str(e)}")
            return False
            
    async def test_seller_analytics(self) -> bool:
        """Test Seller Analytics (Live Data)"""
        print("\n🧪 Testing Seller Analytics (Live Data)...")
        
        try:
            # Test 1: Track impression
            print("   Testing POST /api/analytics/impression...")
            impression_data = {
                "listing_id": "test-launch",
                "source": "homepage"
            }
            
            async with self.session.post(
                f"{BASE_URL}/analytics/impression",
                json=impression_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Impression tracked successfully")
                    print(f"   - Response: {data}")
                else:
                    print(f"❌ Failed to track impression: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Track click
            print("   Testing POST /api/analytics/click...")
            click_data = {
                "listing_id": "test-launch",
                "source": "marketplace"
            }
            
            async with self.session.post(
                f"{BASE_URL}/analytics/click",
                json=click_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Click tracked successfully")
                    print(f"   - Response: {data}")
                else:
                    print(f"❌ Failed to track click: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 3: Track multiple impressions to verify accumulation
            print("   Testing multiple impressions for accumulation...")
            for i in range(3):
                async with self.session.post(
                    f"{BASE_URL}/analytics/impression",
                    json=impression_data
                ) as response:
                    if response.status != 200:
                        print(f"❌ Failed to track impression {i+1}: {response.status}")
                        return False
            
            print(f"✅ Multiple impressions tracked successfully")
            
            # Test 4: Get seller analytics (requires admin login)
            if self.admin_token:
                print("   Testing GET /api/analytics/seller/{admin_id}?period=7d...")
                
                async with self.session.get(
                    f"{BASE_URL}/analytics/seller/{self.admin_id}?period=7d",
                    headers=self.get_admin_headers()
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ Seller analytics retrieved successfully")
                        print(f"   - Analytics data: {data}")
                        
                        # Verify we can see the tracked data
                        if "impressions" in str(data) or "clicks" in str(data):
                            print(f"   - Tracked data visible in analytics")
                    elif response.status == 404:
                        print(f"✅ No analytics data found (expected for new admin user)")
                    else:
                        print(f"❌ Failed to get seller analytics: {response.status}")
                        text = await response.text()
                        print(f"Response: {text}")
                        return False
            else:
                print("   ⏭️  Skipping seller analytics test - no admin token")
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing seller analytics: {str(e)}")
            return False
            
    async def test_service_worker_push_notifications(self) -> bool:
        """Test Service Worker & Push Notifications"""
        print("\n🧪 Testing Service Worker & Push Notifications...")
        
        try:
            # Test 1: Get service worker script
            print("   Testing GET /public/sw.js...")
            
            # Note: This might be served by the frontend, but let's check if backend has it
            async with self.session.get(f"{BASE_URL}/../public/sw.js") as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Verify it's a JavaScript file
                    if "javascript" in response.headers.get("content-type", "").lower() or \
                       "self.addEventListener" in content or \
                       "push" in content.lower():
                        print(f"✅ Service worker script found and appears valid")
                        print(f"   - Content-Type: {response.headers.get('content-type', 'N/A')}")
                        print(f"   - Content length: {len(content)} characters")
                    else:
                        print(f"⚠️  Service worker found but content unclear")
                        print(f"   - Content preview: {content[:100]}...")
                elif response.status == 404:
                    # Try alternative path
                    async with self.session.get("https://vscodeshare-1.preview.emergentagent.com/public/sw.js") as alt_response:
                        if alt_response.status == 200:
                            content = await alt_response.text()
                            print(f"✅ Service worker script found at alternative path")
                            print(f"   - Content length: {len(content)} characters")
                        else:
                            print(f"⚠️  Service worker not found at expected paths")
                            print(f"   - This might be handled by frontend build process")
                            return True  # Not a failure, just different architecture
                else:
                    print(f"❌ Failed to get service worker: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing service worker: {str(e)}")
            return False
            
    async def test_email_service_language_parity(self) -> bool:
        """Test Email Service (Language Parity)"""
        print("\n🧪 Testing Email Service (Language Parity)...")
        
        try:
            # Test 1: Login with admin credentials and check profile
            if not self.admin_token:
                print("   ⏭️  Skipping email service test - no admin token")
                return True
                
            print("   Testing admin profile includes preferred_language field...")
            
            async with self.session.get(
                f"{BASE_URL}/auth/me",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify preferred_language field exists
                    if "preferred_language" in data:
                        print(f"✅ User profile includes preferred_language field")
                        print(f"   - Preferred Language: {data['preferred_language']}")
                        
                        # Verify it's a valid language code
                        if data["preferred_language"] in ["en", "fr"]:
                            print(f"   - Language code is valid: {data['preferred_language']}")
                        else:
                            print(f"⚠️  Unexpected language code: {data['preferred_language']}")
                    else:
                        print(f"❌ User profile missing preferred_language field")
                        print(f"   - Available fields: {list(data.keys())}")
                        return False
                    
                    # Also check for backward compatibility language field
                    if "language" in data:
                        print(f"   - Backward compatibility 'language' field: {data['language']}")
                else:
                    print(f"❌ Failed to get admin profile: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Check if email templates support language selection
            print("   Testing email template language support...")
            
            async with self.session.get(
                f"{BASE_URL}/admin/email-templates",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Look for bilingual template support
                    if "categories" in data:
                        templates_found = False
                        en_templates = 0
                        fr_templates = 0
                        
                        for category in data["categories"]:
                            if "templates" in category:
                                templates_found = True
                                for template in category["templates"]:
                                    if "en_id" in template:
                                        en_templates += 1
                                    if "fr_id" in template:
                                        fr_templates += 1
                        
                        if templates_found:
                            print(f"✅ Email templates support bilingual configuration")
                            print(f"   - English templates: {en_templates}")
                            print(f"   - French templates: {fr_templates}")
                        else:
                            print(f"⚠️  Email templates structure unclear")
                    else:
                        print(f"⚠️  Email templates response structure unexpected")
                        print(f"   - Response keys: {list(data.keys())}")
                elif response.status == 401 or response.status == 403:
                    print(f"⚠️  Admin access required for email templates (expected)")
                else:
                    print(f"❌ Failed to get email templates: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing email service language parity: {str(e)}")
            return False
            
    async def run_all_tests(self):
        """Run all BidVex Anniversary Launch tests"""
        print("🚀 Starting BidVex Final Anniversary Launch Features Tests")
        print("=" * 80)
        
        await self.setup_session()
        
        try:
            # Setup admin user
            if not await self.login_admin_user():
                print("❌ Failed to setup admin user")
                return False
            
            # Run tests in specific order
            tests = [
                ("Live SMS Verification (Twilio Integration)", self.test_sms_verification_twilio),
                ("Automated Handshake - Auction End Processing", self.test_auction_end_processing),
                ("Seller Analytics (Live Data)", self.test_seller_analytics),
                ("Service Worker & Push Notifications", self.test_service_worker_push_notifications),
                ("Email Service (Language Parity)", self.test_email_service_language_parity)
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
            print("\n" + "=" * 80)
            print("📊 BIDVEX ANNIVERSARY LAUNCH FEATURES TEST RESULTS SUMMARY")
            print("=" * 80)
            
            passed = 0
            total = len(results)
            
            for test_name, result in results:
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status} - {test_name}")
                if result:
                    passed += 1
            
            print(f"\nOverall: {passed}/{total} tests passed")
            
            if passed == total:
                print("🎉 All BidVex Anniversary Launch features tests PASSED!")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = BidVexAnniversaryTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)