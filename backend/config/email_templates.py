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
    
    # User Authentication (Category Template ID: d-e0ee403fbd8646db8011339cf2eeac30)
    WELCOME = 'd-e0ee403fbd8646db8011339cf2eeac30'  # New user registration
    EMAIL_VERIFICATION = 'd-e0ee403fbd8646db8011339cf2eeac30'  # Email verification
    PASSWORD_RESET = 'd-e0ee403fbd8646db8011339cf2eeac30'  # Password reset link
    PASSWORD_CHANGED = 'd-e0ee403fbd8646db8011339cf2eeac30'  # Password successfully changed
    
    # Bidding Notifications (Category Template ID: d-13806757fbd24818b24bc520074ea979)
    BID_PLACED = 'd-13806757fbd24818b24bc520074ea979'  # Confirmation of bid placement
    BID_OUTBID = 'd-13806757fbd24818b24bc520074ea979'  # User has been outbid
    BID_WON = 'd-13806757fbd24818b24bc520074ea979'  # User won the auction
    BID_LOST = 'd-13806757fbd24818b24bc520074ea979'  # Auction ended, user didn't win
    
    # Auction Updates (Category Template ID: d-f22625d31ef74262887e3a8f96934bc1)
    AUCTION_ENDING_SOON = 'd-f22625d31ef74262887e3a8f96934bc1'  # Auction ending in 24h
    AUCTION_STARTED = 'd-f22625d31ef74262887e3a8f96934bc1'  # Upcoming auction now live
    AUCTION_CANCELLED = 'd-f22625d31ef74262887e3a8f96934bc1'  # Auction cancelled by seller
    
    # Seller Notifications (Category Template ID: d-794b529ec05e407da60b26113e0c4ea1)
    NEW_BID_RECEIVED = 'd-794b529ec05e407da60b26113e0c4ea1'  # Seller: new bid on item
    LISTING_APPROVED = 'd-794b529ec05e407da60b26113e0c4ea1'  # Listing approved by admin
    LISTING_REJECTED = 'd-794b529ec05e407da60b26113e0c4ea1'  # Listing rejected
    ITEM_SOLD = 'd-794b529ec05e407da60b26113e0c4ea1'  # Item sold successfully
    
    # Financial (Category Template ID: d-a8cb13c061e3449394e900b406e9a391)
    INVOICE = 'd-a8cb13c061e3449394e900b406e9a391'  # Invoice/receipt for purchase
    PAYMENT_RECEIVED = 'd-a8cb13c061e3449394e900b406e9a391'  # Payment confirmed
    PAYMENT_FAILED = 'd-a8cb13c061e3449394e900b406e9a391'  # Payment processing failed
    REFUND_ISSUED = 'd-a8cb13c061e3449394e900b406e9a391'  # Refund processed
    
    # Communication (Category Template ID: d-3153ed45d6764d0687e69c85ffddcb10)
    NEW_MESSAGE = 'd-3153ed45d6764d0687e69c85ffddcb10'  # New message from another user
    
    # Admin (Category Template ID: d-94d4a5d7855b4fa38badae9cf12ded41)
    REPORT_RECEIVED = 'd-94d4a5d7855b4fa38badae9cf12ded41'  # Report/flag submitted
    ACCOUNT_SUSPENDED = 'd-94d4a5d7855b4fa38badae9cf12ded41'  # Account suspended


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
        reset_url = f'https://bidvex.com/reset-password?token={reset_token}'
        expiry_message = f'{expires_in_hours} hour' if expires_in_hours == 1 else f'{expires_in_hours} hours'
        
        return {
            'first_name': user.get('name', '').split()[0],
            # Both variable name formats for template compatibility
            'reset_url': reset_url,
            'reset_link': reset_url,  # Alternative name used in template
            'expires_in_hours': expires_in_hours,
            'expiry_time': expiry_message,  # Formatted expiry time
            'support_email': 'support@bidvex.com'
        }
    
    @staticmethod
    def password_changed_email(user: Dict[str, Any]) -> Dict[str, Any]:
        """Build data for password changed confirmation email."""
        return {
            'first_name': user.get('name', '').split()[0],
            'email': user.get('email'),
            'change_time': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
            'support_email': 'support@bidvex.com',
            'login_url': 'https://bidvex.com/auth'
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
