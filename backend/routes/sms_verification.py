"""
BidVex SMS Verification Router
Handles phone number verification using Twilio Verify API
Features:
- OTP sending with bilingual support (EN/FR)
- Rate limiting to prevent abuse
- Verification status tracking
- Admin audit logging
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import os
import logging
import re

logger = logging.getLogger(__name__)

sms_router = APIRouter(prefix="/sms", tags=["SMS Verification"])

# Database and rate limiting storage
_db = None
_rate_limit_store = {}  # In-memory rate limiting (use Redis in production)

# Rate limiting configuration
MAX_ATTEMPTS_PER_PHONE = 5  # Max verification attempts per phone per hour
MAX_SENDS_PER_PHONE = 3  # Max OTP sends per phone per hour
MAX_SENDS_PER_IP = 10  # Max OTP sends per IP per hour
COOLDOWN_SECONDS = 60  # Seconds between resend attempts


def set_db(db_instance):
    """Set database instance from main app"""
    global _db
    _db = db_instance


def get_db():
    """Get database instance"""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return _db


def get_twilio_client():
    """Get Twilio client with credentials from environment"""
    from twilio.rest import Client
    
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    
    if not account_sid or not auth_token or account_sid == "your_twilio_account_sid":
        logger.warning("Twilio credentials not configured - using mock mode")
        return None
    
    return Client(account_sid, auth_token)


def get_verify_service_sid():
    """Get Twilio Verify Service SID"""
    return os.environ.get("TWILIO_VERIFY_SERVICE_SID", "VA67a9820b7bb137d7b70f01dabbc12d15")


def validate_phone_number(phone: str) -> str:
    """Validate and normalize phone number to E.164 format"""
    # Remove spaces, dashes, parentheses
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Ensure it starts with +
    if not cleaned.startswith('+'):
        # Assume US/Canada if no country code
        if len(cleaned) == 10:
            cleaned = '+1' + cleaned
        elif len(cleaned) == 11 and cleaned.startswith('1'):
            cleaned = '+' + cleaned
        else:
            cleaned = '+' + cleaned
    
    # Basic E.164 validation
    if not re.match(r'^\+[1-9]\d{6,14}$', cleaned):
        raise HTTPException(status_code=400, detail="Invalid phone number format. Use E.164 format (e.g., +14155552671)")
    
    return cleaned


def check_rate_limit(key: str, limit: int, window_seconds: int = 3600) -> bool:
    """Check if rate limit is exceeded"""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=window_seconds)
    
    if key not in _rate_limit_store:
        _rate_limit_store[key] = []
    
    # Clean old entries
    _rate_limit_store[key] = [t for t in _rate_limit_store[key] if t > window_start]
    
    if len(_rate_limit_store[key]) >= limit:
        return False
    
    _rate_limit_store[key].append(now)
    return True


class SendOTPRequest(BaseModel):
    phone_number: str
    user_id: Optional[str] = None
    language: str = "en"  # 'en' or 'fr'


class VerifyOTPRequest(BaseModel):
    phone_number: str
    code: str
    user_id: Optional[str] = None


# ========== SEND OTP ==========
@sms_router.post("/send-otp")
async def send_otp(request: SendOTPRequest, req: Request):
    """
    Send a 6-digit OTP to the provided phone number via Twilio Verify
    Supports EN/FR localization
    """
    db = get_db()
    client_ip = req.client.host if req.client else "unknown"
    
    try:
        # Validate and normalize phone number
        phone = validate_phone_number(request.phone_number)
        
        # Rate limiting checks
        if not check_rate_limit(f"send_phone_{phone}", MAX_SENDS_PER_PHONE):
            raise HTTPException(
                status_code=429, 
                detail="Too many OTP requests for this phone number. Please wait before trying again."
            )
        
        if not check_rate_limit(f"send_ip_{client_ip}", MAX_SENDS_PER_IP):
            raise HTTPException(
                status_code=429,
                detail="Too many OTP requests from this IP. Please wait before trying again."
            )
        
        # Check cooldown for resend
        last_send = await db.sms_verifications.find_one(
            {"phone_number": phone, "verified": False},
            sort=[("created_at", -1)]
        )
        
        if last_send:
            last_send_time = datetime.fromisoformat(last_send["created_at"])
            cooldown_end = last_send_time + timedelta(seconds=COOLDOWN_SECONDS)
            if datetime.now(timezone.utc) < cooldown_end:
                remaining = int((cooldown_end - datetime.now(timezone.utc)).total_seconds())
                raise HTTPException(
                    status_code=429,
                    detail=f"Please wait {remaining} seconds before requesting a new code."
                )
        
        # Get Twilio client
        client = get_twilio_client()
        
        if client:
            # Live Twilio integration
            try:
                verification = client.verify.v2.services(get_verify_service_sid()) \
                    .verifications.create(
                        to=phone,
                        channel="sms",
                        locale=request.language  # 'en' or 'fr'
                    )
                
                status = verification.status
                logger.info(f"✅ OTP sent to {phone[:6]}*** via Twilio: {status}")
                
            except Exception as twilio_error:
                error_str = str(twilio_error)
                logger.error(f"Twilio error: {twilio_error}")
                
                # Check if it's a trial account limitation (unverified number)
                if "21608" in error_str or "unverified" in error_str.lower() or "trial" in error_str.lower():
                    # Fallback to mock mode for trial accounts
                    logger.warning(f"📱 Trial account limitation - falling back to mock mode for {phone[:6]}***")
                    import random
                    mock_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                    
                    await db.sms_verifications.update_one(
                        {"phone_number": phone, "verified": False},
                        {"$set": {
                            "mock_code": mock_code,
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }},
                        upsert=True
                    )
                    
                    status = "pending"
                    logger.info(f"📱 MOCK OTP for {phone}: {mock_code} (trial fallback)")
                else:
                    raise HTTPException(status_code=500, detail="Failed to send verification code. Please try again.")
        else:
            # Mock mode for development
            import random
            mock_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            
            # Store mock code in database
            await db.sms_verifications.update_one(
                {"phone_number": phone, "verified": False},
                {"$set": {
                    "mock_code": mock_code,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
            
            status = "pending"
            logger.info(f"📱 MOCK OTP for {phone}: {mock_code}")
        
        # Log verification attempt
        verification_record = {
            "id": str(uuid4()),
            "phone_number": phone,
            "user_id": request.user_id,
            "status": status,
            "language": request.language,
            "ip_address": client_ip,
            "verified": False,
            "attempts": 0,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.sms_verifications.insert_one(verification_record)
        
        # Bilingual response
        if request.language == "fr":
            message = "Code de vérification envoyé. Vérifiez vos SMS."
        else:
            message = "Verification code sent. Please check your SMS."
        
        return {
            "status": "sent",
            "message": message,
            "phone": phone[:6] + "***" + phone[-2:],  # Masked phone for security
            "cooldown_seconds": COOLDOWN_SECONDS
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending OTP: {e}")
        raise HTTPException(status_code=500, detail="Failed to send verification code")


# ========== VERIFY OTP ==========
@sms_router.post("/verify-otp")
async def verify_otp(request: VerifyOTPRequest, req: Request):
    """
    Verify the 6-digit OTP code against Twilio Verify
    """
    db = get_db()
    client_ip = req.client.host if req.client else "unknown"
    
    try:
        # Validate phone number
        phone = validate_phone_number(request.phone_number)
        code = request.code.strip()
        
        # Validate code format
        if not re.match(r'^\d{6}$', code):
            raise HTTPException(status_code=400, detail="Invalid code format. Please enter 6 digits.")
        
        # Rate limiting for verification attempts
        if not check_rate_limit(f"verify_phone_{phone}", MAX_ATTEMPTS_PER_PHONE):
            raise HTTPException(
                status_code=429,
                detail="Too many verification attempts. Please request a new code."
            )
        
        # Get Twilio client
        client = get_twilio_client()
        
        is_valid = False
        
        if client:
            # Live Twilio verification
            try:
                verification_check = client.verify.v2.services(get_verify_service_sid()) \
                    .verification_checks.create(
                        to=phone,
                        code=code
                    )
                
                is_valid = verification_check.status == "approved"
                logger.info(f"Twilio verification for {phone[:6]}***: {verification_check.status}")
                
            except Exception as twilio_error:
                logger.error(f"Twilio verification error: {twilio_error}")
                # Check if it's an invalid code error
                if "invalid" in str(twilio_error).lower() or "not found" in str(twilio_error).lower():
                    is_valid = False
                else:
                    raise HTTPException(status_code=500, detail="Verification service error. Please try again.")
        else:
            # Mock mode verification
            mock_record = await db.sms_verifications.find_one(
                {"phone_number": phone, "verified": False},
                sort=[("created_at", -1)]
            )
            
            if mock_record and mock_record.get("mock_code") == code:
                is_valid = True
                logger.info(f"✅ Mock verification successful for {phone}")
            else:
                is_valid = False
                logger.info(f"❌ Mock verification failed for {phone}")
        
        # Update verification record
        await db.sms_verifications.update_one(
            {"phone_number": phone, "verified": False},
            {
                "$set": {
                    "verified": is_valid,
                    "verified_at": datetime.now(timezone.utc).isoformat() if is_valid else None
                },
                "$inc": {"attempts": 1}
            }
        )
        
        if is_valid:
            # Update user's phone_verified status if user_id provided
            if request.user_id:
                await db.users.update_one(
                    {"id": request.user_id},
                    {"$set": {
                        "phone_verified": True,
                        "phone_number": phone,
                        "phone_verified_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                # Log to admin logs
                await db.admin_logs.insert_one({
                    "id": str(uuid4()),
                    "action": "phone_verification_completed",
                    "user_id": request.user_id,
                    "details": {
                        "phone": phone[:6] + "***" + phone[-2:],
                        "ip_address": client_ip
                    },
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
            
            return {
                "valid": True,
                "message": "Phone number verified successfully!",
                "message_fr": "Numéro de téléphone vérifié avec succès!"
            }
        else:
            return {
                "valid": False,
                "message": "Invalid or expired code. Please try again.",
                "message_fr": "Code invalide ou expiré. Veuillez réessayer."
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying OTP: {e}")
        raise HTTPException(status_code=500, detail="Verification failed")


# ========== CHECK VERIFICATION STATUS ==========
@sms_router.get("/status/{user_id}")
async def check_verification_status(user_id: str):
    """
    Check if a user's phone number is verified
    """
    db = get_db()
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "phone_verified": 1, "phone_number": 1})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user_id": user_id,
        "phone_verified": user.get("phone_verified", False),
        "phone_number": user.get("phone_number", "")[:6] + "***" if user.get("phone_number") else None
    }


# ========== RESEND COOLDOWN CHECK ==========
@sms_router.get("/cooldown/{phone_number}")
async def check_resend_cooldown(phone_number: str):
    """
    Check remaining cooldown time before resend is allowed
    """
    db = get_db()
    
    try:
        phone = validate_phone_number(phone_number)
        
        last_send = await db.sms_verifications.find_one(
            {"phone_number": phone, "verified": False},
            sort=[("created_at", -1)]
        )
        
        if last_send:
            last_send_time = datetime.fromisoformat(last_send["created_at"])
            cooldown_end = last_send_time + timedelta(seconds=COOLDOWN_SECONDS)
            remaining = max(0, int((cooldown_end - datetime.now(timezone.utc)).total_seconds()))
            
            return {
                "can_resend": remaining == 0,
                "remaining_seconds": remaining
            }
        
        return {
            "can_resend": True,
            "remaining_seconds": 0
        }
        
    except Exception as e:
        return {
            "can_resend": True,
            "remaining_seconds": 0
        }
