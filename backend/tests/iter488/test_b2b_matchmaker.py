"""
iter488 — B2B Matchmaker Phase 2 regression tests.

Coverage:
  * Manifest parser — valid, malformed, missing fields.
  * Vehicle / equipment / storage / lot normalisation.
  * Buyer clustering — segments identified from user profile.
  * Match scoring — vertical / category / geography / price / quantity.
  * Match explanation — every score carries reasons.
  * Campaign generation — EN + FR (natural, non-identical, non-concatenated).
  * Safety — no autonomous email/spend/bid; approval required.
  * PII protection — no buyer email/phone in output.
  * MCP integration — tools/list, tools/call, subscription gate, audit.
"""
from __future__ import annotations

import asyncio
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


def _mint(user_id: str, email: str, role: str = "user") -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode(
        {"sub": user_id, "email": email, "role": role, "exp": exp},
        JWT_SECRET, algorithm=JWT_ALG,
    )


@pytest_asyncio.fixture(scope="module")
async def seeded_b2b():
    """Seed a premium seller with a diverse manifest + a set of qualified
    B2B buyer profiles."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()

    seller_id = f"iter488b2b_sel_{uuid.uuid4().hex[:8]}"
    seller = {
        "id":                  seller_id,
        "email":               f"{seller_id}@bidvex-mcp.test",
        "name":                "iter488 B2B Seller",
        "role":                "user",
        "account_type":        "personal",
        "subscription_tier":   "premium",
        "subscription_status": "active",
        "phone_verified":      True,
        "created_at":          now,
    }
    await db.users.replace_one({"id": seller_id}, seller, upsert=True)

    # Diverse manifest across all five collections
    listing_docs = [
        # Marketplace listing
        {"id": f"iter488b2b_ml_{uuid.uuid4().hex[:8]}", "seller_id": seller_id,
         "title": "Steel Beams 20T Lot", "category": "industrial",
         "current_price": 12500.0, "quantity": 20, "location": "QC Montreal",
         "condition": "good", "status": "active", "created_at": now},
        # Multi-item lot
        {"id": f"iter488b2b_lot_{uuid.uuid4().hex[:8]}", "seller_id": seller_id,
         "title": "Warehouse Liquidation Lot", "category": "wholesale",
         "current_price": 8000.0, "quantity": 150, "location": "ON Toronto",
         "condition": "used", "status": "active", "created_at": now},
        # Vehicle
        {"id": f"iter488b2b_veh_{uuid.uuid4().hex[:8]}", "seller_id": seller_id,
         "title": "2018 Ford F-150 Fleet Truck", "category": "trucks",
         "make": "Ford", "model": "F-150", "year": 2018,
         "current_bid": 22000.0, "location": "QC Longueuil",
         "condition": "good", "status": "active", "created_at": now},
        # Storage
        {"id": f"iter488b2b_sto_{uuid.uuid4().hex[:8]}", "seller_id": seller_id,
         "title": "Storage Unit 12x24 Abandoned",
         "current_bid": 350.0, "location": "QC Laval",
         "status": "active", "created_at": now},
        # Malformed — missing critical fields (no title, no price)
        {"id": f"iter488b2b_bad_{uuid.uuid4().hex[:8]}", "seller_id": seller_id,
         "status": "active", "created_at": now},
    ]
    await db.listings.insert_one(listing_docs[0])
    await db.multi_item_listings.insert_one(listing_docs[1])
    await db.vehicles.insert_one(listing_docs[2])
    await db.storage_units.insert_one(listing_docs[3])
    # Insert the malformed doc alongside a real collection so the parser
    # exercises the "missing critical field" path.
    await db.listings.insert_one(listing_docs[4])

    # Qualified buyer profiles across every segment
    buyers = [
        {
            "id": f"iter488b2b_dealer_{uuid.uuid4().hex[:8]}",
            "email": "dealer@iter488b2b.test",
            "name": "Ford Dealer Rep",
            "role": "user",
            "account_type": "personal",
            "is_vehicle_dealer": True,
            "vehicle_dealer_verified": True,
            "subscription_tier": "premium",
            "subscription_status": "active",
            "business_name": "AutoMax Dealers Inc.",
            "province": "QC",
            "buyer_preferences": {
                "categories":  ["trucks", "vans"],
                "verticals":   ["vehicle"],
                "provinces":   ["QC"],
                "min_price":   5000,
                "max_price":   50000,
            },
            "created_at": now,
        },
        {
            "id": f"iter488b2b_broker_{uuid.uuid4().hex[:8]}",
            "email": "broker@iter488b2b.test",
            "name": "Industrial Broker",
            "role": "user",
            "account_type": "broker",
            "subscription_tier": "partner_pro",
            "subscription_status": "active",
            "admin_verified": True,
            "business_name": "Global Broker Services",
            "province": "QC",
            "buyer_preferences": {
                "categories":  ["industrial", "wholesale"],
                "verticals":   ["marketplace", "lots"],
                "provinces":   ["QC", "ON"],
                "min_price":   1000,
                "max_price":   100000,
                "min_quantity": 10,
            },
            "created_at": now,
        },
        {
            "id": f"iter488b2b_facility_{uuid.uuid4().hex[:8]}",
            "email": "facility@iter488b2b.test",
            "name": "Storage Facility Op",
            "role": "user",
            "account_type": "storage_facility",
            "facility_verified": True,
            "subscription_tier": "premium",
            "subscription_status": "active",
            "business_name": "Nord Storage Corp.",
            "province": "QC",
            "buyer_preferences": {"verticals": ["storage"], "provinces": ["QC"]},
            "created_at": now,
        },
    ]
    for b in buyers:
        await db.users.replace_one({"id": b["id"]}, b, upsert=True)

    yield {
        "seller_id": seller_id,
        "seller_jwt": _mint(seller_id, seller["email"]),
        "buyers": {b["email"]: b["id"] for b in buyers},
        "listings": [d["id"] for d in listing_docs],
    }

    # Cleanup
    await db.users.delete_one({"id": seller_id})
    for b in buyers:
        await db.users.delete_one({"id": b["id"]})
    for d in listing_docs:
        await db.listings.delete_one({"id": d["id"]})
        await db.multi_item_listings.delete_one({"id": d["id"]})
        await db.vehicles.delete_one({"id": d["id"]})
        await db.storage_units.delete_one({"id": d["id"]})
    client.close()


# ═══════════════════════════════════════════════════════════════════
# 1) MANIFEST PARSER
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_manifest_parses_all_verticals(seeded_b2b):
    from services.b2b_matchmaker import parse_seller_manifest
    mc = AsyncIOMotorClient(MONGO_URL)
    db = mc[DB_NAME]
    manifest = await parse_seller_manifest(db, seeded_b2b["seller_id"])
    mc.close()
    verticals = {i["vertical"] for i in manifest["items"]}
    assert {"marketplace", "lots", "vehicle", "storage"} <= verticals
    # Malformed row should surface in `malformed`
    assert any("missing_fields" in m["reason"] for m in manifest["malformed"])


@pytest.mark.asyncio
async def test_manifest_never_fabricates_missing_fields(seeded_b2b):
    from services.b2b_matchmaker import parse_seller_manifest
    mc = AsyncIOMotorClient(MONGO_URL)
    manifest = await parse_seller_manifest(mc[DB_NAME], seeded_b2b["seller_id"])
    mc.close()
    for item in manifest["items"]:
        if not item["_is_complete"]:
            # Missing fields must be None, not fabricated values
            for f in item["_missing_fields"]:
                assert item.get(f) is None


@pytest.mark.asyncio
async def test_manifest_vehicle_normalisation(seeded_b2b):
    from services.b2b_matchmaker import parse_seller_manifest
    mc = AsyncIOMotorClient(MONGO_URL)
    manifest = await parse_seller_manifest(mc[DB_NAME], seeded_b2b["seller_id"])
    mc.close()
    veh = next(i for i in manifest["items"] if i["vertical"] == "vehicle")
    assert veh["make"] == "Ford"
    assert veh["model"] == "F-150"
    assert veh["year"] == 2018
    assert veh["price"] == 22000.0


# ═══════════════════════════════════════════════════════════════════
# 2) BUYER CLUSTERING
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_qualified_buyers_include_all_segments(seeded_b2b):
    from services.b2b_matchmaker import identify_qualified_buyers
    mc = AsyncIOMotorClient(MONGO_URL)
    buyers = await identify_qualified_buyers(mc[DB_NAME])
    mc.close()
    segments = {b["segment"] for b in buyers}
    assert {"vehicle_dealer", "broker", "storage_facility"} <= segments


@pytest.mark.asyncio
async def test_qualified_buyer_pii_not_exposed(seeded_b2b):
    from services.b2b_matchmaker import identify_qualified_buyers
    mc = AsyncIOMotorClient(MONGO_URL)
    buyers = await identify_qualified_buyers(mc[DB_NAME])
    mc.close()
    # Only user_id + business_name + segment + non-PII signals allowed
    for b in buyers:
        assert "email" not in b
        assert "phone" not in b
        assert "phone_number" not in b
        # signals must be non-PII buckets only
        for k in (b.get("signals") or {}):
            assert k in {"categories", "verticals", "provinces", "min_price",
                         "max_price", "min_quantity", "condition_preference"}


# ═══════════════════════════════════════════════════════════════════
# 3) MATCH SCORING + EXPLANATIONS
# ═══════════════════════════════════════════════════════════════════
def test_score_match_vertical():
    from services.b2b_matchmaker import score_match
    item = {"vertical": "vehicle", "asset_type": "vehicle", "category": "trucks",
            "location": "QC", "price": 22000, "quantity": 1, "condition": "good"}
    buyer = {"segment": "vehicle_dealer",
             "signals": {"verticals": ["vehicle"], "categories": ["trucks"],
                         "provinces": ["QC"], "min_price": 5000, "max_price": 50000}}
    r = score_match(item, buyer)
    assert r["score"] >= 60
    assert "vertical_match:vehicle" in r["reasons"]
    assert "category_match:trucks" in r["reasons"]
    assert "geography_match" in r["reasons"]
    assert "price_range_match" in r["reasons"]


def test_score_match_out_of_price_range():
    from services.b2b_matchmaker import score_match
    item = {"vertical": "vehicle", "category": "trucks", "price": 100000, "quantity": 1}
    buyer = {"segment": "vehicle_dealer",
             "signals": {"verticals": ["vehicle"], "categories": ["trucks"],
                         "min_price": 5000, "max_price": 50000}}
    r = score_match(item, buyer)
    assert "price_range_match" not in r["reasons"]


def test_score_match_quantity_dimension():
    from services.b2b_matchmaker import score_match
    item = {"vertical": "marketplace", "category": "industrial", "price": 5000, "quantity": 50}
    buyer = {"segment": "broker",
             "signals": {"verticals": ["marketplace"], "categories": ["industrial"],
                         "min_quantity": 10}}
    r = score_match(item, buyer)
    assert "quantity_match" in r["reasons"]


def test_score_match_reasons_are_explainable():
    from services.b2b_matchmaker import score_match
    item = {"vertical": "storage", "location": "QC Laval", "price": 350, "quantity": 1}
    buyer = {"segment": "storage_facility",
             "signals": {"verticals": ["storage"], "provinces": ["QC"]}}
    r = score_match(item, buyer)
    assert r["score"] > 0
    assert len(r["reasons"]) >= 1
    for reason in r["reasons"]:
        assert isinstance(reason, str) and ":" in reason or reason in {
            "geography_match", "price_range_match", "quantity_match",
            "historical_bidding_in_category", "condition_match",
        }


# ═══════════════════════════════════════════════════════════════════
# 4) CAMPAIGN GENERATION (BILINGUAL)
# ═══════════════════════════════════════════════════════════════════
def test_campaign_generation_bilingual():
    from services.b2b_matchmaker import draft_bilingual_campaign
    match = {
        "buyer": {"user_id": "u1", "business_name": "Test Co", "segment": "vehicle_dealer"},
        "items": [{"listing_id": "L1", "title": "2018 Ford F-150", "category": "trucks",
                   "price": 22000, "score": 75, "reasons": ["vertical_match:vehicle"]}],
        "top_score": 75,
    }
    c = draft_bilingual_campaign(match)
    assert "en" in c and "fr" in c
    assert c["en"]["subject"] and c["fr"]["subject"]
    assert c["en"]["message"] and c["fr"]["message"]
    # Must not be mechanical concatenation
    assert c["en"]["message"] != c["fr"]["message"]
    # EN and FR must not be identical to each other or empty
    assert "BidVex" in c["en"]["message"]
    assert "BidVex" in c["fr"]["message"] or "acheteur" in c["fr"]["message"] or "vendeur" in c["fr"]["message"]
    # French must contain FR-specific tokens (not just English text)
    fr_msg = c["fr"]["message"].lower()
    assert any(w in fr_msg for w in ["bonjour", "cordialement", "l'équipe", "pertinence"])
    en_msg = c["en"]["message"].lower()
    assert any(w in en_msg for w in ["hello", "best regards", "the bidvex team", "match"])
    assert c["status"] == "draft_awaiting_approval"


def test_campaign_lists_all_matched_listings():
    from services.b2b_matchmaker import draft_bilingual_campaign
    match = {
        "buyer": {"user_id": "u1", "business_name": "Multi Co", "segment": "broker"},
        "items": [
            {"listing_id": "L1", "title": "Lot A", "category": "industrial", "price": 1000, "score": 70, "reasons": []},
            {"listing_id": "L2", "title": "Lot B", "category": "industrial", "price": 2000, "score": 65, "reasons": []},
            {"listing_id": "L3", "title": "Lot C", "category": "industrial", "price": 3000, "score": 60, "reasons": []},
        ],
        "top_score": 70,
    }
    c = draft_bilingual_campaign(match)
    assert set(c["listing_refs"]) == {"L1", "L2", "L3"}
    assert "Lot A" in c["en"]["message"] and "Lot B" in c["en"]["message"] and "Lot C" in c["en"]["message"]
    assert "Lot A" in c["fr"]["message"] and "Lot B" in c["fr"]["message"] and "Lot C" in c["fr"]["message"]


# ═══════════════════════════════════════════════════════════════════
# 5) SAFETY — APPROVAL REQUIRED, NO AUTONOMOUS ACTION
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_run_matchmaker_does_not_send_or_spend(seeded_b2b):
    from services.b2b_matchmaker import run_matchmaker
    mc = AsyncIOMotorClient(MONGO_URL)
    result = await run_matchmaker(mc[DB_NAME], seller_id=seeded_b2b["seller_id"])
    mc.close()
    assert result["status"] == "drafts_ready"
    assert result["approval_required"] is True
    # None of the campaigns are marked as sent/dispatched
    for c in result["campaigns"]:
        assert c["status"] == "draft_awaiting_approval"


@pytest.mark.asyncio
async def test_authorise_without_explicit_flag_no_action(seeded_b2b):
    from services.b2b_matchmaker import authorised_execute_campaign
    mc = AsyncIOMotorClient(MONGO_URL)
    r = await authorised_execute_campaign(
        mc[DB_NAME],
        campaign_id="camp_test1",
        actor_user_id=seeded_b2b["seller_id"],
        seller_id=seeded_b2b["seller_id"],
        explicit_authorization=False,
    )
    mc.close()
    assert r["status"] == "approval_required"


@pytest.mark.asyncio
async def test_authorise_records_but_does_not_dispatch(seeded_b2b):
    from services.b2b_matchmaker import authorised_execute_campaign
    mc = AsyncIOMotorClient(MONGO_URL)
    r = await authorised_execute_campaign(
        mc[DB_NAME],
        campaign_id="camp_test2",
        actor_user_id=seeded_b2b["seller_id"],
        seller_id=seeded_b2b["seller_id"],
        explicit_authorization=True,
    )
    # Even after explicit authorisation, we NEVER auto-dispatch.
    assert r["status"] == "authorized_pending_dispatch"
    assert r["dispatched"] is False
    # Audit row present in the collection
    row = await mc[DB_NAME]["b2b_matchmaker_authorisations"].find_one({"campaign_id": "camp_test2"})
    mc.close()
    assert row is not None and row["dispatched"] is False


# ═══════════════════════════════════════════════════════════════════
# 6) MCP INTEGRATION
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_mcp_tools_list_exposes_matchmaker(seeded_b2b):
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{BACKEND_URL}/api/mcp/tools/list",
            headers={"Authorization": f"Bearer {seeded_b2b['seller_jwt']}"},
        )
    names = {t["name"] for t in r.json()["tools"]}
    assert "B2B_syndication_matchmaker" in names
    spec = next(t for t in r.json()["tools"] if t["name"] == "B2B_syndication_matchmaker")
    # Description mentions approval requirement
    desc = spec["description_en"].lower()
    assert "authorised" in desc or "authorized" in desc or "approval" in desc
    assert "will never" in desc or "will not" in desc or "never" in desc


@pytest.mark.asyncio
async def test_mcp_matchmaker_analyze_via_tools_call(seeded_b2b):
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{BACKEND_URL}/api/mcp/tools/call",
            headers={"Authorization": f"Bearer {seeded_b2b['seller_jwt']}", "Content-Type": "application/json"},
            json={"name": "B2B_syndication_matchmaker",
                  "arguments": {"action": "analyze", "min_score": 20, "max_matches": 5}},
        )
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert result["status"] == "drafts_ready"
    assert result["approval_required"] is True
    assert result["match_count"] >= 1
    # Campaigns have both EN and FR
    if result["campaigns"]:
        c0 = result["campaigns"][0]
        assert c0["en"]["message"] and c0["fr"]["message"]


@pytest.mark.asyncio
async def test_mcp_matchmaker_blocks_cross_seller(seeded_b2b):
    """Non-admin cannot run matchmaker on someone else's inventory."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{BACKEND_URL}/api/mcp/tools/call",
            headers={"Authorization": f"Bearer {seeded_b2b['seller_jwt']}", "Content-Type": "application/json"},
            json={"name": "B2B_syndication_matchmaker",
                  "arguments": {"action": "analyze", "seller_id": "someone-else-id"}},
        )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_mcp_matchmaker_authorise_via_mcp(seeded_b2b):
    """Approval via MCP tool call must record the intent but never
    dispatch."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{BACKEND_URL}/api/mcp/tools/call",
            headers={"Authorization": f"Bearer {seeded_b2b['seller_jwt']}", "Content-Type": "application/json"},
            json={"name": "B2B_syndication_matchmaker",
                  "arguments": {"action": "authorise", "campaign_id": "camp_via_mcp",
                                "explicit_authorization": True}},
        )
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["status"] == "authorized_pending_dispatch"
    assert result["dispatched"] is False


@pytest.mark.asyncio
async def test_mcp_matchmaker_audit_row_written(seeded_b2b):
    """The audit-log sanitiser must record the matchmaker call without
    leaking any secret."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(
            f"{BACKEND_URL}/api/mcp/tools/call",
            headers={"Authorization": f"Bearer {seeded_b2b['seller_jwt']}", "Content-Type": "application/json"},
            json={"name": "B2B_syndication_matchmaker", "arguments": {"action": "analyze"}},
        )
    mc = AsyncIOMotorClient(MONGO_URL)
    rows = await mc[DB_NAME].mcp_audit_logs.find(
        {"user_id": seeded_b2b["seller_id"], "tool_name": "B2B_syndication_matchmaker"},
    ).sort("timestamp", -1).limit(5).to_list(5)
    mc.close()
    assert rows, "audit row must be written for matchmaker calls"
    latest = rows[0]
    assert latest["result_status"] == "success"
    # Nothing sensitive should leak into input_params
    ip_str = str(latest.get("input_params") or {})
    assert "password" not in ip_str.lower()
    assert "jwt" not in ip_str.lower()
