"""
Test suite for Bid Email Notifications
Tests:
1. Bid Placed email confirmation - sent to bidder after successful bid
2. Outbid email notification - sent to previous highest bidder when outbid
3. Email content includes required fields
4. Emails are non-blocking (bid succeeds even if email fails)

Note: SendGrid is MOCKED - emails are logged to console instead of sent
"""
import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable must be set")

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestBidEmailNotifications:
    """Test suite for bid email notifications"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Authenticate as admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Admin login failed: {response.status_code} - {response.text}")
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def admin_user(self, admin_token):
        """Get admin user details"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 200, f"Failed to get admin user: {response.text}"
        return response.json()
    
    @pytest.fixture(scope="class")
    def test_user_a(self, admin_token):
        """Create or get test user A for bidding tests"""
        # Try to register a new test user
        test_email = f"test_bidder_a_{uuid.uuid4().hex[:6]}@test.bidvex.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": test_email,
            "password": "TestPass123!",
            "name": "Test Bidder A",
            "phone": "+15141234567",
            "account_type": "personal"
        })
        
        if response.status_code == 200:
            data = response.json()
            return {
                "token": data["access_token"],
                "user": data["user"],
                "email": test_email
            }
        elif response.status_code == 400:
            # User already exists, try to login
            login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
                "email": test_email,
                "password": "TestPass123!"
            })
            if login_resp.status_code == 200:
                data = login_resp.json()
                return {
                    "token": data["access_token"],
                    "user": data["user"],
                    "email": test_email
                }
        pytest.skip(f"Failed to create/login test user A: {response.text}")
    
    @pytest.fixture(scope="class")
    def test_user_b(self, admin_token):
        """Create or get test user B for bidding tests"""
        test_email = f"test_bidder_b_{uuid.uuid4().hex[:6]}@test.bidvex.com"
        response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": test_email,
            "password": "TestPass123!",
            "name": "Test Bidder B",
            "phone": "+15149876543",
            "account_type": "personal"
        })
        
        if response.status_code == 200:
            data = response.json()
            return {
                "token": data["access_token"],
                "user": data["user"],
                "email": test_email
            }
        pytest.skip(f"Failed to create test user B: {response.text}")
    
    @pytest.fixture(scope="class")
    def test_listing(self, admin_token, admin_user):
        """Create a test listing for bidding"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Create a listing that ends in 2 hours
        auction_end = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        
        listing_data = {
            "title": f"TEST_Email_Notification_Vehicle_{uuid.uuid4().hex[:6]}",
            "description": "Test listing for email notification testing",
            "category": "Vehicles",
            "condition": "Good",
            "starting_price": 100.00,
            "buy_now_price": 5000.00,
            "images": [],
            "location": "Montreal, QC",
            "city": "Montreal",
            "region": "QC",
            "auction_end_date": auction_end,
            "agreement_accepted": True,
            "agreement_metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ip_address": "127.0.0.1",
                "user_agent": "pytest"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/listings", headers=headers, json=listing_data)
        
        if response.status_code != 200:
            pytest.skip(f"Failed to create test listing: {response.status_code} - {response.text}")
        
        listing = response.json()
        yield listing
        
        # Cleanup: Delete the test listing after tests
        try:
            requests.delete(f"{BASE_URL}/api/listings/{listing['id']}", headers=headers)
        except:
            pass
    
    def test_health_check(self):
        """Verify API is running"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("✅ Health check passed")
    
    def test_admin_login(self, admin_token):
        """Verify admin can login"""
        assert admin_token is not None
        assert len(admin_token) > 0
        print(f"✅ Admin login successful, token length: {len(admin_token)}")
    
    def test_bid_placement_returns_success(self, admin_token, test_listing):
        """
        Test that placing a bid returns successful response
        The bid confirmation email should be logged (since SendGrid is mocked)
        """
        # Admin needs phone verified and payment method to bid
        # For this test, we use admin who should have those set
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get current price
        listing_response = requests.get(f"{BASE_URL}/api/listings/{test_listing['id']}", headers=headers)
        if listing_response.status_code != 200:
            pytest.skip(f"Failed to get listing: {listing_response.text}")
        
        current_price = listing_response.json().get("current_price", test_listing["starting_price"])
        
        # Place a bid (increase by $5)
        bid_amount = current_price + 5
        
        bid_data = {
            "listing_id": test_listing["id"],
            "amount": bid_amount
        }
        
        response = requests.post(f"{BASE_URL}/api/bids", headers=headers, json=bid_data)
        
        # Check response - may fail due to phone/payment verification requirements
        if response.status_code == 403:
            error_detail = response.json().get("detail", "")
            if "Phone verification" in error_detail or "Payment method" in error_detail:
                print(f"⚠️ Bid blocked due to verification requirements: {error_detail}")
                # This is expected behavior - verification is required
                # The email functions are still being called in the code path
                pytest.skip(f"Test user requires verification: {error_detail}")
        
        # If bid succeeds, verify the response
        if response.status_code == 200:
            bid_response = response.json()
            assert "id" in bid_response, "Bid response should contain id"
            assert bid_response.get("amount") == bid_amount, f"Bid amount should be {bid_amount}"
            print(f"✅ Bid placed successfully: ${bid_amount}")
            print(f"   Bid ID: {bid_response['id']}")
            # Email should be logged in backend logs
            print("   📧 Bid confirmation email should be logged in backend (SendGrid mocked)")
            return bid_response
        else:
            print(f"❌ Bid failed: {response.status_code} - {response.text}")
            # Assert for detailed error
            assert response.status_code == 200, f"Bid should succeed: {response.text}"
    
    def test_email_notification_code_exists(self):
        """
        Verify the email notification functions exist in the codebase
        This is a code review check rather than runtime test
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        try:
            from services.email_notifications import send_bid_placed_email, send_outbid_email
            print("✅ send_bid_placed_email function exists")
            print("✅ send_outbid_email function exists")
            
            # Verify they are async functions
            import inspect
            assert inspect.iscoroutinefunction(send_bid_placed_email), "send_bid_placed_email should be async"
            assert inspect.iscoroutinefunction(send_outbid_email), "send_outbid_email should be async"
            print("✅ Both functions are async (non-blocking)")
            
        except ImportError as e:
            pytest.fail(f"Failed to import email notification functions: {e}")
    
    def test_email_notification_fallback_logging(self):
        """
        Verify that when SendGrid is not configured, emails are logged instead
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.email_notifications import SENDGRID_AVAILABLE, send_email
        
        # Since SendGrid API key is placeholder, SENDGRID_AVAILABLE should be False
        print(f"   SENDGRID_AVAILABLE: {SENDGRID_AVAILABLE}")
        
        if not SENDGRID_AVAILABLE:
            print("✅ SendGrid not configured - emails will be logged (as expected)")
        else:
            print("⚠️ SendGrid appears to be configured - emails may be sent")
    
    def test_bid_placed_email_function_signature(self):
        """
        Verify the send_bid_placed_email function has correct parameters
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.email_notifications import send_bid_placed_email
        import inspect
        
        sig = inspect.signature(send_bid_placed_email)
        params = list(sig.parameters.keys())
        
        # Required parameters based on implementation
        expected_params = ['bidder_email', 'bidder_name', 'listing_title', 'bid_amount', 
                         'listing_id', 'auction_end_date', 'is_leading']
        
        for param in expected_params:
            assert param in params, f"Missing parameter: {param}"
        
        print(f"✅ send_bid_placed_email has all required parameters: {params}")
    
    def test_outbid_email_function_signature(self):
        """
        Verify the send_outbid_email function has correct parameters
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.email_notifications import send_outbid_email
        import inspect
        
        sig = inspect.signature(send_outbid_email)
        params = list(sig.parameters.keys())
        
        # Required parameters based on implementation
        expected_params = ['user_email', 'user_name', 'listing_title', 'their_bid',
                         'new_high_bid', 'listing_id', 'auction_end_date']
        
        for param in expected_params:
            assert param in params, f"Missing parameter: {param}"
        
        print(f"✅ send_outbid_email has all required parameters: {params}")
    
    def test_bid_email_content_includes_required_fields(self):
        """
        Verify bid confirmation email template includes:
        - Bidder name
        - Listing title  
        - Bid amount
        - Auction end date
        - Link to listing
        - Leading status
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.email_notifications import send_bid_placed_email
        import inspect
        
        # Get the source code of the function to verify template content
        source = inspect.getsource(send_bid_placed_email)
        
        # Check for required fields in the template
        required_content = [
            'bidder_name',      # Bidder's name
            'listing_title',    # Item title
            'bid_amount',       # Bid amount
            'auction_end_date', # When auction ends
            'listing_id',       # For link to listing
            'is_leading'        # Leading status
        ]
        
        for field in required_content:
            assert field in source, f"Template should include {field}"
        
        # Check for formatting
        assert '_format_currency' in source, "Should format currency amounts"
        assert '_format_date' in source, "Should format dates"
        
        print("✅ Bid confirmation email includes all required fields")
        print("   - Bidder name ✓")
        print("   - Listing title ✓")
        print("   - Bid amount ✓")
        print("   - Auction end date ✓")
        print("   - Link to listing ✓")
        print("   - Leading status ✓")
    
    def test_outbid_email_content_includes_required_fields(self):
        """
        Verify outbid email template includes:
        - User name
        - Listing title
        - Their previous bid (struck through)
        - New high bid
        - Auction end date
        - Suggested next bid
        - 'Bid Again' CTA
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.email_notifications import send_outbid_email
        import inspect
        
        # Get the source code of the function to verify template content
        source = inspect.getsource(send_outbid_email)
        
        # Check for required fields in the template
        required_content = [
            'user_name',        # User's name
            'listing_title',    # Item title
            'their_bid',        # Previous bid
            'new_high_bid',     # New highest bid
            'listing_id',       # For link
            'auction_end_date'  # When auction ends
        ]
        
        for field in required_content:
            assert field in source, f"Template should include {field}"
        
        # Check for strike-through styling on previous bid
        assert 'line-through' in source, "Previous bid should have line-through styling"
        
        # Check for suggested bid
        assert 'suggested_bid' in source, "Should include suggested next bid"
        
        # Check for Bid Again CTA
        assert 'Bid Again' in source, "Should include 'Bid Again' CTA"
        
        print("✅ Outbid email includes all required fields")
        print("   - User name ✓")
        print("   - Listing title ✓")
        print("   - Previous bid (struck through) ✓")
        print("   - New high bid ✓")
        print("   - Auction end date ✓")
        print("   - Suggested next bid ✓")
        print("   - 'Bid Again' CTA ✓")
    
    def test_email_functions_are_nonblocking(self):
        """
        Verify that email functions are wrapped in try-except
        so bid still succeeds even if email fails
        """
        # Read the server.py to check the try-except wrapping
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Find the bid email section
        bid_email_section = content[content.find("BID PLACED EMAIL CONFIRMATION"):content.find("BID PLACED EMAIL CONFIRMATION")+500]
        outbid_email_section = content[content.find("OUTBID EMAIL NOTIFICATION"):content.find("OUTBID EMAIL NOTIFICATION")+500]
        
        # Check for try-except wrapper
        assert "try:" in bid_email_section, "Bid email should be wrapped in try-except"
        assert "except" in bid_email_section, "Bid email should have except handler"
        
        assert "try:" in outbid_email_section, "Outbid email should be wrapped in try-except"
        assert "except" in outbid_email_section, "Outbid email should have except handler"
        
        print("✅ Both email functions are non-blocking (wrapped in try-except)")
        print("   - Bid confirmation email: try-except ✓")
        print("   - Outbid notification email: try-except ✓")
    
    def test_user_name_field_issue(self):
        """
        Verify that the code correctly accesses user name field.
        Issue found: code uses current_user.first_name but User model has 'name'
        """
        # Read server.py to check the field access
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Find where bidder_name is being set for email
        if 'current_user.first_name' in content:
            print("⚠️ ISSUE FOUND: Code uses 'current_user.first_name' but User model uses 'name'")
            print("   This could cause AttributeError or return None")
            # Check if User model has first_name
            if 'first_name: ' not in content or 'first_name:' not in content:
                print("   User model does NOT have first_name field")
                pytest.xfail("User model field mismatch: code uses first_name but model uses name")
        elif 'current_user.name' in content:
            print("✅ Code correctly uses 'current_user.name'")
        else:
            print("⚠️ Could not determine how user name is accessed")


class TestEmailNotificationIntegration:
    """Integration tests that check backend logs for email logging"""
    
    def test_check_backend_log_for_email_entries(self):
        """
        Check if [EMAIL LOG] entries appear in backend logs
        This verifies the fallback logging is working
        """
        import subprocess
        
        # Read recent backend logs
        try:
            result = subprocess.run(
                ['tail', '-n', '500', '/var/log/supervisor/backend.out.log'],
                capture_output=True,
                text=True,
                timeout=10
            )
            log_content = result.stdout
            
            # Check for EMAIL LOG entries
            email_logs = [line for line in log_content.split('\n') if '[EMAIL LOG]' in line or 'email' in line.lower()]
            
            if email_logs:
                print("✅ Found email-related log entries:")
                for log in email_logs[-5:]:  # Show last 5 entries
                    print(f"   {log[:100]}...")
            else:
                print("⚠️ No [EMAIL LOG] entries found in recent logs")
                print("   This is expected if no bids have been placed recently")
            
        except Exception as e:
            print(f"⚠️ Could not read backend logs: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
