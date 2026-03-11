"""
BidVex Admin Router
Handles administrative operations including:
- User management
- Subscription overrides
- Listings moderation
- System configuration
- Trust & Safety
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import logging
import uuid
import os

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/admin", tags=["Admin"])
security = HTTPBearer(auto_error=False)

# Database and service instances
_db = None
_get_current_user = None
_email_service = None


def set_admin_db(db_instance):
    """Set database instance"""
    global _db
    _db = db_instance


def set_admin_auth(get_current_user_func):
    """Set authentication function"""
    global _get_current_user
    _get_current_user = get_current_user_func


def set_admin_email_service(email_svc):
    """Set email service"""
    global _email_service
    _email_service = email_svc


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


async def require_admin(credentials: HTTPAuthorizationCredentials):
    """Verify user has admin role"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    current_user = await _get_current_user(credentials)
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ========== USER MANAGEMENT ==========

@admin_router.get("/users")
async def list_users(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    role: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """List all users with pagination"""
    await require_admin(credentials)
    db = get_db()
    
    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}}
        ]
    if role:
        query["role"] = role
    
    skip = (page - 1) * limit
    users = await db.users.find(query, {"_id": 0, "password_hash": 0}).skip(skip).limit(limit).to_list(limit)
    total = await db.users.count_documents(query)
    
    return {
        "users": users,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }


class AdminUserCreate(BaseModel):
    email: EmailStr
    name: str
    phone: str
    account_type: str = "personal"
    role: Optional[str] = None
    subscription_tier: Optional[str] = "free"


@admin_router.post("/users/create")
async def admin_create_user(
    data: AdminUserCreate,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Admin creates a new user account with temporary password"""
    from passlib.context import CryptContext
    import secrets
    import string
    
    admin = await require_admin(credentials)
    db = get_db()
    
    # Check if email exists
    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Generate secure temporary password
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    password_hash = pwd_context.hash(temp_password)
    
    now = datetime.now(timezone.utc)
    user_id = str(uuid.uuid4())
    
    user = {
        "id": user_id,
        "email": data.email.lower(),
        "name": data.name,
        "phone": data.phone,
        "account_type": data.account_type,
        "role": data.role,
        "password_hash": password_hash,
        "password_reset_required": True,
        "email_verified": True,  # Admin-created accounts are auto-verified
        "admin_verified": False,
        "subscription_tier": data.subscription_tier or "free",
        "created_at": now.isoformat(),
        "created_by_admin": admin.id
    }
    
    await db.users.insert_one(user)
    
    # Log the action
    await db.admin_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "user_created",
        "admin_id": admin.id,
        "admin_email": admin.email,
        "target_user_id": user_id,
        "target_email": data.email,
        "ip_address": request.client.host if request.client else "unknown",
        "created_at": now.isoformat()
    })
    
    # Send welcome email (if email service configured)
    if _email_service:
        try:
            await _email_service.send_email(
                to_email=data.email,
                subject="Welcome to BidVex - Your Account Has Been Created",
                html_content=f"""
                <h2>Welcome to BidVex!</h2>
                <p>An administrator has created an account for you.</p>
                <p><strong>Your temporary password:</strong> {temp_password}</p>
                <p>You will be required to change this password on your first login.</p>
                """,
                template_id=None
            )
        except Exception as e:
            logger.warning(f"Failed to send welcome email: {e}")
    
    return {
        "status": "success",
        "user_id": user_id,
        "email": data.email,
        "temporary_password": temp_password,
        "message": "User created. Provide the temporary password to the user securely."
    }


@admin_router.put("/users/{user_id}/admin-verify")
async def toggle_admin_verified(
    user_id: str,
    data: Dict[str, bool],
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Toggle admin verification badge for a user"""
    admin = await require_admin(credentials)
    db = get_db()
    
    verified = data.get("verified", False)
    
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "admin_verified": verified,
            "admin_verified_by": admin.id if verified else None,
            "admin_verified_at": datetime.now(timezone.utc).isoformat() if verified else None
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Log action
    await db.admin_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "admin_verify_toggled",
        "admin_id": admin.id,
        "target_user_id": user_id,
        "verified": verified,
        "ip_address": request.client.host if request.client else "unknown",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"status": "success", "admin_verified": verified}


@admin_router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    data: Dict[str, Any],
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update user status (active/suspended/banned)"""
    admin = await require_admin(credentials)
    db = get_db()
    
    status = data.get("status")
    reason = data.get("reason", "")
    
    if status not in ["active", "suspended", "banned"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    result = await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "status": status,
            "status_reason": reason,
            "status_updated_by": admin.id,
            "status_updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Log action
    await db.admin_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": f"user_status_{status}",
        "admin_id": admin.id,
        "target_user_id": user_id,
        "reason": reason,
        "ip_address": request.client.host if request.client else "unknown",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"status": "success", "user_status": status}


@admin_router.get("/users/{user_id}/detail")
async def get_user_detail(
    user_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get detailed user information for admin"""
    await require_admin(credentials)
    db = get_db()
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get additional stats
    listings_count = await db.listings.count_documents({"seller_id": user_id})
    bids_count = await db.bids.count_documents({"bidder_id": user_id})
    reports_against = await db.reports.count_documents({"reported_user_id": user_id})
    reports_made = await db.reports.count_documents({"reporter_id": user_id})
    
    return {
        **user,
        "stats": {
            "listings_count": listings_count,
            "bids_count": bids_count,
            "reports_against": reports_against,
            "reports_made": reports_made
        }
    }


# ========== SUBSCRIPTION MANAGEMENT ==========

@admin_router.get("/users/{user_id}/subscription")
async def get_user_subscription(
    user_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get user subscription details"""
    await require_admin(credentials)
    db = get_db()
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check Stripe subscription if exists
    stripe_status = None
    if user.get("stripe_subscription_id"):
        import stripe
        try:
            sub = stripe.Subscription.retrieve(user["stripe_subscription_id"])
            stripe_status = sub.status
        except Exception:
            stripe_status = "error"
    
    return {
        "user_id": user_id,
        "current_tier": user.get("subscription_tier", "free"),
        "subscription_source": user.get("subscription_source", "manual"),
        "subscription_status": user.get("subscription_status", "inactive"),
        "subscription_start_date": user.get("subscription_start_date"),
        "subscription_end_date": user.get("subscription_end_date"),
        "stripe_subscription_id": user.get("stripe_subscription_id"),
        "stripe_status": stripe_status,
        "override_info": {
            "override_by": user.get("subscription_override_by"),
            "override_at": user.get("subscription_override_at"),
            "override_reason": user.get("subscription_override_reason")
        }
    }


class SubscriptionOverride(BaseModel):
    plan: str = Field(..., pattern="^(free|premium|vip)$")
    duration_days: Optional[int] = None
    end_date: Optional[str] = None
    reason: str = Field(..., min_length=10)


@admin_router.post("/users/{user_id}/subscription/override")
async def override_subscription(
    user_id: str,
    data: SubscriptionOverride,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Override user subscription manually"""
    admin = await require_admin(credentials)
    db = get_db()
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Block if active Stripe subscription
    if user.get("stripe_subscription_id") and user.get("subscription_source") == "stripe":
        import stripe
        try:
            sub = stripe.Subscription.retrieve(user["stripe_subscription_id"])
            if sub.status == "active":
                raise HTTPException(
                    status_code=409,
                    detail="Cannot override active Stripe subscription. Cancel Stripe subscription first."
                )
        except stripe.StripeError:
            pass
    
    now = datetime.now(timezone.utc)
    
    # Calculate end date
    if data.end_date:
        end_date = data.end_date
    elif data.duration_days:
        end_date = (now + timedelta(days=data.duration_days)).isoformat()
    else:
        end_date = (now + timedelta(days=30)).isoformat()
    
    update_data = {
        "subscription_tier": data.plan,
        "subscription_source": "manual",
        "subscription_status": "active" if data.plan != "free" else "inactive",
        "subscription_start_date": now.isoformat(),
        "subscription_end_date": end_date if data.plan != "free" else None,
        "subscription_override_by": admin.id,
        "subscription_override_at": now.isoformat(),
        "subscription_override_reason": data.reason
    }
    
    await db.users.update_one({"id": user_id}, {"$set": update_data})
    
    # Audit log
    await db.subscription_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "override",
        "user_id": user_id,
        "admin_id": admin.id,
        "old_tier": user.get("subscription_tier", "free"),
        "new_tier": data.plan,
        "end_date": end_date,
        "reason": data.reason,
        "ip_address": request.client.host if request.client else "unknown",
        "created_at": now.isoformat()
    })
    
    return {
        "status": "success",
        "new_tier": data.plan,
        "end_date": end_date
    }


@admin_router.post("/users/{user_id}/subscription/extend")
async def extend_subscription(
    user_id: str,
    data: Dict[str, Any],
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Extend existing manual subscription"""
    admin = await require_admin(credentials)
    db = get_db()
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.get("subscription_source") != "manual":
        raise HTTPException(status_code=400, detail="Can only extend manual subscriptions")
    
    days = data.get("days", 30)
    reason = data.get("reason", "")
    
    if not reason or len(reason) < 10:
        raise HTTPException(status_code=400, detail="Reason required (min 10 chars)")
    
    current_end = user.get("subscription_end_date")
    if current_end:
        try:
            end_dt = datetime.fromisoformat(current_end.replace('Z', '+00:00'))
        except:
            end_dt = datetime.now(timezone.utc)
    else:
        end_dt = datetime.now(timezone.utc)
    
    new_end = (end_dt + timedelta(days=days)).isoformat()
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "subscription_end_date": new_end,
            "subscription_override_by": admin.id,
            "subscription_override_at": datetime.now(timezone.utc).isoformat(),
            "subscription_override_reason": reason
        }}
    )
    
    # Audit log
    await db.subscription_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "extend",
        "user_id": user_id,
        "admin_id": admin.id,
        "days_added": days,
        "old_end_date": current_end,
        "new_end_date": new_end,
        "reason": reason,
        "ip_address": request.client.host if request.client else "unknown",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {
        "status": "success",
        "new_end_date": new_end,
        "days_added": days
    }


@admin_router.post("/users/{user_id}/subscription/revoke")
async def revoke_subscription(
    user_id: str,
    data: Dict[str, str],
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Revoke subscription and downgrade to free"""
    admin = await require_admin(credentials)
    db = get_db()
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    reason = data.get("reason", "")
    if not reason or len(reason) < 10:
        raise HTTPException(status_code=400, detail="Reason required (min 10 chars)")
    
    old_tier = user.get("subscription_tier", "free")
    now = datetime.now(timezone.utc)
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "subscription_tier": "free",
            "subscription_status": "revoked",
            "subscription_end_date": now.isoformat(),
            "subscription_override_by": admin.id,
            "subscription_override_at": now.isoformat(),
            "subscription_override_reason": reason
        }}
    )
    
    # Audit log
    await db.subscription_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "revoke",
        "user_id": user_id,
        "admin_id": admin.id,
        "old_tier": old_tier,
        "reason": reason,
        "ip_address": request.client.host if request.client else "unknown",
        "created_at": now.isoformat()
    })
    
    return {"status": "success", "new_tier": "free"}


@admin_router.get("/users/{user_id}/subscription/history")
async def get_subscription_history(
    user_id: str,
    limit: int = 20,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get subscription audit history"""
    await require_admin(credentials)
    db = get_db()
    
    logs = await db.subscription_audit_logs.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"history": logs}


# ========== LISTINGS MODERATION ==========

@admin_router.get("/listings/all")
async def get_all_listings(
    status: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get all listings for admin"""
    await require_admin(credentials)
    db = get_db()
    
    query = {}
    if status:
        query["status"] = status
    
    listings = await db.listings.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    total = await db.listings.count_documents(query)
    
    return {"listings": listings, "total": total}


@admin_router.get("/listings/pending")
async def get_pending_listings(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get listings pending approval"""
    await require_admin(credentials)
    db = get_db()
    
    listings = await db.listings.find(
        {"status": "pending"},
        {"_id": 0}
    ).to_list(100)
    
    return {"listings": listings, "count": len(listings)}


@admin_router.put("/listings/{listing_id}/moderate")
async def moderate_listing(
    listing_id: str,
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Approve or reject a listing"""
    admin = await require_admin(credentials)
    db = get_db()
    
    action = data.get("action")  # approve, reject, suspend
    reason = data.get("reason", "")
    
    if action not in ["approve", "reject", "suspend"]:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    status_map = {
        "approve": "active",
        "reject": "rejected",
        "suspend": "suspended"
    }
    
    result = await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "status": status_map[action],
            "moderated_by": admin.id,
            "moderated_at": datetime.now(timezone.utc).isoformat(),
            "moderation_reason": reason
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    return {"status": "success", "action": action}


# ========== DELETION REQUESTS ==========

@admin_router.get("/deletion-requests")
async def get_deletion_requests(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get pending deletion requests"""
    await require_admin(credentials)
    db = get_db()
    
    requests = await db.deletion_requests.find(
        {"status": "pending"},
        {"_id": 0}
    ).to_list(100)
    
    return {"requests": requests}


@admin_router.post("/deletion-requests/{request_id}/approve")
async def approve_deletion(
    request_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Approve and execute a deletion request"""
    admin = await require_admin(credentials)
    db = get_db()
    
    req = await db.deletion_requests.find_one({"id": request_id})
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Execute deletion based on type
    if req.get("listing_id"):
        await db.listings.delete_one({"id": req["listing_id"]})
    
    await db.deletion_requests.update_one(
        {"id": request_id},
        {"$set": {
            "status": "approved",
            "approved_by": admin.id,
            "approved_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"status": "approved"}


@admin_router.post("/deletion-requests/{request_id}/reject")
async def reject_deletion(
    request_id: str,
    data: Dict[str, str],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Reject a deletion request"""
    admin = await require_admin(credentials)
    db = get_db()
    
    reason = data.get("reason", "")
    
    result = await db.deletion_requests.update_one(
        {"id": request_id},
        {"$set": {
            "status": "rejected",
            "rejected_by": admin.id,
            "rejected_at": datetime.now(timezone.utc).isoformat(),
            "rejection_reason": reason
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Request not found")
    
    return {"status": "rejected"}


# ========== REPORTS & ANALYTICS ==========

@admin_router.get("/reports")
async def get_reports(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get user reports"""
    await require_admin(credentials)
    db = get_db()
    
    reports = await db.reports.find({}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    return {"reports": reports}


@admin_router.put("/reports/{report_id}/update")
async def update_report(
    report_id: str,
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update report status"""
    admin = await require_admin(credentials)
    db = get_db()
    
    status = data.get("status")
    notes = data.get("notes", "")
    
    result = await db.reports.update_one(
        {"id": report_id},
        {"$set": {
            "status": status,
            "admin_notes": notes,
            "updated_by": admin.id,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return {"status": "updated"}


@admin_router.get("/analytics/users")
async def get_user_analytics(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get user analytics summary"""
    await require_admin(credentials)
    db = get_db()
    
    total_users = await db.users.count_documents({})
    new_today = await db.users.count_documents({
        "created_at": {"$gte": datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()}
    })
    
    by_tier = {}
    for tier in ["free", "premium", "vip"]:
        by_tier[tier] = await db.users.count_documents({"subscription_tier": tier})
    
    return {
        "total_users": total_users,
        "new_today": new_today,
        "by_tier": by_tier
    }


@admin_router.get("/analytics/revenue")
async def get_revenue_analytics(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get revenue analytics"""
    await require_admin(credentials)
    db = get_db()
    
    # Get sold listings
    sold = await db.listings.find({"status": "sold"}, {"current_price": 1}).to_list(None)
    total_gmv = sum(l.get("current_price", 0) for l in sold)
    
    return {
        "total_gmv": total_gmv,
        "sold_listings": len(sold)
    }


@admin_router.get("/analytics/listings")
async def get_listing_analytics(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get listing analytics"""
    await require_admin(credentials)
    db = get_db()
    
    stats = {}
    for status in ["active", "pending", "sold", "ended", "cancelled"]:
        stats[status] = await db.listings.count_documents({"status": status})
    
    return stats


# ========== AUDIT LOGS ==========

@admin_router.post("/logs")
async def create_admin_log(
    data: Dict[str, Any],
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create admin audit log entry"""
    admin = await require_admin(credentials)
    db = get_db()
    
    log_entry = {
        "id": str(uuid.uuid4()),
        "admin_id": admin.id,
        "admin_email": admin.email,
        "action": data.get("action"),
        "details": data.get("details"),
        "ip_address": request.client.host if request.client else "unknown",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.admin_audit_logs.insert_one(log_entry)
    return {"status": "logged", "log_id": log_entry["id"]}


@admin_router.get("/logs")
async def get_admin_logs(
    limit: int = 50,
    skip: int = 0,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get admin audit logs"""
    await require_admin(credentials)
    db = get_db()
    
    logs = await db.admin_audit_logs.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    return {"logs": logs}
