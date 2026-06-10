"""
iter205 P0 — Compliance Admin Notification Dispatcher
======================================================
Whenever the watchdog or AI scanner pauses a listing, OR the synchronous
gate blocks a listing creation, this module:

  1. Inserts a row into `admin_notifications` (visible on Admin Home /
     Compliance Alerts tab) so an admin always sees the event.
  2. Best-effort SendGrid email to every super-admin / admin so urgent
     violations are pushed beyond the in-app surface.
  3. Bumps the `compliance_health_signals` counter so the green/yellow/red
     KPI can detect false-negatives even when the watchdog reports 0 paused.

All operations are fail-OPEN — a notification dispatch failure must NEVER
prevent the listing from being paused.

Public API:
  • notify_admins_of_violation(db, *, kind, listing, signals, …) → dict
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


async def _admin_recipients(db) -> list[str]:
    """Return list of admin email addresses to notify."""
    cursor = db.users.find(
        {"role": {"$in": ["admin", "super_admin"]}, "email": {"$ne": None}},
        {"_id": 0, "email": 1},
    ).limit(20)
    return [doc["email"] async for doc in cursor if doc.get("email")]


async def _send_admin_email(*, recipients: list[str], subject: str, html: str) -> bool:
    """Best-effort SendGrid send. Returns True on success, False on any failure."""
    if not recipients:
        return False
    try:
        from services.emails._email_core import send_email
    except Exception as e:
        logger.warning("[notify] no email sender available: %s", e)
        return False
    sent_any = False
    for to in recipients:
        try:
            res = await send_email(to_email=to, subject=subject, html_content=html)
            if res:
                sent_any = True
        except Exception as e:
            logger.warning("[notify] sendgrid failure for %s: %s", to, e)
    return sent_any


async def notify_admins_of_violation(
    db,
    *,
    kind: str,                      # "blocked_at_gate" | "paused_by_ai" | "paused_by_watchdog"
    listing: dict,
    signals: list[str],
    seller_email: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    """Insert admin_notifications row + dispatch email. Always returns a summary.

    Always best-effort: any failure is logged but never re-raised."""
    now = datetime.now(timezone.utc).isoformat()
    listing_id = listing.get("id")
    title = (listing.get("title") or "")[:160]
    category = listing.get("category")
    seller_id = listing.get("seller_id")

    severity = {
        "blocked_at_gate": "info",         # gate did its job — informational
        "paused_by_ai":    "warning",      # AI caught a slip-through
        "paused_by_watchdog": "high",      # watchdog backstop fired = something went wrong upstream
    }.get(kind, "warning")

    notification = {
        "kind": "vehicle_compliance_violation",
        "subkind": kind,
        "severity": severity,
        "listing_id": listing_id,
        "collection": (extra or {}).get("collection", "listings"),
        "seller_id": seller_id,
        "seller_email": seller_email,
        "title": title,
        "category": category,
        "detection_signals": signals,
        "read": False,
        "resolved": False,
        "created_at": now,
        **(extra or {}),
    }
    try:
        await db.admin_notifications.insert_one(notification)
    except Exception as e:
        logger.error("[notify] admin_notifications insert failed: %s", e)

    # Dispatch email asynchronously — do NOT block the watchdog/scanner
    if kind != "blocked_at_gate":  # Don't email for every blocked POST — too noisy
        try:
            recipients = await _admin_recipients(db)
            subject = f"[BidVex Compliance] Vehicle listing {kind.replace('_',' ')} — {title}"
            signal_html = "".join(f"<li><code>{s}</code></li>" for s in signals[:8])
            html = f"""
                <h2>Compliance system action</h2>
                <p><strong>Kind:</strong> {kind}</p>
                <p><strong>Listing ID:</strong> {listing_id}</p>
                <p><strong>Title:</strong> {title}</p>
                <p><strong>Category:</strong> {category or "(none)"}</p>
                <p><strong>Seller:</strong> {seller_email or seller_id}</p>
                <p><strong>Detection signals:</strong></p>
                <ul>{signal_html or '<li>(none)</li>'}</ul>
                <p><strong>Severity:</strong> {severity}</p>
                <p>Triage in the admin panel: Vehicles → Compliance Alerts.</p>
                <p style="color:#64748b;font-size:12px">iter205 — automated by the BidVex Safety Watchdog. Replies are not monitored.</p>
            """
            asyncio.create_task(_send_admin_email(recipients=recipients, subject=subject, html=html))
        except Exception as e:
            logger.warning("[notify] email dispatch scheduling failed: %s", e)

    # iter206 — also notify the seller so they understand WHY their listing
    # was paused and what to do next (verify dealer licence, switch to
    # vehicle-auctions, contact support).
    if kind != "blocked_at_gate" and seller_id:
        try:
            asyncio.create_task(_dispatch_seller_pause_notification(
                db, listing=listing, signals=signals, seller_email=seller_email,
                kind=kind, collection=(extra or {}).get("collection", "listings"),
            ))
        except Exception as e:
            logger.warning("[notify] seller dispatch scheduling failed: %s", e)

    return {"created_at": now, "severity": severity, "kind": kind, "listing_id": listing_id}


# ---------------------------------------------------------------------------
# iter206 — Seller notifications (in-app + SendGrid)
# ---------------------------------------------------------------------------
async def _dispatch_seller_pause_notification(
    db,
    *,
    listing: dict,
    signals: list[str],
    seller_email: Optional[str],
    kind: str,
    collection: str,
) -> None:
    """Insert a seller_notifications row + send a bilingual SendGrid email
    explaining why the listing was paused and what to do next."""
    listing_id = listing.get("id")
    seller_id = listing.get("seller_id")
    title = (listing.get("title") or "")[:160]

    # Resolve seller email if not passed
    if not seller_email and seller_id:
        seller = await db.users.find_one(
            {"id": seller_id}, {"_id": 0, "email": 1, "name": 1, "preferred_language": 1}
        ) or {}
        seller_email = seller.get("email")
        seller_name = seller.get("name") or "Seller"
        lang = (seller.get("preferred_language") or "en").lower()
    else:
        seller_name = "Seller"
        lang = "en"

    # In-app row (visible on the seller dashboard)
    try:
        await db.seller_notifications.insert_one({
            "kind": "vehicle_listing_paused",
            "severity": "high",
            "seller_id": seller_id,
            "seller_email": seller_email,
            "listing_id": listing_id,
            "collection": collection,
            "title": title,
            "detection_signals": signals,
            "paused_by": kind,  # paused_by_watchdog | paused_by_ai
            "read": False,
            "resolved": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error("[notify] seller_notifications insert failed: %s", e)

    if not seller_email:
        return
    # Email
    try:
        from services.emails._email_core import send_email
    except Exception:
        return
    is_fr = lang.startswith("fr")
    if is_fr:
        subject = f"[BidVex] Votre annonce a été mise en pause — {title}"
        html = f"""
            <h2>Votre annonce a été mise en pause</h2>
            <p>Bonjour {seller_name},</p>
            <p>Notre système de conformité a détecté que votre annonce
            <strong>« {title} »</strong> contient du contenu lié à un véhicule
            (voiture, camion, moto, bateau ou équipement lourd).</p>
            <p>Au Canada, les annonces de véhicules sont réservées aux
            concessionnaires titulaires d'une licence provinciale (OMVIC en ON,
            AMVIC en AB, VSA en C.-B., SAAQ au QC, FCAA en SK, etc.).</p>
            <p>Votre annonce est maintenant en
            <strong>statut « En attente d'examen »</strong>
            jusqu'à ce qu'un administrateur l'approuve ou la rejette.</p>
            <p><strong>Que pouvez-vous faire ?</strong></p>
            <ul>
                <li>Vérifier votre licence de concessionnaire :
                    <a href="https://bidvex.com/vehicle-auctions/dealer-license">Faire vérifier ma licence</a></li>
                <li>Consulter les Enchères de véhicules :
                    <a href="https://bidvex.com/vehicle-auctions">Voir BidVex Enchères de véhicules</a></li>
                <li>Si c'est une fausse alerte, répondez à ce courriel et
                    notre équipe examinera votre cas.</li>
            </ul>
            <p style="color:#64748b;font-size:12px">
                Référence interne : {listing_id} · Signaux détectés : {', '.join(signals[:5])}
            </p>
        """
    else:
        subject = f"[BidVex] Your listing has been paused — {title}"
        html = f"""
            <h2>Your listing has been paused</h2>
            <p>Hi {seller_name},</p>
            <p>Our compliance system detected that your listing
            <strong>"{title}"</strong> contains vehicle-related content
            (car, truck, motorcycle, boat, or heavy equipment).</p>
            <p>In Canada, vehicle listings are restricted to dealers holding
            a verified provincial dealer licence (OMVIC in ON, AMVIC in AB,
            VSA in BC, SAAQ in QC, FCAA in SK, etc.).</p>
            <p>Your listing is now in
            <strong>"Pending review"</strong>
            status until an admin approves or rejects it.</p>
            <p><strong>What can you do?</strong></p>
            <ul>
                <li>Verify your dealer licence:
                    <a href="https://bidvex.com/vehicle-auctions/dealer-license">Verify my licence</a></li>
                <li>Browse Vehicle Auctions:
                    <a href="https://bidvex.com/vehicle-auctions">Visit BidVex Vehicle Auctions</a></li>
                <li>If this is a false flag, reply to this email and our team
                    will review your case.</li>
            </ul>
            <p style="color:#64748b;font-size:12px">
                Internal ref: {listing_id} · Detected signals: {', '.join(signals[:5])}
            </p>
        """
    try:
        await send_email(to_email=seller_email, subject=subject, html_content=html)
    except Exception as e:
        logger.warning("[notify] seller email send failed: %s", e)


async def notify_seller_of_resolution(
    db,
    *,
    listing: dict,
    decision: str,                 # "approved" | "rejected"
    admin_email: Optional[str],
    note: Optional[str],
    collection: str,
) -> None:
    """When an admin approves/rejects a paused listing, send a follow-up
    SendGrid email to the seller and write a seller_notifications row."""
    listing_id = listing.get("id")
    seller_id = listing.get("seller_id")
    title = (listing.get("title") or "")[:160]
    seller = await db.users.find_one(
        {"id": seller_id}, {"_id": 0, "email": 1, "name": 1, "preferred_language": 1}
    ) or {}
    seller_email = seller.get("email")
    seller_name = seller.get("name") or "Seller"
    lang = (seller.get("preferred_language") or "en").lower()
    is_fr = lang.startswith("fr")

    try:
        await db.seller_notifications.insert_one({
            "kind": f"vehicle_listing_{decision}",
            "severity": "info" if decision == "approved" else "warning",
            "seller_id": seller_id,
            "listing_id": listing_id,
            "collection": collection,
            "title": title,
            "decision": decision,
            "admin_note": note,
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.error("[notify] seller_notifications resolution insert failed: %s", e)

    if not seller_email:
        return
    try:
        from services.emails._email_core import send_email
    except Exception:
        return
    if decision == "approved":
        subject = ("[BidVex] Votre annonce a été approuvée" if is_fr
                   else "[BidVex] Your listing has been approved")
        body_top = ("Bonne nouvelle ! Un administrateur a examiné votre annonce et l'a approuvée. Elle est de nouveau en ligne."
                    if is_fr
                    else "Good news — an admin reviewed your listing and approved it. It is back online.")
    else:
        subject = ("[BidVex] Votre annonce a été rejetée" if is_fr
                   else "[BidVex] Your listing has been rejected")
        body_top = ("Après examen, votre annonce a été rejetée car elle ne respecte pas les exigences provinciales pour les annonces de véhicules. Une licence de concessionnaire vérifiée est requise."
                    if is_fr
                    else "After review, your listing was rejected because it does not meet provincial requirements for vehicle listings. A verified dealer licence is required.")

    note_block = ""
    if note:
        note_label = "Note de l'administrateur" if is_fr else "Admin note"
        note_block = f"<p><strong>{note_label}:</strong> {note}</p>"

    html = f"""
        <h2>{subject.split('] ',1)[1]}</h2>
        <p>{('Bonjour' if is_fr else 'Hi')} {seller_name},</p>
        <p>{body_top}</p>
        <p><strong>{('Annonce' if is_fr else 'Listing')}:</strong> {title}</p>
        {note_block}
        <p style="color:#64748b;font-size:12px">
            {('Réf' if is_fr else 'Ref')}: {listing_id}
        </p>
    """
    try:
        await send_email(to_email=seller_email, subject=subject, html_content=html)
    except Exception as e:
        logger.warning("[notify] seller resolution email failed: %s", e)
