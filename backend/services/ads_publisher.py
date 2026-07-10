"""
iter339 — Meta / Google Ads direct publishing service.

All external SDK imports are LAZY (inside functions) so the app boots
even when facebook-business / google-ads aren't needed. Every public
entry point is gated by feature flags derived from env vars:

  Meta:   META_APP_ID, META_APP_SECRET, META_ACCESS_TOKEN,
          META_AD_ACCOUNT_ID (act_...), META_PAGE_ID
          Optional: META_INTEREST_IDS, META_DAILY_BUDGET_CENTS, META_AD_STATUS
  Google: GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CLIENT_ID,
          GOOGLE_ADS_CLIENT_SECRET, GOOGLE_ADS_REFRESH_TOKEN,
          GOOGLE_ADS_LOGIN_CUSTOMER_ID, GOOGLE_ADS_CLIENT_CUSTOMER_ID

Ads are created PAUSED by default (safe) — the BidVex team activates
them in Ads Manager / Google Ads UI.
"""
from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

META_REQUIRED_ENV = [
    "META_APP_ID", "META_APP_SECRET", "META_ACCESS_TOKEN",
    "META_AD_ACCOUNT_ID", "META_PAGE_ID",
]
GOOGLE_REQUIRED_ENV = [
    "GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_LOGIN_CUSTOMER_ID", "GOOGLE_ADS_CLIENT_CUSTOMER_ID",
]

META_INTEREST_NAMES = ["Auction", "Vehicles", "Liquidation", "Real estate"]


def meta_flag() -> Dict[str, Any]:
    missing = [k for k in META_REQUIRED_ENV if not os.environ.get(k, "").strip()]
    return {
        "enabled": not missing,
        "missing": missing,
        "prerequisite": (
            "" if not missing else
            "Meta Ads publishing requires a verified Business Manager account and an "
            "approved Marketing API access request. Once approved, set the missing "
            "environment variables and publishing enables automatically."
        ),
    }


def google_flag() -> Dict[str, Any]:
    missing = [k for k in GOOGLE_REQUIRED_ENV if not os.environ.get(k, "").strip()]
    return {
        "enabled": not missing,
        "missing": missing,
        "prerequisite": (
            "" if not missing else
            "Google Ads publishing requires a Google Ads account with API access enabled "
            "and a STANDARD-access developer token (not test access), plus OAuth credentials. "
            "Once approved, set the missing environment variables and publishing enables automatically."
        ),
    }


# ─── Payload builders (pure — unit-testable without SDKs) ───────────────

def build_meta_adset_targeting(interest_ids: List[str]) -> Dict[str, Any]:
    """Canada · age 25-55 · auctions/vehicles/liquidation/real-estate interests."""
    targeting: Dict[str, Any] = {
        "geo_locations": {"countries": ["CA"]},
        "age_min": 25,
        "age_max": 55,
    }
    if interest_ids:
        targeting["flexible_spec"] = [{"interests": [{"id": i} for i in interest_ids]}]
    return targeting


def build_meta_creative_payload(campaign_doc: Dict[str, Any], language: str = "en",
                                page_id: Optional[str] = None) -> Dict[str, Any]:
    lang = "fr" if str(language or "").lower().startswith("fr") else "en"
    headline = campaign_doc.get(f"headline_{lang}") or campaign_doc.get("headline_en") or ""
    description = campaign_doc.get(f"description_{lang}") or campaign_doc.get("description_en") or ""
    link = campaign_doc.get("landing_url") or ""
    return {
        "name": f"BidVex {campaign_doc.get('listing_id', '')} ({lang})"[:100],
        "object_story_spec": {
            "page_id": page_id if page_id is not None else os.environ.get("META_PAGE_ID", ""),
            "link_data": {
                "name": headline,
                "message": description,
                "link": link,
                "call_to_action": {"type": "LEARN_MORE", "value": {"link": link}},
            },
        },
    }


# ─── Meta (facebook-business SDK, sync — call via asyncio.to_thread) ────

def _meta_api():
    from facebook_business.api import FacebookAdsApi
    FacebookAdsApi.init(
        os.environ["META_APP_ID"],
        os.environ["META_APP_SECRET"],
        os.environ["META_ACCESS_TOKEN"],
    )


def _resolve_meta_interests() -> List[str]:
    env_ids = [s.strip() for s in os.environ.get("META_INTEREST_IDS", "").split(",") if s.strip()]
    if env_ids:
        return env_ids
    from facebook_business.adobjects.targetingsearch import TargetingSearch
    ids: List[str] = []
    for name in META_INTEREST_NAMES:
        try:
            results = TargetingSearch.search(params={
                "q": name, "type": "adinterest", "limit": 1,
            })
            for r in results:
                ids.append(str(r["id"]))
                break
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[meta-ads] interest search failed for {name!r}: {e}")
    return ids


def list_meta_campaigns_sync() -> List[Dict[str, Any]]:
    from facebook_business.adobjects.adaccount import AdAccount
    _meta_api()
    account = AdAccount(os.environ["META_AD_ACCOUNT_ID"])
    out: List[Dict[str, Any]] = []
    for c in account.get_campaigns(fields=["id", "name", "status", "objective"],
                                   params={"limit": 100}):
        out.append({
            "id": str(c["id"]), "name": c.get("name") or "",
            "status": c.get("status") or "", "objective": c.get("objective") or "",
        })
    return out


def publish_to_meta_sync(campaign_doc: Dict[str, Any],
                         meta_campaign_id: Optional[str] = None,
                         new_campaign_name: Optional[str] = None,
                         language: str = "en") -> Dict[str, Any]:
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.adimage import AdImage
    _meta_api()
    account = AdAccount(os.environ["META_AD_ACCOUNT_ID"])

    # 1. Upload the listing image → hash
    image_hash = None
    img_url = campaign_doc.get("image_url") or ""
    if img_url.startswith("http"):
        import requests
        resp = requests.get(img_url, timeout=25)
        resp.raise_for_status()
        suffix = ".jpg"
        low = img_url.lower().split("?")[0]
        for ext in (".png", ".webp", ".jpeg", ".jpg"):
            if low.endswith(ext):
                suffix = ext
                break
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(resp.content)
                tmp_path = f.name
            img = account.create_ad_image(params={AdImage.Field.filename: tmp_path})
            image_hash = img[AdImage.Field.hash]
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    # 2. Campaign (attach to existing, or create a new PAUSED one)
    if not meta_campaign_id:
        camp = account.create_campaign(params={
            "name": (new_campaign_name or
                     f"BidVex Listings {datetime.now(timezone.utc).date().isoformat()}")[:100],
            "objective": "OUTCOME_TRAFFIC",
            "status": "PAUSED",
            "special_ad_categories": [],
        })
        meta_campaign_id = str(camp["id"])

    # 3. Ad set — Canada, 25-55, interests
    targeting = build_meta_adset_targeting(_resolve_meta_interests())
    adset = account.create_ad_set(params={
        "name": f"BidVex {str(campaign_doc.get('listing_id') or '')[:24]} CA 25-55",
        "campaign_id": meta_campaign_id,
        "daily_budget": int(os.environ.get("META_DAILY_BUDGET_CENTS", "1000")),
        "billing_event": "IMPRESSIONS",
        "optimization_goal": "LINK_CLICKS",
        "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "targeting": targeting,
        "status": "PAUSED",
    })

    # 4. Creative
    creative_payload = build_meta_creative_payload(campaign_doc, language)
    if image_hash:
        creative_payload["object_story_spec"]["link_data"]["image_hash"] = image_hash
    creative = account.create_ad_creative(params=creative_payload)

    # 5. Ad (PAUSED by default — activate in Ads Manager)
    ad_status = os.environ.get("META_AD_STATUS", "PAUSED")
    ad = account.create_ad(params={
        "name": creative_payload["name"],
        "adset_id": str(adset["id"]),
        "creative": {"creative_id": str(creative["id"])},
        "status": ad_status,
    })
    acct_num = os.environ["META_AD_ACCOUNT_ID"].replace("act_", "")
    return {
        "meta_ad_id": str(ad["id"]),
        "meta_adset_id": str(adset["id"]),
        "meta_campaign_id": str(meta_campaign_id),
        "meta_creative_id": str(creative["id"]),
        "image_hash": image_hash,
        "ad_status": ad_status,
        "preview_url": (f"https://business.facebook.com/adsmanager/manage/ads"
                        f"?act={acct_num}&selected_ad_ids={ad['id']}"),
    }


def fetch_meta_insights_sync(ad_id: str) -> Dict[str, Any]:
    from facebook_business.adobjects.ad import Ad
    _meta_api()
    rows = Ad(ad_id).get_insights(fields=["impressions", "clicks", "spend"],
                                  params={"date_preset": "maximum"})
    impressions = clicks = 0
    spend = 0.0
    for r in rows:
        impressions += int(r.get("impressions") or 0)
        clicks += int(r.get("clicks") or 0)
        spend += float(r.get("spend") or 0)
    return {"impressions": impressions, "clicks": clicks, "spend": round(spend, 2)}


# ─── Google Ads (google-ads SDK, sync — call via asyncio.to_thread) ─────

def _google_client():
    from google.ads.googleads.client import GoogleAdsClient
    return GoogleAdsClient.load_from_dict({
        "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        "login_customer_id": os.environ["GOOGLE_ADS_LOGIN_CUSTOMER_ID"].replace("-", ""),
        "use_proto_plus": True,
    })


def _google_customer_id() -> str:
    return os.environ["GOOGLE_ADS_CLIENT_CUSTOMER_ID"].replace("-", "")


def list_google_campaigns_sync() -> List[Dict[str, Any]]:
    client = _google_client()
    ga = client.get_service("GoogleAdsService")
    query = ("SELECT campaign.id, campaign.name, campaign.status FROM campaign "
             "WHERE campaign.status != 'REMOVED' ORDER BY campaign.id")
    out: List[Dict[str, Any]] = []
    for row in ga.search(customer_id=_google_customer_id(), query=query):
        out.append({"id": str(row.campaign.id), "name": row.campaign.name,
                    "status": row.campaign.status.name})
    return out


def list_google_ad_groups_sync(campaign_id: str) -> List[Dict[str, Any]]:
    client = _google_client()
    ga = client.get_service("GoogleAdsService")
    query = (f"SELECT ad_group.id, ad_group.name, ad_group.status, campaign.id "
             f"FROM ad_group WHERE campaign.id = {int(campaign_id)} "
             f"AND ad_group.status != 'REMOVED' ORDER BY ad_group.id")
    out: List[Dict[str, Any]] = []
    for row in ga.search(customer_id=_google_customer_id(), query=query):
        out.append({"id": str(row.ad_group.id), "name": row.ad_group.name,
                    "status": row.ad_group.status.name,
                    "campaign_id": str(row.campaign.id)})
    return out


def create_google_rsa_sync(ad_group_id: str, headlines: List[str],
                           descriptions: List[str], final_url: str) -> Dict[str, Any]:
    client = _google_client()
    svc = client.get_service("AdGroupAdService")
    op = client.get_type("AdGroupAdOperation")
    aga = op.create
    aga.ad_group = client.get_service("AdGroupService").ad_group_path(
        _google_customer_id(), str(int(ad_group_id)))
    aga.status = client.enums.AdGroupAdStatusEnum.PAUSED
    ad = aga.ad
    ad.final_urls.append(final_url)
    for h in headlines[:15]:
        asset = client.get_type("AdTextAsset")
        asset.text = h[:30]
        ad.responsive_search_ad.headlines.append(asset)
    for d in descriptions[:4]:
        asset = client.get_type("AdTextAsset")
        asset.text = d[:90]
        ad.responsive_search_ad.descriptions.append(asset)
    resp = svc.mutate_ad_group_ads(customer_id=_google_customer_id(), operations=[op])
    resource_name = resp.results[0].resource_name
    ad_id = resource_name.rsplit("~", 1)[-1] if "~" in resource_name else resource_name
    return {"google_ad_id": ad_id, "resource_name": resource_name}


def fetch_google_insights_sync(ad_id: str) -> Dict[str, Any]:
    client = _google_client()
    ga = client.get_service("GoogleAdsService")
    query = (f"SELECT metrics.impressions, metrics.clicks, metrics.cost_micros "
             f"FROM ad_group_ad WHERE ad_group_ad.ad.id = {int(ad_id)} "
             f"AND segments.date DURING LAST_30_DAYS")
    impressions = clicks = 0
    cost_micros = 0
    for row in ga.search(customer_id=_google_customer_id(), query=query):
        impressions += int(row.metrics.impressions)
        clicks += int(row.metrics.clicks)
        cost_micros += int(row.metrics.cost_micros)
    return {"impressions": impressions, "clicks": clicks,
            "spend": round(cost_micros / 1_000_000, 2), "window": "last_30_days"}
