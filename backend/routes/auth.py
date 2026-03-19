"""
BidVex Authentication Routes
Handles user registration, login, password reset, and session management

Extracted from server.py for maintainability
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
import os
import uuid
import logging
import aiohttp

logger = logging.getLogger(__name__)

# Router setup
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
security = HTTPBearer(auto_error=False)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
JWT_SECRET = os.environ.get('JWT_SECRET', 'dev-secret-key-change-in-production')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

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


class SessionCreate(BaseModel):
    session_id: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
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
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


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


# ============= AUTH ROUTES =============

@auth_router.post("/register")
async def register(user_data: UserCreate, request: Request):
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
    
    # Check existing user
    existing = await db.users.find_one({"email": user_data.email})
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
    except Exception as e:
        logger.warning(f"Geolocation failed for registration: {e}")
    
    now = datetime.now(timezone.utc)
    
    # Create user document
    user_doc = {
        "id": user_id,
        "email": user_data.email,
        "password": hashed_pwd,
        "name": user_data.name,
        "account_type": user_data.account_type,
        "phone": user_data.phone or "",
        "address": user_data.address or "",
        "company_name": user_data.company_name or "",
        "tax_number": user_data.tax_number or "",
        "bank_details": user_data.bank_details or "",
        "role": "user",
        "preferred_language": "en",
        "preferred_currency": preferred_currency,
        "enforced_currency": enforced_currency,
        "currency_locked": currency_locked,
        "location_confidence_score": location_confidence,
        "affiliate_code": affiliate_code,
        "phone_verified": False,
        "email_verified": False,
        "terms_agreed_at": now.isoformat(),
        "created_at": now.isoformat(),
        "updated_at": None
    }
    
    await db.users.insert_one(user_doc)
    
    # Audit log for currency
    await db.currency_audit_logs.insert_one({
        "user_id": user_id,
        "action": "registration",
        "ip_address": client_ip,
        "timestamp": now.isoformat()
    })
    
    # Generate token
    token = create_access_token({"sub": user_id, "email": user_data.email, "role": "user"})
    
    # Prepare response (exclude password)
    user_response = {k: v for k, v in user_doc.items() if k != "password"}
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_response
    }


@auth_router.post("/login")
async def login(credentials: UserLogin, request: Request):
    """
    Authenticate user with email and password
    
    Returns JWT token on success
    """
    user_doc = await db.users.find_one({"email": credentials.email})
    
    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(credentials.password, user_doc.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user_doc.get("status") == "suspended":
        raise HTTPException(status_code=403, detail="Account suspended. Please contact support.")

    if user_doc.get("status") == "deactivated":
        raise HTTPException(status_code=403, detail="Account deactivated. Please contact support to reactivate.")

    # Track last login
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "unknown") if request else "unknown"
    await db.users.update_one(
        {"email": credentials.email},
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
    
    # Prepare response (exclude password and _id)
    user_response = {k: v for k, v in user_doc.items() if k not in ["password", "_id"]}
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_response
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
        user_doc = await db.users.find_one({"email": request.email}, {"_id": 0})
        
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
        
        # Update user password
        await db.users.update_one(
            {"id": user_doc["id"]},
            {"$set": {"password": hashed_password}}
        )
        
        # Mark token as used
        await db.password_reset_tokens.update_one(
            {"token": request.token},
            {"$set": {"used": True}}
        )
        
        # Invalidate all sessions for security
        await db.sessions.delete_many({"user_id": user_doc["id"]})
        
        # Try to send confirmation email
        try:
            from services.email_service import get_email_service
            email_service = get_email_service()
            
            if email_service.is_configured():
                from config.email_templates import EmailTemplates, EmailDataBuilder
                
                result = await email_service.send_email(
                    to=user_doc["email"],
                    template_id=EmailTemplates.PASSWORD_CHANGED,
                    dynamic_data=EmailDataBuilder.password_changed_email(user_doc),
                    language=user_doc.get('preferred_language', 'en')
                )
                
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


@auth_router.post("/force-reset-password")
async def force_reset_password(request: Request):
    """
    Complete forced password reset for admin-created accounts.
    Used when password_reset_required = true.
    """
    from jose import JWTError
    body = await request.json()
    reset_token = body.get("reset_token", "")
    new_password = body.get("new_password", "")

    try:
        payload = jwt.decode(reset_token, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        purpose = payload.get("purpose")
        if purpose != "password_reset":
            raise HTTPException(status_code=400, detail="Invalid token purpose")
    except (JWTError, jwt.PyJWTError) as e:
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

