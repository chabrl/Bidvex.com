"""
BidVex - Email Marketing (Admin + User)
Auto-extracted from server.py during P2 refactoring.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect, Body
import os
from deps import get_db, get_current_user, get_current_user_optional, User
from shared import (
    DEFAULT_EMAIL_TEMPLATES, EMAIL_TEMPLATE_CATEGORIES,
    DEFAULT_MARKETPLACE_SETTINGS, AFFILIATE_COMMISSION_RATE,
    generate_affiliate_code, get_email_templates, get_email_template_id,
    get_marketplace_settings, get_epoch_timestamp, get_server_timestamp,
    calculate_buyer_fees, calculate_seller_fees, calculate_stripe_fee_recovery,
    calculate_partner_checkout, calculate_standard_checkout,
    FeeCalculation, UserCreate, Category, Invoice, PaddleNumber,
    PaymentTransaction, SessionCreate, get_minimum_increment,
    STANDARD_BUYER_PREMIUM_RATE, STANDARD_SELLER_COMMISSION_RATE,
    PARTNER_PLATFORM_FEE_RATE, PARTNER_ANNUAL_ACCESS_FEE,
    STRIPE_PERCENTAGE_FEE, STRIPE_FIXED_FEE,
    AdvancedAudiencePreviewRequest, CampaignCreateRequest, CampaignUpdateRequest,
    UserContactCreateRequest, UserContactBulkRequest, UserCampaignCreateRequest,
)
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from pathlib import Path
import logging
import uuid
import os as _os
import json as _json

logger = logging.getLogger(__name__)

from services.email_marketing import get_marketing_service, SEGMENT_FILTERS, CAMPAIGN_STATUS
from services.user_email_marketing import get_user_marketing_service, SUBSCRIPTION_LIMITS

email_marketing_ext_router = APIRouter(tags=["Email Marketing"])


@email_marketing_ext_router.get("/admin/marketing/segment-filters")
async def get_segment_filters(current_user: User = Depends(get_current_user)):
    """Get available audience segment filter options"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return {
        "filters": SEGMENT_FILTERS,
        "campaign_statuses": list(CAMPAIGN_STATUS.values())
    }




@email_marketing_ext_router.post("/admin/marketing/audience/preview")
async def preview_audience(
    filters: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Preview audience matching basic filters"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    marketing = get_marketing_service(get_db())
    count = await marketing.get_audience_count(filters)
    preview = await marketing.get_audience_preview(filters, limit=10)
    
    return {
        "count": count,
        "preview": preview
    }




@email_marketing_ext_router.post("/admin/marketing/audience/advanced-preview")
async def preview_advanced_audience(
    data: AdvancedAudiencePreviewRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Preview advanced audience with manual emails and exclusions.

    iter241 Mission 5 — `recipient_type` field enforces strict gate:
      - "segment" / "all_users": ONLY DB segment, manual_emails ignored
      - "custom_list" / "csv_upload": ONLY manual_emails, no segment

    Returns:
    - Final count after (Segmented OR Manual) - Exclusions - Suppressed
    - Breakdown by source
    - Preview of recipients
    - List of excluded/suppressed emails
    """
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    marketing = get_marketing_service(get_db())

    # Accept either `audience_filters` (canonical iter241) or the older
    # `filters` field for back-compat.
    filters = data.audience_filters if data.audience_filters is not None else (data.filters or {})

    result = await marketing.get_advanced_audience_preview(
        filters=filters,
        manual_emails=data.manual_emails,
        exclude_emails=data.exclude_emails,
        limit=20,
        recipient_type=(data.recipient_type or "segment"),
    )

    return result


@email_marketing_ext_router.post("/admin/marketing/campaigns/preview-recipients")
async def preview_campaign_recipients(
    data: AdvancedAudiencePreviewRequest,
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    marketing = get_marketing_service(get_db())
    filters = data.audience_filters if data.audience_filters is not None else (data.filters or {})
    result = await marketing.get_advanced_audience_preview(
        filters=filters,
        manual_emails=data.manual_emails,
        exclude_emails=data.exclude_emails,
        limit=10,
        recipient_type=(data.recipient_type or "segment"),
    )
    # Return a smaller, UI-friendly shape.
    return {
        "recipient_type": data.recipient_type or "segment",
        "total_recipients": result.get("count", 0),
        "sample_emails": [r.get("email") for r in result.get("preview", [])],
        "breakdown": result.get("breakdown", {}),
        "excluded_count": result.get("excluded_count", 0),
        "suppressed_count": result.get("suppressed_count", 0),
    }


# iter241 Mission 6 — Campaign attachment upload constants.
_CAMPAIGN_ATTACHMENT_ROOT = "/app/backend/uploads/campaign_attachments"
_ALLOWED_ATTACHMENT_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}
_MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024  # 5 MB
_MAX_ATTACHMENTS_PER_CAMPAIGN = 3


@email_marketing_ext_router.post("/admin/marketing/campaigns/{campaign_id}/attachments")
async def upload_campaign_attachment(
    campaign_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """iter241 Mission 6 — Attach a file to a campaign.

    Validations:
      - max 3 attachments per campaign
      - PDF / JPG / PNG / DOCX only
      - 5 MB per file
    """
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    marketing = get_marketing_service(get_db())
    campaign = await marketing.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.get("status") not in ("draft", "scheduled", "DRAFT", "SCHEDULED"):
        raise HTTPException(
            status_code=400,
            detail="Attachments can only be added to draft or scheduled campaigns",
        )

    existing = campaign.get("attachments") or []
    if len(existing) >= _MAX_ATTACHMENTS_PER_CAMPAIGN:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {_MAX_ATTACHMENTS_PER_CAMPAIGN} attachments per campaign",
        )

    mime = (file.content_type or "").lower()
    if mime not in _ALLOWED_ATTACHMENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type {mime!r}. Allowed: PDF, JPG, PNG, DOCX",
        )

    body = await file.read()
    if len(body) > _MAX_ATTACHMENT_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds 5 MB limit ({len(body)} bytes)",
        )

    # Save to disk under /uploads/campaign_attachments/{campaign_id}/
    safe_name = (file.filename or "attachment").replace("/", "_").replace("\\", "_")
    target_dir = _os.path.join(_CAMPAIGN_ATTACHMENT_ROOT, campaign_id)
    _os.makedirs(target_dir, exist_ok=True)
    storage_path = _os.path.join(target_dir, f"{uuid.uuid4()}_{safe_name}")
    with open(storage_path, "wb") as fh:
        fh.write(body)

    new_att = {
        "id": str(uuid.uuid4()),
        "filename": safe_name,
        "mime_type": mime,
        "size_bytes": len(body),
        "storage_path": storage_path,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    existing.append(new_att)
    await get_db().email_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"attachments": existing, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"attachment": new_att, "total_attachments": len(existing)}


@email_marketing_ext_router.delete("/admin/marketing/campaigns/{campaign_id}/attachments/{attachment_id}")
async def delete_campaign_attachment(
    campaign_id: str,
    attachment_id: str,
    current_user: User = Depends(get_current_user),
):
    """iter241 Mission 6 — Remove an attachment from a campaign."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    marketing = get_marketing_service(get_db())
    campaign = await marketing.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    existing = campaign.get("attachments") or []
    keep = [a for a in existing if a.get("id") != attachment_id]
    removed = [a for a in existing if a.get("id") == attachment_id]
    if not removed:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Best-effort file delete.
    try:
        sp = removed[0].get("storage_path")
        if sp and _os.path.exists(sp):
            _os.remove(sp)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Attachment file delete failed: {e}")

    await get_db().email_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"attachments": keep, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"removed_id": attachment_id, "remaining": len(keep)}






@email_marketing_ext_router.post("/admin/marketing/parse-emails")
async def parse_email_list(
    data: Dict[str, str],
    current_user: User = Depends(get_current_user)
):
    """
    Parse and validate a list of emails from text input
    
    Request: {"emails": "email1@test.com, email2@test.com\\nemail3@test.com"}
    Returns: {"valid": [...], "invalid": [...], "count": N}
    """
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    email_text = data.get("emails", "")
    marketing = get_marketing_service(get_db())
    
    valid_emails = marketing.parse_email_list(email_text)
    
    # Find invalid entries
    import re
    raw_emails = re.split(r'[,\n;\s]+', email_text)
    invalid_emails = [e.strip() for e in raw_emails if e.strip() and e.strip().lower() not in [v.lower() for v in valid_emails]]
    
    return {
        "valid": valid_emails,
        "invalid": invalid_emails,
        "count": len(valid_emails)
    }




@email_marketing_ext_router.post("/admin/marketing/parse-csv")
async def parse_csv_emails(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Parse and validate emails from a CSV file upload
    
    Returns:
    - valid: List of valid emails
    - invalid: List of invalid entries
    - duplicates: List of duplicate emails
    - total_rows: Number of rows processed
    """
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    # Read file content
    try:
        content = await file.read()
        csv_content = content.decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")
    
    marketing = get_marketing_service(get_db())
    result = marketing.parse_csv_emails(csv_content)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result




@email_marketing_ext_router.post("/admin/marketing/check-suppressed")
async def check_suppressed_emails(
    data: Dict[str, List[str]],
    current_user: User = Depends(get_current_user)
):
    """
    Check which emails are suppressed (unsubscribed, bounced, spam reported)
    
    Request: {"emails": ["email1@test.com", "email2@test.com"]}
    Returns: {"suppressed": [...], "valid": [...]}
    """
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    emails = data.get("emails", [])
    if not emails:
        return {"suppressed": [], "valid": []}
    
    marketing = get_marketing_service(get_db())
    suppressed_set = await marketing.get_suppressed_emails()
    
    suppressed = []
    valid = []
    
    for email in emails:
        email_lower = email.strip().lower()
        if email_lower in suppressed_set:
            suppressed.append(email_lower)
        else:
            valid.append(email_lower)
    
    return {
        "suppressed": suppressed,
        "valid": valid,
        "suppressed_count": len(suppressed),
        "valid_count": len(valid)
    }




@email_marketing_ext_router.post("/admin/marketing/campaigns")
async def create_campaign(
    data: CampaignCreateRequest,
    current_user: User = Depends(get_current_user)
):
    """Create new email campaign with advanced targeting support"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    marketing = get_marketing_service(get_db())
    
    try:
        campaign = await marketing.create_campaign(
            name=data.name,
            subject=data.subject,
            html_content=data.html_content,
            plain_text_content=data.plain_text_content or "",
            audience_filters=data.audience_filters,
            admin_id=current_user.id,
            admin_email=current_user.email,
            scheduled_at=data.scheduled_at,
            from_email=data.from_email,
            from_name=data.from_name,
            reply_to=data.reply_to,
            manual_emails=data.manual_emails,
            exclude_emails=data.exclude_emails,
            recipient_type=data.recipient_type or "segment",
            attachments=data.attachments,
        )
        return campaign
    except ValueError as ve:
        # iter241 Mission 5 — Strict-validation failure (empty custom list,
        # bad recipient_type, etc) — bubble up as 400 instead of 500.
        logger.warning(f"Campaign validation rejected: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to create campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@email_marketing_ext_router.get("/admin/marketing/campaigns")
async def list_campaigns(
    status: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    current_user: User = Depends(get_current_user)
):
    """List email campaigns with optional status filter"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    marketing = get_marketing_service(get_db())
    campaigns = await marketing.list_campaigns(status=status, limit=limit, skip=skip)
    
    return {
        "campaigns": campaigns,
        "count": len(campaigns)
    }




@email_marketing_ext_router.get("/admin/marketing/campaigns/{campaign_id}")
async def get_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get campaign by ID"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    marketing = get_marketing_service(get_db())
    campaign = await marketing.get_campaign(campaign_id)
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return campaign




@email_marketing_ext_router.put("/admin/marketing/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    data: CampaignUpdateRequest,
    current_user: User = Depends(get_current_user)
):
    """Update draft or scheduled campaign"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    marketing = get_marketing_service(get_db())
    
    try:
        # Build update dict from non-None values
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        
        campaign = await marketing.update_campaign(
            campaign_id=campaign_id,
            updates=updates,
            admin_id=current_user.id,
            admin_email=current_user.email
        )
        return campaign
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@email_marketing_ext_router.post("/admin/marketing/campaigns/{campaign_id}/test")
async def send_test_email(
    campaign_id: str,
    data: Dict[str, str],
    current_user: User = Depends(get_current_user)
):
    """Send test email for campaign preview"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    test_email = data.get("email")
    if not test_email:
        raise HTTPException(status_code=400, detail="Test email address required")
    
    marketing = get_marketing_service(get_db())
    
    try:
        result = await marketing.send_test_email(
            campaign_id=campaign_id,
            test_email=test_email,
            admin_id=current_user.id,
            admin_email=current_user.email
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to send test email: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@email_marketing_ext_router.post("/admin/marketing/campaigns/{campaign_id}/schedule")
async def schedule_campaign(
    campaign_id: str,
    data: Dict[str, str],
    current_user: User = Depends(get_current_user)
):
    """Schedule campaign for sending"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    scheduled_at = data.get("scheduled_at")
    if not scheduled_at:
        raise HTTPException(status_code=400, detail="Scheduled time required")
    
    marketing = get_marketing_service(get_db())
    
    try:
        campaign = await marketing.schedule_campaign(
            campaign_id=campaign_id,
            scheduled_at=scheduled_at,
            admin_id=current_user.id,
            admin_email=current_user.email
        )
        return campaign
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to schedule campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@email_marketing_ext_router.post("/admin/marketing/campaigns/{campaign_id}/send")
async def send_campaign_now(
    campaign_id: str,
    current_user: User = Depends(get_current_user)
):
    """Send campaign immediately"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    marketing = get_marketing_service(get_db())
    
    try:
        result = await marketing.send_campaign_now(
            campaign_id=campaign_id,
            admin_id=current_user.id,
            admin_email=current_user.email
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to send campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@email_marketing_ext_router.post("/admin/marketing/campaigns/{campaign_id}/cancel")
async def cancel_campaign(
    campaign_id: str,
    data: Dict[str, str],
    current_user: User = Depends(get_current_user)
):
    """Cancel scheduled campaign"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    reason = data.get("reason", "")
    if not reason:
        raise HTTPException(status_code=400, detail="Cancellation reason required")
    
    marketing = get_marketing_service(get_db())
    
    try:
        campaign = await marketing.cancel_campaign(
            campaign_id=campaign_id,
            admin_id=current_user.id,
            admin_email=current_user.email,
            reason=reason
        )
        return campaign
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@email_marketing_ext_router.get("/admin/marketing/campaigns/{campaign_id}/stats")
async def get_campaign_stats(
    campaign_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get campaign statistics with open/click rates"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    marketing = get_marketing_service(get_db())
    
    try:
        stats = await marketing.get_campaign_stats(campaign_id)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get campaign stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@email_marketing_ext_router.get("/admin/marketing/campaigns/{campaign_id}/events")
async def get_campaign_events(
    campaign_id: str,
    event_type: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """Get email events for a campaign"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    marketing = get_marketing_service(get_db())
    events = await marketing.get_email_events(
        campaign_id=campaign_id,
        event_type=event_type,
        limit=limit
    )
    
    return {"events": events, "count": len(events)}




@email_marketing_ext_router.get("/admin/marketing/audit")
async def get_marketing_audit_logs(
    campaign_id: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user)
):
    """Get marketing audit logs"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    query = {}
    if campaign_id:
        query["campaign_id"] = campaign_id
    
    logs = await get_db().marketing_audit_logs.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    
    return {"logs": logs, "count": len(logs)}


# ========== CAMPAIGN MANAGEMENT ACTIONS ==========

@email_marketing_ext_router.delete("/admin/marketing/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str, current_user: User = Depends(get_current_user)):
    """Delete a campaign by ID."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_db()
    campaign = await db.email_campaigns.find_one({"id": campaign_id}, {"_id": 0, "status": 1})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.get("status") == "sending":
        raise HTTPException(status_code=400, detail="Cannot delete a campaign that is currently sending")

    await db.email_campaigns.delete_one({"id": campaign_id})
    await db.marketing_audit_logs.insert_one({
        "action": "campaign_deleted",
        "campaign_id": campaign_id,
        "admin_email": current_user.email,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "message": "Campaign deleted"}


@email_marketing_ext_router.post("/admin/marketing/campaigns/{campaign_id}/resend")
async def resend_campaign(campaign_id: str, current_user: User = Depends(get_current_user)):
    """Re-send a completed or failed campaign."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_db()
    campaign = await db.email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.get("status") not in ("sent", "completed", "failed"):
        raise HTTPException(status_code=400, detail="Only completed or failed campaigns can be resent")

    # Reset campaign status to draft so send_campaign_now can process it
    await db.email_campaigns.update_one(
        {"id": campaign_id},
        {"$set": {"status": "draft", "sent_count": 0, "failed_count": 0, "error_message": None}}
    )

    marketing = get_marketing_service(db)
    try:
        result = await marketing.send_campaign_now(campaign_id, current_user.id, current_user.email)
    except Exception as e:
        logger.error(f"Resend failed for campaign {campaign_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Resend failed: {str(e)}")

    await db.marketing_audit_logs.insert_one({
        "action": "campaign_resent",
        "campaign_id": campaign_id,
        "admin_email": current_user.email,
        "result": str(result)[:200],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return result


@email_marketing_ext_router.post("/admin/marketing/campaigns/{campaign_id}/clone")
async def clone_campaign(campaign_id: str, current_user: User = Depends(get_current_user)):
    """Clone a campaign as a new draft."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_db()
    original = await db.email_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not original:
        raise HTTPException(status_code=404, detail="Campaign not found")

    new_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    clone = {
        **original,
        "id": new_id,
        "name": f"{original.get('name', 'Campaign')} (Copy)",
        "status": "draft",
        "sent_count": 0,
        "failed_count": 0,
        "open_count": 0,
        "click_count": 0,
        "error_message": None,
        "sent_at": None,
        "scheduled_at": None,
        "created_at": now,
        "updated_at": now,
        "created_by": current_user.email,
    }
    await db.email_campaigns.insert_one(clone)

    await db.marketing_audit_logs.insert_one({
        "action": "campaign_cloned",
        "campaign_id": campaign_id,
        "new_campaign_id": new_id,
        "admin_email": current_user.email,
        "timestamp": now,
    })
    clone.pop("_id", None)
    return clone






@email_marketing_ext_router.get("/admin/marketing/config")
async def get_marketing_config(current_user: User = Depends(get_current_user)):
    """Get marketing email configuration status"""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    marketing = get_marketing_service(get_db())
    
    marketing_key = os.environ.get("SENDGRID_MARKETING_API_KEY")
    transactional_key = os.environ.get("SENDGRID_API_KEY")
    
    return {
        "marketing_configured": marketing.is_configured(),
        "has_marketing_key": bool(marketing_key and marketing_key != "SG.your-actual-sendgrid-key-here"),
        "has_transactional_key": bool(transactional_key and transactional_key != "SG.your-actual-sendgrid-key-here"),
        "using_separate_keys": bool(marketing_key and marketing_key != transactional_key),
        "from_email": os.environ.get("SENDGRID_FROM_EMAIL", "noreply@bidvex.com"),
        "marketing_from_email": os.environ.get("SENDGRID_MARKETING_FROM_EMAIL") or os.environ.get("SENDGRID_FROM_EMAIL", "noreply@bidvex.com"),
        "webhook_url": f"{os.environ.get('FRONTEND_URL', '')}/api/webhooks/sendgrid"
    }




@email_marketing_ext_router.get("/user/marketing/access")
async def check_marketing_access(current_user: User = Depends(get_current_user)):
    """Check user's access to email marketing feature"""
    user_marketing = get_user_marketing_service(get_db())
    tier = current_user.subscription_tier or "free"
    
    can_send = user_marketing.can_access_feature(tier)
    quota = await user_marketing.get_remaining_quota(current_user.id, tier)
    contact_limit = await user_marketing.check_contact_limit(current_user.id, tier)
    
    return {
        "can_access": True,  # All users can access the feature to manage contacts
        "can_send": can_send,  # Only Premium/VIP can send
        "subscription_tier": tier,
        "limits": user_marketing.get_subscription_limits(tier),
        "quota": quota,
        "contact_limit": contact_limit,
        "upgrade_message": "Upgrade to Premium or VIP to send auctions to your client list." if not can_send else None
    }




@email_marketing_ext_router.get("/user/marketing/contacts")
async def get_user_contacts(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    current_user: User = Depends(get_current_user)
):
    """Get user's contacts - all tiers can view their contacts"""
    user_marketing = get_user_marketing_service(get_db())
    
    result = await user_marketing.get_contacts(
        user_id=current_user.id,
        status=status,
        search=search,
        limit=limit,
        skip=skip
    )
    return result




@email_marketing_ext_router.get("/user/marketing/contacts/stats")
async def get_user_contact_stats(current_user: User = Depends(get_current_user)):
    """Get contact statistics - all tiers can view stats"""
    user_marketing = get_user_marketing_service(get_db())
    tier = current_user.subscription_tier or "free"
    
    stats = await user_marketing.get_contact_stats(current_user.id)
    contact_limit = await user_marketing.check_contact_limit(current_user.id, tier)
    
    return {
        **stats,
        "contact_limit": contact_limit
    }




@email_marketing_ext_router.post("/user/marketing/contacts")
async def add_user_contact(
    data: UserContactCreateRequest,
    current_user: User = Depends(get_current_user)
):
    """Add a single contact - all tiers can add contacts up to their limit"""
    user_marketing = get_user_marketing_service(get_db())
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




@email_marketing_ext_router.post("/user/marketing/contacts/bulk")
async def add_user_contacts_bulk(
    data: UserContactBulkRequest,
    current_user: User = Depends(get_current_user)
):
    """Add multiple contacts at once - all tiers can add up to their limit"""
    user_marketing = get_user_marketing_service(get_db())
    tier = current_user.subscription_tier or "free"
    
    result = await user_marketing.add_contacts_bulk(
        user_id=current_user.id,
        emails=data.emails,
        consent_confirmed=data.consent_confirmed,
        user_tier=tier
    )
    return result




@email_marketing_ext_router.post("/user/marketing/contacts/parse")
async def parse_user_emails(
    data: Dict[str, str],
    current_user: User = Depends(get_current_user)
):
    """Parse and validate email list"""
    user_marketing = get_user_marketing_service(get_db())
    tier = current_user.subscription_tier or "free"
    
    if not user_marketing.can_access_feature(tier):
        raise HTTPException(
            status_code=403,
            detail="Upgrade to Premium or VIP to access client email marketing"
        )
    
    result = user_marketing.parse_email_list(data.get("emails", ""))
    return result




@email_marketing_ext_router.post("/user/marketing/contacts/csv")
async def upload_user_contacts_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload CSV file with contacts"""
    user_marketing = get_user_marketing_service(get_db())
    tier = current_user.subscription_tier or "free"
    
    if not user_marketing.can_access_feature(tier):
        raise HTTPException(
            status_code=403,
            detail="Upgrade to Premium or VIP to access client email marketing"
        )
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        content = await file.read()
        csv_content = content.decode('utf-8')
        result = user_marketing.parse_csv_emails(csv_content)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))




@email_marketing_ext_router.get("/user/marketing/contacts/{contact_id}")
async def get_user_contact(
    contact_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get single contact"""
    user_marketing = get_user_marketing_service(get_db())
    contact = await user_marketing.get_contact(current_user.id, contact_id)
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return contact




@email_marketing_ext_router.put("/user/marketing/contacts/{contact_id}")
async def update_user_contact(
    contact_id: str,
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Update a contact"""
    user_marketing = get_user_marketing_service(get_db())
    tier = current_user.subscription_tier or "free"
    
    if not user_marketing.can_access_feature(tier):
        raise HTTPException(
            status_code=403,
            detail="Upgrade to Premium or VIP to access client email marketing"
        )
    
    try:
        contact = await user_marketing.update_contact(
            user_id=current_user.id,
            contact_id=contact_id,
            updates=data
        )
        return contact
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))




@email_marketing_ext_router.delete("/user/marketing/contacts/{contact_id}")
async def delete_user_contact(
    contact_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a contact"""
    user_marketing = get_user_marketing_service(get_db())
    tier = current_user.subscription_tier or "free"
    
    if not user_marketing.can_access_feature(tier):
        raise HTTPException(
            status_code=403,
            detail="Upgrade to Premium or VIP to access client email marketing"
        )
    
    deleted = await user_marketing.delete_contact(current_user.id, contact_id)
    
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    return {"status": "deleted"}




@email_marketing_ext_router.post("/user/marketing/contacts/delete-bulk")
async def delete_user_contacts_bulk(
    data: Dict[str, List[str]],
    current_user: User = Depends(get_current_user)
):
    """Delete multiple contacts"""
    user_marketing = get_user_marketing_service(get_db())
    tier = current_user.subscription_tier or "free"
    
    if not user_marketing.can_access_feature(tier):
        raise HTTPException(
            status_code=403,
            detail="Upgrade to Premium or VIP to access client email marketing"
        )
    
    contact_ids = data.get("contact_ids", [])
    deleted_count = await user_marketing.delete_contacts_bulk(current_user.id, contact_ids)
    
    return {"deleted_count": deleted_count}


# User Campaigns


@email_marketing_ext_router.get("/user/marketing/campaigns")
async def get_user_campaigns(
    status: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    current_user: User = Depends(get_current_user)
):
    """Get user's campaigns"""
    user_marketing = get_user_marketing_service(get_db())
    tier = current_user.subscription_tier or "free"
    
    if not user_marketing.can_access_feature(tier):
        raise HTTPException(
            status_code=403,
            detail="Upgrade to Premium or VIP to access client email marketing"
        )
    
    result = await user_marketing.get_campaigns(
        user_id=current_user.id,
        status=status,
        limit=limit,
        skip=skip
    )
    return result




@email_marketing_ext_router.post("/user/marketing/campaigns")
async def create_user_campaign(
    data: UserCampaignCreateRequest,
    current_user: User = Depends(get_current_user)
):
    """Create a new campaign"""
    user_marketing = get_user_marketing_service(get_db())
    tier = current_user.subscription_tier or "free"
    
    if not user_marketing.can_access_feature(tier):
        raise HTTPException(
            status_code=403,
            detail="Upgrade to Premium or VIP to access client email marketing"
        )
    
    campaign = await user_marketing.create_campaign(
        user_id=current_user.id,
        user_email=current_user.email,
        name=data.name,
        subject=data.subject,
        html_content=data.html_content,
        plain_text_content=data.plain_text_content,
        contact_ids=data.contact_ids,
        auction_id=data.auction_id
    )
    return campaign




@email_marketing_ext_router.get("/user/marketing/campaigns/{campaign_id}")
async def get_user_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get single campaign"""
    user_marketing = get_user_marketing_service(get_db())
    campaign = await user_marketing.get_campaign(current_user.id, campaign_id)
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return campaign




@email_marketing_ext_router.put("/user/marketing/campaigns/{campaign_id}")
async def update_user_campaign(
    campaign_id: str,
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Update a draft campaign"""
    user_marketing = get_user_marketing_service(get_db())
    tier = current_user.subscription_tier or "free"
    
    if not user_marketing.can_access_feature(tier):
        raise HTTPException(
            status_code=403,
            detail="Upgrade to Premium or VIP to access client email marketing"
        )
    
    try:
        campaign = await user_marketing.update_campaign(
            user_id=current_user.id,
            campaign_id=campaign_id,
            updates=data
        )
        return campaign
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))




@email_marketing_ext_router.post("/user/marketing/campaigns/{campaign_id}/confirm-consent")
async def confirm_user_campaign_consent(
    campaign_id: str,
    current_user: User = Depends(get_current_user)
):
    """Confirm consent before sending"""
    user_marketing = get_user_marketing_service(get_db())
    
    campaign = await user_marketing.confirm_consent(current_user.id, campaign_id)
    return campaign




@email_marketing_ext_router.post("/user/marketing/campaigns/{campaign_id}/send")
async def send_user_campaign(
    campaign_id: str,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Send a campaign"""
    user_marketing = get_user_marketing_service(get_db())
    tier = current_user.subscription_tier or "free"
    
    if not user_marketing.can_access_feature(tier):
        raise HTTPException(
            status_code=403,
            detail="Upgrade to Premium or VIP to access client email marketing"
        )
    
    user_ip = request.client.host if request.client else None
    
    try:
        result = await user_marketing.send_campaign(
            user_id=current_user.id,
            user_email=current_user.email,
            campaign_id=campaign_id,
            user_tier=tier,
            user_ip=user_ip
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))




@email_marketing_ext_router.get("/user/marketing/campaigns/{campaign_id}/stats")
async def get_user_campaign_stats(
    campaign_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get campaign stats"""
    user_marketing = get_user_marketing_service(get_db())
    
    try:
        stats = await user_marketing.get_campaign_stats(current_user.id, campaign_id)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))




@email_marketing_ext_router.get("/user/marketing/auction-template/{auction_id}")
async def get_auction_email_template(
    auction_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get email template for an auction"""
    user_marketing = get_user_marketing_service(get_db())
    tier = current_user.subscription_tier or "free"
    
    if not user_marketing.can_access_feature(tier):
        raise HTTPException(
            status_code=403,
            detail="Upgrade to Premium or VIP to access client email marketing"
        )
    
    # Get auction details
    auction = await get_db().listings.find_one({"id": auction_id}, {"_id": 0})
    if not auction:
        # Try vehicles
        auction = await get_db().vehicle_auctions.find_one({"id": auction_id}, {"_id": 0})
    
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    
    template = user_marketing.get_auction_email_template(auction)
    
    return {
        "auction_id": auction_id,
        "auction_title": auction.get("title"),
        "html_template": template
    }


# Public unsubscribe endpoint


@email_marketing_ext_router.get("/unsubscribe/user")
async def unsubscribe_user_contact(
    user: str,
    contact: str
):
    """Handle unsubscribe from user marketing email"""
    user_marketing = get_user_marketing_service(get_db())
    
    success = await user_marketing.handle_unsubscribe(user, contact)
    
    if success:
        return {"status": "unsubscribed", "message": "You have been unsubscribed from this sender's list."}
    else:
        return {"status": "not_found", "message": "Contact not found or already unsubscribed."}


@email_marketing_ext_router.post("/marketing/unsubscribe")
async def marketing_unsubscribe_by_token(data: dict = Body(...)):
    """
    Public unsubscribe endpoint — called by frontend /unsubscribe page.
    Token is either a user_id or an email address.
    """
    token = data.get("token", "").strip()
    if not token:
        return {"status": "error", "message": "Invalid token"}

    db = get_db()
    # Try to find user by ID or email
    user = await db.users.find_one(
        {"$or": [{"id": token}, {"email": token}]},
        {"_id": 0, "id": 1, "email": 1, "marketing_unsubscribed": 1}
    )

    if user:
        if user.get("marketing_unsubscribed"):
            return {"status": "already", "success": True, "message": "You are already unsubscribed from marketing emails."}
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {"marketing_unsubscribed": True, "marketing_unsubscribed_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"status": "unsubscribed", "success": True, "message": "You have been successfully unsubscribed from marketing emails."}

    # Token might be a raw email not in our user DB (manual recipient)
    if "@" in token:
        existing = await db.marketing_suppressions.find_one({"email": token.lower()})
        if existing:
            return {"status": "already", "success": True, "message": "This email is already unsubscribed."}
        await db.marketing_suppressions.insert_one({
            "email": token.lower(), "reason": "user_unsubscribed",
            "unsubscribed_at": datetime.now(timezone.utc).isoformat()
        })
        return {"status": "unsubscribed", "success": True, "message": "You have been successfully unsubscribed."}

    return {"status": "error", "message": "Could not process unsubscribe request. Please contact support@bidvex.com."}





@email_marketing_ext_router.get("/user/marketing/templates")
async def get_user_email_templates_route(current_user: User = Depends(get_current_user)):
    """Get pre-built email templates"""
    user_marketing = get_user_marketing_service(get_db())
    templates = user_marketing.get_email_templates()
    return {"templates": templates}


# Include all API routes - MUST be after all routes are defined



@email_marketing_ext_router.get("/admin/marketing/dashboard-stats")
async def get_marketing_dashboard_stats(current_user: User = Depends(get_current_user)):
    """Get aggregate marketing stats for the admin dashboard."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    service = get_marketing_service(db)
    stats = await service.get_global_dashboard_stats()

    recent = await db.email_campaigns.find(
        {}, {"_id": 0, "id": 1, "name": 1, "status": 1, "sent_at": 1, "stats": 1}
    ).sort("created_at", -1).limit(5).to_list(5)

    stats["recent_campaigns"] = recent
    return stats


@email_marketing_ext_router.post("/admin/marketing/sync-contacts")
async def sync_contacts(current_user: User = Depends(get_current_user)):
    """Sync all registered users into the marketing contacts pool."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    service = get_marketing_service(db)
    result = await service.sync_registered_contacts()
    return result

