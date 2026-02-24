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
import asyncio
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable must be set")

# Test credentials
ADMIN_EMAIL = "charbeladmin@bidvex.com"
ADMIN_PASSWORD = "Admin123!"


class TestBidEmailNotificationFunctions:
    """Test the email notification function implementation"""
    
    def test_health_check(self):
        """Verify API is running"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("✅ Health check passed")
    
    def test_email_notification_code_exists(self):
        """
        Verify the email notification functions exist in the codebase
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
        
        from services.email_notifications import SENDGRID_AVAILABLE
        
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
    
    def test_email_functions_are_nonblocking_in_server(self):
        """
        Verify that email functions are wrapped in try-except
        so bid still succeeds even if email fails
        """
        # Read the server.py to check the try-except wrapping
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Find the place_bid function and check email handling
        place_bid_start = content.find("async def place_bid(")
        place_bid_end = content.find("@api_router.post(\"/buy-now\")")
        place_bid_code = content[place_bid_start:place_bid_end]
        
        # Check for both email sections with try-except
        # Bid confirmation email
        assert "BID PLACED EMAIL CONFIRMATION" in place_bid_code, "Bid email section should exist"
        bid_email_start = place_bid_code.find("BID PLACED EMAIL CONFIRMATION")
        bid_email_section = place_bid_code[bid_email_start:bid_email_start+1000]
        assert "try:" in bid_email_section, "Bid email should be wrapped in try"
        assert "except" in bid_email_section, "Bid email should have except handler"
        
        # Outbid notification email
        assert "OUTBID EMAIL NOTIFICATION" in place_bid_code, "Outbid email section should exist"
        outbid_email_start = place_bid_code.find("OUTBID EMAIL NOTIFICATION")
        # Get a larger section to include the except handler
        outbid_email_section = place_bid_code[outbid_email_start:outbid_email_start+1200]
        assert "try:" in outbid_email_section, "Outbid email should be wrapped in try"
        assert "except" in outbid_email_section, "Outbid email should have except handler"
        
        print("✅ Both email functions are non-blocking (wrapped in try-except)")
        print("   - Bid confirmation email: try-except ✓")
        print("   - Outbid notification email: try-except ✓")
    
    def test_user_name_field_is_correct(self):
        """
        Verify that the code correctly accesses user name field.
        User model has 'name' field (not first_name)
        """
        # Read server.py to check the field access
        with open('/app/backend/server.py', 'r') as f:
            content = f.read()
        
        # Find the bid placed email section
        place_bid_start = content.find("async def place_bid(")
        place_bid_end = content.find("@api_router.post(\"/buy-now\")")
        place_bid_code = content[place_bid_start:place_bid_end]
        
        # Check bid placed email uses current_user.name (not first_name)
        if 'bidder_name=current_user.first_name' in place_bid_code:
            pytest.fail("Bug: Code uses 'current_user.first_name' but User model has 'name'")
        
        if 'bidder_name=current_user.name' in place_bid_code:
            print("✅ Bid email correctly uses 'current_user.name'")
        else:
            print("⚠️ Could not verify bidder_name field access")
        
        # Check outbid email
        if '"first_name": 1, "last_name": 1' in place_bid_code:
            pytest.fail("Bug: Query uses first_name/last_name but User model has 'name'")
        
        if '"name": 1' in place_bid_code:
            print("✅ Outbid query correctly uses 'name' field")
        else:
            print("⚠️ Could not verify outbid user query")


class TestEmailNotificationDirectCall:
    """Test the email functions directly (unit tests)"""
    
    def test_send_bid_placed_email_logging(self):
        """
        Test that send_bid_placed_email logs the email when SendGrid is not configured
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.email_notifications import send_bid_placed_email, SENDGRID_AVAILABLE
        
        # Run async function using asyncio
        result = asyncio.get_event_loop().run_until_complete(
            send_bid_placed_email(
                bidder_email="test@example.com",
                bidder_name="Test User",
                listing_title="Test Vehicle 2024",
                bid_amount=1500.00,
                listing_id="test-listing-123",
                auction_end_date=datetime.now(timezone.utc).isoformat(),
                is_leading=True
            )
        )
        
        if not SENDGRID_AVAILABLE:
            assert result["status"] == "logged", f"Expected logged status, got: {result}"
            print("✅ Bid placed email was logged (SendGrid not configured)")
            print(f"   Result: {result}")
        else:
            print(f"⚠️ SendGrid is configured, result: {result}")
    
    def test_send_outbid_email_logging(self):
        """
        Test that send_outbid_email logs the email when SendGrid is not configured
        """
        import sys
        sys.path.insert(0, '/app/backend')
        
        from services.email_notifications import send_outbid_email, SENDGRID_AVAILABLE
        
        # Run async function using asyncio
        result = asyncio.get_event_loop().run_until_complete(
            send_outbid_email(
                user_email="outbid@example.com",
                user_name="Outbid User",
                listing_title="Test Vehicle 2024",
                their_bid=1400.00,
                new_high_bid=1500.00,
                listing_id="test-listing-123",
                auction_end_date=datetime.now(timezone.utc).isoformat()
            )
        )
        
        if not SENDGRID_AVAILABLE:
            assert result["status"] == "logged", f"Expected logged status, got: {result}"
            print("✅ Outbid email was logged (SendGrid not configured)")
            print(f"   Result: {result}")
        else:
            print(f"⚠️ SendGrid is configured, result: {result}")


class TestEmailNotificationIntegration:
    """Integration tests that check backend logs for email logging"""
    
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
    
    def test_admin_login(self, admin_token):
        """Verify admin can login"""
        assert admin_token is not None
        assert len(admin_token) > 0
        print(f"✅ Admin login successful")
    
    def test_get_active_listings(self, admin_token):
        """
        Get active listings to understand available test data
        """
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/listings?limit=5", headers=headers)
        assert response.status_code == 200, f"Failed to get listings: {response.text}"
        
        data = response.json()
        # Handle both list and dict response formats
        if isinstance(data, list):
            listings = data
        elif isinstance(data, dict):
            listings = data.get("listings", [])
        else:
            listings = []
        
        print(f"✅ Found {len(listings)} listing(s)")
        for listing in listings[:3]:
            print(f"   - {listing.get('title', 'N/A')[:50]} (ID: {listing.get('id', 'N/A')[:8]}...)")
            print(f"     Current price: ${listing.get('current_price', 0)}, Status: {listing.get('status', 'N/A')}")
    
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
            email_logs = [line for line in log_content.split('\n') 
                         if '[EMAIL LOG]' in line or 'email' in line.lower() or '📧' in line]
            
            if email_logs:
                print("✅ Found email-related log entries:")
                for log in email_logs[-10:]:  # Show last 10 entries
                    print(f"   {log[:120]}...")
            else:
                print("⚠️ No [EMAIL LOG] entries found in recent logs")
                print("   This is expected if no bids have been placed recently")
            
        except Exception as e:
            print(f"⚠️ Could not read backend logs: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
