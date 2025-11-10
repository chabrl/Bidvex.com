#!/usr/bin/env python3
"""
Multi-Item Listings Backend API Testing for BidVex Platform
Tests the complete multi-item listings functionality including create, list, and get endpoints.
Focuses on Phase 3 Multi-Lot Wizard backend validation.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

# Configuration
BASE_URL = "https://auction-platform-12.preview.emergentagent.com/api"
TEST_BUSINESS_EMAIL = "business.tester@bidvex.com"
TEST_PERSONAL_EMAIL = "personal.tester@bidvex.com"
TEST_PASSWORD = "MultiLotTest123!"

class MultiItemListingTester:
    def __init__(self):
        self.session = None
        self.business_auth_token = None
        self.personal_auth_token = None
        self.business_user_id = None
        self.personal_user_id = None
        self.created_listing_ids = []
        self.test_results = {}
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def register_business_user(self) -> bool:
        """Register a business test user"""
        try:
            user_data = {
                "email": TEST_BUSINESS_EMAIL,
                "password": TEST_PASSWORD,
                "name": "Estate Sale Business",
                "account_type": "business",
                "phone": "+1234567890",
                "address": "456 Business Ave, Commerce City",
                "company_name": "Premium Estate Sales Ltd",
                "tax_number": "BN123456789"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.business_auth_token = data["access_token"]
                    self.business_user_id = data["user"]["id"]
                    print(f"✅ Business user registered successfully: {self.business_user_id}")
                    return True
                elif response.status == 400:
                    # User might already exist, try login
                    return await self.login_business_user()
                else:
                    print(f"❌ Failed to register business user: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error registering business user: {str(e)}")
            return False
            
    async def login_business_user(self) -> bool:
        """Login with business user credentials"""
        try:
            login_data = {
                "email": TEST_BUSINESS_EMAIL,
                "password": TEST_PASSWORD
            }
            
            async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.business_auth_token = data["access_token"]
                    self.business_user_id = data["user"]["id"]
                    print(f"✅ Business user logged in successfully: {self.business_user_id}")
                    return True
                else:
                    print(f"❌ Failed to login business user: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in business user: {str(e)}")
            return False
            
    async def register_personal_user(self) -> bool:
        """Register a personal test user for negative testing"""
        try:
            user_data = {
                "email": TEST_PERSONAL_EMAIL,
                "password": TEST_PASSWORD,
                "name": "Personal User",
                "account_type": "personal",
                "phone": "+1987654321",
                "address": "123 Personal St, Individual City"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.personal_auth_token = data["access_token"]
                    self.personal_user_id = data["user"]["id"]
                    print(f"✅ Personal user registered successfully: {self.personal_user_id}")
                    return True
                elif response.status == 400:
                    # User might already exist, try login
                    return await self.login_personal_user()
                else:
                    print(f"❌ Failed to register personal user: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error registering personal user: {str(e)}")
            return False
            
    async def login_personal_user(self) -> bool:
        """Login with personal user credentials"""
        try:
            login_data = {
                "email": TEST_PERSONAL_EMAIL,
                "password": TEST_PASSWORD
            }
            
            async with self.session.post(f"{BASE_URL}/auth/login", json=login_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.personal_auth_token = data["access_token"]
                    self.personal_user_id = data["user"]["id"]
                    print(f"✅ Personal user logged in successfully: {self.personal_user_id}")
                    return True
                else:
                    print(f"❌ Failed to login personal user: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in personal user: {str(e)}")
            return False
            
    def get_business_auth_headers(self) -> Dict[str, str]:
        """Get business user authorization headers"""
        return {"Authorization": f"Bearer {self.business_auth_token}"}
        
    def get_personal_auth_headers(self) -> Dict[str, str]:
        """Get personal user authorization headers"""
        return {"Authorization": f"Bearer {self.personal_auth_token}"}
        
    def create_sample_lots(self, count: int = 1) -> List[Dict[str, Any]]:
        """Create sample lots for testing"""
        lots = []
        for i in range(count):
            lot = {
                "lot_number": i + 1,
                "title": f"Antique Mahogany Dining Chair #{i + 1}",
                "description": f"Beautiful hand-carved mahogany dining chair from the Victorian era. Excellent craftsmanship with intricate details and original upholstery. Perfect for collectors or dining room restoration projects. Chair #{i + 1} in a set.",
                "quantity": 1,
                "starting_price": 150.0 + (i * 25),
                "current_price": 150.0 + (i * 25),
                "condition": "good",
                "images": [
                    f"https://example.com/chair{i+1}_front.jpg",
                    f"https://example.com/chair{i+1}_back.jpg"
                ]
            }
            lots.append(lot)
        return lots
        
    async def test_create_minimal_listing(self) -> bool:
        """Test POST /api/multi-item-listings with minimal 1 lot"""
        print("\n🧪 Testing POST /api/multi-item-listings (minimal 1 lot)...")
        
        try:
            listing_data = {
                "title": "Estate Sale - Victorian Dining Set",
                "description": "Complete Victorian dining room furniture from a prestigious estate. All pieces are authentic antiques in excellent condition.",
                "category": "Furniture",
                "location": "Westmount Estate",
                "city": "Montreal",
                "region": "Quebec",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "lots": self.create_sample_lots(1)
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_business_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "id" in data
                    assert "seller_id" in data
                    assert data["seller_id"] == self.business_user_id
                    assert data["title"] == listing_data["title"]
                    assert data["total_lots"] == 1
                    assert len(data["lots"]) == 1
                    assert data["status"] == "active"
                    
                    self.created_listing_ids.append(data["id"])
                    print(f"✅ Minimal listing created successfully: {data['id']}")
                    print(f"   - Title: {data['title']}")
                    print(f"   - Total lots: {data['total_lots']}")
                    return True
                else:
                    print(f"❌ Failed to create minimal listing: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing minimal listing creation: {str(e)}")
            return False
            
    async def test_create_bulk_listing(self) -> bool:
        """Test POST /api/multi-item-listings with 10 lots (CSV scenario)"""
        print("\n🧪 Testing POST /api/multi-item-listings (10 lots from CSV)...")
        
        try:
            # Create 10 lots with varied data
            lots = []
            furniture_items = [
                ("Mahogany Dining Table", "Stunning oval mahogany dining table seats 8 people comfortably", 850.0),
                ("China Cabinet", "Glass-front china cabinet with original hardware and shelving", 650.0),
                ("Sideboard Buffet", "Matching sideboard with marble top and storage compartments", 750.0),
                ("Dining Chair Set", "Set of 6 matching dining chairs with original upholstery", 450.0),
                ("Crystal Chandelier", "Waterford crystal chandelier with 12 lights, fully restored", 1200.0),
                ("Persian Area Rug", "Hand-woven Persian rug 9x12 feet, excellent condition", 2200.0),
                ("Silver Tea Service", "Complete sterling silver tea service, 8 pieces, hallmarked", 950.0),
                ("Oil Painting", "Original oil painting landscape by listed artist, framed", 1800.0),
                ("Grandfather Clock", "Working grandfather clock with Westminster chimes", 3200.0),
                ("Jewelry Box", "Antique jewelry box with multiple compartments and mirror", 275.0)
            ]
            
            for i, (title, desc, price) in enumerate(furniture_items):
                lot = {
                    "lot_number": i + 1,
                    "title": title,
                    "description": desc,
                    "quantity": 1,
                    "starting_price": price,
                    "current_price": price,
                    "condition": "excellent" if price > 1000 else "good",
                    "images": [
                        f"https://example.com/lot{i+1}_main.jpg",
                        f"https://example.com/lot{i+1}_detail.jpg"
                    ]
                }
                lots.append(lot)
            
            listing_data = {
                "title": "Complete Estate Liquidation - Luxury Home Contents",
                "description": "Entire contents of a luxury estate home. All items are authentic antiques and high-quality pieces. Perfect opportunity for dealers and collectors.",
                "category": "Antiques",
                "location": "Rosedale Mansion",
                "city": "Toronto",
                "region": "Ontario",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
                "lots": lots
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_business_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "id" in data
                    assert data["total_lots"] == 10
                    assert len(data["lots"]) == 10
                    
                    # Verify lot details
                    for i, lot in enumerate(data["lots"]):
                        assert lot["lot_number"] == i + 1
                        assert "title" in lot
                        assert "starting_price" in lot
                        assert "current_price" in lot
                    
                    self.created_listing_ids.append(data["id"])
                    print(f"✅ Bulk listing created successfully: {data['id']}")
                    print(f"   - Total lots: {data['total_lots']}")
                    print(f"   - Price range: ${min(lot['starting_price'] for lot in lots):.0f} - ${max(lot['starting_price'] for lot in lots):.0f}")
                    return True
                else:
                    print(f"❌ Failed to create bulk listing: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing bulk listing creation: {str(e)}")
            return False
            
    async def test_validation_edge_cases(self) -> bool:
        """Test validation edge cases for lot data"""
        print("\n🧪 Testing validation edge cases...")
        
        success = True
        
        # Test 1: Minimum starting price (1 CAD)
        try:
            lots = [{
                "lot_number": 1,
                "title": "Small Collectible Item",
                "description": "This is exactly twenty characters long for minimum test",
                "quantity": 1,
                "starting_price": 1.0,
                "current_price": 1.0,
                "condition": "fair",
                "images": ["https://example.com/min_price.jpg"]
            }]
            
            listing_data = {
                "title": "Minimum Price Test Listing",
                "description": "Testing minimum validation rules",
                "category": "Collectibles",
                "location": "Test Location",
                "city": "Test City",
                "region": "Test Region",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
                "lots": lots
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_business_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.created_listing_ids.append(data["id"])
                    print("✅ Minimum price validation passed (1 CAD)")
                else:
                    print(f"❌ Minimum price validation failed: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing minimum price: {str(e)}")
            success = False
            
        # Test 2: Maximum starting price (10,000 CAD)
        try:
            lots = [{
                "lot_number": 1,
                "title": "Luxury High-Value Item",
                "description": "This description is exactly twenty characters long and tests the minimum length requirement for lot descriptions in our validation system.",
                "quantity": 1,
                "starting_price": 10000.0,
                "current_price": 10000.0,
                "condition": "excellent",
                "images": ["https://example.com/max_price.jpg"]
            }]
            
            listing_data = {
                "title": "Maximum Price Test Listing",
                "description": "Testing maximum validation rules",
                "category": "Luxury",
                "location": "Test Location",
                "city": "Test City", 
                "region": "Test Region",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
                "lots": lots
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_business_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.created_listing_ids.append(data["id"])
                    print("✅ Maximum price validation passed (10,000 CAD)")
                else:
                    print(f"❌ Maximum price validation failed: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing maximum price: {str(e)}")
            success = False
            
        # Test 3: Various quantities
        try:
            lots = [
                {
                    "lot_number": 1,
                    "title": "Single Item Test",
                    "description": "Testing quantity of exactly one item for validation purposes",
                    "quantity": 1,
                    "starting_price": 100.0,
                    "current_price": 100.0,
                    "condition": "good",
                    "images": ["https://example.com/qty1.jpg"]
                },
                {
                    "lot_number": 2,
                    "title": "Medium Quantity Test",
                    "description": "Testing medium quantity of fifty items for bulk validation",
                    "quantity": 50,
                    "starting_price": 200.0,
                    "current_price": 200.0,
                    "condition": "good",
                    "images": ["https://example.com/qty50.jpg"]
                },
                {
                    "lot_number": 3,
                    "title": "Large Quantity Test",
                    "description": "Testing large quantity of one hundred items for maximum validation",
                    "quantity": 100,
                    "starting_price": 300.0,
                    "current_price": 300.0,
                    "condition": "good",
                    "images": ["https://example.com/qty100.jpg"]
                }
            ]
            
            listing_data = {
                "title": "Quantity Validation Test Listing",
                "description": "Testing various quantity validation rules",
                "category": "Mixed",
                "location": "Test Location",
                "city": "Test City",
                "region": "Test Region", 
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
                "lots": lots
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_business_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.created_listing_ids.append(data["id"])
                    print("✅ Quantity validation passed (1, 50, 100)")
                else:
                    print(f"❌ Quantity validation failed: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing quantities: {str(e)}")
            success = False
            
        return success
        
    async def test_authentication_requirements(self) -> bool:
        """Test authentication and authorization requirements"""
        print("\n🧪 Testing authentication and authorization...")
        
        success = True
        
        # Test 1: Unauthenticated request
        try:
            listing_data = {
                "title": "Unauthorized Test",
                "description": "This should fail",
                "category": "Test",
                "location": "Test",
                "city": "Test",
                "region": "Test",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                "lots": self.create_sample_lots(1)
            }
            
            async with self.session.post(f"{BASE_URL}/multi-item-listings", json=listing_data) as response:
                if response.status == 401:
                    print("✅ Correctly rejected unauthenticated request (401)")
                else:
                    print(f"❌ Should have rejected unauthenticated request, got: {response.status}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing unauthenticated request: {str(e)}")
            success = False
            
        # Test 2: Personal account (should be rejected)
        try:
            listing_data = {
                "title": "Personal Account Test",
                "description": "This should fail for personal accounts",
                "category": "Test",
                "location": "Test",
                "city": "Test",
                "region": "Test",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                "lots": self.create_sample_lots(1)
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_personal_auth_headers()
            ) as response:
                if response.status == 403:
                    print("✅ Correctly rejected personal account (403)")
                else:
                    print(f"❌ Should have rejected personal account, got: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    success = False
        except Exception as e:
            print(f"❌ Error testing personal account rejection: {str(e)}")
            success = False
            
        return success
        
    async def test_get_all_listings(self) -> bool:
        """Test GET /api/multi-item-listings"""
        print("\n🧪 Testing GET /api/multi-item-listings...")
        
        try:
            async with self.session.get(f"{BASE_URL}/multi-item-listings") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response is a list
                    assert isinstance(data, list), "Response should be a list"
                    
                    # Should contain our created listings
                    found_listings = 0
                    for listing in data:
                        if listing["id"] in self.created_listing_ids:
                            found_listings += 1
                            
                            # Verify listing structure
                            assert "id" in listing
                            assert "title" in listing
                            assert "description" in listing
                            assert "total_lots" in listing
                            assert "status" in listing
                            assert "created_at" in listing
                            assert "auction_end_date" in listing
                    
                    print(f"✅ Retrieved all listings successfully")
                    print(f"   - Total listings: {len(data)}")
                    print(f"   - Our test listings found: {found_listings}/{len(self.created_listing_ids)}")
                    return True
                else:
                    print(f"❌ Failed to get all listings: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing get all listings: {str(e)}")
            return False
            
    async def test_get_specific_listing(self) -> bool:
        """Test GET /api/multi-item-listings/{listing_id}"""
        print("\n🧪 Testing GET /api/multi-item-listings/{listing_id}...")
        
        if not self.created_listing_ids:
            print("❌ No listings available for testing")
            return False
            
        try:
            listing_id = self.created_listing_ids[0]
            
            async with self.session.get(f"{BASE_URL}/multi-item-listings/{listing_id}") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify detailed listing structure
                    assert data["id"] == listing_id
                    assert "seller_id" in data
                    assert "title" in data
                    assert "description" in data
                    assert "category" in data
                    assert "location" in data
                    assert "city" in data
                    assert "region" in data
                    assert "auction_end_date" in data
                    assert "lots" in data
                    assert "total_lots" in data
                    assert "status" in data
                    assert "created_at" in data
                    
                    # Verify lots structure
                    assert isinstance(data["lots"], list)
                    assert len(data["lots"]) == data["total_lots"]
                    
                    for lot in data["lots"]:
                        assert "lot_number" in lot
                        assert "title" in lot
                        assert "description" in lot
                        assert "quantity" in lot
                        assert "starting_price" in lot
                        assert "current_price" in lot
                        assert "condition" in lot
                        assert "images" in lot
                    
                    print(f"✅ Retrieved specific listing successfully: {listing_id}")
                    print(f"   - Title: {data['title']}")
                    print(f"   - Total lots: {data['total_lots']}")
                    print(f"   - Status: {data['status']}")
                    return True
                else:
                    print(f"❌ Failed to get specific listing: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing get specific listing: {str(e)}")
            return False
            
    async def test_nonexistent_listing(self) -> bool:
        """Test GET /api/multi-item-listings/{listing_id} with non-existent ID"""
        print("\n🧪 Testing GET /api/multi-item-listings/{listing_id} (non-existent)...")
        
        try:
            fake_id = "non-existent-listing-id-12345"
            
            async with self.session.get(f"{BASE_URL}/multi-item-listings/{fake_id}") as response:
                if response.status == 404:
                    print("✅ Correctly returned 404 for non-existent listing")
                    return True
                else:
                    print(f"❌ Should have returned 404, got: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error testing non-existent listing: {str(e)}")
            return False
            
    async def run_all_tests(self):
        """Run all multi-item listing API tests"""
        print("🚀 Starting Multi-Item Listings API Tests")
        print("=" * 60)
        
        await self.setup_session()
        
        try:
            # Setup test users
            if not await self.register_business_user():
                print("❌ Failed to setup business user")
                return False
                
            if not await self.register_personal_user():
                print("❌ Failed to setup personal user")
                return False
            
            # Run tests in logical order
            tests = [
                ("Authentication & Authorization", self.test_authentication_requirements),
                ("Create Minimal Listing (1 lot)", self.test_create_minimal_listing),
                ("Create Bulk Listing (10 lots)", self.test_create_bulk_listing),
                ("Validation Edge Cases", self.test_validation_edge_cases),
                ("Get All Listings", self.test_get_all_listings),
                ("Get Specific Listing", self.test_get_specific_listing),
                ("Get Non-existent Listing", self.test_nonexistent_listing)
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
            print("\n" + "=" * 60)
            print("📊 MULTI-ITEM LISTINGS API TEST RESULTS")
            print("=" * 60)
            
            passed = 0
            total = len(results)
            
            for test_name, result in results:
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{status} - {test_name}")
                if result:
                    passed += 1
            
            print(f"\nOverall: {passed}/{total} tests passed")
            print(f"Created listings: {len(self.created_listing_ids)}")
            
            if passed == total:
                print("🎉 All multi-item listings API tests PASSED!")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = MultiItemListingTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)