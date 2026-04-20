"""
BidVex Email Marketing Service
Comprehensive email campaign management with audience segmentation,
scheduling, and SendGrid webhook tracking.
"""

import os
import uuid
import logging
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

# Email Marketing Configuration
# Use separate API key for marketing if available, else fall back to transactional
MARKETING_API_KEY = os.environ.get("SENDGRID_MARKETING_API_KEY") or os.environ.get("SENDGRID_API_KEY")
TRANSACTIONAL_API_KEY = os.environ.get("SENDGRID_API_KEY")
FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@bidvex.com")
FROM_NAME = os.environ.get("SENDGRID_FROM_NAME", "BidVex")
MARKETING_FROM_EMAIL = os.environ.get("SENDGRID_MARKETING_FROM_EMAIL") or FROM_EMAIL
MARKETING_FROM_NAME = os.environ.get("SENDGRID_MARKETING_FROM_NAME") or "BidVex Updates"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://www.bidvex.com")

# Initialize clients
marketing_client = None
transactional_client = None

if MARKETING_API_KEY and MARKETING_API_KEY != "SG.your-actual-sendgrid-key-here":
    marketing_client = SendGridAPIClient(MARKETING_API_KEY)
    logger.info("SendGrid Marketing client initialized")
else:
    logger.warning("SendGrid Marketing API key not configured")

if TRANSACTIONAL_API_KEY and TRANSACTIONAL_API_KEY != "SG.your-actual-sendgrid-key-here":
    transactional_client = SendGridAPIClient(TRANSACTIONAL_API_KEY)
    logger.info("SendGrid Transactional client initialized")


# Campaign status constants
CAMPAIGN_STATUS = {
    "DRAFT": "draft",
    "SCHEDULED": "scheduled",
    "SENDING": "sending",
    "SENT": "sent",
    "PAUSED": "paused",
    "CANCELLED": "cancelled",
    "FAILED": "failed"
}

# Audience segment filters
SEGMENT_FILTERS = {
    "subscription_tier": ["free", "premium", "vip"],
    "account_type": ["personal", "business"],
    "region": ["ON", "QC", "BC", "AB", "SK", "MB", "NS", "NB", "NL", "PE", "NT", "YT", "NU"],
    "activity_status": ["active", "inactive", "new"],
    "email_engagement": ["engaged", "unengaged", "never_opened"],
    "seller_status": ["verified", "pending", "none"],
    "user_role": ["buyers", "sellers", "partners"],
}


class EmailMarketingService:
    """
    Email Marketing Service for campaign management
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.campaigns = db.email_campaigns
        self.email_sends = db.email_sends
        self.email_events = db.email_events
        self.marketing_audit = db.marketing_audit_logs
        
    def is_configured(self) -> bool:
        """Check if marketing email is configured"""
        return marketing_client is not None
    
    def validate_email(self, email: str) -> bool:
        """Validate email format"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email.strip().lower()))
    
    def parse_email_list(self, email_text: str) -> List[str]:
        """
        Parse a string of emails (comma or newline separated) into a list
        Returns only valid, unique, lowercase emails
        """
        if not email_text or not email_text.strip():
            return []
        
        # Split by comma, newline, semicolon, or space
        import re
        raw_emails = re.split(r'[,\n;\s]+', email_text)
        
        # Validate and deduplicate
        valid_emails = set()
        for email in raw_emails:
            email = email.strip().lower()
            if email and self.validate_email(email):
                valid_emails.add(email)
        
        return list(valid_emails)
    
    def parse_csv_emails(self, csv_content: str) -> Dict[str, Any]:
        """
        Parse CSV content to extract emails
        Returns: {valid: [...], invalid: [...], duplicates: [...]}
        """
        import csv
        import io
        
        result = {
            "valid": [],
            "invalid": [],
            "duplicates": [],
            "total_rows": 0
        }
        
        try:
            reader = csv.DictReader(io.StringIO(csv_content))
            seen_emails = set()
            
            # Find email column (case-insensitive)
            email_column = None
            if reader.fieldnames:
                for field in reader.fieldnames:
                    if field.lower() in ['email', 'e-mail', 'email_address', 'emailaddress', 'mail']:
                        email_column = field
                        break
                # If no email column found, try first column
                if not email_column and reader.fieldnames:
                    email_column = reader.fieldnames[0]
            
            for row in reader:
                result["total_rows"] += 1
                email = row.get(email_column, "").strip().lower() if email_column else ""
                
                if not email:
                    continue
                
                if not self.validate_email(email):
                    result["invalid"].append(email)
                elif email in seen_emails:
                    result["duplicates"].append(email)
                else:
                    seen_emails.add(email)
                    result["valid"].append(email)
                    
        except Exception as e:
            logger.error(f"CSV parsing error: {e}")
            result["error"] = str(e)
        
        return result
    
    async def get_suppressed_emails(self) -> set:
        """
        Get set of emails that should not receive marketing emails:
        - Unsubscribed users
        - Bounced emails
        - Spam reporters
        """
        suppressed = set()
        
        # Get unsubscribed users
        unsubscribed = await self.db.users.find(
            {"marketing_unsubscribed": True},
            {"_id": 0, "email": 1}
        ).to_list(None)
        suppressed.update(u["email"].lower() for u in unsubscribed if u.get("email"))
        
        # Get bounced emails from email_events
        bounced = await self.email_events.distinct(
            "email",
            {"event_type": {"$in": ["bounce", "dropped", "spamreport"]}}
        )
        suppressed.update(e.lower() for e in bounced if e)
        
        return suppressed
    
    async def build_advanced_audience(
        self,
        filters: Dict[str, Any],
        manual_emails: List[str] = None,
        exclude_emails: List[str] = None,
        include_external: bool = True
    ) -> Dict[str, Any]:
        """
        Build complete audience with advanced targeting:
        
        Final Audience = (Segmented Users + Manual Emails) - Exclusions - Suppressed
        
        Args:
            filters: Standard segmentation filters
            manual_emails: List of manually added email addresses
            exclude_emails: List of emails to exclude
            include_external: Whether to include non-registered emails
            
        Returns:
            {
                "segmented_users": [...],  # Users from DB
                "manual_external": [...],   # Manual emails not in DB
                "excluded": [...],          # Emails excluded
                "suppressed": [...],        # Emails suppressed (unsubscribed/bounced)
                "final_count": int,
                "breakdown": {...}
            }
        """
        manual_emails = manual_emails or []
        exclude_emails = exclude_emails or []
        
        # Normalize all emails
        manual_emails = [e.strip().lower() for e in manual_emails if e and self.validate_email(e)]
        exclude_emails = [e.strip().lower() for e in exclude_emails if e and self.validate_email(e)]
        exclude_set = set(exclude_emails)
        
        # Get suppressed emails
        suppressed_set = await self.get_suppressed_emails()
        
        # Get segmented users from database
        query = await self.build_audience_query(filters)
        segmented_users = await self.db.users.find(
            query,
            {"_id": 0, "id": 1, "email": 1, "name": 1}
        ).to_list(None)
        
        # Build final recipient lists
        final_recipients = []
        excluded_list = []
        suppressed_list = []
        segmented_emails = set()
        
        # Process segmented users
        for user in segmented_users:
            email = user.get("email", "").lower()
            if not email:
                continue
                
            segmented_emails.add(email)
            
            if email in exclude_set:
                excluded_list.append({"email": email, "reason": "manually_excluded", "source": "segmented"})
            elif email in suppressed_set:
                suppressed_list.append({"email": email, "reason": "suppressed", "source": "segmented"})
            else:
                final_recipients.append({
                    "email": email,
                    "name": user.get("name"),
                    "user_id": user.get("id"),
                    "source": "segmented"
                })
        
        # Process manual emails
        manual_external = []
        for email in manual_emails:
            if email in exclude_set:
                excluded_list.append({"email": email, "reason": "manually_excluded", "source": "manual"})
            elif email in suppressed_set:
                suppressed_list.append({"email": email, "reason": "suppressed", "source": "manual"})
            elif email in segmented_emails:
                # Already included from segmentation, skip to avoid duplicates
                continue
            else:
                # Check if user exists in DB
                existing_user = await self.db.users.find_one(
                    {"email": {"$regex": f"^{email}$", "$options": "i"}},
                    {"_id": 0, "id": 1, "name": 1, "email": 1}
                )
                
                if existing_user:
                    final_recipients.append({
                        "email": email,
                        "name": existing_user.get("name"),
                        "user_id": existing_user.get("id"),
                        "source": "manual_existing"
                    })
                elif include_external:
                    manual_external.append(email)
                    final_recipients.append({
                        "email": email,
                        "name": None,
                        "user_id": None,
                        "source": "manual_external"
                    })
        
        return {
            "recipients": final_recipients,
            "excluded": excluded_list,
            "suppressed": suppressed_list,
            "manual_external": manual_external,
            "final_count": len(final_recipients),
            "breakdown": {
                "segmented_count": len([r for r in final_recipients if r["source"] == "segmented"]),
                "manual_existing_count": len([r for r in final_recipients if r["source"] == "manual_existing"]),
                "manual_external_count": len(manual_external),
                "excluded_count": len(excluded_list),
                "suppressed_count": len(suppressed_list)
            }
        }
    
    async def get_advanced_audience_preview(
        self,
        filters: Dict[str, Any],
        manual_emails: List[str] = None,
        exclude_emails: List[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Get preview of advanced audience with breakdown"""
        audience = await self.build_advanced_audience(
            filters=filters,
            manual_emails=manual_emails,
            exclude_emails=exclude_emails
        )
        
        # Limit preview
        preview = audience["recipients"][:limit]
        
        return {
            "count": audience["final_count"],
            "preview": preview,
            "breakdown": audience["breakdown"],
            "excluded_count": len(audience["excluded"]),
            "suppressed_count": len(audience["suppressed"]),
            "excluded_preview": audience["excluded"][:5],
            "suppressed_preview": audience["suppressed"][:5]
        }
    
    async def build_audience_query(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build MongoDB query from audience filters
        
        Filters:
        - subscription_tiers: List of tiers (free, premium, vip)
        - account_types: List of types (personal, business)
        - regions: List of province codes
        - activity_status: active (logged in last 30d), inactive (>30d), new (<7d)
        - email_engagement: engaged (opened in 90d), unengaged, never_opened
        - seller_status: verified, pending, none
        - exclude_unsubscribed: bool (default True)
        - min_created_date: datetime
        - max_created_date: datetime
        """
        query = {}
        conditions = []
        
        # Always exclude unsubscribed users unless explicitly included
        if filters.get("exclude_unsubscribed", True):
            conditions.append({
                "$or": [
                    {"marketing_unsubscribed": {"$ne": True}},
                    {"marketing_unsubscribed": {"$exists": False}}
                ]
            })
        
        # Must have valid email
        conditions.append({"email": {"$exists": True, "$ne": ""}})
        
        # Subscription tier filter
        if filters.get("subscription_tiers"):
            tiers = filters["subscription_tiers"]
            if "free" in tiers:
                # Free includes users without subscription_tier set
                conditions.append({
                    "$or": [
                        {"subscription_tier": {"$in": tiers}},
                        {"subscription_tier": {"$exists": False}}
                    ]
                })
            else:
                conditions.append({"subscription_tier": {"$in": tiers}})
        
        # Account type filter
        if filters.get("account_types"):
            conditions.append({"account_type": {"$in": filters["account_types"]}})
        
        # Region filter (province)
        if filters.get("regions"):
            conditions.append({"province": {"$in": filters["regions"]}})
        
        # Activity status
        if filters.get("activity_status"):
            now = datetime.now(timezone.utc)
            status = filters["activity_status"]
            
            if status == "active":
                # Logged in within last 30 days
                cutoff = now - timedelta(days=30)
                conditions.append({"last_login": {"$gte": cutoff.isoformat()}})
            elif status == "inactive":
                # Not logged in for 30+ days
                cutoff = now - timedelta(days=30)
                conditions.append({
                    "$or": [
                        {"last_login": {"$lt": cutoff.isoformat()}},
                        {"last_login": {"$exists": False}}
                    ]
                })
            elif status == "new":
                # Created within last 7 days
                cutoff = now - timedelta(days=7)
                conditions.append({"created_at": {"$gte": cutoff.isoformat()}})
        
        # Email engagement (based on email_events)
        if filters.get("email_engagement"):
            engagement = filters["email_engagement"]
            # This would require a lookup/aggregation, simplified for now
            if engagement == "engaged":
                conditions.append({"last_email_opened": {"$exists": True}})
            elif engagement == "never_opened":
                conditions.append({"last_email_opened": {"$exists": False}})
        
        # Seller status
        if filters.get("seller_status"):
            status = filters["seller_status"]
            if status == "verified":
                conditions.append({"seller_verified": True})
            elif status == "pending":
                conditions.append({
                    "seller_verified": {"$ne": True},
                    "seller_application_pending": True
                })
            elif status == "none":
                conditions.append({
                    "$or": [
                        {"seller_verified": {"$exists": False}},
                        {"seller_verified": False}
                    ],
                    "seller_application_pending": {"$ne": True}
                })
        
        # Date range filters
        if filters.get("min_created_date"):
            conditions.append({"created_at": {"$gte": filters["min_created_date"]}})
        if filters.get("max_created_date"):
            conditions.append({"created_at": {"$lte": filters["max_created_date"]}})

        # User role (buyers/sellers/partners) — dynamic based on activity
        if filters.get("user_role"):
            role = filters["user_role"]
            if role == "buyers":
                # Users who have placed at least one bid
                buyer_ids = await self.db.bids.distinct("user_id")
                if buyer_ids:
                    conditions.append({"id": {"$in": buyer_ids}})
                else:
                    conditions.append({"id": "__no_match__"})
            elif role == "sellers":
                # Users who have created at least one listing
                seller_ids = await self.db.listings.distinct("seller_id")
                multi_seller_ids = await self.db.multi_item_listings.distinct("seller_id")
                all_seller_ids = list(set(seller_ids + multi_seller_ids))
                if all_seller_ids:
                    conditions.append({"id": {"$in": all_seller_ids}})
                else:
                    conditions.append({"id": "__no_match__"})
            elif role == "partners":
                conditions.append({"is_partner": True})        
        # Combine all conditions
        if conditions:
            query["$and"] = conditions
        
        return query
    
    async def get_audience_count(self, filters: Dict[str, Any]) -> int:
        """Get count of users matching audience filters"""
        query = await self.build_audience_query(filters)
        return await self.db.users.count_documents(query)
    
    async def get_audience_preview(self, filters: Dict[str, Any], limit: int = 10) -> List[Dict]:
        """Get preview of users matching audience filters"""
        query = await self.build_audience_query(filters)
        users = await self.db.users.find(
            query, 
            {"_id": 0, "email": 1, "name": 1, "subscription_tier": 1, "province": 1, "account_type": 1}
        ).limit(limit).to_list(limit)
        return users
    
    async def calculate_final_audience_count(
        self,
        audience_filters: Dict[str, Any],
        manual_emails: List[str] = None,
        exclude_emails: List[str] = None
    ) -> Dict[str, Any]:
        """Calculate final audience count with advanced targeting"""
        audience = await self.build_advanced_audience(
            filters=audience_filters,
            manual_emails=manual_emails or [],
            exclude_emails=exclude_emails or []
        )
        return {
            "total": audience["final_count"],
            "breakdown": audience["breakdown"]
        }
    
    async def create_campaign(
        self,
        name: str,
        subject: str,
        html_content: str,
        plain_text_content: str,
        audience_filters: Dict[str, Any],
        admin_id: str,
        admin_email: str,
        scheduled_at: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        manual_emails: Optional[List[str]] = None,
        exclude_emails: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a new email campaign with advanced targeting support"""
        now = datetime.now(timezone.utc)
        
        # Parse and validate manual emails
        manual_emails = manual_emails or []
        exclude_emails = exclude_emails or []
        
        # Calculate advanced audience
        audience_result = await self.calculate_final_audience_count(
            audience_filters=audience_filters,
            manual_emails=manual_emails,
            exclude_emails=exclude_emails
        )
        
        campaign = {
            "id": str(uuid.uuid4()),
            "name": name,
            "subject": subject,
            "html_content": html_content,
            "plain_text_content": plain_text_content,
            "audience_filters": audience_filters,
            "manual_emails": manual_emails,
            "exclude_emails": exclude_emails,
            "audience_count": audience_result["total"],
            "audience_breakdown": audience_result["breakdown"],
            "from_email": from_email or MARKETING_FROM_EMAIL,
            "from_name": from_name or MARKETING_FROM_NAME,
            "reply_to": reply_to,
            "status": CAMPAIGN_STATUS["SCHEDULED"] if scheduled_at else CAMPAIGN_STATUS["DRAFT"],
            "scheduled_at": scheduled_at,
            "created_by": admin_id,
            "created_by_email": admin_email,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "sent_at": None,
            "completed_at": None,
            "stats": {
                "total_recipients": 0,
                "sent": 0,
                "delivered": 0,
                "opened": 0,
                "clicked": 0,
                "bounced": 0,
                "unsubscribed": 0,
                "spam_reports": 0
            }
        }
        
        await self.campaigns.insert_one(campaign)
        
        # Audit log with advanced targeting details
        audit_details = {
            "name": name, 
            "audience_count": audience_result["total"],
            "breakdown": audience_result["breakdown"]
        }
        if manual_emails:
            audit_details["manual_emails_count"] = len(manual_emails)
        if exclude_emails:
            audit_details["exclude_emails_count"] = len(exclude_emails)
        
        await self._log_audit(
            action="campaign_created",
            campaign_id=campaign["id"],
            admin_id=admin_id,
            admin_email=admin_email,
            details=audit_details
        )
        
        return {k: v for k, v in campaign.items() if k != "_id"}
    
    async def update_campaign(
        self,
        campaign_id: str,
        updates: Dict[str, Any],
        admin_id: str,
        admin_email: str
    ) -> Dict[str, Any]:
        """Update a draft campaign with advanced targeting support"""
        campaign = await self.campaigns.find_one({"id": campaign_id})
        if not campaign:
            raise ValueError("Campaign not found")
        
        if campaign["status"] not in [CAMPAIGN_STATUS["DRAFT"], CAMPAIGN_STATUS["SCHEDULED"]]:
            raise ValueError("Can only edit draft or scheduled campaigns")
        
        # Recalculate audience if filters, manual_emails, or exclude_emails changed
        recalculate = any(key in updates for key in ["audience_filters", "manual_emails", "exclude_emails"])
        
        if recalculate:
            audience_filters = updates.get("audience_filters", campaign.get("audience_filters", {}))
            manual_emails = updates.get("manual_emails", campaign.get("manual_emails", []))
            exclude_emails = updates.get("exclude_emails", campaign.get("exclude_emails", []))
            
            audience_result = await self.calculate_final_audience_count(
                audience_filters=audience_filters,
                manual_emails=manual_emails,
                exclude_emails=exclude_emails
            )
            updates["audience_count"] = audience_result["total"]
            updates["audience_breakdown"] = audience_result["breakdown"]
        
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await self.campaigns.update_one(
            {"id": campaign_id},
            {"$set": updates}
        )
        
        # Audit log
        await self._log_audit(
            action="campaign_updated",
            campaign_id=campaign_id,
            admin_id=admin_id,
            admin_email=admin_email,
            details={"updated_fields": list(updates.keys())}
        )
        
        return await self.get_campaign(campaign_id)
    
    async def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get campaign by ID"""
        campaign = await self.campaigns.find_one({"id": campaign_id}, {"_id": 0})
        return campaign
    
    async def list_campaigns(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """List campaigns with optional status filter"""
        query = {}
        if status:
            query["status"] = status
        
        campaigns = await self.campaigns.find(
            query, {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        return campaigns
    
    async def send_test_email(
        self,
        campaign_id: str,
        test_email: str,
        admin_id: str,
        admin_email: str
    ) -> Dict[str, Any]:
        """Send test email to preview campaign"""
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        
        if not marketing_client:
            logger.warning(f"[TEST EMAIL] To: {test_email}, Subject: {campaign['subject']}")
            return {"status": "logged", "message": "SendGrid not configured - email logged only"}
        
        try:
            plain_text = campaign.get("plain_text_content") or "View this email in HTML"
            message = Mail(
                from_email=Email(campaign["from_email"], campaign["from_name"]),
                to_emails=To(test_email),
                subject=f"[TEST] {campaign['subject']}",
                html_content=Content("text/html", campaign["html_content"]),
                plain_text_content=Content("text/plain", plain_text)
            )
            
            # Add tracking
            tracking = TrackingSettings()
            tracking.click_tracking = ClickTracking(True, True)
            tracking.open_tracking = OpenTracking(True)
            message.tracking_settings = tracking
            
            response = marketing_client.send(message)
            
            # Audit log
            await self._log_audit(
                action="test_email_sent",
                campaign_id=campaign_id,
                admin_id=admin_id,
                admin_email=admin_email,
                details={"test_recipient": test_email, "status_code": response.status_code}
            )
            
            return {
                "status": "sent",
                "message": f"Test email sent to {test_email}",
                "status_code": response.status_code
            }
        except Exception as e:
            logger.error(f"Failed to send test email: {e}")
            return {"status": "error", "message": str(e)}
    
    async def schedule_campaign(
        self,
        campaign_id: str,
        scheduled_at: str,
        admin_id: str,
        admin_email: str
    ) -> Dict[str, Any]:
        """Schedule a campaign for sending"""
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        
        if campaign["status"] not in [CAMPAIGN_STATUS["DRAFT"], CAMPAIGN_STATUS["SCHEDULED"]]:
            raise ValueError("Campaign cannot be scheduled in current status")
        
        # Validate scheduled time is in the future
        scheduled_dt = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
        if scheduled_dt <= datetime.now(timezone.utc):
            raise ValueError("Scheduled time must be in the future")
        
        await self.campaigns.update_one(
            {"id": campaign_id},
            {"$set": {
                "status": CAMPAIGN_STATUS["SCHEDULED"],
                "scheduled_at": scheduled_at,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        await self._log_audit(
            action="campaign_scheduled",
            campaign_id=campaign_id,
            admin_id=admin_id,
            admin_email=admin_email,
            details={"scheduled_at": scheduled_at}
        )
        
        return await self.get_campaign(campaign_id)
    
    async def send_campaign_now(
        self,
        campaign_id: str,
        admin_id: str,
        admin_email: str
    ) -> Dict[str, Any]:
        """Send campaign immediately"""
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        
        if campaign["status"] not in [CAMPAIGN_STATUS["DRAFT"], CAMPAIGN_STATUS["SCHEDULED"]]:
            raise ValueError("Campaign cannot be sent in current status")
        
        # Update status to sending
        now = datetime.now(timezone.utc)
        await self.campaigns.update_one(
            {"id": campaign_id},
            {"$set": {
                "status": CAMPAIGN_STATUS["SENDING"],
                "sent_at": now.isoformat(),
                "updated_at": now.isoformat()
            }}
        )
        
        await self._log_audit(
            action="campaign_send_started",
            campaign_id=campaign_id,
            admin_id=admin_id,
            admin_email=admin_email,
            details={}
        )
        
        # Execute sending in background
        result = await self._execute_campaign_send(campaign_id)
        
        return result
    
    async def _execute_campaign_send(self, campaign_id: str) -> Dict[str, Any]:
        """Execute the actual campaign send with advanced targeting"""
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            return {"status": "error", "message": "Campaign not found"}
        
        # Use advanced audience builder to get final recipients
        audience = await self.build_advanced_audience(
            filters=campaign.get("audience_filters", {}),
            manual_emails=campaign.get("manual_emails", []),
            exclude_emails=campaign.get("exclude_emails", [])
        )
        
        recipients = audience["recipients"]
        total = len(recipients)
        sent = 0
        failed = 0
        
        logger.info(f"Starting campaign {campaign_id} send to {total} recipients")
        logger.info(f"Audience breakdown: {audience['breakdown']}")
        
        # Track sent emails to prevent duplicates
        sent_emails = set()
        
        for recipient in recipients:
            email = recipient["email"].lower()
            
            # Skip if already sent (shouldn't happen but safety check)
            if email in sent_emails:
                logger.warning(f"Skipping duplicate email: {email}")
                continue
            
            sent_emails.add(email)
            
            try:
                result = await self._send_campaign_email(campaign, recipient)
                if result["success"]:
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Failed to send to {email}: {e}")
                failed += 1
        
        # Update campaign stats
        now = datetime.now(timezone.utc)
        await self.campaigns.update_one(
            {"id": campaign_id},
            {"$set": {
                "status": CAMPAIGN_STATUS["SENT"],
                "completed_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "stats.total_recipients": total,
                "stats.sent": sent,
                "stats.failed": failed,
                "stats.segmented_count": audience["breakdown"]["segmented_count"],
                "stats.manual_existing_count": audience["breakdown"]["manual_existing_count"],
                "stats.manual_external_count": audience["breakdown"]["manual_external_count"],
                "stats.excluded_count": audience["breakdown"]["excluded_count"],
                "stats.suppressed_count": audience["breakdown"]["suppressed_count"]
            }}
        )
        
        logger.info(f"Campaign {campaign_id} completed: {sent}/{total} sent, {failed} failed")
        
        return {
            "status": "completed",
            "total": total,
            "sent": sent,
            "failed": failed,
            "breakdown": audience["breakdown"]
        }
    
    async def _send_campaign_email(
        self,
        campaign: Dict[str, Any],
        recipient: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send campaign email to a single recipient (user or external)"""
        email = recipient["email"]
        name = recipient.get("name", "")
        user_id = recipient.get("user_id")
        source = recipient.get("source", "unknown")
        
        if not marketing_client:
            logger.info(f"[CAMPAIGN EMAIL] To: {email}, Campaign: {campaign['id']}, Source: {source}")
            
            # Still record the send
            await self.email_sends.insert_one({
                "id": str(uuid.uuid4()),
                "campaign_id": campaign["id"],
                "user_id": user_id,
                "email": email,
                "source": source,
                "status": "logged",
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "message_id": None
            })
            
            return {"success": True, "logged": True}
        
        try:
            # Personalize content
            html_content = campaign["html_content"]
            html_content = html_content.replace("{{name}}", name or "")
            html_content = html_content.replace("{{email}}", email)
            unsubscribe_token = user_id or email
            html_content = html_content.replace("{{unsubscribe_url}}", 
                f"{FRONTEND_URL}/unsubscribe?token={unsubscribe_token}")
            
            plain_content = campaign.get("plain_text_content") or ""
            plain_content = plain_content.replace("{{name}}", name or "")
            plain_content = plain_content.replace("{{email}}", email)
            
            message = Mail()
            message.from_email = Email(campaign["from_email"], campaign["from_name"])
            message.subject = campaign["subject"]
            
            # Single personalization with recipient + custom tracking args
            personalization = Personalization()
            personalization.add_to(To(email))
            personalization.add_custom_arg(CustomArg("campaign_id", campaign["id"]))
            if user_id:
                personalization.add_custom_arg(CustomArg("user_id", user_id))
            personalization.add_custom_arg(CustomArg("source", source))
            message.add_personalization(personalization)
            
            message.add_content(Content("text/plain", plain_content or "View this email in HTML"))
            message.add_content(Content("text/html", html_content))
            
            # Add tracking
            tracking = TrackingSettings()
            tracking.click_tracking = ClickTracking(True, True)
            tracking.open_tracking = OpenTracking(True)
            message.tracking_settings = tracking
            
            response = marketing_client.send(message)
            message_id = response.headers.get("X-Message-Id")
            
            # Record the send
            await self.email_sends.insert_one({
                "id": str(uuid.uuid4()),
                "campaign_id": campaign["id"],
                "user_id": user_id,
                "email": email,
                "source": source,
                "status": "sent",
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "message_id": message_id,
                "status_code": response.status_code
            })
            
            return {"success": True, "message_id": message_id}
            
        except Exception as e:
            logger.error(f"Send failed for {email}: {e}")
            
            await self.email_sends.insert_one({
                "id": str(uuid.uuid4()),
                "campaign_id": campaign["id"],
                "user_id": user_id,
                "email": email,
                "source": source,
                "status": "failed",
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            })
            
            return {"success": False, "error": str(e)}
    
    async def cancel_campaign(
        self,
        campaign_id: str,
        admin_id: str,
        admin_email: str,
        reason: str
    ) -> Dict[str, Any]:
        """Cancel a scheduled campaign"""
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        
        if campaign["status"] != CAMPAIGN_STATUS["SCHEDULED"]:
            raise ValueError("Only scheduled campaigns can be cancelled")
        
        await self.campaigns.update_one(
            {"id": campaign_id},
            {"$set": {
                "status": CAMPAIGN_STATUS["CANCELLED"],
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
                "cancelled_by": admin_id,
                "cancel_reason": reason,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        await self._log_audit(
            action="campaign_cancelled",
            campaign_id=campaign_id,
            admin_id=admin_id,
            admin_email=admin_email,
            details={"reason": reason}
        )
        
        return await self.get_campaign(campaign_id)
    
    async def process_webhook_event(self, event: Dict[str, Any]) -> None:
        """
        Process SendGrid webhook event
        
        Event types: delivered, open, click, bounce, dropped, 
                     spam_report, unsubscribe, group_unsubscribe
        """
        event_type = event.get("event")
        email = event.get("email")
        timestamp = event.get("timestamp")
        
        # Get campaign_id from custom args if present
        campaign_id = None
        user_id = None
        if "campaign_id" in event:
            campaign_id = event["campaign_id"]
        if "user_id" in event:
            user_id = event["user_id"]
        
        # Store event
        await self.email_events.insert_one({
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "email": email,
            "campaign_id": campaign_id,
            "user_id": user_id,
            "message_id": event.get("sg_message_id"),
            "timestamp": datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat() if timestamp else datetime.now(timezone.utc).isoformat(),
            "url": event.get("url"),  # For click events
            "useragent": event.get("useragent"),
            "ip": event.get("ip"),
            "reason": event.get("reason"),  # For bounce/dropped
            "raw_event": event,
            "processed_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Update campaign stats if we have campaign_id
        if campaign_id:
            stat_field = None
            if event_type == "delivered":
                stat_field = "stats.delivered"
            elif event_type == "open":
                stat_field = "stats.opened"
            elif event_type == "click":
                stat_field = "stats.clicked"
            elif event_type in ["bounce", "dropped"]:
                stat_field = "stats.bounced"
            elif event_type == "spamreport":
                stat_field = "stats.spam_reports"
            elif event_type in ["unsubscribe", "group_unsubscribe"]:
                stat_field = "stats.unsubscribed"
            
            if stat_field:
                await self.campaigns.update_one(
                    {"id": campaign_id},
                    {"$inc": {stat_field: 1}}
                )
        
        # Handle unsubscribe - update user
        if event_type in ["unsubscribe", "group_unsubscribe"] and email:
            await self.db.users.update_one(
                {"email": email},
                {"$set": {
                    "marketing_unsubscribed": True,
                    "marketing_unsubscribed_at": datetime.now(timezone.utc).isoformat()
                }}
            )
        
        # Track engagement for user
        if event_type == "open" and email:
            await self.db.users.update_one(
                {"email": email},
                {"$set": {"last_email_opened": datetime.now(timezone.utc).isoformat()}}
            )
        
        logger.info(f"Processed webhook event: {event_type} for {email}")
    
    async def get_campaign_stats(self, campaign_id: str) -> Dict[str, Any]:
        """Get detailed campaign statistics"""
        campaign = await self.get_campaign(campaign_id)
        if not campaign:
            raise ValueError("Campaign not found")
        
        stats = campaign.get("stats", {})
        
        # Calculate rates
        total = stats.get("sent", 0) or 1  # Avoid division by zero
        
        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign["name"],
            "status": campaign["status"],
            "sent_at": campaign.get("sent_at"),
            "completed_at": campaign.get("completed_at"),
            "stats": {
                **stats,
                "delivery_rate": round((stats.get("delivered", 0) / total) * 100, 2),
                "open_rate": round((stats.get("opened", 0) / total) * 100, 2),
                "click_rate": round((stats.get("clicked", 0) / total) * 100, 2),
                "bounce_rate": round((stats.get("bounced", 0) / total) * 100, 2),
                "unsubscribe_rate": round((stats.get("unsubscribed", 0) / total) * 100, 2)
            }
        }
    
    async def get_email_events(
        self,
        campaign_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get email events with optional filters"""
        query = {}
        if campaign_id:
            query["campaign_id"] = campaign_id
        if event_type:
            query["event_type"] = event_type
        
        events = await self.email_events.find(
            query, {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        return events
    
    async def _log_audit(
        self,
        action: str,
        campaign_id: str,
        admin_id: str,
        admin_email: str,
        details: Dict[str, Any]
    ) -> None:
        """Log marketing action for audit trail"""
        await self.marketing_audit.insert_one({
            "id": str(uuid.uuid4()),
            "action": action,
            "campaign_id": campaign_id,
            "admin_id": admin_id,
            "admin_email": admin_email,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })


    async def get_global_dashboard_stats(self) -> Dict[str, Any]:
        """Aggregate stats across all campaigns for the marketing dashboard."""
        pipeline = [
            {"$match": {"status": {"$in": ["sent", "sending"]}}},
            {"$group": {
                "_id": None,
                "total_campaigns": {"$sum": 1},
                "total_sent": {"$sum": "$stats.sent"},
                "total_opened": {"$sum": "$stats.opened"},
                "total_clicked": {"$sum": "$stats.clicked"},
                "total_bounced": {"$sum": "$stats.bounced"},
                "total_unsubscribed": {"$sum": "$stats.unsubscribed"},
            }},
        ]
        result = await self.campaigns.aggregate(pipeline).to_list(1)
        if not result:
            total_campaigns = await self.campaigns.count_documents({})
            return {
                "total_campaigns": total_campaigns,
                "total_sent": 0, "total_opened": 0, "total_clicked": 0,
                "total_bounced": 0, "total_unsubscribed": 0,
                "open_rate": 0, "click_rate": 0,
            }

        r = result[0]
        sent = r.get("total_sent", 0) or 1
        return {
            "total_campaigns": r.get("total_campaigns", 0),
            "total_sent": r.get("total_sent", 0),
            "total_opened": r.get("total_opened", 0),
            "total_clicked": r.get("total_clicked", 0),
            "total_bounced": r.get("total_bounced", 0),
            "total_unsubscribed": r.get("total_unsubscribed", 0),
            "open_rate": round((r.get("total_opened", 0) / sent) * 100, 1),
            "click_rate": round((r.get("total_clicked", 0) / sent) * 100, 1),
        }

    async def sync_registered_contacts(self) -> Dict[str, Any]:
        """Auto-sync all registered users into the contacts pool with role tags."""
        users = await self.db.users.find(
            {"email": {"$exists": True, "$ne": ""}},
            {"_id": 0, "id": 1, "email": 1, "name": 1,
             "preferred_language": 1, "language_preference": 1,
             "is_partner": 1, "subscription_tier": 1, "province": 1}
        ).to_list(None)

        # Determine buyer/seller/partner roles
        buyer_ids = set(await self.db.bids.distinct("user_id"))
        seller_ids = set(await self.db.listings.distinct("seller_id"))
        multi_seller_ids = set(await self.db.multi_item_listings.distinct("seller_id"))
        all_seller_ids = seller_ids | multi_seller_ids

        synced = 0
        for u in users:
            uid = u.get("id", "")
            roles = []
            if uid in buyer_ids:
                roles.append("buyer")
            if uid in all_seller_ids:
                roles.append("seller")
            if u.get("is_partner"):
                roles.append("partner")
            if not roles:
                roles.append("user")

            lang = u.get("preferred_language", u.get("language_preference", "en"))
            await self.db.marketing_contacts.update_one(
                {"email": u["email"].lower()},
                {"$set": {
                    "email": u["email"].lower(),
                    "name": u.get("name", ""),
                    "language": lang[:2] if lang else "en",
                    "user_id": uid,
                    "user_roles": roles,
                    "source": "registered",
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True,
            )
            synced += 1

        return {"synced": synced, "total_users": len(users)}


# Singleton instance
_marketing_service = None

def get_marketing_service(db: AsyncIOMotorDatabase) -> EmailMarketingService:
    """Get or create the singleton marketing service instance"""
    global _marketing_service
    if _marketing_service is None:
        _marketing_service = EmailMarketingService(db)
    return _marketing_service
