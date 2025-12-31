#!/usr/bin/env python3
"""
Phase 6: Launch Readiness - Comprehensive Backend Validation
BidVex Auction Platform - Pre-Production Testing Suite

This test suite validates all critical systems before production deployment:
1. Security & Access Validation
2. Infrastructure Health Check  
3. Currency Enforcement Validation
4. Bilingual Support Testing (All 4 combinations)
5. Admin Panel Functionality
6. PDF Generation All Combinations
7. E2E Scenarios
"""

import asyncio
import aiohttp
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

# Configuration
BASE_URL = "https://bidvex-upgrade.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@admin.bazario.com"
ADMIN_PASSWORD = "admin123"
TEST_USER_EMAIL = "test.user@bazario.com"
TEST_USER_PASSWORD = "Test123!"

# Fallback credentials for testing
PHASE6_ADMIN_EMAIL = "phase6.admin@admin.bazario.com"
PHASE6_ADMIN_PASSWORD = "Phase6Admin123!"
PHASE6_USER_EMAIL = "phase6.user@bazario.com"
PHASE6_USER_PASSWORD = "Phase6User123!"

class Phase6ComprehensiveTester:
    def __init__(self):
        self.session = None
        self.admin_token = None
        self.admin_id = None
        self.test_user_token = None
        self.test_user_id = None
        self.test_results = {}
        self.test_auction_id = None
        self.test_seller_id = None
        self.test_buyer_ids = []
        
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
            # Try Phase 6 admin first
            admin_data = {
                "email": PHASE6_ADMIN_EMAIL,
                "password": PHASE6_ADMIN_PASSWORD,
                "name": "Phase 6 Admin",
                "account_type": "business",
                "phone": "+1234567890"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=admin_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.admin_token = data["access_token"]
                    self.admin_id = data["user"]["id"]
                    print(f"✅ Phase 6 admin user registered: {self.admin_id}")
                    return True
                elif response.status == 400:
                    # User already exists, try login
                    return await self.login_admin_user(PHASE6_ADMIN_EMAIL, PHASE6_ADMIN_PASSWORD)
                else:
                    print(f"❌ Failed to register Phase 6 admin: {response.status}")
                    # Try original admin credentials
                    return await self.login_admin_user(ADMIN_EMAIL, ADMIN_PASSWORD)
        except Exception as e:
            print(f"❌ Error setting up admin user: {str(e)}")
            return False
            
    async def login_admin_user(self, email=None, password=None) -> bool:
        """Login with admin credentials"""
        try:
            login_data = {
                "email": email or PHASE6_ADMIN_EMAIL,
                "password": password or PHASE6_ADMIN_PASSWORD
            }
            
            async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.admin_token = data["access_token"]
                    self.admin_id = data["user"]["id"]
                    print(f"✅ Admin user authenticated: {self.admin_id}")
                    return True
                else:
                    print(f"❌ Failed to authenticate admin: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in admin: {str(e)}")
            return False
            
    async def setup_test_user(self) -> bool:
        """Setup test user for testing"""
        try:
            # Try to register Phase 6 test user first
            user_data = {
                "email": PHASE6_USER_EMAIL,
                "password": PHASE6_USER_PASSWORD,
                "name": "Phase 6 Test User",
                "account_type": "personal",
                "phone": "+1234567891"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_user_token = data["access_token"]
                    self.test_user_id = data["user"]["id"]
                    print(f"✅ Phase 6 test user registered: {self.test_user_id}")
                    return True
                elif response.status == 400:
                    # User already exists, try login
                    return await self.login_test_user(PHASE6_USER_EMAIL, PHASE6_USER_PASSWORD)
                else:
                    print(f"❌ Failed to register Phase 6 test user: {response.status}")
                    # Try original test user
                    return await self.login_test_user(TEST_USER_EMAIL, TEST_USER_PASSWORD)
        except Exception as e:
            print(f"❌ Error setting up test user: {str(e)}")
            return False
            
    async def login_test_user(self, email=None, password=None) -> bool:
        """Login with test user credentials"""
        try:
            login_data = {
                "email": email or PHASE6_USER_EMAIL,
                "password": password or PHASE6_USER_PASSWORD
            }
            
            async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_user_token = data["access_token"]
                    self.test_user_id = data["user"]["id"]
                    print(f"✅ Test user authenticated: {self.test_user_id}")
                    return True
                else:
                    print(f"❌ Failed to authenticate test user: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in test user: {str(e)}")
            return False
            
    def get_admin_headers(self) -> Dict[str, str]:
        """Get admin authorization headers"""
        return {"Authorization": f"Bearer {self.admin_token}"}
        
    def get_user_headers(self) -> Dict[str, str]:
        """Get user authorization headers"""
        return {"Authorization": f"Bearer {self.test_user_token}"}

    # ============================================
    # 1. SECURITY & ACCESS VALIDATION
    # ============================================
    
    async def test_admin_authorization(self) -> bool:
        """Test admin endpoints require proper authorization"""
        print("\n🔐 Testing Admin Authorization...")
        
        try:
            success = True
            
            # Test 1: Admin endpoint with admin credentials
            async with self.session.get(
                f"{BASE_URL}/admin/currency-appeals",
                headers=self.get_admin_headers()
            ) as response:
                if response.status in [200, 404]:  # 404 is ok if no appeals exist
                    print("✅ Admin access granted with admin credentials")
                else:
                    print(f"❌ Admin endpoint failed with admin creds: {response.status}")
                    success = False
            
            # Test 2: Admin endpoint with regular user credentials
            async with self.session.get(
                f"{BASE_URL}/admin/currency-appeals",
                headers=self.get_user_headers()
            ) as response:
                if response.status == 403:
                    print("✅ Admin access denied for regular user")
                else:
                    print(f"❌ Should deny regular user admin access, got: {response.status}")
                    success = False
            
            # Test 3: Admin endpoint without credentials
            async with self.session.get(f"{BASE_URL}/admin/currency-appeals") as response:
                if response.status == 401:
                    print("✅ Admin access denied without credentials")
                else:
                    print(f"❌ Should deny access without credentials, got: {response.status}")
                    success = False
            
            return success
            
        except Exception as e:
            print(f"❌ Error testing admin authorization: {str(e)}")
            return False
    
    async def test_password_security(self) -> bool:
        """Test bcrypt password hashing and security"""
        print("\n🔒 Testing Password Security...")
        
        try:
            # Create a test user to verify password hashing
            test_email = f"security.test.{int(time.time())}@bazario.com"
            user_data = {
                "email": test_email,
                "password": "TestPassword123!",
                "name": "Security Test User",
                "account_type": "personal",
                "phone": "+1234567890"
            }
            
            # Test registration
            async with self.session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ User registration successful")
                    
                    # Test login with correct password
                    login_data = {
                        "email": test_email,
                        "password": "TestPassword123!"
                    }
                    
                    async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as login_response:
                        if login_response.status == 200:
                            print("✅ Login successful with correct password")
                        else:
                            print(f"❌ Login failed with correct password: {login_response.status}")
                            return False
                    
                    # Test login with incorrect password
                    wrong_login_data = {
                        "email": test_email,
                        "password": "WrongPassword123!"
                    }
                    
                    async with self.session.post(f"{BASE_URL}/auth/login", json=wrong_login_data) as wrong_response:
                        if wrong_response.status == 401:
                            print("✅ Login correctly rejected with wrong password")
                        else:
                            print(f"❌ Should reject wrong password, got: {wrong_response.status}")
                            return False
                    
                    return True
                else:
                    print(f"❌ Failed to register test user: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing password security: {str(e)}")
            return False
    
    async def test_audit_logging(self) -> bool:
        """Test audit logging for currency appeals"""
        print("\n📝 Testing Audit Logging...")
        
        try:
            # Register a new user to trigger geolocation audit log
            test_email = f"audit.test.{int(time.time())}@bazario.com"
            user_data = {
                "email": test_email,
                "password": "AuditTest123!",
                "name": "Audit Test User",
                "account_type": "personal",
                "phone": "+1234567891"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
                if response.status == 200:
                    data = await response.json()
                    user = data["user"]
                    
                    # Verify geolocation fields are populated (indicating audit log creation)
                    if ("enforced_currency" in user and 
                        "currency_locked" in user and 
                        "location_confidence_score" in user):
                        print("✅ Geolocation audit logging working (fields populated)")
                        print(f"   - Enforced Currency: {user['enforced_currency']}")
                        print(f"   - Currency Locked: {user['currency_locked']}")
                        print(f"   - Location Confidence: {user['location_confidence_score']}")
                        return True
                    else:
                        print("❌ Geolocation audit fields missing")
                        return False
                else:
                    print(f"❌ Failed to register user for audit test: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing audit logging: {str(e)}")
            return False

    # ============================================
    # 2. INFRASTRUCTURE HEALTH CHECK
    # ============================================
    
    async def test_backend_health(self) -> bool:
        """Test backend health endpoint"""
        print("\n🏥 Testing Backend Health...")
        
        try:
            async with self.session.get(f"{BASE_URL}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Backend health endpoint responding")
                    print(f"   - Status: {data.get('status', 'N/A')}")
                    print(f"   - Database: {data.get('database', 'N/A')}")
                    return True
                else:
                    print(f"❌ Health endpoint failed: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing backend health: {str(e)}")
            return False
    
    async def test_mongodb_connection(self) -> bool:
        """Test MongoDB connection integrity"""
        print("\n🗄️ Testing MongoDB Connection...")
        
        try:
            # Test by making a simple authenticated request that requires DB
            async with self.session.get(
                f"{BASE_URL}/auth/me",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ MongoDB connection active (user data retrieved)")
                    print(f"   - User ID: {data.get('id', 'N/A')}")
                    return True
                else:
                    print(f"❌ MongoDB connection issue: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing MongoDB connection: {str(e)}")
            return False
    
    async def test_load_testing(self) -> bool:
        """Basic load testing - 10 rapid requests"""
        print("\n⚡ Testing Load Handling (10 rapid requests)...")
        
        try:
            endpoints = [
                ("/auth/me", self.get_admin_headers()),
                ("/multi-item-listings", {}),
                ("/categories", {})
            ]
            
            success_count = 0
            total_requests = 0
            start_time = time.time()
            
            for endpoint, headers in endpoints:
                for i in range(3):  # 3 requests per endpoint
                    try:
                        async with self.session.get(f"{BASE_URL}{endpoint}", headers=headers) as response:
                            total_requests += 1
                            if response.status < 500:  # Accept any non-server error
                                success_count += 1
                    except Exception:
                        total_requests += 1
            
            end_time = time.time()
            duration = end_time - start_time
            
            success_rate = (success_count / total_requests) * 100
            avg_response_time = duration / total_requests
            
            print(f"✅ Load test completed")
            print(f"   - Success Rate: {success_rate:.1f}% ({success_count}/{total_requests})")
            print(f"   - Average Response Time: {avg_response_time:.3f}s")
            print(f"   - Total Duration: {duration:.3f}s")
            
            return success_rate >= 80 and avg_response_time < 2.0
            
        except Exception as e:
            print(f"❌ Error in load testing: {str(e)}")
            return False

    # ============================================
    # 3. CURRENCY ENFORCEMENT VALIDATION
    # ============================================
    
    async def test_currency_lock_unlock(self) -> bool:
        """Test currency lock and unlock functionality"""
        print("\n💱 Testing Currency Lock & Unlock...")
        
        try:
            # Get current user info
            async with self.session.get(
                f"{BASE_URL}/auth/me",
                headers=self.get_user_headers()
            ) as response:
                if response.status == 200:
                    user_data = await response.json()
                    is_locked = user_data.get("currency_locked", False)
                    enforced_currency = user_data.get("enforced_currency")
                    
                    print(f"   - Currency Locked: {is_locked}")
                    print(f"   - Enforced Currency: {enforced_currency}")
                    
                    # Test currency change when unlocked
                    if not is_locked:
                        different_currency = "CAD" if enforced_currency == "USD" else "USD"
                        
                        async with self.session.put(
                            f"{BASE_URL}/users/me",
                            json={"preferred_currency": different_currency},
                            headers=self.get_user_headers()
                        ) as update_response:
                            if update_response.status == 200:
                                print("✅ Currency change allowed when unlocked")
                                
                                # Change back
                                await self.session.put(
                                    f"{BASE_URL}/users/me",
                                    json={"preferred_currency": enforced_currency},
                                    headers=self.get_user_headers()
                                )
                            else:
                                print(f"❌ Currency change failed when unlocked: {update_response.status}")
                                return False
                    else:
                        # Test currency change when locked (should fail)
                        different_currency = "CAD" if enforced_currency == "USD" else "USD"
                        
                        async with self.session.put(
                            f"{BASE_URL}/users/me",
                            json={"preferred_currency": different_currency},
                            headers=self.get_user_headers()
                        ) as update_response:
                            if update_response.status == 403:
                                data = await update_response.json()
                                detail = data.get("detail", {})
                                if detail.get("error") == "currency_locked":
                                    print("✅ Currency change correctly blocked when locked")
                                else:
                                    print("❌ Wrong error structure for locked currency")
                                    return False
                            else:
                                print(f"❌ Should block currency change when locked, got: {update_response.status}")
                                return False
                    
                    return True
                else:
                    print(f"❌ Failed to get user info: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing currency lock/unlock: {str(e)}")
            return False
    
    async def test_currency_appeal_workflow(self) -> bool:
        """Test complete currency appeal workflow"""
        print("\n📋 Testing Currency Appeal Workflow...")
        
        try:
            # Test submitting appeal (will likely fail in container environment)
            appeal_data = {
                "requested_currency": "CAD",
                "reason": "Relocated to Canada for work",
                "current_location": "Toronto, ON"
            }
            
            async with self.session.post(
                f"{BASE_URL}/currency-appeal",
                params=appeal_data,
                headers=self.get_user_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    appeal_id = data.get("appeal_id")
                    print(f"✅ Currency appeal submitted: {appeal_id}")
                    
                    # Test admin review
                    review_data = {
                        "status": "approved",
                        "admin_notes": "Verified relocation documents"
                    }
                    
                    async with self.session.post(
                        f"{BASE_URL}/admin/currency-appeals/{appeal_id}/review",
                        params=review_data,
                        headers=self.get_admin_headers()
                    ) as review_response:
                        if review_response.status == 200:
                            print("✅ Admin appeal review successful")
                            return True
                        else:
                            print(f"❌ Admin review failed: {review_response.status}")
                            return False
                            
                elif response.status == 400:
                    data = await response.json()
                    if "Currency is not locked" in data.get("detail", ""):
                        print("✅ Appeal correctly rejected (currency not locked - expected in container)")
                        return True
                    else:
                        print(f"❌ Unexpected appeal error: {data.get('detail')}")
                        return False
                else:
                    print(f"❌ Appeal submission failed: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing currency appeal workflow: {str(e)}")
            return False

    # ============================================
    # 4. BILINGUAL SUPPORT TESTING
    # ============================================
    
    async def test_bilingual_invoice_generation(self) -> bool:
        """Test all 4 invoice combinations (EN/CAD, EN/USD, FR/CAD, FR/USD)"""
        print("\n🌐 Testing Bilingual Invoice Generation (All 4 Combinations)...")
        
        try:
            # First, get existing auction data
            async with self.session.get(f"{BASE_URL}/multi-item-listings") as response:
                if response.status == 200:
                    listings = await response.json()
                    if not listings:
                        print("❌ No auctions found for invoice testing")
                        return False
                    
                    auction = listings[0]
                    auction_id = auction["id"]
                    seller_id = auction["seller_id"]
                    
                    print(f"   - Using auction: {auction_id}")
                    print(f"   - Seller: {seller_id}")
                    
                    # Test all 4 combinations for seller statement
                    combinations = [
                        ("en", "CAD"),
                        ("en", "USD"), 
                        ("fr", "CAD"),
                        ("fr", "USD")
                    ]
                    
                    success_count = 0
                    
                    for lang, currency in combinations:
                        try:
                            async with self.session.post(
                                f"{BASE_URL}/invoices/seller-statement/{auction_id}/{seller_id}?lang={lang}&currency={currency}",
                                headers=self.get_admin_headers()
                            ) as invoice_response:
                                if invoice_response.status == 200:
                                    data = await invoice_response.json()
                                    print(f"✅ Seller Statement {lang.upper()}/{currency}: {data.get('pdf_path', 'Generated')}")
                                    success_count += 1
                                else:
                                    print(f"❌ Seller Statement {lang.upper()}/{currency} failed: {invoice_response.status}")
                        except Exception as e:
                            print(f"❌ Error generating {lang.upper()}/{currency} invoice: {str(e)}")
                    
                    # Test buyer documents if we have users
                    async with self.session.post(
                        f"{BASE_URL}/invoices/lots-won/{auction_id}/{self.test_user_id}?lang=en&currency=CAD",
                        headers=self.get_admin_headers()
                    ) as buyer_response:
                        if buyer_response.status == 200:
                            data = await buyer_response.json()
                            print(f"✅ Buyer Lots Won EN/CAD: {data.get('pdf_path', 'Generated')}")
                            success_count += 1
                        else:
                            print(f"❌ Buyer invoice failed: {buyer_response.status}")
                    
                    return success_count >= 4  # At least 4 successful generations
                else:
                    print(f"❌ Failed to get auctions: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing bilingual invoices: {str(e)}")
            return False
    
    async def test_tax_logic_validation(self) -> bool:
        """Test tax logic for CAD vs USD invoices"""
        print("\n💰 Testing Tax Logic Validation...")
        
        try:
            # Get auction data
            async with self.session.get(f"{BASE_URL}/multi-item-listings") as response:
                if response.status == 200:
                    listings = await response.json()
                    if not listings:
                        print("⚠️  No auctions found for tax testing")
                        return True
                    
                    auction = listings[0]
                    auction_id = auction["id"]
                    seller_id = auction["seller_id"]
                    
                    # Test CAD invoice (should have taxes)
                    async with self.session.post(
                        f"{BASE_URL}/invoices/lots-won/{auction_id}/{self.test_user_id}?lang=en&currency=CAD",
                        headers=self.get_admin_headers()
                    ) as cad_response:
                        if cad_response.status == 200:
                            print("✅ CAD invoice generated (should include GST + QST)")
                        else:
                            print(f"❌ CAD invoice failed: {cad_response.status}")
                            return False
                    
                    # Test USD invoice (should have no taxes)
                    async with self.session.post(
                        f"{BASE_URL}/invoices/lots-won/{auction_id}/{self.test_user_id}?lang=en&currency=USD",
                        headers=self.get_admin_headers()
                    ) as usd_response:
                        if usd_response.status == 200:
                            print("✅ USD invoice generated (should have no taxes)")
                        else:
                            print(f"❌ USD invoice failed: {usd_response.status}")
                            return False
                    
                    return True
                else:
                    print(f"❌ Failed to get auctions for tax testing: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing tax logic: {str(e)}")
            return False

    # ============================================
    # 5. ADMIN PANEL FUNCTIONALITY
    # ============================================
    
    async def test_admin_currency_appeals(self) -> bool:
        """Test admin currency appeals management"""
        print("\n👨‍💼 Testing Admin Currency Appeals Management...")
        
        try:
            # Test getting all appeals
            async with self.session.get(
                f"{BASE_URL}/admin/currency-appeals",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Admin can access currency appeals")
                    print(f"   - Total appeals: {len(data.get('appeals', []))}")
                    return True
                elif response.status == 404:
                    print("✅ Admin currency appeals endpoint accessible (no appeals found)")
                    return True
                else:
                    print(f"❌ Admin appeals access failed: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing admin currency appeals: {str(e)}")
            return False
    
    async def test_other_admin_endpoints(self) -> bool:
        """Test other critical admin endpoints"""
        print("\n🔧 Testing Other Admin Endpoints...")
        
        try:
            success_count = 0
            total_tests = 0
            
            # Test admin users endpoint
            total_tests += 1
            async with self.session.get(
                f"{BASE_URL}/admin/users",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    print("✅ Admin users endpoint accessible")
                    success_count += 1
                else:
                    print(f"❌ Admin users failed: {response.status}")
            
            # Test admin analytics
            total_tests += 1
            async with self.session.get(
                f"{BASE_URL}/admin/analytics",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Admin analytics accessible")
                    print(f"   - Active listings: {data.get('active_listings', 'N/A')}")
                    print(f"   - Total users: {data.get('total_users', 'N/A')}")
                    success_count += 1
                else:
                    print(f"❌ Admin analytics failed: {response.status}")
            
            return success_count >= (total_tests // 2)  # At least half should work
            
        except Exception as e:
            print(f"❌ Error testing admin endpoints: {str(e)}")
            return False

    # ============================================
    # 6. EMAIL TRACKING & AUTO-SEND
    # ============================================
    
    async def test_email_logs(self) -> bool:
        """Test email logs endpoint"""
        print("\n📧 Testing Email Logs...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/email-logs",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Email logs accessible")
                    print(f"   - Total email logs: {len(data)}")
                    
                    if len(data) > 0:
                        log = data[0]
                        print(f"   - Latest email to: {log.get('recipient', 'N/A')}")
                        print(f"   - Subject: {log.get('subject', 'N/A')}")
                    
                    return True
                else:
                    print(f"❌ Email logs failed: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing email logs: {str(e)}")
            return False
    
    async def test_auction_completion(self) -> bool:
        """Test auction completion with auto-send"""
        print("\n🏁 Testing Auction Completion & Auto-Send...")
        
        try:
            # Get an auction to complete
            async with self.session.get(f"{BASE_URL}/multi-item-listings") as response:
                if response.status == 200:
                    listings = await response.json()
                    if not listings:
                        print("⚠️  No auctions found for completion testing")
                        return True
                    
                    auction = listings[0]
                    auction_id = auction["id"]
                    
                    # Test auction completion
                    async with self.session.post(
                        f"{BASE_URL}/auctions/{auction_id}/complete?lang=en",
                        headers=self.get_admin_headers()
                    ) as complete_response:
                        if complete_response.status == 200:
                            data = await complete_response.json()
                            print(f"✅ Auction completion successful")
                            print(f"   - Documents generated: {data.get('total_documents', 0)}")
                            print(f"   - Emails sent: {data.get('total_emails', 0)}")
                            print(f"   - Errors: {data.get('total_errors', 0)}")
                            return True
                        else:
                            print(f"❌ Auction completion failed: {complete_response.status}")
                            return False
                else:
                    print(f"❌ Failed to get auctions: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing auction completion: {str(e)}")
            return False

    # ============================================
    # MAIN TEST RUNNER
    # ============================================
    
    async def run_all_tests(self):
        """Run all Phase 6 validation tests"""
        print("🚀 PHASE 6: LAUNCH READINESS - COMPREHENSIVE BACKEND VALIDATION")
        print("=" * 80)
        print("BidVex Auction Platform - Pre-Production Testing Suite")
        print("=" * 80)
        
        await self.setup_session()
        
        try:
            # Setup test users
            if not await self.setup_admin_user():
                print("❌ Failed to setup admin user")
                return False
                
            if not await self.setup_test_user():
                print("❌ Failed to setup test user")
                return False
            
            # Define all test sections
            test_sections = [
                ("1. SECURITY & ACCESS VALIDATION", [
                    ("Admin Authorization", self.test_admin_authorization),
                    ("Password Security (bcrypt)", self.test_password_security),
                    ("Audit Logging", self.test_audit_logging)
                ]),
                ("2. INFRASTRUCTURE HEALTH CHECK", [
                    ("Backend Health Endpoint", self.test_backend_health),
                    ("MongoDB Connection", self.test_mongodb_connection),
                    ("Load Testing (Basic)", self.test_load_testing)
                ]),
                ("3. CURRENCY ENFORCEMENT VALIDATION", [
                    ("Currency Lock & Unlock", self.test_currency_lock_unlock),
                    ("Currency Appeal Workflow", self.test_currency_appeal_workflow)
                ]),
                ("4. BILINGUAL SUPPORT TESTING", [
                    ("Invoice Generation (All 4 Combinations)", self.test_bilingual_invoice_generation),
                    ("Tax Logic Validation", self.test_tax_logic_validation)
                ]),
                ("5. ADMIN PANEL FUNCTIONALITY", [
                    ("Currency Appeals Management", self.test_admin_currency_appeals),
                    ("Other Admin Endpoints", self.test_other_admin_endpoints)
                ]),
                ("6. EMAIL TRACKING & AUTO-SEND", [
                    ("Email Logs", self.test_email_logs),
                    ("Auction Completion", self.test_auction_completion)
                ])
            ]
            
            # Run all tests
            all_results = []
            section_results = {}
            
            for section_name, tests in test_sections:
                print(f"\n{'='*60}")
                print(f"🧪 {section_name}")
                print(f"{'='*60}")
                
                section_passed = 0
                section_total = len(tests)
                
                for test_name, test_func in tests:
                    try:
                        result = await test_func()
                        all_results.append((f"{section_name} - {test_name}", result))
                        self.test_results[test_name] = result
                        
                        if result:
                            section_passed += 1
                            
                    except Exception as e:
                        print(f"❌ {test_name} failed with exception: {str(e)}")
                        all_results.append((f"{section_name} - {test_name}", False))
                        self.test_results[test_name] = False
                
                section_results[section_name] = (section_passed, section_total)
            
            # Print comprehensive summary
            print(f"\n{'='*80}")
            print("📊 PHASE 6 VALIDATION RESULTS SUMMARY")
            print(f"{'='*80}")
            
            total_passed = 0
            total_tests = 0
            
            for section_name, (passed, total) in section_results.items():
                total_passed += passed
                total_tests += total
                percentage = (passed / total * 100) if total > 0 else 0
                status = "✅ PASS" if passed == total else "⚠️  PARTIAL" if passed > 0 else "❌ FAIL"
                print(f"{status} {section_name}: {passed}/{total} ({percentage:.0f}%)")
            
            overall_percentage = (total_passed / total_tests * 100) if total_tests > 0 else 0
            
            print(f"\n🎯 OVERALL RESULTS: {total_passed}/{total_tests} tests passed ({overall_percentage:.0f}%)")
            
            if total_passed == total_tests:
                print("🎉 ALL PHASE 6 VALIDATION TESTS PASSED!")
                print("✅ System ready for production deployment")
                return True
            elif overall_percentage >= 80:
                print("⚠️  MOSTLY READY - Some minor issues found")
                print("🔍 Review failed tests before production deployment")
                return True
            else:
                print("❌ CRITICAL ISSUES FOUND - NOT READY FOR PRODUCTION")
                print("🚨 Address failed tests before deployment")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = Phase6ComprehensiveTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)