"""
iter487 — Regression tests locking in the BidVex platform context
prefix on every MCP tool description.

Guards against:
  1. Accidental removal of the platform prefix from any tool.
  2. Accidental de-labelling of the two stubs (Higgsfield /
     generate_listing_video and Phase 2 / B2B_syndication_matchmaker).
  3. Silent English-only regression: FR descriptions must also carry
     the equivalent French prefix.
  4. Prefix stored somewhere but not actually returned to Claude via
     the JSON-RPC `tools/list` response.

Tokens are minted directly against the backend's JWT_SECRET so the
tests do not exercise the login rate limiter.
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


# Exact prefix strings we must find, byte-for-byte, per iter487 spec.
_EXPECTED_EN_PREFIX = (
    "BidVex is a revolutionary AI-powered auction platform transforming how "
    "assets are bought and sold through intelligent automation, real-time "
    "bidding technology, and a transparent digital marketplace. Sellers keep "
    "100% of the hammer price. Built for vehicle dealers, auctioneers, "
    "storage facilities, liquidators, bankruptcy trustees, municipalities, "
    "and businesses selling assets across Canada, the US, and international "
    "markets. Bilingual EN/FR."
)
_EXPECTED_FR_PREFIX = (
    "BidVex est une plateforme d’enchères révolutionnaire propulsée par "
    "l’intelligence artificielle, qui transforme la façon dont les actifs "
    "sont achetés et vendus grâce à l’automatisation intelligente, aux "
    "enchères en temps réel et à une place de marché numérique transparente. "
    "Les vendeurs conservent 100 % du prix d’adjudication. BidVex est conçue "
    "pour les concessionnaires automobiles, maisons de ventes aux enchères, "
    "installations d’entreposage, liquidateurs, syndics de faillite, "
    "municipalités et entreprises qui vendent des actifs au Canada, aux "
    "États-Unis et sur les marchés internationaux. Bilingue FR/EN."
)


def _mint(user_id: str, email: str, role: str = "user") -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode(
        {"sub": user_id, "email": email, "role": role, "exp": exp},
        JWT_SECRET, algorithm=JWT_ALG,
    )


@pytest_asyncio.fixture(scope="module")
async def premium_and_admin():
    """Seed one premium user + one admin so we can verify prefix
    presence across BOTH the non-admin view (12 tools) and the admin
    view (13 tools including identify_top_sellers)."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()

    users = {
        "premium": {
            "id":                          f"mcp487_p_{uuid.uuid4().hex[:8]}",
            "email":                       f"mcp487_p_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
            "name":                        "MCP487 Premium",
            "role":                        "user",
            "account_type":                "personal",
            "subscription_tier":           "premium",
            "subscription_status":         "active",
            "phone_verified":              True,
            "platform_terms_accepted_at":  now,
            "created_at":                  now,
        },
        "admin": {
            "id":                          f"mcp487_a_{uuid.uuid4().hex[:8]}",
            "email":                       f"mcp487_a_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
            "name":                        "MCP487 Admin",
            "role":                        "super_admin",
            "account_type":                "personal",
            "subscription_tier":           "premium",
            "subscription_status":         "active",
            "phone_verified":              True,
            "platform_terms_accepted_at":  now,
            "created_at":                  now,
        },
    }
    for u in users.values():
        await db.users.insert_one(dict(u))
        u["token"] = _mint(u["id"], u["email"], u.get("role") or "user")
    yield users
    ids = [u["id"] for u in users.values()]
    await db.users.delete_many({"id": {"$in": ids}})
    await db.mcp_audit_logs.delete_many({"user_id": {"$in": ids}})
    client.close()


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─── (1) EN prefix present on every tool returned to Claude ────────
@pytest.mark.asyncio
async def test_all_tools_have_bidvex_platform_prefix_en_via_jsonrpc(premium_and_admin):
    """Every tool returned by the MCP `tools/list` JSON-RPC response
    (i.e. what Claude actually receives) must start with the exact
    English BidVex platform prefix."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post(
            "/api/mcp/rpc",
            headers=_bearer(premium_and_admin["admin"]["token"]),
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "result" in body, body
    tools = body["result"]["tools"]
    # Admin view exposes all 13 tools (including identify_top_sellers)
    assert len(tools) == 13, f"expected 13 tools in admin view, got {len(tools)}"
    for t in tools:
        desc = t["description"]
        assert desc.startswith(_EXPECTED_EN_PREFIX), (
            f"tool '{t['name']}' description does not start with the required "
            f"BidVex EN prefix. First 200 chars: {desc[:200]!r}"
        )
        # Sanity: the tool-specific tail must still be present. The
        # prefix ends with '. ' (space before the tool-specific text)
        # so at minimum the description must be longer than the prefix.
        assert len(desc) > len(_EXPECTED_EN_PREFIX) + 5, (
            f"tool '{t['name']}' has no tool-specific description after prefix"
        )


@pytest.mark.asyncio
async def test_all_tools_have_bidvex_platform_prefix_en_via_legacy_rest(premium_and_admin):
    """Same EN prefix check via the legacy REST endpoint (iter485 back-compat)."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post(
            "/api/mcp/tools/list",
            headers=_bearer(premium_and_admin["admin"]["token"]),
        )
    assert r.status_code == 200
    tools = r.json()["tools"]
    assert len(tools) == 13
    for t in tools:
        # Legacy REST uses `description_en` field name
        assert t["description_en"].startswith(_EXPECTED_EN_PREFIX), (
            f"tool '{t['name']}' legacy REST description_en missing EN prefix"
        )


# ─── (2) FR prefix present on every tool ────────────────────────────
def test_all_tools_have_bidvex_platform_prefix_fr_in_registry():
    """The registry-level `description_fr` must carry the French prefix
    (the FR text is currently server-side only — the MCP JSON-RPC
    `description` field is English, per Claude's expected UX).
    """
    import sys
    sys.path.insert(0, "/app/backend")
    import mcp_server

    for name, spec in mcp_server.TOOL_REGISTRY.items():
        assert spec.description_fr.startswith(_EXPECTED_FR_PREFIX), (
            f"tool '{name}' description_fr does not start with the required "
            f"BidVex FR prefix. First 200 chars: {spec.description_fr[:200]!r}"
        )
        assert len(spec.description_fr) > len(_EXPECTED_FR_PREFIX) + 5, (
            f"tool '{name}' has no tool-specific FR description after prefix"
        )


# ─── (3) Stub labels still correct after the prefix prepend ─────────
@pytest.mark.asyncio
async def test_stubs_still_correctly_labeled(premium_and_admin):
    """Both stub tools MUST still carry their identifying labels in the
    tool-specific portion of the description.

    - generate_listing_video → mentions Higgsfield + NOT_IMPLEMENTED
    - B2B_syndication_matchmaker → mentions Phase 2 + NOT_IMPLEMENTED
    """
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post(
            "/api/mcp/rpc",
            headers=_bearer(premium_and_admin["admin"]["token"]),
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
    tools = {t["name"]: t for t in r.json()["result"]["tools"]}

    higgs = tools.get("generate_listing_video")
    assert higgs is not None, "generate_listing_video missing from tools/list"
    higgs_tail = higgs["description"][len(_EXPECTED_EN_PREFIX):].lower()
    assert "higgsfield" in higgs_tail, "Higgsfield label lost from generate_listing_video"
    assert "not_implemented" in higgs_tail, "NOT_IMPLEMENTED label lost from generate_listing_video"
    assert "stub" in higgs_tail, "STUB label lost from generate_listing_video"

    # iter488 — B2B matchmaker graduated from stub to functional
    # approval-based matchmaker. Description must reflect that it is
    # recommendation + campaign preparation only (no autonomous action).
    b2b = tools.get("B2B_syndication_matchmaker")
    assert b2b is not None, "B2B_syndication_matchmaker missing from tools/list"
    b2b_tail = b2b["description"][len(_EXPECTED_EN_PREFIX):].lower()
    assert "authorised" in b2b_tail or "authorized" in b2b_tail or "approval" in b2b_tail, \
        "Authorisation/approval requirement missing from B2B_syndication_matchmaker description"
    assert "never" in b2b_tail, \
        "'never send/spend/bid' safety guardrail missing from B2B_syndication_matchmaker description"


# ─── (4) EN and FR semantically equivalent (rough sanity, not word-diff) ───
def test_en_and_fr_descriptions_semantically_equivalent_lengths():
    """Sanity: for every tool, the tool-specific portion of the FR
    description is comparable in length to the EN portion (± 3x range).
    Guards against one language being blank or accidentally truncated.
    """
    import sys
    sys.path.insert(0, "/app/backend")
    import mcp_server

    for name, spec in mcp_server.TOOL_REGISTRY.items():
        en_tail = spec.description_en[len(_EXPECTED_EN_PREFIX):].strip()
        fr_tail = spec.description_fr[len(_EXPECTED_FR_PREFIX):].strip()
        assert en_tail, f"{name} has empty EN tool-specific description"
        assert fr_tail, f"{name} has empty FR tool-specific description"
        ratio = len(fr_tail) / max(1, len(en_tail))
        assert 0.3 <= ratio <= 3.0, (
            f"{name} FR/EN length ratio {ratio:.2f} out of sanity range "
            f"(en={len(en_tail)}, fr={len(fr_tail)})"
        )
