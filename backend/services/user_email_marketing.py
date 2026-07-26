"""
BidVex User Email Marketing Service
Allows users to manage their own client email lists and send auction campaigns.
Subscription-restricted: Premium and VIP only.
"""

import os
import uuid
import logging
import re
import csv
import io
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Email, To, Content, Personalization,
    TrackingSettings, ClickTracking, OpenTracking,
    SubscriptionTracking, Ganalytics,
    CustomArg
)

logger = logging.getLogger(__name__)

# Configuration
MARKETING_API_KEY = os.environ.get("SENDGRID_MARKETING_API_KEY") or os.environ.get("SENDGRID_API_KEY")
MARKETING_FROM_EMAIL = os.environ.get("SENDGRID_MARKETING_FROM_EMAIL", "noreply@bidvex.com")
MARKETING_FROM_NAME = os.environ.get("SENDGRID_MARKETING_FROM_NAME", "BidVex")
MARKETING_REPLY_TO = os.environ.get("SENDGRID_MARKETING_REPLY_TO", "service@bidvex.com")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://www.bidvex.com")

# Initialize client
marketing_client = None
if MARKETING_API_KEY and MARKETING_API_KEY != "SG.your-actual-sendgrid-key-here":
    marketing_client = SendGridAPIClient(MARKETING_API_KEY)

# Subscription limits
# Daily limit prevents spam blasts, monthly limit protects cost structure
SUBSCRIPTION_LIMITS = {
    "free": {"daily": 0, "monthly": 0, "contacts": 50},
    "premium": {"daily": 500, "monthly": 5000, "contacts": 5000},
    "vip": {"daily": 2000, "monthly": 50000, "contacts": 25000}
}

# Pre-built auction email templates
EMAIL_TEMPLATES = {
    "new_auction": {
        "name": "New Auction Announcement",
        "subject": "New Auction: {{auction_title}}",
        "description": "Announce a new auction to your client list"
    },
    "ending_soon": {
        "name": "Ending Soon Reminder",
        "subject": "Ending Soon: {{auction_title}} - Don't Miss Out!",
        "description": "Remind clients about auctions ending within 24 hours"
    },
    "new_inventory": {
        "name": "New Inventory Alert",
        "subject": "Fresh Inventory Just Listed!",
        "description": "Notify clients about new items in your listings"
    },
    "vip_preview": {
        "name": "Exclusive VIP Preview",
        "subject": "VIP Preview: Early Access to Upcoming Auction",
        "description": "Give VIP clients early preview access"
    },
    "price_drop": {
        "name": "Price Drop Alert",
        "subject": "Price Drop Alert: {{auction_title}}",
        "description": "Notify clients about reduced starting prices"
    }
}

# Contact status constants
CONTACT_STATUS = {
    "ACTIVE": "active",
    "UNSUBSCRIBED": "unsubscribed",
    "BOUNCED": "bounced",
    "INVALID": "invalid"
}


class UserEmailMarketingService:
    """
    User Email Marketing Service for managing client contacts and campaigns
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.contacts = db.user_contacts
        self.campaigns = db.user_campaigns
        self.campaign_sends = db.user_campaign_sends
        self.campaign_events = db.user_campaign_events
        self.usage_logs = db.user_marketing_usage
        
    # ==================== SUBSCRIPTION CHECKS ====================
    
    def get_subscription_limits(self, tier: str) -> Dict[str, int]:
        """Get all limits for subscription tier"""
        return SUBSCRIPTION_LIMITS.get(tier.lower(), SUBSCRIPTION_LIMITS["free"])
    
    def get_contact_limit(self, tier: str) -> int:
        """Get contact storage limit for subscription tier"""
        return self.get_subscription_limits(tier).get("contacts", 50)
    
    def can_access_feature(self, tier: str) -> bool:
        """Check if user's subscription tier can access send feature (Premium/VIP only)"""
        return tier.lower() in ["premium", "vip"]
    
    def can_manage_contacts(self, tier: str) -> bool:
        """Free users can manage up to 50 contacts but cannot send"""
        return True  # All tiers can manage contacts
    
    async def get_daily_usage(self, user_id: str) -> int:
        """Get user's email sends for today"""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        count = await self.campaign_sends.count_documents({
            "user_id": user_id,
            "sent_at": {"$gte": today_start.isoformat()},
            "status": {"$in": ["sent", "logged"]}
        })
        return count
    
    async def get_monthly_usage(self, user_id: str) -> int:
        """Get user's email sends for the current month"""
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        count = await self.campaign_sends.count_documents({
            "user_id": user_id,
            "sent_at": {"$gte": month_start.isoformat()},
            "status": {"$in": ["sent", "logged"]}
        })
        return count
    
    async def get_remaining_quota(self, user_id: str, tier: str) -> Dict[str, Any]:
        """Get remaining email quota for daily and monthly limits"""
        limits = self.get_subscription_limits(tier)
        daily_used = await self.get_daily_usage(user_id)
        monthly_used = await self.get_monthly_usage(user_id)
        
        daily_limit = limits.get("daily", 0)
        monthly_limit = limits.get("monthly", 0)
        contact_limit = limits.get("contacts", 50)
        
        daily_remaining = max(0, daily_limit - daily_used)
        monthly_remaining = max(0, monthly_limit - monthly_used)
        
        # Can only send if both daily and monthly limits allow
        can_send = daily_remaining > 0 and monthly_remaining > 0 if (daily_limit > 0 and monthly_limit > 0) else False
        
        return {
            "daily_limit": daily_limit,
            "daily_used": daily_used,
            "daily_remaining": daily_remaining,
            "monthly_limit": monthly_limit,
            "monthly_used": monthly_used,
            "monthly_remaining": monthly_remaining,
            "contact_limit": contact_limit,
            "can_send": can_send,
            "tier": tier,
            # Legacy fields for backwards compatibility
            "limit": monthly_limit,
            "used": monthly_used,
            "remaining": monthly_remaining
        }
    
    async def check_contact_limit(self, user_id: str, tier: str) -> Dict[str, Any]:
        """Check if user can add more contacts"""
        limit = self.get_contact_limit(tier)
        current_count = await self.contacts.count_documents({"user_id": user_id})
        
        return {
            "limit": limit,
            "current": current_count,
            "remaining": max(0, limit - current_count),
            "can_add": current_count < limit
        }
    
    # ==================== CONTACT MANAGEMENT ====================
    
    def validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email.strip().lower()))
    
    def parse_email_list(self, email_text: str) -> Dict[str, List[str]]:
        """Parse email list from text input"""
        if not email_text or not email_text.strip():
            return {"valid": [], "invalid": []}
        
        raw_emails = re.split(r'[,\n;\s]+', email_text)
        valid = []
        invalid = []
        seen = set()
        
        for email in raw_emails:
            email = email.strip().lower()
            if not email:
                continue
            if email in seen:
                continue
            seen.add(email)
            
            if self.validate_email(email):
                valid.append(email)
            else:
                invalid.append(email)
        
        return {"valid": valid, "invalid": invalid}
    
    def parse_csv_emails(self, csv_content: str) -> Dict[str, Any]:
        """Parse emails from CSV content"""
        result = {
            "valid": [],
            "invalid": [],
            "duplicates": [],
            "total_rows": 0
        }
        
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            seen = set()
            
            email_column = None
            if reader.fieldnames:
                for field in reader.fieldnames:
                    if field.lower() in ['email', 'e-mail', 'email_address', 'emailaddress', 'mail']:
                        email_column = field
                        break
                if not email_column and reader.fieldnames:
                    email_column = reader.fieldnames[0]
            
            for row in reader:
                result["total_rows"] += 1
                email = row.get(email_column, "").strip().lower() if email_column else ""
                
                if not email:
                    continue
                
                if not self.validate_email(email):
                    result["invalid"].append(email)
                elif email in seen:
                    result["duplicates"].append(email)
                else:
                    seen.add(email)
                    result["valid"].append(email)
                    
        except Exception as e:
            logger.error(f"CSV parsing error: {e}")
            result["error"] = str(e)
        
        return result
    
    async def add_contact(
        self,
        user_id: str,
        email: str,
        name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        consent_confirmed: bool = False,
        user_tier: str = "free"
    ) -> Dict[str, Any]:
        """Add a single contact"""
        email = email.strip().lower()
        
        if not self.validate_email(email):
            raise ValueError(f"Invalid email format: {email}")
        
        # Check contact limit
        contact_check = await self.check_contact_limit(user_id, user_tier)
        if not contact_check["can_add"]:
            tier_name = user_tier.capitalize()
            raise ValueError(f"Contact limit reached ({contact_check['limit']} contacts for {tier_name}). Upgrade to add more contacts.")
        
        # Check for duplicate
        existing = await self.contacts.find_one({
            "user_id": user_id,
            "email": email
        })
        
        if existing:
            raise ValueError(f"Contact already exists: {email}")
        
        now = datetime.now(timezone.utc)
        contact = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "email": email,
            "name": name,
            "tags": tags or [],
            "status": CONTACT_STATUS["ACTIVE"],
            "consent_confirmed": consent_confirmed,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        
        await self.contacts.insert_one(contact)
        return {k: v for k, v in contact.items() if k != "_id"}
    
    async def add_contacts_bulk(
        self,
        user_id: str,
        emails: List[str],
        consent_confirmed: bool = False,
        user_tier: str = "free"
    ) -> Dict[str, Any]:
        """Add multiple contacts at once"""
        now = datetime.now(timezone.utc)
        
        # Check contact limit
        contact_check = await self.check_contact_limit(user_id, user_tier)
        slots_available = contact_check["remaining"]
        
        # Get existing emails for this user
        existing = await self.contacts.distinct("email", {"user_id": user_id})
        existing_set = set(e.lower() for e in existing)
        
        added = []
        duplicates = []
        invalid = []
        limit_exceeded = []
        
        contacts_to_insert = []
        
        for email in emails:
            email = email.strip().lower()
            
            if not email:
                continue
            
            if not self.validate_email(email):
                invalid.append(email)
                continue
            
            if email in existing_set:
                duplicates.append(email)
                continue
            
            # Check if we've hit the limit
            if len(contacts_to_insert) >= slots_available:
                limit_exceeded.append(email)
                continue
            
            existing_set.add(email)
            contact = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "email": email,
                "name": None,
                "tags": [],
                "status": CONTACT_STATUS["ACTIVE"],
                "consent_confirmed": consent_confirmed,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }
            contacts_to_insert.append(contact)
            added.append(email)
        
        if contacts_to_insert:
            await self.contacts.insert_many(contacts_to_insert)
        
        return {
            "added": added,
            "added_count": len(added),
            "duplicates": duplicates,
            "duplicates_count": len(duplicates),
            "invalid": invalid,
            "invalid_count": len(invalid),
            "limit_exceeded": limit_exceeded,
            "limit_exceeded_count": len(limit_exceeded),
            "contact_limit": contact_check["limit"],
            "contacts_remaining": max(0, slots_available - len(contacts_to_insert))
        }
    
    async def get_contacts(
        self,
        user_id: str,
        status: Optional[str] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        skip: int = 0
    ) -> Dict[str, Any]:
        """Get user's contacts with optional filtering"""
        query = {"user_id": user_id}
        
        if status:
            query["status"] = status
        
        if search:
            query["$or"] = [
                {"email": {"$regex": search, "$options": "i"}},
                {"name": {"$regex": search, "$options": "i"}}
            ]
        
        if tags:
            query["tags"] = {"$in": tags}
        
        total = await self.contacts.count_documents(query)
        contacts = await self.contacts.find(
            query, {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        return {
            "contacts": contacts,
            "total": total,
            "limit": limit,
            "skip": skip
        }
    
    async def get_contact(self, user_id: str, contact_id: str) -> Optional[Dict[str, Any]]:
        """Get single contact"""
        contact = await self.contacts.find_one(
            {"user_id": user_id, "id": contact_id},
            {"_id": 0}
        )
        return contact
    
    async def update_contact(
        self,
        user_id: str,
        contact_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a contact"""
        # Prevent updating certain fields
        updates.pop("id", None)
        updates.pop("user_id", None)
        updates.pop("created_at", None)
        
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        result = await self.contacts.update_one(
            {"user_id": user_id, "id": contact_id},
            {"$set": updates}
        )
        
        if result.matched_count == 0:
            raise ValueError("Contact not found")
        
        return await self.get_contact(user_id, contact_id)
    
    async def delete_contact(self, user_id: str, contact_id: str) -> bool:
        """Delete a contact"""
        result = await self.contacts.delete_one({
            "user_id": user_id,
            "id": contact_id
        })
        return result.deleted_count > 0
    
    async def delete_contacts_bulk(self, user_id: str, contact_ids: List[str]) -> int:
        """Delete multiple contacts"""
        result = await self.contacts.delete_many({
            "user_id": user_id,
            "id": {"$in": contact_ids}
        })
        return result.deleted_count
    
    async def get_contact_stats(self, user_id: str) -> Dict[str, int]:
        """Get contact statistics"""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        results = await self.contacts.aggregate(pipeline).to_list(None)
        
        stats = {
            "total": 0,
            "active": 0,
            "unsubscribed": 0,
            "bounced": 0,
            "invalid": 0
        }
        
        for r in results:
            status = r["_id"]
            count = r["count"]
            stats["total"] += count
            if status in stats:
                stats[status] = count
        
        return stats
    
    async def get_suppressed_contacts(self, user_id: str) -> set:
        """Get emails that should not receive emails"""
        suppressed = set()
        
        # Get unsubscribed/bounced from contacts
        cursor = self.contacts.find(
            {
                "user_id": user_id,
                "status": {"$in": [CONTACT_STATUS["UNSUBSCRIBED"], CONTACT_STATUS["BOUNCED"], CONTACT_STATUS["INVALID"]]}
            },
            {"email": 1}
        )
        
        async for doc in cursor:
            suppressed.add(doc["email"].lower())
        
        return suppressed
    
    # ==================== CAMPAIGN MANAGEMENT ====================
    
    async def create_campaign(
        self,
        user_id: str,
        user_email: str,
        name: str,
        subject: str,
        html_content: str,
        plain_text_content: str = "",
        contact_ids: Optional[List[str]] = None,
        contact_filter: Optional[Dict[str, Any]] = None,
        auction_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new campaign"""
        now = datetime.now(timezone.utc)
        
        # Calculate recipient count
        if contact_ids:
            recipient_count = len(contact_ids)
        else:
            query = {"user_id": user_id, "status": CONTACT_STATUS["ACTIVE"]}
            if contact_filter:
                query.update(contact_filter)
            recipient_count = await self.contacts.count_documents(query)
        
        campaign = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "user_email": user_email,
            "name": name,
            "subject": subject,
            "html_content": html_content,
            "plain_text_content": plain_text_content,
            "contact_ids": contact_ids,
            "contact_filter": contact_filter,
            "auction_id": auction_id,
            "recipient_count": recipient_count,
            "status": "draft",
            "consent_confirmed": False,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "sent_at": None,
            "completed_at": None,
            "stats": {
                "total": 0,
                "sent": 0,
                "delivered": 0,
                "opened": 0,
                "clicked": 0,
                "bounced": 0,
                "unsubscribed": 0
            }
        }
        
        await self.campaigns.insert_one(campaign)
        return {k: v for k, v in campaign.items() if k != "_id"}
    
    async def get_campaigns(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> Dict[str, Any]:
        """Get user's campaigns"""
        query = {"user_id": user_id}
        if status:
            query["status"] = status
        
        total = await self.campaigns.count_documents(query)
        campaigns = await self.campaigns.find(
            query, {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        return {
            "campaigns": campaigns,
            "total": total
        }
    
    async def get_campaign(self, user_id: str, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get single campaign"""
        campaign = await self.campaigns.find_one(
            {"user_id": user_id, "id": campaign_id},
            {"_id": 0}
        )
        return campaign
    
    async def update_campaign(
        self,
        user_id: str,
        campaign_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a draft campaign"""
        campaign = await self.get_campaign(user_id, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        
        if campaign["status"] != "draft":
            raise ValueError("Can only edit draft campaigns")
        
        updates.pop("id", None)
        updates.pop("user_id", None)
        updates.pop("created_at", None)
        updates.pop("status", None)
        
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await self.campaigns.update_one(
            {"user_id": user_id, "id": campaign_id},
            {"$set": updates}
        )
        
        return await self.get_campaign(user_id, campaign_id)
    
    async def confirm_consent(self, user_id: str, campaign_id: str) -> Dict[str, Any]:
        """Confirm consent for sending"""
        await self.campaigns.update_one(
            {"user_id": user_id, "id": campaign_id},
            {"$set": {
                "consent_confirmed": True,
                "consent_confirmed_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        return await self.get_campaign(user_id, campaign_id)
    
    async def send_campaign(
        self,
        user_id: str,
        user_email: str,
        campaign_id: str,
        user_tier: str,
        user_ip: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a campaign"""
        campaign = await self.get_campaign(user_id, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        
        if campaign["status"] != "draft":
            raise ValueError("Campaign has already been sent")
        
        if not campaign.get("consent_confirmed"):
            raise ValueError("You must confirm consent before sending")
        
        # Check quota - both daily and monthly limits
        quota = await self.get_remaining_quota(user_id, user_tier)
        
        if not quota["can_send"]:
            if quota["daily_remaining"] <= 0:
                raise ValueError(f"Daily sending limit reached ({quota['daily_limit']} emails/day). Try again tomorrow.")
            elif quota["monthly_remaining"] <= 0:
                raise ValueError(f"Monthly sending limit reached ({quota['monthly_limit']} emails/month). Upgrade to VIP to increase capacity.")
            else:
                raise ValueError("Sending limit reached. Upgrade to Premium or VIP to send emails.")
        
        # Get recipients
        suppressed = await self.get_suppressed_contacts(user_id)
        
        if campaign.get("contact_ids"):
            contacts = await self.contacts.find({
                "user_id": user_id,
                "id": {"$in": campaign["contact_ids"]},
                "status": CONTACT_STATUS["ACTIVE"]
            }, {"_id": 0}).to_list(None)
        else:
            query = {"user_id": user_id, "status": CONTACT_STATUS["ACTIVE"]}
            if campaign.get("contact_filter"):
                query.update(campaign["contact_filter"])
            contacts = await self.contacts.find(query, {"_id": 0}).to_list(None)
        
        # Filter out suppressed
        recipients = [c for c in contacts if c["email"].lower() not in suppressed]
        
        # Check if within quota - use the minimum of daily and monthly remaining
        effective_remaining = min(quota["daily_remaining"], quota["monthly_remaining"])
        if len(recipients) > effective_remaining:
            if quota["daily_remaining"] < len(recipients):
                raise ValueError(f"Campaign has {len(recipients)} recipients but you only have {quota['daily_remaining']} emails remaining today. Reduce recipients or try tomorrow.")
            else:
                raise ValueError(f"Campaign has {len(recipients)} recipients but you only have {quota['monthly_remaining']} emails remaining this month. Upgrade to VIP to increase capacity.")
        
        # Update campaign status
        now = datetime.now(timezone.utc)
        await self.campaigns.update_one(
            {"id": campaign_id},
            {"$set": {
                "status": "sending",
                "sent_at": now.isoformat(),
                "updated_at": now.isoformat()
            }}
        )
        
        # Send emails
        sent = 0
        failed = 0
        
        for contact in recipients:
            try:
                result = await self._send_email(campaign, contact, user_id)
                if result["success"]:
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Failed to send to {contact['email']}: {e}")
                failed += 1
        
        # Update campaign
        await self.campaigns.update_one(
            {"id": campaign_id},
            {"$set": {
                "status": "sent",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "stats.total": len(recipients),
                "stats.sent": sent
            }}
        )
        
        # Log usage
        await self.usage_logs.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "user_email": user_email,
            "campaign_id": campaign_id,
            "recipients_count": len(recipients),
            "sent_count": sent,
            "failed_count": failed,
            "user_ip": user_ip,
            "timestamp": now.isoformat()
        })
        
        return {
            "status": "sent",
            "total": len(recipients),
            "sent": sent,
            "failed": failed
        }
    
    async def _send_email(
        self,
        campaign: Dict[str, Any],
        contact: Dict[str, Any],
        user_id: str
    ) -> Dict[str, Any]:
        """Send email to a single contact"""
        email = contact["email"]
        name = contact.get("name", "")
        
        if not marketing_client:
            logger.info(f"[USER CAMPAIGN] To: {email}, Campaign: {campaign['id']}")
            
            await self.campaign_sends.insert_one({
                "id": str(uuid.uuid4()),
                "campaign_id": campaign["id"],
                "user_id": user_id,
                "contact_id": contact["id"],
                "email": email,
                "status": "logged",
                "sent_at": datetime.now(timezone.utc).isoformat()
            })
            
            return {"success": True, "logged": True}
        
        try:
            html_content = campaign["html_content"]
            html_content = html_content.replace("{{name}}", name or "")
            html_content = html_content.replace("{{email}}", email)
            # iter386 — Use a signed platform token so the /unsubscribe SPA
            # page validates it correctly. The previous /unsubscribe/user
            # URL had no matching frontend route (would 404) and no signed
            # token, so recipients saw a broken/expired-link screen. We
            # still record the user_id+contact_id lineage via the audit
            # trail written by /api/unsubscribe/auto-confirm.
            try:
                from routes.unsubscribe import build_unsubscribe_urls
                _unsub_url = build_unsubscribe_urls(email).get("en", "")
            except Exception:
                _unsub_url = ""
            if not _unsub_url:
                _unsub_url = f"{FRONTEND_URL}/unsubscribe/user?user={user_id}&contact={contact['id']}"
            html_content = html_content.replace("{{unsubscribe_url}}", _unsub_url)
            
            plain_content = campaign.get("plain_text_content", "")
            plain_content = plain_content.replace("{{name}}", name or "")
            plain_content = plain_content.replace("{{email}}", email)
            
            # Build message — single personalization only
            message = Mail()
            message.from_email = Email(MARKETING_FROM_EMAIL, MARKETING_FROM_NAME)
            message.subject = campaign["subject"]
            message.reply_to = Email(MARKETING_REPLY_TO)
            
            personalization = Personalization()
            personalization.add_to(To(email, name))
            personalization.add_custom_arg(CustomArg("user_campaign_id", campaign["id"]))
            personalization.add_custom_arg(CustomArg("user_id", user_id))
            personalization.add_custom_arg(CustomArg("contact_id", contact["id"]))
            message.add_personalization(personalization)
            
            message.add_content(Content("text/plain", plain_content or "View this email in HTML."))
            message.add_content(Content("text/html", html_content))
            
            # SendGrid tracking: ALL OFF (belt & suspenders — clicktracking=off
            # is also baked into every <a> tag in the HTML templates)
            tracking = TrackingSettings()
            tracking.click_tracking = ClickTracking(False, False)
            tracking.open_tracking = OpenTracking(False)
            tracking.subscription_tracking = SubscriptionTracking(False)
            tracking.ganalytics = Ganalytics(False)
            message.tracking_settings = tracking
            
            response = marketing_client.send(message)
            status_code = response.status_code
            message_id = response.headers.get("X-Message-Id")
            response_body = response.body.decode("utf-8") if response.body else ""
            
            logger.info(
                f"[MARKETING EMAIL] to={email}, status={status_code}, "
                f"message_id={message_id}, from={MARKETING_FROM_EMAIL}, "
                f"body={response_body[:200]}"
            )
            
            await self.campaign_sends.insert_one({
                "id": str(uuid.uuid4()),
                "campaign_id": campaign["id"],
                "user_id": user_id,
                "contact_id": contact["id"],
                "email": email,
                "status": "sent",
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "message_id": message_id
            })
            
            return {"success": True, "message_id": message_id}
            
        except Exception as e:
            error_detail = str(e)
            # Extract full SendGrid error body if available
            if hasattr(e, 'body'):
                error_detail = f"{e} | body={e.body}"
            if hasattr(e, 'status_code'):
                error_detail = f"HTTP {e.status_code}: {error_detail}"
            logger.error(f"[MARKETING EMAIL FAILED] to={email}, from={MARKETING_FROM_EMAIL}, error={error_detail}")
            
            await self.campaign_sends.insert_one({
                "id": str(uuid.uuid4()),
                "campaign_id": campaign["id"],
                "user_id": user_id,
                "contact_id": contact["id"],
                "email": email,
                "status": "failed",
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            })
            
            return {"success": False, "error": str(e)}
    
    async def process_webhook_event(self, event: Dict[str, Any]) -> None:
        """Process SendGrid webhook event for user campaigns"""
        event_type = event.get("event")
        email = event.get("email")
        
        user_campaign_id = event.get("user_campaign_id")
        user_id = event.get("user_id")
        contact_id = event.get("contact_id")
        
        if not user_campaign_id:
            return
        
        await self.campaign_events.insert_one({
            "id": str(uuid.uuid4()),
            "campaign_id": user_campaign_id,
            "user_id": user_id,
            "contact_id": contact_id,
            "email": email,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw_event": event
        })
        
        # Update campaign stats
        stat_field = None
        if event_type == "delivered":
            stat_field = "stats.delivered"
        elif event_type == "open":
            stat_field = "stats.opened"
        elif event_type == "click":
            stat_field = "stats.clicked"
        elif event_type in ["bounce", "dropped"]:
            stat_field = "stats.bounced"
            # Mark contact as bounced
            if contact_id:
                await self.contacts.update_one(
                    {"id": contact_id},
                    {"$set": {"status": CONTACT_STATUS["BOUNCED"]}}
                )
        elif event_type in ["unsubscribe", "group_unsubscribe"]:
            stat_field = "stats.unsubscribed"
            if contact_id:
                await self.contacts.update_one(
                    {"id": contact_id},
                    {"$set": {"status": CONTACT_STATUS["UNSUBSCRIBED"]}}
                )
        
        if stat_field:
            await self.campaigns.update_one(
                {"id": user_campaign_id},
                {"$inc": {stat_field: 1}}
            )
    
    async def get_campaign_stats(self, user_id: str, campaign_id: str) -> Dict[str, Any]:
        """Get detailed campaign stats"""
        campaign = await self.get_campaign(user_id, campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        
        stats = campaign.get("stats", {})
        total = stats.get("sent", 1) or 1
        
        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign["name"],
            "status": campaign["status"],
            "sent_at": campaign.get("sent_at"),
            "stats": {
                **stats,
                "open_rate": round((stats.get("opened", 0) / total) * 100, 2),
                "click_rate": round((stats.get("clicked", 0) / total) * 100, 2),
                "bounce_rate": round((stats.get("bounced", 0) / total) * 100, 2)
            }
        }
    
    async def handle_unsubscribe(self, user_id: str, contact_id: str) -> bool:
        """Handle unsubscribe request"""
        result = await self.contacts.update_one(
            {"user_id": user_id, "id": contact_id},
            {"$set": {
                "status": CONTACT_STATUS["UNSUBSCRIBED"],
                "unsubscribed_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        return result.modified_count > 0
    
    # ==================== TEMPLATES ====================
    
    def get_auction_email_template(self, auction: Dict[str, Any]) -> str:
        """Generate HTML template for auction campaign"""
        title = auction.get("title", "Auction")
        description = auction.get("description", "")[:200]
        image = auction.get("images", [{}])[0].get("url", "")
        starting_bid = auction.get("starting_bid", 0)
        end_date = auction.get("end_date", "")
        
        return f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
  <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
    <div style="background: linear-gradient(135deg, #3B82F6, #8B5CF6); padding: 30px; text-align: center;">
      <h1 style="color: white; margin: 0; font-size: 24px;">New Auction Alert</h1>
    </div>
    
    <div style="padding: 30px;">
      <p style="color: #333; font-size: 16px;">Hello {{{{name}}}},</p>
      
      <p style="color: #333; font-size: 16px;">Check out this auction that might interest you:</p>
      
      <div style="border: 1px solid #eee; border-radius: 8px; overflow: hidden; margin: 20px 0;">
        {f'<img src="{image}" style="width: 100%; height: 200px; object-fit: cover;" alt="{title}">' if image else ''}
        <div style="padding: 20px;">
          <h2 style="margin: 0 0 10px; color: #333;">{title}</h2>
          <p style="color: #666; font-size: 14px; margin: 0 0 15px;">{description}...</p>
          <p style="font-size: 18px; color: #3B82F6; font-weight: bold; margin: 0;">
            Starting at ${starting_bid:,.2f} CAD
          </p>
          {f'<p style="color: #666; font-size: 12px; margin-top: 10px;">Ends: {end_date}</p>' if end_date else ''}
        </div>
      </div>
      
      <div style="text-align: center;">
        <a href="{FRONTEND_URL}/auction/{auction.get('id', '')}" style="display: inline-block; background: #3B82F6; color: white; padding: 14px 40px; text-decoration: none; border-radius: 6px; font-weight: bold;">
          View Auction
        </a>
      </div>
    </div>
    
    <div style="background: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #eee;">
      <p style="color: #666; font-size: 12px; margin: 0;">
        You received this email because you're on {{{{email}}}}'s client list.
      </p>
      <p style="margin: 10px 0 0; font-size: 12px;">
        <a href="{{{{unsubscribe_url}}}}" style="color: #999;">Unsubscribe</a>
      </p>
    </div>
  </div>
</body>
</html>'''
    
    def get_email_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get available pre-built email templates"""
        templates = {}
        
        for key, meta in EMAIL_TEMPLATES.items():
            templates[key] = {
                **meta,
                "html_content": self._get_template_html(key)
            }
        
        return templates
    
    def _get_template_html(self, template_key: str) -> str:
        """Get HTML content for a specific template"""
        base_style = """
            font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;
        """
        container_style = """
            max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; 
            overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        """
        
        templates = {
            "new_auction": f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="{base_style}">
  <div style="{container_style}">
    <div style="background: linear-gradient(135deg, #3B82F6, #8B5CF6); padding: 30px; text-align: center;">
      <h1 style="color: white; margin: 0; font-size: 24px;">🔔 New Auction Announcement</h1>
    </div>
    <div style="padding: 30px;">
      <p style="color: #333; font-size: 16px;">Hello {{{{name}}}},</p>
      <p style="color: #333; font-size: 16px;">I'm excited to announce a new auction that you won't want to miss!</p>
      <div style="background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 20px 0;">
        <h2 style="margin: 0 0 10px; color: #333;">{{{{auction_title}}}}</h2>
        <p style="color: #666; font-size: 14px; margin: 0 0 15px;">{{{{auction_description}}}}</p>
        <p style="font-size: 18px; color: #3B82F6; font-weight: bold; margin: 0;">Starting Bid: ${{{{starting_price}}}}</p>
      </div>
      <div style="text-align: center; margin-top: 30px;">
        <a href="{{{{auction_link}}}}" style="display: inline-block; background: #3B82F6; color: white; padding: 14px 40px; text-decoration: none; border-radius: 6px; font-weight: bold;">View Auction</a>
      </div>
    </div>
    <div style="background: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #eee;">
      <p style="color: #666; font-size: 12px; margin: 0;">You received this email from a BidVex seller.</p>
      <p style="margin: 10px 0 0; font-size: 12px;"><a href="{{{{unsubscribe_url}}}}" style="color: #999;">Unsubscribe</a></p>
    </div>
  </div>
</body>
</html>''',

            "ending_soon": f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="{base_style}">
  <div style="{container_style}">
    <div style="background: linear-gradient(135deg, #EF4444, #F97316); padding: 30px; text-align: center;">
      <h1 style="color: white; margin: 0; font-size: 24px;">⏰ Ending Soon!</h1>
    </div>
    <div style="padding: 30px;">
      <p style="color: #333; font-size: 16px;">Hello {{{{name}}}},</p>
      <p style="color: #333; font-size: 16px;"><strong>Don't miss out!</strong> This auction is ending soon:</p>
      <div style="background: #FEF2F2; border: 2px solid #FECACA; border-radius: 8px; padding: 20px; margin: 20px 0;">
        <h2 style="margin: 0 0 10px; color: #991B1B;">{{{{auction_title}}}}</h2>
        <p style="color: #B91C1C; font-size: 16px; font-weight: bold; margin: 0;">⏰ Ends in {{{{time_remaining}}}}</p>
        <p style="font-size: 18px; color: #333; margin-top: 15px;">Current Bid: ${{{{current_price}}}}</p>
      </div>
      <div style="text-align: center; margin-top: 30px;">
        <a href="{{{{auction_link}}}}" style="display: inline-block; background: #EF4444; color: white; padding: 14px 40px; text-decoration: none; border-radius: 6px; font-weight: bold;">Bid Now</a>
      </div>
    </div>
    <div style="background: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #eee;">
      <p style="color: #666; font-size: 12px; margin: 0;">You received this email from a BidVex seller.</p>
      <p style="margin: 10px 0 0; font-size: 12px;"><a href="{{{{unsubscribe_url}}}}" style="color: #999;">Unsubscribe</a></p>
    </div>
  </div>
</body>
</html>''',

            "new_inventory": f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="{base_style}">
  <div style="{container_style}">
    <div style="background: linear-gradient(135deg, #10B981, #059669); padding: 30px; text-align: center;">
      <h1 style="color: white; margin: 0; font-size: 24px;">📦 Fresh Inventory Alert</h1>
    </div>
    <div style="padding: 30px;">
      <p style="color: #333; font-size: 16px;">Hello {{{{name}}}},</p>
      <p style="color: #333; font-size: 16px;">New items have just been added to our inventory!</p>
      <div style="background: #ECFDF5; border-radius: 8px; padding: 20px; margin: 20px 0;">
        <h3 style="margin: 0 0 15px; color: #065F46;">What's New:</h3>
        <p style="color: #333; font-size: 14px; margin: 0;">{{{{inventory_description}}}}</p>
      </div>
      <p style="color: #333; font-size: 16px;">Be the first to browse and bid on these exciting new items!</p>
      <div style="text-align: center; margin-top: 30px;">
        <a href="{{{{browse_link}}}}" style="display: inline-block; background: #10B981; color: white; padding: 14px 40px; text-decoration: none; border-radius: 6px; font-weight: bold;">Browse New Items</a>
      </div>
    </div>
    <div style="background: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #eee;">
      <p style="color: #666; font-size: 12px; margin: 0;">You received this email from a BidVex seller.</p>
      <p style="margin: 10px 0 0; font-size: 12px;"><a href="{{{{unsubscribe_url}}}}" style="color: #999;">Unsubscribe</a></p>
    </div>
  </div>
</body>
</html>''',

            "vip_preview": f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="{base_style}">
  <div style="{container_style}">
    <div style="background: linear-gradient(135deg, #8B5CF6, #7C3AED); padding: 30px; text-align: center;">
      <h1 style="color: white; margin: 0; font-size: 24px;">👑 Exclusive VIP Preview</h1>
    </div>
    <div style="padding: 30px;">
      <p style="color: #333; font-size: 16px;">Hello {{{{name}}}},</p>
      <p style="color: #333; font-size: 16px;">As one of our valued clients, you're getting <strong>exclusive early access</strong> to an upcoming auction!</p>
      <div style="background: linear-gradient(135deg, #F5F3FF, #EDE9FE); border: 2px solid #C4B5FD; border-radius: 8px; padding: 20px; margin: 20px 0;">
        <div style="text-align: center; margin-bottom: 15px;">
          <span style="background: #8B5CF6; color: white; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold;">VIP EARLY ACCESS</span>
        </div>
        <h2 style="margin: 0 0 10px; color: #5B21B6; text-align: center;">{{{{auction_title}}}}</h2>
        <p style="color: #6B7280; font-size: 14px; margin: 0; text-align: center;">{{{{preview_details}}}}</p>
      </div>
      <p style="color: #333; font-size: 14px; text-align: center;"><em>This preview is available exclusively to you before the general public.</em></p>
      <div style="text-align: center; margin-top: 30px;">
        <a href="{{{{preview_link}}}}" style="display: inline-block; background: #8B5CF6; color: white; padding: 14px 40px; text-decoration: none; border-radius: 6px; font-weight: bold;">Get VIP Access</a>
      </div>
    </div>
    <div style="background: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #eee;">
      <p style="color: #666; font-size: 12px; margin: 0;">You received this exclusive preview from a BidVex seller.</p>
      <p style="margin: 10px 0 0; font-size: 12px;"><a href="{{{{unsubscribe_url}}}}" style="color: #999;">Unsubscribe</a></p>
    </div>
  </div>
</body>
</html>''',

            "price_drop": f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="{base_style}">
  <div style="{container_style}">
    <div style="background: linear-gradient(135deg, #F59E0B, #D97706); padding: 30px; text-align: center;">
      <h1 style="color: white; margin: 0; font-size: 24px;">💰 Price Drop Alert!</h1>
    </div>
    <div style="padding: 30px;">
      <p style="color: #333; font-size: 16px;">Hello {{{{name}}}},</p>
      <p style="color: #333; font-size: 16px;">Great news! The starting price has been reduced on this auction:</p>
      <div style="background: #FFFBEB; border: 2px solid #FDE68A; border-radius: 8px; padding: 20px; margin: 20px 0;">
        <h2 style="margin: 0 0 10px; color: #92400E;">{{{{auction_title}}}}</h2>
        <div style="display: flex; align-items: center; justify-content: center; gap: 20px; margin: 15px 0;">
          <span style="color: #9CA3AF; text-decoration: line-through; font-size: 18px;">${{{{old_price}}}}</span>
          <span style="color: #B45309; font-size: 24px; font-weight: bold;">→</span>
          <span style="color: #059669; font-size: 24px; font-weight: bold;">${{{{new_price}}}}</span>
        </div>
        <p style="text-align: center; color: #059669; font-weight: bold; margin: 0;">Save ${{{{savings}}}}!</p>
      </div>
      <div style="text-align: center; margin-top: 30px;">
        <a href="{{{{auction_link}}}}" style="display: inline-block; background: #F59E0B; color: white; padding: 14px 40px; text-decoration: none; border-radius: 6px; font-weight: bold;">View Reduced Price</a>
      </div>
    </div>
    <div style="background: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #eee;">
      <p style="color: #666; font-size: 12px; margin: 0;">You received this email from a BidVex seller.</p>
      <p style="margin: 10px 0 0; font-size: 12px;"><a href="{{{{unsubscribe_url}}}}" style="color: #999;">Unsubscribe</a></p>
    </div>
  </div>
</body>
</html>'''
        }
        
        return templates.get(template_key, templates["new_auction"])


# Singleton instance
_user_marketing_service = None

def get_user_marketing_service(db: AsyncIOMotorDatabase) -> UserEmailMarketingService:
    """Get or create the singleton service instance"""
    global _user_marketing_service
    if _user_marketing_service is None:
        _user_marketing_service = UserEmailMarketingService(db)
    return _user_marketing_service
