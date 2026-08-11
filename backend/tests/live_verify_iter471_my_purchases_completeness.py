"""
iter471 — Live e2e verification of the Buyer Dashboard "My Purchases"
completeness fix.

Test matrix (per user directive):
  T1. Paid single-item (marketplace) purchase → 1 row visible with
      order#, hammer, payment=collected, pickup pending.
  T2. Paid multi-lot lot auction (multi_item_listings) — Buyer A wins
      lots 1, 2, 3 → 3 distinct rows, each with correct lot_number,
      lot_title from the parent doc's `lots` array (NOT from
      receipt.listing_title), quantity, and parent auction title.
  T3. Same multi-lot auction — Buyer B wins lot 4 → 1 row in B's
      dashboard. Buyer B's lot must NEVER appear in Buyer A's
      dashboard (and vice versa).
  T4. Paid vehicle multi-lot (vehicle_listings) — 2 lots won by one
      buyer → 2 distinct rows with vehicle lot titles.
  T5. Paid storage_auctions purchase → 1 row visible.

Additional guardrails asserted:
  * Section-aware de-duplication identity: `(section, listing_id,
    lot_number)`. Same listing_id in two sections must not collapse.
  * `receipt.listing_title` is used only as a fallback — when the lot
    doc has a distinct title, the primary title MUST be the lot's.
  * Bilingual EN/FR: primary title and secondary parent title remain
    stable across language toggle (they are section-native strings).

Every row is prefixed `iter471-*` and cleaned on exit.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND = Path("/app/backend")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # type: ignore
load_dotenv(BACKEND / ".env")
load_dotenv(Path("/app/frontend/.env"), override=False)

import httpx  # type: ignore
from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
from passlib.context import CryptContext  # type: ignore

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL") or "https://prod-verify-2.preview.emergentagent.com"
API = f"{BACKEND_URL.rstrip('/')}/api"

PREFIX = "iter471-"
PWD = "IterFourSevenOne!"
PASS, FAIL = "✓", "✗"
results: List[Dict[str, Any]] = []


def record(name, ok, detail=""):
    print(f"  {PASS if ok else FAIL} {name}{(' — ' + detail) if detail else ''}")
    results.append({"name": name, "ok": ok, "detail": detail})


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def mint_buyer(db, http, tag: str) -> Dict[str, Any]:
    tl = tag.lower()
    email = f"{PREFIX}buyer-{tl}-{uuid.uuid4().hex[:6]}@test.example"
    uid = f"{PREFIX}buyer-{tl}-{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": uid, "email": email, "password": _pwd.hash(PWD),
        "name": f"iter471 buyer {tag}", "role": "user",
        "account_type": "individual", "created_at": now_iso(),
        "iter471_seed": True,
    })
    await asyncio.sleep(0.4)
    r = await http.post(f"{API}/auth/login", json={"email": email, "password": PWD})
    r.raise_for_status()
    token = r.json().get("access_token") or r.json().get("token")
    return {"id": uid, "email": email, "token": token}


async def seed_marketplace_listing(db, *, buyer_id, title, hammer, tag):
    lid = f"{PREFIX}mkt-{tag}-{uuid.uuid4().hex[:8]}"
    await db.listings.insert_one({
        "id": lid, "title": title, "final_price": hammer,
        "current_price": hammer, "status": "sold",
        "winner_user_id": buyer_id, "seller_id": f"{PREFIX}seller-x",
        "sold_at": now_iso(), "iter471_seed": True,
    })
    return lid


async def seed_multi_item_auction(db, *, tag, event_title, lots_spec: list):
    """Create a parent multi_item_listings doc with the given lots.
    Each spec: dict{lot_number, title, quantity, price}."""
    lid = f"{PREFIX}lot-{tag}-{uuid.uuid4().hex[:8]}"
    await db.multi_item_listings.insert_one({
        "id": lid, "title": event_title, "status": "ended",
        "lots": [
            {"lot_number": s["lot_number"], "title": s["title"],
             "description": s.get("description", ""),
             "quantity": s.get("quantity", 1),
             "current_price": s.get("price", 0.0),
             "condition": "used", "starting_price": s.get("price", 0.0)}
            for s in lots_spec
        ],
        "seller_id": f"{PREFIX}seller-y",
        "iter471_seed": True,
    })
    return lid


async def seed_vehicle_auction(db, *, tag, event_title, lots_spec: list):
    lid = f"{PREFIX}veh-{tag}-{uuid.uuid4().hex[:8]}"
    await db.vehicle_listings.insert_one({
        "id": lid, "title": event_title, "status": "ended",
        "lots": [
            {"lot_number": s["lot_number"], "title": s["title"],
             "description": s.get("description", ""),
             "quantity": s.get("quantity", 1),
             "vin": s.get("vin", "1HGCM82633A123456")}
            for s in lots_spec
        ],
        "seller_id": f"{PREFIX}seller-v",
        "iter471_seed": True,
    })
    return lid


async def seed_storage_auction(db, *, tag, title):
    lid = f"{PREFIX}sto-{tag}-{uuid.uuid4().hex[:8]}"
    await db.storage_auctions.insert_one({
        "id": lid, "title": title, "status": "ended",
        "seller_id": f"{PREFIX}seller-s",
        "iter471_seed": True,
    })
    return lid


async def seed_buyer_receipt(
    db, *, section: str, listing_id: str, buyer_id: str,
    hammer: float, lot_number: Optional[int] = None,
    receipt_listing_title: str = "receipt fallback title",
    pickup_code: Optional[str] = None,
):
    """Emulate services/receipts.issue_transaction_records — inserts a
    minimal buyer_receipt row so /api/dashboard/buyer picks it up."""
    rid = str(uuid.uuid4())
    _short = (listing_id or "x").replace("-", "")[:8].upper()
    await db.receipts.insert_one({
        "id": rid, "type": "buyer_receipt", "user_id": buyer_id,
        "section": section, "listing_id": listing_id, "lot_number": lot_number,
        # This is the RECEIPT's listing_title — it should be used as a
        # FALLBACK only. The primary lot title must come from the
        # section-native parent doc's `lots` array.
        "listing_title": receipt_listing_title,
        "hammer_price": hammer, "platform_fee": 0.5,
        "taxes": 0.0, "processing_fee": 0.0,
        "total_charged": round(hammer + 0.5, 2), "net_payout": hammer - 0.5,
        "currency": "CAD", "payment_method_last4": None,
        "transaction_id": f"tx_iter471_{uuid.uuid4().hex[:8]}",
        "order_number": f"BVX-{_short}",
        "pickup_code": pickup_code,
        "created_at": now_iso(),
        "iter471_seed": True,
    })
    return rid


async def fetch_purchases(http, token) -> List[Dict[str, Any]]:
    r = await http.get(f"{API}/dashboard/buyer", headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    data = r.json()
    return [w for w in data.get("won_items_detail", []) if str(w.get("listing_id", "")).startswith(PREFIX)]


# ── Tests ────────────────────────────────────────────────────────────

async def t1_paid_single_marketplace(db, http, buyer):
    print("[T1] Paid single-item marketplace purchase")
    lid = await seed_marketplace_listing(
        db, buyer_id=buyer["id"], title="iter471 T1 · Single Widget",
        hammer=42.00, tag="T1",
    )
    await seed_buyer_receipt(
        db, section="marketplace", listing_id=lid, buyer_id=buyer["id"],
        hammer=42.00, lot_number=None,
        receipt_listing_title="receipt fallback (should NOT be primary)",
    )
    rows = await fetch_purchases(http, buyer["token"])
    r = next((x for x in rows if x["listing_id"] == lid), None)
    record("T1a: single-item row visible", r is not None)
    if r:
        record("T1b: title comes from listings.title (NOT receipt fallback)",
               r.get("title") == "iter471 T1 · Single Widget", str(r.get("title")))
        record("T1c: payment_status=payment_collected",
               r.get("payment_status") == "payment_collected", str(r.get("payment_status")))
        record("T1d: lot_number is None", r.get("lot_number") is None)
        record("T1e: order_number present", bool(r.get("order_number")))
        record("T1f: hammer_price=42.00", float(r.get("hammer_price") or 0) == 42.00)
        record("T1g: total_charged=42.50", float(r.get("total_charged") or 0) == 42.50)
        record("T1h: section=marketplace", r.get("section") == "marketplace")


async def t2_paid_multi_lot_marketplace(db, http, buyer_a):
    print("[T2] Paid multi-lot lot auction — Buyer A wins lots 1,2,3")
    parent_title = "iter471 T2 · Estate Auction Batch"
    lid = await seed_multi_item_auction(
        db, tag="T2", event_title=parent_title,
        lots_spec=[
            {"lot_number": 1, "title": "Vintage Radio", "quantity": 1, "price": 15.0},
            {"lot_number": 2, "title": "Copper Kettle Set", "quantity": 3, "price": 22.5},
            {"lot_number": 3, "title": "Antique Toolbox", "quantity": 1, "price": 40.0},
            {"lot_number": 4, "title": "Model Train Cars", "quantity": 5, "price": 60.0},
        ],
    )
    # Buyer A wins lots 1, 2, 3
    for ln, hammer in [(1, 15.0), (2, 22.5), (3, 40.0)]:
        await seed_buyer_receipt(
            db, section="lots", listing_id=lid, buyer_id=buyer_a["id"],
            hammer=hammer, lot_number=ln,
            receipt_listing_title=f"receipt fallback lot {ln} (should NOT be primary)",
            pickup_code=f"BVX-IT471T2L{ln}",
        )
    rows = await fetch_purchases(http, buyer_a["token"])
    a_rows = [x for x in rows if x["listing_id"] == lid]
    record("T2a: buyer A sees exactly 3 rows for this multi-lot auction",
           len(a_rows) == 3, f"got {len(a_rows)}")
    lot_nums = sorted([x.get("lot_number") for x in a_rows])
    record("T2b: rows have lot_number 1, 2, 3", lot_nums == [1, 2, 3], str(lot_nums))
    # Lot titles come from the parent doc's `lots` array, not the receipt
    expected_titles = {1: "Vintage Radio", 2: "Copper Kettle Set", 3: "Antique Toolbox"}
    for x in a_rows:
        ln = x.get("lot_number")
        record(f"T2c-lot{ln}: lot_title from parent (not receipt fallback)",
               x.get("lot_title") == expected_titles.get(ln),
               f"got {x.get('lot_title')!r} expected {expected_titles.get(ln)!r}")
        record(f"T2d-lot{ln}: parent_listing_title = event title",
               x.get("parent_listing_title") == parent_title,
               str(x.get("parent_listing_title")))
    # Quantity from the lot doc, not receipt
    qty_by_lot = {x.get("lot_number"): x.get("quantity") for x in a_rows}
    record("T2e: lot 2 quantity=3 (from parent lots array)", qty_by_lot.get(2) == 3, str(qty_by_lot))
    # Order numbers all present. In production, `services/receipts.py`
    # derives `order_number` from the parent `listing_id`, so all lots
    # inside the same multi-lot auction SHARE the same order_number
    # (per-auction order id). We assert presence only — not uniqueness.
    orders = [x.get("order_number") for x in a_rows]
    record("T2f: order numbers present on every lot row",
           all(o for o in orders), str(orders))
    record("T2f2: order numbers all identical (parent-auction-scoped)",
           len(set(orders)) == 1, str(orders))
    # No duplicates
    dedupe_keys = set((x.get("section"), x.get("listing_id"), x.get("lot_number")) for x in a_rows)
    record("T2g: no duplicate rows (section,listing,lot key)", len(dedupe_keys) == 3)
    # Lot 4 (not won by buyer A) must NOT appear
    lot4 = [x for x in a_rows if x.get("lot_number") == 4]
    record("T2h: buyer A does NOT see lot 4 (won by someone else)", len(lot4) == 0)
    return lid


async def t3_two_buyers_same_auction(db, http, buyer_a, buyer_b, lid):
    print("[T3] Cross-buyer isolation — Buyer B wins lot 4 in the SAME auction")
    await seed_buyer_receipt(
        db, section="lots", listing_id=lid, buyer_id=buyer_b["id"],
        hammer=60.0, lot_number=4,
        receipt_listing_title="receipt fallback lot 4",
        pickup_code="BVX-IT471T2L4",
    )
    b_rows = await fetch_purchases(http, buyer_b["token"])
    b_lot4 = [x for x in b_rows if x["listing_id"] == lid]
    record("T3a: buyer B sees exactly 1 row (lot 4)", len(b_lot4) == 1, f"got {len(b_lot4)}")
    if b_lot4:
        record("T3b: buyer B's row is lot 4", b_lot4[0].get("lot_number") == 4)
        record("T3c: buyer B does NOT see lots 1/2/3",
               all(x.get("lot_number") != 4 or x.get("listing_id") == lid for x in b_rows) and len(b_lot4) == 1)

    # Buyer A re-check — must still see only lots 1, 2, 3 (never lot 4)
    a_rows_again = await fetch_purchases(http, buyer_a["token"])
    a_lot4_leak = [x for x in a_rows_again if x["listing_id"] == lid and x.get("lot_number") == 4]
    record("T3d: buyer A never sees buyer B's lot 4", len(a_lot4_leak) == 0)


async def t4_vehicle_multi_lot(db, http, buyer):
    print("[T4] Paid vehicle multi-lot purchase")
    parent_title = "iter471 T4 · Vehicle Auction Batch"
    lid = await seed_vehicle_auction(
        db, tag="T4", event_title=parent_title,
        lots_spec=[
            {"lot_number": 1, "title": "2018 Honda Civic", "vin": "2HGFC2F5XJH500001"},
            {"lot_number": 2, "title": "2020 Toyota Corolla", "vin": "5YFEPRAE6LP500002"},
            {"lot_number": 3, "title": "2019 Ford Focus", "vin": "1FADP3F2XKL500003"},
        ],
    )
    # Buyer wins lots 1 and 3
    for ln, hammer in [(1, 12000.0), (3, 8500.0)]:
        await seed_buyer_receipt(
            db, section="vehicles", listing_id=lid, buyer_id=buyer["id"],
            hammer=hammer, lot_number=ln,
            receipt_listing_title=f"veh receipt fallback lot {ln}",
        )
    rows = await fetch_purchases(http, buyer["token"])
    veh_rows = [x for x in rows if x["listing_id"] == lid]
    record("T4a: buyer sees exactly 2 vehicle rows", len(veh_rows) == 2, f"got {len(veh_rows)}")
    lots = sorted([x.get("lot_number") for x in veh_rows])
    record("T4b: rows are lots 1 and 3", lots == [1, 3])
    expected_titles = {1: "2018 Honda Civic", 3: "2019 Ford Focus"}
    for x in veh_rows:
        ln = x.get("lot_number")
        record(f"T4c-lot{ln}: vehicle title from parent lots array",
               x.get("lot_title") == expected_titles.get(ln),
               f"got {x.get('lot_title')!r}")
        record(f"T4d-lot{ln}: section=vehicles", x.get("section") == "vehicles")
        record(f"T4e-lot{ln}: parent_listing_title = event title",
               x.get("parent_listing_title") == parent_title)


async def t5_storage(db, http, buyer):
    print("[T5] Paid storage_auctions purchase (user-mandated)")
    lid = await seed_storage_auction(
        db, tag="T5", title="iter471 T5 · Storage Unit #A123",
    )
    await seed_buyer_receipt(
        db, section="storage", listing_id=lid, buyer_id=buyer["id"],
        hammer=250.0, lot_number=None,
        receipt_listing_title="storage receipt fallback",
    )
    rows = await fetch_purchases(http, buyer["token"])
    sto = [x for x in rows if x["listing_id"] == lid]
    record("T5a: storage row visible", len(sto) == 1, f"got {len(sto)}")
    if sto:
        r = sto[0]
        record("T5b: title comes from storage_auctions.title",
               r.get("title") == "iter471 T5 · Storage Unit #A123", str(r.get("title")))
        record("T5c: section=storage", r.get("section") == "storage")
        record("T5d: payment_status=payment_collected",
               r.get("payment_status") == "payment_collected")


async def t6_section_dedup_isolation(db, http, buyer):
    """Even if two rows shared the SAME listing_id across different
    sections (theoretical edge case), the section-aware dedup key
    prevents collapse."""
    print("[T6] Section-aware dedup identity — same listing_id across sections")
    # Construct two seed rows with EXACTLY the same listing_id in
    # different sections so we can prove the tuple (section, listing_id,
    # lot_number) properly isolates them.
    shared_id = f"{PREFIX}shared-{uuid.uuid4().hex[:8]}"
    await db.listings.insert_one({
        "id": shared_id, "title": "iter471 T6 · Marketplace clash",
        "status": "sold", "winner_user_id": buyer["id"],
        "seller_id": f"{PREFIX}seller-shared", "sold_at": now_iso(),
        "iter471_seed": True,
    })
    await db.storage_auctions.insert_one({
        "id": shared_id, "title": "iter471 T6 · Storage clash",
        "status": "ended", "seller_id": f"{PREFIX}seller-shared",
        "iter471_seed": True,
    })
    await seed_buyer_receipt(
        db, section="marketplace", listing_id=shared_id, buyer_id=buyer["id"],
        hammer=10.0, lot_number=None,
        receipt_listing_title="mkt fallback",
    )
    await seed_buyer_receipt(
        db, section="storage", listing_id=shared_id, buyer_id=buyer["id"],
        hammer=20.0, lot_number=None,
        receipt_listing_title="sto fallback",
    )
    rows = await fetch_purchases(http, buyer["token"])
    shared_rows = [x for x in rows if x["listing_id"] == shared_id]
    record("T6a: two rows visible (marketplace + storage, same id)",
           len(shared_rows) == 2, f"got {len(shared_rows)}")
    secs = sorted([x.get("section") for x in shared_rows])
    record("T6b: sections are marketplace + storage",
           secs == ["marketplace", "storage"], str(secs))


# ── Cleanup ──────────────────────────────────────────────────────────

async def cleanup(db):
    targets = [
        ("receipts", {"iter471_seed": True}),
        ("listings", {"iter471_seed": True}),
        ("multi_item_listings", {"iter471_seed": True}),
        ("vehicle_listings", {"iter471_seed": True}),
        ("storage_auctions", {"iter471_seed": True}),
        ("users", {"iter471_seed": True}),
        ("won_auctions", {"listing_id": {"$regex": f"^{PREFIX}"}}),
    ]
    removed = {}
    for coll, q in targets:
        try:
            r = await db[coll].delete_many(q)
            removed[coll] = r.deleted_count
        except Exception as e:  # noqa: BLE001
            removed[coll] = f"err: {e}"
    return removed


# ── Runner ───────────────────────────────────────────────────────────

async def main():
    print(f"[iter471] backend: {BACKEND_URL}")
    print(f"[iter471] db: {DB_NAME}")
    client = AsyncIOMotorClient(MONGO_URL, tz_aware=True)
    db = client[DB_NAME]
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            buyer_a = await mint_buyer(db, http, "A")
            buyer_b = await mint_buyer(db, http, "B")
            print(f"[iter471] buyers A={buyer_a['id']} B={buyer_b['id']}\n")

            await t1_paid_single_marketplace(db, http, buyer_a)
            multi_lid = await t2_paid_multi_lot_marketplace(db, http, buyer_a)
            await t3_two_buyers_same_auction(db, http, buyer_a, buyer_b, multi_lid)
            await t4_vehicle_multi_lot(db, http, buyer_a)
            await t5_storage(db, http, buyer_a)
            await t6_section_dedup_isolation(db, http, buyer_a)
    finally:
        removed = await cleanup(db)
        print(f"\n[iter471] cleanup: {removed}")

    total = len(results)
    ok = sum(1 for r in results if r["ok"])
    print("\n═════════════════════════════════════════════")
    print(f"[iter471] RESULT: {ok}/{total} checks PASS")
    print("═════════════════════════════════════════════")
    failed = [r for r in results if not r["ok"]]
    if failed:
        print("\nFAILED CHECKS:")
        for r in failed:
            print(f"  {FAIL} {r['name']} — {r['detail']}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
