"""
BidVex Marketing Router
Handles both Admin Email Marketing and Client Email Marketing functionality
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import logging
import uuid
import csv
import io

logger = logging.getLogger(__name__)

marketing_router = APIRouter(tags=["Marketing"])
security = HTTPBearer(auto_error=False)

# Database and service instances
_db = None
_get_current_user = None
_get_marketing_service = None
_get_user_marketing_service = None
_SEGMENT_FILTERS = None
_CAMPAIGN_STATUS = None
_SUBSCRIPTION_LIMITS = None


def set_marketing_db(db_instance):
    """Set database instance"""
    global _db
    _db = db_instance


def set_marketing_auth(get_current_user_func):
    """Set authentication function"""
    global _get_current_user
    _get_current_user = get_current_user_func


def set_marketing_services(
    marketing_service_func,
    user_marketing_service_func,
    segment_filters,
    campaign_status,
    subscription_limits
):
    """Set marketing service functions and constants"""
    global _get_marketing_service, _get_user_marketing_service
    global _SEGMENT_FILTERS, _CAMPAIGN_STATUS, _SUBSCRIPTION_LIMITS
    _get_marketing_service = marketing_service_func
    _get_user_marketing_service = user_marketing_service_func
    _SEGMENT_FILTERS = segment_filters
    _CAMPAIGN_STATUS = campaign_status
    _SUBSCRIPTION_LIMITS = subscription_limits


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


# ========== HELPER: Check Admin Role ==========
async def require_admin(credentials: HTTPAuthorizationCredentials):
    """Verify user has admin role"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    current_user = await _get_current_user(credentials)
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ========================================
# ADMIN EMAIL MARKETING ENDPOINTS
# ========================================

@marketing_router.get("/admin/marketing/segment-filters")
async def get_segment_filters(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get available audience segment filters"""
    await require_admin(credentials)
    return _SEGMENT_FILTERS


@marketing_router.post("/admin/marketing/audience/preview")
async def preview_audience(
    filters: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Preview audience count and sample with given filters"""
    await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    result = await marketing.get_audience_preview(filters)
    return result


@marketing_router.post("/admin/marketing/audience/advanced-preview")
async def advanced_audience_preview(
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Preview audience with advanced targeting (manual emails, exclusions)"""
    await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    result = await marketing.get_advanced_audience_preview(
        filters=data.get("filters", {}),
        manual_emails=data.get("manual_emails", []),
        exclude_emails=data.get("exclude_emails", [])
    )
    return result


@marketing_router.post("/admin/marketing/parse-emails")
async def parse_email_list(
    data: Dict[str, str],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Parse and validate a list of emails from text input"""
    await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    text = data.get("text", "")
    result = await marketing.parse_email_list(text)
    return result


@marketing_router.post("/admin/marketing/parse-csv")
async def parse_csv_emails(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Parse emails from uploaded CSV file"""
    await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    content = await file.read()
    result = await marketing.parse_csv_emails(content.decode('utf-8'))
    return result


@marketing_router.post("/admin/marketing/check-suppressed")
async def check_suppressed_emails(
    data: Dict[str, List[str]],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Check which emails are on suppression list"""
    await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    emails = data.get("emails", [])
    result = await marketing.check_suppressed(emails)
    return result


@marketing_router.post("/admin/marketing/campaigns")
async def create_campaign(
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create a new email campaign"""
    admin = await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    campaign = await marketing.create_campaign(
        created_by=admin.id,
        **data
    )
    return campaign


@marketing_router.get("/admin/marketing/campaigns")
async def list_campaigns(
    status: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """List all email campaigns"""
    await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    result = await marketing.list_campaigns(status=status, limit=limit, skip=skip)
    return result


@marketing_router.get("/admin/marketing/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get single campaign details"""
    await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    campaign = await marketing.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@marketing_router.put("/admin/marketing/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update a draft or scheduled campaign"""
    admin = await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    try:
        campaign = await marketing.update_campaign(campaign_id, admin.id, data)
        return campaign
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@marketing_router.post("/admin/marketing/campaigns/{campaign_id}/test")
async def send_test_email(
    campaign_id: str,
    data: Dict[str, str],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Send test email for a campaign"""
    admin = await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    test_email = data.get("email")
    if not test_email:
        raise HTTPException(status_code=400, detail="Test email address required")
    
    try:
        result = await marketing.send_test_email(campaign_id, test_email, admin.id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@marketing_router.post("/admin/marketing/campaigns/{campaign_id}/schedule")
async def schedule_campaign(
    campaign_id: str,
    data: Dict[str, str],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Schedule a campaign for future sending"""
    admin = await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    scheduled_time = data.get("scheduled_time")
    if not scheduled_time:
        raise HTTPException(status_code=400, detail="Scheduled time required")
    
    try:
        campaign = await marketing.schedule_campaign(campaign_id, scheduled_time, admin.id)
        return campaign
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@marketing_router.post("/admin/marketing/campaigns/{campaign_id}/send")
async def send_campaign_now(
    campaign_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Send campaign immediately"""
    admin = await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    try:
        result = await marketing.send_campaign(campaign_id, admin.id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@marketing_router.post("/admin/marketing/campaigns/{campaign_id}/cancel")
async def cancel_campaign(
    campaign_id: str,
    data: Dict[str, str],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Cancel a scheduled campaign"""
    admin = await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    reason = data.get("reason")
    if not reason:
        raise HTTPException(status_code=400, detail="Cancellation reason required")
    
    try:
        campaign = await marketing.cancel_campaign(campaign_id, admin.id, reason)
        return campaign
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@marketing_router.get("/admin/marketing/campaigns/{campaign_id}/stats")
async def get_campaign_stats(
    campaign_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get campaign statistics"""
    await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    stats = await marketing.get_campaign_stats(campaign_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return stats


@marketing_router.get("/admin/marketing/campaigns/{campaign_id}/events")
async def get_campaign_events(
    campaign_id: str,
    event_type: Optional[str] = None,
    limit: int = 100,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get email events for a campaign"""
    await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    events = await marketing.get_campaign_events(campaign_id, event_type, limit)
    return {"events": events}


@marketing_router.get("/admin/marketing/audit")
async def get_marketing_audit_log(
    limit: int = 50,
    skip: int = 0,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get marketing audit log"""
    await require_admin(credentials)
    db = get_db()
    marketing = _get_marketing_service(db)
    
    logs = await marketing.get_audit_log(limit=limit, skip=skip)
    return {"logs": logs}


@marketing_router.get("/admin/marketing/config")
async def get_marketing_config(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get marketing configuration status"""
    import os
    await require_admin(credentials)
    
    return {
        "sendgrid_configured": bool(os.environ.get("SENDGRID_MARKETING_API_KEY")),
        "marketing_from_email": os.environ.get("SENDGRID_MARKETING_FROM_EMAIL", ""),
        "marketing_from_name": os.environ.get("SENDGRID_MARKETING_FROM_NAME", "")
    }


# ========================================
# USER/CLIENT EMAIL MARKETING ENDPOINTS
# ========================================

@marketing_router.get("/user/marketing/access")
async def check_user_marketing_access(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Check user's access to email marketing feature"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    tier = current_user.subscription_tier or "free"
    
    can_send = user_marketing.can_access_feature(tier)
    quota = await user_marketing.get_remaining_quota(current_user.id, tier)
    contact_limit = await user_marketing.check_contact_limit(current_user.id, tier)
    
    return {
        "can_access": True,
        "can_send": can_send,
        "subscription_tier": tier,
        "limits": user_marketing.get_subscription_limits(tier),
        "quota": quota,
        "contact_limit": contact_limit,
        "upgrade_message": "Upgrade to Premium or VIP to send auctions to your client list." if not can_send else None
    }


@marketing_router.get("/user/marketing/contacts")
async def get_user_contacts(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get user's contacts"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    
    result = await user_marketing.get_contacts(
        user_id=current_user.id,
        status=status,
        search=search,
        limit=limit,
        skip=skip
    )
    return result


@marketing_router.get("/user/marketing/contacts/stats")
async def get_user_contact_stats(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get contact statistics"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    tier = current_user.subscription_tier or "free"
    
    stats = await user_marketing.get_contact_stats(current_user.id)
    contact_limit = await user_marketing.check_contact_limit(current_user.id, tier)
    
    return {
        **stats,
        "contact_limit": contact_limit
    }


class UserContactCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    tags: Optional[List[str]] = None
    consent_confirmed: bool = False


@marketing_router.post("/user/marketing/contacts")
async def add_user_contact(
    data: UserContactCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Add a single contact"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    tier = current_user.subscription_tier or "free"
    
    try:
        contact = await user_marketing.add_contact(
            user_id=current_user.id,
            email=data.email,
            name=data.name,
            tags=data.tags,
            consent_confirmed=data.consent_confirmed,
            user_tier=tier
        )
        return contact
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class UserContactBulk(BaseModel):
    emails: List[str]
    consent_confirmed: bool = False


@marketing_router.post("/user/marketing/contacts/bulk")
async def add_user_contacts_bulk(
    data: UserContactBulk,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Add multiple contacts at once"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    tier = current_user.subscription_tier or "free"
    
    result = await user_marketing.add_contacts_bulk(
        user_id=current_user.id,
        emails=data.emails,
        consent_confirmed=data.consent_confirmed,
        user_tier=tier
    )
    return result


@marketing_router.post("/user/marketing/contacts/parse")
async def parse_user_contact_emails(
    data: Dict[str, str],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Parse email list text"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    
    text = data.get("text", "")
    result = user_marketing.parse_email_list(text)
    return result


@marketing_router.post("/user/marketing/contacts/csv")
async def upload_user_contacts_csv(
    file: UploadFile = File(...),
    consent_confirmed: bool = False,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Upload contacts from CSV file"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    tier = current_user.subscription_tier or "free"
    
    content = await file.read()
    result = await user_marketing.import_csv_contacts(
        user_id=current_user.id,
        csv_content=content.decode('utf-8'),
        consent_confirmed=consent_confirmed,
        user_tier=tier
    )
    return result


@marketing_router.get("/user/marketing/contacts/{contact_id}")
async def get_user_contact(
    contact_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get single contact"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    
    contact = await user_marketing.get_contact(current_user.id, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@marketing_router.put("/user/marketing/contacts/{contact_id}")
async def update_user_contact(
    contact_id: str,
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update a contact"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    
    try:
        contact = await user_marketing.update_contact(current_user.id, contact_id, data)
        return contact
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@marketing_router.delete("/user/marketing/contacts/{contact_id}")
async def delete_user_contact(
    contact_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete a contact"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    
    try:
        await user_marketing.delete_contact(current_user.id, contact_id)
        return {"status": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@marketing_router.post("/user/marketing/contacts/delete-bulk")
async def delete_user_contacts_bulk(
    data: Dict[str, List[str]],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete multiple contacts"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    
    contact_ids = data.get("contact_ids", [])
    result = await user_marketing.delete_contacts_bulk(current_user.id, contact_ids)
    return result


# ========== USER CAMPAIGNS ==========

@marketing_router.get("/user/marketing/campaigns")
async def get_user_campaigns(
    status: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get user's marketing campaigns"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    tier = current_user.subscription_tier or "free"
    
    if not user_marketing.can_access_feature(tier):
        raise HTTPException(status_code=403, detail="Upgrade to Premium or VIP to access campaigns")
    
    result = await user_marketing.get_campaigns(current_user.id, status, limit, skip)
    return result


@marketing_router.post("/user/marketing/campaigns")
async def create_user_campaign(
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create a new campaign"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    tier = current_user.subscription_tier or "free"
    
    if not user_marketing.can_access_feature(tier):
        raise HTTPException(status_code=403, detail="Upgrade to Premium or VIP to create campaigns")
    
    try:
        campaign = await user_marketing.create_campaign(current_user.id, data)
        return campaign
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@marketing_router.get("/user/marketing/campaigns/{campaign_id}")
async def get_user_campaign(
    campaign_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get single campaign"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    
    campaign = await user_marketing.get_campaign(current_user.id, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@marketing_router.put("/user/marketing/campaigns/{campaign_id}")
async def update_user_campaign(
    campaign_id: str,
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update a draft campaign"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    
    try:
        campaign = await user_marketing.update_campaign(current_user.id, campaign_id, data)
        return campaign
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@marketing_router.post("/user/marketing/campaigns/{campaign_id}/confirm-consent")
async def confirm_campaign_consent(
    campaign_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Confirm consent for sending campaign"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    
    await user_marketing.confirm_campaign_consent(current_user.id, campaign_id)
    return {"status": "consent_confirmed"}


@marketing_router.post("/user/marketing/campaigns/{campaign_id}/send")
async def send_user_campaign(
    campaign_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Send a campaign"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    tier = current_user.subscription_tier or "free"
    
    if not user_marketing.can_access_feature(tier):
        raise HTTPException(status_code=403, detail="Upgrade to Premium or VIP to send campaigns")
    
    try:
        result = await user_marketing.send_campaign(current_user.id, campaign_id, tier)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@marketing_router.get("/user/marketing/campaigns/{campaign_id}/stats")
async def get_user_campaign_stats(
    campaign_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get campaign statistics"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    
    stats = await user_marketing.get_campaign_stats(current_user.id, campaign_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return stats


@marketing_router.get("/user/marketing/auction-template/{auction_id}")
async def get_auction_email_template(
    auction_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get pre-filled email template for an auction"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    
    # Find the auction
    auction = await db.listings.find_one({"id": auction_id, "seller_id": current_user.id})
    if not auction:
        auction = await db.multi_item_listings.find_one({"id": auction_id, "seller_id": current_user.id})
    
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found or not owned by you")
    
    user_marketing = _get_user_marketing_service(db)
    template = user_marketing.generate_auction_template(auction)
    
    return {
        "auction_id": auction_id,
        "auction_title": auction.get("title"),
        "html_template": template
    }


@marketing_router.get("/user/marketing/templates")
async def get_user_email_templates(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get pre-built email templates"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    templates = user_marketing.get_email_templates()
    return {"templates": templates}


# ========== UNSUBSCRIBE HANDLING ==========

@marketing_router.get("/unsubscribe/user")
async def handle_user_unsubscribe(
    user: str = Query(...),
    contact: str = Query(...)
):
    """Handle unsubscribe request from user marketing emails"""
    db = get_db()
    user_marketing = _get_user_marketing_service(db)
    
    success = await user_marketing.handle_unsubscribe(user, contact)
    
    if success:
        return {"status": "unsubscribed", "message": "You have been unsubscribed from this sender's list."}
    else:
        return {"status": "not_found", "message": "Contact not found or already unsubscribed."}
