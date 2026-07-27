"""
iter401 — Automated marketing email flows (bilingual EN + FR).

Two flows, five triggers total:

Flow 1 — Buyer Interest (real-time)
    dispatch_buyer_interest_emails(db, listing_id, listing_type)
      Fires immediately after a new listing goes live. Emails every
      user who has placed ≥1 bid historically AND either follows the
      seller OR has previously bid on the same category. Rate-limited
      to 1 email per user per hour via `buyer_interest_email_log`.

Flow 2 — Seller Action (cron)
    run_seller_draft_reminders(db)                   — Trigger A (24h)
      Draft listing created ≥24h ago and never published.
    run_seller_auction_starting_reminders(db)        — Trigger B (T-2h)
      Multi-item auction with `auction_start_date` in 90–150 min.
    run_seller_winner_approval_reminders(db)         — Trigger C (T+24h)
      Auction ended ≥24h ago with winning bids not yet approved.

All three seller triggers are idempotent — every listing/auction gets
one reminder per trigger (stamped on the source doc). Only registered
sellers with ≥1 listing (any status) are targeted.

Email dispatch uses the shared `services.emails._email_core.send_email`
so global suppression + tracking headers apply automatically. All
outbound has `is_marketing=True` so users who opted out of marketing
are silently skipped.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("marketing_flows")

FRONTEND_URL = (os.environ.get("FRONTEND_URL") or os.environ.get("REACT_APP_BACKEND_URL") or "https://www.bidvex.com").rstrip("/")

# ─── Rate-limit knobs (kept tunable) ─────────────────────────────────
BUYER_INTEREST_RATE_LIMIT_HOURS = 1
SELLER_DRAFT_TRIGGER_HOURS      = 24
SELLER_STARTING_LOWER_MIN       = 90    # ≥ 90 min before start
SELLER_STARTING_UPPER_MIN       = 150   # ≤ 150 min before start (24h window/60min cron)
SELLER_WINNER_APPROVE_HOURS     = 24


# ─── Small helpers ───────────────────────────────────────────────────

def _lang_of(user: Dict[str, Any]) -> str:
    v = (user.get("preferred_language") or "en").lower()
    return "fr" if v.startswith("fr") else "en"


def _fmt_money(amount: Optional[float], currency: str = "CAD", lang: str = "en") -> str:
    if amount is None:
        return "—"
    if lang == "fr":
        return f"{amount:,.2f}".replace(",", " ").replace(".", ",") + f" $ {currency}"
    return f"${amount:,.2f} {currency}"


def _fmt_datetime(dt: Optional[datetime], lang: str = "en") -> str:
    if not dt:
        return "—"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if lang == "fr":
        months = ["janvier", "février", "mars", "avril", "mai", "juin",
                  "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
        return f"{dt.day} {months[dt.month - 1]} {dt.year} à {dt:%H:%M} UTC"
    return dt.strftime("%B %-d, %Y at %H:%M UTC")


def _base_email_shell(subject: str, body_html: str) -> str:
    """Standard BidVex email chrome wrapping the given body HTML."""
    return f"""
<!doctype html><html><body style="margin:0;padding:0;background:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#0f172a;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.06);overflow:hidden;">
        <tr><td style="padding:24px 28px;border-bottom:1px solid #e2e8f0;">
          <div style="font-size:18px;font-weight:700;color:#0055FF;">BidVex</div>
        </td></tr>
        <tr><td style="padding:24px 28px;">{body_html}</td></tr>
        <tr><td style="padding:14px 28px 22px;color:#94a3b8;font-size:12px;text-align:center;">
          © BidVex — Auction Marketplace · <a href="{FRONTEND_URL}" style="color:#94a3b8;">bidvex.com</a>
          &nbsp;·&nbsp; <a href="{FRONTEND_URL}/unsubscribe" style="color:#94a3b8;">Unsubscribe / Désabonnement</a>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>
""".strip()


async def _send(to_email: str, subject: str, html: str, category: str) -> Dict[str, Any]:
    """Wrapper around `send_email` that always sets marketing=True and a
    per-flow SendGrid category so activity feed segments cleanly."""
    try:
        from services.emails._email_core import send_email
        return await send_email(
            to_email=to_email,
            subject=subject,
            html_content=html,
            is_marketing=True,
            categories=[category],
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"[marketing_flows] send failed to={to_email} category={category}: {e}")
        return {"status": "error", "reason": str(e)}


async def _resolve_listing(db, listing_id: str, listing_type: str) -> tuple[Optional[dict], str]:
    """Return `(listing_doc, collection_name)` for the given id + type.

    listing_type ∈ {'multi_item','vehicle','storage','single'}.
    Falls back across the four collections so callers can leave the type
    blank when it isn't known statically.
    """
    tries: List[tuple[str, str]] = []
    if listing_type == "multi_item":
        tries.append(("multi_item_listings", listing_id))
    elif listing_type == "vehicle":
        tries.append(("vehicle_listings", listing_id))
    elif listing_type == "storage":
        tries.append(("storage_auctions", listing_id))
    elif listing_type == "single":
        tries.append(("listings", listing_id))
    else:
        tries = [
            ("multi_item_listings", listing_id),
            ("vehicle_listings",   listing_id),
            ("storage_auctions",   listing_id),
            ("listings",           listing_id),
        ]
    for col, lid in tries:
        doc = await db[col].find_one({"id": lid}, {"_id": 0})
        if doc:
            return doc, col
    return None, ""


def _listing_public_url(listing_doc: dict, collection: str) -> str:
    lid = listing_doc.get("id")
    if collection == "multi_item_listings":
        return f"{FRONTEND_URL}/multi-item-listing/{lid}"
    if collection == "vehicle_listings":
        return f"{FRONTEND_URL}/vehicle/{lid}"
    if collection == "storage_auctions":
        return f"{FRONTEND_URL}/storage-auction/{lid}"
    return f"{FRONTEND_URL}/listing/{lid}"


def _seller_admin_url(listing_doc: dict, collection: str, action: str = "manage") -> str:
    """Direct link to the seller's action-relevant admin page.

    action ∈ {'edit','publish','manage','approve_winners'}
    """
    lid = listing_doc.get("id")
    if collection == "multi_item_listings":
        base = f"{FRONTEND_URL}/seller/multi-item/{lid}"
        return base + ("?tab=approve" if action == "approve_winners" else "")
    if collection == "vehicle_listings":
        return f"{FRONTEND_URL}/seller/vehicles/{lid}"
    if collection == "storage_auctions":
        return f"{FRONTEND_URL}/seller/storage/{lid}"
    return f"{FRONTEND_URL}/seller/listings/{lid}"


def _listing_starting_price(listing_doc: dict, collection: str) -> Optional[float]:
    if collection == "multi_item_listings":
        lots = listing_doc.get("lots") or []
        # Prefer the lowest starting_price across lots so email advertises
        # the "starting from" number.
        prices = [float(lot.get("starting_price") or 0) for lot in lots if lot.get("starting_price")]
        return min(prices) if prices else None
    for key in ("starting_bid", "starting_price", "reserve_price", "current_price"):
        v = listing_doc.get(key)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def _listing_end_time(listing_doc: dict, collection: str) -> Optional[str]:
    for key in ("auction_end_date", "auction_end_time", "ends_at", "end_date", "end_time"):
        v = listing_doc.get(key)
        if v:
            return v
    if collection == "multi_item_listings":
        # Use max lot_end_time across lots as a proxy.
        lots = listing_doc.get("lots") or []
        ends = [lot.get("lot_end_time") for lot in lots if lot.get("lot_end_time")]
        return max(ends) if ends else None
    return None


def _listing_start_time(listing_doc: dict, collection: str) -> Optional[str]:
    for key in ("auction_start_date", "auction_start_time", "starts_at", "scheduled_start"):
        v = listing_doc.get(key)
        if v:
            return v
    return None


# ═══════════════════════════════════════════════════════════════════════
# Flow 1 — Buyer Interest (real-time)
# ═══════════════════════════════════════════════════════════════════════

async def _build_buyer_interest_email(user: dict, listing: dict, collection: str) -> Dict[str, str]:
    lang = _lang_of(user)
    title = listing.get("title") or "New auction"
    price = _listing_starting_price(listing, collection)
    end   = _listing_end_time(listing, collection)
    url   = _listing_public_url(listing, collection)
    category = listing.get("category") or "—"

    price_str = _fmt_money(price, listing.get("currency", "CAD"), lang) if price is not None else ("—" if lang == "en" else "—")
    end_str = _fmt_datetime(end, lang)

    if lang == "fr":
        subject = f"Nouvelle enchère qui pourrait vous intéresser : {title}"
        body = f"""
          <h2 style="margin:0 0 10px;color:#0f172a;">Nouvelle enchère qui pourrait vous intéresser</h2>
          <p style="color:#334155;margin:0 0 14px;">Bonjour {user.get('name') or 'là'},</p>
          <p style="color:#334155;margin:0 0 14px;">Une nouvelle enchère vient d'être publiée dans une catégorie qui vous intéresse ou par un vendeur que vous suivez.</p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;margin:8px 0 20px;">
            <tr><td style="padding:16px 18px;background:#f1f5f9;border-radius:10px;">
              <div style="font-size:16px;font-weight:700;color:#0f172a;margin-bottom:6px;">{title}</div>
              <div style="color:#475569;font-size:14px;line-height:1.6;">
                <div><strong>Catégorie :</strong> {category}</div>
                <div><strong>Prix de départ :</strong> {price_str}</div>
                <div><strong>Fin de l'enchère :</strong> {end_str}</div>
              </div>
            </td></tr>
          </table>
          <p style="text-align:left;margin:0 0 4px;">
            <a href="{url}" style="display:inline-block;padding:12px 22px;background:#0055FF;color:#ffffff;font-weight:600;border-radius:8px;text-decoration:none;">Voir l'enchère</a>
          </p>"""
    else:
        subject = f"New auction you might love: {title}"
        body = f"""
          <h2 style="margin:0 0 10px;color:#0f172a;">A new auction you may want to bid on</h2>
          <p style="color:#334155;margin:0 0 14px;">Hi {user.get('name') or 'there'},</p>
          <p style="color:#334155;margin:0 0 14px;">A new auction just went live in a category you've bid on before — or from a seller you follow.</p>
          <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;margin:8px 0 20px;">
            <tr><td style="padding:16px 18px;background:#f1f5f9;border-radius:10px;">
              <div style="font-size:16px;font-weight:700;color:#0f172a;margin-bottom:6px;">{title}</div>
              <div style="color:#475569;font-size:14px;line-height:1.6;">
                <div><strong>Category:</strong> {category}</div>
                <div><strong>Starting price:</strong> {price_str}</div>
                <div><strong>Auction ends:</strong> {end_str}</div>
              </div>
            </td></tr>
          </table>
          <p style="text-align:left;margin:0 0 4px;">
            <a href="{url}" style="display:inline-block;padding:12px 22px;background:#0055FF;color:#ffffff;font-weight:600;border-radius:8px;text-decoration:none;">View auction</a>
          </p>"""
    return {"subject": subject, "html": _base_email_shell(subject, body)}


async def _eligible_buyer_ids(db, listing: dict, collection: str) -> List[str]:
    """Compute the union of (a) followers of the seller and (b) users who
    have previously bid on the same category — restricted to users who
    have placed ≥1 bid historically.
    """
    seller_id = listing.get("seller_id")
    listing_id = listing.get("id")
    category = listing.get("category") or ""

    followers: set = set()
    if seller_id:
        async for f in db.seller_follows.find(
            {"seller_id": seller_id}, {"_id": 0, "follower_id": 1},
        ):
            if f.get("follower_id"):
                followers.add(f["follower_id"])

    # Users who have EVER placed a bid → their listing_ids
    ever_bidders: set = set()
    async for b in db.bids.find({}, {"_id": 0, "bidder_id": 1}):
        if b.get("bidder_id"):
            ever_bidders.add(b["bidder_id"])

    # Users who have bid on same category (via joins across 3 listing types).
    same_category: set = set()
    if category:
        # Grab all bids by ever_bidders — join to their listing category.
        # We iterate bids and look up the listing per unique listing_id.
        seen_listings: Dict[str, str] = {}
        async for b in db.bids.find({}, {"_id": 0, "bidder_id": 1, "listing_id": 1}):
            lid = b.get("listing_id")
            bidder = b.get("bidder_id")
            if not lid or not bidder:
                continue
            cat = seen_listings.get(lid)
            if cat is None:
                for col in ("multi_item_listings", "vehicle_listings", "storage_auctions", "listings"):
                    doc = await db[col].find_one({"id": lid}, {"_id": 0, "category": 1})
                    if doc:
                        cat = doc.get("category") or ""
                        break
                seen_listings[lid] = cat or ""
            if cat == category:
                same_category.add(bidder)

    # Union & intersection with ever_bidders (must have bid ≥1 time).
    candidates = (followers | same_category) & ever_bidders

    # Exclude the seller themselves and the listing's own existing bidders (they've clearly seen it).
    candidates.discard(seller_id)
    async for b in db.bids.find({"listing_id": listing_id}, {"_id": 0, "bidder_id": 1}):
        candidates.discard(b.get("bidder_id"))

    return list(candidates)


async def _rate_limit_ok(db, user_id: str) -> bool:
    """True iff no buyer-interest email was sent to this user in the last
    BUYER_INTEREST_RATE_LIMIT_HOURS window."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=BUYER_INTEREST_RATE_LIMIT_HOURS)
    hit = await db.buyer_interest_email_log.find_one(
        {"user_id": user_id, "sent_at": {"$gte": cutoff.isoformat()}},
        {"_id": 0, "user_id": 1},
    )
    return hit is None


async def dispatch_buyer_interest_emails(db, listing_id: str, listing_type: str = "") -> Dict[str, int]:
    """Real-time entry point called from listing-create endpoints. Runs
    the eligibility query, applies the per-user hourly rate limit,
    dispatches the bilingual email, and records the send.

    Return `{eligible, sent, rate_limited, no_email}` counters for logs.
    """
    counts = {"eligible": 0, "sent": 0, "rate_limited": 0, "no_email": 0, "skipped": 0}
    listing, collection = await _resolve_listing(db, listing_id, listing_type)
    if not listing:
        logger.warning(f"[buyer_interest] listing not found id={listing_id} type={listing_type}")
        return counts
    # Only emit for active listings — draft/inactive should not blast users.
    if (listing.get("status") or "").lower() not in ("active", "live", "published", "scheduled"):
        return counts

    candidate_ids = await _eligible_buyer_ids(db, listing, collection)
    counts["eligible"] = len(candidate_ids)
    if not candidate_ids:
        return counts

    now_iso = datetime.now(timezone.utc).isoformat()
    async for user in db.users.find(
        {"id": {"$in": candidate_ids},
         "marketing_unsubscribed": {"$ne": True}},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "preferred_language": 1},
    ):
        if not user.get("email"):
            counts["no_email"] += 1
            continue
        if not await _rate_limit_ok(db, user["id"]):
            counts["rate_limited"] += 1
            continue
        try:
            content = await _build_buyer_interest_email(user, listing, collection)
            result = await _send(user["email"], content["subject"], content["html"], category="buyer_interest")
            if (result or {}).get("status") == "skipped":
                counts["skipped"] += 1
                continue
            # Stamp rate-limit log regardless of SendGrid success — protects
            # against SendGrid transient failures triggering re-sends.
            await db.buyer_interest_email_log.insert_one({
                "user_id":    user["id"],
                "listing_id": listing_id,
                "collection": collection,
                "sent_at":    now_iso,
            })
            counts["sent"] += 1
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[buyer_interest] send failed user={user.get('id')}: {e}")

    logger.info(f"[buyer_interest] listing={listing_id} counts={counts}")
    return counts


# ═══════════════════════════════════════════════════════════════════════
# Flow 2 — Seller Action (cron)
# ═══════════════════════════════════════════════════════════════════════

async def _seller_has_any_listing(db, seller_id: str) -> bool:
    """Guardrail — only registered sellers with ≥1 listing get reminders."""
    for col in ("multi_item_listings", "vehicle_listings", "storage_auctions", "listings"):
        c = await db[col].count_documents({"seller_id": seller_id})
        if c > 0:
            return True
    return False


async def _get_seller_user(db, seller_id: str) -> Optional[dict]:
    return await db.users.find_one(
        {"id": seller_id, "marketing_unsubscribed": {"$ne": True}},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "preferred_language": 1},
    )


def _seller_draft_email(seller: dict, listing: dict, collection: str) -> Dict[str, str]:
    lang = _lang_of(seller)
    title = listing.get("title") or "Your draft"
    edit_url = _seller_admin_url(listing, collection, "edit")
    if lang == "fr":
        subject = f"Terminez et publiez votre annonce : {title}"
        body = f"""
          <h2 style="margin:0 0 10px;color:#0f172a;">Votre annonce est encore en brouillon</h2>
          <p style="color:#334155;margin:0 0 14px;">Bonjour {seller.get('name') or 'là'},</p>
          <p style="color:#334155;margin:0 0 14px;">Vous avez commencé à créer <strong>{title}</strong> il y a 24 heures et elle n'a pas encore été publiée. Terminez les derniers détails et publiez-la pour commencer à recevoir des offres.</p>
          <p style="text-align:left;margin:20px 0 0;">
            <a href="{edit_url}" style="display:inline-block;padding:12px 22px;background:#0055FF;color:#ffffff;font-weight:600;border-radius:8px;text-decoration:none;">Terminer et publier</a>
          </p>"""
    else:
        subject = f"Finish and publish your listing: {title}"
        body = f"""
          <h2 style="margin:0 0 10px;color:#0f172a;">Your listing is still a draft</h2>
          <p style="color:#334155;margin:0 0 14px;">Hi {seller.get('name') or 'there'},</p>
          <p style="color:#334155;margin:0 0 14px;">You started creating <strong>{title}</strong> 24 hours ago but haven't published it yet. Wrap up the final details and publish so buyers can start bidding.</p>
          <p style="text-align:left;margin:20px 0 0;">
            <a href="{edit_url}" style="display:inline-block;padding:12px 22px;background:#0055FF;color:#ffffff;font-weight:600;border-radius:8px;text-decoration:none;">Finish &amp; publish</a>
          </p>"""
    return {"subject": subject, "html": _base_email_shell(subject, body)}


def _seller_starting_email(seller: dict, listing: dict, collection: str) -> Dict[str, str]:
    lang = _lang_of(seller)
    title = listing.get("title") or "Your auction"
    start = _fmt_datetime(_listing_start_time(listing, collection), lang)
    url   = _seller_admin_url(listing, collection, "manage")
    if lang == "fr":
        subject = f"Votre enchère commence bientôt : {title}"
        body = f"""
          <h2 style="margin:0 0 10px;color:#0f172a;">Votre enchère commence dans environ 2 heures</h2>
          <p style="color:#334155;margin:0 0 14px;">Bonjour {seller.get('name') or 'là'},</p>
          <p style="color:#334155;margin:0 0 14px;">Votre enchère <strong>{title}</strong> commence à <strong>{start}</strong>. C'est le moment de vérifier les détails, les lots et les images.</p>
          <p style="text-align:left;margin:20px 0 0;">
            <a href="{url}" style="display:inline-block;padding:12px 22px;background:#0055FF;color:#ffffff;font-weight:600;border-radius:8px;text-decoration:none;">Ouvrir l'enchère</a>
          </p>"""
    else:
        subject = f"Your auction starts soon: {title}"
        body = f"""
          <h2 style="margin:0 0 10px;color:#0f172a;">Your auction is starting in about 2 hours</h2>
          <p style="color:#334155;margin:0 0 14px;">Hi {seller.get('name') or 'there'},</p>
          <p style="color:#334155;margin:0 0 14px;">Your auction <strong>{title}</strong> starts at <strong>{start}</strong>. Now's the time to double-check details, lots, and images.</p>
          <p style="text-align:left;margin:20px 0 0;">
            <a href="{url}" style="display:inline-block;padding:12px 22px;background:#0055FF;color:#ffffff;font-weight:600;border-radius:8px;text-decoration:none;">Open auction</a>
          </p>"""
    return {"subject": subject, "html": _base_email_shell(subject, body)}


def _seller_winner_email(seller: dict, listing: dict, collection: str, winner_count: int) -> Dict[str, str]:
    lang = _lang_of(seller)
    title = listing.get("title") or "Your auction"
    url = _seller_admin_url(listing, collection, "approve_winners")
    if lang == "fr":
        subject = f"Action requise : approuver les enchérisseurs gagnants — {title}"
        body = f"""
          <h2 style="margin:0 0 10px;color:#0f172a;">Approuvez les enchérisseurs gagnants et lancez l'expédition</h2>
          <p style="color:#334155;margin:0 0 14px;">Bonjour {seller.get('name') or 'là'},</p>
          <p style="color:#334155;margin:0 0 14px;">Votre enchère <strong>{title}</strong> s'est terminée il y a 24 heures avec <strong>{winner_count}</strong> enchérisseur(s) gagnant(s) qui n'ont pas encore été approuvés. Approuvez-les pour lancer l'expédition et clore les transactions.</p>
          <p style="text-align:left;margin:20px 0 0;">
            <a href="{url}" style="display:inline-block;padding:12px 22px;background:#0055FF;color:#ffffff;font-weight:600;border-radius:8px;text-decoration:none;">Approuver &amp; expédier</a>
          </p>"""
    else:
        subject = f"Action required: approve winning bidders — {title}"
        body = f"""
          <h2 style="margin:0 0 10px;color:#0f172a;">Approve your winning bidders and start shipping</h2>
          <p style="color:#334155;margin:0 0 14px;">Hi {seller.get('name') or 'there'},</p>
          <p style="color:#334155;margin:0 0 14px;">Your auction <strong>{title}</strong> ended 24 hours ago with <strong>{winner_count}</strong> winning bidder(s) still awaiting your approval. Approve them to trigger shipping and close out the sale.</p>
          <p style="text-align:left;margin:20px 0 0;">
            <a href="{url}" style="display:inline-block;padding:12px 22px;background:#0055FF;color:#ffffff;font-weight:600;border-radius:8px;text-decoration:none;">Approve &amp; ship</a>
          </p>"""
    return {"subject": subject, "html": _base_email_shell(subject, body)}


# ─── Trigger A: Draft ≥24h ───────────────────────────────────────────

async def run_seller_draft_reminders(db) -> Dict[str, int]:
    """Find draft listings created ≥24h ago that have never been reminded
    and email the seller. Runs hourly via APScheduler."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=SELLER_DRAFT_TRIGGER_HOURS)
    counts = {"scanned": 0, "sent": 0, "skipped": 0}

    for col in ("multi_item_listings", "vehicle_listings", "storage_auctions", "listings"):
        # Match both datetime-typed and string-typed created_at.
        cutoff_iso = cutoff.isoformat()
        query = {
            "status": {"$regex": "^(draft|pending)$", "$options": "i"},
            "$or": [
                {"draft_reminder_sent_at": {"$exists": False}},
                {"draft_reminder_sent_at": None},
                {"draft_reminder_sent_at": ""},
            ],
            "$and": [{
                "$or": [
                    {"created_at": {"$lte": cutoff}},
                    {"created_at": {"$lte": cutoff_iso}},
                ]
            }],
        }
        async for listing in db[col].find(query, {"_id": 0}):
            counts["scanned"] += 1
            # Also match against string-typed created_at (some collections store ISO).
            ca = listing.get("created_at")
            if isinstance(ca, str):
                try:
                    ca_dt = datetime.fromisoformat(ca.replace("Z", "+00:00"))
                    if ca_dt.tzinfo is None:
                        ca_dt = ca_dt.replace(tzinfo=timezone.utc)
                    if ca_dt > cutoff:
                        continue
                except Exception:
                    pass
            seller_id = listing.get("seller_id")
            if not seller_id or not await _seller_has_any_listing(db, seller_id):
                counts["skipped"] += 1
                continue
            seller = await _get_seller_user(db, seller_id)
            if not seller or not seller.get("email"):
                counts["skipped"] += 1
                continue
            content = _seller_draft_email(seller, listing, col)
            result = await _send(seller["email"], content["subject"], content["html"], category="seller_draft")
            await db[col].update_one(
                {"id": listing["id"]},
                {"$set": {"draft_reminder_sent_at": now.isoformat()}},
            )
            if (result or {}).get("status") == "skipped":
                counts["skipped"] += 1
            else:
                counts["sent"] += 1
    logger.info(f"[seller_draft_reminders] {counts}")
    return counts


# ─── Trigger B: Auction starting in 90–150 min ───────────────────────

async def run_seller_auction_starting_reminders(db) -> Dict[str, int]:
    """Find scheduled auctions whose `auction_start_date` falls between
    90 and 150 minutes from now, that haven't already been reminded."""
    now = datetime.now(timezone.utc)
    lo_dt = now + timedelta(minutes=SELLER_STARTING_LOWER_MIN)
    hi_dt = now + timedelta(minutes=SELLER_STARTING_UPPER_MIN)
    lo_iso, hi_iso = lo_dt.isoformat(), hi_dt.isoformat()
    counts = {"scanned": 0, "sent": 0, "skipped": 0}

    # We do string-ISO comparisons because start dates are stored as ISO
    # strings in most collections.
    for col in ("multi_item_listings", "vehicle_listings", "storage_auctions"):
        # Auction start date is stored under different keys per collection.
        for start_field in ("auction_start_date", "auction_start_time", "scheduled_start"):
            query = {
                start_field: {"$gte": lo_iso, "$lte": hi_iso},
                "$or": [
                    {"starting_reminder_sent_at": {"$exists": False}},
                    {"starting_reminder_sent_at": None},
                ],
            }
            async for listing in db[col].find(query, {"_id": 0}):
                counts["scanned"] += 1
                seller_id = listing.get("seller_id")
                if not seller_id or not await _seller_has_any_listing(db, seller_id):
                    counts["skipped"] += 1
                    continue
                seller = await _get_seller_user(db, seller_id)
                if not seller or not seller.get("email"):
                    counts["skipped"] += 1
                    continue
                content = _seller_starting_email(seller, listing, col)
                result = await _send(seller["email"], content["subject"], content["html"], category="seller_starting_soon")
                await db[col].update_one(
                    {"id": listing["id"]},
                    {"$set": {"starting_reminder_sent_at": now.isoformat()}},
                )
                if (result or {}).get("status") == "skipped":
                    counts["skipped"] += 1
                else:
                    counts["sent"] += 1
    logger.info(f"[seller_starting_reminders] {counts}")
    return counts


# ─── Trigger C: Ended ≥24h with unapproved winners ───────────────────

async def _has_unapproved_winners(db, listing: dict, collection: str) -> int:
    """Return the count of unapproved winners on the listing.
    A "winner" is defined as the top bid on a lot/vehicle whose status is
    not yet "approved" or "paid"."""
    lid = listing["id"]
    if collection == "multi_item_listings":
        unapproved = 0
        for lot in (listing.get("lots") or []):
            lot_status = (lot.get("lot_status") or lot.get("status") or "").lower()
            if lot_status in ("ended", "closed"):
                # Look up top bid on this lot
                top = await db.bids.find_one(
                    {"listing_id": lid, "lot_number": lot.get("lot_number")},
                    {"_id": 0, "status": 1},
                    sort=[("amount", -1)],
                )
                if top and (top.get("status") or "").lower() not in ("approved", "paid", "shipped"):
                    unapproved += 1
        return unapproved
    # Single-listing collections: check for a single top bid.
    top = await db.bids.find_one(
        {"listing_id": lid}, {"_id": 0, "status": 1},
        sort=[("amount", -1)],
    )
    if top and (top.get("status") or "").lower() not in ("approved", "paid", "shipped"):
        return 1
    return 0


async def run_seller_winner_approval_reminders(db) -> Dict[str, int]:
    """Find ended auctions whose end date was ≥24h ago and which still
    have winning bids that the seller hasn't approved."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=SELLER_WINNER_APPROVE_HOURS)
    cutoff_iso = cutoff.isoformat()
    counts = {"scanned": 0, "sent": 0, "skipped": 0}

    for col in ("multi_item_listings", "vehicle_listings", "storage_auctions", "listings"):
        # End date lives under different keys — try each.
        for end_field in ("auction_end_date", "auction_end_time", "ends_at", "end_date"):
            query = {
                end_field: {"$lte": cutoff_iso},
                "status": {"$in": ["ended", "closed", "sold"]},
                "$or": [
                    {"winner_reminder_sent_at": {"$exists": False}},
                    {"winner_reminder_sent_at": None},
                ],
            }
            async for listing in db[col].find(query, {"_id": 0}):
                counts["scanned"] += 1
                unapproved = await _has_unapproved_winners(db, listing, col)
                if unapproved <= 0:
                    counts["skipped"] += 1
                    continue
                seller_id = listing.get("seller_id")
                if not seller_id or not await _seller_has_any_listing(db, seller_id):
                    counts["skipped"] += 1
                    continue
                seller = await _get_seller_user(db, seller_id)
                if not seller or not seller.get("email"):
                    counts["skipped"] += 1
                    continue
                content = _seller_winner_email(seller, listing, col, unapproved)
                result = await _send(seller["email"], content["subject"], content["html"], category="seller_winner_approval")
                await db[col].update_one(
                    {"id": listing["id"]},
                    {"$set": {"winner_reminder_sent_at": now.isoformat()}},
                )
                if (result or {}).get("status") == "skipped":
                    counts["skipped"] += 1
                else:
                    counts["sent"] += 1
    logger.info(f"[seller_winner_reminders] {counts}")
    return counts


__all__ = [
    "dispatch_buyer_interest_emails",
    "run_seller_draft_reminders",
    "run_seller_auction_starting_reminders",
    "run_seller_winner_approval_reminders",
    "BUYER_INTEREST_RATE_LIMIT_HOURS",
]
