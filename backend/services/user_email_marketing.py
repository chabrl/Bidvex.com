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
    CustomArg
)

logger = logging.getLogger(__name__)

# Configuration
MARKETING_API_KEY = os.environ.get("SENDGRID_MARKETING_API_KEY") or os.environ.get("SENDGRID_API_KEY")
FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@bidvex.com")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://www.bidvex.com")

# Initialize client
marketing_client = None
if MARKETING_API_KEY and MARKETING_API_KEY != "SG.your-actual-sendgrid-key-here":
    marketing_client = SendGridAPIClient(MARKETING_API_KEY)

# Subscription limits (emails per month)
SUBSCRIPTION_LIMITS = {
    "free": 0,
    "premium": 5000,
    "vip": 50000
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
    
    def get_subscription_limit(self, tier: str) -> int:
        """Get monthly email limit for subscription tier"""
        return SUBSCRIPTION_LIMITS.get(tier.lower(), 0)
    
    def can_access_feature(self, tier: str) -> bool:
        """Check if user's subscription tier can access the feature"""
        return tier.lower() in ["premium", "vip"]
    
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
        """Get remaining email quota for the month"""
        limit = self.get_subscription_limit(tier)
        used = await self.get_monthly_usage(user_id)
        
        return {
            "limit": limit,
            "used": used,
            "remaining": max(0, limit - used),
            "can_send": used < limit if limit > 0 else False,
            "tier": tier
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
        consent_confirmed: bool = False
    ) -> Dict[str, Any]:
        """Add a single contact"""
        email = email.strip().lower()
        
        if not self.validate_email(email):
            raise ValueError(f"Invalid email format: {email}")
        
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
        consent_confirmed: bool = False
    ) -> Dict[str, Any]:
        """Add multiple contacts at once"""
        now = datetime.now(timezone.utc)
        
        # Get existing emails for this user
        existing = await self.contacts.distinct("email", {"user_id": user_id})
        existing_set = set(e.lower() for e in existing)
        
        added = []
        duplicates = []
        invalid = []
        
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
            "invalid_count": len(invalid)
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
        
        # Check quota
        quota = await self.get_remaining_quota(user_id, user_tier)
        if not quota["can_send"]:
            raise ValueError(f"Monthly email limit reached ({quota['limit']} emails)")
        
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
        
        # Check if within quota
        remaining = quota["remaining"]
        if len(recipients) > remaining:
            raise ValueError(f"Campaign has {len(recipients)} recipients but you only have {remaining} emails remaining this month")
        
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
            html_content = html_content.replace("{{unsubscribe_url}}",
                f"{FRONTEND_URL}/unsubscribe/user?user={user_id}&contact={contact['id']}")
            
            plain_content = campaign.get("plain_text_content", "")
            plain_content = plain_content.replace("{{name}}", name or "")
            plain_content = plain_content.replace("{{email}}", email)
            
            message = Mail(
                from_email=Email(FROM_EMAIL, "BidVex Auctions"),
                to_emails=To(email),
                subject=campaign["subject"],
                html_content=Content("text/html", html_content),
                plain_text_content=Content("text/plain", plain_content) if plain_content else None
            )
            
            tracking = TrackingSettings()
            tracking.click_tracking = ClickTracking(True, True)
            tracking.open_tracking = OpenTracking(True)
            message.tracking_settings = tracking
            
            personalization = Personalization()
            personalization.add_to(To(email))
            personalization.add_custom_arg(CustomArg("user_campaign_id", campaign["id"]))
            personalization.add_custom_arg(CustomArg("user_id", user_id))
            personalization.add_custom_arg(CustomArg("contact_id", contact["id"]))
            message.add_personalization(personalization)
            
            response = marketing_client.send(message)
            message_id = response.headers.get("X-Message-Id")
            
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
            logger.error(f"Send failed: {e}")
            
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


# Singleton instance
_user_marketing_service = None

def get_user_marketing_service(db: AsyncIOMotorDatabase) -> UserEmailMarketingService:
    """Get or create the singleton service instance"""
    global _user_marketing_service
    if _user_marketing_service is None:
        _user_marketing_service = UserEmailMarketingService(db)
    return _user_marketing_service
