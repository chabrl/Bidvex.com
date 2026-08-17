"""
iter488 — B2B Matchmaker Phase 2 (approval-based).

Replaces the Phase-1 stub of the `B2B_syndication_matchmaker` MCP tool
with a working, approval-based recommendation pipeline:

    Seller Inventory  →  Manifest Parser
                    ↓
             Buyer Preference Clustering
                    ↓
        Match Scoring (explainable, 0..100)
                    ↓
     Bilingual EN/FR Campaign Draft Generation
                    ↓
    REQUIRES EXPLICIT APPROVAL (no autonomous action)
                    ↓
                Audit

Design invariants (never violated):
  * Never sends emails or contacts buyers autonomously.
  * Never spends advertising money.
  * Never creates paid campaigns.
  * Never modifies seller listings or places bids.
  * Never exposes buyer PII beyond what the seller already knows about
    them (user_id + optional business_name); no phone, no email address,
    no card details.
  * Uses ONLY legitimate business signals (vertical, category, asset
    type, geography, price range, quantity, condition, explicit buyer
    preferences, historical bidding).
  * "Execution" is a no-op that returns
    `campaign_status="authorized_pending_dispatch"` — actual dispatch
    is deliberately deferred to Ops until BidVex email/ad plumbing is
    wired for approval-based campaigns.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("bidvex.b2b_matchmaker")

# Collections we inspect for the seller's inventory. Each is normalised
# into a common Inventory Item schema below.
_SELLER_COLLECTIONS: List[Tuple[str, str]] = [
    ("listings",                 "marketplace"),
    ("multi_item_listings",      "lots"),
    ("vehicles",                 "vehicle"),
    ("vehicle_multi_lot_listings", "vehicle_multi_lot"),
    ("storage_units",            "storage"),
]

# Verticals surfaced to buyers.
VERTICALS = {"marketplace", "lots", "vehicle", "vehicle_multi_lot", "storage"}


# ═══════════════════════════════════════════════════════════════════
# 1) MANIFEST PARSER
# ═══════════════════════════════════════════════════════════════════
def _pick(doc: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in doc and doc[k] is not None:
            return doc[k]
    return default


def _normalise_item(doc: Dict[str, Any], vertical: str) -> Dict[str, Any]:
    """Common schema across all five collections. Missing values are
    explicitly None — we never invent data."""
    price = _pick(doc, "current_price", "current_bid", "starting_bid", "starting_price")
    quantity = _pick(doc, "quantity", default=1)
    end_time = _pick(doc, "auction_end_date", "lot_end_time", "end_time", "auction_end_time")
    location = _pick(doc, "pickup_location", "location", "city", "province")

    make = _pick(doc, "make", "manufacturer")
    model = _pick(doc, "model")
    year = _pick(doc, "year", "model_year")

    normalised = {
        "listing_id":    _pick(doc, "id"),
        "seller_id":     _pick(doc, "seller_id"),
        "vertical":      vertical,
        "title":         _pick(doc, "title", "title_en"),
        "description":   _pick(doc, "description", "description_en"),
        "category":      _pick(doc, "category"),
        "asset_type":    _pick(doc, "asset_type", "type", default=vertical),
        "make":          make,
        "model":         model,
        "year":          year,
        "quantity":      quantity,
        "condition":     _pick(doc, "condition"),
        "location":      location,
        "price":         float(price) if price is not None else None,
        "reserve_price": _pick(doc, "reserve_price"),  # may be masked at API boundary
        "current_bid":   _pick(doc, "current_bid", "current_price"),
        "status":        _pick(doc, "status", default="unknown"),
        "auction_end":   end_time,
        "buyer_requirements": _pick(doc, "buyer_requirements", "required_buyer_type", default=None),
    }
    # Flag missing critical fields for transparency.
    missing = [k for k in ("title", "vertical", "price") if not normalised.get(k)]
    normalised["_missing_fields"] = missing
    normalised["_is_complete"] = not missing
    return normalised


async def parse_seller_manifest(db, seller_id: str, *, limit: int = 200) -> Dict[str, Any]:
    """Fetch and normalise a seller's inventory across all five verticals.

    Returns:
        {
          "seller_id": str,
          "total_items": int,
          "items": [InventoryItem, ...],   # normalised
          "malformed": [{"listing_id","vertical","reason"}, ...],
        }
    """
    items: List[Dict[str, Any]] = []
    malformed: List[Dict[str, Any]] = []
    for coll_name, vertical in _SELLER_COLLECTIONS:
        try:
            rows = await db[coll_name].find(
                {"seller_id": seller_id}, {"_id": 0},
            ).sort("created_at", -1).limit(limit).to_list(limit)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[b2b] parse_seller_manifest {coll_name}: {type(exc).__name__}")
            continue
        for row in rows:
            try:
                item = _normalise_item(row, vertical)
                items.append(item)
                if not item["_is_complete"]:
                    malformed.append({
                        "listing_id": item["listing_id"],
                        "vertical":   vertical,
                        "reason":     f"missing_fields:{','.join(item['_missing_fields'])}",
                    })
            except Exception as exc:  # noqa: BLE001
                malformed.append({
                    "listing_id": row.get("id"),
                    "vertical":   vertical,
                    "reason":     f"normalise_error:{type(exc).__name__}",
                })
    return {
        "seller_id":     seller_id,
        "total_items":   len(items),
        "malformed":     malformed,
        "items":         items,
    }


# ═══════════════════════════════════════════════════════════════════
# 2) BUYER PREFERENCE CLUSTERING
# ═══════════════════════════════════════════════════════════════════
def _buyer_segment(user: Dict[str, Any]) -> str:
    """Classify a qualified B2B buyer into a coarse segment."""
    if user.get("is_vehicle_dealer") is True:
        return "vehicle_dealer"
    account_type = (user.get("account_type") or "").lower()
    if account_type == "broker":
        return "broker"
    if account_type == "storage_facility":
        return "storage_facility"
    if account_type == "business":
        return "business"
    return "corporate_buyer"


async def _historical_signals(db, buyer_id: str) -> Dict[str, Any]:
    """Collect legitimate historical bidding signals for a buyer.

    Uses ONLY `bids` and `lot_bids` — no PII collection, no attempt to
    identify buyer interest beyond what they've already publicly signalled
    on-platform.
    """
    try:
        recent_bids = await db.bids.find(
            {"bidder_id": buyer_id},
            {"_id": 0, "listing_id": 1, "amount": 1, "created_at": 1},
        ).sort("created_at", -1).limit(100).to_list(100)
    except Exception:  # noqa: BLE001
        recent_bids = []
    try:
        recent_lot_bids = await db.lot_bids.find(
            {"bidder_id": buyer_id},
            {"_id": 0, "listing_id": 1, "lot_number": 1, "amount": 1, "created_at": 1},
        ).sort("created_at", -1).limit(100).to_list(100)
    except Exception:  # noqa: BLE001
        recent_lot_bids = []
    # Pull the categories of those listings (best-effort)
    listing_ids: Set[str] = set()
    for b in recent_bids + recent_lot_bids:
        lid = b.get("listing_id")
        if lid:
            listing_ids.add(lid)
    categories_seen: List[str] = []
    if listing_ids:
        try:
            docs = await db.listings.find(
                {"id": {"$in": list(listing_ids)}},
                {"_id": 0, "category": 1, "vertical": 1},
            ).to_list(200)
            categories_seen = [d.get("category") for d in docs if d.get("category")]
        except Exception:  # noqa: BLE001
            pass
    return {
        "bid_count":       len(recent_bids) + len(recent_lot_bids),
        "categories_seen": categories_seen[:20],
        "avg_bid_amount":  round(
            sum(float(b.get("amount") or 0) for b in recent_bids + recent_lot_bids) /
            max(1, len(recent_bids) + len(recent_lot_bids)),
            2,
        ),
    }


async def identify_qualified_buyers(db, *, limit: int = 200) -> List[Dict[str, Any]]:
    """Return a lean list of qualified B2B buyer profiles.

    A "qualified" buyer is any BidVex user who meets at least ONE:
      * `is_vehicle_dealer=True` with `vehicle_dealer_verified=True`
      * `account_type in {"broker", "storage_facility", "business"}` with
        `subscription_status="active"` OR `admin_verified=True`

    Returns:
        [
          {
            "user_id":       str,
            "business_name": str | None,     # legitimate on-platform
            "segment":       str,
            "signals":       {"categories","verticals","provinces","avg_bid"},
            "historical":    { … from _historical_signals },
          },
          …
        ]
    """
    query = {
        "$or": [
            {"is_vehicle_dealer": True, "vehicle_dealer_verified": True},
            {"account_type": "broker", "subscription_status": "active"},
            {"account_type": "broker", "admin_verified": True},
            {"account_type": "storage_facility", "facility_verified": True},
            {"account_type": "business", "subscription_status": "active"},
            {"account_type": "business", "admin_verified": True},
        ],
    }
    try:
        rows = await db.users.find(
            query,
            {"_id": 0, "id": 1, "business_name": 1, "company_name": 1,
             "account_type": 1, "is_vehicle_dealer": 1,
             "buyer_preferences": 1, "province": 1, "address": 1,
             "categories_of_interest": 1},
        ).limit(limit).to_list(limit)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[b2b] identify_qualified_buyers query failed: {type(exc).__name__}")
        return []
    profiles: List[Dict[str, Any]] = []
    for u in rows:
        prefs = u.get("buyer_preferences") or {}
        signals = {
            "categories":  list(prefs.get("categories") or u.get("categories_of_interest") or []),
            "verticals":   list(prefs.get("verticals") or []),
            "provinces":   list(prefs.get("provinces") or ([u.get("province")] if u.get("province") else [])),
            "min_price":   prefs.get("min_price"),
            "max_price":   prefs.get("max_price"),
            "min_quantity": prefs.get("min_quantity"),
        }
        profiles.append({
            "user_id":       u.get("id"),
            "business_name": u.get("business_name") or u.get("company_name"),
            "segment":       _buyer_segment(u),
            "signals":       signals,
            "historical":    await _historical_signals(db, u.get("id")),
        })
    return profiles


# ═══════════════════════════════════════════════════════════════════
# 3) MATCH SCORING (0..100, explainable)
# ═══════════════════════════════════════════════════════════════════
def _norm(s: Any) -> str:
    return (str(s or "").strip().lower())


def score_match(item: Dict[str, Any], buyer: Dict[str, Any]) -> Dict[str, Any]:
    """Score an inventory item against a buyer profile. Every score
    contribution is emitted as an explicit reason string so downstream
    consumers can render the match rationale to a human.

    Score components (weights sum to 100):
      * vertical / asset_type match       →  25 pts
      * category match                    →  20 pts
      * geography match (province)        →  15 pts
      * price-range match                 →  15 pts
      * quantity-range match              →  10 pts
      * historical bid signal (same cat.) →  10 pts
      * condition preference              →   5 pts
    """
    reasons: List[str] = []
    score = 0

    signals = buyer.get("signals") or {}
    hist = buyer.get("historical") or {}

    # (a) vertical / asset_type
    v = _norm(item.get("vertical"))
    at = _norm(item.get("asset_type"))
    buyer_verticals = {_norm(x) for x in (signals.get("verticals") or [])}
    if v and (v in buyer_verticals or _buyer_matches_vertical(buyer, v)):
        score += 25
        reasons.append(f"vertical_match:{v}")
    elif at and buyer_verticals and at in buyer_verticals:
        score += 15
        reasons.append(f"asset_type_match:{at}")

    # (b) category
    cat = _norm(item.get("category"))
    buyer_cats = {_norm(x) for x in (signals.get("categories") or [])}
    if cat and cat in buyer_cats:
        score += 20
        reasons.append(f"category_match:{cat}")

    # (c) geography
    loc = _norm(item.get("location"))
    buyer_provs = {_norm(x) for x in (signals.get("provinces") or []) if x}
    if loc and buyer_provs and any(p in loc for p in buyer_provs):
        score += 15
        reasons.append("geography_match")

    # (d) price range
    price = item.get("price")
    min_p, max_p = signals.get("min_price"), signals.get("max_price")
    if price is not None and (min_p is not None or max_p is not None):
        ok = True
        if min_p is not None and price < float(min_p):
            ok = False
        if max_p is not None and price > float(max_p):
            ok = False
        if ok:
            score += 15
            reasons.append("price_range_match")

    # (e) quantity
    q = item.get("quantity") or 1
    min_q = signals.get("min_quantity")
    if min_q is not None:
        try:
            if int(q) >= int(min_q):
                score += 10
                reasons.append("quantity_match")
        except (TypeError, ValueError):
            pass

    # (f) historical bid signal — same category previously bid on
    if cat and cat in {_norm(c) for c in (hist.get("categories_seen") or [])}:
        score += 10
        reasons.append("historical_bidding_in_category")

    # (g) condition preference (if buyer stated one)
    cond_pref = _norm(signals.get("condition_preference"))
    cond_item = _norm(item.get("condition"))
    if cond_pref and cond_item and cond_pref == cond_item:
        score += 5
        reasons.append("condition_match")

    return {
        "score":   min(100, score),
        "reasons": reasons,
    }


def _buyer_matches_vertical(buyer: Dict[str, Any], vertical: str) -> bool:
    """Segment-based fallback: vehicle dealers care about vehicle
    verticals, storage facilities about storage, etc."""
    seg = (buyer.get("segment") or "").lower()
    if seg == "vehicle_dealer" and vertical in {"vehicle", "vehicle_multi_lot"}:
        return True
    if seg == "storage_facility" and vertical == "storage":
        return True
    if seg == "broker" and vertical in {"marketplace", "lots", "vehicle"}:
        return True
    if seg == "business" and vertical in {"marketplace", "lots", "storage"}:
        return True
    return False


def rank_matches(items: List[Dict[str, Any]], buyers: List[Dict[str, Any]],
                 *, min_score: int = 30, per_buyer_limit: int = 5) -> List[Dict[str, Any]]:
    """Produce a ranked cross-product of `(buyer, [top items])`."""
    out: List[Dict[str, Any]] = []
    for buyer in buyers:
        scored: List[Dict[str, Any]] = []
        for item in items:
            r = score_match(item, buyer)
            if r["score"] >= min_score:
                scored.append({
                    "listing_id": item.get("listing_id"),
                    "vertical":   item.get("vertical"),
                    "title":      item.get("title"),
                    "category":   item.get("category"),
                    "price":      item.get("price"),
                    "score":      r["score"],
                    "reasons":    r["reasons"],
                })
        scored.sort(key=lambda x: -x["score"])
        if scored:
            out.append({
                "buyer": {
                    "user_id":       buyer["user_id"],
                    "business_name": buyer.get("business_name"),
                    "segment":       buyer.get("segment"),
                },
                "items": scored[:per_buyer_limit],
                "top_score": scored[0]["score"],
            })
    out.sort(key=lambda x: -x["top_score"])
    return out


# ═══════════════════════════════════════════════════════════════════
# 4) BILINGUAL CAMPAIGN DRAFT GENERATION
# ═══════════════════════════════════════════════════════════════════
_SEGMENT_LABEL_EN = {
    "vehicle_dealer":   "vehicle dealers",
    "broker":           "professional brokers",
    "storage_facility": "storage facility operators",
    "business":         "business buyers",
    "corporate_buyer":  "corporate buyers",
}
_SEGMENT_LABEL_FR = {
    "vehicle_dealer":   "concessionnaires automobiles",
    "broker":           "courtiers professionnels",
    "storage_facility": "exploitants d'installations d'entreposage",
    "business":         "acheteurs professionnels",
    "corporate_buyer":  "acheteurs corporatifs",
}


def _campaign_subject(match: Dict[str, Any], lang: str) -> str:
    n = len(match.get("items") or [])
    seg = match.get("buyer", {}).get("segment") or "corporate_buyer"
    if lang == "fr":
        return (
            f"{n} annonces BidVex correspondant à votre profil "
            f"({_SEGMENT_LABEL_FR.get(seg, 'acheteur')})"
        )
    return (
        f"{n} BidVex listings matched to your profile "
        f"({_SEGMENT_LABEL_EN.get(seg, 'buyer')})"
    )


def _campaign_body(match: Dict[str, Any], lang: str) -> str:
    items = match.get("items") or []
    seg = match.get("buyer", {}).get("segment") or "corporate_buyer"
    if lang == "fr":
        lines = [
            "Bonjour,",
            "",
            f"Nous avons identifié {len(items)} annonce(s) actuellement disponibles sur BidVex "
            f"qui correspondent aux préférences enregistrées pour votre segment "
            f"({_SEGMENT_LABEL_FR.get(seg, 'acheteur')}). Voici un aperçu :",
            "",
        ]
        for it in items:
            price = f"{it['price']:.2f} $" if isinstance(it.get("price"), (int, float)) else "—"
            lines.append(
                f"  • {it.get('title') or '(sans titre)'} — {it.get('category') or 'sans catégorie'} — {price} "
                f"(pertinence {it['score']}/100 · raisons : {', '.join(it.get('reasons') or [])})"
            )
        lines += [
            "",
            "Consultez les annonces sur BidVex si elles correspondent à vos besoins.",
            "Cordialement, l'équipe BidVex.",
        ]
        return "\n".join(lines)
    # English
    lines = [
        "Hello,",
        "",
        f"We identified {len(items)} BidVex listing(s) currently available "
        f"that align with the preferences registered for your buyer segment "
        f"({_SEGMENT_LABEL_EN.get(seg, 'buyer')}). Preview:",
        "",
    ]
    for it in items:
        price = f"${it['price']:.2f}" if isinstance(it.get("price"), (int, float)) else "—"
        lines.append(
            f"  • {it.get('title') or '(untitled)'} — {it.get('category') or 'uncategorized'} — {price} "
            f"(match {it['score']}/100 · reasons: {', '.join(it.get('reasons') or [])})"
        )
    lines += [
        "",
        "Please review the listings on BidVex if any match your buying needs.",
        "Best regards, the BidVex team.",
    ]
    return "\n".join(lines)


def draft_bilingual_campaign(match: Dict[str, Any]) -> Dict[str, Any]:
    """Build a bilingual campaign draft for one buyer-match block."""
    items = match.get("items") or []
    listing_refs = [it.get("listing_id") for it in items if it.get("listing_id")]
    return {
        "campaign_id":  f"camp_{uuid.uuid4().hex[:16]}",
        "buyer":        match["buyer"],
        "listing_refs": listing_refs,
        "match_score":  match["top_score"],
        "match_reasons": sorted({r for it in items for r in (it.get("reasons") or [])}),
        "en": {
            "subject": _campaign_subject(match, "en"),
            "message": _campaign_body(match, "en"),
        },
        "fr": {
            "subject": _campaign_subject(match, "fr"),
            "message": _campaign_body(match, "fr"),
        },
        "status": "draft_awaiting_approval",
    }


# ═══════════════════════════════════════════════════════════════════
# 5) TOP-LEVEL ORCHESTRATION — analyze / match / generate
# ═══════════════════════════════════════════════════════════════════
async def run_matchmaker(
    db, *, seller_id: str, min_score: int = 30, max_matches: int = 20,
) -> Dict[str, Any]:
    """Analyze the seller's inventory, find qualified buyers, rank
    matches, and produce bilingual campaign drafts. This function does
    NOT send anything, does NOT modify listings, and does NOT bid.

    Returns a plain-JSON-serialisable result with `status="drafts_ready"`.
    """
    manifest = await parse_seller_manifest(db, seller_id)
    if not manifest["items"]:
        return {
            "status":       "no_inventory",
            "seller_id":    seller_id,
            "manifest":     manifest,
            "matches":      [],
            "campaigns":    [],
        }
    buyers = await identify_qualified_buyers(db)
    ranked = rank_matches(manifest["items"], buyers, min_score=min_score)
    ranked = ranked[:max_matches]
    campaigns = [draft_bilingual_campaign(m) for m in ranked]
    return {
        "status":       "drafts_ready",
        "seller_id":    seller_id,
        "manifest": {
            "total_items": manifest["total_items"],
            "malformed":   manifest["malformed"],
        },
        "qualified_buyer_count": len(buyers),
        "match_count":           len(ranked),
        "matches":               ranked,
        "campaigns":             campaigns,
        "approval_required":     True,
        "safety_notice_en": (
            "This tool produces campaign drafts and match recommendations only. "
            "BidVex will never send emails, contact buyers, place bids, or spend "
            "advertising money without explicit authorised approval."
        ),
        "safety_notice_fr": (
            "Cet outil produit uniquement des projets de campagne et des "
            "recommandations. BidVex n'envoie jamais de courriels, ne contacte "
            "jamais d'acheteurs, ne place jamais d'enchères et ne dépense jamais "
            "de budget publicitaire sans autorisation explicite."
        ),
    }


async def authorised_execute_campaign(
    db, *, campaign_id: str, actor_user_id: str, seller_id: str,
    explicit_authorization: bool,
) -> Dict[str, Any]:
    """Deliberately does NOT dispatch. Records the intent in the audit
    log and returns `authorized_pending_dispatch`. Actual dispatch is
    left to a future Ops-provisioned worker; this keeps the Matchmaker
    approval-gated in perpetuity.
    """
    if not explicit_authorization:
        return {
            "status":  "approval_required",
            "message_en": "This campaign requires explicit authorised approval before any external action.",
            "message_fr": "Cette campagne nécessite une autorisation explicite avant toute action externe.",
        }
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id":             str(uuid.uuid4()),
        "campaign_id":    campaign_id,
        "seller_id":      seller_id,
        "authorised_by":  actor_user_id,
        "authorised_at":  now,
        "status":         "authorized_pending_dispatch",
        "dispatched":     False,
    }
    try:
        await db["b2b_matchmaker_authorisations"].insert_one(record)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[b2b] authorisation persist failed: {type(exc).__name__}")
    return {
        "campaign_id":    campaign_id,
        "status":         "authorized_pending_dispatch",
        "dispatched":     False,
        "message_en":     "Authorisation recorded. No external action has been performed. "
                          "Dispatch remains a manual Ops action.",
        "message_fr":     "Autorisation enregistrée. Aucune action externe n'a été effectuée. "
                          "L'envoi reste une action manuelle de l'exploitation.",
    }


__all__ = [
    "parse_seller_manifest",
    "identify_qualified_buyers",
    "score_match",
    "rank_matches",
    "draft_bilingual_campaign",
    "run_matchmaker",
    "authorised_execute_campaign",
]
