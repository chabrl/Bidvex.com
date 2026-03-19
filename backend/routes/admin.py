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
from jose import jwt, JWTError
from deps import User
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
    """Verify user has admin role by decoding JWT directly."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    db = get_db()
    token = credentials.credentials
    jwt_secret = os.environ.get("JWT_SECRET", "your-secret-key")
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if not user_doc:
            raise HTTPException(status_code=401, detail="User not found")
        current_user = User(**user_doc)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
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



# ========== PARTNER MANAGEMENT ==========

import stripe


async def _get_sendgrid_config():
    """Get SendGrid config: checks DB-stored key first, then env var."""
    db = get_db()
    try:
        doc = await db.settings.find_one({"key": "sendgrid"}, {"_id": 0})
        if doc and doc.get("api_key") and not doc["api_key"].startswith("SG.your"):
            return {
                "api_key": doc["api_key"],
                "from_email": doc.get("from_email", "noreply@bidvex.com"),
                "from_name": doc.get("from_name", "BidVex Partner Team"),
                "source": "database",
            }
    except Exception:
        pass
    env_key = os.environ.get("SENDGRID_API_KEY", "")
    if env_key and not env_key.startswith("SG.your"):
        return {
            "api_key": env_key,
            "from_email": os.environ.get("SENDGRID_FROM_EMAIL", "noreply@bidvex.com"),
            "from_name": "BidVex Partner Team",
            "source": "environment",
        }
    return None


def _send_partner_email(to_email: str, subject: str, html_content: str):
    """Send email via SendGrid if configured (sync wrapper)."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        config = loop.run_until_complete(_get_sendgrid_config())
    except RuntimeError:
        config = None
    if not config:
        logger.info(f"SendGrid not configured — skipping email to {to_email}")
        return
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Email, To, Content
        sg = sendgrid.SendGridAPIClient(api_key=config["api_key"])
        from_email = Email(config["from_email"], config["from_name"])
        mail = Mail(from_email=from_email, to_emails=To(to_email), subject=subject, html_content=Content("text/html", html_content))
        sg.client.mail.send.post(request_body=mail.get())
        logger.info(f"Email sent to {to_email}: {subject}")
    except Exception as e:
        logger.warning(f"Failed to send email to {to_email}: {e}")


async def _get_or_create_partner_fee_price():
    """Get or create the $100 CAD/year partner fee Stripe Price."""
    db = get_db()
    setting = await db.settings.find_one({"key": "partner_fee_price_id"}, {"_id": 0})
    if setting and setting.get("price_id"):
        try:
            price = stripe.Price.retrieve(setting["price_id"])
            if price.active:
                return setting["price_id"]
        except Exception:
            pass

    product = stripe.Product.create(
        name="BidVex Partner Annual Fee",
        description="Annual platform access fee for BidVex Partner accounts ($100 CAD/year)",
        metadata={"type": "partner_annual_fee"}
    )
    price = stripe.Price.create(
        product=product.id,
        unit_amount=10000,
        currency="cad",
        recurring={"interval": "year"},
        metadata={"type": "partner_annual_fee"}
    )
    await db.settings.update_one(
        {"key": "partner_fee_price_id"},
        {"$set": {"key": "partner_fee_price_id", "price_id": price.id, "product_id": product.id}},
        upsert=True
    )
    return price.id


@admin_router.get("/partners")
async def get_partner_applications(
    status: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Admin: List all partner applications, optionally filtered by status."""
    current_user = await require_admin(credentials)
    db = get_db()
    
    query = {"partner_verification_status": {"$in": ["pending", "verified", "rejected"]}}
    if status:
        query["partner_verification_status"] = status
    
    users = await db.users.find(
        query, {"_id": 0, "password": 0}
    ).sort("partner_applied_at", -1).to_list(100)
    
    applications = []
    for u in users:
        applications.append({
            "id": u.get("id"),
            "email": u.get("email"),
            "name": u.get("name"),
            "account_type": u.get("account_type"),
            "partner_company_name": u.get("partner_company_name"),
            "partner_neq": u.get("partner_neq"),
            "partner_neq_document": u.get("partner_neq_document"),
            "partner_certifications": u.get("partner_certifications", []),
            "partner_verification_status": u.get("partner_verification_status"),
            "partner_applied_at": u.get("partner_applied_at"),
            "partner_verified_at": u.get("partner_verified_at"),
            "partner_rejection_reason": u.get("partner_rejection_reason"),
            "is_partner": u.get("is_partner", False),
            "custom_premium_rate": u.get("custom_premium_rate"),
            "platform_fee_paid": u.get("platform_fee_paid", False),
            "partner_subscription_id": u.get("partner_subscription_id"),
        })
    
    return {"applications": applications, "total": len(applications)}


@admin_router.post("/partners/{user_id}/verify")
async def verify_partner(
    user_id: str,
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Admin: Verify a partner application.
    Creates a Stripe Checkout Session for the $100 CAD/year annual fee.
    Partner account remains locked until payment is completed via webhook.
    """
    current_user = await require_admin(credentials)
    db = get_db()
    
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    if user_doc.get("partner_verification_status") != "pending":
        raise HTTPException(status_code=400, detail=f"User is not in pending status (current: {user_doc.get('partner_verification_status')})")
    
    now = datetime.now(timezone.utc).isoformat()
    custom_rate = data.get("custom_premium_rate")
    
    update = {
        "is_partner": True,
        "partner_verification_status": "verified",
        "partner_verified_at": now,
        "partner_rejection_reason": None,
        "platform_fee_paid": False,
        "updated_at": now,
    }
    if custom_rate is not None:
        update["custom_premium_rate"] = float(custom_rate)
    
    await db.users.update_one({"id": user_id}, {"$set": update})
    
    # Create Stripe Checkout Session for annual partner fee
    checkout_url = None
    try:
        price_id = await _get_or_create_partner_fee_price()
        base_url = os.environ.get("REACT_APP_BACKEND_URL", "https://www.bidvex.com")
        
        customer_id = user_doc.get("stripe_customer_id")
        if not customer_id:
            customer = stripe.Customer.create(
                email=user_doc.get("email"),
                name=user_doc.get("name", ""),
                metadata={"user_id": user_id, "type": "partner"}
            )
            customer_id = customer.id
            await db.users.update_one({"id": user_id}, {"$set": {"stripe_customer_id": customer_id}})
        
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"user_id": user_id, "type": "partner_activation", "business_name": user_doc.get("partner_company_name", user_doc.get("name", ""))},
            success_url=f"{base_url}/partner/dashboard?session_id={{CHECKOUT_SESSION_ID}}&partner_payment=success",
            cancel_url=f"{base_url}/partner/dashboard?partner_payment=cancelled",
            subscription_data={
                "metadata": {"user_id": user_id, "type": "partner_annual_fee"}
            },
        )
        checkout_url = session.url
        
        await db.users.update_one({"id": user_id}, {"$set": {
            "partner_checkout_session_id": session.id,
            "partner_checkout_url": checkout_url,
        }})
    except Exception as e:
        logger.error(f"Failed to create Stripe checkout for partner {user_id}: {e}")
    
    # Audit log
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "partner_verified",
        "admin_id": current_user.id,
        "target_user_id": user_id,
        "details": {"custom_premium_rate": custom_rate, "checkout_url": checkout_url},
        "timestamp": now,
    })
    
    # Send Verification + Payment email
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "https://www.bidvex.com")
    company = user_doc.get("partner_company_name", "Partner")
    rate_info = f"{custom_rate*100:.1f}%" if custom_rate else "not yet set — you can configure it per listing"
    
    payment_section = ""
    if checkout_url:
        payment_section = f"""
            <h2 style="color:#2563eb;font-size:16px;margin:24px 0 8px;">Complete Your Activation</h2>
            <p style="font-size:14px;color:#475569;line-height:1.7;">
              To activate your partner account, please complete the annual platform fee payment of <strong>$100 CAD/year + applicable taxes</strong>.
              Your account features will be unlocked immediately upon payment.
            </p>
            <div style="margin:24px 0;text-align:center;">
              <a href="{checkout_url}" style="display:inline-block;background:#16a34a;color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:15px;">Pay $100 CAD/year &rarr; Activate Now</a>
            </div>
            <p style="font-size:12px;color:#94a3b8;text-align:center;">This is a recurring annual subscription. You can cancel anytime from your account settings.</p>
        """
    
    _send_partner_email(
        to_email=user_doc.get("email"),
        subject="BidVex Partner Application Approved — Complete Your Payment",
        html_content=f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:560px;margin:0 auto;color:#1e293b;">
          <div style="background:#2563eb;padding:24px 28px;border-radius:12px 12px 0 0;">
            <h1 style="color:#fff;margin:0;font-size:22px;">Application Approved!</h1>
            <p style="color:#bfdbfe;margin:6px 0 0;font-size:14px;">{company} has been approved as a BidVex Partner</p>
          </div>
          <div style="padding:28px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;">
            <p>Congratulations! Your application has been reviewed and approved.</p>
            {payment_section}
            <h2 style="color:#2563eb;font-size:16px;margin:24px 0 8px;">What You'll Unlock</h2>
            <ul style="color:#475569;font-size:14px;line-height:1.8;">
              <li><strong>Verified Auction Firm</strong> badge on all your listings</li>
              <li><strong>3% platform fee</strong> — the lowest in the industry</li>
              <li>Direct Stripe Connect payouts to your bank</li>
              <li>Custom buyer premium rates per auction</li>
            </ul>
            <h2 style="color:#2563eb;font-size:16px;margin:24px 0 8px;">Setting Your Premiums</h2>
            <p style="font-size:14px;color:#475569;line-height:1.7;">
              When creating a new listing, you'll see a <strong>"Buyer's Premium"</strong> field.
              You can set any rate — 10%, 15%, 18%, or any custom percentage.
              If you leave it empty, no buyer premium will be applied.
              Your current default rate is: <strong>{rate_info}</strong>.
            </p>
            <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;" />
            <p style="color:#94a3b8;font-size:12px;">
              Questions? Contact us at <a href="mailto:partners@bidvex.ca" style="color:#2563eb;">partners@bidvex.ca</a>
            </p>
          </div>
        </div>
        """
    )
    
    return {
        "success": True,
        "message": f"Partner {user_doc.get('email')} verified. Payment link sent via email.",
        "checkout_url": checkout_url,
    }


@admin_router.post("/partners/{user_id}/reject")
async def reject_partner(
    user_id: str,
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Admin: Reject a partner application with a reason."""
    current_user = await require_admin(credentials)
    db = get_db()
    
    reason = data.get("reason", "Application does not meet requirements.")
    now = datetime.now(timezone.utc).isoformat()
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "is_partner": False,
            "partner_verification_status": "rejected",
            "partner_rejection_reason": reason,
            "updated_at": now,
        }}
    )
    
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "partner_rejected",
        "admin_id": current_user.id,
        "target_user_id": user_id,
        "details": {"reason": reason},
        "timestamp": now,
    })
    
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "partner_company_name": 1})
    if user_doc:
        _send_partner_email(
            to_email=user_doc.get("email"),
            subject="BidVex Partner Application — Update",
            html_content=f"""
            <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:560px;margin:0 auto;color:#1e293b;">
              <div style="background:#475569;padding:24px 28px;border-radius:12px 12px 0 0;">
                <h1 style="color:#fff;margin:0;font-size:22px;">Application Update</h1>
              </div>
              <div style="padding:28px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;">
                <p>Dear {user_doc.get('partner_company_name', 'Applicant')},</p>
                <p>Thank you for your interest in the BidVex Partner Network. After reviewing your submitted credentials, we are unable to approve your application at this time.</p>
                <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:16px;margin:16px 0;">
                  <p style="margin:0;font-size:14px;color:#991b1b;"><strong>Reason:</strong> {reason}</p>
                </div>
                <p style="font-size:14px;color:#475569;">If you believe this is an error or have additional documentation to submit, please reach out to our team directly.</p>
                <div style="margin:20px 0;text-align:center;">
                  <a href="mailto:partners@bidvex.ca" style="display:inline-block;background:#2563eb;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">Contact partners@bidvex.ca</a>
                </div>
                <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;" />
                <p style="color:#94a3b8;font-size:12px;">This is an automated message from BidVex Inc.</p>
              </div>
            </div>
            """
        )
    
    return {"success": True, "message": "Partner application rejected."}


@admin_router.put("/partners/{user_id}/premium-rate")
async def update_partner_premium_rate(
    user_id: str,
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Admin: Update a verified partner's custom buyer premium rate."""
    current_user = await require_admin(credentials)
    db = get_db()
    
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc or not user_doc.get("is_partner"):
        raise HTTPException(status_code=400, detail="User is not a verified partner.")
    
    rate = data.get("custom_premium_rate")
    if rate is None or not isinstance(rate, (int, float)) or rate < 0:
        raise HTTPException(status_code=400, detail="custom_premium_rate must be a non-negative number (e.g., 0.18 for 18%).")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"custom_premium_rate": float(rate), "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"success": True, "message": f"Partner premium rate updated to {rate*100:.1f}%."}


@admin_router.post("/partners/{user_id}/toggle")
async def admin_toggle_partner(
    user_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Admin: One-click toggle is_partner status."""
    current_user = await require_admin(credentials)
    db = get_db()
    
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_partner = not user_doc.get("is_partner", False)
    now = datetime.now(timezone.utc).isoformat()
    update = {
        "is_partner": new_partner,
        "partner_verification_status": "verified" if new_partner else "unverified",
        "updated_at": now,
    }
    if new_partner:
        update["partner_verified_at"] = now
        update["platform_fee_paid"] = False
    else:
        update["platform_fee_paid"] = False
        update["partner_subscription_id"] = None
    
    await db.users.update_one({"id": user_id}, {"$set": update})
    
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": f"partner_toggled_{'on' if new_partner else 'off'}",
        "admin_id": current_user.id, "target_user_id": user_id,
        "timestamp": now,
    })
    return {"success": True, "is_partner": new_partner}


# ========== EMAIL SETTINGS ==========

@admin_router.get("/email-settings")
async def get_email_settings(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Admin: Get current email configuration status."""
    current_user = await require_admin(credentials)
    db = get_db()
    
    doc = await db.settings.find_one({"key": "sendgrid"}, {"_id": 0})
    config = await _get_sendgrid_config()
    
    masked_key = None
    if doc and doc.get("api_key"):
        k = doc["api_key"]
        masked_key = k[:5] + "..." + k[-4:] if len(k) > 12 else "***configured***"
    
    return {
        "configured": config is not None,
        "source": config["source"] if config else None,
        "masked_key": masked_key,
        "from_email": doc.get("from_email", "noreply@bidvex.com") if doc else "noreply@bidvex.com",
        "from_name": doc.get("from_name", "BidVex Partner Team") if doc else "BidVex Partner Team",
        "last_test_at": doc.get("last_test_at") if doc else None,
        "last_test_status": doc.get("last_test_status") if doc else None,
    }


@admin_router.post("/email-settings")
async def save_email_settings(
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Admin: Save SendGrid API key and sender config to database."""
    current_user = await require_admin(credentials)
    db = get_db()
    
    api_key = data.get("api_key", "").strip()
    from_email = data.get("from_email", "noreply@bidvex.com").strip()
    from_name = data.get("from_name", "BidVex Partner Team").strip()
    
    if not api_key:
        raise HTTPException(status_code=400, detail="API key is required.")
    if not api_key.startswith("SG."):
        raise HTTPException(status_code=400, detail="Invalid SendGrid API key format. Keys start with 'SG.'")
    
    now = datetime.now(timezone.utc).isoformat()
    await db.settings.update_one(
        {"key": "sendgrid"},
        {"$set": {
            "key": "sendgrid",
            "api_key": api_key,
            "from_email": from_email,
            "from_name": from_name,
            "updated_at": now,
            "updated_by": current_user.id,
        }},
        upsert=True
    )
    
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "email_settings_updated",
        "admin_id": current_user.id,
        "details": {"from_email": from_email},
        "timestamp": now,
    })
    
    return {"success": True, "message": "SendGrid settings saved. Use 'Send Test Email' to verify."}


@admin_router.post("/email-settings/test")
async def test_email_settings(
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Admin: Send a test email to verify SendGrid configuration."""
    current_user = await require_admin(credentials)
    db = get_db()
    
    recipient = data.get("recipient", current_user.email).strip()
    if not recipient or "@" not in recipient:
        raise HTTPException(status_code=400, detail="Valid recipient email required.")
    
    config = await _get_sendgrid_config()
    if not config:
        raise HTTPException(status_code=400, detail="SendGrid is not configured. Save your API key first.")
    
    now = datetime.now(timezone.utc).isoformat()
    test_html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:560px;margin:0 auto;color:#1e293b;">
      <div style="background:linear-gradient(135deg,#2563eb,#06b6d4);padding:24px 28px;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;margin:0;font-size:22px;">BidVex Email Test</h1>
        <p style="color:#bfdbfe;margin:6px 0 0;font-size:14px;">Configuration verified successfully</p>
      </div>
      <div style="padding:28px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;">
        <p>This is a test email from your BidVex Admin panel.</p>
        <p>If you're reading this, your SendGrid integration is working correctly.</p>
        <table style="font-size:14px;color:#475569;margin:16px 0;border-collapse:collapse;">
          <tr><td style="padding:4px 12px 4px 0;font-weight:bold;">Sent by:</td><td>{current_user.email}</td></tr>
          <tr><td style="padding:4px 12px 4px 0;font-weight:bold;">From:</td><td>{config['from_email']}</td></tr>
          <tr><td style="padding:4px 12px 4px 0;font-weight:bold;">Source:</td><td>{config['source']}</td></tr>
          <tr><td style="padding:4px 12px 4px 0;font-weight:bold;">Timestamp:</td><td>{now}</td></tr>
        </table>
        <p style="font-size:13px;color:#64748b;">Partner onboarding emails (application received, verification, rejection) are now active.</p>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;" />
        <p style="color:#94a3b8;font-size:12px;">BidVex Inc. — 103-761 Chalifoux Street, Sherbrooke, QC, J1G 0A8</p>
      </div>
    </div>
    """
    
    try:
        import sendgrid as sg_lib
        from sendgrid.helpers.mail import Mail, Email, To, Content
        sg = sg_lib.SendGridAPIClient(api_key=config["api_key"])
        from_email = Email(config["from_email"], config["from_name"])
        mail = Mail(from_email=from_email, to_emails=To(recipient), subject="BidVex Email Test — Configuration Verified", html_content=Content("text/html", test_html))
        response = sg.client.mail.send.post(request_body=mail.get())
        status = response.status_code
        
        await db.settings.update_one(
            {"key": "sendgrid"},
            {"$set": {"last_test_at": now, "last_test_status": "success", "last_test_recipient": recipient}}
        )
        
        await db.admin_logs.insert_one({
            "id": str(uuid.uuid4()),
            "action": "email_test_sent",
            "admin_id": current_user.id,
            "details": {"recipient": recipient, "status_code": status},
            "timestamp": now,
        })
        
        return {"success": True, "message": f"Test email sent to {recipient}. Check your inbox.", "status_code": status}
    except Exception as e:
        await db.settings.update_one(
            {"key": "sendgrid"},
            {"$set": {"last_test_at": now, "last_test_status": f"failed: {str(e)}"}}
        )
        raise HTTPException(status_code=400, detail=f"Email send failed: {str(e)}")


@admin_router.post("/admin/partners/{partner_id}/verified-firm")
async def toggle_verified_firm(partner_id: str, data: dict, current_user=Depends(get_admin_current_user)):
    """Admin toggle for 'Verified Auction Firm' badge."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    is_verified = data.get("is_verified_firm", False)

    result = await _db.users.update_one(
        {"id": partner_id, "is_partner": True},
        {"$set": {"is_verified_firm": is_verified}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Partner not found")

    return {"success": True, "is_verified_firm": is_verified}

