"""
BidVex Email Templates Configuration

Defines all email template IDs and provides helper functions
for sending specific email types.

Note: Template IDs are from SendGrid Dynamic Templates.
Create templates in SendGrid dashboard first.
"""

from typing import Dict, Any
from datetime import datetime


class EmailTemplates:
    """
    SendGrid Dynamic Template IDs for BidVex emails.
    
    IMPORTANT: Update these IDs after creating templates in SendGrid dashboard.
    Go to: SendGrid Dashboard → Email API → Dynamic Templates
    """
    
    # User Authentication
    WELCOME = 'd-welcome-template-id'  # New user registration
    EMAIL_VERIFICATION = 'd-email-verification-id'  # Email verification
    PASSWORD_RESET = 'd-password-reset-id'  # Password reset link
    PASSWORD_CHANGED = 'd-password-changed-id'  # Password successfully changed
    
    # Bidding Notifications
    BID_PLACED = 'd-bid-placed-id'  # Confirmation of bid placement
    BID_OUTBID = 'd-outbid-id'  # User has been outbid
    BID_WON = 'd-bid-won-id'  # User won the auction
    BID_LOST = 'd-bid-lost-id'  # Auction ended, user didn't win
    
    # Auction Notifications
    AUCTION_ENDING_SOON = 'd-auction-ending-id'  # Auction ending in 24h
    AUCTION_STARTED = 'd-auction-started-id'  # Upcoming auction now live
    AUCTION_CANCELLED = 'd-auction-cancelled-id'  # Auction cancelled by seller
    
    # Seller Notifications
    NEW_BID_RECEIVED = 'd-new-bid-received-id'  # Seller: new bid on item
    LISTING_APPROVED = 'd-listing-approved-id'  # Listing approved by admin
    LISTING_REJECTED = 'd-listing-rejected-id'  # Listing rejected
    ITEM_SOLD = 'd-item-sold-id'  # Item sold successfully
    
    # Financial
    INVOICE = 'd-invoice-id'  # Invoice/receipt for purchase
    PAYMENT_RECEIVED = 'd-payment-received-id'  # Payment confirmed
    PAYMENT_FAILED = 'd-payment-failed-id'  # Payment processing failed
    REFUND_ISSUED = 'd-refund-issued-id'  # Refund processed
    
    # Messaging
    NEW_MESSAGE = 'd-new-message-id'  # New message from another user
    
    # Admin
    REPORT_RECEIVED = 'd-report-received-id'  # Report/flag submitted
    ACCOUNT_SUSPENDED = 'd-account-suspended-id'  # Account suspended


class EmailDataBuilder:
    """
    Helper class to build dynamic data for email templates.
    """
    
    @staticmethod
    def welcome_email(user: Dict[str, Any]) -> Dict[str, Any]:
        """Build data for welcome email."""
        return {
            'first_name': user.get('name', '').split()[0],
            'full_name': user.get('name'),
            'email': user.get('email'),
            'login_url': 'https://bidvex.com/auth',
            'explore_url': 'https://bidvex.com/marketplace',
            'account_type': user.get('account_type', 'personal').title()
        }
    
    @staticmethod
    def password_reset_email(
        user: Dict[str, Any],
        reset_token: str,
        expires_in_hours: int = 1
    ) -> Dict[str, Any]:
        """Build data for password reset email."""
        return {
            'first_name': user.get('name', '').split()[0],
            'reset_url': f'https://bidvex.com/reset-password?token={reset_token}',
            'expires_in_hours': expires_in_hours,
            'support_email': 'support@bidvex.com'
        }
    
    @staticmethod
    def bid_placed_email(
        user: Dict[str, Any],
        listing: Dict[str, Any],
        bid_amount: float,
        currency: str = 'CAD'
    ) -> Dict[str, Any]:
        """Build data for bid confirmation email."""
        return {
            'first_name': user.get('name', '').split()[0],
            'listing_title': listing.get('title'),
            'listing_url': f'https://bidvex.com/listing/{listing.get("id")}',
            'bid_amount': f'{bid_amount:.2f}',
            'currency': currency,
            'listing_image': listing.get('images', [''])[0],
            'auction_end_date': listing.get('auction_end_date'),
            'current_high_bid': f"{listing.get('current_price', 0):.2f}"
        }
    
    @staticmethod
    def outbid_email(
        user: Dict[str, Any],
        listing: Dict[str, Any],
        new_bid_amount: float,
        currency: str = 'CAD'
    ) -> Dict[str, Any]:
        """Build data for outbid notification."""
        return {
            'first_name': user.get('name', '').split()[0],
            'listing_title': listing.get('title'),
            'listing_url': f'https://bidvex.com/listing/{listing.get("id")}',
            'new_bid_amount': f'{new_bid_amount:.2f}',
            'currency': currency,
            'listing_image': listing.get('images', [''])[0],
            'time_remaining': 'Calculate from auction_end_date',
            'bid_now_url': f'https://bidvex.com/listing/{listing.get("id")}#bid'
        }
    
    @staticmethod
    def auction_won_email(
        user: Dict[str, Any],
        listing: Dict[str, Any],
        winning_bid: float,
        currency: str = 'CAD'
    ) -> Dict[str, Any]:
        """Build data for auction won notification."""
        return {
            'first_name': user.get('name', '').split()[0],
            'listing_title': listing.get('title'),
            'winning_bid': f'{winning_bid:.2f}',
            'currency': currency,
            'listing_image': listing.get('images', [''])[0],
            'seller_name': listing.get('seller_name', 'Seller'),
            'payment_url': f'https://bidvex.com/payment/{listing.get("id")}',
            'invoice_url': f'https://bidvex.com/invoice/{listing.get("id")}'
        }
    
    @staticmethod
    def invoice_email(
        user: Dict[str, Any],
        invoice: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build data for invoice/receipt email."""
        return {
            'first_name': user.get('name', '').split()[0],
            'invoice_number': invoice.get('invoice_number'),
            'invoice_date': invoice.get('date'),
            'total_amount': f"{invoice.get('total', 0):.2f}",
            'currency': invoice.get('currency', 'CAD'),
            'items': invoice.get('items', []),
            'subtotal': f"{invoice.get('subtotal', 0):.2f}",
            'tax': f"{invoice.get('tax', 0):.2f}",
            'shipping': f"{invoice.get('shipping', 0):.2f}",
            'invoice_pdf_url': invoice.get('pdf_url'),
            'payment_method': invoice.get('payment_method', 'Credit Card')
        }
    
    @staticmethod
    def new_message_email(
        user: Dict[str, Any],
        sender: Dict[str, Any],
        message_preview: str
    ) -> Dict[str, Any]:
        """Build data for new message notification."""
        return {
            'first_name': user.get('name', '').split()[0],
            'sender_name': sender.get('name'),
            'message_preview': message_preview[:100] + '...' if len(message_preview) > 100 else message_preview,
            'messages_url': 'https://bidvex.com/messages',
            'sender_profile_url': f'https://bidvex.com/seller/{sender.get("id")}'
        }


# Helper functions for common email operations

async def send_welcome_email(email_service, user: Dict[str, Any], language: str = 'en'):
    """Send welcome email to new user."""
    return await email_service.send_email(
        to=user['email'],
        template_id=EmailTemplates.WELCOME,
        dynamic_data=EmailDataBuilder.welcome_email(user),
        language=language
    )

async def send_password_reset_email(
    email_service,
    user: Dict[str, Any],
    reset_token: str,
    language: str = 'en'
):
    """Send password reset email."""
    return await email_service.send_email(
        to=user['email'],
        template_id=EmailTemplates.PASSWORD_RESET,
        dynamic_data=EmailDataBuilder.password_reset_email(user, reset_token),
        language=language
    )

async def send_bid_confirmation(
    email_service,
    user: Dict[str, Any],
    listing: Dict[str, Any],
    bid_amount: float,
    language: str = 'en'
):
    """Send bid placement confirmation."""
    return await email_service.send_email(
        to=user['email'],
        template_id=EmailTemplates.BID_PLACED,
        dynamic_data=EmailDataBuilder.bid_placed_email(user, listing, bid_amount),
        language=language
    )

async def send_outbid_notification(
    email_service,
    user: Dict[str, Any],
    listing: Dict[str, Any],
    new_bid_amount: float,
    language: str = 'en'
):
    """Send outbid notification."""
    return await email_service.send_email(
        to=user['email'],
        template_id=EmailTemplates.BID_OUTBID,
        dynamic_data=EmailDataBuilder.outbid_email(user, listing, new_bid_amount),
        language=language
    )
