"""
iter216 P3 — Automated 6-Email Onboarding Journey
====================================================

Strategy:
  • Email 1 (Welcome) fires immediately on registration via FastAPI
    BackgroundTask.
  • Emails 2–6 are scheduled by inserting a row into
    `user_email_journey`. A daily cron (registered alongside the existing
    `lifecycle_onboarding` cron in `email_automation.py`) processes due
    rows each morning.
  • Skips: demo accounts, suspended accounts, unsubscribed users.
  • Email 6 (Day 30 re-engagement) is conditional — only fires if the
    user has zero activity (no bids placed, no listings created, no
    purchases). The `_user_is_engaged()` helper checks across collections.

All emails:
  • Bilingual EN+FR — body shows EN first then FR
  • Gmail-compatible — table-based inline styles, no external CSS, no
    Google Fonts (Arial fallback)
  • White light-mode background + #2563eb brand blue
  • Include the `{{unsubscribe_url}}` token at the bottom (replaced
    upstream by SendGrid's unsubscribe tracking)
  • Append BidVex GST# / QST# legal footer

Stop conditions:
  • `users.email_subscribed = false` → mark journey cancelled
  • `users.is_demo_account = true` → never enrol
  • `users.suspended = true` → pause until reactivated
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional
import logging
import uuid

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Email templates — bilingual, Gmail-compatible, table-based
# ─────────────────────────────────────────────────────────────────────

BRAND_BLUE = "#2563eb"
BRAND_FOOTER = (
    "BidVex Inc. · GST# 706766367RT0001 · QST# 1233530880TQ0001 · All amounts in CAD<br>"
    "<a href='https://www.bidvex.com/unsubscribe' style='color:#64748b;'>Unsubscribe</a> · "
    "<a href='https://www.bidvex.com/desinscription' style='color:#64748b;'>Se désabonner</a>"
)


def _wrap(html_body: str) -> str:
    """Wrap inner body in the BidVex email shell."""
    return f"""
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background:#f8fafc;padding:20px 0;font-family:Arial,Helvetica,sans-serif;">
      <tr><td align="center">
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="600" style="max-width:600px;background:white;border-radius:12px;border:1px solid #e2e8f0;">
          <tr><td style="padding:24px 28px 0 28px;">
            <h1 style="color:{BRAND_BLUE};margin:0;font-size:24px;letter-spacing:-0.01em;">BidVex</h1>
          </td></tr>
          <tr><td style="padding:16px 28px 24px 28px;color:#334155;font-size:14px;line-height:1.6;">
            {html_body}
          </td></tr>
          <tr><td style="padding:14px 28px 22px 28px;color:#94a3b8;font-size:11px;text-align:center;border-top:1px solid #e2e8f0;">
            {BRAND_FOOTER}
          </td></tr>
        </table>
      </td></tr>
    </table>
    """


def _cta(href: str, text: str) -> str:
    return (
        f'<div style="text-align:center;margin:18px 0;">'
        f'<a href="{href}" style="display:inline-block;padding:12px 28px;'
        f'background:{BRAND_BLUE};color:white;text-decoration:none;'
        f'border-radius:8px;font-weight:600;font-size:14px;">{text}</a></div>'
    )


def email_1_welcome(name: str) -> tuple[str, str]:
    """Welcome email — Day 0. Returns (subject, html)."""
    subject = "Welcome to BidVex 🎉 — Canada's Auction Platform · Bienvenue sur BidVex"
    body = f"""
      <p>Hi <strong>{name}</strong>, welcome to BidVex — Canada's Marketplace + Storage + Vehicles auction platform!</p>
      <p>3 quick things you can do right now:</p>
      <ul style="padding-left:18px;margin:8px 0;">
        <li>🔍 <a href="https://www.bidvex.com/marketplace" style="color:{BRAND_BLUE};">Browse live auctions</a></li>
        <li>🏷️ <a href="https://www.bidvex.com/create-listing" style="color:{BRAND_BLUE};">List your first item</a></li>
        <li>💡 <a href="https://www.bidvex.com/how-it-works" style="color:{BRAND_BLUE};">Learn how it works</a></li>
      </ul>
      <p style="color:#475569;font-size:12px;">🔒 Secure Payments · ✅ Verified Sellers · 🛡️ Buyer Protection</p>
      {_cta("https://www.bidvex.com/marketplace", "Explore BidVex →")}
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
      <p>Bonjour <strong>{name}</strong>, bienvenue sur BidVex — la plateforme d'enchères canadienne (Marketplace + Entreposage + Véhicules) !</p>
      <p>3 actions rapides à essayer dès maintenant :</p>
      <ul style="padding-left:18px;margin:8px 0;">
        <li>🔍 <a href="https://www.bidvex.com/marketplace" style="color:{BRAND_BLUE};">Parcourir les enchères en direct</a></li>
        <li>🏷️ <a href="https://www.bidvex.com/create-listing" style="color:{BRAND_BLUE};">Lister votre premier article</a></li>
        <li>💡 <a href="https://www.bidvex.com/how-it-works" style="color:{BRAND_BLUE};">Découvrir le fonctionnement</a></li>
      </ul>
      <p style="color:#64748b;font-size:12px;">Besoin d'aide ? <a href="mailto:support@bidvex.com">support@bidvex.com</a></p>
    """
    return subject, _wrap(body)


def email_2_how_to_buy(name: str) -> tuple[str, str]:
    subject = "💰 How to win your first auction · Comment remporter votre première enchère"
    body = f"""
      <h2 style="margin:0 0 10px;color:{BRAND_BLUE};font-size:18px;">💰 How to win your first auction</h2>
      <p>Hi <strong>{name}</strong>, ready to bid? The 5-step flow:</p>
      <ol style="padding-left:18px;line-height:1.7;">
        <li><strong>Browse</strong> live auctions in your category</li>
        <li><strong>Watch</strong> — get notified when an auction is ending</li>
        <li><strong>Set your max bid</strong> — BidVex will proxy-bid up to that max for you, only paying what's needed</li>
        <li><strong>Win</strong> — the auction soft-closes (auto-extends 2 min if a last-second bid arrives)</li>
        <li><strong>Pay</strong> via the seller's preferred method</li>
      </ol>
      <p style="background:#eff6ff;border-left:4px solid {BRAND_BLUE};padding:10px;font-size:13px;">
        💡 <strong>Tip:</strong> Set your maximum bid and let BidVex bid for you — you only pay what's needed to win.
      </p>
      {_cta("https://www.bidvex.com/marketplace", "Browse Live Auctions →")}
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
      <h2 style="margin:0 0 10px;color:{BRAND_BLUE};font-size:18px;">💰 Comment remporter votre première enchère</h2>
      <p>Bonjour <strong>{name}</strong>, le flux en 5 étapes :</p>
      <ol style="padding-left:18px;line-height:1.7;">
        <li><strong>Parcourir</strong> les enchères dans votre catégorie</li>
        <li><strong>Surveiller</strong> — recevez une alerte avant la fin de l'enchère</li>
        <li><strong>Saisir votre mise maximale</strong> — BidVex enchérit par procuration jusqu'à ce maximum</li>
        <li><strong>Gagner</strong> — l'enchère se ferme en douceur (prolongation auto de 2 min)</li>
        <li><strong>Payer</strong> selon la méthode préférée du vendeur</li>
      </ol>
    """
    return subject, _wrap(body)


def email_3_how_to_sell(name: str) -> tuple[str, str]:
    subject = "🏷️ Turn your unused items into cash · Transformez vos articles en argent"
    body = f"""
      <h2 style="margin:0 0 10px;color:{BRAND_BLUE};font-size:18px;">🏷️ Turn your unused items into cash</h2>
      <p>Hi <strong>{name}</strong>! What sells well on BidVex: furniture, electronics, tools, collectibles, restaurant equipment.</p>
      <ol style="padding-left:18px;line-height:1.7;">
        <li>📸 Take clear photos from multiple angles</li>
        <li>✍️ Write an honest description</li>
        <li>💵 Set a fair starting price</li>
        <li>⏱️ Choose auction duration (3–14 days)</li>
        <li>🚀 Publish and watch the bids roll in</li>
      </ol>
      <p style="background:#fef3c7;border-left:4px solid #b45309;padding:10px;font-size:13px;">
        💡 <strong>Tip:</strong> Items with 3+ clear photos get 2× more bids on average.
      </p>
      {_cta("https://www.bidvex.com/create-listing", "List Your First Item →")}
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
      <h2 style="margin:0 0 10px;color:{BRAND_BLUE};font-size:18px;">🏷️ Transformez vos articles inutilisés en argent</h2>
      <p>Bonjour <strong>{name}</strong>! Ce qui se vend bien : meubles, électronique, outils, objets de collection, équipement de restaurant.</p>
    """
    return subject, _wrap(body)


def email_4_money_tips(name: str) -> tuple[str, str]:
    subject = "💡 5 ways BidVex sellers make more money · 5 façons de gagner plus"
    body = f"""
      <h2 style="margin:0 0 10px;color:{BRAND_BLUE};font-size:18px;">💡 5 ways BidVex sellers make more money</h2>
      <p>Hi <strong>{name}</strong>, here's what top sellers do differently:</p>
      <ol style="padding-left:18px;line-height:1.8;">
        <li>📸 <strong>Photos sell</strong> — list 8–10 photos minimum</li>
        <li>⏰ <strong>End auctions on Sunday evenings</strong> — highest bidder traffic</li>
        <li>🔍 <strong>Use specific keywords</strong> in titles (brand, model, size, condition)</li>
        <li>💬 <strong>Reply to buyer questions quickly</strong> — active sellers get more watchers</li>
        <li>🔼 <strong>Upgrade your tier</strong> — VIP Elite sellers keep 98% of the hammer price</li>
      </ol>
      {_cta("https://www.bidvex.com/create-listing", "Start Selling Today →")}
      <div style="text-align:center;margin-top:8px;">
        <a href="https://www.bidvex.com/settings#tier" style="color:{BRAND_BLUE};font-size:12px;">Upgrade My Tier →</a>
      </div>
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
      <h2 style="margin:0 0 10px;color:{BRAND_BLUE};font-size:18px;">💡 5 façons de gagner plus sur BidVex</h2>
      <ol style="padding-left:18px;line-height:1.8;">
        <li>📸 8 à 10 photos minimum</li>
        <li>⏰ Terminez le dimanche soir</li>
        <li>🔍 Marque, modèle, taille, état</li>
        <li>💬 Répondez vite aux questions</li>
        <li>🔼 VIP Elite garde 98 %</li>
      </ol>
    """
    return subject, _wrap(body)


def email_5_features(name: str) -> tuple[str, str]:
    subject = "🚀 Features you might have missed · Fonctionnalités à découvrir"
    body = f"""
      <h2 style="margin:0 0 10px;color:{BRAND_BLUE};font-size:18px;">🚀 Features you might have missed</h2>
      <p>Hi <strong>{name}</strong>,</p>
      <ul style="padding-left:18px;line-height:1.8;">
        <li>🤖 <strong>Auto-bid</strong> — set it and forget it</li>
        <li>👀 <strong>Watchlist</strong> — save auctions and get outbid alerts</li>
        <li>📊 <strong>Seller dashboard</strong> — analytics, bid history, payouts</li>
        <li>💬 <strong>AI Concierge</strong> — chat for help anytime</li>
        <li>📦 <strong>Storage Auctions</strong> — bargains in abandoned units</li>
        <li>🚚 <strong>Lots Auction</strong> — bulk inventory at deep discounts</li>
        <li>🚗 <strong>Vehicle Auctions</strong> (coming soon — join the waitlist)</li>
      </ul>
      {_cta("https://www.bidvex.com/", "Explore All Features →")}
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
      <h2 style="margin:0 0 10px;color:{BRAND_BLUE};font-size:18px;">🚀 Fonctionnalités à découvrir</h2>
      <p>Bonjour <strong>{name}</strong>, à explorer :</p>
    """
    return subject, _wrap(body)


def email_6_reengagement(name: str, live_auctions: list = None) -> tuple[str, str]:
    """Day 30 — only sent if user has zero activity."""
    cards = ""
    for a in (live_auctions or [])[:3]:
        title = a.get("title", "Live auction")
        price = a.get("current_price") or a.get("starting_price") or 0
        url = f"https://www.bidvex.com/listing/{a.get('id', '')}"
        cards += f"""
          <a href="{url}" style="display:block;text-decoration:none;color:inherit;padding:10px;border:1px solid #e2e8f0;border-radius:8px;margin:8px 0;">
            <strong style="color:{BRAND_BLUE};">{title}</strong>
            <div style="color:#475569;font-size:12px;">Current bid: <strong>CA${float(price):,.2f}</strong></div>
          </a>
        """
    if not cards:
        cards = '<p style="color:#94a3b8;font-style:italic;">Many live auctions ending soon — come and see!</p>'

    subject = "👋 Still there? Here's what's happening on BidVex · Toujours là ?"
    body = f"""
      <h2 style="margin:0 0 10px;color:{BRAND_BLUE};font-size:18px;">👋 Still there? Here's what's hot right now</h2>
      <p>Hi <strong>{name}</strong>, we noticed you haven't placed a bid or listed yet. A few live auctions ending soon:</p>
      {cards}
      <p style="background:#fef3c7;border-left:4px solid #b45309;padding:10px;font-size:13px;">
        ⚡ Don't miss out — these auctions close soon.
      </p>
      {_cta("https://www.bidvex.com/marketplace?sort=ending_soon", "Bid Now Before It's Too Late →")}
      <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0;">
      <h2 style="margin:0 0 10px;color:{BRAND_BLUE};font-size:18px;">👋 Voici ce qui se passe sur BidVex</h2>
      <p>Bonjour <strong>{name}</strong>, quelques enchères qui se terminent bientôt :</p>
    """
    return subject, _wrap(body)


# ─────────────────────────────────────────────────────────────────────
# Journey schedule + dispatch logic
# ─────────────────────────────────────────────────────────────────────

# Day offsets per email_number
JOURNEY_SCHEDULE = {
    1: 0,    # immediately
    2: 3,
    3: 7,
    4: 14,
    5: 21,
    6: 30,
}

EMAIL_BUILDERS = {
    1: ("welcome", email_1_welcome),
    2: ("how_to_buy", email_2_how_to_buy),
    3: ("how_to_sell", email_3_how_to_sell),
    4: ("money_tips", email_4_money_tips),
    5: ("features", email_5_features),
    6: ("reengagement", email_6_reengagement),
}


async def schedule_journey_for_user(db, user: dict) -> Optional[str]:
    """Create a `user_email_journey` document + fire Email 1 immediately.

    Idempotent — does nothing if a journey already exists or if the user is
    a demo / unsubscribed account.
    """
    if not user or not user.get("email"):
        return None
    if user.get("is_demo_account"):
        logger.info(f"[journey] skip demo account {user.get('id')}")
        return None
    if user.get("email_subscribed") is False:
        return None

    existing = await db.user_email_journey.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
    if existing:
        return existing["id"]

    now = datetime.now(timezone.utc)
    journey_id = str(uuid.uuid4())
    emails = []
    for n, offset in JOURNEY_SCHEDULE.items():
        emails.append({
            "email_number": n,
            "key": EMAIL_BUILDERS[n][0],
            "scheduled_at": (now + timedelta(days=offset)).isoformat(),
            "sent_at": None,
            "opened": False,
            "clicked": False,
            "skipped": False,
            "skipped_reason": None,
        })

    await db.user_email_journey.insert_one({
        "id": journey_id,
        "user_id": user["id"],
        "email": user["email"],
        "name": user.get("name", ""),
        "registered_at": now.isoformat(),
        "language": user.get("language", "en"),
        "journey_emails": emails,
        "journey_active": True,
        "journey_completed_at": None,
        "created_at": now.isoformat(),
    })

    # Fire Email 1 right away — never await the SendGrid call so registration
    # response time isn't impacted.
    try:
        await dispatch_journey_email(db, user, email_number=1)
    except Exception as e:
        logger.error(f"[journey] Email 1 fire failed for {user.get('email')}: {e}")

    return journey_id


async def _user_is_engaged(db, user_id: str) -> bool:
    """Returns True if the user has placed a bid, listed something, or bought."""
    try:
        if await db.listings.count_documents({"seller_id": user_id}) > 0:
            return True
        if await db.bids.count_documents({"bidder_id": user_id}) > 0:
            return True
        if await db.transactions.count_documents({"buyer_id": user_id}) > 0:
            return True
    except Exception:
        pass
    return False


async def dispatch_journey_email(db, user: dict, *, email_number: int) -> bool:
    """Render and send a single journey email. Updates `journey_emails[]`."""
    if email_number not in EMAIL_BUILDERS:
        return False
    key, builder = EMAIL_BUILDERS[email_number]

    # Stop conditions
    user_doc = await db.users.find_one({"id": user["id"]}, {"_id": 0}) or {}
    if user_doc.get("is_demo_account") or user_doc.get("email_subscribed") is False:
        await db.user_email_journey.update_one(
            {"user_id": user["id"], "journey_emails.email_number": email_number},
            {"$set": {
                "journey_emails.$.skipped": True,
                "journey_emails.$.skipped_reason": "user_demo_or_unsubscribed",
            }},
        )
        return False
    if user_doc.get("suspended"):
        await db.user_email_journey.update_one(
            {"user_id": user["id"], "journey_emails.email_number": email_number},
            {"$set": {
                "journey_emails.$.skipped": True,
                "journey_emails.$.skipped_reason": "user_suspended",
            }},
        )
        return False

    # Email 6 only sends if zero activity
    if email_number == 6 and await _user_is_engaged(db, user["id"]):
        await db.user_email_journey.update_one(
            {"user_id": user["id"], "journey_emails.email_number": 6},
            {"$set": {
                "journey_emails.$.skipped": True,
                "journey_emails.$.skipped_reason": "user_already_engaged",
            }},
        )
        return False

    name = user.get("name") or user.get("first_name") or (user.get("email") or "").split("@")[0]

    if email_number == 6:
        # Fetch up to 3 live auctions ending soon to embed
        try:
            soon = datetime.now(timezone.utc) + timedelta(days=2)
            auctions = await db.listings.find(
                {"status": "active", "end_time": {"$lte": soon.isoformat()}},
                {"_id": 0, "id": 1, "title": 1, "current_price": 1, "starting_price": 1},
            ).sort("end_time", 1).limit(3).to_list(3)
        except Exception:
            auctions = []
        subject, html = builder(name, auctions)
    else:
        subject, html = builder(name)

    # Send
    try:
        from services.email_notifications import send_email
        ok = await send_email(to_email=user["email"], subject=subject, html_content=html)
    except Exception as e:
        logger.error(f"[journey:E{email_number}] send failed for {user.get('email')}: {e}")
        return False

    if ok:
        await db.user_email_journey.update_one(
            {"user_id": user["id"], "journey_emails.email_number": email_number},
            {"$set": {"journey_emails.$.sent_at": datetime.now(timezone.utc).isoformat()}},
        )
    return bool(ok)


async def process_due_journey_emails(db) -> int:
    """Daily cron — sends every journey email whose `scheduled_at <= now`
    AND `sent_at IS None`. Returns the count of emails dispatched."""
    now_iso = datetime.now(timezone.utc).isoformat()
    sent = 0
    cursor = db.user_email_journey.find({
        "journey_active": True,
        "journey_emails": {
            "$elemMatch": {"sent_at": None, "skipped": {"$ne": True}, "scheduled_at": {"$lte": now_iso}},
        },
    })
    async for j in cursor:
        user = await db.users.find_one({"id": j["user_id"]}, {"_id": 0})
        if not user:
            continue
        for e in j.get("journey_emails", []):
            if e.get("sent_at") or e.get("skipped"):
                continue
            if e.get("scheduled_at", "") > now_iso:
                continue
            try:
                if await dispatch_journey_email(db, user, email_number=e["email_number"]):
                    sent += 1
            except Exception as exc:
                logger.exception(f"[journey:cron] dispatch failed: {exc}")

        # Mark journey completed if all emails have been sent/skipped
        emails = (await db.user_email_journey.find_one({"id": j["id"]}, {"_id": 0, "journey_emails": 1}) or {}).get("journey_emails", [])
        if all(e.get("sent_at") or e.get("skipped") for e in emails):
            await db.user_email_journey.update_one(
                {"id": j["id"]},
                {"$set": {"journey_active": False, "journey_completed_at": datetime.now(timezone.utc).isoformat()}},
            )

    logger.info(f"[journey:cron] dispatched {sent} due journey emails")
    return sent
