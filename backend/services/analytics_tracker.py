"""
iter217 Phase 5 — Meta Conversion API (CAPI) server-side hook.

Implements the server-side Meta "Purchase" event for BidVex broker
transactions.

LEGAL CONSTRAINT (mirrors the broker-fee engine v7 refactor):
    The vehicle hammer price is NEVER sent to Meta as the transaction
    value. BidVex is a marketplace, not a vehicle dealer. The value we
    report is the sum of:
        platform_fee + broker_fee
    in CAD — i.e., the revenue BidVex's Stripe actually processed.
    GST/QST are excluded (taxes are not platform value); Stripe gross-up
    is excluded (it's a pass-through to Stripe, not earned).

User-identifying fields are SHA-256-hashed per Meta's "Customer
Information Parameters" spec before transmission:
    https://developers.facebook.com/docs/marketing-api/conversions-api/parameters/customer-information-parameters

Environment configuration:
    META_PIXEL_ID                ← required
    META_CAPI_ACCESS_TOKEN       ← required
    META_CAPI_TEST_EVENT_CODE    ← optional (sandbox)
    META_CAPI_DISABLE=true       ← kill-switch for emergencies / tests

When the env vars are missing, the function NO-OPs gracefully and writes
a row to `meta_capi_log` so downstream analytics / pytest can still
verify the value math.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

META_API_VERSION = "v19.0"


def _utcnow():
    return datetime.now(timezone.utc)


def _sha256(value: Optional[str]) -> Optional[str]:
    """Lowercase + strip + UTF-8 + SHA-256 hex digest.  Empty / None → None."""
    if value is None:
        return None
    v = str(value).strip().lower()
    if not v:
        return None
    return hashlib.sha256(v.encode("utf-8")).hexdigest()


def _phone_digits(phone: Optional[str]) -> Optional[str]:
    """Strip everything except digits (Meta expects E.164 without symbols)."""
    if not phone:
        return None
    digits = "".join(c for c in str(phone) if c.isdigit())
    return digits or None


def compute_purchase_value_cad(*, platform_fee: float, broker_fee: float) -> float:
    """The only legal Meta value: platform_fee + broker_fee. NEVER hammer."""
    return round(max(0.0, float(platform_fee or 0.0)) + max(0.0, float(broker_fee or 0.0)), 2)


def build_user_data(*,
                    email:        Optional[str] = None,
                    phone:        Optional[str] = None,
                    first_name:   Optional[str] = None,
                    last_name:    Optional[str] = None,
                    city:         Optional[str] = None,
                    state:        Optional[str] = None,
                    country:      Optional[str] = "ca",
                    zip_code:     Optional[str] = None,
                    external_id:  Optional[str] = None,
                    client_ip:    Optional[str] = None,
                    client_ua:    Optional[str] = None,
                    fbp:          Optional[str] = None,
                    fbc:          Optional[str] = None) -> Dict[str, Any]:
    """Hash + assemble the `user_data` block per Meta's spec.

    `client_ip` and `client_ua` are sent in cleartext (Meta hashes them
    server-side) — every other PII field is SHA-256-hashed here.
    """
    out: Dict[str, Any] = {}
    if (em := _sha256(email)):           out["em"]          = [em]
    if (ph := _sha256(_phone_digits(phone))): out["ph"]   = [ph]
    if (fn := _sha256(first_name)):      out["fn"]          = [fn]
    if (ln := _sha256(last_name)):       out["ln"]          = [ln]
    if (ct := _sha256(city)):            out["ct"]          = [ct]
    if (st := _sha256(state)):           out["st"]          = [st]
    if (co := _sha256(country)):         out["country"]     = [co]
    if (zp := _sha256(zip_code)):        out["zp"]          = [zp]
    if (xid := _sha256(external_id)):    out["external_id"] = [xid]
    if client_ip:                        out["client_ip_address"] = client_ip
    if client_ua:                        out["client_user_agent"] = client_ua
    if fbp:                              out["fbp"]         = fbp
    if fbc:                              out["fbc"]         = fbc
    return out


def build_purchase_event(*,
                         platform_fee:  float,
                         broker_fee:    float,
                         user_data:     Dict[str, Any],
                         event_id:      Optional[str] = None,
                         event_source_url: Optional[str] = None,
                         action_source: str = "website",
                         currency:      str = "CAD",
                         content_ids:   Optional[list[str]] = None,
                         content_type:  Optional[str] = None,
                         content_name:  Optional[str] = None,
                         content_category: Optional[str] = None) -> Dict[str, Any]:
    """Build a single Meta CAPI Purchase event payload.

    iter218 — `content_ids` MUST be supplied for catalog match. Format mirrors
    the frontend canonical helper:
        BIDVEX-{MKT|LOT|VEH|STO}-{listing_id}
    Producing this exact string is the only way Meta Commerce Manager can
    attribute the Purchase event to the catalog row.
    """
    value = compute_purchase_value_cad(platform_fee=platform_fee, broker_fee=broker_fee)
    custom_data: Dict[str, Any] = {
        "currency":         currency,
        "value":            value,
        "content_type":     content_type or "product",
        "content_name":     content_name or "BidVex Broker Service Fees",
        "content_category": content_category or "broker_transaction",
    }
    if content_ids:
        custom_data["content_ids"] = content_ids
        # `contents` is required by Meta Advantage+ for full catalog matching.
        custom_data["contents"] = [
            {"id": cid, "quantity": 1, "item_price": value} for cid in content_ids
        ]
        custom_data["num_items"] = len(content_ids)
    return {
        "event_name":     "Purchase",
        "event_time":     int(time.time()),
        "event_id":       event_id or str(uuid.uuid4()),
        "action_source":  action_source,
        "event_source_url": event_source_url or "https://bidvex.com/",
        "user_data":      user_data,
        "custom_data":    custom_data,
    }


# ── Canonical content_id + event_id helpers (mirror frontend) ────────
# Both functions MUST produce identical strings to the frontend's
# `utils/metaContentId.js`. Backend and frontend share these formats so
# Meta dedupes the browser pixel and CAPI events.

_TYPE_PREFIX_MAP = {
    "marketplace":    "MKT",
    "single":         "MKT",
    "product":        "MKT",
    "lots":           "LOT",
    "multi_lot":      "LOT",
    "multi_item":     "LOT",
    "vehicle":        "VEH",
    "vehicles":       "VEH",
    "vehicle_dealer": "VEH",
    "storage":        "STO",
    "storage_locker": "STO",
    "storage_unit":   "STO",
}


def canonical_content_id(listing_type: Optional[str], listing_id: Optional[str]) -> Optional[str]:
    """Returns the canonical Meta content_id for a (listing_type, listing_id).

    iter224 hotfix — Format is now RAW `listing_id` (UUID string). Matches
    `services/meta_feed_mapper.py::_content_id()` and the frontend
    `utils/metaContentId.js::getCanonicalContentId()`. Pixel content_ids and
    catalog item ids MUST be byte-identical (no prefix, no reformatting) per
    Meta + Google Merchant Center matching rules.
    """
    if not listing_id:
        return None
    # `listing_type` arg retained for backwards-compat with callers; ignored.
    return str(listing_id)


def canonical_content_type(listing_type: Optional[str]) -> str:
    """Returns 'vehicle' for vehicle listings, 'product' for everything else.

    Mirrors `utils/metaContentId.js::getCanonicalContentType()`.
    """
    t = (listing_type or "").lower()
    return "vehicle" if t in ("vehicle", "vehicles", "vehicle_dealer") else "product"


def deterministic_event_id(*, event_name: str,
                           content_id: str,
                           discriminator: Optional[str] = None) -> str:
    """Builds the same event_id the frontend would build via
    `metaContentId.js::buildEventId`. Used so the server-side Purchase event
    deduplicates against the browser pixel's Purchase event when Meta receives
    both copies (within the 7-day attribution window).
    """
    parts = ["bidvex", (event_name or "").lower(), content_id]
    if discriminator:
        parts.append(str(discriminator))
    return "_".join(parts).replace(" ", "")



async def _send_to_meta(events: list[Dict[str, Any]]) -> Dict[str, Any]:
    """POST to Meta CAPI. Returns a status dict (does not raise on Meta errors).

    Phase 5.3 — when env vars are missing we no longer just bypass: we run
    the full payload assembly (already done by the caller) and emit a
    structured *server-side log line* with the value, currency and event_id
    so downstream log-pipelines / Sentry / Datadog can still capture
    conversion telemetry until credentials are wired.
    """
    pixel_id = os.environ.get("META_PIXEL_ID")
    access_token = os.environ.get("META_CAPI_ACCESS_TOKEN")
    if (os.environ.get("META_CAPI_DISABLE") or "").lower() == "true":
        # Even when explicitly disabled we still log so analytics replay
        # can reconstruct the funnel.
        _structured_log_fallback(events, reason="disabled_via_env")
        return {"ok": False, "reason": "disabled_via_env"}
    if not pixel_id or not access_token:
        # Graceful structured-log fallback — no longer bypasses the
        # full pipeline. Hashes are already in `events[].user_data`.
        _structured_log_fallback(events, reason="missing_env")
        return {"ok": False, "reason": "missing_env", "fallback": "structured_log"}

    url = f"https://graph.facebook.com/{META_API_VERSION}/{pixel_id}/events"
    payload: Dict[str, Any] = {"data": events}
    if (tc := os.environ.get("META_CAPI_TEST_EVENT_CODE")):
        payload["test_event_code"] = tc

    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url,
                             params={"access_token": access_token},
                             json=payload)
        try:
            body = r.json()
        except Exception:
            body = {"raw": r.text}
        return {"ok": r.status_code == 200, "status_code": r.status_code, "body": body}
    except Exception as e:
        logger.error("[meta_capi] request failed: %s", e, exc_info=True)
        return {"ok": False, "reason": "exception", "error": str(e)}


def _structured_log_fallback(events: list[Dict[str, Any]], *, reason: str) -> None:
    """Phase 5.3 — emit a structured single-line log per event so that even
    without Meta credentials, conversion telemetry is captured in a form
    that log-aggregators / analytics replays can ingest.

    The log line is INFO level, prefixed with `[meta_capi/fallback]`, and
    intentionally omits raw PII (only hashed identifiers are present in
    the event payload anyway, but we double-check by stripping any
    `client_ip_address` / `client_user_agent` before logging).
    """
    for ev in events or []:
        try:
            safe_user_data = dict(ev.get("user_data") or {})
            # Remove cleartext-passthrough fields before logging
            safe_user_data.pop("client_ip_address", None)
            safe_user_data.pop("client_user_agent", None)
            logger.info(
                "[meta_capi/fallback] reason=%s event_name=%s event_id=%s value=%s currency=%s "
                "content_type=%s content_category=%s hashed_user_data_keys=%s",
                reason,
                ev.get("event_name"),
                ev.get("event_id"),
                ev.get("custom_data", {}).get("value"),
                ev.get("custom_data", {}).get("currency"),
                ev.get("custom_data", {}).get("content_type"),
                ev.get("custom_data", {}).get("content_category"),
                ",".join(sorted(safe_user_data.keys())),
            )
        except Exception:
            # Logging must never crash the request path
            continue


async def track_broker_purchase(*,
                                 db,
                                 invoice_id:    str,
                                 platform_fee:  float,
                                 broker_fee:    float,
                                 buyer_user:    Optional[Dict[str, Any]] = None,
                                 client_ip:     Optional[str] = None,
                                 client_ua:     Optional[str] = None,
                                 event_source_url: Optional[str] = None,
                                 fbp:           Optional[str] = None,
                                 fbc:           Optional[str] = None,
                                 listing_id:    Optional[str] = None,
                                 listing_type:  Optional[str] = None,
                                 listing_title: Optional[str] = None,
                                 listing_category: Optional[str] = None) -> Dict[str, Any]:
    """One-call entrypoint to fire a Meta CAPI Purchase event for a broker
    transaction. Persists a row in `meta_capi_log` either way so we have
    a verifiable audit trail (and so tests pass even without env vars).

    LEGAL: never pass `hammer_price` — value is always
    `platform_fee + broker_fee` in CAD.

    iter218 — `listing_id` + `listing_type` are now passed for catalog match.
    When supplied, the event carries content_ids = ["BIDVEX-VEH-<id>"] so
    Meta Commerce Manager can attribute the Purchase to the catalog row.
    """
    user_data: Dict[str, Any] = {}
    if buyer_user:
        full = buyer_user.get("full_name") or buyer_user.get("name") or ""
        parts = full.strip().split()
        first = parts[0] if parts else None
        last  = parts[-1] if len(parts) > 1 else None
        user_data = build_user_data(
            email       = buyer_user.get("email"),
            phone       = buyer_user.get("phone"),
            first_name  = first,
            last_name   = last,
            city        = buyer_user.get("city"),
            state       = buyer_user.get("province") or buyer_user.get("state"),
            country     = (buyer_user.get("country") or "ca"),
            zip_code    = buyer_user.get("postal_code") or buyer_user.get("zip"),
            external_id = buyer_user.get("id"),
            client_ip   = client_ip,
            client_ua   = client_ua,
            fbp         = fbp,
            fbc         = fbc,
        )

    # iter218 — canonical content_id + deterministic event_id for FE↔BE dedup.
    content_id = canonical_content_id(listing_type or "vehicle", listing_id)
    content_ids = [content_id] if content_id else None
    content_type = canonical_content_type(listing_type or "vehicle") if listing_id else None
    # event_id is deterministic per invoice — every retry / replay produces
    # the same event_id, so Meta deduplicates server-side replays.
    event_id = f"broker_invoice_{invoice_id}"

    event = build_purchase_event(
        platform_fee     = platform_fee,
        broker_fee       = broker_fee,
        user_data        = user_data,
        event_id         = event_id,
        event_source_url = event_source_url,
        content_ids      = content_ids,
        content_type     = content_type,
        content_name     = listing_title or ("BidVex Broker Service Fees" if not content_id else None),
        content_category = listing_category or ("broker_transaction" if not content_id else None),
    )
    value = event["custom_data"]["value"]

    delivery = await _send_to_meta([event])

    try:
        await db.meta_capi_log.insert_one({
            "id":             str(uuid.uuid4()),
            "invoice_id":     invoice_id,
            "event_name":     "Purchase",
            "event_id":       event["event_id"],
            "value_cad":      value,
            "currency":       "CAD",
            "content_ids":    content_ids or [],
            "content_type":   content_type,
            "listing_id":     listing_id,
            "listing_type":   listing_type,
            "delivery":       delivery,
            "had_user_data":  bool(user_data),
            "at":             _utcnow(),
        })
    except Exception as e:
        logger.warning("[meta_capi] audit insert failed: %s", e)

    return {"event_id": event["event_id"], "value_cad": value, "delivery": delivery, "content_ids": content_ids}


async def track_listing_purchase(*,
                                  db,
                                  session_id:   str,
                                  listing_id:   str,
                                  listing_type: str,
                                  total_charged: float,
                                  buyer_user:   Optional[Dict[str, Any]] = None,
                                  client_ip:    Optional[str] = None,
                                  client_ua:    Optional[str] = None,
                                  event_source_url: Optional[str] = None,
                                  listing_title: Optional[str] = None,
                                  listing_category: Optional[str] = None,
                                  fbp:          Optional[str] = None,
                                  fbc:          Optional[str] = None) -> Dict[str, Any]:
    """Fires Meta CAPI Purchase for a non-broker checkout (marketplace,
    multi-lot, storage). `event_id` is deterministic based on the Stripe
    `session_id` so the browser-side pixel can be deduplicated.

    For BidVex revenue accounting this passes the buyer's TOTAL charged
    amount (gross) as the Meta value — Meta's catalog attribution model
    uses gross as the conversion value for non-broker SKUs.
    """
    user_data: Dict[str, Any] = {}
    if buyer_user:
        full = buyer_user.get("full_name") or buyer_user.get("name") or ""
        parts = full.strip().split()
        first = parts[0] if parts else None
        last  = parts[-1] if len(parts) > 1 else None
        user_data = build_user_data(
            email       = buyer_user.get("email"),
            phone       = buyer_user.get("phone"),
            first_name  = first,
            last_name   = last,
            city        = buyer_user.get("city"),
            state       = buyer_user.get("province") or buyer_user.get("state"),
            country     = (buyer_user.get("country") or "ca"),
            zip_code    = buyer_user.get("postal_code") or buyer_user.get("zip"),
            external_id = buyer_user.get("id"),
            client_ip   = client_ip,
            client_ua   = client_ua,
            fbp         = fbp,
            fbc         = fbc,
        )

    content_id = canonical_content_id(listing_type, listing_id)
    if not content_id:
        return {"ok": False, "reason": "missing_content_id"}
    content_ids = [content_id]
    content_type = canonical_content_type(listing_type)

    # Deterministic event_id matches the format used by the frontend
    # `metaContentId.js::buildEventId` (eventName=Purchase, contentId,
    # discriminator=session_id). This is the dedup key Meta uses to merge
    # the browser-side pixel + server-side CAPI Purchase.
    event_id = deterministic_event_id(
        event_name="Purchase",
        content_id=content_id,
        discriminator=f"session_{session_id}",
    )

    value = round(float(total_charged or 0.0), 2)
    event = {
        "event_name":       "Purchase",
        "event_time":       int(time.time()),
        "event_id":         event_id,
        "action_source":    "website",
        "event_source_url": event_source_url or "https://bidvex.com/",
        "user_data":        user_data,
        "custom_data": {
            "currency":         "CAD",
            "value":            value,
            "content_ids":      content_ids,
            "content_type":     content_type,
            "content_name":     listing_title or "",
            "content_category": listing_category or "",
            "contents": [{"id": content_id, "quantity": 1, "item_price": value}],
            "num_items":        1,
        },
    }
    delivery = await _send_to_meta([event])
    try:
        await db.meta_capi_log.insert_one({
            "id":             str(uuid.uuid4()),
            "session_id":     session_id,
            "event_name":     "Purchase",
            "event_id":       event_id,
            "value_cad":      value,
            "currency":       "CAD",
            "content_ids":    content_ids,
            "content_type":   content_type,
            "listing_id":     listing_id,
            "listing_type":   listing_type,
            "delivery":       delivery,
            "had_user_data":  bool(user_data),
            "at":             _utcnow(),
        })
    except Exception as e:
        logger.warning("[meta_capi] listing-purchase audit insert failed: %s", e)
    return {
        "event_id":    event_id,
        "value_cad":   value,
        "content_ids": content_ids,
        "delivery":    delivery,
    }
