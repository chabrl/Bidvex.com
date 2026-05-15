"""
BidVex Authentication Routes
Handles user registration, login, password reset, and session management

Extracted from server.py for maintainability
"""

from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
import asyncio
import hashlib
import os
import secrets
import uuid
import logging
import aiohttp

logger = logging.getLogger(__name__)

# Router setup
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration — short-lived access tokens + long-lived refresh tokens
JWT_SECRET = os.environ.get('JWT_SECRET', 'dev-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get('ACCESS_TOKEN_EXPIRE_MINUTES', '60'))   # 1 hour
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get('REFRESH_TOKEN_EXPIRE_DAYS', '30'))       # 30 days
# Backwards-compat env var (older deployments may still set this)
JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', str(ACCESS_TOKEN_EXPIRE_MINUTES // 60 or 1)))

# Database connection (will be set from main app)
db = None


def set_auth_db(database):
    """Set database instance from main app"""
    global db
    db = database


# ============= PYDANTIC MODELS =============

class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    account_type: str = "personal"
    phone: Optional[str] = ""
    address: Optional[str] = ""
    company_name: Optional[str] = ""
    tax_number: Optional[str] = ""
    bank_details: Optional[str] = ""
    terms_agreed: bool = False
    ai_disclosure_consent: bool = False
    ref_code: Optional[str] = None


class SessionCreate(BaseModel):
    session_id: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ============= HELPER FUNCTIONS =============

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """Create JWT access token (short-lived, 60 minutes)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def create_refresh_token(user_id: str) -> str:
    """Create a long-lived (30-day) refresh token, hash-stored in DB for revocation."""
    token = secrets.token_urlsafe(48)
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    if db is not None:
        await db.refresh_tokens.insert_one({
            "user_id": user_id,
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "created_at": datetime.now(timezone.utc),
            "expires_at": expire,
            "revoked": False,
        })
    return token


async def get_current_user_from_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Extract and validate current user from JWT token"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


def get_client_ip(request: Request) -> str:
    """Extract client IP from request headers"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


from rate_limit import limiter as _limiter

MAX_LOGIN_ATTEMPTS = 5


# ============= AUTH ROUTES =============

@auth_router.post("/register")
@_limiter.limit("5/minute")
async def register(user_data: UserCreate, request: Request, background_tasks: BackgroundTasks):
    """
    Register a new user
    
    - Validates email uniqueness
    - Hashes password securely
    - Applies geolocation-based currency enforcement
    - Generates affiliate code for referral program
    """
    # Validate terms consent
    if not user_data.terms_agreed:
        raise HTTPException(status_code=400, detail="You must agree to the Terms of Service and Privacy Policy to create an account.")
    
    # Validate AI disclosure consent (Law 25 requirement)
    if not user_data.ai_disclosure_consent:
        raise HTTPException(status_code=400, detail="You must acknowledge the AI disclosure to create an account. / Vous devez accepter la divulgation sur l'IA pour créer un compte.")
    
    # Check existing user (email normalized to lowercase)
    normalized_email = user_data.email.strip().lower()
    existing = await db.users.find_one({"email": normalized_email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = hash_password(user_data.password)
    
    # Generate unique user ID
    user_id = str(uuid.uuid4())
    
    # Generate affiliate code
    prefix = user_id[:8].upper()
    import random
    import string
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    affiliate_code = f"BVX{prefix}{suffix}"
    
    # Get client IP for geolocation
    client_ip = get_client_ip(request)
    
    # Default currency settings
    preferred_currency = "CAD"
    enforced_currency = "CAD"
    currency_locked = False
    location_confidence = 0.5
    signup_country_code = None
    signup_country_name = None
    
    # Try to get geolocation data
    try:
        from geolocation_service import geolocation_service
        ip_location = await geolocation_service.get_location_from_ip(client_ip)
        confidence_data = geolocation_service.calculate_location_confidence(
            ip_location=ip_location,
            billing_country=None,
            shipping_country=None
        )
        enforcement_data = geolocation_service.determine_enforced_currency(
            ip_location=ip_location,
            confidence_data=confidence_data
        )
        preferred_currency = enforcement_data.get('enforced_currency', 'CAD')
        enforced_currency = enforcement_data.get('enforced_currency', 'CAD')
        currency_locked = enforcement_data.get('currency_locked', False)
        location_confidence = confidence_data.get('confidence_score', 0.5)
        signup_country_code = ip_location.get('country_code')
        signup_country_name = ip_location.get('country_name')
    except Exception as e:
        logger.warning(f"Geolocation failed for registration: {e}")
    
    now = datetime.now(timezone.utc)
    
    # Create user document
    user_doc = {
        "id": user_id,
        "email": normalized_email,
        "password": hashed_pwd,
        "name": user_data.name,
        "account_type": user_data.account_type,
        "phone": user_data.phone or "",
        "address": user_data.address or "",
        "company_name": user_data.company_name or "",
        "tax_number": user_data.tax_number or "",
        "bank_details": user_data.bank_details if isinstance(user_data.bank_details, dict) else None,
        "role": "user",
        "preferred_language": "en",
        "preferred_currency": preferred_currency,
        "enforced_currency": enforced_currency,
        "currency_locked": currency_locked,
        "location_confidence_score": location_confidence,
        "signup_country_code": signup_country_code,
        "signup_country_name": signup_country_name,
        "signup_ip": client_ip,
        "affiliate_code": affiliate_code,
        "referred_by": None,
        "referred_by_code": None,
        "referred_by_email": None,
        "referred_by_name": None,
        "phone_verified": False,
        "email_verified": False,
        "terms_agreed_at": now.isoformat(),
        "ai_disclosure_consent": True,
        "ai_consent_timestamp": now.isoformat(),
        "ai_consent_ip": client_ip,
        # iter201 — Dealer-license fields (province-aware). Legacy opc_permit_* mirrored for back-compat.
        "dealer_license_number": None,
        "dealer_license_verified": False,
        "dealer_license_province": None,
        "dealer_license_type": None,
        "neq": None,  # Quebec Enterprise Number — required only for QC dealers
        "vehicle_buyer_verification": None,  # set on first restricted-province bid attempt
        # LEGACY (preserved for back-compat — do not expose to users; new code reads dealer_license_*)
        "opc_permit_number": None,
        "opc_permit_verified": False,
        "created_at": now.isoformat(),
        "updated_at": None
    }
    
    await db.users.insert_one(user_doc)

    # ── Affiliate Referral Tracking ──
    ref_code = user_data.ref_code
    if ref_code:
        referrer = await db.users.find_one({"affiliate_code": ref_code}, {"_id": 0, "id": 1, "email": 1, "name": 1})
        if referrer and referrer["id"] != user_id:
            await db.users.update_one(
                {"id": user_id},
                {"$set": {
                    "referred_by": referrer["id"],
                    "referred_by_code": ref_code,
                    "referred_by_email": referrer.get("email"),
                    "referred_by_name": referrer.get("name"),
                }}
            )
            # Update user_doc to reflect the referral for the response + admin email
            user_doc["referred_by"] = referrer["id"]
            user_doc["referred_by_code"] = ref_code
            user_doc["referred_by_email"] = referrer.get("email")
            user_doc["referred_by_name"] = referrer.get("name")
            
            await db.affiliate_referrals.insert_one({
                "id": str(uuid.uuid4()),
                "affiliate_id": referrer["id"],
                "affiliate_code": ref_code,
                "referred_user_id": user_id,
                "referred_email": normalized_email,
                "click_timestamp": now.isoformat(),
                "signup_timestamp": now.isoformat(),
                "status": "pending",
                "converted": False,
                "first_purchase_at": None,
                "total_commission_earned": 0.0,
                "created_at": now.isoformat(),
            })
            logger.info(f"[AFFILIATE] New referral: {ref_code} → {normalized_email} (affiliate={referrer['id']})")
    
    # ── Welcome + Admin notification (NON-BLOCKING via FastAPI BackgroundTasks) ──
    # Welcome email is transactional (not subject to marketing email_suppressions).
    # Both run AFTER the HTTP response is sent, so the user never waits on SendGrid.
    try:
        from services.email_service import send_welcome_email as _send_welcome
        from services.admin_notifications import notify_admin_new_user as _notify_admin
        background_tasks.add_task(_send_welcome, user_doc)
        background_tasks.add_task(_notify_admin, user_doc)
        logger.info(f"[SIGNUP_EMAILS] Scheduled welcome + admin notify for {normalized_email} (provider=email)")
    except Exception as e:
        logger.error(f"[SIGNUP_EMAILS] Failed to schedule signup emails for {normalized_email}: {e}")

    # iter216 P3 — Enrol every new user in the 6-email onboarding journey.
    # Email 1 (Welcome) fires immediately; 2–6 are scheduled in the
    # `user_email_journey` collection and dispatched by the daily cron.
    try:
        from services.email_journey import schedule_journey_for_user
        background_tasks.add_task(schedule_journey_for_user, db, user_doc)
    except Exception as e:
        logger.error(f"[JOURNEY] Failed to enrol {normalized_email}: {e}")
    
    # Audit log for currency
    await db.currency_audit_logs.insert_one({
        "user_id": user_id,
        "action": "registration",
        "ip_address": client_ip,
        "timestamp": now.isoformat()
    })
    
    # Generate token
    token = create_access_token({"sub": user_id, "email": user_data.email, "role": "user"})
    
    # Prepare response (exclude password and _id)
    user_response = {k: v for k, v in user_doc.items() if k not in ["password", "_id"]}
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_response
    }


@auth_router.post("/login")
@_limiter.limit("5/minute")
async def login(credentials: UserLogin, request: Request):
    """
    Authenticate user with email and password.
    Brute-force protected: 5 failed attempts per IP → 24h block.
    """
    from services.brute_force import check_blocked, record_failure, reset_failures

    client_ip = get_client_ip(request)
    normalized_email = credentials.email.strip().lower()
    logger.info(f"[AUTH] Login attempt for '{normalized_email}' from IP {client_ip}")

    # ── Check if IP is blocked ──
    block_info = await check_blocked(client_ip)
    if block_info:
        logger.warning(f"[AUTH] BLOCKED IP {client_ip} attempted login for '{normalized_email}'")
        raise HTTPException(status_code=429, detail=block_info["reason"])

    user_doc = await db.users.find_one({"email": normalized_email})

    if not user_doc:
        logger.warning(f"[AUTH_DEBUG] Login attempt email: {normalized_email} | User found in DB: False")
        await record_failure(client_ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    stored_password = user_doc.get("password") or user_doc.get("password_hash", "")
    logger.info(f"[AUTH_DEBUG] Login attempt email: {normalized_email} | User found in DB: True | status: {user_doc.get('status')} | Hashed PW in DB starts with: {stored_password[:10] if stored_password else 'EMPTY'}")

    if not stored_password:
        logger.error(f"[AUTH_DEBUG] No password field in DB for '{normalized_email}'")
        await record_failure(client_ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(credentials.password, stored_password):
        # Skip brute force for admin users — they self-lock too easily during debugging
        is_admin = user_doc.get("role") in ("admin", "super_admin")
        if not is_admin:
            result = await record_failure(client_ip)
            remaining = MAX_LOGIN_ATTEMPTS - result["attempts"]
            logger.warning(f"[AUTH_DEBUG] PASSWORD MISMATCH for '{normalized_email}' (attempts: {result['attempts']}/{MAX_LOGIN_ATTEMPTS})")
            detail = "Invalid credentials"
            if 0 < remaining <= 3:
                detail = f"Invalid credentials. {remaining} attempt{'s' if remaining != 1 else ''} remaining before temporary block."
            elif result.get("blocked"):
                detail = "Too many failed attempts. Please wait 15 minutes and try again."
            raise HTTPException(status_code=401, detail=detail)
        else:
            logger.warning(f"[AUTH_DEBUG] PASSWORD MISMATCH for admin '{normalized_email}' — brute force skipped for admin role")
            raise HTTPException(status_code=401, detail="Invalid credentials")

    if user_doc.get("status") == "suspended":
        raise HTTPException(status_code=403, detail="Account suspended. Please contact support.")

    if user_doc.get("status") == "deactivated":
        raise HTTPException(status_code=403, detail="Account deactivated. Please contact support to reactivate.")

    # ── Success: clear failure counter ──
    await reset_failures(client_ip)
    logger.info(f"[AUTH] LOGIN SUCCESS for '{normalized_email}' (user_id={user_doc['id']}, role={user_doc.get('role')})")

    # Track last login
    user_agent = request.headers.get("user-agent", "unknown") if request else "unknown"
    await db.users.update_one(
        {"email": normalized_email},
        {"$set": {
            "last_login": datetime.now(timezone.utc).isoformat(),
            "last_login_ip": client_ip,
            "last_login_user_agent": user_agent,
        }}
    )

    # Generate token with role for RBAC
    token = create_access_token({
        "sub": user_doc["id"],
        "email": user_doc["email"],
        "role": user_doc.get("role", "user"),
    })
    refresh_token = await create_refresh_token(user_doc["id"])

    # Prepare response (exclude password and _id)
    user_response = {k: v for k, v in user_doc.items() if k not in ["password", "_id"]}
    
    return {
        "access_token": token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user_response
    }


# ============= REFRESH TOKEN ENDPOINT =============

class RefreshTokenRequest(BaseModel):
    refresh_token: str


@auth_router.post("/refresh")
@_limiter.limit("10/minute")
async def refresh_access_token(request: Request, payload: RefreshTokenRequest):
    """Exchange a valid refresh token for a new access token (with rotation)."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database unavailable")

    token_hash = hashlib.sha256(payload.refresh_token.encode()).hexdigest()
    stored = await db.refresh_tokens.find_one({
        "token_hash": token_hash,
        "revoked": False,
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })

    if not stored:
        raise HTTPException(status_code=401, detail={
            "error": "invalid_refresh_token",
            "message_en": "Invalid or expired refresh token. Please log in again.",
            "message_fr": "Jeton de rafraîchissement invalide ou expiré. Veuillez vous reconnecter.",
        })

    # Rotate — invalidate old token, issue new pair
    await db.refresh_tokens.update_one(
        {"_id": stored["_id"]},
        {"$set": {"revoked": True, "rotated_at": datetime.now(timezone.utc)}}
    )

    user_doc = await db.users.find_one({"id": stored["user_id"]}, {"_id": 0, "password": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User no longer exists")

    new_access_token = create_access_token({
        "sub": user_doc["id"],
        "email": user_doc["email"],
        "role": user_doc.get("role", "user"),
    })
    new_refresh_token = await create_refresh_token(user_doc["id"])

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@auth_router.post("/session")
async def process_session(session_data: SessionCreate):
    """
    Process OAuth session from Emergent Auth
    
    Used for Google OAuth login
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_data.session_id}
        ) as response:
            if response.status != 200:
                raise HTTPException(status_code=400, detail="Invalid session")
            
            data = await response.json()
            
            existing_user = await db.users.find_one({"email": data["email"]})
            
            if not existing_user:
                # Create new user from OAuth data
                user_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc)
                
                user_doc = {
                    "id": user_id,
                    "email": data["email"],
                    "name": data["name"],
                    "picture": data.get("picture"),
                    "account_type": "personal",
                    "phone": "",
                    "phone_verified": False,
                    "email_verified": True,  # OAuth emails are verified
                    "role": "user",
                    "preferred_language": "en",
                    "preferred_currency": "CAD",
                    "created_at": now.isoformat()
                }
                await db.users.insert_one(user_doc)
            else:
                user_id = existing_user["id"]
            
            # Create session token
            session_token = create_access_token({"sub": user_id})
            
            # Store session
            session_doc = {
                "user_id": user_id,
                "session_token": data["session_token"],
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.sessions.insert_one(session_doc)
            
            return {"session_token": session_token}


@auth_router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user_from_token)):
    """
    Logout current user by invalidating all sessions
    """
    await db.sessions.delete_many({"user_id": current_user["id"]})
    return {"message": "Logged out successfully"}


@auth_router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user_from_token)):
    """
    Get current authenticated user's profile
    
    Includes payment method status
    """
    # Add dynamic has_payment_method flag
    payment_methods_count = await db.payment_methods.count_documents({"user_id": current_user["id"]})
    current_user["has_payment_method"] = payment_methods_count > 0
    return current_user


@auth_router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    """
    Initiate password reset process
    
    Sends reset email if user exists
    Always returns success to prevent email enumeration
    """
    try:
        normalized_email = request.email.strip().lower()
        user_doc = await db.users.find_one({"email": normalized_email}, {"_id": 0})
        
        if user_doc:
            # Generate secure reset token
            reset_token = str(uuid.uuid4())
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            
            # Store reset token
            token_doc = {
                "id": str(uuid.uuid4()),
                "user_id": user_doc["id"],
                "token": reset_token,
                "expires_at": expires_at.isoformat(),
                "used": False,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.password_reset_tokens.insert_one(token_doc)
            
            # Try to send email
            try:
                from services.email_service import get_email_service
                email_service = get_email_service()
                
                if email_service.is_configured():
                    from config.email_templates import send_password_reset_email
                    
                    result = await send_password_reset_email(
                        email_service,
                        user=user_doc,
                        reset_token=reset_token,
                        language=user_doc.get('preferred_language', 'en')
                    )
                    
                    if result['success']:
                        logger.info(f"Password reset email sent to {request.email}")
                    else:
                        logger.error(f"Failed to send password reset email: {result.get('error')}")
                else:
                    logger.warning("Email service not configured - password reset email not sent")
            except Exception as e:
                logger.error(f"Error sending password reset email: {e}")
        
        # Always return success to prevent email enumeration
        return {
            "message": "If an account with that email exists, a password reset link has been sent.",
            "success": True
        }
        
    except Exception as e:
        logger.exception(f"Error in forgot_password: {e}")
        return {
            "message": "If an account with that email exists, a password reset link has been sent.",
            "success": True
        }


@auth_router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """
    Reset password using valid token
    """
    try:
        # Find the token
        token_doc = await db.password_reset_tokens.find_one(
            {"token": request.token, "used": False},
            {"_id": 0}
        )
        
        if not token_doc:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        
        # Check if token is expired
        expires_at = datetime.fromisoformat(token_doc["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(status_code=400, detail="Reset token has expired")
        
        # Get user
        user_doc = await db.users.find_one({"id": token_doc["user_id"]}, {"_id": 0})
        
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Validate password
        if len(request.new_password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")
        
        # Hash new password
        hashed_password = hash_password(request.new_password)
        
        # Update user password permanently
        await db.users.update_one(
            {"id": user_doc["id"]},
            {"$set": {
                "password": hashed_password,
                "password_changed_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        
        # Mark token as used
        await db.password_reset_tokens.update_one(
            {"token": request.token},
            {"$set": {"used": True}}
        )
        
        # Invalidate all sessions for security
        await db.sessions.delete_many({"user_id": user_doc["id"]})
        
        # Try to send confirmation email (raw HTML — bypasses broken SendGrid template)
        try:
            from services.email_service import get_email_service
            email_service = get_email_service()
            
            if email_service.is_configured():
                from config.email_templates import send_password_changed_email
                
                lang = user_doc.get('preferred_language', 'en')
                result = await send_password_changed_email(email_service, user_doc, language=lang)
                
                if result['success']:
                    logger.info(f"Password changed confirmation sent to {user_doc['email']}")
        except Exception as e:
            logger.error(f"Error sending password changed email: {e}")
        
        logger.info(f"Password reset successful for user {user_doc['id']}")
        
        return {
            "message": "Password reset successful. Please log in with your new password.",
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in reset_password: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while resetting password")


@auth_router.get("/verify-reset-token/{token}")
async def verify_reset_token(token: str):
    """
    Verify if a reset token is valid and not expired
    
    Used by frontend to check token before showing password reset form
    """
    try:
        token_doc = await db.password_reset_tokens.find_one(
            {"token": token, "used": False},
            {"_id": 0}
        )
        
        if not token_doc:
            return {"valid": False, "message": "Invalid or already used token"}
        
        # Check if expired
        expires_at = datetime.fromisoformat(token_doc["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            return {"valid": False, "message": "Token has expired"}
        
        # Calculate time remaining
        time_remaining = expires_at - datetime.now(timezone.utc)
        minutes_remaining = int(time_remaining.total_seconds() / 60)
        
        return {
            "valid": True,
            "message": "Token is valid",
            "expires_in_minutes": minutes_remaining
        }
        
    except Exception as e:
        logger.exception(f"Error verifying reset token: {e}")
        return {"valid": False, "message": "Error verifying token"}


# Export the router
__all__ = ['auth_router', 'set_auth_db', 'get_current_user_from_token']


@auth_router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user_from_token)
):
    """
    Authenticated password change.
    Requires current password verification before updating.
    """
    try:
        user_doc = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")

        # Verify current password — admin-created accounts store the hash under
        # `password_hash`; regular signup uses `password`. Mirror the login flow.
        stored_password = user_doc.get("password") or user_doc.get("password_hash", "")
        if not stored_password or not verify_password(request.current_password, stored_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        # Validate new password strength
        new_pw = request.new_password
        if len(new_pw) < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
        if not any(c.isupper() for c in new_pw):
            raise HTTPException(status_code=400, detail="New password must contain an uppercase letter")
        if not any(c.isdigit() for c in new_pw):
            raise HTTPException(status_code=400, detail="New password must contain a number")

        if request.current_password == new_pw:
            raise HTTPException(status_code=400, detail="New password must be different from the current one")

        # Hash and save — write to canonical `password` field, drop legacy `password_hash`,
        # and clear the forced-reset flag for admin-created accounts.
        hashed = hash_password(new_pw)
        await db.users.update_one(
            {"id": current_user["id"]},
            {
                "$set": {
                    "password": hashed,
                    "password_changed_at": datetime.now(timezone.utc).isoformat(),
                    "password_reset_required": False,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                "$unset": {"password_hash": ""},
            }
        )

        # Send confirmation email (raw HTML — bypasses broken SendGrid template)
        try:
            from services.email_service import get_email_service
            email_service = get_email_service()
            if email_service.is_configured():
                from config.email_templates import send_password_changed_email
                lang = user_doc.get('preferred_language', 'en')
                await send_password_changed_email(email_service, user_doc, language=lang)
        except Exception as e:
            logger.error(f"Error sending password changed email: {e}")

        logger.info(f"Password changed for user {current_user['id']}")
        return {"success": True, "message": "Password updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error in change_password: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while changing password")


@auth_router.post("/force-reset-password")
async def force_reset_password(request: Request):
    """
    Complete forced password reset for admin-created accounts.
    Used when password_reset_required = true.
    """
    body = await request.json()
    reset_token = body.get("reset_token", "")
    new_password = body.get("new_password", "")

    try:
        payload = jwt.decode(reset_token, JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        purpose = payload.get("purpose")
        if purpose != "password_reset":
            raise HTTPException(status_code=400, detail="Invalid token purpose")
    except JWTError as e:
        raise HTTPException(status_code=400, detail=f"Invalid or expired token: {str(e)}")

    user_doc = await db.users.find_one({"id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    if not user_doc.get("password_reset_required", False):
        raise HTTPException(status_code=400, detail="Password reset not required for this account")

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")

    hashed_password = hash_password(new_password)
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "password": hashed_password,
            "password_reset_required": False,
            "password_changed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    await db.sessions.delete_many({"user_id": user_id})

    await db.admin_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "force_password_reset_completed",
        "target_user_id": user_id,
        "target_email": user_doc.get("email"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    logger.info(f"Forced password reset completed for user {user_id}")
    return {"success": True, "message": "Password reset successful. Please log in with your new password."}



@auth_router.post("/admin-force-sync")
async def admin_force_password_sync(request: Request):
    """
    One-time admin password sync endpoint.
    Uses the EXACT same hash_password() as login verification.
    Requires a secret header to prevent abuse.
    """
    body = await request.json()
    email = body.get("email", "").strip().lower()
    new_password = body.get("new_password", "")
    sync_key = request.headers.get("X-Sync-Key", "")

    # Require the JWT_SECRET as the sync key to prevent abuse
    if sync_key != JWT_SECRET:
        raise HTTPException(status_code=403, detail="Invalid sync key")

    if not email or not new_password:
        raise HTTPException(status_code=400, detail="Email and new_password required")

    user_doc = await db.users.find_one({"email": email}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    # Hash with the EXACT same function used in login verification
    hashed = hash_password(new_password)

    # Verify roundtrip immediately
    if not verify_password(new_password, hashed):
        raise HTTPException(status_code=500, detail="CRITICAL: Hash roundtrip failed")

    await db.users.update_one(
        {"email": email},
        {"$set": {
            "password": hashed,
            "password_changed_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    # Clear any brute force blocks
    from services.brute_force import reset_failures, unblock_ip
    client_ip = get_client_ip(request)
    await reset_failures(client_ip)

    logger.info(f"[AUTH_DEBUG] Admin force-sync completed for '{email}' — hash starts with: {hashed[:10]}")
    return {"success": True, "message": f"Password synced for {email}. Hash verified."}



# ============= EMAIL CHANGE WITH VERIFICATION (Law 25 Compliance) =============

class EmailChangeRequest(BaseModel):
    new_email: EmailStr
    current_password: str


@auth_router.post("/email-change/request")
async def request_email_change(
    request: EmailChangeRequest,
    current_user: dict = Depends(get_current_user_from_token),
):
    """
    Step 1: User requests an email change.
    Validates current password, then sends a confirmation link to the NEW email address.
    The change is only applied after the user clicks the link (Law 25 + security).
    """
    new_email = request.new_email.strip().lower()
    user_doc = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify current password before allowing change
    stored_pw = user_doc.get("password") or user_doc.get("password_hash", "")
    if not stored_pw or not verify_password(request.current_password, stored_pw):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if new_email == (user_doc.get("email") or "").lower():
        raise HTTPException(status_code=400, detail="New email is the same as current email")

    # Check uniqueness
    existing = await db.users.find_one({"email": new_email})
    if existing:
        raise HTTPException(status_code=400, detail="That email is already registered to another account")

    token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    await db.email_change_tokens.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": current_user["id"],
        "old_email": user_doc.get("email"),
        "new_email": new_email,
        "token": token,
        "used": False,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Send verification link to NEW email
    confirm_url = f"{os.environ.get('FRONTEND_URL', 'https://bidvex.com')}/settings?email_change_token={token}"
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        api_key = os.environ.get("SENDGRID_API_KEY")
        from_email = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@bidvex.com")
        from_name = os.environ.get("SENDGRID_FROM_NAME", "BidVex Canada")
        if api_key:
            lang = user_doc.get("preferred_language", "en")
            subject_en = "Confirm your new email address — BidVex"
            subject_fr = "Confirmez votre nouvelle adresse courriel — BidVex"
            body_en = f"""
                <p>Hi {user_doc.get('name', '')},</p>
                <p>You requested to change your BidVex account email to <strong>{new_email}</strong>.</p>
                <p>To confirm this change, click the button below within 24 hours:</p>
                <p><a href="{confirm_url}" style="display:inline-block;padding:12px 24px;background:#1E3A8A;color:#fff;border-radius:8px;text-decoration:none;">Confirm new email</a></p>
                <p>If you did not request this change, ignore this email — your account is safe.</p>
            """
            body_fr = f"""
                <p>Bonjour {user_doc.get('name', '')},</p>
                <p>Vous avez demandé de changer votre courriel BidVex pour <strong>{new_email}</strong>.</p>
                <p>Pour confirmer ce changement, cliquez sur le bouton ci-dessous dans les 24 heures :</p>
                <p><a href="{confirm_url}" style="display:inline-block;padding:12px 24px;background:#1E3A8A;color:#fff;border-radius:8px;text-decoration:none;">Confirmer la nouvelle adresse</a></p>
                <p>Si vous n'avez pas demandé ce changement, ignorez ce courriel — votre compte reste sécurisé.</p>
            """
            mail = Mail(
                from_email=(from_email, from_name),
                to_emails=new_email,
                subject=subject_fr if lang == "fr" else subject_en,
                html_content=body_fr if lang == "fr" else body_en,
            )
            mail.tracking_settings = None
            sg = SendGridAPIClient(api_key)
            sg.send(mail)
            logger.info(f"[EMAIL_CHANGE] Verification link sent to new email '{new_email}' for user {current_user['id']}")
    except Exception as e:
        logger.error(f"[EMAIL_CHANGE] Failed to send verification email: {e}")

    return {
        "success": True,
        "message": "A verification link has been sent to your new email address. Please check your inbox to confirm the change.",
    }


class EmailChangeConfirm(BaseModel):
    token: str


@auth_router.post("/email-change/confirm")
async def confirm_email_change(payload: EmailChangeConfirm):
    """
    Step 2: User clicks confirmation link in their new email inbox.
    Token is validated, email updated atomically, all sessions invalidated.
    """
    token_doc = await db.email_change_tokens.find_one(
        {"token": payload.token, "used": False}, {"_id": 0}
    )
    if not token_doc:
        raise HTTPException(status_code=400, detail="Invalid or already-used confirmation link")

    expires_at = datetime.fromisoformat(token_doc["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Confirmation link has expired")

    new_email = token_doc["new_email"]
    # Re-check uniqueness at confirm-time
    existing = await db.users.find_one({"email": new_email, "id": {"$ne": token_doc["user_id"]}})
    if existing:
        raise HTTPException(status_code=400, detail="That email is now registered to another account")

    await db.users.update_one(
        {"id": token_doc["user_id"]},
        {"$set": {
            "email": new_email,
            "email_verified": True,
            "email_changed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    await db.email_change_tokens.update_one(
        {"token": payload.token},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc).isoformat()}},
    )
    # Invalidate all sessions — user must log in again with new email
    await db.sessions.delete_many({"user_id": token_doc["user_id"]})
    logger.info(f"[EMAIL_CHANGE] Email confirmed: user={token_doc['user_id']} new={new_email}")
    return {"success": True, "message": "Email updated. Please log in with your new email address.", "new_email": new_email}



# ============================================================================
# DIRECT GOOGLE OAUTH 2.0 (replaces auth.emergentagent.com proxy flow)
# ----------------------------------------------------------------------------
# Routes:
#   GET /api/auth/google?redirect=/marketplace   → 302 to Google consent
#   GET /api/auth/google/callback?code=&state=    → finds/creates user, signs
#                                                    JWT, 302 to frontend
#                                                    /auth/google/finish#token=...
#
# REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS,
#           THIS BREAKS THE AUTH. The redirect_uri sent to Google MUST match
#           a value listed in Google Cloud Console → Authorized Redirect URIs
#           exactly. Configure via the GOOGLE_CALLBACK_URL env var.
# ============================================================================

import secrets as _secrets_unused  # noqa: F401  (kept for backwards compat; canonical import is at module top)
from urllib.parse import urlencode

import httpx
from fastapi.responses import RedirectResponse


GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_CALLBACK_URL = os.environ.get("GOOGLE_CALLBACK_URL", "")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@auth_router.get("/google")
async def google_oauth_start(request: Request, redirect: str = "/marketplace"):
    """
    Step 1 — Generate state, store it in a short-lived DB record, redirect to
    Google's consent screen.
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CALLBACK_URL:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CALLBACK_URL.",
        )

    state = secrets.token_urlsafe(32)
    await db.oauth_states.insert_one({
        "state": state,
        "post_login_redirect": redirect or "/marketplace",
        "created_at": datetime.now(timezone.utc),
        "ip": get_client_ip(request),
        "ua": request.headers.get("user-agent", ""),
    })

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_CALLBACK_URL,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "select_account",
        "state": state,
    }
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}", status_code=302)


def _frontend_url() -> str:
    """Frontend base URL — required for the post-callback redirect."""
    return (
        os.environ.get("FRONTEND_URL")
        or os.environ.get("REACT_APP_FRONTEND_URL")
        or ""
    ).rstrip("/")


@auth_router.get("/google/callback")
async def google_oauth_callback(request: Request, background_tasks: BackgroundTasks, code: str = "", state: str = "", error: str = ""):
    """
    Step 2 — Validate state, exchange code → tokens, fetch userinfo,
    find-or-create user in MongoDB, sign JWT, redirect to frontend with token
    in the URL fragment (#token=...) so it never hits a server log.
    """
    frontend = _frontend_url()
    if not frontend:
        raise HTTPException(
            status_code=500,
            detail="FRONTEND_URL env var not configured — cannot complete redirect.",
        )

    # User denied / Google returned an error
    if error:
        return RedirectResponse(url=f"{frontend}/auth?google_error={error}", status_code=302)
    if not code or not state:
        return RedirectResponse(url=f"{frontend}/auth?google_error=missing_code_or_state", status_code=302)

    # Validate state (CSRF protection) and consume it
    state_doc = await db.oauth_states.find_one_and_delete({"state": state})
    if not state_doc:
        return RedirectResponse(url=f"{frontend}/auth?google_error=invalid_state", status_code=302)

    # Reject states older than 10 minutes (defense in depth)
    created_at = state_doc.get("created_at")
    if isinstance(created_at, datetime):
        if (datetime.now(timezone.utc) - created_at.replace(tzinfo=timezone.utc) if created_at.tzinfo is None else datetime.now(timezone.utc) - created_at).total_seconds() > 600:
            return RedirectResponse(url=f"{frontend}/auth?google_error=state_expired", status_code=302)

    # Exchange code for tokens
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            tok_resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": GOOGLE_CALLBACK_URL,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if tok_resp.status_code != 200:
                logger.error(f"[GOOGLE_OAUTH] token exchange {tok_resp.status_code}: {tok_resp.text[:300]}")
                return RedirectResponse(url=f"{frontend}/auth?google_error=token_exchange_failed", status_code=302)
            tokens = tok_resp.json()

            access_token = tokens.get("access_token")
            if not access_token:
                return RedirectResponse(url=f"{frontend}/auth?google_error=no_access_token", status_code=302)

            # Fetch userinfo
            ui_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if ui_resp.status_code != 200:
                logger.error(f"[GOOGLE_OAUTH] userinfo {ui_resp.status_code}: {ui_resp.text[:300]}")
                return RedirectResponse(url=f"{frontend}/auth?google_error=userinfo_failed", status_code=302)
            userinfo = ui_resp.json()
    except Exception as e:
        logger.error(f"[GOOGLE_OAUTH] network error: {type(e).__name__}: {e}")
        return RedirectResponse(url=f"{frontend}/auth?google_error=network", status_code=302)

    google_email = (userinfo.get("email") or "").strip().lower()
    google_sub = userinfo.get("sub")
    if not google_email or not userinfo.get("email_verified", False):
        return RedirectResponse(url=f"{frontend}/auth?google_error=email_not_verified", status_code=302)

    # Find-or-create user
    now = datetime.now(timezone.utc)
    user = await db.users.find_one({"email": google_email}, {"_id": 0, "password": 0})

    if not user:
        new_id = str(uuid.uuid4())

        # Geolocate signup IP for admin notification (best-effort, never blocks)
        signup_country_code = None
        signup_country_name = None
        try:
            from geolocation_service import geolocation_service
            ip_location = await geolocation_service.get_location_from_ip(get_client_ip(request))
            signup_country_code = ip_location.get("country_code")
            signup_country_name = ip_location.get("country_name")
        except Exception as e:
            logger.warning(f"[GOOGLE_OAUTH] geolocation lookup failed: {e}")

        user = {
            "id": new_id,
            "email": google_email,
            "name": userinfo.get("name") or google_email.split("@")[0],
            "picture": userinfo.get("picture", ""),
            "google_sub": google_sub,
            "auth_provider": "google",
            "email_verified": True,
            "role": "user",
            "subscription_tier": "free",
            "preferred_language": "en",
            "preferred_currency": "CAD",
            "signup_country_code": signup_country_code,
            "signup_country_name": signup_country_name,
            "signup_ip": get_client_ip(request),
            "referred_by": None,
            "referred_by_code": None,
            "referred_by_email": None,
            "referred_by_name": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "last_login_at": now.isoformat(),
        }
        try:
            await db.users.insert_one(user.copy())
            logger.info(f"[GOOGLE_OAUTH] new user created via Google: {google_email}")
        except Exception as e:
            logger.error(f"[GOOGLE_OAUTH] insert user failed: {e}")
            return RedirectResponse(url=f"{frontend}/auth?google_error=user_creation_failed", status_code=302)

        # ── Welcome + Admin notification (NON-BLOCKING via FastAPI BackgroundTasks) ──
        # Only fires for NEW Google users — existing users skip the welcome.
        # Welcome email is transactional (not subject to marketing email_suppressions).
        try:
            from services.email_service import send_welcome_email as _send_welcome
            from services.admin_notifications import notify_admin_new_user as _notify_admin
            background_tasks.add_task(_send_welcome, user)
            background_tasks.add_task(_notify_admin, user)
            logger.info(f"[SIGNUP_EMAILS] Scheduled welcome + admin notify for {google_email} (provider=google)")
        except Exception as e:
            logger.error(f"[SIGNUP_EMAILS] Failed to schedule Google signup emails for {google_email}: {e}")

        # iter216 P3 — Enrol Google-OAuth signups in the 6-email journey too.
        try:
            from services.email_journey import schedule_journey_for_user
            background_tasks.add_task(schedule_journey_for_user, db, user)
        except Exception as e:
            logger.error(f"[JOURNEY] Failed to enrol Google user {google_email}: {e}")
    else:
        # Update existing user with latest Google data + login timestamp
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {
                "google_sub": google_sub,
                "picture": user.get("picture") or userinfo.get("picture", ""),
                "email_verified": True,
                "last_login_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }},
        )

    # Sign JWT
    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "role": user.get("role", "user"),
    })

    # Redirect to frontend with token in URL fragment (never logged)
    safe_redirect = state_doc.get("post_login_redirect", "/marketplace")
    if not safe_redirect.startswith("/"):
        safe_redirect = "/marketplace"
    finish_url = f"{frontend}/auth/google/finish#token={token}&redirect={safe_redirect}"
    return RedirectResponse(url=finish_url, status_code=302)
