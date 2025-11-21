"""
Production Template Verification Test

This script tests all 7 SendGrid template categories with real email sending.
Use this to verify templates are configured correctly in production.
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add backend to path
sys.path.insert(0, '/app/backend')

from services.email_service import get_email_service
from config.email_templates import EmailTemplates, EmailDataBuilder

# ANSI color codes
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*70}")
    print(f"{text}")
    print(f"{'='*70}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")

async def test_authentication_template(email_service, test_email):
    """Test Authentication category template (Welcome, Password Reset, etc.)"""
    print_header("Testing Authentication Template (d-e0ee403fbd8646db8011339cf2eeac30)")
    
    try:
        result = await email_service.send_email(
            to=test_email,
            template_id=EmailTemplates.WELCOME,
            dynamic_data={
                'first_name': 'Test',
                'full_name': 'Test User',
                'email': test_email,
                'login_url': 'https://bidvex.com/auth',
                'explore_url': 'https://bidvex.com/marketplace',
                'account_type': 'Personal'
            },
            language='en'
        )
        
        if result['success']:
            print_success(f"Welcome email sent successfully")
            print_info(f"Message ID: {result['message_id']}")
            print_info(f"Status Code: {result['status_code']}")
            return True
        else:
            print_error(f"Failed: {result['error']}")
            return False
    except Exception as e:
        print_error(f"Exception: {str(e)}")
        return False

async def test_bidding_template(email_service, test_email):
    """Test Bidding category template (Bid Placed, Outbid, Won, Lost)"""
    print_header("Testing Bidding Template (d-13806757fbd24818b24bc520074ea979)")
    
    try:
        result = await email_service.send_email(
            to=test_email,
            template_id=EmailTemplates.BID_PLACED,
            dynamic_data={
                'first_name': 'Test',
                'listing_title': 'Vintage Watch',
                'listing_url': 'https://bidvex.com/listing/123',
                'bid_amount': '150.00',
                'currency': 'CAD',
                'listing_image': 'https://images.unsplash.com/photo-1523170335258-f5ed11844a49',
                'auction_end_date': '2025-12-31',
                'current_high_bid': '150.00'
            },
            language='en'
        )
        
        if result['success']:
            print_success(f"Bid confirmation sent successfully")
            print_info(f"Message ID: {result['message_id']}")
            print_info(f"Status Code: {result['status_code']}")
            return True
        else:
            print_error(f"Failed: {result['error']}")
            return False
    except Exception as e:
        print_error(f"Exception: {str(e)}")
        return False

async def test_auction_updates_template(email_service, test_email):
    """Test Auction Updates category template (Ending Soon, Started, Cancelled)"""
    print_header("Testing Auction Updates Template (d-f22625d31ef74262887e3a8f96934bc1)")
    
    try:
        result = await email_service.send_email(
            to=test_email,
            template_id=EmailTemplates.AUCTION_ENDING_SOON,
            dynamic_data={
                'first_name': 'Test',
                'auction_title': 'Estate Sale Collection',
                'auction_url': 'https://bidvex.com/auction/456',
                'end_time': '2025-11-22 15:00:00',
                'current_bid': '250.00',
                'currency': 'CAD'
            },
            language='en'
        )
        
        if result['success']:
            print_success(f"Auction ending notification sent successfully")
            print_info(f"Message ID: {result['message_id']}")
            print_info(f"Status Code: {result['status_code']}")
            return True
        else:
            print_error(f"Failed: {result['error']}")
            return False
    except Exception as e:
        print_error(f"Exception: {str(e)}")
        return False

async def test_seller_notifications_template(email_service, test_email):
    """Test Seller Notifications category template (New Bid, Approved, Sold)"""
    print_header("Testing Seller Notifications Template (d-794b529ec05e407da60b26113e0c4ea1)")
    
    try:
        result = await email_service.send_email(
            to=test_email,
            template_id=EmailTemplates.NEW_BID_RECEIVED,
            dynamic_data={
                'first_name': 'Test',
                'listing_title': 'Antique Vase',
                'listing_url': 'https://bidvex.com/listing/789',
                'bid_amount': '300.00',
                'currency': 'CAD',
                'bidder_name': 'John Doe',
                'total_bids': '5'
            },
            language='en'
        )
        
        if result['success']:
            print_success(f"Seller notification sent successfully")
            print_info(f"Message ID: {result['message_id']}")
            print_info(f"Status Code: {result['status_code']}")
            return True
        else:
            print_error(f"Failed: {result['error']}")
            return False
    except Exception as e:
        print_error(f"Exception: {str(e)}")
        return False

async def test_financial_template(email_service, test_email):
    """Test Financial category template (Invoice, Payment, Refund)"""
    print_header("Testing Financial Template (d-a8cb13c061e3449394e900b406e9a391)")
    
    try:
        result = await email_service.send_email(
            to=test_email,
            template_id=EmailTemplates.INVOICE,
            dynamic_data={
                'first_name': 'Test',
                'invoice_number': 'BV-2025-001',
                'invoice_date': '2025-11-21',
                'total_amount': '450.00',
                'currency': 'CAD',
                'items': [
                    {'name': 'Vintage Watch', 'amount': '150.00'},
                    {'name': 'Antique Vase', 'amount': '300.00'}
                ],
                'subtotal': '450.00',
                'tax': '67.49',
                'shipping': '0.00',
                'invoice_pdf_url': 'https://bidvex.com/invoices/001.pdf',
                'payment_method': 'Credit Card'
            },
            language='en'
        )
        
        if result['success']:
            print_success(f"Invoice email sent successfully")
            print_info(f"Message ID: {result['message_id']}")
            print_info(f"Status Code: {result['status_code']}")
            return True
        else:
            print_error(f"Failed: {result['error']}")
            return False
    except Exception as e:
        print_error(f"Exception: {str(e)}")
        return False

async def test_communication_template(email_service, test_email):
    """Test Communication category template (New Message)"""
    print_header("Testing Communication Template (d-3153ed45d6764d0687e69c85ffddcb10)")
    
    try:
        result = await email_service.send_email(
            to=test_email,
            template_id=EmailTemplates.NEW_MESSAGE,
            dynamic_data={
                'first_name': 'Test',
                'sender_name': 'Jane Smith',
                'message_preview': 'Hello! I have a question about the vintage watch you listed...',
                'messages_url': 'https://bidvex.com/messages',
                'sender_profile_url': 'https://bidvex.com/seller/123'
            },
            language='en'
        )
        
        if result['success']:
            print_success(f"Message notification sent successfully")
            print_info(f"Message ID: {result['message_id']}")
            print_info(f"Status Code: {result['status_code']}")
            return True
        else:
            print_error(f"Failed: {result['error']}")
            return False
    except Exception as e:
        print_error(f"Exception: {str(e)}")
        return False

async def test_admin_template(email_service, test_email):
    """Test Admin category template (Report Received, Account Suspended)"""
    print_header("Testing Admin Template (d-94d4a5d7855b4fa38badae9cf12ded41)")
    
    try:
        result = await email_service.send_email(
            to=test_email,
            template_id=EmailTemplates.REPORT_RECEIVED,
            dynamic_data={
                'first_name': 'Admin',
                'report_type': 'Spam',
                'reported_item': 'Listing #456',
                'reporter_name': 'John Doe',
                'report_reason': 'This listing appears to be spam',
                'admin_url': 'https://bidvex.com/admin/reports/123'
            },
            language='en'
        )
        
        if result['success']:
            print_success(f"Admin notification sent successfully")
            print_info(f"Message ID: {result['message_id']}")
            print_info(f"Status Code: {result['status_code']}")
            return True
        else:
            print_error(f"Failed: {result['error']}")
            return False
    except Exception as e:
        print_error(f"Exception: {str(e)}")
        return False

async def run_all_tests():
    """Run all template tests"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║       BidVex Production Templates Verification Test Suite         ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print(Colors.END)
    
    print_info(f"Test started at: {datetime.now().isoformat()}")
    
    # Get email service
    email_service = get_email_service()
    
    if not email_service.is_configured():
        print_error("SendGrid not configured! Check .env file.")
        return False
    
    print_success("SendGrid API key detected")
    print_info(f"From: {email_service.from_name} <{email_service.from_email}>")
    
    # Get test email from user
    test_email = input(f"\n{Colors.YELLOW}Enter your email address to receive test emails: {Colors.END}")
    
    if not test_email or '@' not in test_email:
        print_error("Invalid email address")
        return False
    
    print_info(f"Sending test emails to: {test_email}")
    print_info("Check your inbox for 7 emails (one per template category)")
    
    # Run tests
    results = {}
    
    tests = [
        ("Authentication", test_authentication_template),
        ("Bidding", test_bidding_template),
        ("Auction Updates", test_auction_updates_template),
        ("Seller Notifications", test_seller_notifications_template),
        ("Financial", test_financial_template),
        ("Communication", test_communication_template),
        ("Admin", test_admin_template)
    ]
    
    for test_name, test_func in tests:
        try:
            results[test_name] = await test_func(email_service, test_email)
        except Exception as e:
            print_error(f"Test '{test_name}' crashed: {str(e)}")
            results[test_name] = False
        
        # Brief pause between sends
        await asyncio.sleep(1)
    
    # Print summary
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║                         TEST SUMMARY                               ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print(Colors.END)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = f"{Colors.GREEN}✅ PASSED{Colors.END}" if passed_test else f"{Colors.RED}❌ FAILED{Colors.END}"
        print(f"{test_name:.<50} {status}")
    
    print(f"\n{Colors.BOLD}Total: {passed}/{total} templates tested successfully{Colors.END}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL TEMPLATES WORKING! 🎉{Colors.END}")
        print_info(f"Check {test_email} for {total} test emails")
    else:
        print(f"\n{Colors.YELLOW}⚠️  Some templates failed. Check SendGrid dashboard.{Colors.END}")
    
    print_info("\nNext steps:")
    print_info("  1. Check your inbox for test emails")
    print_info("  2. Verify template formatting and variables")
    print_info("  3. Test EN/FR language versions")
    print_info("  4. Configure SendGrid webhook")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
