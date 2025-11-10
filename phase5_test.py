#!/usr/bin/env python3
"""
Phase 5 Part 4 & 5 Testing: Bilingual Support and Auto-Send PDFs
Tests bilingual PDF generation and auction completion with email automation
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
import os

# Configuration
BASE_URL = "https://auction-platform-12.preview.emergentagent.com/api"

# Test users
ADMIN_EMAIL = "admin@admin.bazario.com"
ADMIN_PASSWORD = "AdminTest123!"
ADMIN_NAME = "Admin Tester"

SELLER_EMAIL = "seller.phase5@bazario.com"
SELLER_PASSWORD = "SellerTest123!"
SELLER_NAME = "Phase 5 Seller"

BUYER1_EMAIL = "buyer1.phase5@bazario.com"
BUYER1_PASSWORD = "Buyer1Test123!"
BUYER1_NAME = "Phase 5 Buyer 1"

BUYER2_EMAIL = "buyer2.phase5@bazario.com"
BUYER2_PASSWORD = "Buyer2Test123!"
BUYER2_NAME = "Phase 5 Buyer 2"


class Phase5Tester:
    def __init__(self):
        self.session = None
        self.admin_token = None
        self.admin_id = None
        self.seller_token = None
        self.seller_id = None
        self.buyer1_token = None
        self.buyer1_id = None
        self.buyer2_token = None
        self.buyer2_id = None
        self.auction_id = None
        self.test_results = {}
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
    
    async def register_or_login_user(self, email: str, password: str, name: str, account_type: str = "personal") -> tuple:
        """Register or login a user, return (token, user_id)"""
        try:
            # Try to register
            user_data = {
                "email": email,
                "password": password,
                "name": name,
                "account_type": account_type,
                "phone": "+15141234567",
                "address": "123 Test Street, Montreal, QC"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Registered user: {email}")
                    return data["access_token"], data["user"]["id"]
                elif response.status == 400:
                    # User exists, try login
                    login_data = {"email": email, "password": password}
                    async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as login_response:
                        if login_response.status == 200:
                            data = await login_response.json()
                            print(f"✅ Logged in user: {email}")
                            return data["access_token"], data["user"]["id"]
                        else:
                            print(f"❌ Failed to login user {email}: {login_response.status}")
                            return None, None
                else:
                    print(f"❌ Failed to register user {email}: {response.status}")
                    return None, None
        except Exception as e:
            print(f"❌ Error with user {email}: {str(e)}")
            return None, None
    
    def get_auth_headers(self, token: str) -> Dict[str, str]:
        """Get authorization headers"""
        return {"Authorization": f"Bearer {token}"}
    
    async def setup_test_data(self) -> bool:
        """Setup all test users and auction"""
        print("\n🔧 Setting up test data...")
        
        # Setup admin user
        self.admin_token, self.admin_id = await self.register_or_login_user(
            ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME, "admin"
        )
        if not self.admin_token:
            print("❌ Failed to setup admin user")
            return False
        
        # Setup seller user
        self.seller_token, self.seller_id = await self.register_or_login_user(
            SELLER_EMAIL, SELLER_PASSWORD, SELLER_NAME, "business"
        )
        if not self.seller_token:
            print("❌ Failed to setup seller user")
            return False
        
        # Setup buyer users
        self.buyer1_token, self.buyer1_id = await self.register_or_login_user(
            BUYER1_EMAIL, BUYER1_PASSWORD, BUYER1_NAME, "personal"
        )
        if not self.buyer1_token:
            print("❌ Failed to setup buyer 1")
            return False
        
        self.buyer2_token, self.buyer2_id = await self.register_or_login_user(
            BUYER2_EMAIL, BUYER2_PASSWORD, BUYER2_NAME, "personal"
        )
        if not self.buyer2_token:
            print("❌ Failed to setup buyer 2")
            return False
        
        # Create auction with lots
        auction_data = {
            "title": "Phase 5 Estate Sale - Bilingual Test Auction",
            "description": "Complete estate sale with antique furniture and collectibles for Phase 5 testing",
            "category": "Home & Garden",
            "location": "Old Montreal Historic District",
            "city": "Montreal",
            "region": "Quebec",
            "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "auction_start_date": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "lots": [
                {
                    "lot_number": 1,
                    "title": "Victorian Mahogany Dining Table",
                    "description": "Authentic Victorian mahogany dining table from 1880s, seats 8-10 people",
                    "quantity": 1,
                    "starting_price": 1200.00,
                    "current_price": 1850.00,
                    "condition": "excellent",
                    "images": ["https://example.com/table1.jpg"]
                },
                {
                    "lot_number": 2,
                    "title": "Antique Persian Rug Collection",
                    "description": "Set of 3 hand-woven Persian rugs from early 1900s",
                    "quantity": 3,
                    "starting_price": 800.00,
                    "current_price": 1450.00,
                    "condition": "good",
                    "images": ["https://example.com/rug1.jpg"]
                },
                {
                    "lot_number": 3,
                    "title": "Crystal Chandelier - French Empire Style",
                    "description": "Stunning French Empire crystal chandelier, 24 lights",
                    "quantity": 1,
                    "starting_price": 2500.00,
                    "current_price": 3200.00,
                    "condition": "excellent",
                    "images": ["https://example.com/chandelier1.jpg"]
                },
                {
                    "lot_number": 4,
                    "title": "Vintage Porcelain Tea Set",
                    "description": "Complete Royal Doulton porcelain tea set, 12 place settings",
                    "quantity": 1,
                    "starting_price": 350.00,
                    "current_price": 350.00,
                    "condition": "like_new",
                    "images": ["https://example.com/teaset1.jpg"]
                },
                {
                    "lot_number": 5,
                    "title": "Oil Painting - Canadian Landscape",
                    "description": "Original oil painting by Quebec artist, circa 1950",
                    "quantity": 1,
                    "starting_price": 600.00,
                    "current_price": 600.00,
                    "condition": "good",
                    "images": ["https://example.com/painting1.jpg"]
                }
            ]
        }
        
        try:
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=auction_data,
                headers=self.get_auth_headers(self.seller_token)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.auction_id = data["id"]
                    print(f"✅ Created test auction: {self.auction_id}")
                    print(f"   - Title: {data['title']}")
                    print(f"   - Total lots: {data['total_lots']}")
                    return True
                else:
                    print(f"❌ Failed to create auction: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error creating auction: {str(e)}")
            return False
    
    async def test_bilingual_lots_won_pdf(self) -> bool:
        """Test Phase 5 Part 4: Bilingual Lots Won PDF Generation"""
        print("\n🧪 Testing Phase 5 Part 4: Bilingual Lots Won PDF...")
        
        try:
            # Test 1: Generate English PDF
            print("\n  📄 Generating English PDF...")
            async with self.session.post(
                f"{BASE_URL}/invoices/lots-won/{self.auction_id}/{self.buyer1_id}?lang=en",
                headers=self.get_auth_headers(self.admin_token)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "success" in data
                    assert data["success"] is True
                    assert "invoice_number" in data
                    assert "pdf_path" in data
                    assert "paddle_number" in data
                    
                    english_pdf_path = data["pdf_path"]
                    english_invoice_number = data["invoice_number"]
                    paddle_number = data["paddle_number"]
                    
                    print(f"  ✅ English PDF generated successfully")
                    print(f"     - Invoice Number: {english_invoice_number}")
                    print(f"     - PDF Path: {english_pdf_path}")
                    print(f"     - Paddle Number: {paddle_number}")
                    
                    # Verify PDF file exists
                    if os.path.exists(english_pdf_path):
                        file_size = os.path.getsize(english_pdf_path)
                        print(f"     - PDF File Size: {file_size} bytes")
                    else:
                        print(f"  ⚠️  PDF file not found at: {english_pdf_path}")
                else:
                    print(f"  ❌ Failed to generate English PDF: {response.status}")
                    text = await response.text()
                    print(f"  Response: {text}")
                    return False
            
            # Test 2: Generate French PDF
            print("\n  📄 Generating French PDF...")
            async with self.session.post(
                f"{BASE_URL}/invoices/lots-won/{self.auction_id}/{self.buyer2_id}?lang=fr",
                headers=self.get_auth_headers(self.admin_token)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "success" in data
                    assert data["success"] is True
                    assert "invoice_number" in data
                    assert "pdf_path" in data
                    assert "paddle_number" in data
                    
                    french_pdf_path = data["pdf_path"]
                    french_invoice_number = data["invoice_number"]
                    paddle_number_fr = data["paddle_number"]
                    
                    print(f"  ✅ French PDF generated successfully")
                    print(f"     - Invoice Number: {french_invoice_number}")
                    print(f"     - PDF Path: {french_pdf_path}")
                    print(f"     - Paddle Number: {paddle_number_fr}")
                    
                    # Verify PDF file exists
                    if os.path.exists(french_pdf_path):
                        file_size = os.path.getsize(french_pdf_path)
                        print(f"     - PDF File Size: {file_size} bytes")
                    else:
                        print(f"  ⚠️  PDF file not found at: {french_pdf_path}")
                    
                    # Verify different paddle numbers for different buyers
                    assert paddle_number != paddle_number_fr, "Different buyers should have different paddle numbers"
                    print(f"  ✅ Paddle numbers correctly assigned to different buyers")
                    
                    return True
                else:
                    print(f"  ❌ Failed to generate French PDF: {response.status}")
                    text = await response.text()
                    print(f"  Response: {text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing bilingual PDFs: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_auction_completion(self) -> bool:
        """Test Phase 5 Part 5: Auction Completion with Auto-Send"""
        print("\n🧪 Testing Phase 5 Part 5: Auction Completion Endpoint...")
        
        try:
            async with self.session.post(
                f"{BASE_URL}/auctions/{self.auction_id}/complete?lang=en",
                headers=self.get_auth_headers(self.admin_token)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    print(f"\n  ✅ Auction completion endpoint responded successfully")
                    
                    # Verify response structure
                    assert "auction_id" in data
                    assert "auction_title" in data
                    assert "documents_generated" in data
                    assert "emails_sent" in data
                    assert "summary" in data
                    
                    print(f"     - Auction ID: {data['auction_id']}")
                    print(f"     - Auction Title: {data['auction_title']}")
                    
                    # Check documents generated
                    documents = data["documents_generated"]
                    print(f"\n  📄 Documents Generated ({len(documents)}):")
                    for doc in documents:
                        print(f"     - {doc}")
                    
                    # Verify seller documents
                    expected_seller_docs = ['seller_statement', 'seller_receipt', 'commission_invoice']
                    for doc in expected_seller_docs:
                        if doc in documents:
                            print(f"  ✅ {doc} generated")
                        else:
                            print(f"  ⚠️  {doc} NOT generated")
                    
                    # Check emails sent
                    emails = data["emails_sent"]
                    print(f"\n  📧 Emails Sent ({len(emails)}):")
                    for email in emails:
                        print(f"     - Type: {email['type']}")
                        print(f"       Recipient: {email['recipient']}")
                        if 'documents' in email:
                            print(f"       Documents: {', '.join(email['documents'])}")
                        if 'paddle_number' in email:
                            print(f"       Paddle: {email['paddle_number']}")
                    
                    # Verify at least seller email and buyer emails sent
                    email_types = [e['type'] for e in emails]
                    if 'seller_documents' in email_types:
                        print(f"  ✅ Seller email sent")
                    else:
                        print(f"  ⚠️  Seller email NOT sent (email types: {email_types})")
                    
                    buyer_emails = [e for e in emails if e['type'] == 'buyer_invoice']
                    if len(buyer_emails) >= 2:
                        print(f"  ✅ {len(buyer_emails)} buyer emails sent")
                    else:
                        print(f"  ⚠️  Expected at least 2 buyer emails, got {len(buyer_emails)}")
                    
                    # Check summary
                    summary = data["summary"]
                    print(f"\n  📊 Summary:")
                    print(f"     - Total Documents: {summary['total_documents']}")
                    print(f"     - Total Emails: {summary['total_emails']}")
                    print(f"     - Total Errors: {summary['total_errors']}")
                    
                    if summary['total_errors'] > 0:
                        print(f"\n  ⚠️  Errors encountered:")
                        for error in data.get('errors', []):
                            print(f"     - {error}")
                    
                    # Verify auction status changed to 'ended'
                    async with self.session.get(
                        f"{BASE_URL}/multi-item-listings/{self.auction_id}",
                        headers=self.get_auth_headers(self.admin_token)
                    ) as auction_response:
                        if auction_response.status == 200:
                            auction_data = await auction_response.json()
                            if auction_data.get('status') == 'ended':
                                print(f"  ✅ Auction status updated to 'ended'")
                            else:
                                print(f"  ⚠️  Auction status is '{auction_data.get('status')}', expected 'ended'")
                    
                    return True
                else:
                    print(f"  ❌ Failed to complete auction: {response.status}")
                    text = await response.text()
                    print(f"  Response: {text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing auction completion: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_email_logs(self) -> bool:
        """Test Phase 5 Part 5: Email Logs Endpoint"""
        print("\n🧪 Testing Email Logs Endpoint...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/email-logs",
                headers=self.get_auth_headers(self.admin_token)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    print(f"  ✅ Email logs retrieved successfully")
                    
                    # Verify response structure
                    assert "total" in data
                    assert "emails" in data
                    assert isinstance(data["emails"], list)
                    
                    total_emails = data["total"]
                    emails = data["emails"]
                    
                    print(f"     - Total Emails Logged: {total_emails}")
                    
                    if total_emails == 0:
                        print(f"  ⚠️  No email logs found")
                        return False
                    
                    # Display email logs
                    print(f"\n  📧 Email Log Details:")
                    for i, email in enumerate(emails[:10], 1):  # Show first 10
                        print(f"\n     Email {i}:")
                        print(f"       - Recipient: {email.get('recipient', 'N/A')}")
                        print(f"       - Subject: {email.get('subject', 'N/A')}")
                        print(f"       - Timestamp: {email.get('timestamp', 'N/A')}")
                        if 'attachments' in email:
                            print(f"       - Attachments: {len(email['attachments'])}")
                            for att in email['attachments']:
                                print(f"         * {att}")
                    
                    # Verify email logs have required fields
                    for email in emails:
                        assert "recipient" in email, "Email log should have recipient"
                        assert "subject" in email, "Email log should have subject"
                        assert "timestamp" in email, "Email log should have timestamp"
                    
                    print(f"\n  ✅ All email logs have required fields")
                    
                    # Verify seller and buyer emails are present
                    seller_emails = [e for e in emails if SELLER_EMAIL in e.get('recipient', '')]
                    buyer_emails = [e for e in emails if BUYER1_EMAIL in e.get('recipient', '') or BUYER2_EMAIL in e.get('recipient', '')]
                    
                    print(f"  ✅ Seller emails logged: {len(seller_emails)}")
                    print(f"  ✅ Buyer emails logged: {len(buyer_emails)}")
                    
                    return True
                else:
                    print(f"  ❌ Failed to retrieve email logs: {response.status}")
                    text = await response.text()
                    print(f"  Response: {text}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing email logs: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_invoice_email_tracking(self) -> bool:
        """Test Phase 5 Part 5: Invoice Email Tracking"""
        print("\n🧪 Testing Invoice Email Tracking...")
        
        try:
            # Test seller invoices
            print("\n  📋 Checking Seller Invoices...")
            async with self.session.get(
                f"{BASE_URL}/invoices/{self.seller_id}",
                headers=self.get_auth_headers(self.admin_token)
            ) as response:
                if response.status == 200:
                    invoices = await response.json()
                    
                    print(f"  ✅ Retrieved {len(invoices)} seller invoices")
                    
                    # Filter invoices for this auction
                    auction_invoices = [inv for inv in invoices if inv.get('auction_id') == self.auction_id]
                    
                    if len(auction_invoices) == 0:
                        print(f"  ⚠️  No invoices found for auction {self.auction_id}")
                        return False
                    
                    print(f"     - Invoices for this auction: {len(auction_invoices)}")
                    
                    # Check email tracking fields
                    for invoice in auction_invoices:
                        invoice_type = invoice.get('invoice_type', 'unknown')
                        email_sent = invoice.get('email_sent', False)
                        sent_timestamp = invoice.get('sent_timestamp')
                        recipient_email = invoice.get('recipient_email')
                        
                        print(f"\n     Invoice Type: {invoice_type}")
                        print(f"       - Email Sent: {email_sent}")
                        print(f"       - Sent Timestamp: {sent_timestamp}")
                        print(f"       - Recipient Email: {recipient_email}")
                        
                        if email_sent:
                            assert sent_timestamp is not None, "Sent timestamp should be populated"
                            assert recipient_email is not None, "Recipient email should be populated"
                            print(f"       ✅ Email tracking fields populated")
                        else:
                            print(f"       ⚠️  Email not marked as sent")
                else:
                    print(f"  ❌ Failed to retrieve seller invoices: {response.status}")
                    return False
            
            # Test buyer invoices
            print("\n  📋 Checking Buyer 1 Invoices...")
            async with self.session.get(
                f"{BASE_URL}/invoices/{self.buyer1_id}",
                headers=self.get_auth_headers(self.admin_token)
            ) as response:
                if response.status == 200:
                    invoices = await response.json()
                    
                    print(f"  ✅ Retrieved {len(invoices)} buyer 1 invoices")
                    
                    # Filter invoices for this auction
                    auction_invoices = [inv for inv in invoices if inv.get('auction_id') == self.auction_id]
                    
                    if len(auction_invoices) > 0:
                        print(f"     - Invoices for this auction: {len(auction_invoices)}")
                        
                        for invoice in auction_invoices:
                            invoice_type = invoice.get('invoice_type', 'unknown')
                            email_sent = invoice.get('email_sent', False)
                            
                            print(f"     - {invoice_type}: Email Sent = {email_sent}")
                            
                            if email_sent:
                                print(f"       ✅ Email tracking updated")
                else:
                    print(f"  ⚠️  Failed to retrieve buyer 1 invoices: {response.status}")
            
            print("\n  📋 Checking Buyer 2 Invoices...")
            async with self.session.get(
                f"{BASE_URL}/invoices/{self.buyer2_id}",
                headers=self.get_auth_headers(self.admin_token)
            ) as response:
                if response.status == 200:
                    invoices = await response.json()
                    
                    print(f"  ✅ Retrieved {len(invoices)} buyer 2 invoices")
                    
                    # Filter invoices for this auction
                    auction_invoices = [inv for inv in invoices if inv.get('auction_id') == self.auction_id]
                    
                    if len(auction_invoices) > 0:
                        print(f"     - Invoices for this auction: {len(auction_invoices)}")
                        
                        for invoice in auction_invoices:
                            invoice_type = invoice.get('invoice_type', 'unknown')
                            email_sent = invoice.get('email_sent', False)
                            
                            print(f"     - {invoice_type}: Email Sent = {email_sent}")
                            
                            if email_sent:
                                print(f"       ✅ Email tracking updated")
                else:
                    print(f"  ⚠️  Failed to retrieve buyer 2 invoices: {response.status}")
            
            return True
                    
        except Exception as e:
            print(f"❌ Error testing invoice email tracking: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    async def run_all_tests(self):
        """Run all Phase 5 tests"""
        print("🚀 Starting Phase 5 Part 4 & 5 Testing")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Setup test data
            if not await self.setup_test_data():
                print("❌ Failed to setup test data")
                return False
            
            # Run tests in order
            tests = [
                ("Phase 5 Part 4: Bilingual Lots Won PDF", self.test_bilingual_lots_won_pdf),
                ("Phase 5 Part 5: Auction Completion", self.test_auction_completion),
                ("Phase 5 Part 5: Email Logs", self.test_email_logs),
                ("Phase 5 Part 5: Invoice Email Tracking", self.test_invoice_email_tracking)
            ]
            
            results = []
            for test_name, test_func in tests:
                try:
                    result = await test_func()
                    results.append((test_name, result))
                    self.test_results[test_name] = result
                except Exception as e:
                    print(f"❌ {test_name} failed with exception: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    results.append((test_name, False))
                    self.test_results[test_name] = False
            
            # Print summary
            print("\n" + "=" * 70)
            print("📊 PHASE 5 TEST RESULTS SUMMARY")
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
                print("🎉 All Phase 5 tests PASSED!")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()


async def main():
    """Main test runner"""
    tester = Phase5Tester()
    success = await tester.run_all_tests()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
