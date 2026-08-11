"""
iter469 — Live e2e verification of the escrow pickup-confirmation fix
for paid non-vehicle orders.

Test matrix (per the user directive):
  T1. Normal order with an escrow_transactions row (existing behaviour).
  T2. Paid transaction with NO escrow_transactions row (the bug we
      reproduced) — confirm now resolves the transactions row.
  T3. A new eligible paid non-vehicle Stripe order (simulated by
      calling ``services.payment_collection.finalize_auction_payment``
      via a monkeypatch of ``process_seller_payout`` and receipt
      issuance so nothing else fires) creates escrow-hold state.
  T4. Invalid pickup code → 400 invalid_code.
  T5. Expired pickup code → 410 code_expired.
  T6. Same code submitted twice → second call returns 409
      already_confirmed (no double release, no double payout).
  T7. Different seller attempting the code → 404 escrow_not_found
      (seller identity is enforced as a matching constraint).
  T8. Different auction attempting the code → 404 escrow_not_found.
  T9. Two different paid orders in the SAME auction — each seller can
      only confirm their own transaction using its own buyer code, and
      one order's code can never release the other. (User-mandated.)
  T10. Dashboard vs pickup confirmation resolve the SAME record for
       every eligible paid order (both surfaces agree).

Guardrails:
  - No production data touched (all rows prefixed ``iter469-*``).
  - No Stripe transfers actually executed — the transactions-only
    fallback path never calls stripe.Transfer.create, and the
    escrow-row happy path is executed against a seller with NO
    ``stripe_connect_account_id`` so the payout skips Stripe entirely.
  - All records removed on exit (cleaned up even on error).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

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

PREFIX = "iter469-"
PASSWORD = "IterFourSixNine!"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Seed helpers ──────────────────────────────────────────────────────

async def mint_and_login(db, http: httpx.AsyncClient, tag: str) -> Dict[str, Any]:
    tag_lower = tag.lower()
    email = f"{PREFIX}seller-{tag_lower}-{uuid.uuid4().hex[:6]}@test.example"
    uid = f"{PREFIX}seller-{tag_lower}-{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": uid, "email": email, "password": _pwd_ctx.hash(PASSWORD),
        "name": f"iter469 seller {tag}", "role": "user",
        "account_type": "individual", "created_at": now_iso(),
        "iter469_seed": True,
    })
    await asyncio.sleep(0.6)
    r = await http.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    r.raise_for_status()
    token = r.json().get("access_token") or r.json().get("token")
    return {"id": uid, "email": email, "token": token}


async def mint_buyer(db, tag: str) -> str:
    uid = f"{PREFIX}buyer-{tag.lower()}-{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": uid, "email": f"{PREFIX}buyer-{tag.lower()}@test.example",
        "name": f"iter469 buyer {tag}", "role": "user",
        "created_at": now_iso(), "iter469_seed": True,
    })
    return uid


async def seed_transactions_only(
    db, *, seller_id: str, buyer_id: str, listing_id: str, hammer: float,
    pickup_code: str, lot_number=None,
) -> str:
    """Emulate the ``_ensure_stripe_pickup_code`` output: paid transactions
    row with a pickup_code and NO escrow_transactions row."""
    txn_id = str(uuid.uuid4())
    await db.transactions.insert_one({
        "id": txn_id, "listing_id": listing_id,
        "pickup_code_listing_id": listing_id, "auction_id": listing_id,
        "lot_number": lot_number,
        "listing_title": f"iter469 lot {lot_number or ''}".strip(),
        "buyer_id": buyer_id, "seller_id": seller_id,
        "pickup_code_seller_id": seller_id,
        "hammer_price": hammer, "amount": hammer,
        "payment_method": "stripe",
        "stripe_payment_intent": f"pi_iter469_{uuid.uuid4().hex[:8]}",
        "status": "paid", "payment_confirmed": True,
        "commission_already_collected": True,
        "pickup_code": pickup_code,
        "pickup_code_issued_at": now_iso(),
        "created_at": now_iso(), "iter469_seed": True,
    })
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {"pickup_code": pickup_code, "iter469_seed": True, "title": f"iter469 listing {listing_id}"}},
        upsert=True,
    )
    return txn_id


async def seed_escrow_row(
    db, *, seller_id: str, buyer_id: str, listing_id: str, hammer_cents: int,
    total_cents: int, fee_cents: int, pickup_code: str, expires_at: datetime | None = None,
) -> None:
    """Seed a normal escrow_transactions row (the classic path)."""
    if not expires_at:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    await db.escrow_transactions.insert_one({
        "auction_id": listing_id, "listing_id": listing_id,
        "buyer_id": buyer_id, "seller_id": seller_id,
        "hammer_price_cents": hammer_cents,
        "total_charged_cents": total_cents,
        "application_fee_cents": fee_cents,
        "stripe_payment_intent_id": f"pi_iter469_{uuid.uuid4().hex[:8]}",
        "escrow_status": "held",
        "pickup_code": pickup_code,
        "pickup_code_expires_at": expires_at.isoformat(),
        "auto_release_scheduled_at": expires_at.isoformat(),
        "created_at": now_iso(), "updated_at": now_iso(),
        "item_type": "non_vehicle", "province": "QC",
    })


# ── Cleanup ───────────────────────────────────────────────────────────

async def cleanup(db) -> Dict[str, int]:
    coll_targets: List = [
        ("transactions", {"iter469_seed": True}),
        ("escrow_transactions", {"$or": [
            {"auction_id": {"$regex": f"^{PREFIX}"}},
            {"listing_id": {"$regex": f"^{PREFIX}"}},
        ]}),
        ("listings", {"iter469_seed": True}),
        ("users", {"iter469_seed": True}),
        ("pickup_attempt_log", {"auction_id": {"$regex": f"^{PREFIX}"}}),
        ("seller_payouts", {"listing_id": {"$regex": f"^{PREFIX}"}}),
        ("pending_payouts", {"listing_id": {"$regex": f"^{PREFIX}"}}),
        ("receipts", {"listing_id": {"$regex": f"^{PREFIX}"}}),
        ("notifications", {"data.listing_id": {"$regex": f"^{PREFIX}"}}),
        ("admin_flags", {"auction_id": {"$regex": f"^{PREFIX}"}}),
    ]
    removed = {}
    for coll, q in coll_targets:
        try:
            r = await db[coll].delete_many(q)
            removed[coll] = r.deleted_count
        except Exception as e:  # noqa: BLE001
            removed[coll] = f"error: {e}"
    return removed


# ── Assertion helpers ─────────────────────────────────────────────────

PASS = "✓"
FAIL = "✗"

results: List[Dict[str, Any]] = []


def record(name: str, ok: bool, detail: str = ""):
    marker = PASS if ok else FAIL
    print(f"  {marker} {name}{(' — ' + detail) if detail else ''}")
    results.append({"name": name, "ok": ok, "detail": detail})


# ── Individual tests ──────────────────────────────────────────────────

async def t1_normal_escrow_row(db, http, seller):
    print("[T1] Normal order with an escrow_transactions row")
    listing_id = f"{PREFIX}auction-T1-{uuid.uuid4().hex[:8]}"
    buyer_id = await mint_buyer(db, "T1")
    pickup = f"BVX-IT469T1{uuid.uuid4().hex[:2].upper()}"
    await seed_escrow_row(
        db, seller_id=seller["id"], buyer_id=buyer_id, listing_id=listing_id,
        hammer_cents=5000, total_cents=5500, fee_cents=250, pickup_code=pickup,
    )
    r = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing_id, "code": pickup},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T1a: confirm returns 200 for held escrow row", r.status_code == 200, f"got {r.status_code} {r.text[:100]}")
    if r.status_code == 200:
        body = r.json()
        # iter470 — with no `seller_payouts` row and no Connect account,
        # the safer contract returns `pickup_confirmed_payout_review`
        # (payout_state=unknown) instead of falsely claiming released.
        record(
            "T1b: status reflects payout state (not falsely released)",
            body.get("status") in {"released", "pickup_confirmed_payout_review", "pickup_confirmed_payout_pending"},
            body.get("status", ""),
        )
    # DB check
    row = await db.escrow_transactions.find_one({"auction_id": listing_id}, {"_id": 0})
    record(
        "T1c: escrow row moved out of 'held'",
        (row or {}).get("escrow_status") in {"released", "pickup_confirmed_payout_pending"},
        str((row or {}).get("escrow_status")),
    )
    record("T1d: pickup_confirmed_at set", bool((row or {}).get("pickup_confirmed_at")))
    # Re-confirm (idempotency) → must not release twice.
    r2 = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing_id, "code": pickup},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T1e: second confirm returns 409 (already_confirmed)", r2.status_code == 409, f"got {r2.status_code}")


async def t2_transactions_only(db, http, seller):
    print("[T2] Paid transaction with NO escrow_transactions row")
    listing_id = f"{PREFIX}auction-T2-{uuid.uuid4().hex[:8]}"
    buyer_id = await mint_buyer(db, "T2")
    pickup = f"BVX-IT469T2{uuid.uuid4().hex[:2].upper()}"
    await seed_transactions_only(
        db, seller_id=seller["id"], buyer_id=buyer_id, listing_id=listing_id,
        hammer=42.00, pickup_code=pickup,
    )
    esc = await db.escrow_transactions.find_one({"auction_id": listing_id})
    record("T2a: no escrow_transactions row exists (setup)", esc is None)
    # Dashboard shows this row as held (union)
    dash = await http.get(f"{API}/escrow/seller/status", headers={"Authorization": f"Bearer {seller['token']}"})
    dash.raise_for_status()
    rows = dash.json()
    dash_row = next((x for x in rows if x.get("auction_id") == listing_id), None)
    record("T2b: dashboard shows this order via transactions union", dash_row is not None)
    if dash_row:
        record("T2c: dashboard reports escrow_status=held", dash_row.get("escrow_status") == "held")
    # Confirm now succeeds
    r = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing_id, "code": pickup},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T2d: confirm returns 200 on transactions-only path", r.status_code == 200, f"got {r.status_code} body={r.text[:200]}")
    if r.status_code == 200:
        body = r.json()
        # Transactions-only path never triggers a new Stripe transfer.
        record("T2e: transfer_id is None (no second Stripe transfer)", body.get("transfer_id") is None)
    # DB check: transaction row is stamped confirmed
    tx = await db.transactions.find_one({"listing_id": listing_id}, {"_id": 0})
    record("T2f: pickup_code_confirmed_at set on transactions row", bool((tx or {}).get("pickup_code_confirmed_at")))
    # Second attempt returns 409
    r2 = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing_id, "code": pickup},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T2g: second confirm returns 409 (already_confirmed)", r2.status_code == 409, f"got {r2.status_code}")


async def t3_forward_fix_creates_escrow(db, http, seller):
    print("[T3] finalize_auction_payment creates escrow-hold going forward")
    # Direct call to the internal helper — no scheduler side-effects.
    # We monkey-patch process_seller_payout so no Stripe activity happens.
    from services import payment_collection as pc

    listing_id = f"{PREFIX}auction-T3-{uuid.uuid4().hex[:8]}"
    buyer_id = await mint_buyer(db, "T3")
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "id": listing_id, "title": "iter469 T3 listing", "iter469_seed": True,
            "current_price": 100.0, "final_price": 100.0, "quantity": 1,
        }},
        upsert=True,
    )

    async def _fake_payout(*args, **kwargs):
        return {"status": "sent", "payout_id": "iter469-fake"}

    # Silence side channels (receipts + notifications) so we test only the
    # relevant behaviour: escrow row + pickup code creation.
    from services import receipts as rec_mod, notifications_i18n as noti_mod
    real_receipts = rec_mod.issue_transaction_records

    async def _fake_receipts(*args, **kwargs):
        return {"receipt_id": "iter469-r", "statement_id": "iter469-s"}

    async def _fake_notif(*args, **kwargs):
        return None

    from services import seller_payouts as sp_mod
    real_payout = sp_mod.process_seller_payout
    real_notif = noti_mod.create_notification
    sp_mod.process_seller_payout = _fake_payout
    rec_mod.issue_transaction_records = _fake_receipts
    noti_mod.create_notification = _fake_notif
    try:
        settlement = {
            "buyer_charge": {"stripe_pi": "pi_iter469_forward", "amount": 105.0},
            "fee_breakdown": {
                "hammer_price": 100.0,
                "buyer_premium": 5.0,
                "buyer_taxes": 0.0,
                "buyer_stripe_fee": 0.0,
                "buyer_total_charged": 105.0,
                "seller_commission": 5.0,
            },
            "warnings": [],
            "scenario": "individual",
        }
        listing = {
            "id": listing_id, "title": "iter469 T3 listing",
            "winner_user_id": buyer_id, "seller_id": seller["id"],
            "current_price": 100.0, "final_price": 100.0, "quantity": 1,
            "province": "QC",
        }
        out = await pc.finalize_auction_payment(
            db, listing=listing, collection="listings",
            settlement=settlement, section="marketplace",
        )
        record("T3a: finalize returned payment_collected", out.get("payment_status") == "payment_collected", str(out.get("payment_status")))
        pickup_code = out.get("pickup_code")
        record("T3b: pickup_code generated", bool(pickup_code))
        # THE FORWARD FIX: escrow_transactions row created
        esc = await db.escrow_transactions.find_one({"auction_id": listing_id}, {"_id": 0})
        record("T3c: escrow_transactions row created by finalize", esc is not None)
        if esc:
            record("T3d: escrow_status=held", esc.get("escrow_status") == "held")
            record("T3e: pickup_code stored on escrow row", esc.get("pickup_code") == pickup_code)
            record("T3f: created_via=finalize_auction_payment marker", esc.get("created_via") == "finalize_auction_payment")

        # Verify confirm-pickup now works via the escrow row path.
        r = await http.post(
            f"{API}/escrow/seller/confirm-pickup",
            json={"auction_id": listing_id, "code": pickup_code},
            headers={"Authorization": f"Bearer {seller['token']}"},
        )
        record("T3g: confirm returns 200 for the forward-fix escrow row", r.status_code == 200, f"got {r.status_code} {r.text[:100]}")
    finally:
        sp_mod.process_seller_payout = real_payout
        rec_mod.issue_transaction_records = real_receipts
        noti_mod.create_notification = real_notif


async def t4_invalid_code(db, http, seller):
    print("[T4] Invalid pickup code")
    listing_id = f"{PREFIX}auction-T4-{uuid.uuid4().hex[:8]}"
    buyer_id = await mint_buyer(db, "T4")
    pickup = f"BVX-IT469T4{uuid.uuid4().hex[:2].upper()}"
    await seed_transactions_only(
        db, seller_id=seller["id"], buyer_id=buyer_id, listing_id=listing_id,
        hammer=10.00, pickup_code=pickup,
    )
    r = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing_id, "code": "BVX-NOPE0000"},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T4a: wrong code returns 400", r.status_code == 400, f"got {r.status_code} {r.text[:100]}")
    body = r.json()
    err = ((body.get("detail") or {}).get("error")) if isinstance(body.get("detail"), dict) else None
    record("T4b: error=invalid_code", err == "invalid_code", str(err))
    # DB check: transaction NOT confirmed
    tx = await db.transactions.find_one({"listing_id": listing_id}, {"_id": 0, "pickup_code_confirmed_at": 1})
    record("T4c: transaction remains unconfirmed", (tx or {}).get("pickup_code_confirmed_at") is None)
    # Failed attempt log
    attempts = await db.pickup_attempt_log.count_documents({"auction_id": listing_id})
    record("T4d: failed attempt logged", attempts >= 1, f"count={attempts}")


async def t5_expired_code(db, http, seller):
    print("[T5] Expired pickup code")
    listing_id = f"{PREFIX}auction-T5-{uuid.uuid4().hex[:8]}"
    buyer_id = await mint_buyer(db, "T5")
    pickup = f"BVX-IT469T5{uuid.uuid4().hex[:2].upper()}"
    expired = datetime.now(timezone.utc) - timedelta(hours=1)
    await seed_escrow_row(
        db, seller_id=seller["id"], buyer_id=buyer_id, listing_id=listing_id,
        hammer_cents=1500, total_cents=1600, fee_cents=100, pickup_code=pickup,
        expires_at=expired,
    )
    r = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing_id, "code": pickup},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T5a: expired code returns 410", r.status_code == 410, f"got {r.status_code}")
    if r.status_code == 410:
        err = ((r.json().get("detail") or {}).get("error")) if isinstance(r.json().get("detail"), dict) else None
        record("T5b: error=code_expired", err == "code_expired", str(err))
    # DB check: row is still 'held' (not accidentally released)
    row = await db.escrow_transactions.find_one({"auction_id": listing_id}, {"_id": 0})
    record("T5c: escrow row stays held (not released by expired confirm)", (row or {}).get("escrow_status") == "held")


async def t6_double_confirm_no_double_payout(db, http, seller):
    print("[T6] Same code submitted twice — no double release/payout")
    listing_id = f"{PREFIX}auction-T6-{uuid.uuid4().hex[:8]}"
    buyer_id = await mint_buyer(db, "T6")
    pickup = f"BVX-IT469T6{uuid.uuid4().hex[:2].upper()}"
    await seed_transactions_only(
        db, seller_id=seller["id"], buyer_id=buyer_id, listing_id=listing_id,
        hammer=25.00, pickup_code=pickup,
    )
    # First confirm succeeds
    r1 = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing_id, "code": pickup},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T6a: first confirm 200", r1.status_code == 200)
    # Second confirm returns 409
    r2 = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing_id, "code": pickup},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T6b: second confirm returns 409", r2.status_code == 409, f"got {r2.status_code}")
    # DB counts — one confirmed transaction, zero escrow rows, no payouts.
    tx_confirmed = await db.transactions.count_documents({
        "listing_id": listing_id, "pickup_code_confirmed_at": {"$ne": None},
    })
    record("T6c: exactly 1 confirmed transaction row", tx_confirmed == 1, f"count={tx_confirmed}")
    payouts = await db.seller_payouts.count_documents({"listing_id": listing_id})
    record("T6d: no additional seller payouts written", payouts == 0, f"count={payouts}")


async def t7_wrong_seller(db, http, seller_a, seller_b):
    print("[T7] Different seller attempting the code")
    listing_id = f"{PREFIX}auction-T7-{uuid.uuid4().hex[:8]}"
    buyer_id = await mint_buyer(db, "T7")
    pickup = f"BVX-IT469T7{uuid.uuid4().hex[:2].upper()}"
    await seed_transactions_only(
        db, seller_id=seller_a["id"], buyer_id=buyer_id, listing_id=listing_id,
        hammer=15.00, pickup_code=pickup,
    )
    # Seller B tries seller A's code
    r = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing_id, "code": pickup},
        headers={"Authorization": f"Bearer {seller_b['token']}"},
    )
    record("T7a: wrong seller returns 404 escrow_not_found", r.status_code == 404, f"got {r.status_code} {r.text[:100]}")
    tx = await db.transactions.find_one({"listing_id": listing_id}, {"_id": 0, "pickup_code_confirmed_at": 1})
    record("T7b: transaction remains unconfirmed", (tx or {}).get("pickup_code_confirmed_at") is None)


async def t8_wrong_auction(db, http, seller):
    print("[T8] Different auction attempting the code")
    la = f"{PREFIX}auction-T8a-{uuid.uuid4().hex[:8]}"
    lb = f"{PREFIX}auction-T8b-{uuid.uuid4().hex[:8]}"
    buyer = await mint_buyer(db, "T8")
    pickup_a = f"BVX-IT469T8A{uuid.uuid4().hex[:2].upper()}"
    pickup_b = f"BVX-IT469T8B{uuid.uuid4().hex[:2].upper()}"
    await seed_transactions_only(
        db, seller_id=seller["id"], buyer_id=buyer, listing_id=la,
        hammer=20.00, pickup_code=pickup_a,
    )
    await seed_transactions_only(
        db, seller_id=seller["id"], buyer_id=buyer, listing_id=lb,
        hammer=30.00, pickup_code=pickup_b,
    )
    # Try B's code on A's auction
    r = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": la, "code": pickup_b},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T8a: cross-auction code returns 400 invalid_code", r.status_code == 400, f"got {r.status_code}")


async def t9_two_orders_same_auction(db, http, seller_a, seller_b):
    """USER-MANDATED: two different paid orders in the SAME auction.
    Each seller confirms ONLY their own transaction using its own buyer
    code. One order's code can never release the other order."""
    print("[T9] Two paid orders in the SAME auction (user-mandated)")
    listing_id = f"{PREFIX}auction-T9-{uuid.uuid4().hex[:8]}"
    buyer_a = await mint_buyer(db, "T9A")
    buyer_b = await mint_buyer(db, "T9B")
    pickup_a = f"BVX-IT469T9A{uuid.uuid4().hex[:2].upper()}"
    pickup_b = f"BVX-IT469T9B{uuid.uuid4().hex[:2].upper()}"

    # Two paid orders sharing the same auction_id but different sellers
    # (and different lot_numbers) — simulates a multi-item lot auction.
    await seed_transactions_only(
        db, seller_id=seller_a["id"], buyer_id=buyer_a, listing_id=listing_id,
        hammer=17.00, pickup_code=pickup_a, lot_number=1,
    )
    await seed_transactions_only(
        db, seller_id=seller_b["id"], buyer_id=buyer_b, listing_id=listing_id,
        hammer=23.00, pickup_code=pickup_b, lot_number=2,
    )

    # Seller B tries to use seller A's buyer code on the shared auction
    r_cross = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing_id, "code": pickup_a},
        headers={"Authorization": f"Bearer {seller_b['token']}"},
    )
    record(
        "T9a: seller B cannot release seller A's order via A's code",
        r_cross.status_code in (400, 404),
        f"got {r_cross.status_code}",
    )

    # Seller A tries to use seller B's buyer code on the shared auction
    r_cross2 = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing_id, "code": pickup_b},
        headers={"Authorization": f"Bearer {seller_a['token']}"},
    )
    record(
        "T9b: seller A cannot release seller B's order via B's code",
        r_cross2.status_code in (400, 404),
        f"got {r_cross2.status_code}",
    )

    # Each seller confirms their OWN order — must succeed.
    r_a = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing_id, "code": pickup_a},
        headers={"Authorization": f"Bearer {seller_a['token']}"},
    )
    record("T9c: seller A confirms own order (200)", r_a.status_code == 200, f"got {r_a.status_code} {r_a.text[:100]}")
    r_b = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing_id, "code": pickup_b},
        headers={"Authorization": f"Bearer {seller_b['token']}"},
    )
    record("T9d: seller B confirms own order (200)", r_b.status_code == 200, f"got {r_b.status_code} {r_b.text[:100]}")

    # DB check: exactly ONE confirmed row per seller.
    tx_a = await db.transactions.find_one(
        {"listing_id": listing_id, "seller_id": seller_a["id"]}, {"_id": 0}
    )
    tx_b = await db.transactions.find_one(
        {"listing_id": listing_id, "seller_id": seller_b["id"]}, {"_id": 0}
    )
    record("T9e: seller A's row confirmed", bool((tx_a or {}).get("pickup_code_confirmed_at")))
    record("T9f: seller B's row confirmed", bool((tx_b or {}).get("pickup_code_confirmed_at")))
    record(
        "T9g: seller A's row NOT confirmed by seller B",
        (tx_a or {}).get("pickup_code_confirmed_by") == seller_a["id"],
        str((tx_a or {}).get("pickup_code_confirmed_by")),
    )


async def t10_dashboard_and_confirm_agree(db, http, seller):
    """For every paid order the dashboard shows, pickup confirmation
    must be able to resolve it (no orphans in the union)."""
    print("[T10] Dashboard display + pickup confirmation resolve the same order")
    dash = await http.get(f"{API}/escrow/seller/status", headers={"Authorization": f"Bearer {seller['token']}"})
    dash.raise_for_status()
    rows = dash.json()
    # Filter to iter469 rows only.
    ours = [r for r in rows if str(r.get("auction_id", "")).startswith(PREFIX)]
    resolvable = 0
    for row in ours:
        # Skip already released — the dashboard also shows historical rows.
        if row.get("escrow_status") != "held":
            continue
        aid = row["auction_id"]
        # Look up the record the confirm flow WOULD resolve.
        esc = await db.escrow_transactions.find_one(
            {"auction_id": aid, "seller_id": seller["id"], "escrow_status": {"$in": ["held", "disputed"]}}
        )
        tx = await db.transactions.find_one({
            "$or": [{"listing_id": aid}, {"pickup_code_listing_id": aid}, {"auction_id": aid}],
            "$and": [{"$or": [{"seller_id": seller["id"]}, {"pickup_code_seller_id": seller["id"]}]}],
            "pickup_code": {"$exists": True, "$ne": None},
            "pickup_code_confirmed_at": None,
        })
        if esc or tx:
            resolvable += 1
    record(
        "T10a: every dashboard 'held' row is resolvable by confirm-pickup",
        resolvable == sum(1 for r in ours if r.get("escrow_status") == "held"),
        f"resolvable={resolvable}/{sum(1 for r in ours if r.get('escrow_status') == 'held')}",
    )


# ── Runner ────────────────────────────────────────────────────────────

async def main():
    print(f"[iter469] backend: {BACKEND_URL}")
    print(f"[iter469] db: {DB_NAME}")
    client = AsyncIOMotorClient(MONGO_URL, tz_aware=True)
    db = client[DB_NAME]
    async with httpx.AsyncClient(timeout=30) as http:
        seller_a = None
        try:
            seller_a = await mint_and_login(db, http, "A")
            seller_b = await mint_and_login(db, http, "B")
            seller_c = await mint_and_login(db, http, "C")
            print(f"[iter469] seeded sellers A={seller_a['id']} B={seller_b['id']} C={seller_c['id']}\n")

            await t1_normal_escrow_row(db, http, seller_a)
            await t2_transactions_only(db, http, seller_a)
            await t3_forward_fix_creates_escrow(db, http, seller_c)
            await t4_invalid_code(db, http, seller_a)
            await t5_expired_code(db, http, seller_a)
            await t6_double_confirm_no_double_payout(db, http, seller_a)
            await t7_wrong_seller(db, http, seller_a, seller_b)
            await t8_wrong_auction(db, http, seller_a)
            await t9_two_orders_same_auction(db, http, seller_a, seller_b)
            await t10_dashboard_and_confirm_agree(db, http, seller_a)
        finally:
            removed = await cleanup(db)
            print(f"\n[iter469] cleanup: {removed}")

    total = len(results)
    ok = sum(1 for r in results if r["ok"])
    print("\n═════════════════════════════════════════════")
    print(f"[iter469] RESULT: {ok}/{total} checks PASS")
    print("═════════════════════════════════════════════")
    failed = [r for r in results if not r["ok"]]
    if failed:
        print("\nFAILED CHECKS:")
        for r in failed:
            print(f"  {FAIL} {r['name']} — {r['detail']}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
