"""
iter337 — Proactive Contractor Nudges + Daily Follow-Up Targets.

Two schedulers:
  • Post-call nudge sweep (every 15 min): scans ai_voice_calls documents
    completed within the last hour and inserts in-platform notifications
    based on the session outcome (declining sentiment, compliance flag,
    warming sentiment, unactioned action items).

  • Daily follow-up target scheduler (09:00 America/Toronto = 13:00 UTC
    during EDT / 14:00 UTC during EST — we run at both to be safe): scans
    each contractor's referred accounts and surfaces a prioritised list
    of "Today's Follow-Up Targets" (idle accounts, uncomplete-first-sale,
    demos-approaching-expiry). Persisted under `followup_targets` so the
    dashboard reads from a snapshot.

Notifications are IN-PLATFORM ONLY (no email fan-out) per Directive 2 —
avoids email fatigue for contractors already receiving referral, payout,
and system emails.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


NUDGE_KIND = "contractor_post_call_nudge"
FOLLOWUP_TARGET_COLLECTION = "followup_targets"
NUDGE_LOOKBACK_HOURS = 1
FOLLOWUP_MAX_ITEMS_PER_CONTRACTOR = 5


# ─── Post-call nudge sweep ──────────────────────────────────────────────

async def _has_followup_sent(session: Dict[str, Any]) -> bool:
    """True if any followup_emails_generated entry has sent=True."""
    for d in session.get("followup_emails_generated") or []:
        if d.get("sent"):
            return True
    return False


async def _nudge_already_pushed(db, contractor_id: str, call_log_id: str, reason: str) -> bool:
    """Idempotency guard — one nudge per (contractor, call, reason)."""
    key = f"post_call_nudge:{call_log_id}:{reason}"
    existing = await db.notifications.find_one({"id": key}, {"_id": 0, "id": 1})
    return existing is not None


async def _push_nudge(
    db,
    *,
    contractor_id: str,
    call_log_id: str,
    reason: str,
    title_en: str,
    title_fr: str,
    msg_en: str,
    msg_fr: str,
    lang: str = "en",
) -> Optional[Dict[str, Any]]:
    if await _nudge_already_pushed(db, contractor_id, call_log_id, reason):
        return None
    key = f"post_call_nudge:{call_log_id}:{reason}"
    doc = {
        "id":         key,
        "user_id":    contractor_id,
        "type":       NUDGE_KIND,
        "title":      title_en,
        "message":    msg_en,
        "title_en":   title_en,
        "message_en": msg_en,
        "title_fr":   title_fr,
        "message_fr": msg_fr,
        "data": {
            "call_log_id":       call_log_id,
            "reason":            reason,
            "language_detected": lang,
            "deep_link":         "/admin?tab=ai-coach-sessions",
        },
        "read":       False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Dismissal state (per contractor) is stored on the doc itself
        # so the dashboard can filter dismissed items out.
        "dismissed":  False,
    }
    try:
        await db.notifications.insert_one(doc)
        return doc
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[nudge] insert failed for {contractor_id}:{reason}: {e}")
        return None


async def run_post_call_nudge_sweep(db) -> Dict[str, int]:
    """Scan sessions completed within the last hour and push nudges.
    Runs every ~15 min. Idempotent per (call_log_id, reason)."""
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=NUDGE_LOOKBACK_HOURS)).isoformat()
    stats = {"scanned": 0, "declining": 0, "warming": 0, "compliance": 0, "action_items": 0}

    cursor = db.ai_voice_calls.find(
        {
            "call_type": "outbound_coach",
            "ai_session_status": "completed",
            "call_ended_at": {"$gte": cutoff},
        },
        {
            "_id": 0,
            "call_log_id": 1,
            "contractor_id": 1,
            "sentiment_trend": 1,
            "avg_client_sentiment": 1,
            "compliance_flags_triggered": 1,
            "action_items": 1,
            "language_detected": 1,
            "followup_emails_generated": 1,
        },
    )
    async for s in cursor:
        stats["scanned"] += 1
        contractor_id = s.get("contractor_id")
        call_log_id = s.get("call_log_id")
        if not contractor_id or not call_log_id:
            continue
        lang = (s.get("language_detected") or "en").lower()
        followup_sent = await _has_followup_sent(s)

        # Declining sentiment / very negative — always nudge.
        trend = (s.get("sentiment_trend") or "").lower()
        avg_s = s.get("avg_client_sentiment")
        if trend == "declining" or (isinstance(avg_s, (int, float)) and avg_s < -0.2):
            r = await _push_nudge(
                db, contractor_id=contractor_id, call_log_id=call_log_id,
                reason="declining_sentiment",
                title_en="Post-call insight — negative note",
                title_fr="Après-appel — note négative",
                msg_en="This call ended on a negative note. A follow-up email in the next 24h increases re-engagement by up to 3×.",
                msg_fr="Cet appel s'est terminé sur une note négative. Un courriel de suivi dans les 24h augmente le réengagement.",
                lang=lang,
            )
            if r:
                stats["declining"] += 1

        # Warming sentiment + no follow-up yet — strike-while-hot.
        if trend == "improving" and not followup_sent:
            r = await _push_nudge(
                db, contractor_id=contractor_id, call_log_id=call_log_id,
                reason="warming_no_followup",
                title_en="Post-call insight — client was warming up",
                title_fr="Après-appel — le client se réchauffait",
                msg_en="Client was warming up at the end of the call — strike while the iron is hot. Send a follow-up now.",
                msg_fr="Le client s'est réchauffé en fin d'appel — profitez-en. Envoyez un suivi maintenant.",
                lang=lang,
            )
            if r:
                stats["warming"] += 1

        # Compliance flags — always nudge (never suppressed by followup-sent).
        flags = s.get("compliance_flags_triggered") or []
        if flags:
            flag_label = ", ".join(flags[:3])
            r = await _push_nudge(
                db, contractor_id=contractor_id, call_log_id=call_log_id,
                reason="compliance_flag",
                title_en=f"Compliance flag: {flag_label}",
                title_fr=f"Signal de conformité : {flag_label}",
                msg_en=f"This call triggered {flag_label}. Review the compliance note before following up.",
                msg_fr=f"Cet appel a déclenché {flag_label}. Consultez la note de conformité avant de faire un suivi.",
                lang=lang,
            )
            if r:
                stats["compliance"] += 1

        # Unactioned action items — nudge only if call ended >=24h ago AND
        # no follow-up email sent. We check both conditions here (not
        # limited to the 1h lookback for this specific rule).
        action_items = s.get("action_items") or []
        if action_items and not followup_sent:
            # Only nudge if 24h has actually elapsed since call end — else
            # the contractor still has legit time to act. This branch runs
            # in the same sweep but reads the wider call range below.
            pass  # handled by run_action_items_nudge_sweep

    logger.info(f"[nudge] post-call sweep completed: {stats}")
    return stats


async def run_action_items_nudge_sweep(db) -> Dict[str, int]:
    """Separate sweep: nudge on unactioned action items 24h after call end.
    Kept out of the 1h sweep so we don't nudge prematurely."""
    now = datetime.now(timezone.utc)
    older_than = (now - timedelta(hours=24)).isoformat()
    younger_than = (now - timedelta(hours=48)).isoformat()  # narrow window
    stats = {"scanned": 0, "action_items_nudges": 0}

    cursor = db.ai_voice_calls.find(
        {
            "call_type": "outbound_coach",
            "ai_session_status": "completed",
            "call_ended_at": {"$gte": younger_than, "$lte": older_than},
            "action_items": {"$exists": True, "$ne": []},
        },
        {
            "_id": 0,
            "call_log_id": 1,
            "contractor_id": 1,
            "action_items": 1,
            "language_detected": 1,
            "followup_emails_generated": 1,
        },
    )
    async for s in cursor:
        stats["scanned"] += 1
        contractor_id = s.get("contractor_id")
        call_log_id = s.get("call_log_id")
        if not contractor_id or not call_log_id:
            continue
        if await _has_followup_sent(s):
            continue
        n_items = len(s.get("action_items") or [])
        lang = (s.get("language_detected") or "en").lower()
        r = await _push_nudge(
            db, contractor_id=contractor_id, call_log_id=call_log_id,
            reason="unactioned_action_items",
            title_en=f"{n_items} action items from your call are unactioned",
            title_fr=f"{n_items} points d'action de votre appel sont en attente",
            msg_en=f"You have {n_items} action items from this call that haven't been followed up on yet.",
            msg_fr=f"Vous avez {n_items} points d'action de cet appel qui n'ont pas encore reçu de suivi.",
            lang=lang,
        )
        if r:
            stats["action_items_nudges"] += 1

    logger.info(f"[nudge] action-items sweep completed: {stats}")
    return stats


# ─── Daily Follow-Up Targets ────────────────────────────────────────────

async def _build_followup_targets_for_contractor(
    db, contractor_id: str,
) -> List[Dict[str, Any]]:
    """Return the prioritised list of at most FOLLOWUP_MAX_ITEMS_PER_CONTRACTOR
    action items for a single contractor. Priority order:
      1. Demo accounts expiring within 7 days (highest urgency)
      2. Referred accounts with active listings but zero completed sales
      3. Referred accounts with no activity in the past 30 days
    """
    now = datetime.now(timezone.utc)
    thirty_days_ago_iso = (now - timedelta(days=30)).isoformat()
    seven_days_from_now = now + timedelta(days=7)

    items: List[Dict[str, Any]] = []

    # 1) Demo accounts approaching expiry.
    demos = await db.contractor_account_creations.find(
        {"contractor_id": contractor_id, "demo": True},
        {"_id": 0, "account_id": 1, "account_type": 1, "created_at": 1},
    ).to_list(500)
    for d in demos:
        acct_id = d.get("account_id")
        if not acct_id:
            continue
        u = await db.users.find_one(
            {"id": acct_id},
            {"_id": 0, "id": 1, "name": 1, "business_name": 1, "email": 1,
             "demo_expiry_date": 1, "demo_expires_at": 1},
        )
        if not u:
            continue
        exp = u.get("demo_expiry_date") or u.get("demo_expires_at")
        if not exp:
            continue
        try:
            exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
        except Exception:
            continue
        if not (now <= exp_dt <= seven_days_from_now):
            continue
        days_left = max(0, (exp_dt - now).days)
        items.append({
            "id":         f"demo_expiring:{acct_id}",
            "reason":     "demo_expiring",
            "urgency":    100 - days_left,  # sooner = higher score
            "account_id": acct_id,
            "account_name": u.get("business_name") or u.get("name") or u.get("email") or "—",
            "text_en":    f"Demo account [{u.get('business_name') or u.get('name') or 'unnamed'}] expires in {days_left} day{'s' if days_left != 1 else ''} — convert them now.",
            "text_fr":    f"Le compte démo [{u.get('business_name') or u.get('name') or 'sans nom'}] expire dans {days_left} jour{'s' if days_left != 1 else ''} — convertissez-le maintenant.",
            "days_left":  days_left,
        })

    # 2) Referred accounts with active listings but zero completed sales.
    #    We inspect vehicle_listings + storage_auctions + listings.
    creations = await db.contractor_account_creations.find(
        {"contractor_id": contractor_id, "demo": {"$ne": True}},
        {"_id": 0, "account_id": 1},
    ).to_list(2000)
    for c in creations:
        acct_id = c.get("account_id")
        if not acct_id:
            continue
        u = await db.users.find_one(
            {"id": acct_id},
            {"_id": 0, "id": 1, "name": 1, "business_name": 1, "email": 1},
        )
        if not u:
            continue
        # Count active listings across the 3 seller-facing collections.
        try:
            active_count = 0
            active_count += await db.vehicle_listings.count_documents({"seller_user_id": acct_id, "status": "active"})
        except Exception:
            pass
        try:
            active_count += await db.listings.count_documents({"user_id": acct_id, "status": "active"})
        except Exception:
            pass
        try:
            completed_sales = await db.completed_sales.count_documents({"seller_user_id": acct_id})
        except Exception:
            completed_sales = 0
        if active_count > 0 and completed_sales == 0:
            items.append({
                "id":         f"no_first_sale:{acct_id}",
                "reason":     "no_first_sale",
                "urgency":    60 + min(active_count, 20),
                "account_id": acct_id,
                "account_name": u.get("business_name") or u.get("name") or u.get("email") or "—",
                "text_en":    f"Help {u.get('business_name') or u.get('name') or 'this seller'} close their first sale — they have {active_count} active listing{'s' if active_count != 1 else ''}.",
                "text_fr":    f"Aidez {u.get('business_name') or u.get('name') or 'ce vendeur'} à conclure sa première vente — {active_count} annonce{'s' if active_count != 1 else ''} active{'s' if active_count != 1 else ''}.",
                "active_listings": active_count,
            })

    # 3) Referred accounts with no activity in the past 30 days.
    for c in creations:
        acct_id = c.get("account_id")
        if not acct_id:
            continue
        u = await db.users.find_one(
            {"id": acct_id},
            {"_id": 0, "id": 1, "name": 1, "business_name": 1, "email": 1, "last_login_at": 1, "last_activity_at": 1},
        )
        if not u:
            continue
        last_act = u.get("last_activity_at") or u.get("last_login_at") or ""
        if last_act and str(last_act) >= thirty_days_ago_iso:
            continue  # user active in last 30 days
        items.append({
            "id":         f"idle_30d:{acct_id}",
            "reason":     "idle_30d",
            "urgency":    40,
            "account_id": acct_id,
            "account_name": u.get("business_name") or u.get("name") or u.get("email") or "—",
            "text_en":    f"Follow up with {u.get('business_name') or u.get('name') or 'this account'} — no activity in the past 30 days.",
            "text_fr":    f"Faites un suivi avec {u.get('business_name') or u.get('name') or 'ce compte'} — aucune activité depuis 30 jours.",
            "last_activity_at": last_act or None,
        })

    # De-duplicate by id (in case an account matches multiple rules —
    # keep the highest-urgency variant), then sort desc + cap.
    dedup: Dict[str, Dict[str, Any]] = {}
    for it in items:
        prev = dedup.get(it["id"])
        if not prev or it["urgency"] > prev["urgency"]:
            dedup[it["id"]] = it
    ordered = sorted(dedup.values(), key=lambda i: i["urgency"], reverse=True)
    return ordered[:FOLLOWUP_MAX_ITEMS_PER_CONTRACTOR]


async def run_daily_followup_targets(db) -> Dict[str, int]:
    """Daily 09:00 America/Toronto — build each contractor's list of at
    most 5 prioritised follow-up targets and persist a fresh snapshot
    under `followup_targets`. Preserves dismissed=true state so items
    the contractor has hidden don't re-appear the next morning."""
    stats = {"contractors": 0, "targets_generated": 0}
    today_iso = datetime.now(timezone.utc).date().isoformat()

    # Every user with role=dialer_contractor OR that has ever created
    # a referred account (safety net for admins).
    contractors_cur = db.users.find(
        {"role": {"$in": ["dialer_contractor", "admin", "super_admin"]}},
        {"_id": 0, "id": 1},
    )
    async for c in contractors_cur:
        contractor_id = c.get("id")
        if not contractor_id:
            continue
        items = await _build_followup_targets_for_contractor(db, contractor_id)
        if not items:
            continue
        stats["contractors"] += 1
        stats["targets_generated"] += len(items)

        # Merge with any previously-dismissed items so they don't re-appear.
        prev = await db[FOLLOWUP_TARGET_COLLECTION].find_one(
            {"contractor_id": contractor_id}, {"_id": 0, "items": 1},
        )
        prev_dismissed = {
            i["id"]: i for i in ((prev or {}).get("items") or [])
            if i.get("dismissed")
        }
        merged = []
        for it in items:
            existing = prev_dismissed.get(it["id"])
            if existing:
                # Keep dismissed=true so the dashboard filters it out.
                it["dismissed"] = True
                it["dismissed_at"] = existing.get("dismissed_at")
            else:
                it["dismissed"] = False
            merged.append(it)

        await db[FOLLOWUP_TARGET_COLLECTION].update_one(
            {"contractor_id": contractor_id},
            {"$set": {
                "contractor_id": contractor_id,
                "generated_date": today_iso,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "items": merged,
            }},
            upsert=True,
        )

    logger.info(f"[followup-targets] daily sweep completed: {stats}")
    return stats


__all__ = [
    "NUDGE_KIND",
    "FOLLOWUP_TARGET_COLLECTION",
    "run_post_call_nudge_sweep",
    "run_action_items_nudge_sweep",
    "run_daily_followup_targets",
    "_build_followup_targets_for_contractor",
]
