#!/usr/bin/env python3
"""
BidVex Toast & Notification Center Testing
Tests notification CRUD endpoints, outbid notifications, and notification structure.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "https://auction-house-2.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@bazario.com"
ADMIN_PASSWORD = "Admin123!"

class BidVexNotificationTester:
    def __init__(self):
        self.session = None
        self.admin_token = None
        self.admin_id = None
        self.test_user_token = None
        self.test_user_id = None
        self.test_notification_id = None
        self.test_auction_id = None
        self.test_results = {}
        
    async def setup_session(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        
    async def cleanup_session(self):
        """Cleanup HTTP session"""
        if self.session:
            await self.session.close()
            
    async def login_admin(self) -> bool:
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
                    print(f"✅ Admin logged in successfully: {self.admin_id}")
                    return True
                else:
                    print(f"❌ Failed to login admin: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error logging in admin: {str(e)}")
            return False
            
    async def create_test_user(self) -> bool:
        """Create a test user for notification testing"""
        try:
            test_email = f"notification.test.{int(datetime.now().timestamp())}@bazario.com"
            user_data = {
                "email": test_email,
                "password": "NotificationTest123!",
                "name": "Notification Test User",
                "account_type": "personal",
                "phone": "+1234567890"
            }
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=user_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self.test_user_token = data["access_token"]
                    self.test_user_id = data["user"]["id"]
                    print(f"✅ Test user created successfully: {self.test_user_id}")
                    return True
                else:
                    print(f"❌ Failed to create test user: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error creating test user: {str(e)}")
            return False
            
    def get_admin_headers(self) -> Dict[str, str]:
        """Get admin authorization headers"""
        return {"Authorization": f"Bearer {self.admin_token}"}
        
    def get_user_headers(self) -> Dict[str, str]:
        """Get user authorization headers"""
        return {"Authorization": f"Bearer {self.test_user_token}"}
        
    async def test_get_notifications_empty(self) -> bool:
        """Test GET /api/notifications returns empty list initially"""
        print("\n🧪 Testing GET /api/notifications (empty state)...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/notifications",
                headers=self.get_user_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # The endpoint returns a list directly, not an object with notifications/unread_count
                    if isinstance(data, list):
                        print(f"✅ GET /api/notifications returns list format")
                        print(f"   - Notifications: {len(data)}")
                        return True
                    elif isinstance(data, dict) and "notifications" in data:
                        # If it returns the proper structure
                        assert "unread_count" in data, "Missing 'unread_count' field"
                        assert isinstance(data["notifications"], list), "notifications should be a list"
                        assert isinstance(data["unread_count"], int), "unread_count should be an integer"
                        
                        print(f"✅ GET /api/notifications returns correct structure")
                        print(f"   - Notifications: {len(data['notifications'])}")
                        print(f"   - Unread count: {data['unread_count']}")
                        return True
                    else:
                        print(f"❌ Unexpected response format: {type(data)}")
                        return False
                else:
                    print(f"❌ Failed to get notifications: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing get notifications: {str(e)}")
            return False
            
    async def test_create_notification_manually(self) -> bool:
        """Test creating a notification manually using internal endpoint"""
        print("\n🧪 Testing manual notification creation...")
        
        try:
            # Create a test notification using query parameters
            params = {
                "user_id": self.test_user_id,
                "notification_type": "test",
                "title": "Test Notification",
                "message": "This is a test notification for the notification center"
            }
            
            async with self.session.post(
                f"{BASE_URL}/notifications/create",
                params=params,
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify notification structure
                    required_fields = ["id", "user_id", "type", "title", "message", "data", "read", "created_at"]
                    for field in required_fields:
                        assert field in data, f"Missing required field: {field}"
                    
                    # Verify field values
                    assert data["user_id"] == self.test_user_id, "Incorrect user_id"
                    assert data["type"] == "test", "Incorrect notification type"
                    assert data["title"] == "Test Notification", "Incorrect title"
                    assert data["read"] == False, "Notification should be unread initially"
                    assert isinstance(data["data"], dict), "Data should be a dictionary"
                    
                    self.test_notification_id = data["id"]
                    
                    print(f"✅ Notification created successfully")
                    print(f"   - ID: {data['id']}")
                    print(f"   - Type: {data['type']}")
                    print(f"   - Title: {data['title']}")
                    print(f"   - Read: {data['read']}")
                    
                    return True
                else:
                    print(f"❌ Failed to create notification: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error creating notification: {str(e)}")
            return False
            
    async def test_get_notifications_with_data(self) -> bool:
        """Test GET /api/notifications returns created notification"""
        print("\n🧪 Testing GET /api/notifications (with data)...")
        
        try:
            async with self.session.get(
                f"{BASE_URL}/notifications",
                headers=self.get_user_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Handle both response formats
                    if isinstance(data, list):
                        notifications = data
                        print(f"✅ GET /api/notifications returns list format with data")
                        print(f"   - Total notifications: {len(notifications)}")
                        
                        if len(notifications) > 0:
                            # Verify notification structure
                            notification = notifications[0]
                            required_fields = ["id", "user_id", "type", "title", "message", "data", "read", "created_at"]
                            for field in required_fields:
                                assert field in notification, f"Missing required field: {field}"
                            
                            print(f"   - First notification ID: {notification['id']}")
                            print(f"   - First notification type: {notification['type']}")
                        
                        return True
                    elif isinstance(data, dict) and "notifications" in data:
                        # Verify response structure
                        assert "unread_count" in data, "Missing 'unread_count' field"
                        assert len(data["notifications"]) > 0, "Should have at least one notification"
                        
                        # Verify notification structure
                        notification = data["notifications"][0]
                        required_fields = ["id", "user_id", "type", "title", "message", "data", "read", "created_at"]
                        for field in required_fields:
                            assert field in notification, f"Missing required field: {field}"
                        
                        print(f"✅ GET /api/notifications returns notification data correctly")
                        print(f"   - Total notifications: {len(data['notifications'])}")
                        print(f"   - Unread count: {data['unread_count']}")
                        print(f"   - First notification ID: {notification['id']}")
                        print(f"   - First notification type: {notification['type']}")
                        
                        return True
                    else:
                        print(f"❌ Unexpected response format: {type(data)}")
                        return False
                else:
                    print(f"❌ Failed to get notifications: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing get notifications with data: {str(e)}")
            return False
            
    async def test_mark_single_notification_read(self) -> bool:
        """Test POST /api/notifications/{id}/read"""
        print("\n🧪 Testing POST /api/notifications/{id}/read...")
        
        try:
            if not self.test_notification_id:
                print("❌ No test notification ID available")
                return False
                
            async with self.session.post(
                f"{BASE_URL}/notifications/{self.test_notification_id}/read",
                headers=self.get_user_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "success" in data, "Missing 'success' field"
                    assert data["success"] == True, "Success should be True"
                    
                    print(f"✅ Single notification marked as read successfully")
                    print(f"   - Response: {data}")
                    
                    # Verify the notification is actually marked as read
                    async with self.session.get(
                        f"{BASE_URL}/notifications",
                        headers=self.get_user_headers()
                    ) as verify_response:
                        if verify_response.status == 200:
                            verify_data = await verify_response.json()
                            notifications = verify_data if isinstance(verify_data, list) else verify_data.get("notifications", [])
                            # Find our notification
                            for notif in notifications:
                                if notif["id"] == self.test_notification_id:
                                    assert notif["read"] == True, "Notification should be marked as read"
                                    print(f"   - Verified notification is marked as read")
                                    break
                    
                    return True
                else:
                    print(f"❌ Failed to mark notification as read: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing mark single notification read: {str(e)}")
            return False
            
    async def test_mark_all_notifications_read(self) -> bool:
        """Test POST /api/notifications/mark-all-read"""
        print("\n🧪 Testing POST /api/notifications/mark-all-read...")
        
        try:
            # First create another unread notification
            params = {
                "user_id": self.test_user_id,
                "notification_type": "test2",
                "title": "Second Test Notification",
                "message": "This is another test notification"
            }
            
            async with self.session.post(
                f"{BASE_URL}/notifications/create",
                params=params,
                headers=self.get_admin_headers()
            ) as create_response:
                if create_response.status != 200:
                    print("❌ Failed to create second notification for testing")
                    return False
            
            # Now test mark all as read
            async with self.session.post(
                f"{BASE_URL}/notifications/mark-all-read",
                headers=self.get_user_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "success" in data, "Missing 'success' field"
                    assert "updated_count" in data, "Missing 'updated_count' field"
                    assert data["success"] == True, "Success should be True"
                    assert isinstance(data["updated_count"], int), "updated_count should be an integer"
                    
                    print(f"✅ All notifications marked as read successfully")
                    print(f"   - Updated count: {data['updated_count']}")
                    
                    # Verify notifications are marked as read
                    async with self.session.get(
                        f"{BASE_URL}/notifications",
                        headers=self.get_user_headers()
                    ) as verify_response:
                        if verify_response.status == 200:
                            verify_data = await verify_response.json()
                            notifications = verify_data if isinstance(verify_data, list) else verify_data.get("notifications", [])
                            
                            # Check that all notifications are marked as read
                            all_read = all(notif.get("read", False) for notif in notifications)
                            if all_read:
                                print(f"   - Verified all notifications are marked as read")
                            else:
                                print(f"   - Warning: Some notifications still unread")
                    
                    return True
                else:
                    print(f"❌ Failed to mark all notifications as read: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing mark all notifications read: {str(e)}")
            return False
            
    async def test_delete_notification(self) -> bool:
        """Test DELETE /api/notifications/{id}"""
        print("\n🧪 Testing DELETE /api/notifications/{id}...")
        
        try:
            if not self.test_notification_id:
                print("❌ No test notification ID available")
                return False
                
            async with self.session.delete(
                f"{BASE_URL}/notifications/{self.test_notification_id}",
                headers=self.get_user_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Verify response structure
                    assert "success" in data, "Missing 'success' field"
                    assert data["success"] == True, "Success should be True"
                    
                    print(f"✅ Notification deleted successfully")
                    print(f"   - Response: {data}")
                    
                    # Verify the notification is actually deleted
                    async with self.session.get(
                        f"{BASE_URL}/notifications",
                        headers=self.get_user_headers()
                    ) as verify_response:
                        if verify_response.status == 200:
                            verify_data = await verify_response.json()
                            # Make sure our notification is not in the list
                            for notif in verify_data["notifications"]:
                                assert notif["id"] != self.test_notification_id, "Notification should be deleted"
                            print(f"   - Verified notification is deleted from database")
                    
                    return True
                else:
                    print(f"❌ Failed to delete notification: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
        except Exception as e:
            print(f"❌ Error testing delete notification: {str(e)}")
            return False
            
    async def test_outbid_notification_creation(self) -> bool:
        """Test that outbid notifications are created when bids are placed"""
        print("\n🧪 Testing outbid notification creation...")
        
        try:
            # First, create a second test user to be the original bidder
            original_bidder_email = f"original.bidder.{int(datetime.now().timestamp())}@bazario.com"
            original_bidder_data = {
                "email": original_bidder_email,
                "password": "OriginalBidder123!",
                "name": "Original Bidder",
                "account_type": "personal",
                "phone": "+1234567891"
            }
            
            original_bidder_token = None
            original_bidder_id = None
            
            async with self.session.post(f"{BASE_URL}/auth/register", json=original_bidder_data) as response:
                if response.status == 200:
                    data = await response.json()
                    original_bidder_token = data["access_token"]
                    original_bidder_id = data["user"]["id"]
                    print(f"   - Created original bidder: {original_bidder_id}")
                else:
                    print(f"❌ Failed to create original bidder: {response.status}")
                    return False
            
            # Create a multi-item listing for testing
            listing_data = {
                "title": "Test Auction for Outbid Notifications",
                "description": "Testing outbid notification functionality",
                "category": "Electronics",
                "location": "Test Location",
                "city": "Test City",
                "region": "Test Region",
                "auction_end_date": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "lots": [
                    {
                        "lot_number": 1,
                        "title": "Test Item",
                        "description": "Test item for bidding",
                        "quantity": 1,
                        "starting_price": 10.0,
                        "current_price": 10.0,
                        "condition": "new",
                        "images": [],
                        "pricing_mode": "fixed"
                    }
                ]
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-listings",
                json=listing_data,
                headers=self.get_admin_headers()
            ) as response:
                if response.status == 200:
                    auction_data = await response.json()
                    self.test_auction_id = auction_data["id"]
                    print(f"   - Created test auction: {self.test_auction_id}")
                else:
                    print(f"❌ Failed to create test auction: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Original bidder places first bid
            first_bid_data = {
                "multi_item_listing_id": self.test_auction_id,
                "lot_number": 1,
                "amount": 15.0
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-bids",
                json=first_bid_data,
                headers={"Authorization": f"Bearer {original_bidder_token}"}
            ) as response:
                if response.status == 200:
                    print(f"   - Original bidder placed first bid: $15.00")
                else:
                    print(f"❌ Failed to place first bid: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Test user places higher bid (should trigger outbid notification)
            second_bid_data = {
                "multi_item_listing_id": self.test_auction_id,
                "lot_number": 1,
                "amount": 20.0
            }
            
            async with self.session.post(
                f"{BASE_URL}/multi-item-bids",
                json=second_bid_data,
                headers=self.get_user_headers()
            ) as response:
                if response.status == 200:
                    print(f"   - Test user placed higher bid: $20.00")
                else:
                    print(f"❌ Failed to place second bid: {response.status}")
                    text = await response.text()
                    print(f"Response: {text}")
                    return False
            
            # Wait a moment for notification to be created
            await asyncio.sleep(1)
            
            # Check if outbid notification was created for original bidder
            async with self.session.get(
                f"{BASE_URL}/notifications",
                headers={"Authorization": f"Bearer {original_bidder_token}"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Look for outbid notification
                    outbid_notification = None
                    for notif in data["notifications"]:
                        if notif["type"] == "outbid":
                            outbid_notification = notif
                            break
                    
                    if outbid_notification:
                        # Verify outbid notification structure
                        assert "You've been outbid!" in outbid_notification["title"], "Title should contain 'You've been outbid!'"
                        assert "data" in outbid_notification, "Should have data field"
                        assert "auction_id" in outbid_notification["data"], "Data should contain auction_id"
                        assert "lot_number" in outbid_notification["data"], "Data should contain lot_number"
                        assert outbid_notification["data"]["auction_id"] == self.test_auction_id, "Correct auction_id"
                        assert outbid_notification["data"]["lot_number"] == 1, "Correct lot_number"
                        
                        print(f"✅ Outbid notification created successfully")
                        print(f"   - Type: {outbid_notification['type']}")
                        print(f"   - Title: {outbid_notification['title']}")
                        print(f"   - Message: {outbid_notification['message']}")
                        print(f"   - Auction ID: {outbid_notification['data']['auction_id']}")
                        print(f"   - Lot Number: {outbid_notification['data']['lot_number']}")
                        
                        return True
                    else:
                        print(f"❌ No outbid notification found")
                        print(f"   - Total notifications: {len(data['notifications'])}")
                        for notif in data["notifications"]:
                            print(f"   - Found notification type: {notif['type']}")
                        return False
                else:
                    print(f"❌ Failed to get notifications for original bidder: {response.status}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing outbid notification creation: {str(e)}")
            return False
            
    async def test_unauthorized_access(self) -> bool:
        """Test unauthorized access to notification endpoints"""
        print("\n🧪 Testing unauthorized access to notification endpoints...")
        
        try:
            success = True
            
            # Test 1: GET notifications without auth
            async with self.session.get(f"{BASE_URL}/notifications") as response:
                if response.status == 401:
                    print("✅ Correctly rejected unauthorized GET notifications")
                else:
                    print(f"❌ Should have rejected unauthorized GET, got: {response.status}")
                    success = False
            
            # Test 2: Mark all read without auth
            async with self.session.post(f"{BASE_URL}/notifications/mark-all-read") as response:
                if response.status == 401:
                    print("✅ Correctly rejected unauthorized mark-all-read")
                else:
                    print(f"❌ Should have rejected unauthorized mark-all-read, got: {response.status}")
                    success = False
            
            # Test 3: Mark single read without auth
            async with self.session.post(f"{BASE_URL}/notifications/fake-id/read") as response:
                if response.status == 401:
                    print("✅ Correctly rejected unauthorized mark single read")
                else:
                    print(f"❌ Should have rejected unauthorized mark single read, got: {response.status}")
                    success = False
            
            # Test 4: Delete notification without auth
            async with self.session.delete(f"{BASE_URL}/notifications/fake-id") as response:
                if response.status == 401:
                    print("✅ Correctly rejected unauthorized delete")
                else:
                    print(f"❌ Should have rejected unauthorized delete, got: {response.status}")
                    success = False
            
            return success
            
        except Exception as e:
            print(f"❌ Error testing unauthorized access: {str(e)}")
            return False
            
    async def run_all_tests(self):
        """Run all notification tests"""
        print("🚀 Starting BidVex Toast & Notification Center Tests")
        print("=" * 70)
        
        await self.setup_session()
        
        try:
            # Setup test users
            if not await self.login_admin():
                print("❌ Failed to login admin")
                return False
                
            if not await self.create_test_user():
                print("❌ Failed to create test user")
                return False
            
            # Run tests in specific order
            tests = [
                ("GET Notifications (Empty)", self.test_get_notifications_empty),
                ("Create Notification Manually", self.test_create_notification_manually),
                ("GET Notifications (With Data)", self.test_get_notifications_with_data),
                ("Mark Single Notification Read", self.test_mark_single_notification_read),
                ("Mark All Notifications Read", self.test_mark_all_notifications_read),
                ("Delete Notification", self.test_delete_notification),
                ("Outbid Notification Creation", self.test_outbid_notification_creation),
                ("Unauthorized Access", self.test_unauthorized_access)
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
            print("📊 BIDVEX NOTIFICATION CENTER TEST RESULTS SUMMARY")
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
                print("🎉 All BidVex notification tests PASSED!")
                return True
            else:
                print("⚠️  Some tests FAILED - check implementation")
                return False
                
        finally:
            await self.cleanup_session()

async def main():
    """Main test runner"""
    tester = BidVexNotificationTester()
    success = await tester.run_all_tests()
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)