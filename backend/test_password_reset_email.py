#!/usr/bin/env python3
"""
Test script to validate password reset email data and send test email.
"""

import asyncio
import os
from dotenv import load_dotenv
from services.email_service import get_email_service
from config.email_templates import EmailTemplates, EmailDataBuilder, send_password_reset_email

# Load environment
load_dotenv()

async def test_password_reset_email_data():
    """Test password reset email data generation."""
    print("=" * 80)
    print("PASSWORD RESET EMAIL DATA VALIDATION TEST")
    print("=" * 80)
    print()
    
    # Sample user data
    test_user = {
        'name': 'Jean Dupont',
        'email': 'jean.dupont@example.com',
        'preferred_language': 'fr'
    }
    
    # Sample reset token
    test_token = 'sample-uuid-token-123456789'
    
    # Build email data
    email_data = EmailDataBuilder.password_reset_email(test_user, test_token)
    
    print("✅ Email Data Generated:")
    print("-" * 80)
    for key, value in email_data.items():
        print(f"  {key:.<30} {value}")
    print()
    
    # Verify required fields
    required_fields = ['first_name', 'reset_url', 'reset_link', 'expires_in_hours', 'expiry_time', 'support_email']
    print("✅ Field Validation:")
    print("-" * 80)
    
    all_present = True
    for field in required_fields:
        present = field in email_data
        status = "✅" if present else "❌"
        print(f"  {status} {field:.<30} {'Present' if present else 'MISSING'}")
        if not present:
            all_present = False
    print()
    
    if not all_present:
        print("❌ VALIDATION FAILED: Missing required fields")
        return False
    
    # Verify values are not empty
    print("✅ Value Validation:")
    print("-" * 80)
    
    all_valid = True
    for field, value in email_data.items():
        is_valid = value is not None and value != ''
        status = "✅" if is_valid else "❌"
        print(f"  {status} {field:.<30} {str(value)[:50]}")
        if not is_valid:
            all_valid = False
    print()
    
    if not all_valid:
        print("❌ VALIDATION FAILED: Empty or null values found")
        return False
    
    # Test actual email sending
    email_service = get_email_service()
    
    if not email_service.is_configured():
        print("⚠️  Email service not configured - skipping send test")
        return True
    
    print("✅ Email Service Configuration:")
    print("-" * 80)
    print(f"  From Email: {email_service.from_email}")
    print(f"  From Name: {email_service.from_name}")
    print(f"  Template ID: {EmailTemplates.PASSWORD_RESET}")
    print()
    
    # Prompt for test email
    send_test = input("Send test password reset email? (yes/no): ").strip().lower()
    
    if send_test == 'yes':
        test_email = input("Enter recipient email address: ").strip()
        
        if not test_email:
            print("❌ No email provided")
            return False
        
        print(f"\n📧 Sending test email to: {test_email}")
        print("-" * 80)
        
        try:
            # Update test user with provided email
            test_user['email'] = test_email
            
            result = await send_password_reset_email(
                email_service,
                user=test_user,
                reset_token=test_token,
                language='en'  # Test with English
            )
            
            if result['success']:
                print(f"✅ Email sent successfully!")
                print(f"  Message ID: {result.get('message_id')}")
                print(f"  Status Code: {result.get('status_code')}")
                print()
                print("📝 Check your inbox for the email")
                print("🔍 Verify:")
                print("  - Reset button has a working link")
                print("  - Expiry message is visible")
                print("  - All variables are rendered")
                print()
                
                # Send French version too
                send_french = input("Send French version too? (yes/no): ").strip().lower()
                if send_french == 'yes':
                    result_fr = await send_password_reset_email(
                        email_service,
                        user=test_user,
                        reset_token=test_token,
                        language='fr'
                    )
                    
                    if result_fr['success']:
                        print(f"✅ French email sent successfully!")
                        print(f"  Message ID: {result_fr.get('message_id')}")
                    else:
                        print(f"❌ French email failed: {result_fr.get('error')}")
                
                return True
            else:
                print(f"❌ Email sending failed: {result.get('error')}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending test email: {str(e)}")
            return False
    
    print("✅ All validations passed!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_password_reset_email_data())
    
    print()
    print("=" * 80)
    if success:
        print("✅ PASSWORD RESET EMAIL DATA VALIDATION COMPLETE")
        print()
        print("Next steps:")
        print("1. Test actual password reset flow")
        print("2. Verify email variables render correctly")
        print("3. Check SendGrid template configuration")
    else:
        print("❌ VALIDATION FAILED - Please fix issues above")
    print("=" * 80)
