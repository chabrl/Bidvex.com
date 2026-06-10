"""
iter210 Step 5 — Admin-Created Demo Accounts.

Demo accounts let BidVex onboard companies for sales demos WITHOUT requiring
them to go through the full verification flow. Restrictions:
  * `is_demo_account=True` — gates Stripe payments + filters demo listings
    from public search
  * `demo_expires_at` — daily scheduler flips status to "demo_expired"
  * `account_type` ∈ {vehicle_dealer, partner, storage_facility}
  * Auto-grants `subscription_tier=vip_elite` for the best UX
  * No Stripe subscription created

Storage:
  * users.is_demo_account, demo_expires_at, demo_created_by, demo_notes,
    demo_status ("active" | "expiring_soon" | "expired"), demo_temp_password_set_at
"""
from __future__ import annotations

import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from passlib.context import CryptContext

logger = logging.getLogger(__name__)

DEMO_ACCOUNT_TYPES = {"vehicle_dealer", "partner", "storage_facility", "auctioneer"}
DEMO_DURATION_PRESETS = {7, 14, 30}

# Same passlib config as routes/auth.py so demo accounts can log in normally
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _generate_temp_password(length: int = 14) -> str:
    """Generate a URL-safe random password. Stored only as bcrypt hash."""
    return secrets.token_urlsafe(length)[:length]


async def create_demo_account(
    db,
    *,
    account_type: str,
    company_name: str,
    contact_email: str,
    province: str,
    duration_days: int,
    notes: str = "",
    created_by_email: str = "system",
) -> dict:
    """Create a fully functional demo account. Returns dict including temp password."""
    if account_type not in DEMO_ACCOUNT_TYPES:
        raise ValueError(f"account_type must be one of {DEMO_ACCOUNT_TYPES}")
    if not contact_email or "@" not in contact_email:
        raise ValueError("invalid contact_email")
    if duration_days <= 0 or duration_days > 365:
        raise ValueError("duration_days must be 1..365")

    contact_email = contact_email.strip().lower()

    # Don't overwrite a real user
    existing = await db.users.find_one({"email": contact_email}, {"_id": 0, "id": 1, "is_demo_account": 1})
    if existing and not existing.get("is_demo_account"):
        raise ValueError("email_already_used_by_real_account")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=duration_days)
    temp_password = _generate_temp_password()
    password_hash = _pwd_context.hash(temp_password)
    uid = existing["id"] if existing else str(uuid.uuid4())

    # Roles + bypass flags
    user_doc = {
        "id": uid,
        "email": contact_email,
        "password": password_hash,
        "name": company_name,
        "role": "user",
        "account_type": account_type,
        "subscription_tier": "vip_elite",   # best UX for demos
        "phone_verified": True,
        "email_verified": True,
        "is_demo_account": True,
        "demo_account_type": account_type,
        "demo_company_name": company_name,
        "demo_province": province,
        "demo_expires_at": expires_at,
        "demo_created_by": created_by_email,
        "demo_created_at": now,
        "demo_notes": notes,
        "demo_status": "active",
        "demo_temp_password_set_at": now,
    }
    # Account-type-specific bypass flags so the demo can use every screen
    if account_type == "vehicle_dealer":
        user_doc["is_vehicle_dealer"] = True
        user_doc["dealer_license_verified"] = True
        user_doc["account_type"] = "vehicle_dealer"
    elif account_type == "partner":
        user_doc["is_partner"] = True
        user_doc["partner_verification_status"] = "verified"
        user_doc["partner_verified_at"] = now
        user_doc["partner_company_name"] = company_name
        user_doc["account_type"] = "partner"
    elif account_type == "storage_facility":
        user_doc["is_storage_facility"] = True
        user_doc["account_type"] = "storage_facility"
    elif account_type == "auctioneer":
        # iter223 — Auctioneer demos act as multi-lot auction operators
        # (the "AUC" persona). They get partner-tier UX + multi-item creation
        # permissions so leads can experience the full lot-bidding flow.
        user_doc["is_auctioneer"] = True
        user_doc["is_partner"] = True
        user_doc["partner_verification_status"] = "verified"
        user_doc["partner_verified_at"] = now
        user_doc["partner_company_name"] = company_name
        user_doc["account_type"] = "auctioneer"

    if existing:
        await db.users.update_one({"id": uid}, {"$set": user_doc})
    else:
        user_doc["created_at"] = now
        await db.users.insert_one(user_doc)

    # Welcome email
    email_sent = False
    try:
        from services.emails._email_core import send_email
        await send_email(
            to_email=contact_email,
            subject="Your BidVex Demo Account is Ready · Votre compte de démonstration BidVex est prêt",
            html_content=_welcome_email_html(
                company_name=company_name,
                login_email=contact_email,
                temp_password=temp_password,
                expires_at=expires_at,
                account_type=account_type,
            ),
        )
        email_sent = True
    except Exception as exc:
        logger.exception(f"[iter210] demo welcome email crashed for {contact_email}: {exc}")

    return {
        "id": uid,
        "email": contact_email,
        "temp_password": temp_password,
        "expires_at": expires_at.isoformat(),
        "account_type": account_type,
        "company_name": company_name,
        "welcome_email_sent": email_sent,
    }


def _welcome_email_html(*, company_name: str, login_email: str, temp_password: str,
                       expires_at: datetime, account_type: str) -> str:
    type_label = {
        "vehicle_dealer": "Vehicle Dealer · Marchand automobile",
        "partner": "Partner · Partenaire",
        "storage_facility": "Storage Facility · Établissement de stockage",
    }.get(account_type, account_type)
    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:560px;margin:0 auto;color:#1e293b;">
      <div style="background:linear-gradient(135deg,#7c3aed,#2563eb);padding:24px 28px;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;margin:0;font-size:22px;">🎭 Your BidVex Demo is Ready</h1>
        <p style="color:#c4b5fd;margin:6px 0 0;font-size:13px;">Votre démonstration est prête</p>
      </div>
      <div style="padding:24px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;font-size:14px;line-height:1.7;">
        <p>Hi {company_name},</p>
        <p>Your demo account ({type_label}) is live. Use the credentials below to log in at <a href="https://bidvex.com">bidvex.com</a>:</p>
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px;margin:14px 0;font-family:'SF Mono',Menlo,Consolas,monospace;font-size:13px;">
          <div><strong>Email:</strong> {login_email}</div>
          <div><strong>Temporary password:</strong> {temp_password}</div>
          <div><strong>Demo expires:</strong> {expires_at.strftime('%Y-%m-%d %H:%M UTC')}</div>
        </div>
        <p>You can explore every part of the platform — dashboard, analytics, listings, settings. <strong>Note: this is a demo account — no real transactions will be processed.</strong></p>
        <p style="margin:20px 0;text-align:center;">
          <a href="https://bidvex.com" style="display:inline-block;background:#2563eb;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;">Start Exploring</a>
        </p>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:18px 0;" />
        <p style="color:#475569;font-size:13px;">
          <strong>Bonjour,</strong><br/>
          Votre compte de démonstration BidVex est prêt. Connectez-vous à bidvex.com avec les identifiants ci-dessus.
          Toutes les fonctionnalités sont disponibles à des fins de démonstration — aucune transaction réelle ne sera traitée.
          Le compte expire le {expires_at.strftime('%Y-%m-%d')}.
        </p>
      </div>
    </div>
    """


# ─── Listing + admin queries ──────────────────────────────────────────────
async def list_demo_accounts(db) -> list[dict]:
    rows = []
    async for u in db.users.find(
        {"is_demo_account": True},
        {"_id": 0, "id": 1, "email": 1, "demo_company_name": 1, "demo_account_type": 1,
         "demo_province": 1, "demo_created_at": 1, "demo_expires_at": 1,
         "demo_status": 1, "demo_notes": 1},
    ):
        rows.append(_serialize(u))
    rows.sort(key=lambda r: r.get("demo_created_at") or "", reverse=True)
    return rows


def _serialize(u: dict) -> dict:
    expires = u.get("demo_expires_at")
    now = datetime.now(timezone.utc)
    if isinstance(expires, datetime):
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            status = "expired"
        elif (expires - now).days < 3:
            status = "expiring_soon"
        else:
            status = u.get("demo_status") or "active"
    else:
        status = "active"
    return {
        "id": u["id"],
        "email": u.get("email"),
        "company_name": u.get("demo_company_name"),
        "account_type": u.get("demo_account_type"),
        "province": u.get("demo_province"),
        "created_at": u.get("demo_created_at"),
        "expires_at": expires,
        "status": status,
        "notes": u.get("demo_notes", ""),
    }


# ─── Actions: extend / convert / delete ───────────────────────────────────
async def extend_demo_account(db, user_id: str, *, additional_days: int = 14) -> dict:
    if additional_days <= 0 or additional_days > 365:
        raise ValueError("additional_days must be 1..365")
    u = await db.users.find_one({"id": user_id, "is_demo_account": True}, {"_id": 0, "demo_expires_at": 1})
    if not u:
        raise ValueError("not_a_demo_account")
    current = u.get("demo_expires_at") or datetime.now(timezone.utc)
    if isinstance(current, datetime) and current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if current < datetime.now(timezone.utc):
        current = datetime.now(timezone.utc)
    new_expiry = current + timedelta(days=additional_days)
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"demo_expires_at": new_expiry, "demo_status": "active"}},
    )
    return {"id": user_id, "new_expires_at": new_expiry.isoformat()}


async def convert_demo_to_real(db, user_id: str) -> dict:
    """Strip the demo flag so the user has to go through normal verification."""
    u = await db.users.find_one({"id": user_id, "is_demo_account": True}, {"_id": 0, "email": 1, "demo_account_type": 1})
    if not u:
        raise ValueError("not_a_demo_account")

    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "is_demo_account": False,
            "is_vehicle_dealer": False,
            "is_partner": False,
            "is_storage_facility": False,
            "dealer_license_verified": False,
            "partner_verification_status": "unverified",
            "demo_status": "converted",
            "demo_converted_at": datetime.now(timezone.utc),
        }},
    )
    # Notify
    try:
        from services.emails._email_core import send_email
        await send_email(
            to_email=u.get("email"),
            subject="Welcome to BidVex — Complete Your Verification · Complétez votre vérification",
            html_content=f"""
            <div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#1e293b;padding:20px;">
              <p>Hi {u.get('email')},</p>
              <p>Your BidVex demo has been converted to a regular account. To unlock real listings and payouts,
              please complete the verification flow from your dashboard.</p>
              <p>Votre démonstration BidVex a été convertie. Veuillez compléter le processus de vérification depuis votre tableau de bord.</p>
            </div>
            """,
        )
    except Exception as exc:
        logger.warning(f"[iter210] demo→real conversion email failed: {exc}")
    return {"id": user_id, "status": "converted"}


async def delete_demo_account(db, user_id: str) -> dict:
    u = await db.users.find_one({"id": user_id, "is_demo_account": True}, {"_id": 0, "id": 1})
    if not u:
        raise ValueError("not_a_demo_account")
    await db.users.delete_one({"id": user_id})
    # Delete demo listings only (those tagged is_demo=True)
    await db.listings.delete_many({"created_by": user_id, "is_demo": True})
    await db.vehicles.delete_many({"created_by": user_id, "is_demo": True})
    return {"id": user_id, "deleted": True}


# ─── Daily expiry scheduler ───────────────────────────────────────────────
async def check_demo_account_expiry(db) -> dict:
    """Find demo accounts whose `demo_expires_at` has passed and flip status to expired."""
    now = datetime.now(timezone.utc)
    expired_uids: list[str] = []
    async for u in db.users.find(
        {"is_demo_account": True, "demo_expires_at": {"$lt": now}, "demo_status": {"$ne": "expired"}},
        {"_id": 0, "id": 1, "email": 1, "demo_account_type": 1},
    ):
        expired_uids.append(u["id"])
        await db.users.update_one(
            {"id": u["id"]},
            {"$set": {"demo_status": "expired", "demo_expired_at": now}},
        )
        # Hide their demo listings
        await db.listings.update_many(
            {"created_by": u["id"], "is_demo": True}, {"$set": {"status": "demo_expired"}},
        )
        await db.vehicles.update_many(
            {"created_by": u["id"], "is_demo": True}, {"$set": {"status": "demo_expired"}},
        )
        # Send expiry email
        try:
            from services.emails._email_core import send_email
            await send_email(
                to_email=u.get("email"),
                subject="Your BidVex demo has ended · Votre démonstration est terminée",
                html_content="""
                <div style="font-family:sans-serif;max-width:560px;margin:0 auto;color:#1e293b;padding:20px;">
                  <p>Hi,</p>
                  <p>Your BidVex demo has ended. Ready to go live? Apply for full verification to activate your account.</p>
                  <p style="margin:14px 0;text-align:center;">
                    <a href="https://bidvex.com" style="display:inline-block;background:#2563eb;color:#fff;padding:10px 22px;border-radius:8px;text-decoration:none;">Apply for verification</a>
                  </p>
                  <hr/>
                  <p>Votre démonstration BidVex est terminée. Prêt à vous lancer ? Postulez pour la vérification complète.</p>
                </div>
                """,
            )
        except Exception as exc:
            logger.warning(f"[iter210] demo expiry email failed: {exc}")
    return {"expired_count": len(expired_uids), "checked_at": now.isoformat(), "expired_ids": expired_uids}
