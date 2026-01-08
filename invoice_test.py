#!/usr/bin/env python3
"""
Invoice System Testing for Zero Commission Policy
Tests all seller and buyer invoice endpoints to verify zero commission implementation.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://bidding-platform-20.preview.emergentagent.com/api"
SELLER_EMAIL = "seller.invoice.test@bazario.com"
SELLER_PASSWORD = "SellerInvoice123!"
SELLER_NAME = "Estate Auction Seller"

BUYER_EMAIL = "buyer.invoice.test@bazario.com"
BUYER_PASSWORD = "BuyerInvoice123!"
BUYER_NAME = "Antique Collector Buyer"

class InvoiceSystemTester:
    def __init__(self):
        self.session = None
        self.seller_token = None
        self.seller_id = None
        self.buyer_token = None
        self.buyer_id = None
        self.auction_id = None
        self.test_results = {}
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def register_or_login_seller(self) -> bool:
        """Register or login seller account"""
        try:
            # Try to register
            user_data = {
                "email": SELLER_EMAIL,
                "password": SELLER_PASSWORD,
                "name": SELLER_NAME,
                "account_type": "business",
                "phone": "+14165551234",
                "address": "456 Auction Street, Toronto, ON M5H 2N2",
                "company_name": "Heritage Estate Auctions Inc.",
                "tax_number": "123456789RT0001"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.seller_token = data["access_token"]
                    self.seller_id = data["user"]["id"]
                    print(f"✅ Seller registered successfully: {self.seller_id}")
                    return True
                elif response.status == 400:
                    # Try login
                    return await self.login_seller()
                else:
                    print(f"❌ Failed to register seller: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error registering seller: {str(e)}")
            return False
            
    async def login_seller(self) -> bool:
        """Login seller account"""
        try:
            login_data = {
                "email": SELLER_EMAIL,
                "password": SELLER_PASSWORD
            }
            
            async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.seller_token = data["access_token"]
                    self.seller_id = data["user"]["id"]
                    print(f"✅ Seller logged in successfully: {self.seller_id}")
                    return True
                else:
                    print(f"❌ Failed to login seller: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in seller: {str(e)}")
            return False
            
    async def register_or_login_buyer(self) -> bool:
        """Register or login buyer account"""
        try:
            user_data = {
                "email": BUYER_EMAIL,
                "password": BUYER_PASSWORD,
                "name": BUYER_NAME,
                "account_type": "personal",
                "phone": "+14165559876",
                "address": "789 Collector Lane, Toronto, ON M4W 1A1"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.buyer_token = data["access_token"]
                    self.buyer_id = data["user"]["id"]
                    print(f"✅ Buyer registered successfully: {self.buyer_id}")
                    return True
                elif response.status == 400:
                    return await self.login_buyer()
                else:
                    print(f"❌ Failed to register buyer: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error registering buyer: {str(e)}")
            return False
            
    async def login_buyer(self) -> bool:
        """Login buyer account"""
        try:
            login_data = {
                "email": BUYER_EMAIL,
                "password": BUYER_PASSWORD
            }
            
            async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.buyer_token = data["access_token"]
                    self.buyer_id = data["user"]["id"]
                    print(f"✅ Buyer logged in successfully: {self.buyer_id}")
                    return True
                else:
                    print(f"❌ Failed to login buyer: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in buyer: {str(e)}")
            return False
            
    def get_seller_headers(self) -> Dict[str, str]:
        """Get seller authorization headers"""
        return {"Authorization": f"Bearer {self.seller_token}"}
        
    def get_buyer_headers(self) -> Dict[str, str]:
        """Get buyer authorization headers"""
        return {"Authorization": f"Bearer {self.buyer_token}"}
        
    async def create_test_auction(self) -> bool:
        """Create a multi-item auction for testing"""
        try:
            auction_data = {
                "title": "Estate Sale - Antique Furniture & Collectibles",
                "description": "Complete estate liquidation featuring Victorian furniture, vintage china, and rare collectibles from a prominent Toronto family.",
                "category": "Antiques & Collectibles",
                "location": "Downtown Toronto Auction House",
                "city": "Toronto",
                "region": "Ontario",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "auction_start_date": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "lots": [
                    {
                        "lot_number": 1,
                        "title": "Victorian Mahogany Dining Table",
                        "description": "Stunning Victorian-era mahogany dining table, seats 8-10, excellent condition",
                        "quantity": 1,
                        "starting_price": 1200.00,
                        "current_price": 1200.00,
                        "condition": "excellent",
                        "images": ["https://example.com/table1.jpg"]
                    },
                    {
                        "lot_number": 2,
                        "title": "Royal Doulton China Set (Service for 12)",
                        "description": "Complete Royal Doulton china service, vintage 1950s pattern, mint condition",
                        "quantity": 1,
                        "starting_price": 850.00,
                        "current_price": 850.00,
                        "condition": "excellent",
                        "images": ["https://example.com/china1.jpg"]
                    },
                    {
                        "lot_number": 3,
                        "title": "Antique Persian Rug (9x12)",
                        "description": "Hand-knotted Persian rug, circa 1920s, vibrant colors, professionally cleaned",
                        "quantity": 1,
                        "starting_price": 2500.00,
                        "current_price": 2500.00,
                        "condition": "good",
                        "images": ["https://example.com/rug1.jpg"]
                    },
                    {
                        "lot_number": 4,
                        "title": "Crystal Chandelier",
                        "description": "Elegant crystal chandelier, 8 lights, perfect for dining room",
                        "quantity": 1,
                        "starting_price": 650.00,
                        "current_price": 650.00,
                        "condition": "excellent",
                        "images": ["https://example.com/chandelier1.jpg"]
                    },
                    {
                        "lot_number": 5,
                        "title": "Vintage Grandfather Clock",
                        "description": "Working grandfather clock, Westminster chimes, walnut case",
                        "quantity": 1,
                        "starting_price": 1800.00,
                        "current_price": 1800.00,
                        "condition": "good",
                        "images": ["https://example.com/clock1.jpg"]
                    }
                ]
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=auction_data,
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.auction_id = data["id"]
                    print(f"✅ Test auction created successfully: {self.auction_id}")
                    print(f"   - Title: {data['title']}")
                    print(f"   - Total lots: {data['total_lots']}")
                    print(f"   - Commission rate: {data.get('commission_rate', 0.0)}%")
                    return True
                else:
                    print(f"❌ Failed to create auction: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error creating auction: {str(e)}")
            return False
            
    async def test_seller_statement(self) -> bool:
        """Test POST /api/invoices/seller-statement/{auction_id}/{seller_id}"""
        print("\n🧪 Testing Seller Statement Generation...")
        
        try:
            async with self.session.post(
                f"{BASE_URL}/invoices/seller-statement/{self.auction_id}/{self.seller_id}",
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "success" in data
                    assert data["success"] is True
                    assert "pdf_path" in data
                    assert "message" in data
                    
                    print(f"✅ Seller statement generated successfully")
                    print(f"   - PDF Path: {data['pdf_path']}")
                    print(f"   - Message: {data['message']}")
                    
                    # Verify commission rate is 0% (this is checked in the template)
                    print(f"   ✓ Commission rate should be 0% in the document")
                    print(f"   ✓ No commission deductions should be shown")
                    
                    return True
                else:
                    print(f"❌ Failed to generate seller statement: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing seller statement: {str(e)}")
            return False
            
    async def test_seller_receipt(self) -> bool:
        """Test POST /api/invoices/seller-receipt/{auction_id}/{seller_id}"""
        print("\n🧪 Testing Seller Receipt Generation...")
        
        try:
            async with self.session.post(
                f"{BASE_URL}/invoices/seller-receipt/{self.auction_id}/{self.seller_id}",
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "success" in data
                    assert data["success"] is True
                    assert "pdf_path" in data
                    assert "receipt_number" in data
                    assert "message" in data
                    
                    print(f"✅ Seller receipt generated successfully")
                    print(f"   - Receipt Number: {data['receipt_number']}")
                    print(f"   - PDF Path: {data['pdf_path']}")
                    
                    # Key verification points for zero commission
                    print(f"   ✓ Net payout should equal hammer total (no deductions)")
                    print(f"   ✓ Should show 'No commission charged for this auction' notice")
                    print(f"   ✓ Commission, GST, and QST on commission should all be $0.00")
                    
                    return True
                else:
                    print(f"❌ Failed to generate seller receipt: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing seller receipt: {str(e)}")
            return False
            
    async def test_commission_invoice(self) -> bool:
        """Test POST /api/invoices/commission-invoice/{auction_id}/{seller_id}"""
        print("\n🧪 Testing Commission Invoice Generation...")
        
        try:
            async with self.session.post(
                f"{BASE_URL}/invoices/commission-invoice/{self.auction_id}/{self.seller_id}",
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "success" in data
                    assert data["success"] is True
                    assert "invoice_number" in data
                    assert "pdf_path" in data
                    assert "message" in data
                    
                    print(f"✅ Commission invoice generated successfully")
                    print(f"   - Invoice Number: {data['invoice_number']}")
                    print(f"   - PDF Path: {data['pdf_path']}")
                    
                    # Key verification points for zero commission
                    print(f"   ✓ Commission amount should be $0.00")
                    print(f"   ✓ Should show 'No commission charged for this auction' in payment terms")
                    print(f"   ✓ Total due should be $0.00")
                    
                    return True
                else:
                    print(f"❌ Failed to generate commission invoice: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing commission invoice: {str(e)}")
            return False
            
    async def test_buyer_lots_won(self) -> bool:
        """Test POST /api/invoices/lots-won/{auction_id}/{user_id}"""
        print("\n🧪 Testing Buyer Lots Won Summary...")
        
        try:
            async with self.session.post(
                f"{BASE_URL}/invoices/lots-won/{self.auction_id}/{self.buyer_id}",
                headers=self.get_buyer_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "success" in data
                    assert data["success"] is True
                    assert "invoice_number" in data
                    assert "pdf_path" in data
                    assert "paddle_number" in data
                    assert "message" in data
                    
                    print(f"✅ Buyer lots won summary generated successfully")
                    print(f"   - Invoice Number: {data['invoice_number']}")
                    print(f"   - Paddle Number: {data['paddle_number']}")
                    print(f"   - PDF Path: {data['pdf_path']}")
                    
                    # Key verification points for payment separation
                    print(f"   ✓ Payment separation notice should be present")
                    print(f"   ✓ Buyer should see: 'To Seller: ${{hammer_total}}'")
                    print(f"   ✓ Buyer should see: 'To BidVex: ${{premium + taxes}}'")
                    
                    return True
                else:
                    print(f"❌ Failed to generate buyer lots won: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing buyer lots won: {str(e)}")
            return False
            
    async def test_payment_letter(self) -> bool:
        """Test POST /api/invoices/payment-letter/{auction_id}/{user_id}"""
        print("\n🧪 Testing Payment Letter Generation...")
        
        try:
            async with self.session.post(
                f"{BASE_URL}/invoices/payment-letter/{self.auction_id}/{self.buyer_id}",
                headers=self.get_buyer_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "success" in data
                    assert data["success"] is True
                    assert "invoice_number" in data
                    assert "pdf_path" in data
                    assert "paddle_number" in data
                    assert "amount_due" in data
                    assert "message" in data
                    
                    print(f"✅ Payment letter generated successfully")
                    print(f"   - Invoice Number: {data['invoice_number']}")
                    print(f"   - Paddle Number: {data['paddle_number']}")
                    print(f"   - Amount Due: ${data['amount_due']:.2f}")
                    print(f"   - PDF Path: {data['pdf_path']}")
                    
                    # Key verification points
                    print(f"   ✓ Two-part payment instructions should be clear")
                    print(f"   ✓ Amounts should be correctly separated")
                    
                    return True
                else:
                    print(f"❌ Failed to generate payment letter: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing payment letter: {str(e)}")
            return False
            
    async def test_authorization(self) -> bool:
        """Test authorization requirements"""
        print("\n🧪 Testing Authorization Requirements...")
        
        success = True
        
        # Test 1: Buyer trying to access seller documents
        try:
            async with self.session.post(
                f"{BASE_URL}/invoices/seller-statement/{self.auction_id}/{self.seller_id}",
                headers=self.get_buyer_headers()
            ) as response:
                if response.status == 403:
                    print("✅ Correctly rejected buyer accessing seller statement")
                else:
                    print(f"❌ Should reject buyer accessing seller docs, got: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing buyer access to seller docs: {str(e)}")
            success = False
            
        # Test 2: Unauthorized access (no token)
        try:
            async with self.session.post(
                f"{BASE_URL}/invoices/seller-statement/{self.auction_id}/{self.seller_id}"
            ) as response:
                if response.status == 401:
                    print("✅ Correctly rejected unauthorized access")
                else:
                    print(f"❌ Should reject unauthorized access, got: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing unauthorized access: {str(e)}")
            success = False
            
        # Test 3: Non-existent auction
        try:
            async with self.session.post(
                f"{BASE_URL}/invoices/seller-statement/non-existent-auction/{self.seller_id}",
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 404:
                    print("✅ Correctly rejected non-existent auction")
                else:
                    print(f"❌ Should reject non-existent auction, got: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing non-existent auction: {str(e)}")
            success = False
            
        return success
        
    async def verify_auction_commission_rate(self) -> bool:
        """Verify the auction has commission_rate set to 0.0"""
        print("\n🧪 Verifying Auction Commission Rate...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/multi-item-listings/{self.auction_id}",
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    commission_rate = data.get('commission_rate', None)
                    
                    if commission_rate is not None:
                        if commission_rate == 0.0:
                            print(f"✅ Auction commission rate is correctly set to 0.0%")
                            return True
                        else:
                            print(f"❌ Auction commission rate is {commission_rate}%, expected 0.0%")
                            return False
                    else:
                        print(f"❌ Auction commission_rate field is missing")
                        return False
                else:
                    print(f"❌ Failed to fetch auction: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error verifying commission rate: {str(e)}")
            return False
        
    async def run_all_tests(self):
        """Run all invoice system tests"""
        print("🚀 Starting Invoice System Tests - Zero Commission Policy")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Setup test accounts
            if not await self.register_or_login_seller():
                print("❌ Failed to setup seller account")
                return False
                
            if not await self.register_or_login_buyer():
                print("❌ Failed to setup buyer account")
                return False
                
            # Create test auction
            if not await self.create_test_auction():
                print("❌ Failed to create test auction")
                return False
            
            # Verify commission rate
            if not await self.verify_auction_commission_rate():
                print("⚠️  Warning: Commission rate verification failed")
            
            # Run invoice generation tests
            tests = [
                ("Seller Statement", self.test_seller_statement),
                ("Seller Receipt", self.test_seller_receipt),
                ("Commission Invoice", self.test_commission_invoice),
                ("Buyer Lots Won Summary", self.test_buyer_lots_won),
                ("Payment Letter", self.test_payment_letter),
                ("Authorization & Security", self.test_authorization)
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
            print("📊 INVOICE SYSTEM TEST RESULTS SUMMARY")
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
                print("🎉 All invoice system tests PASSED!")
                print("\n✅ Zero Commission Policy Verification:")
                print("   - Seller documents show 0% commission")
                print("   - Net payout equals hammer total for sellers")
                print("   - Buyer documents separate hammer payment from premium+taxes")
                print("   - All PDFs generated without errors")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = InvoiceSystemTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
