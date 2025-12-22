#!/usr/bin/env python3
"""
Email Template Manager Backend Testing for BidVex
Tests the database-driven Email Template Manager with bilingual support.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://auction-house-2.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@bazario.com"
ADMIN_PASSWORD = "Admin123!"

class EmailTemplateTester:
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
            
    async def setup_admin_user(self) -> bool:
        """Setup admin user for testing admin endpoints"""
        try:
            # Try to register admin user first
            admin_data = {
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "name": "Admin User",
                "account_type": "business",
                "phone": "+1234567891"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=admin_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.admin_token = data["access_token"]
                    self.admin_id = data["user"]["id"]
                    print(f"✅ Admin user registered successfully: {self.admin_id}")
                    return True
                elif response.status == 400:
                    # Admin might already exist, try login
                    return await self.login_admin_user()
                else:
                    print(f"❌ Failed to register admin: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error setting up admin user: {str(e)}")
            return False
            
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
        
    async def test_get_all_email_templates(self) -> bool:
        """Test GET /api/admin/email-templates (Admin Only)"""
        print("\n🧪 Testing GET /api/admin/email-templates...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/admin/email-templates",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    required_fields = ["categories", "total_templates", "updated_at", "updated_by"]
                    for field in required_fields:
                        assert field in data, f"Missing required field: {field}"
                    
                    # Verify categories structure
                    categories = data["categories"]
                    expected_categories = ["authentication", "financial", "bidding", "seller", "communication", "affiliate"]
                    
                    for cat in expected_categories:
                        assert cat in categories, f"Missing category: {cat}"
                        
                        # Verify category structure
                        cat_data = categories[cat]
                        assert "name" in cat_data, f"Category {cat} missing name"
                        assert "description" in cat_data, f"Category {cat} missing description"
                        assert "icon" in cat_data, f"Category {cat} missing icon"
                        assert "templates" in cat_data, f"Category {cat} missing templates"
                        assert "count" in cat_data, f"Category {cat} missing count"
                        
                        # Verify template structure
                        for template in cat_data["templates"]:
                            assert "key" in template, f"Template missing key in {cat}"
                            assert "name" in template, f"Template missing name in {cat}"
                            assert "en_id" in template, f"Template missing en_id in {cat}"
                            assert "fr_id" in template, f"Template missing fr_id in {cat}"
                    
                    total_templates = data["total_templates"]
                    print(f"✅ Successfully retrieved all email templates")
                    print(f"   - Total templates: {total_templates}")
                    print(f"   - Categories: {len(categories)}")
                    print(f"   - Updated by: {data.get('updated_by', 'N/A')}")
                    
                    # Verify we have 52+ templates as specified
                    if total_templates >= 52:
                        print(f"✅ Template count meets requirement (52+): {total_templates}")
                    else:
                        print(f"⚠️  Template count below requirement: {total_templates} < 52")
                    
                    return True
                else:
                    print(f"❌ Failed to get email templates: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing get all email templates: {str(e)}")
            return False
            
    async def test_update_email_templates(self) -> bool:
        """Test PUT /api/admin/email-templates (Admin Only)"""
        print("\n🧪 Testing PUT /api/admin/email-templates...")
        
        try:
            # Test 1: Valid template ID update
            valid_template_id = "d-12345678901234567890123456789012"  # Valid format, different from current
            update_data = {
                "templates": {
                    "bid_outbid_en": valid_template_id
                }
            }
            
            async with self.session.put(
                f"{BASE_URL}/admin/email-templates",
                json=update_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    required_fields = ["message", "updated_keys", "updated_at", "updated_by"]
                    for field in required_fields:
                        assert field in data, f"Missing required field: {field}"
                    
                    if len(data["updated_keys"]) > 0:
                        assert "bid_outbid_en" in data["updated_keys"], "Updated key not in response"
                        print(f"✅ Successfully updated template with valid ID")
                        print(f"   - Updated keys: {data['updated_keys']}")
                        print(f"   - Message: {data['message']}")
                        print(f"   - Updated by: {data['updated_by']}")
                    else:
                        print(f"ℹ️  No update needed (template already has this ID)")
                        print(f"   - Message: {data['message']}")
                        print(f"   - Updated by: {data['updated_by']}")
                    
                else:
                    print(f"❌ Failed to update template with valid ID: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Invalid template ID format (should fail with 400)
            invalid_update_data = {
                "templates": {
                    "bid_outbid_en": "invalid-template-id"
                }
            }
            
            async with self.session.put(
                f"{BASE_URL}/admin/email-templates",
                json=invalid_update_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 400:
                    data = await response.json()
                    assert "Invalid template ID format" in data["detail"], "Expected validation error message"
                    print(f"✅ Correctly rejected invalid template ID format")
                    print(f"   - Error: {data['detail']}")
                else:
                    print(f"❌ Should have rejected invalid template ID, got: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 3: Another valid format test
            another_valid_id = "d-1234567890abcdef1234567890abcdef"
            update_data_2 = {
                "templates": {
                    "auth_welcome_fr": another_valid_id
                }
            }
            
            async with self.session.put(
                f"{BASE_URL}/admin/email-templates",
                json=update_data_2,
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    print(f"✅ Successfully updated another template with valid ID")
                else:
                    print(f"❌ Failed to update second template: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing update email templates: {str(e)}")
            return False
            
    async def test_search_email_templates(self) -> bool:
        """Test GET /api/admin/email-templates/search?q={query} (Admin Only)"""
        print("\n🧪 Testing GET /api/admin/email-templates/search...")
        
        try:
            # Test 1: Search for "outbid" templates
            search_query = "outbid"
            async with self.session.get(
                f"{BASE_URL}/admin/email-templates/search?q={search_query}",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    required_fields = ["query", "count", "results"]
                    for field in required_fields:
                        assert field in data, f"Missing required field: {field}"
                    
                    assert data["query"] == search_query, "Query mismatch in response"
                    
                    # Verify results structure
                    for result in data["results"]:
                        required_result_fields = ["key", "template_id", "category", "name"]
                        for field in required_result_fields:
                            assert field in result, f"Missing field in result: {field}"
                    
                    print(f"✅ Successfully searched for '{search_query}'")
                    print(f"   - Query: {data['query']}")
                    print(f"   - Count: {data['count']}")
                    print(f"   - Results found: {len(data['results'])}")
                    
                    # Should find outbid templates
                    if data["count"] > 0:
                        print(f"✅ Found outbid templates as expected")
                        for result in data["results"][:3]:  # Show first 3
                            print(f"     - {result['key']}: {result['template_id']}")
                    else:
                        print(f"⚠️  No outbid templates found")
                else:
                    print(f"❌ Failed to search templates: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test 2: Search for specific template ID
            template_id_search = "d-89c95108533249aaa1659e258f11dd90"
            async with self.session.get(
                f"{BASE_URL}/admin/email-templates/search?q={template_id_search}",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Successfully searched by template ID")
                    print(f"   - Found {data['count']} results for ID search")
                else:
                    print(f"❌ Failed to search by template ID: {response.status}")
                    return False
            
            # Test 3: Empty search (should return all)
            async with self.session.get(
                f"{BASE_URL}/admin/email-templates/search?q=",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Empty search returned {data['count']} results")
                else:
                    print(f"❌ Failed empty search: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing search email templates: {str(e)}")
            return False
            
    async def test_get_audit_log(self) -> bool:
        """Test GET /api/admin/email-templates/audit-log (Admin Only)"""
        print("\n🧪 Testing GET /api/admin/email-templates/audit-log...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/admin/email-templates/audit-log",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Should be a list of audit entries
                    assert isinstance(data, list), "Audit log should be a list"
                    
                    print(f"✅ Successfully retrieved audit log")
                    print(f"   - Total entries: {len(data)}")
                    
                    # If we have entries, verify structure
                    if len(data) > 0:
                        entry = data[0]  # Most recent entry
                        required_fields = ["target_id", "old_value", "new_value", "admin_email", "created_at"]
                        
                        for field in required_fields:
                            assert field in entry, f"Missing field in audit entry: {field}"
                        
                        print(f"✅ Audit log entries have correct structure")
                        print(f"   - Latest change: {entry['target_id']}")
                        print(f"   - Changed by: {entry['admin_email']}")
                        print(f"   - Old value: {entry['old_value']}")
                        print(f"   - New value: {entry['new_value']}")
                    else:
                        print(f"ℹ️  No audit log entries found (expected for fresh system)")
                    
                    return True
                else:
                    print(f"❌ Failed to get audit log: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing get audit log: {str(e)}")
            return False
            
    async def test_bilingual_template_fetching(self) -> bool:
        """Test bilingual template fetching logic"""
        print("\n🧪 Testing Bilingual Template Fetching Logic...")
        
        try:
            # This tests the get_email_template_id function indirectly
            # We'll verify by checking the templates structure from the GET endpoint
            
            async with self.session.get(
                f"{BASE_URL}/admin/email-templates",
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    categories = data["categories"]
                    
                    # Check that we have both English and French templates
                    en_templates = 0
                    fr_templates = 0
                    
                    for category in categories.values():
                        for template in category["templates"]:
                            if template["en_id"]:
                                en_templates += 1
                            if template["fr_id"]:
                                fr_templates += 1
                    
                    print(f"✅ Bilingual template structure verified")
                    print(f"   - English templates: {en_templates}")
                    print(f"   - French templates: {fr_templates}")
                    
                    # Verify specific templates exist
                    auth_category = categories.get("authentication", {})
                    auth_templates = auth_category.get("templates", [])
                    
                    welcome_template = None
                    for template in auth_templates:
                        if template["key"] == "auth_welcome":
                            welcome_template = template
                            break
                    
                    if welcome_template:
                        print(f"✅ Found auth_welcome template")
                        print(f"   - English ID: {welcome_template['en_id']}")
                        print(f"   - French ID: {welcome_template['fr_id']}")
                        
                        # Verify both languages have IDs
                        if welcome_template["en_id"] and welcome_template["fr_id"]:
                            print(f"✅ Both English and French IDs present")
                        else:
                            print(f"⚠️  Missing language variant for auth_welcome")
                    else:
                        print(f"⚠️  auth_welcome template not found")
                    
                    return True
                else:
                    print(f"❌ Failed to get templates for bilingual test: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error testing bilingual template fetching: {str(e)}")
            return False
            
    async def test_template_id_validation(self) -> bool:
        """Test template ID format validation (d-[32 hex characters])"""
        print("\n🧪 Testing Template ID Format Validation...")
        
        try:
            # Test various invalid formats
            invalid_formats = [
                "invalid-id",
                "d-123",  # Too short
                "d-12345678901234567890123456789012345",  # Too long
                "d-gggggggggggggggggggggggggggggggg",  # Invalid hex
                "e-12345678901234567890123456789012",  # Wrong prefix
                "d-12345678901234567890123456789012g",  # Invalid hex at end
            ]
            
            for invalid_id in invalid_formats:
                update_data = {
                    "templates": {
                        "test_template_en": invalid_id
                    }
                }
                
                async with self.session.put(
                    f"{BASE_URL}/admin/email-templates",
                    json=update_data,
                    headers=self.get_admin_headers()
                ) as response:
                    if response.status == 400:
                        data = await response.json()
                        assert "Invalid template ID format" in data["detail"]
                        print(f"✅ Correctly rejected invalid format: {invalid_id}")
                    else:
                        print(f"❌ Should have rejected {invalid_id}, got: {response.status}")
                        return False
            
            # Test valid format
            valid_id = "d-1234567890abcdef1234567890abcdef"
            update_data = {
                "templates": {
                    "test_template_en": valid_id
                }
            }
            
            async with self.session.put(
                f"{BASE_URL}/admin/email-templates",
                json=update_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    print(f"✅ Correctly accepted valid format: {valid_id}")
                else:
                    print(f"❌ Should have accepted valid format, got: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing template ID validation: {str(e)}")
            return False
            
    async def test_unauthorized_access(self) -> bool:
        """Test that non-admin users cannot access admin endpoints"""
        print("\n🧪 Testing Unauthorized Access Protection...")
        
        try:
            # Test without any authentication
            endpoints = [
                "/admin/email-templates",
                "/admin/email-templates/search?q=test",
                "/admin/email-templates/audit-log"
            ]
            
            for endpoint in endpoints:
                async with self.session.get(f"{BASE_URL}{endpoint}") as response:
                    if response.status == 401:
                        print(f"✅ Correctly rejected unauthenticated access to {endpoint}")
                    else:
                        print(f"❌ Should have rejected unauthenticated access to {endpoint}, got: {response.status}")
                        return False
            
            # Test PUT endpoint without auth
            async with self.session.put(
                f"{BASE_URL}/admin/email-templates",
                json={"templates": {"test": "d-1234567890abcdef1234567890abcdef"}}
            ) as response:
                if response.status == 401:
                    print(f"✅ Correctly rejected unauthenticated PUT request")
                else:
                    print(f"❌ Should have rejected unauthenticated PUT, got: {response.status}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error testing unauthorized access: {str(e)}")
            return False
            
    async def run_all_tests(self):
        """Run all email template API tests"""
        print("🚀 Starting BidVex Email Template Manager Backend Tests")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Setup admin user
            if not await self.setup_admin_user():
                print("❌ Failed to setup admin user")
                return False
            
            # Run tests in specific order
            tests = [
                ("GET All Email Templates", self.test_get_all_email_templates),
                ("PUT Update Email Templates", self.test_update_email_templates),
                ("GET Search Email Templates", self.test_search_email_templates),
                ("GET Audit Log", self.test_get_audit_log),
                ("Bilingual Template Fetching", self.test_bilingual_template_fetching),
                ("Template ID Validation", self.test_template_id_validation),
                ("Unauthorized Access Protection", self.test_unauthorized_access)
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
            print("📊 EMAIL TEMPLATE MANAGER TEST RESULTS SUMMARY")
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
                print("🎉 All Email Template Manager API tests PASSED!")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = EmailTemplateTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)