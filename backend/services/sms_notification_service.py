"""
BidVex SMS Notification Service
Handles Twilio-powered SMS notifications for:
- Outbid alerts
- Auction win notifications
- Auction status updates (ending soon, extended)
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# SMS notification templates
SMS_TEMPLATES = {
    "outbid": {
        "en": "🔔 BidVex: You've been outbid! Someone placed ${amount} on '{title}'. Your previous bid: ${previous_bid}. Tap to bid again: {link}",
        "fr": "🔔 BidVex: Vous avez été surenchéri! Quelqu'un a enchéri {amount}$ sur '{title}'. Votre offre précédente: {previous_bid}$. Enchérissez à nouveau: {link}"
    },
    "auction_won": {
        "en": "🎉 BidVex: Congratulations! You won '{title}' for ${amount}! Log in to complete your purchase: {link}",
        "fr": "🎉 BidVex: Félicitations! Vous avez remporté '{title}' pour {amount}$! Connectez-vous pour finaliser: {link}"
    },
    "auction_ending_soon": {
        "en": "⏰ BidVex: Auction ending soon! '{title}' ends in {minutes} minutes. Current bid: ${amount}. Bid now: {link}",
        "fr": "⏰ BidVex: Enchère bientôt terminée! '{title}' se termine dans {minutes} minutes. Offre actuelle: {amount}$. Enchérissez: {link}"
    },
    "auction_extended": {
        "en": "🔄 BidVex: Auction extended! '{title}' has been extended due to last-minute bidding. New end time: {end_time}. Bid now: {link}",
        "fr": "🔄 BidVex: Enchère prolongée! '{title}' a été prolongée. Nouvelle fin: {end_time}. Enchérissez: {link}"
    },
    "bid_confirmed": {
        "en": "✅ BidVex: Your bid of ${amount} on '{title}' was placed successfully. Good luck!",
        "fr": "✅ BidVex: Votre enchère de {amount}$ sur '{title}' a été enregistrée. Bonne chance!"
    },
    "seller_new_bid": {
        "en": "💰 BidVex: New bid on your listing! Someone bid ${amount} on '{title}'. Current total bids: {bid_count}.",
        "fr": "💰 BidVex: Nouvelle enchère! Quelqu'un a enchéri {amount}$ sur '{title}'. Total des enchères: {bid_count}."
    },
    "seller_auction_sold": {
        "en": "🎊 BidVex: Your item sold! '{title}' was won for ${amount}. Login to manage the sale: {link}",
        "fr": "🎊 BidVex: Votre article vendu! '{title}' a été remporté pour {amount}$. Connectez-vous: {link}"
    }
}


class SMSNotificationService:
    """Service for sending SMS notifications via Twilio"""
    
    def __init__(self, db):
        self.db = db
        self.client = None
        self.from_number = None
        self._initialize_twilio()
    
    def _initialize_twilio(self):
        """Initialize Twilio client with credentials from environment"""
        try:
            from twilio.rest import Client
            
            account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
            auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
            self.from_number = os.environ.get("TWILIO_PHONE_NUMBER")
            
            if not account_sid or not auth_token or account_sid == "your_twilio_account_sid":
                logger.warning("⚠️ Twilio credentials not configured - SMS notifications disabled")
                self.client = None
                return
            
            self.client = Client(account_sid, auth_token)
            logger.info(f"✅ Twilio SMS service initialized with number: {self.from_number}")
            
        except ImportError:
            logger.error("❌ Twilio library not installed. Run: pip install twilio")
            self.client = None
        except Exception as e:
            logger.error(f"❌ Failed to initialize Twilio: {e}")
            self.client = None
    
    def is_enabled(self) -> bool:
        """Check if SMS notifications are enabled"""
        return self.client is not None and self.from_number is not None
    
    async def get_user_sms_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user's SMS notification preferences"""
        user = await self.db.users.find_one(
            {"id": user_id}, 
            {"_id": 0, "phone_number": 1, "phone_verified": 1, "preferred_language": 1, "notification_preferences": 1}
        )
        
        if not user:
            return {"enabled": False, "reason": "user_not_found"}
        
        if not user.get("phone_verified", False):
            return {"enabled": False, "reason": "phone_not_verified"}
        
        phone = user.get("phone_number") or user.get("phone")
        if not phone:
            return {"enabled": False, "reason": "no_phone_number"}
        
        # Check user's notification preferences (defaults to enabled)
        prefs = user.get("notification_preferences", {})
        sms_enabled = prefs.get("sms_enabled", True)
        
        return {
            "enabled": sms_enabled,
            "phone": phone,
            "language": user.get("preferred_language", "en"),
            "preferences": prefs
        }
    
    async def send_sms(
        self, 
        to_phone: str, 
        message: str,
        notification_type: str = "general",
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an SMS message via Twilio
        
        Args:
            to_phone: Phone number in E.164 format (+14155552671)
            message: Message text (max 1600 chars, SMS will be split if needed)
            notification_type: Type of notification for logging
            user_id: Optional user ID for logging
        
        Returns:
            Dict with status and message SID
        """
        if not self.is_enabled():
            logger.warning(f"📱 SMS not sent (disabled): {notification_type} to {to_phone[:6]}***")
            return {"status": "disabled", "message": "SMS notifications not configured"}
        
        try:
            # Truncate message if too long (Twilio SMS limit)
            if len(message) > 1600:
                message = message[:1597] + "..."
            
            # Send via Twilio
            sms = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_phone
            )
            
            logger.info(f"✅ SMS sent: {notification_type} to {to_phone[:6]}*** (SID: {sms.sid})")
            
            # Log to database
            await self.db.sms_logs.insert_one({
                "message_sid": sms.sid,
                "to_phone": to_phone[:6] + "***",
                "notification_type": notification_type,
                "user_id": user_id,
                "status": sms.status,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            return {
                "status": "sent",
                "message_sid": sms.sid,
                "segments": sms.num_segments if hasattr(sms, 'num_segments') else 1
            }
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"❌ SMS send failed: {notification_type} to {to_phone[:6]}*** - {error_str}")
            
            # Log failed attempt
            await self.db.sms_logs.insert_one({
                "to_phone": to_phone[:6] + "***",
                "notification_type": notification_type,
                "user_id": user_id,
                "status": "failed",
                "error": error_str[:500],
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Check for trial account limitations
            if "21608" in error_str or "unverified" in error_str.lower():
                return {"status": "trial_limit", "message": "Phone number not verified in Twilio trial"}
            
            return {"status": "error", "message": error_str[:200]}
    
    def format_message(
        self, 
        template_key: str, 
        language: str = "en",
        **kwargs
    ) -> str:
        """Format a message using a template"""
        template = SMS_TEMPLATES.get(template_key, {}).get(language)
        
        if not template:
            template = SMS_TEMPLATES.get(template_key, {}).get("en", "BidVex notification")
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing template variable: {e}")
            return template
    
    # ========== HIGH-LEVEL NOTIFICATION METHODS ==========
    
    async def notify_outbid(
        self, 
        user_id: str, 
        listing_title: str,
        new_bid_amount: float,
        previous_bid_amount: float,
        listing_id: str,
        listing_url: str = None
    ) -> Dict[str, Any]:
        """
        Send outbid notification to user
        """
        prefs = await self.get_user_sms_preferences(user_id)
        
        if not prefs.get("enabled"):
            logger.info(f"📵 Outbid SMS skipped for {user_id}: {prefs.get('reason', 'unknown')}")
            return {"status": "skipped", "reason": prefs.get("reason")}
        
        # Check if outbid notifications are enabled for user
        if not prefs.get("preferences", {}).get("sms_outbid", True):
            return {"status": "skipped", "reason": "user_disabled_outbid_sms"}
        
        link = listing_url or f"https://bidvex.com/listing/{listing_id}"
        
        message = self.format_message(
            "outbid",
            prefs.get("language", "en"),
            amount=f"{new_bid_amount:.2f}",
            title=listing_title[:40],  # Truncate for SMS
            previous_bid=f"{previous_bid_amount:.2f}",
            link=link
        )
        
        return await self.send_sms(
            prefs["phone"],
            message,
            notification_type="outbid",
            user_id=user_id
        )
    
    async def notify_auction_won(
        self, 
        user_id: str,
        listing_title: str,
        winning_amount: float,
        listing_id: str,
        listing_url: str = None
    ) -> Dict[str, Any]:
        """
        Send auction won notification to winner
        """
        prefs = await self.get_user_sms_preferences(user_id)
        
        if not prefs.get("enabled"):
            logger.info(f"📵 Auction won SMS skipped for {user_id}: {prefs.get('reason', 'unknown')}")
            return {"status": "skipped", "reason": prefs.get("reason")}
        
        link = listing_url or f"https://bidvex.com/listing/{listing_id}"
        
        message = self.format_message(
            "auction_won",
            prefs.get("language", "en"),
            title=listing_title[:40],
            amount=f"{winning_amount:.2f}",
            link=link
        )
        
        return await self.send_sms(
            prefs["phone"],
            message,
            notification_type="auction_won",
            user_id=user_id
        )
    
    async def notify_seller_auction_sold(
        self, 
        seller_id: str,
        listing_title: str,
        sold_amount: float,
        listing_id: str
    ) -> Dict[str, Any]:
        """
        Send notification to seller when their item is sold
        """
        prefs = await self.get_user_sms_preferences(seller_id)
        
        if not prefs.get("enabled"):
            return {"status": "skipped", "reason": prefs.get("reason")}
        
        link = f"https://bidvex.com/seller/dashboard"
        
        message = self.format_message(
            "seller_auction_sold",
            prefs.get("language", "en"),
            title=listing_title[:40],
            amount=f"{sold_amount:.2f}",
            link=link
        )
        
        return await self.send_sms(
            prefs["phone"],
            message,
            notification_type="seller_auction_sold",
            user_id=seller_id
        )
    
    async def notify_seller_new_bid(
        self, 
        seller_id: str,
        listing_title: str,
        bid_amount: float,
        bid_count: int
    ) -> Dict[str, Any]:
        """
        Send notification to seller when they receive a new bid
        """
        prefs = await self.get_user_sms_preferences(seller_id)
        
        if not prefs.get("enabled"):
            return {"status": "skipped", "reason": prefs.get("reason")}
        
        # Check if seller has enabled bid notifications
        if not prefs.get("preferences", {}).get("sms_new_bid", False):  # Default off for sellers
            return {"status": "skipped", "reason": "user_disabled_new_bid_sms"}
        
        message = self.format_message(
            "seller_new_bid",
            prefs.get("language", "en"),
            title=listing_title[:40],
            amount=f"{bid_amount:.2f}",
            bid_count=bid_count
        )
        
        return await self.send_sms(
            prefs["phone"],
            message,
            notification_type="seller_new_bid",
            user_id=seller_id
        )


# Global service instance
_sms_service = None


def get_sms_notification_service(db) -> SMSNotificationService:
    """Get or create the global SMS notification service"""
    global _sms_service
    if _sms_service is None:
        _sms_service = SMSNotificationService(db)
    return _sms_service
