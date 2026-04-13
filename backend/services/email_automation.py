"""
BidVex — Email Lifecycle Automation
Event-driven sequences with time delays using APScheduler.
Sequences: Onboarding, Re-engagement, Subscription Expiry.
"""

import os
import logging
import stripe
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

stripe.api_key = os.environ.get("STRIPE_API_KEY", "")


def _first_name(user: dict) -> str:
    name = user.get("name", "")
    return name.split()[0] if name else ""


# ═══════════════════════════════════════════════════════════════
# SEQUENCE 1 — New User Onboarding
# Trigger: signup confirmed
# Day 0: Welcome | Day 3: First bid nudge | Day 7: Guide | Day 14: Sub pitch + coupon
# ═══════════════════════════════════════════════════════════════

async def process_onboarding_sequence(db: AsyncIOMotorDatabase):
    """Run daily. Checks all users and sends the appropriate onboarding email."""
    from services.email_service import send_template_email, resolve_template

    now = datetime.now(timezone.utc)
    users = await db.users.find(
        {"email_verified": {"$ne": False}, "role": {"$ne": "admin"}},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "preferred_language": 1,
         "language_preference": 1, "created_at": 1}
    ).to_list(5000)

    sent_count = 0
    for user in users:
        created = user.get("created_at")
        if not created:
            continue
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except Exception:
                continue

        days_since_signup = (now - created).days
        lang = user.get("preferred_language", user.get("language_preference", "en"))
        uid = user.get("id", "")

        # Check which emails already sent
        sent_log = await db.lifecycle_email_log.find_one({"user_id": uid})
        sent_types = set((sent_log or {}).get("sent", []))

        email_to_send = None
        template_name = None
        dynamic_data = {"first_name": _first_name(user), "current_year": now.year}

        if days_since_signup >= 14 and "onboarding_day14" not in sent_types:
            template_name = "subscription_pitch"
            email_to_send = "onboarding_day14"
            # Generate Stripe coupon
            try:
                coupon = stripe.Coupon.create(
                    percent_off=20,
                    duration="once",
                    max_redemptions=1,
                    redeem_by=int((now + timedelta(hours=48)).timestamp()),
                    metadata={"user_id": uid, "type": "onboarding_day14"},
                )
                dynamic_data["coupon_code"] = coupon.id
                await db.users.update_one({"id": uid}, {"$set": {
                    "onboarding_coupon_code": coupon.id,
                    "onboarding_coupon_expires_at": (now + timedelta(hours=48)).isoformat(),
                }})
            except Exception as e:
                logger.error(f"[LIFECYCLE] Stripe coupon error for {uid}: {e}")
                dynamic_data["coupon_code"] = "BIENVENUE20"

        elif days_since_signup >= 7 and "onboarding_day7" not in sent_types:
            template_name = "onboarding_week1"
            email_to_send = "onboarding_day7"

        elif days_since_signup >= 3 and "onboarding_day3" not in sent_types:
            template_name = "onboarding_day3"
            email_to_send = "onboarding_day3"

        if template_name and email_to_send:
            tid = resolve_template(template_name, lang)
            success = await send_template_email(
                to_email=user["email"],
                to_name=user.get("name", ""),
                template_id=tid,
                dynamic_data=dynamic_data,
            )
            if success:
                await db.lifecycle_email_log.update_one(
                    {"user_id": uid},
                    {"$addToSet": {"sent": email_to_send}, "$set": {"updated_at": now.isoformat()}},
                    upsert=True,
                )
                sent_count += 1
                logger.info(f"[LIFECYCLE] Sent {email_to_send} to {user['email']}")

    logger.info(f"[LIFECYCLE] Onboarding sequence complete: {sent_count} emails sent")
    return sent_count


# ═══════════════════════════════════════════════════════════════
# SEQUENCE 2 — Re-engagement
# Trigger: 30 days since last login | Day 45: final with coupon
# ═══════════════════════════════════════════════════════════════

async def process_reengagement_sequence(db: AsyncIOMotorDatabase):
    """Run daily. Targets users who haven't logged in for 30+ days."""
    from services.email_service import send_template_email, resolve_template

    now = datetime.now(timezone.utc)
    cutoff_30 = (now - timedelta(days=30)).isoformat()
    cutoff_45 = (now - timedelta(days=45)).isoformat()

    inactive_users = await db.users.find(
        {"last_login_at": {"$lt": cutoff_30, "$exists": True}, "role": {"$ne": "admin"}},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "preferred_language": 1,
         "language_preference": 1, "last_login_at": 1}
    ).to_list(5000)

    sent_count = 0
    for user in inactive_users:
        uid = user.get("id", "")
        last_login = user.get("last_login_at", "")
        lang = user.get("preferred_language", user.get("language_preference", "en"))

        sent_log = await db.lifecycle_email_log.find_one({"user_id": uid})
        sent_types = set((sent_log or {}).get("sent", []))

        template_name = None
        email_to_send = None
        dynamic_data = {"first_name": _first_name(user), "current_year": now.year}

        if last_login < cutoff_45 and "reengagement_final" not in sent_types:
            template_name = "reengagement_final"
            email_to_send = "reengagement_final"
            try:
                coupon = stripe.Coupon.create(
                    percent_off=15,
                    duration="once",
                    max_redemptions=1,
                    redeem_by=int((now + timedelta(days=7)).timestamp()),
                    metadata={"user_id": uid, "type": "reengagement_final"},
                )
                dynamic_data["coupon_code"] = coupon.id
            except Exception:
                dynamic_data["coupon_code"] = "RETOUR15"

        elif last_login < cutoff_30 and "reengagement_30" not in sent_types:
            template_name = "reengagement"
            email_to_send = "reengagement_30"

        if template_name and email_to_send:
            tid = resolve_template(template_name, lang)
            success = await send_template_email(
                to_email=user["email"],
                to_name=user.get("name", ""),
                template_id=tid,
                dynamic_data=dynamic_data,
            )
            if success:
                await db.lifecycle_email_log.update_one(
                    {"user_id": uid},
                    {"$addToSet": {"sent": email_to_send}, "$set": {"updated_at": now.isoformat()}},
                    upsert=True,
                )
                sent_count += 1

    logger.info(f"[LIFECYCLE] Re-engagement sequence complete: {sent_count} emails sent")
    return sent_count


# ═══════════════════════════════════════════════════════════════
# SEQUENCE 3 — Subscription Expiry Flow
# -14d, -7d, -1d: reminders | Day 0: expired | +3d: reactivation offer
# ═══════════════════════════════════════════════════════════════

async def process_subscription_expiry_sequence(db: AsyncIOMotorDatabase):
    """Run daily. Sends reminders for expiring subscriptions."""
    from services.email_service import send_template_email, resolve_template

    now = datetime.now(timezone.utc)
    sent_count = 0

    subs = await db.subscriptions.find(
        {"status": {"$in": ["active", "expiring", "expired"]}},
        {"_id": 0}
    ).to_list(5000)

    for sub in subs:
        uid = sub.get("user_id", "")
        expiry = sub.get("expires_at") or sub.get("current_period_end")
        if not expiry:
            continue
        if isinstance(expiry, str):
            try:
                expiry = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
            except Exception:
                continue

        days_until = (expiry - now).days
        user = await db.users.find_one({"id": uid}, {"_id": 0, "email": 1, "name": 1, "preferred_language": 1, "language_preference": 1})
        if not user:
            continue

        lang = user.get("preferred_language", user.get("language_preference", "en"))
        sent_log = await db.lifecycle_email_log.find_one({"user_id": uid})
        sent_types = set((sent_log or {}).get("sent", []))

        template_name = None
        email_to_send = None
        dynamic_data = {
            "first_name": _first_name(user),
            "plan_name": sub.get("plan_name", sub.get("tier", "Pro")),
            "expiry_date": expiry.strftime("%B %d, %Y"),
            "renewal_price": f"${sub.get('price', 0):,.2f}/yr" if sub.get("price") else "",
            "current_year": now.year,
        }

        if days_until <= -3 and "sub_reactivation" not in sent_types:
            template_name = "reactivation_offer"
            email_to_send = "sub_reactivation"
            try:
                coupon = stripe.Coupon.create(
                    percent_off=15, duration="once", max_redemptions=1,
                    redeem_by=int((now + timedelta(days=7)).timestamp()),
                    metadata={"user_id": uid, "type": "subscription_reactivation"},
                )
                dynamic_data["coupon_code"] = coupon.id
            except Exception:
                dynamic_data["coupon_code"] = "RETOUR15"

        elif days_until <= 1 and "sub_final_reminder" not in sent_types:
            template_name = "subscription_final_reminder"
            email_to_send = "sub_final_reminder"

        elif days_until <= 7 and "sub_reminder_7d" not in sent_types:
            template_name = "subscription_final_reminder"
            email_to_send = "sub_reminder_7d"

        elif days_until <= 14 and "sub_reminder_14d" not in sent_types:
            template_name = "subscription_final_reminder"
            email_to_send = "sub_reminder_14d"

        if template_name and email_to_send:
            tid = resolve_template(template_name, lang)
            success = await send_template_email(
                to_email=user["email"],
                to_name=user.get("name", ""),
                template_id=tid,
                dynamic_data=dynamic_data,
            )
            if success:
                await db.lifecycle_email_log.update_one(
                    {"user_id": uid},
                    {"$addToSet": {"sent": email_to_send}, "$set": {"updated_at": now.isoformat()}},
                    upsert=True,
                )
                sent_count += 1

    logger.info(f"[LIFECYCLE] Subscription expiry sequence complete: {sent_count} emails sent")
    return sent_count


# ═══════════════════════════════════════════════════════════════
# SCHEDULER REGISTRATION
# ═══════════════════════════════════════════════════════════════

def register_lifecycle_jobs(scheduler, db: AsyncIOMotorDatabase):
    """Register all lifecycle email jobs with APScheduler. Call from server startup."""
    import asyncio

    def _run_onboarding():
        asyncio.get_event_loop().create_task(process_onboarding_sequence(db))

    def _run_reengagement():
        asyncio.get_event_loop().create_task(process_reengagement_sequence(db))

    def _run_subscription_expiry():
        asyncio.get_event_loop().create_task(process_subscription_expiry_sequence(db))

    scheduler.add_job(_run_onboarding, "cron", hour=9, minute=0, id="lifecycle_onboarding", replace_existing=True)
    scheduler.add_job(_run_reengagement, "cron", hour=9, minute=15, id="lifecycle_reengagement", replace_existing=True)
    scheduler.add_job(_run_subscription_expiry, "cron", hour=9, minute=30, id="lifecycle_subscription", replace_existing=True)

    logger.info("[LIFECYCLE] Registered 3 lifecycle email jobs (9:00, 9:15, 9:30 AM UTC)")
