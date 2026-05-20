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
                         currency:      str = "CAD") -> Dict[str, Any]:
    """Build a single Meta CAPI Purchase event payload."""
    value = compute_purchase_value_cad(platform_fee=platform_fee, broker_fee=broker_fee)
    return {
        "event_name":     "Purchase",
        "event_time":     int(time.time()),
        "event_id":       event_id or str(uuid.uuid4()),
        "action_source":  action_source,
        "event_source_url": event_source_url or "https://bidvex.com/",
        "user_data":      user_data,
        "custom_data": {
            "currency":     currency,
            "value":        value,
            "content_type": "product",
            "content_name": "BidVex Broker Service Fees",
            "content_category": "broker_transaction",
        },
    }


async def _send_to_meta(events: list[Dict[str, Any]]) -> Dict[str, Any]:
    """POST to Meta CAPI. Returns a status dict (does not raise on Meta errors)."""
    pixel_id = os.environ.get("META_PIXEL_ID")
    access_token = os.environ.get("META_CAPI_ACCESS_TOKEN")
    if (os.environ.get("META_CAPI_DISABLE") or "").lower() == "true":
        return {"ok": False, "reason": "disabled_via_env"}
    if not pixel_id or not access_token:
        return {"ok": False, "reason": "missing_env"}

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
                                 fbc:           Optional[str] = None) -> Dict[str, Any]:
    """One-call entrypoint to fire a Meta CAPI Purchase event for a broker
    transaction. Persists a row in `meta_capi_log` either way so we have
    a verifiable audit trail (and so tests pass even without env vars).

    LEGAL: never pass `hammer_price` — value is always
    `platform_fee + broker_fee` in CAD.
    """
    user_data: Dict[str, Any] = {}
    if buyer_user:
        # Split full name → first / last for hashing
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

    event = build_purchase_event(
        platform_fee     = platform_fee,
        broker_fee       = broker_fee,
        user_data        = user_data,
        event_id         = f"broker_invoice_{invoice_id}",
        event_source_url = event_source_url,
    )
    value = event["custom_data"]["value"]

    delivery = await _send_to_meta([event])

    # Persist audit row — same payload, but never re-emit user_data hashes
    # (they're irreversible but writing them all to disk is overkill).
    try:
        await db.meta_capi_log.insert_one({
            "id":           str(uuid.uuid4()),
            "invoice_id":   invoice_id,
            "event_name":   "Purchase",
            "event_id":     event["event_id"],
            "value_cad":    value,
            "currency":     "CAD",
            "delivery":     delivery,
            "had_user_data": bool(user_data),
            "at":           _utcnow(),
        })
    except Exception as e:
        logger.warning("[meta_capi] audit insert failed: %s", e)

    return {"event_id": event["event_id"], "value_cad": value, "delivery": delivery}
