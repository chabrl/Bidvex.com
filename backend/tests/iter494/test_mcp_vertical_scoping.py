"""
iter494 — Vertical-scoped listing-creation verification tests.

Regression coverage for the bug where the MCP `create_auction_draft`
tool blocked General Marketplace listings with
`TAX_ID_REQUIRED / dealer_license_not_verified` simply because the
seller's account happened to carry `is_vehicle_dealer=True`.

Business rules being verified:
  * General Marketplace (`vertical="marketplace"`) drafts MUST NOT be
    gated by dealer-license verification, tax_id presence, or facility
    verification. The trust gate (phone/payment method/T&C) is the
    only requirement.
  * Same for `vertical="lots"`.
  * `vertical="vehicle"` still requires the full compliance cascade:
    unverified dealer → 403 TAX_ID_REQUIRED / dealer_license_not_verified.
  * `vertical="storage"` still requires facility verification.
  * `bulk_create_listings` follows the same per-vertical rules and
    only requires tax-id compliance if ANY item is vehicle/storage.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"
MONGO_URL   = os.environ["MONGO_URL"]
DB_NAME     = os.environ["DB_NAME"]
JWT_SECRET  = os.environ["JWT_SECRET"]
JWT_ALG     = os.environ.get("JWT_ALGORITHM", "HS256")


def _mint_jwt(uid: str, email: str) -> str:
    return jwt.encode({"sub": uid, "email": email, "role": "user",
                       "exp": datetime.now(timezone.utc) + timedelta(hours=2)},
                      JWT_SECRET, algorithm=JWT_ALG)


async def _seed_user(db, uid: str, *, trusted: bool = True, dealer: bool = False,
                     license_verified: bool = False, has_tax_id: bool = True,
                     facility: bool = False, facility_verified: bool = False):
    """Seed a user with trust-gate satisfied by default. Uses the exact
    field names read by `services.trust_gate.require_trust_verified`."""
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": uid,
        "email": f"{uid}@bidvex-iter494.test",
        "name": uid,
        "role": "user",
        "account_type": "storage_facility" if facility else "personal",
        "subscription_tier": "premium",
        "subscription_status": "active",
        # trust-gate signals
        "phone_verified": bool(trusted),
        "platform_terms_accepted_at": now if trusted else None,
        # optional flags
        "is_vehicle_dealer": bool(dealer),
        "dealer_license_verified": bool(license_verified),
        "facility_verified": bool(facility_verified),
        "tax_id": "GST123456789" if has_tax_id else "",
        "created_at": now,
    }
    if dealer:
        doc["dealer_subscription_status"] = "active"
        doc["dealer_subscription_active"] = True
    await db.users.replace_one({"id": uid}, doc, upsert=True)
    # Trust gate reads `db.payment_methods` — seed one for trusted users.
    await db.payment_methods.delete_many({"user_id": uid})
    if trusted:
        await db.payment_methods.insert_one({
            "id": str(uuid.uuid4()), "user_id": uid,
            "brand": "visa", "last4": "4242",
            "stripe_payment_method_id": f"pm_iter494_{uid}",
            "created_at": now,
        })


async def _mint_mcp_token(client: httpx.AsyncClient, user_jwt: str,
                          scopes: list[str]) -> str:
    r = await client.post(f"{BACKEND_URL}/api/mcp/token",
        headers={"Authorization": f"Bearer {user_jwt}",
                 "Content-Type": "application/json"},
        json={"label": "iter494", "scopes": scopes, "expires_in_days": 1})
    return r.json()["token"]


@pytest_asyncio.fixture(scope="module")
async def ctx():
    mc = AsyncIOMotorClient(MONGO_URL)
    db = mc[DB_NAME]
    ids = {
        "personal":            f"iter494_pers_{uuid.uuid4().hex[:8]}",
        "dealer_unverified":   f"iter494_dun_{uuid.uuid4().hex[:8]}",
        "dealer_verified":     f"iter494_dv_{uuid.uuid4().hex[:8]}",
        "facility_unverified": f"iter494_fun_{uuid.uuid4().hex[:8]}",
        "facility_verified":   f"iter494_fv_{uuid.uuid4().hex[:8]}",
    }
    # Personal (no dealer flag) with no tax_id — the "individual buyer"
    # case explicitly called out in the PRD.
    await _seed_user(db, ids["personal"], has_tax_id=False)
    # Vehicle dealer with UNVERIFIED licence — this is the exact account
    # shape that reproduced the reported bug.
    await _seed_user(db, ids["dealer_unverified"], dealer=True,
                     license_verified=False, has_tax_id=True)
    # Vehicle dealer with VERIFIED licence.
    await _seed_user(db, ids["dealer_verified"], dealer=True,
                     license_verified=True, has_tax_id=True)
    # Storage facility, unverified.
    await _seed_user(db, ids["facility_unverified"], facility=True,
                     facility_verified=False, has_tax_id=True)
    # Storage facility, verified.
    await _seed_user(db, ids["facility_verified"], facility=True,
                     facility_verified=True, has_tax_id=True)

    async with httpx.AsyncClient(timeout=15.0) as c:
        tokens = {}
        for key, uid in ids.items():
            j = _mint_jwt(uid, f"{uid}@bidvex-iter494.test")
            tokens[key] = await _mint_mcp_token(c, j, ["read", "list"])

    yield {"ids": ids, "tokens": tokens}

    for uid in ids.values():
        await db.users.delete_one({"id": uid})
        await db.mcp_tokens.delete_many({"user_id": uid})
        await db.payment_methods.delete_many({"user_id": uid})
        await db.listings.delete_many({"seller_id": uid})
        await db.multi_item_listings.delete_many({"seller_id": uid})
        await db.vehicles.delete_many({"seller_id": uid})
        await db.storage_units.delete_many({"seller_id": uid})
    mc.close()


async def _call_tool(client: httpx.AsyncClient, tok: str, name: str, arguments: dict):
    return await client.post(f"{BACKEND_URL}/api/mcp/tools/call",
        headers={"Authorization": f"Bearer {tok}",
                 "Content-Type": "application/json"},
        json={"name": name, "arguments": arguments})


# ═══════════════════════════════════════════════════════════════════
# CASE A — General Marketplace: baby-bed listings MUST succeed
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_marketplace_baby_bed_personal_seller_no_tax_id_succeeds(ctx):
    """Individual seller without a tax_id posts a brand-new baby bed —
    must succeed. Reproduces the PRD line 'the individual user not
    obligated to have TAX ID'."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call_tool(c, ctx["tokens"]["personal"],
            "create_auction_draft",
            {"vertical": "marketplace",
             "raw_input": {"title": "Brand new baby bed",
                           "category": "furniture",
                           "condition": "new",
                           "price": 250.00}})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["result"]["vertical"] == "marketplace"
    assert body["result"]["status"] == "draft"


@pytest.mark.asyncio
async def test_marketplace_baby_bed_by_unverified_vehicle_dealer_succeeds(ctx):
    """EXACT bug repro: user is `is_vehicle_dealer=True` +
    `dealer_license_verified=False`, but the listing is a General
    Marketplace baby bed — MUST succeed (dealer-licence gate must not
    fire for the marketplace vertical)."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call_tool(c, ctx["tokens"]["dealer_unverified"],
            "create_auction_draft",
            {"vertical": "marketplace",
             "raw_input": {"title": "Brand new baby bed",
                           "category": "furniture",
                           "condition": "new",
                           "price": 250.00}})
    assert r.status_code == 200, r.text
    assert r.json()["result"]["vertical"] == "marketplace"


@pytest.mark.asyncio
async def test_lots_by_unverified_vehicle_dealer_succeeds(ctx):
    """Multi-item auction (`lots`) by an unverified vehicle dealer —
    also must succeed. Same vertical-scoping rule."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call_tool(c, ctx["tokens"]["dealer_unverified"],
            "create_auction_draft",
            {"vertical": "lots",
             "raw_input": {"title": "Home goods clearance",
                           "items": [{"title": "Chair"}, {"title": "Lamp"}]}})
    assert r.status_code == 200, r.text
    assert r.json()["result"]["vertical"] == "lots"


# ═══════════════════════════════════════════════════════════════════
# CASE B — Vehicle vertical: dealer compliance still enforced
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_vehicle_draft_by_unverified_dealer_still_rejected(ctx):
    """Regression guard for iter482: an unverified vehicle dealer
    trying to draft a vehicle listing MUST STILL be blocked with
    TAX_ID_REQUIRED / dealer_license_not_verified."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call_tool(c, ctx["tokens"]["dealer_unverified"],
            "create_auction_draft",
            {"vertical": "vehicle",
             "raw_input": {"title": "unit test truck", "vin": "TESTVIN123"}})
    # Existing behaviour: 200 wrap with isError=true and structured error
    # in the audit result envelope. Locate the underlying 403 detail.
    if r.status_code == 200:
        result = r.json().get("result", {})
        # The REST /tools/call surface returns the tool result envelope;
        # a rejected write shows up as `rejected` status with the error
        # nested inside. Accept either shape.
        assert result.get("status") in {"rejected", "error"} or result.get("isError") is True, r.text
        err = result.get("error") or {}
        assert (err.get("error") == "TAX_ID_REQUIRED"
                or err.get("detail") == "dealer_license_not_verified"
                or "TAX_ID_REQUIRED" in str(result)), r.text
    else:
        assert r.status_code == 403
        detail = r.json().get("detail") or {}
        assert detail.get("error") == "TAX_ID_REQUIRED"
        assert detail.get("detail") == "dealer_license_not_verified"


@pytest.mark.asyncio
async def test_vehicle_draft_by_verified_dealer_passes_gate(ctx):
    """A verified dealer with tax_id creates a vehicle draft — MUST
    pass the dealer-licence gate (whether the draft insert then
    succeeds depends on downstream validation which we don't touch)."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call_tool(c, ctx["tokens"]["dealer_verified"],
            "create_auction_draft",
            {"vertical": "vehicle",
             "raw_input": {"title": "Verified dealer truck", "vin": "OK1234"}})
    assert r.status_code == 200, r.text
    # Draft insertion succeeded past the gate — that's what we're proving
    result = r.json().get("result", {})
    assert result.get("vertical") == "vehicle"
    assert result.get("status") == "draft"


# ═══════════════════════════════════════════════════════════════════
# CASE C — Storage vertical: facility verification still enforced
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_storage_draft_by_unverified_facility_rejected(ctx):
    """Unverified storage facility trying to draft a storage listing
    — MUST still be rejected."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call_tool(c, ctx["tokens"]["facility_unverified"],
            "create_auction_draft",
            {"vertical": "storage",
             "raw_input": {"title": "unit 42",
                           "size_sqft": 100, "monthly_rent": 199}})
    if r.status_code == 200:
        result = r.json().get("result", {})
        assert result.get("status") in {"rejected", "error"} or result.get("isError") is True
        assert "facility_not_verified" in str(result) or "TAX_ID_REQUIRED" in str(result)
    else:
        assert r.status_code == 403
        detail = r.json().get("detail") or {}
        assert detail.get("error") == "TAX_ID_REQUIRED"


@pytest.mark.asyncio
async def test_storage_draft_by_verified_facility_succeeds(ctx):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call_tool(c, ctx["tokens"]["facility_verified"],
            "create_auction_draft",
            {"vertical": "storage",
             "raw_input": {"title": "unit 42",
                           "size_sqft": 100, "monthly_rent": 199}})
    assert r.status_code == 200, r.text
    assert r.json()["result"]["vertical"] == "storage"


# ═══════════════════════════════════════════════════════════════════
# bulk_create_listings — same rules apply per-item
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_bulk_all_marketplace_by_unverified_dealer_succeeds(ctx):
    """Bulk of ONLY marketplace items should not trigger the
    tax-id / dealer-licence cascade."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call_tool(c, ctx["tokens"]["dealer_unverified"],
            "bulk_create_listings",
            {"items": [
                {"vertical": "marketplace",
                 "raw_input": {"title": "Baby bed", "price": 250}},
                {"vertical": "marketplace",
                 "raw_input": {"title": "Highchair", "price": 100}},
            ]})
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert result["created"] == 2, result


@pytest.mark.asyncio
async def test_bulk_with_any_vehicle_item_by_unverified_dealer_blocked(ctx):
    """If ANY item targets `vertical=vehicle`, the up-front dealer-
    licence cascade fires and the whole batch is rejected — protects
    against partial writes."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call_tool(c, ctx["tokens"]["dealer_unverified"],
            "bulk_create_listings",
            {"items": [
                {"vertical": "marketplace",
                 "raw_input": {"title": "Baby bed", "price": 250}},
                {"vertical": "vehicle",
                 "raw_input": {"title": "Truck", "vin": "X"}},
            ]})
    if r.status_code == 200:
        result = r.json().get("result", {})
        assert result.get("status") in {"rejected", "error"} or result.get("isError") is True
    else:
        assert r.status_code == 403
