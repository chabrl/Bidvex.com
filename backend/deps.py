"""
Shared dependencies for all route modules.
Provides database access, authentication, and common models.
"""

from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from jose import jwt, JWTError, ExpiredSignatureError
import os
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)
jwt_secret = os.environ.get('JWT_SECRET', 'dev-secret-key-change-in-production')

# Database reference - set by server.py at startup
db = None

def set_db(database):
    global db
    db = database

def get_db():
    return db


# ─── Shared User Model ───
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    account_type: str = "personal"
    phone: str = ""
    address: Optional[str] = None
    company_name: Optional[str] = None
    tax_number: Optional[str] = None
    bank_details: Optional[Any] = None
    subscription_tier: str = "free"
    subscription_status: Optional[str] = None
    subscription_expiry: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    preferred_language: str = "en"
    preferred_currency: str = "CAD"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    picture: Optional[str] = None
    phone_verified: bool = False
    email_verified: bool = False
    bio: Optional[str] = None
    bio_fr: Optional[str] = None
    admin_verified: bool = False
    badge_type: Optional[str] = None
    verification_status: Optional[str] = None
    role: Optional[str] = None
    account_status: str = "active"
    is_partner: bool = False
    partner_status: Optional[str] = None
    partner_application: Optional[Dict[str, Any]] = None
    stripe_connect_id: Optional[str] = None
    stripe_connect_status: Optional[str] = None
    affiliate_code: Optional[str] = None
    referred_by: Optional[str] = None
    affiliate_earnings: float = 0.0
    privacy_settings: Optional[Dict[str, Any]] = None
    trust_score: Optional[Dict[str, Any]] = None
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None
    custom_premium_rate: Optional[float] = None
    personalized_recommendations: bool = True
    platform_fee_paid: bool = False
    partner_subscription_id: Optional[str] = None
    # iter355 — Stripe Identity (KYC) soft-gate at checkout/win.
    is_identity_verified: bool = False
    stripe_identity_status: Optional[str] = None  # requires_input|processing|verified|canceled|requires_action
    stripe_verification_session_id: Optional[str] = None
    identity_legal_name: Optional[str] = None
    identity_dob: Optional[str] = None


# ─── Auth Dependencies ───
async def get_current_user(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> User:
    token = None
    if "session_token" in request.cookies:
        token = request.cookies["session_token"]
    elif credentials:
        token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if not user_doc:
            raise HTTPException(status_code=401, detail="User not found")
        return User(**user_doc)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={
            "error": "token_expired",
            "message_en": "Your session has expired. Please log in again.",
            "message_fr": "Votre session a expiré. Veuillez vous reconnecter.",
        })
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Unified admin gate — use as a FastAPI dependency on any admin route."""
    if current_user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def get_current_user_optional(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[User]:
    token = None
    if "session_token" in request.cookies:
        token = request.cookies["session_token"]
    elif credentials:
        token = credentials.credentials
    if not token:
        return None
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            return None
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if not user_doc:
            return None
        return User(**user_doc)
    except JWTError:
        return None
