#!/usr/bin/env python3
"""
BidVex Backend API Testing
Tests the newly implemented messaging, document upload, and multi-item listing features.
"""

import asyncio
import aiohttp
import json
import base64
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://auction-hub-38.preview.emergentagent.com/api"
TEST_USER_EMAIL = "lots.homepage.tester@bazario.com"
TEST_USER_PASSWORD = "LotsTest123!"
TEST_SELLER_EMAIL = "bidvex.seller@bazario.com"
TEST_SELLER_PASSWORD = "BidVexSeller123!"
TEST_LISTING_ID = "14b0838a-a269-46e4-a015-6ba2a9751dfc"

class BidVexBackendTester:
    def __init__(self):
        self.session = None
        self.buyer_token = None
        self.buyer_id = None
        self.seller_token = None
        self.seller_id = None
        self.test_results = {}
        self.test_listing_id = None
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def setup_test_users(self) -> bool:
        """Setup buyer and seller test users"""
        try:
            # Setup buyer user
            buyer_data = {
                "email": TEST_USER_EMAIL,
                "password": TEST_USER_PASSWORD,
                "name": "BidVex Buyer",
                "account_type": "personal",
                "phone": "+1234567890"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=buyer_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.buyer_token = data["access_token"]
                    self.buyer_id = data["user"]["id"]
                    print(f"✅ Buyer user setup: {self.buyer_id}")
                elif response.status == 400:
                    # User exists, try login
                    async with self.session.post(f"{BASE_URL}/auth/login", json={
                        "email": TEST_USER_EMAIL,
                        "password": TEST_USER_PASSWORD
                    }) as login_response:
                        if login_response.status == 200:
                            data = await login_response.json()
                            self.buyer_token = data["access_token"]
                            self.buyer_id = data["user"]["id"]
                            print(f"✅ Buyer user logged in: {self.buyer_id}")
                        else:
                            print(f"❌ Failed to login buyer: {login_response.status}")
                            return False
                else:
                    print(f"❌ Failed to setup buyer: {response.status}")
                    return False
            
            # Setup seller user (business account for multi-item listings)
            seller_data = {
                "email": TEST_SELLER_EMAIL,
                "password": TEST_SELLER_PASSWORD,
                "name": "BidVex Seller",
                "account_type": "business",
                "phone": "+1234567891",
                "company_name": "BidVex Test Company"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=seller_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.seller_token = data["access_token"]
                    self.seller_id = data["user"]["id"]
                    print(f"✅ Seller user setup: {self.seller_id}")
                elif response.status == 400:
                    # User exists, try login
                    async with self.session.post(f"{BASE_URL}/auth/login", json={
                        "email": TEST_SELLER_EMAIL,
                        "password": TEST_SELLER_PASSWORD
                    }) as login_response:
                        if login_response.status == 200:
                            data = await login_response.json()
                            self.seller_token = data["access_token"]
                            self.seller_id = data["user"]["id"]
                            print(f"✅ Seller user logged in: {self.seller_id}")
                        else:
                            print(f"❌ Failed to login seller: {login_response.status}")
                            return False
                else:
                    print(f"❌ Failed to setup seller: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error setting up test users: {str(e)}")
            return False
            
    def get_buyer_headers(self) -> Dict[str, str]:
        """Get buyer authorization headers"""
        return {"Authorization": f"Bearer {self.buyer_token}"}
        
    def get_seller_headers(self) -> Dict[str, str]:
        """Get seller authorization headers"""
        return {"Authorization": f"Bearer {self.seller_token}"}
        
    async def test_messaging_endpoints(self) -> bool:
        """Test messaging endpoints: POST /api/messages, GET /api/messages, GET /api/messages/unread-count"""
        print("\n🧪 Testing Messaging Endpoints...")
        
        try:
            # Test 1: Send message to seller (POST /api/messages)
            message_data = {
                "receiver_id": self.seller_id,
                "content": "Hi, I'm interested in your listing. Can you provide more details?",
                "listing_id": TEST_LISTING_ID
            }
            
            async with self.session.post(
                f"{BASE_URL}/messages",
                json=message_data,
                headers=self.get_buyer_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Message sent successfully")
                    print(f"   - Message ID: {data.get('id')}")
                    print(f"   - Content: {data.get('content')}")
                    print(f"   - Listing ID: {data.get('listing_id')}")
                    
                    # Verify message structure
                    required_fields = ["id", "conversation_id", "sender_id", "receiver_id", "content", "is_read", "created_at"]
                    for field in required_fields:
                        assert field in data, f"Missing field in message: {field}"
                    
                    assert data["sender_id"] == self.buyer_id
                    assert data["receiver_id"] == self.seller_id
                    assert data["listing_id"] == TEST_LISTING_ID
                    assert data["is_read"] == False
                else:
                    print(f"❌ Failed to send message: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Get unread message count (GET /api/messages/unread-count)
            async with self.session.get(
                f"{BASE_URL}/messages/unread-count",
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Unread count retrieved successfully")
                    print(f"   - Unread count: {data.get('unread_count')}")
                    
                    assert "unread_count" in data
                    assert isinstance(data["unread_count"], int)
                    assert data["unread_count"] >= 1  # Should have at least the message we just sent
                else:
                    print(f"❌ Failed to get unread count: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 3: Get all user messages (GET /api/messages)
            async with self.session.get(
                f"{BASE_URL}/messages",
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 200:
                    messages = await response.json()
                    print(f"✅ Messages retrieved successfully")
                    print(f"   - Total messages: {len(messages)}")
                    
                    # Verify we have at least one message
                    assert len(messages) >= 1
                    
                    # Check the structure of the first message
                    if messages:
                        msg = messages[0]
                        required_fields = ["id", "conversation_id", "sender_id", "receiver_id", "content", "is_read", "created_at"]
                        for field in required_fields:
                            assert field in msg, f"Missing field in message: {field}"
                else:
                    print(f"❌ Failed to get messages: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 4: Get messages filtered by listing_id
            async with self.session.get(
                f"{BASE_URL}/messages?listing_id={TEST_LISTING_ID}",
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 200:
                    messages = await response.json()
                    print(f"✅ Messages filtered by listing_id retrieved successfully")
                    print(f"   - Messages for listing {TEST_LISTING_ID}: {len(messages)}")
                    
                    # Verify all messages are for the correct listing
                    for msg in messages:
                        if msg.get("listing_id"):
                            assert msg["listing_id"] == TEST_LISTING_ID
                else:
                    print(f"❌ Failed to get filtered messages: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 5: Send reply from seller
            reply_data = {
                "receiver_id": self.buyer_id,
                "content": "Thank you for your interest! The item is in excellent condition and comes with original packaging.",
                "listing_id": TEST_LISTING_ID
            }
            
            async with self.session.post(
                f"{BASE_URL}/messages",
                json=reply_data,
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Reply sent successfully")
                    print(f"   - Reply content: {data.get('content')[:50]}...")
                else:
                    print(f"❌ Failed to send reply: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing messaging endpoints: {str(e)}")
            return False
            
    async def test_document_upload_endpoint(self) -> bool:
        """Test document upload endpoint with various file types and sizes"""
        print("\n🧪 Testing Document Upload Endpoint...")
        
        try:
            # Test 1: Valid PDF upload (< 10MB)
            # Create a small PDF-like base64 content
            pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000074 00000 n \n0000000120 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n179\n%%EOF"
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            
            pdf_data = {
                "filename": "test_document.pdf",
                "content_type": "application/pdf",
                "base64_content": pdf_base64
            }
            
            async with self.session.post(
                f"{BASE_URL}/upload-document",
                json=pdf_data,
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ PDF upload successful")
                    print(f"   - Filename: {data.get('filename')}")
                    print(f"   - Content Type: {data.get('content_type')}")
                    print(f"   - Size: {data.get('size_mb')} MB")
                    
                    assert data["success"] == True
                    assert data["filename"] == "test_document.pdf"
                    assert data["content_type"] == "application/pdf"
                    assert data["size_mb"] < 10
                    assert "base64_content" in data
                else:
                    print(f"❌ Failed to upload PDF: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Valid PNG image upload (< 10MB)
            # Create a small PNG-like base64 content (1x1 pixel PNG)
            png_content = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jU77mgAAAABJRU5ErkJggg==")
            png_base64 = base64.b64encode(png_content).decode('utf-8')
            
            png_data = {
                "filename": "test_image.png",
                "content_type": "image/png",
                "base64_content": png_base64
            }
            
            async with self.session.post(
                f"{BASE_URL}/upload-document",
                json=png_data,
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ PNG upload successful")
                    print(f"   - Filename: {data.get('filename')}")
                    print(f"   - Size: {data.get('size_mb')} MB")
                    
                    assert data["success"] == True
                    assert data["content_type"] == "image/png"
                else:
                    print(f"❌ Failed to upload PNG: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 3: Invalid file type (should reject .txt)
            txt_content = base64.b64encode(b"This is a text file content").decode('utf-8')
            txt_data = {
                "filename": "test_document.txt",
                "content_type": "text/plain",
                "base64_content": txt_content
            }
            
            async with self.session.post(
                f"{BASE_URL}/upload-document",
                json=txt_data,
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 400:
                    data = await response.json()
                    print(f"✅ Correctly rejected invalid file type")
                    print(f"   - Error: {data.get('detail')}")
                    
                    assert "Invalid file type" in data.get("detail", "")
                else:
                    print(f"❌ Should have rejected .txt file, got: {response.status}")
                    return False
            
            # Test 4: File too large (simulate > 10MB)
            # Create a large base64 string to simulate > 10MB file
            large_content = b"x" * (11 * 1024 * 1024)  # 11MB of data
            large_base64 = base64.b64encode(large_content).decode('utf-8')
            
            large_data = {
                "filename": "large_document.pdf",
                "content_type": "application/pdf",
                "base64_content": large_base64
            }
            
            async with self.session.post(
                f"{BASE_URL}/upload-document",
                json=large_data,
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 400:
                    data = await response.json()
                    print(f"✅ Correctly rejected file too large")
                    print(f"   - Error: {data.get('detail')}")
                    
                    assert "File too large" in data.get("detail", "")
                else:
                    print(f"❌ Should have rejected large file, got: {response.status}")
                    return False
            
            # Test 5: Invalid base64 content
            invalid_data = {
                "filename": "invalid.pdf",
                "content_type": "application/pdf",
                "base64_content": "this is definitely not base64 content with spaces and special chars @#$%"
            }
            
            async with self.session.post(
                f"{BASE_URL}/upload-document",
                json=invalid_data,
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 400:
                    data = await response.json()
                    print(f"✅ Correctly rejected invalid base64")
                    print(f"   - Error: {data.get('detail')}")
                    
                    assert "Invalid base64 content" in data.get("detail", "")
                else:
                    print(f"❌ Should have rejected invalid base64, got: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing document upload endpoint: {str(e)}")
            return False
            
    async def test_multi_item_listing_new_fields(self) -> bool:
        """Test multi-item listing creation with new fields and data integrity"""
        print("\n🧪 Testing Multi-Item Listing Creation with New Fields...")
        
        try:
            # Create sample documents (base64 encoded)
            terms_pdf = base64.b64encode(b"Terms and Conditions PDF content").decode('utf-8')
            info_pdf = base64.b64encode(b"Important Information PDF content").decode('utf-8')
            catalogue_pdf = base64.b64encode(b"Catalogue PDF content").decode('utf-8')
            
            # Test 1: Create listing with all new fields
            listing_data = {
                "title": "BidVex Test Auction with New Features",
                "description": "Testing new document upload, shipping info, and visit availability features",
                "category": "Electronics",
                "location": "Toronto, ON",
                "city": "Toronto",
                "region": "Ontario",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "auction_start_date": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "lots": [
                    {
                        "lot_number": 1,
                        "title": "Test Item 1",
                        "description": "A test item for BidVex testing",
                        "quantity": 1,
                        "starting_price": 100.0,
                        "current_price": 100.0,
                        "condition": "New",
                        "images": []
                    }
                ],
                "documents": {
                    "terms_conditions": terms_pdf,
                    "important_info": info_pdf,
                    "catalogue": catalogue_pdf
                },
                "shipping_info": {
                    "available": True,
                    "methods": ["Standard Shipping", "Express Shipping", "Local Pickup"],
                    "rates": {
                        "standard": 15.99,
                        "express": 29.99,
                        "local_pickup": 0.00
                    },
                    "delivery_time": "3-5 business days for standard, 1-2 days for express"
                },
                "visit_availability": {
                    "offered": True,
                    "dates": ["2024-12-15", "2024-12-16", "2024-12-17"],
                    "instructions": "Please call 24 hours in advance to schedule your visit. Visits available between 9 AM - 5 PM."
                }
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_seller_headers()
            ) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    self.test_listing_id = data.get("id")
                    print(f"✅ Multi-item listing created successfully")
                    print(f"   - Listing ID: {self.test_listing_id}")
                    print(f"   - Title: {data.get('title')}")
                    
                    # Verify new fields are present
                    assert "documents" in data
                    assert "shipping_info" in data
                    assert "visit_availability" in data
                    
                    # Verify documents structure
                    docs = data["documents"]
                    assert "terms_conditions" in docs
                    assert "important_info" in docs
                    assert "catalogue" in docs
                    
                    # Verify shipping info structure
                    shipping = data["shipping_info"]
                    assert shipping["available"] == True
                    assert "methods" in shipping
                    assert "rates" in shipping
                    assert "delivery_time" in shipping
                    
                    # Verify visit availability structure
                    visit = data["visit_availability"]
                    assert visit["offered"] == True
                    assert "dates" in visit
                    assert "instructions" in visit
                    
                    print(f"   - Documents: {len(docs)} files uploaded")
                    print(f"   - Shipping methods: {len(shipping['methods'])}")
                    print(f"   - Visit dates available: {len(visit['dates'])}")
                    
                else:
                    print(f"❌ Failed to create listing: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Retrieve listing and verify new fields persist
            async with self.session.get(
                f"{BASE_URL}/multi-item-listings/{self.test_listing_id}",
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Listing retrieved successfully")
                    
                    # Verify all new fields are returned
                    assert "documents" in data
                    assert "shipping_info" in data
                    assert "visit_availability" in data
                    
                    # Verify documents persist as base64 strings
                    docs = data["documents"]
                    assert docs["terms_conditions"] == terms_pdf
                    assert docs["important_info"] == info_pdf
                    assert docs["catalogue"] == catalogue_pdf
                    
                    # Verify shipping info structure matches
                    shipping = data["shipping_info"]
                    assert shipping["available"] == True
                    assert len(shipping["methods"]) == 3
                    assert shipping["rates"]["standard"] == 15.99
                    
                    # Verify visit availability structure matches
                    visit = data["visit_availability"]
                    assert visit["offered"] == True
                    assert len(visit["dates"]) == 3
                    
                    print(f"   - All new fields persisted correctly in database")
                    
                else:
                    print(f"❌ Failed to retrieve listing: {response.status}")
                    return False
            
            # Test 3: Create listing with shipping_info.available = false (should be null)
            listing_no_shipping = {
                "title": "BidVex Test - No Shipping",
                "description": "Testing shipping_info null when available=false",
                "category": "Electronics",
                "location": "Toronto, ON",
                "city": "Toronto",
                "region": "Ontario",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "lots": [
                    {
                        "lot_number": 1,
                        "title": "Test Item No Shipping",
                        "description": "A test item with no shipping",
                        "quantity": 1,
                        "starting_price": 50.0,
                        "current_price": 50.0,
                        "condition": "Used",
                        "images": []
                    }
                ],
                "shipping_info": {
                    "available": False
                }
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_no_shipping,
                headers=self.get_seller_headers()
            ) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    no_shipping_id = data.get("id")
                    print(f"✅ Listing with no shipping created")
                    
                    # Verify shipping_info behavior when available=false
                    shipping = data.get("shipping_info")
                    if shipping:
                        assert shipping["available"] == False
                        # Methods, rates, delivery_time should be null or not present when available=false
                        print(f"   - Shipping available: {shipping['available']}")
                    
                else:
                    print(f"❌ Failed to create no-shipping listing: {response.status}")
                    return False
            
            # Test 4: Create listing with visit_availability.offered = false (should be null)
            listing_no_visits = {
                "title": "BidVex Test - No Visits",
                "description": "Testing visit_availability null when offered=false",
                "category": "Electronics",
                "location": "Toronto, ON",
                "city": "Toronto",
                "region": "Ontario",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "lots": [
                    {
                        "lot_number": 1,
                        "title": "Test Item No Visits",
                        "description": "A test item with no visits",
                        "quantity": 1,
                        "starting_price": 75.0,
                        "current_price": 75.0,
                        "condition": "New",
                        "images": []
                    }
                ],
                "visit_availability": {
                    "offered": False
                }
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_no_visits,
                headers=self.get_seller_headers()
            ) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    no_visits_id = data.get("id")
                    print(f"✅ Listing with no visits created")
                    
                    # Verify visit_availability behavior when offered=false
                    visit = data.get("visit_availability")
                    if visit:
                        assert visit["offered"] == False
                        # Dates and instructions should be null or not present when offered=false
                        print(f"   - Visits offered: {visit['offered']}")
                    
                else:
                    print(f"❌ Failed to create no-visits listing: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing multi-item listing new fields: {str(e)}")
            return False
            
    async def test_data_integrity(self) -> bool:
        """Test data integrity for new fields"""
        print("\n🧪 Testing Data Integrity...")
        
        try:
            if not self.test_listing_id:
                print("⏭️  Skipping data integrity test - no test listing created")
                return True
            
            # Retrieve the test listing and verify field structure
            async with self.session.get(
                f"{BASE_URL}/multi-item-listings/{self.test_listing_id}",
                headers=self.get_seller_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Test 1: Verify documents persist as base64 strings
                    docs = data.get("documents", {})
                    for doc_type, content in docs.items():
                        assert isinstance(content, str), f"Document {doc_type} should be string (base64)"
                        # Verify it's valid base64
                        try:
                            base64.b64decode(content)
                            print(f"✅ Document {doc_type} is valid base64")
                        except Exception:
                            print(f"❌ Document {doc_type} is not valid base64")
                            return False
                    
                    # Test 2: Verify shipping_info structure
                    shipping = data.get("shipping_info")
                    if shipping and shipping.get("available"):
                        required_fields = ["methods", "rates", "delivery_time"]
                        for field in required_fields:
                            assert field in shipping, f"Missing shipping field: {field}"
                        
                        assert isinstance(shipping["methods"], list)
                        assert isinstance(shipping["rates"], dict)
                        assert isinstance(shipping["delivery_time"], str)
                        print(f"✅ Shipping info structure is correct")
                    
                    # Test 3: Verify visit_availability structure
                    visit = data.get("visit_availability")
                    if visit and visit.get("offered"):
                        required_fields = ["dates", "instructions"]
                        for field in required_fields:
                            assert field in visit, f"Missing visit field: {field}"
                        
                        assert isinstance(visit["dates"], list)
                        assert isinstance(visit["instructions"], str)
                        print(f"✅ Visit availability structure is correct")
                    
                    # Test 4: Verify field schema matches expected structure
                    expected_fields = [
                        "id", "seller_id", "title", "description", "category",
                        "location", "city", "region", "auction_end_date",
                        "lots", "status", "created_at", "total_lots",
                        "documents", "shipping_info", "visit_availability"
                    ]
                    
                    for field in expected_fields:
                        assert field in data, f"Missing expected field: {field}"
                    
                    print(f"✅ All expected fields present in listing")
                    print(f"   - Total fields: {len(data.keys())}")
                    print(f"   - Documents: {len(data.get('documents', {}))}")
                    print(f"   - Shipping available: {data.get('shipping_info', {}).get('available', False)}")
                    print(f"   - Visits offered: {data.get('visit_availability', {}).get('offered', False)}")
                    
                    return True
                    
                else:
                    print(f"❌ Failed to retrieve listing for integrity test: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing data integrity: {str(e)}")
            return False
            
    async def run_all_tests(self):
        """Run all BidVex backend API tests"""
        print("🚀 Starting BidVex Backend API Tests")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Setup test users
            if not await self.setup_test_users():
                print("❌ Failed to setup test users")
                return False
            
            # Run tests in order
            tests = [
                ("Messaging Endpoints", self.test_messaging_endpoints),
                ("Document Upload Endpoint", self.test_document_upload_endpoint),
                ("Multi-Item Listing New Fields", self.test_multi_item_listing_new_fields),
                ("Data Integrity", self.test_data_integrity)
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
            print("📊 BIDVEX BACKEND API TEST RESULTS SUMMARY")
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
                print("🎉 All BidVex backend API tests PASSED!")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = BidVexBackendTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)