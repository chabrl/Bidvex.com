"""
iter469 — Reproduce the escrow pickup-confirmation failure for paid
non-vehicle orders whose paid transaction row has NO escrow_transactions
row.

Bug hypothesis (from code trace):
  - `services/payment_collection.finalize_auction_payment` (SUCCESS path)
    writes a `transactions` row with a `pickup_code` and stamps the
    listing, but does NOT create an `escrow_transactions` row.
  - Only the webhook `routes/webhooks._handle_auction_payment_success`
    (payment_intent.succeeded → non-vehicle → seller_id set → no
    auto-transfer) creates `escrow_transactions`.
  - The seller dashboard `GET /api/escrow/seller/status`
    (`services/escrow_service.get_seller_escrow_status`) UNIONS both
    collections — so a `transactions`-only paid order shows as
    "Funds Held".
  - `POST /api/escrow/seller/confirm-pickup`
    (`services/escrow_service.confirm_pickup`) reads ONLY
    `escrow_transactions` where `escrow_status="held"`. For a
    `transactions`-only row it returns 404 "escrow_not_found" even
    though the exact same order is on the dashboard.

This reproduction seeds ONE removable auction that mirrors the
`finalize_auction_payment` success path (writes ONLY a transactions
row with a pickup_code) and calls the running preview backend HTTP
API to confirm the failure end-to-end.

All records are prefixed `iter469-*` and cleaned up on exit.
Guardrails:
  - No production data touched
  - No Stripe transfers created
  - No funds released
  - No emails sent to real users (all recipients are fictional
    `iter469-*@test.example`)
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make backend importable
BACKEND = Path("/app/backend")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # type: ignore
load_dotenv(BACKEND / ".env")
load_dotenv(Path("/app/frontend/.env"), override=False)

import httpx  # type: ignore
from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
from passlib.context import CryptContext  # type: ignore
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL") or "https://prod-verify-2.preview.emergentagent.com"
API = f"{BACKEND_URL.rstrip('/')}/api"

# Token used to sign the seller access token (must match server's SECRET_KEY).
# We do NOT need to bypass login for the reproduction — we use the running
# preview backend's /api/auth/login endpoint.

def _password_response_token(json_body: dict):
    return json_body.get("access_token") or json_body.get("token")

PREFIX = "iter469-"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _mint_seller_and_login(db, client: httpx.AsyncClient, tag: str) -> dict:
    """Create a fresh removable seller user and return {id, email, token}."""
    tag_lower = tag.lower()
    email = f"{PREFIX}seller-{tag_lower}-{uuid.uuid4().hex[:6]}@test.example"
    password = "IterFourSixNine!"
    seller_id = f"{PREFIX}seller-{tag_lower}-{uuid.uuid4().hex[:8]}"

    await db.users.insert_one({
        "id": seller_id,
        "email": email,
        "password": _pwd_ctx.hash(password),
        "name": f"iter469 seller {tag}",
        "role": "user",
        "account_type": "individual",
        "phone_verified": True,
        "email_verified": True,
        "id_verified": True,
        "created_at": now_iso(),
        "iter469_seed": True,
    })

    # Sanity: read back to confirm the doc is in the DB before login.
    _check = await db.users.find_one({"email": email}, {"_id": 0, "id": 1, "email": 1, "status": 1, "password": 1})
    print(f"[iter469][DEBUG] seeded user id={_check.get('id')!r} email={_check.get('email')!r} status={_check.get('status')!r} pw_prefix={(_check.get('password') or '')[:10]!r}")
    # Small delay in case of replica lag
    await asyncio.sleep(1.0)

    r = await client.post(f"{API}/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        print(f"[iter469][DEBUG] login {r.status_code}: {r.text[:400]}")
    r.raise_for_status()
    body = r.json()
    token = _password_response_token(body)
    assert token, f"login failed: {r.text}"
    return {"id": seller_id, "email": email, "token": token}


async def _seed_transactions_only_paid_order(
    db, *, seller_id: str, buyer_id: str, listing_id: str, hammer: float,
    pickup_code: str, lot_number=None,
) -> str:
    """Emulate `_ensure_stripe_pickup_code` — writes a transactions row
    with pickup_code + commission_already_collected. NO escrow_transactions
    row (that is the bug we want to reproduce)."""
    txn_id = str(uuid.uuid4())
    await db.transactions.insert_one({
        "id": txn_id,
        "listing_id": listing_id,
        "pickup_code_listing_id": listing_id,
        "auction_id": listing_id,
        "lot_number": lot_number,
        "listing_title": f"iter469 test lot {lot_number or ''}".strip(),
        "buyer_id": buyer_id,
        "buyer_email": f"{PREFIX}buyer@test.example",
        "seller_id": seller_id,
        "seller_email": f"{PREFIX}seller-mail@test.example",
        "pickup_code_seller_id": seller_id,
        "hammer_price": hammer,
        "amount": hammer,
        "payment_method": "stripe",
        "stripe_payment_intent": f"pi_iter469_{uuid.uuid4().hex[:8]}",
        "status": "paid",
        "payment_confirmed": True,
        "commission_already_collected": True,
        "pickup_code": pickup_code,
        "pickup_code_issued_at": now_iso(),
        "created_at": now_iso(),
        "iter469_seed": True,
    })
    # Stamp listing (best-effort — the listing may not exist in this repro)
    await db.listings.update_one(
        {"id": listing_id}, {"$set": {"pickup_code": pickup_code, "iter469_seed": True}}, upsert=True,
    )
    return txn_id


async def _cleanup(db):
    """Remove every iter469-* seed row."""
    coll_prefixes = [
        ("transactions", {"iter469_seed": True}),
        ("escrow_transactions", {"auction_id": {"$regex": f"^{PREFIX}"}}),
        ("listings", {"iter469_seed": True}),
        ("users", {"iter469_seed": True}),
        ("pickup_attempt_log", {"auction_id": {"$regex": f"^{PREFIX}"}}),
        ("seller_payouts", {"listing_id": {"$regex": f"^{PREFIX}"}}),
    ]
    removed = {}
    for coll, q in coll_prefixes:
        r = await db[coll].delete_many(q)
        removed[coll] = r.deleted_count
    return removed


# ── Reproduction ─────────────────────────────────────────────────────

async def repro():
    client = AsyncIOMotorClient(MONGO_URL, tz_aware=True)
    db = client[DB_NAME]
    print(f"[iter469] backend: {BACKEND_URL}")
    print(f"[iter469] db: {DB_NAME}")

    async with httpx.AsyncClient(timeout=30) as http:
        # Seed one seller for the reproduction
        seller = await _mint_seller_and_login(db, http, "A")
        print(f"[iter469] seeded seller {seller['id']}")

        # Seed one buyer id (no login needed — we act as the seller)
        buyer_id = f"{PREFIX}buyer-{uuid.uuid4().hex[:8]}"
        await db.users.insert_one({
            "id": buyer_id,
            "email": f"{PREFIX}buyer@test.example",
            "name": "iter469 buyer",
            "role": "user",
            "created_at": now_iso(),
            "iter469_seed": True,
        })

        # Seed the paid order (transactions row ONLY)
        auction_id = f"{PREFIX}auction-{uuid.uuid4().hex[:10]}"
        pickup_code = f"BVX-IT469{uuid.uuid4().hex[:4].upper()}"
        await _seed_transactions_only_paid_order(
            db, seller_id=seller["id"], buyer_id=buyer_id,
            listing_id=auction_id, hammer=42.00, pickup_code=pickup_code,
        )
        print(f"[iter469] seeded paid transaction {auction_id} pickup_code={pickup_code}")

        # Sanity — confirm NO escrow_transactions row
        esc = await db.escrow_transactions.find_one({"auction_id": auction_id})
        assert esc is None, f"expected NO escrow row for {auction_id}, got {esc}"
        print(f"[iter469] confirmed 0 escrow_transactions rows for {auction_id}")

        # 1) Verify seller dashboard SHOWS this order as held
        headers = {"Authorization": f"Bearer {seller['token']}"}
        r = await http.get(f"{API}/escrow/seller/status", headers=headers)
        r.raise_for_status()
        rows = r.json()
        found = next((x for x in rows if x.get("auction_id") == auction_id), None)
        if not found:
            print(f"[iter469] ⚠ dashboard did NOT include {auction_id} — is the union working?")
            print(f"[iter469] dashboard returned {len(rows)} row(s) for seller {seller['id']}")
        else:
            print(f"[iter469] ✓ dashboard shows {auction_id} with escrow_status={found.get('escrow_status')!r}, has pickup_code={found.get('pickup_code')!r}")

        # 2) Attempt confirm-pickup — expected BUG: 404 escrow_not_found
        r = await http.post(
            f"{API}/escrow/seller/confirm-pickup",
            json={"auction_id": auction_id, "code": pickup_code},
            headers=headers,
        )
        print(f"[iter469] confirm-pickup response: {r.status_code} {r.text[:400]}")
        # Cleanup
        removed = await _cleanup(db)
        print(f"[iter469] cleanup: {removed}")

    client.close()


if __name__ == "__main__":
    asyncio.run(repro())
