"""
iter337 — Ad Campaigns admin panel + Gemini ad-copy generator + CSV export.

Directive 3 — Foundation for multi-platform ad syndication (Google Ads,
Meta Ads). This module owns:

  • POST /api/admin/ad-campaigns              — create draft campaign(s)
      from a list of listing_ids; Gemini 2.5 Flash generates headline
      (<= 40 chars) + description (<= 90 chars) in EN + FR per listing.
  • GET  /api/admin/ad-campaigns              — list campaigns with
      status filter (draft/ready/published).
  • PATCH /api/admin/ad-campaigns/{id}        — admin edits copy or
      flips status draft -> ready.
  • POST /api/admin/ad-campaigns/{id}/regenerate — Gemini re-runs on
      the same listing (max 3 regenerations per campaign row).
  • DELETE /api/admin/ad-campaigns/{id}       — hard delete a draft.
  • GET  /api/admin/ad-campaigns/export.csv?platform=google|meta
      — CSV compatible with Google Merchant Center + Meta Catalog.

Publishing (actual API calls to Meta/Google Ads) is out of scope per the
directive — this module builds the data layer + CSV feed so the BidVex
team can manually upload the CSV to Google Merchant / Meta Business Suite.

Collection: `ad_campaigns`
Document shape:
{
  "id":               "<uuid>",
  "listing_id":       "<listing_id>",
  "listing_type":     "vehicle" | "storage" | "marketplace" | "lots",
  "platform":         "google" | "meta" | "both",
  "headline_en":      "<= 40 chars",
  "headline_fr":      "<= 40 chars",
  "description_en":   "<= 90 chars",
  "description_fr":   "<= 90 chars",
  "image_url":        "<first listing photo>",
  "landing_url":      "<https://bidvex.com/listings/xyz>",
  "status":           "draft" | "ready" | "published",
  "regenerated_count": 0,
  "created_at":       "<iso>",
  "updated_at":       "<iso>",
  "created_by":       "<admin user_id>",
}
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/ad-campaigns", tags=["Ad Campaigns — iter337"])

BIDVEX_BASE_URL = os.environ.get("BIDVEX_BASE_URL", "https://bidvex.com").rstrip("/")
GEMINI_ANALYSIS_MODEL = os.environ.get("GEMINI_COACH_ANALYSIS_MODEL", "").strip() or "gemini-2.5-flash"

MAX_HEADLINE_CHARS = 40   # Google Responsive Search Ads short headline cap
MAX_DESCRIPTION_CHARS = 90  # Google + Meta cross-platform safe cap
MAX_REGENERATIONS = 3


# ─── Pydantic bodies ────────────────────────────────────────────────────

class CreateAdCampaignsBody(BaseModel):
    listing_ids: List[str]
    platform:    str = "both"  # "google" | "meta" | "both"


class UpdateAdCampaignBody(BaseModel):
    headline_en:    Optional[str] = None
    headline_fr:    Optional[str] = None
    description_en: Optional[str] = None
    description_fr: Optional[str] = None
    status:         Optional[str] = None  # draft | ready | published
    platform:       Optional[str] = None


# ─── Gemini copy generator ──────────────────────────────────────────────

_SYSTEM_AD_PROMPT = f"""You are a bilingual (EN + FR) ad copywriter for BidVex, Canada's online auction marketplace.

Given a single BidVex listing, produce a JSON object with EXACTLY these fields:
{{
  "headline_en":    "<= {MAX_HEADLINE_CHARS} characters, punchy, sales-focused, no ALL CAPS>",
  "headline_fr":    "<= {MAX_HEADLINE_CHARS} characters, French, same energy>",
  "description_en": "<= {MAX_DESCRIPTION_CHARS} characters, benefit-focused, includes a call-to-action>",
  "description_fr": "<= {MAX_DESCRIPTION_CHARS} characters, French translation of the description>"
}}

Constraints:
- NEVER exceed {MAX_HEADLINE_CHARS} chars on headlines or {MAX_DESCRIPTION_CHARS} chars on descriptions.
- No prohibited claims (guaranteed profit, "best in world", medical claims).
- No emojis, no ALL CAPS, no exclamation-spam (max 1 !).
- Focus on the specific item's key attribute (make/model, category, condition, etc.).

Output ONLY valid JSON. No markdown fences, no prose, no explanation."""


def _clip(s: str, max_len: int) -> str:
    s = (s or "").strip().replace("\n", " ")
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def _extract_ad_json(raw_text: str) -> Optional[Dict[str, str]]:
    if not raw_text:
        return None
    txt = re.sub(r"```(?:json)?", "", raw_text).strip("` \n\t")
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group())
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(obj, dict):
        return None
    he = _clip(obj.get("headline_en") or "", MAX_HEADLINE_CHARS)
    hf = _clip(obj.get("headline_fr") or "", MAX_HEADLINE_CHARS)
    de = _clip(obj.get("description_en") or "", MAX_DESCRIPTION_CHARS)
    df = _clip(obj.get("description_fr") or "", MAX_DESCRIPTION_CHARS)
    if not (he and hf and de and df):
        return None
    return {"headline_en": he, "headline_fr": hf, "description_en": de, "description_fr": df}


def _fallback_ad_copy(listing: Dict[str, Any]) -> Dict[str, str]:
    """Deterministic bilingual fallback when Gemini output is malformed."""
    title = (listing.get("title") or listing.get("year_make_model")
             or listing.get("name") or "Auction listing").strip()
    title_short = title[:30]
    return {
        "headline_en":    _clip(f"Bid now: {title_short}", MAX_HEADLINE_CHARS),
        "headline_fr":    _clip(f"Enchérissez : {title_short}", MAX_HEADLINE_CHARS),
        "description_en": _clip(f"Live on BidVex — bid on {title_short} today.", MAX_DESCRIPTION_CHARS),
        "description_fr": _clip(f"En direct sur BidVex — enchérissez sur {title_short} dès aujourd'hui.", MAX_DESCRIPTION_CHARS),
    }


async def _generate_ad_copy(listing: Dict[str, Any]) -> tuple[Dict[str, str], bool]:
    """Returns (copy_dict, used_fallback)."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    title = listing.get("title") or listing.get("year_make_model") or listing.get("name") or ""
    description = listing.get("description") or ""
    category = listing.get("category") or listing.get("listing_type") or ""
    price = listing.get("starting_price") or listing.get("current_bid") or listing.get("reserve_price")

    if not api_key:
        logger.info("[ad-copy] GEMINI_API_KEY missing — using fallback")
        return _fallback_ad_copy(listing), True

    prompt = f"""LISTING:
Title: {title}
Category: {category}
Description: {(description or '')[:400]}
Starting price / current bid (CAD): {price if price is not None else 'n/a'}

Generate the JSON per system instructions."""

    try:
        from google import genai
        from google.genai import types as gtypes
        client = genai.Client(api_key=api_key)
        resp = await client.aio.models.generate_content(
            model=GEMINI_ANALYSIS_MODEL,
            contents=prompt,
            config=gtypes.GenerateContentConfig(
                response_mime_type="application/json",
                system_instruction=_SYSTEM_AD_PROMPT,
                temperature=0.6,
            ),
        )
        raw = getattr(resp, "text", None) or ""
        parsed = _extract_ad_json(raw)
        if parsed:
            return parsed, False
        logger.warning(f"[ad-copy] Gemini output malformed — falling back. raw={raw[:200]!r}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ad-copy] Gemini call failed: {e}")

    return _fallback_ad_copy(listing), True


# ─── Listing lookup helper ──────────────────────────────────────────────

_COLLECTIONS_BY_TYPE: Dict[str, str] = {
    "vehicle":     "vehicle_listings",
    "storage":     "storage_auctions",
    "marketplace": "listings",
    "lots":        "multi_item_listings",
}

_URL_PATH_BY_TYPE: Dict[str, str] = {
    "vehicle":     "vehicle-auctions",
    "storage":     "storage-auctions",
    "marketplace": "listings",
    "lots":        "lots",
}


async def _find_listing(db, listing_id: str) -> Optional[Dict[str, Any]]:
    """Look up a listing across the 4 auction-type collections. Returns
    the doc with an added `listing_type` discriminator."""
    for ltype, coll in _COLLECTIONS_BY_TYPE.items():
        try:
            doc = await db[coll].find_one({"id": listing_id})
        except Exception:
            doc = None
        if doc:
            doc["listing_type"] = ltype
            doc.pop("_id", None)
            return doc
    return None


def _first_image_url(listing: Dict[str, Any]) -> str:
    for key in ("primary_image_url", "cover_image", "hero_image_url", "image_url"):
        v = listing.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
    imgs = listing.get("images") or listing.get("photos") or []
    if isinstance(imgs, list):
        for it in imgs:
            if isinstance(it, str) and it.startswith("http"):
                return it
            if isinstance(it, dict):
                u = it.get("url") or it.get("src")
                if isinstance(u, str) and u.startswith("http"):
                    return u
    return f"{BIDVEX_BASE_URL}/assets/placeholder-ad.jpg"


def _landing_url(listing: Dict[str, Any]) -> str:
    ltype = listing.get("listing_type") or "marketplace"
    path = _URL_PATH_BY_TYPE.get(ltype, "listings")
    return f"{BIDVEX_BASE_URL}/{path}/{listing.get('id') or ''}"


# ─── Routes ─────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("")
async def create_ad_campaigns(
    body: CreateAdCampaignsBody,
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Create draft campaigns for a list of listings. Gemini generates
    the copy per listing. Duplicates (same listing_id) are skipped —
    admin should regenerate instead."""
    if body.platform not in {"google", "meta", "both"}:
        raise HTTPException(400, "platform must be one of google|meta|both")
    if not body.listing_ids:
        raise HTTPException(400, "listing_ids cannot be empty")

    created: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    for lid in body.listing_ids:
        existing = await db.ad_campaigns.find_one({"listing_id": lid}, {"_id": 0, "id": 1})
        if existing:
            skipped.append({"listing_id": lid, "reason": "already_exists", "campaign_id": existing["id"]})
            continue
        listing = await _find_listing(db, lid)
        if not listing:
            skipped.append({"listing_id": lid, "reason": "listing_not_found"})
            continue
        copy, used_fallback = await _generate_ad_copy(listing)
        doc = {
            "id":             str(uuid.uuid4()),
            "listing_id":     lid,
            "listing_type":   listing.get("listing_type"),
            "platform":       body.platform,
            **copy,
            "image_url":      _first_image_url(listing),
            "landing_url":    _landing_url(listing),
            "status":         "draft",
            "regenerated_count": 0,
            "used_fallback":  used_fallback,
            "created_at":     _now(),
            "updated_at":     _now(),
            "created_by":     user.id,
        }
        try:
            await db.ad_campaigns.insert_one(doc)
            doc.pop("_id", None)
            created.append(doc)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ad-campaigns] insert failed for {lid}: {e}")
            skipped.append({"listing_id": lid, "reason": "insert_failed"})

    return {"created": created, "skipped": skipped, "total_created": len(created)}


@router.get("")
async def list_ad_campaigns(
    status: Optional[str] = Query(None, description="draft|ready|published"),
    platform: Optional[str] = Query(None, description="google|meta|both"),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if platform:
        q["platform"] = platform
    cursor = db.ad_campaigns.find(q, {"_id": 0}).sort("created_at", -1).limit(limit)
    docs = [d async for d in cursor]
    total = await db.ad_campaigns.count_documents(q)
    return {"items": docs, "count": len(docs), "total": total}


@router.patch("/{campaign_id}")
async def update_ad_campaign(
    campaign_id: str,
    body: UpdateAdCampaignBody,
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    doc = await db.ad_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "campaign not found")
    updates: Dict[str, Any] = {}
    if body.headline_en is not None:
        updates["headline_en"] = _clip(body.headline_en, MAX_HEADLINE_CHARS)
    if body.headline_fr is not None:
        updates["headline_fr"] = _clip(body.headline_fr, MAX_HEADLINE_CHARS)
    if body.description_en is not None:
        updates["description_en"] = _clip(body.description_en, MAX_DESCRIPTION_CHARS)
    if body.description_fr is not None:
        updates["description_fr"] = _clip(body.description_fr, MAX_DESCRIPTION_CHARS)
    if body.status is not None:
        if body.status not in {"draft", "ready", "published"}:
            raise HTTPException(400, "invalid status")
        updates["status"] = body.status
    if body.platform is not None:
        if body.platform not in {"google", "meta", "both"}:
            raise HTTPException(400, "invalid platform")
        updates["platform"] = body.platform
    if not updates:
        return doc
    updates["updated_at"] = _now()
    await db.ad_campaigns.update_one({"id": campaign_id}, {"$set": updates})
    return await db.ad_campaigns.find_one({"id": campaign_id}, {"_id": 0})


@router.post("/{campaign_id}/regenerate")
async def regenerate_ad_campaign(
    campaign_id: str,
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    doc = await db.ad_campaigns.find_one({"id": campaign_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "campaign not found")
    if int(doc.get("regenerated_count") or 0) >= MAX_REGENERATIONS:
        raise HTTPException(429, f"Maximum regenerations reached ({MAX_REGENERATIONS})")
    listing = await _find_listing(db, doc["listing_id"])
    if not listing:
        raise HTTPException(404, "underlying listing no longer exists")
    copy, used_fallback = await _generate_ad_copy(listing)
    await db.ad_campaigns.update_one(
        {"id": campaign_id},
        {
            "$set": {**copy, "used_fallback": used_fallback, "updated_at": _now()},
            "$inc": {"regenerated_count": 1},
        },
    )
    return await db.ad_campaigns.find_one({"id": campaign_id}, {"_id": 0})


@router.delete("/{campaign_id}")
async def delete_ad_campaign(
    campaign_id: str,
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    r = await db.ad_campaigns.delete_one({"id": campaign_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "campaign not found")
    return {"deleted": True, "id": campaign_id}


# ─── CSV Export (Google Merchant / Meta Catalog compatible) ────────────

@router.get("/export.csv", response_class=PlainTextResponse)
async def export_ad_campaigns_csv(
    platform: str = Query("both", description="google|meta|both — controls headers"),
    status: str = Query("ready", description="draft|ready|published — default ready"),
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> PlainTextResponse:
    """Export ready campaigns as CSV. Uses the Google Merchant Center /
    Meta Catalog canonical column names — 'id', 'title', 'description',
    'link', 'image_link', 'availability', 'condition', 'price',
    'brand'. Fields we don't have per-campaign default to 'in stock',
    'used' (auctions are typically used), 'BidVex', CAD-priced from the
    underlying listing if present."""
    if platform not in {"google", "meta", "both"}:
        raise HTTPException(400, "platform must be one of google|meta|both")
    q: Dict[str, Any] = {"status": status}
    if platform != "both":
        q["platform"] = {"$in": [platform, "both"]}
    campaigns = await db.ad_campaigns.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)

    # Google Merchant Center + Meta Catalog canonical columns.
    fieldnames = [
        "id", "title", "description", "link", "image_link",
        "availability", "condition", "price", "brand",
        "custom_label_0", "custom_label_1",  # platform + listing_type
    ]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, quoting=csv.QUOTE_ALL,
                       lineterminator="\r\n")
    w.writeheader()
    for c in campaigns:
        # Prefer English row; export FR variant on request via query param.
        title = c.get("headline_en") or c.get("headline_fr") or ""
        desc  = c.get("description_en") or c.get("description_fr") or ""
        # Try to enrich with listing price (best-effort).
        price_str = ""
        try:
            lst = await _find_listing(db, c.get("listing_id"))
            price = (lst or {}).get("starting_price") or (lst or {}).get("current_bid")
            if isinstance(price, (int, float)) and price > 0:
                price_str = f"{price:.2f} CAD"
        except Exception:
            pass
        w.writerow({
            "id":             c.get("id"),
            "title":          title,
            "description":    desc,
            "link":           c.get("landing_url"),
            "image_link":     c.get("image_url"),
            "availability":   "in stock",
            "condition":      "used",
            "price":          price_str,
            "brand":          "BidVex",
            "custom_label_0": c.get("platform"),
            "custom_label_1": c.get("listing_type"),
        })
    return PlainTextResponse(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="bidvex-ad-campaigns-{datetime.now(timezone.utc).date().isoformat()}.csv"',
        },
    )
