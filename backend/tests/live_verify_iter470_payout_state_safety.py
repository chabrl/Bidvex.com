"""
iter470 — Live e2e verification of the escrow pickup confirmation
payout-state safety fix.

Test matrix (per user directive):
  T1. Normal order with escrow state and payout SENT (transfer_id set)
      → confirm returns 200 "released", NO second Stripe transfer,
      seller_payouts row unchanged, escrow row → released.
  T2. Paid transaction, no escrow, payout SENT with transfer_id
      → confirm returns 200 "released", transfer_id echoed from
      seller_payouts, NO Stripe transfer initiated.
  T3. Paid transaction, no escrow, payout PENDING (no transfer_id)
      → confirm returns 200 "pickup_confirmed_payout_pending",
      NO "funds released" message, pending payout row untouched.
  T4. Paid transaction, no escrow, payout FAILED
      → confirm returns 200 "pickup_confirmed_payout_review",
      NO "funds released" message, failed payout row untouched.
  T5. Paid transaction, no escrow, NO payout record at all (unknown)
      → confirm returns 200 "pickup_confirmed_payout_review",
      NO "funds released" message, no payout row created.
  T6. Invalid pickup code → 400 invalid_code.
  T7. Same code submitted twice → second call 409 already_confirmed
      (no payout obligation consumed on second call).
  T8. Wrong seller → 404 escrow_not_found.
  T9. Wrong auction → 400 invalid_code.
  T10. Dashboard row's payout_state matches confirm-pickup response.

Guardrails:
  - No production data touched (all rows prefixed ``iter470-*``).
  - No Stripe transfers executed — sellers have no
    ``stripe_connect_account_id`` so `stripe.Transfer.create` is never
    called on the escrow-row path either.
  - All records removed on exit.
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

PREFIX = "iter470-"
PASSWORD = "IterFourSevenZero!"

PASS, FAIL = "✓", "✗"
results: List[Dict[str, Any]] = []


def record(name: str, ok: bool, detail: str = ""):
    marker = PASS if ok else FAIL
    print(f"  {marker} {name}{(' — ' + detail) if detail else ''}")
    results.append({"name": name, "ok": ok, "detail": detail})


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Seed helpers ─────────────────────────────────────────────────────

async def mint_and_login(db, http, tag: str) -> Dict[str, Any]:
    tag_lower = tag.lower()
    email = f"{PREFIX}seller-{tag_lower}-{uuid.uuid4().hex[:6]}@test.example"
    uid = f"{PREFIX}seller-{tag_lower}-{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": uid, "email": email, "password": _pwd_ctx.hash(PASSWORD),
        "name": f"iter470 seller {tag}", "role": "user",
        "account_type": "individual", "created_at": now_iso(),
        "iter470_seed": True,
    })
    await asyncio.sleep(0.5)
    r = await http.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    r.raise_for_status()
    body = r.json()
    token = body.get("access_token") or body.get("token")
    return {"id": uid, "email": email, "token": token}


async def mint_buyer(db, tag: str) -> str:
    uid = f"{PREFIX}buyer-{tag.lower()}-{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": uid, "email": f"{PREFIX}buyer-{tag.lower()}@test.example",
        "name": f"iter470 buyer {tag}", "role": "user",
        "created_at": now_iso(), "iter470_seed": True,
    })
    return uid


async def seed_paid_tx(
    db, *, seller_id, buyer_id, listing_id, hammer, pickup_code, lot_number=None,
):
    txn_id = str(uuid.uuid4())
    await db.transactions.insert_one({
        "id": txn_id, "listing_id": listing_id,
        "pickup_code_listing_id": listing_id, "auction_id": listing_id,
        "lot_number": lot_number,
        "listing_title": f"iter470 lot {lot_number or ''}".strip(),
        "buyer_id": buyer_id, "seller_id": seller_id,
        "pickup_code_seller_id": seller_id,
        "hammer_price": hammer, "amount": hammer,
        "payment_method": "stripe",
        "stripe_payment_intent": f"pi_iter470_{uuid.uuid4().hex[:8]}",
        "status": "paid", "payment_confirmed": True,
        "commission_already_collected": True,
        "pickup_code": pickup_code,
        "pickup_code_issued_at": now_iso(),
        "created_at": now_iso(), "iter470_seed": True,
    })
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {"pickup_code": pickup_code, "iter470_seed": True, "title": f"iter470 listing {listing_id}"}},
        upsert=True,
    )
    return txn_id


async def seed_escrow_row(
    db, *, seller_id, buyer_id, listing_id, hammer_cents, total_cents, fee_cents,
    pickup_code, expires_at=None, escrow_status="held",
):
    if not expires_at:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    await db.escrow_transactions.insert_one({
        "auction_id": listing_id, "listing_id": listing_id,
        "buyer_id": buyer_id, "seller_id": seller_id,
        "hammer_price_cents": hammer_cents,
        "total_charged_cents": total_cents,
        "application_fee_cents": fee_cents,
        "stripe_payment_intent_id": f"pi_iter470_{uuid.uuid4().hex[:8]}",
        "escrow_status": escrow_status,
        "pickup_code": pickup_code,
        "pickup_code_expires_at": expires_at.isoformat(),
        "auto_release_scheduled_at": expires_at.isoformat(),
        "created_at": now_iso(), "updated_at": now_iso(),
        "item_type": "non_vehicle", "province": "QC",
    })


async def seed_seller_payout(db, *, listing_id, seller_id, amount, status,
                             transfer_id=None, lot_number=None):
    pid = str(uuid.uuid4())
    await db.seller_payouts.insert_one({
        "id": pid, "section": "marketplace", "listing_id": listing_id,
        "lot_number": lot_number, "listing_title": "iter470 test",
        "seller_id": seller_id, "amount": round(float(amount), 2),
        "currency": "CAD", "status": status,
        "stripe_transfer_id": transfer_id,
        "sent_at": now_iso() if status == "sent" else None,
        "created_at": now_iso(),
    })
    return pid


# ── Cleanup ──────────────────────────────────────────────────────────

async def cleanup(db):
    targets = [
        ("transactions", {"iter470_seed": True}),
        ("escrow_transactions", {"auction_id": {"$regex": f"^{PREFIX}"}}),
        ("listings", {"iter470_seed": True}),
        ("users", {"iter470_seed": True}),
        ("pickup_attempt_log", {"auction_id": {"$regex": f"^{PREFIX}"}}),
        ("seller_payouts", {"listing_id": {"$regex": f"^{PREFIX}"}}),
        ("pending_payouts", {"listing_id": {"$regex": f"^{PREFIX}"}}),
        ("receipts", {"listing_id": {"$regex": f"^{PREFIX}"}}),
    ]
    removed = {}
    for coll, q in targets:
        try:
            r = await db[coll].delete_many(q)
            removed[coll] = r.deleted_count
        except Exception as e:  # noqa: BLE001
            removed[coll] = f"err: {e}"
    return removed


def _msg_en(body: Dict[str, Any]) -> str:
    return str(body.get("message_en") or "").lower()


# ── Tests ────────────────────────────────────────────────────────────

async def t1_escrow_row_payout_sent(db, http, seller):
    print("[T1] Escrow row + payout sent + transfer_id")
    listing = f"{PREFIX}auction-T1-{uuid.uuid4().hex[:8]}"
    buyer = await mint_buyer(db, "T1")
    pickup = f"BVX-IT470T1{uuid.uuid4().hex[:2].upper()}"
    transfer_id = f"tr_iter470_T1_{uuid.uuid4().hex[:8]}"
    await seed_escrow_row(
        db, seller_id=seller["id"], buyer_id=buyer, listing_id=listing,
        hammer_cents=5000, total_cents=5500, fee_cents=250, pickup_code=pickup,
    )
    await seed_seller_payout(
        db, listing_id=listing, seller_id=seller["id"],
        amount=52.50, status="sent", transfer_id=transfer_id,
    )
    r = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing, "code": pickup},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T1a: confirm returns 200", r.status_code == 200, f"got {r.status_code}")
    body = r.json() if r.status_code == 200 else {}
    record("T1b: status=released", body.get("status") == "released", str(body.get("status")))
    record("T1c: transfer_id echoed from seller_payouts", body.get("transfer_id") == transfer_id)
    record("T1d: payout_state=sent", body.get("payout_state") == "sent")
    record("T1e: message says 'funds have been released'", "released" in _msg_en(body))
    # DB check: no second payout row created
    n_payouts = await db.seller_payouts.count_documents({"listing_id": listing})
    record("T1f: no second seller_payouts row", n_payouts == 1, f"count={n_payouts}")
    row = await db.escrow_transactions.find_one({"auction_id": listing})
    record("T1g: escrow row → released", (row or {}).get("escrow_status") == "released")
    record("T1h: escrow row stripe_transfer_id from prior payout", (row or {}).get("stripe_transfer_id") == transfer_id)


async def t2_no_escrow_payout_sent(db, http, seller):
    print("[T2] No escrow + payout sent + transfer_id")
    listing = f"{PREFIX}auction-T2-{uuid.uuid4().hex[:8]}"
    buyer = await mint_buyer(db, "T2")
    pickup = f"BVX-IT470T2{uuid.uuid4().hex[:2].upper()}"
    transfer_id = f"tr_iter470_T2_{uuid.uuid4().hex[:8]}"
    await seed_paid_tx(db, seller_id=seller["id"], buyer_id=buyer, listing_id=listing,
                      hammer=42.00, pickup_code=pickup)
    await seed_seller_payout(
        db, listing_id=listing, seller_id=seller["id"],
        amount=39.90, status="sent", transfer_id=transfer_id,
    )
    r = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing, "code": pickup},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T2a: confirm returns 200", r.status_code == 200, f"got {r.status_code}")
    body = r.json() if r.status_code == 200 else {}
    record("T2b: status=released", body.get("status") == "released", str(body.get("status")))
    record("T2c: transfer_id echoed from seller_payouts", body.get("transfer_id") == transfer_id)
    record("T2d: message says 'funds have been released'", "released" in _msg_en(body))
    n_payouts = await db.seller_payouts.count_documents({"listing_id": listing})
    record("T2e: no additional seller_payouts row", n_payouts == 1, f"count={n_payouts}")
    tx = await db.transactions.find_one({"listing_id": listing})
    record("T2f: transaction pickup_code_confirmed_at set", bool((tx or {}).get("pickup_code_confirmed_at")))


async def t3_no_escrow_payout_pending(db, http, seller):
    print("[T3] No escrow + payout pending (no transfer_id)")
    listing = f"{PREFIX}auction-T3-{uuid.uuid4().hex[:8]}"
    buyer = await mint_buyer(db, "T3")
    pickup = f"BVX-IT470T3{uuid.uuid4().hex[:2].upper()}"
    await seed_paid_tx(db, seller_id=seller["id"], buyer_id=buyer, listing_id=listing,
                      hammer=25.00, pickup_code=pickup)
    payout_id = await seed_seller_payout(
        db, listing_id=listing, seller_id=seller["id"],
        amount=23.75, status="pending", transfer_id=None,
    )
    r = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing, "code": pickup},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T3a: confirm returns 200", r.status_code == 200, f"got {r.status_code} {r.text[:200]}")
    body = r.json() if r.status_code == 200 else {}
    record("T3b: status=pickup_confirmed_payout_pending",
           body.get("status") == "pickup_confirmed_payout_pending", str(body.get("status")))
    record("T3c: payout_state=pending", body.get("payout_state") == "pending")
    record("T3d: transfer_id is None", body.get("transfer_id") is None)
    record("T3e: message says 'payout is pending'", "pending" in _msg_en(body))
    record("T3f: message does NOT say 'funds have been released'", "released" not in _msg_en(body))
    # CRITICAL: pending payout row must survive untouched
    payout = await db.seller_payouts.find_one({"id": payout_id}, {"_id": 0})
    record("T3g: pending payout row survives (status still pending)",
           (payout or {}).get("status") == "pending", str((payout or {}).get("status")))
    record("T3h: pending payout row still has no transfer_id",
           (payout or {}).get("stripe_transfer_id") is None)
    # Transaction stamped confirmed
    tx = await db.transactions.find_one({"listing_id": listing})
    record("T3i: transaction pickup_code_confirmed_at set", bool((tx or {}).get("pickup_code_confirmed_at")))
    record("T3j: transaction payout_state_at_confirm=pending",
           (tx or {}).get("payout_state_at_confirm") == "pending")


async def t4_no_escrow_payout_failed(db, http, seller):
    print("[T4] No escrow + payout FAILED (user-mandated separate test)")
    listing = f"{PREFIX}auction-T4-{uuid.uuid4().hex[:8]}"
    buyer = await mint_buyer(db, "T4")
    pickup = f"BVX-IT470T4{uuid.uuid4().hex[:2].upper()}"
    await seed_paid_tx(db, seller_id=seller["id"], buyer_id=buyer, listing_id=listing,
                      hammer=30.00, pickup_code=pickup)
    payout_id = await seed_seller_payout(
        db, listing_id=listing, seller_id=seller["id"],
        amount=28.50, status="failed", transfer_id=None,
    )
    r = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing, "code": pickup},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T4a: confirm returns 200", r.status_code == 200, f"got {r.status_code}")
    body = r.json() if r.status_code == 200 else {}
    record("T4b: status=pickup_confirmed_payout_review",
           body.get("status") == "pickup_confirmed_payout_review", str(body.get("status")))
    record("T4c: payout_state=failed", body.get("payout_state") == "failed")
    record("T4d: transfer_id is None", body.get("transfer_id") is None)
    record("T4e: message says 'payout requires review'", "review" in _msg_en(body))
    record("T4f: message does NOT say 'funds have been released'", "released" not in _msg_en(body))
    record("T4g: message does NOT say 'will be released shortly'", "shortly" not in _msg_en(body))
    # CRITICAL: failed payout row must survive untouched
    payout = await db.seller_payouts.find_one({"id": payout_id}, {"_id": 0})
    record("T4h: failed payout row survives (status still failed)",
           (payout or {}).get("status") == "failed", str((payout or {}).get("status")))


async def t5_no_escrow_no_payout(db, http, seller):
    """User-mandated: missing payout record must NOT be treated as
    failed and NOT be reported as released. It is `unknown`."""
    print("[T5] No escrow + NO payout record (user-mandated separate test)")
    listing = f"{PREFIX}auction-T5-{uuid.uuid4().hex[:8]}"
    buyer = await mint_buyer(db, "T5")
    pickup = f"BVX-IT470T5{uuid.uuid4().hex[:2].upper()}"
    await seed_paid_tx(db, seller_id=seller["id"], buyer_id=buyer, listing_id=listing,
                      hammer=17.00, pickup_code=pickup)
    # Confirm NO payout row exists.
    n_before = await db.seller_payouts.count_documents({"listing_id": listing})
    record("T5a: no payout row exists (setup)", n_before == 0)
    r = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing, "code": pickup},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T5b: confirm returns 200", r.status_code == 200, f"got {r.status_code}")
    body = r.json() if r.status_code == 200 else {}
    record("T5c: status=pickup_confirmed_payout_review",
           body.get("status") == "pickup_confirmed_payout_review", str(body.get("status")))
    record("T5d: payout_state=unknown (NOT failed)", body.get("payout_state") == "unknown")
    record("T5e: transfer_id is None", body.get("transfer_id") is None)
    record("T5f: message says 'payout requires review'", "review" in _msg_en(body))
    record("T5g: message does NOT say 'funds have been released'", "released" not in _msg_en(body))
    record("T5h: message does NOT say 'will be released shortly'", "shortly" not in _msg_en(body))
    # CRITICAL: confirming a missing payout must NOT create a payout row.
    n_after = await db.seller_payouts.count_documents({"listing_id": listing})
    record("T5i: still no seller_payouts row (confirm didn't create one)", n_after == 0, f"count={n_after}")
    # No pending_payouts row either
    n_pending = await db.pending_payouts.count_documents({"listing_id": listing})
    record("T5j: still no pending_payouts row", n_pending == 0)


async def t6_invalid_code(db, http, seller):
    print("[T6] Invalid pickup code — blocked")
    listing = f"{PREFIX}auction-T6-{uuid.uuid4().hex[:8]}"
    buyer = await mint_buyer(db, "T6")
    pickup = f"BVX-IT470T6{uuid.uuid4().hex[:2].upper()}"
    await seed_paid_tx(db, seller_id=seller["id"], buyer_id=buyer, listing_id=listing,
                      hammer=10.00, pickup_code=pickup)
    await seed_seller_payout(db, listing_id=listing, seller_id=seller["id"],
                             amount=9.50, status="pending", transfer_id=None)
    r = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing, "code": "BVX-NOPEXXX"},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T6a: wrong code returns 400", r.status_code == 400)
    body = r.json()
    err = ((body.get("detail") or {}).get("error")) if isinstance(body.get("detail"), dict) else None
    record("T6b: error=invalid_code", err == "invalid_code")


async def t7_double_confirm_preserves_payout(db, http, seller):
    """Idempotency + payout obligation preservation on double confirm."""
    print("[T7] Same code twice — no double consumption of payout obligation")
    listing = f"{PREFIX}auction-T7-{uuid.uuid4().hex[:8]}"
    buyer = await mint_buyer(db, "T7")
    pickup = f"BVX-IT470T7{uuid.uuid4().hex[:2].upper()}"
    await seed_paid_tx(db, seller_id=seller["id"], buyer_id=buyer, listing_id=listing,
                      hammer=25.00, pickup_code=pickup)
    payout_id = await seed_seller_payout(
        db, listing_id=listing, seller_id=seller["id"],
        amount=23.75, status="pending", transfer_id=None,
    )
    # First confirm succeeds
    r1 = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing, "code": pickup},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T7a: first confirm 200", r1.status_code == 200)
    # Second confirm returns 409
    r2 = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing, "code": pickup},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T7b: second confirm returns 409", r2.status_code == 409)
    # Payout row still pending, still no transfer_id
    payout = await db.seller_payouts.find_one({"id": payout_id}, {"_id": 0})
    record("T7c: payout row still pending", (payout or {}).get("status") == "pending")
    record("T7d: payout row still has no transfer_id",
           (payout or {}).get("stripe_transfer_id") is None)


async def t8_wrong_seller(db, http, seller_a, seller_b):
    print("[T8] Wrong seller — blocked")
    listing = f"{PREFIX}auction-T8-{uuid.uuid4().hex[:8]}"
    buyer = await mint_buyer(db, "T8")
    pickup = f"BVX-IT470T8{uuid.uuid4().hex[:2].upper()}"
    await seed_paid_tx(db, seller_id=seller_a["id"], buyer_id=buyer, listing_id=listing,
                      hammer=15.00, pickup_code=pickup)
    await seed_seller_payout(db, listing_id=listing, seller_id=seller_a["id"],
                             amount=14.25, status="pending", transfer_id=None)
    r = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": listing, "code": pickup},
        headers={"Authorization": f"Bearer {seller_b['token']}"},
    )
    record("T8a: wrong seller returns 404", r.status_code == 404)


async def t9_wrong_auction(db, http, seller):
    print("[T9] Wrong auction — blocked")
    a = f"{PREFIX}auction-T9a-{uuid.uuid4().hex[:8]}"
    b = f"{PREFIX}auction-T9b-{uuid.uuid4().hex[:8]}"
    buyer = await mint_buyer(db, "T9")
    pickup_a = f"BVX-IT470T9A{uuid.uuid4().hex[:2].upper()}"
    pickup_b = f"BVX-IT470T9B{uuid.uuid4().hex[:2].upper()}"
    await seed_paid_tx(db, seller_id=seller["id"], buyer_id=buyer, listing_id=a,
                      hammer=20.00, pickup_code=pickup_a)
    await seed_paid_tx(db, seller_id=seller["id"], buyer_id=buyer, listing_id=b,
                      hammer=30.00, pickup_code=pickup_b)
    r = await http.post(
        f"{API}/escrow/seller/confirm-pickup",
        json={"auction_id": a, "code": pickup_b},
        headers={"Authorization": f"Bearer {seller['token']}"},
    )
    record("T9a: cross-auction code returns 400", r.status_code == 400)


async def t10_dashboard_projects_payout_state(db, http, seller):
    """Dashboard payload MUST distinguish sent / pending / failed /
    unknown for every row."""
    print("[T10] Dashboard projects accurate payout_state")
    # Setup: 4 orders, each with a different payout state.
    orders = []
    for tag, status, transfer_id in [
        ("sent", "sent", f"tr_iter470_T10_{uuid.uuid4().hex[:8]}"),
        ("pending", "pending", None),
        ("failed", "failed", None),
        ("unknown", None, None),  # No payout row at all
    ]:
        listing = f"{PREFIX}auction-T10-{tag}-{uuid.uuid4().hex[:8]}"
        buyer = await mint_buyer(db, f"T10-{tag}")
        pickup = f"BVX-IT470T10{tag[:1].upper()}{uuid.uuid4().hex[:2].upper()}"
        await seed_paid_tx(db, seller_id=seller["id"], buyer_id=buyer, listing_id=listing,
                          hammer=20.00, pickup_code=pickup)
        if status:
            await seed_seller_payout(
                db, listing_id=listing, seller_id=seller["id"],
                amount=19.00, status=status, transfer_id=transfer_id,
            )
        orders.append((listing, tag))

    r = await http.get(f"{API}/escrow/seller/status",
                       headers={"Authorization": f"Bearer {seller['token']}"})
    r.raise_for_status()
    rows = {x.get("auction_id"): x for x in r.json()}
    for listing, expected in orders:
        row = rows.get(listing)
        record(f"T10a-{expected}: dashboard row present", row is not None)
        if row:
            record(f"T10b-{expected}: dashboard payout_state={expected}",
                   row.get("payout_state") == expected,
                   f"got {row.get('payout_state')}")


# ── Runner ───────────────────────────────────────────────────────────

async def main():
    print(f"[iter470] backend: {BACKEND_URL}")
    print(f"[iter470] db: {DB_NAME}")
    client = AsyncIOMotorClient(MONGO_URL, tz_aware=True)
    db = client[DB_NAME]
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            seller_a = await mint_and_login(db, http, "A")
            seller_b = await mint_and_login(db, http, "B")
            print(f"[iter470] sellers A={seller_a['id']} B={seller_b['id']}\n")

            await t1_escrow_row_payout_sent(db, http, seller_a)
            await t2_no_escrow_payout_sent(db, http, seller_a)
            await t3_no_escrow_payout_pending(db, http, seller_a)
            await t4_no_escrow_payout_failed(db, http, seller_a)
            await t5_no_escrow_no_payout(db, http, seller_a)
            await t6_invalid_code(db, http, seller_a)
            await t7_double_confirm_preserves_payout(db, http, seller_a)
            await t8_wrong_seller(db, http, seller_a, seller_b)
            await t9_wrong_auction(db, http, seller_a)
            await t10_dashboard_projects_payout_state(db, http, seller_a)
    finally:
        removed = await cleanup(db)
        print(f"\n[iter470] cleanup: {removed}")

    total = len(results)
    ok = sum(1 for r in results if r["ok"])
    print("\n═════════════════════════════════════════════")
    print(f"[iter470] RESULT: {ok}/{total} checks PASS")
    print("═════════════════════════════════════════════")
    failed = [r for r in results if not r["ok"]]
    if failed:
        print("\nFAILED CHECKS:")
        for r in failed:
            print(f"  {FAIL} {r['name']} — {r['detail']}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
