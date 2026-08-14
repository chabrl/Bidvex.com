"""iter483.3 — Lot-level image upload, bid-locks, Auction Requests
Center, and admin reserve-price tests."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone

import pytest

from services import auction_requests_service as ars
from services.live_edit_service import (
    AccessDenied, Conflict, InvalidField, live_edit, get_edit_state,
    AUCTION_BID_LOCKED_FIELDS,
)

from tests.test_iter483_live_edit import (
    FakeDb, FakeCollection, SELLER, OTHER, ADMIN,
)


# ─── Extended positional-op helper ────────────────────────────────────
# The iter483 FakeCollection.update_one only knows plain $set/$push.
# Lot-level updates in iter483.3 use "lots.$.images" positional syntax.
# We patch the FakeCollection with positional-op support HERE so the
# original tests remain untouched.

def _apply_positional_set(doc: dict, filt: dict, set_dict: dict) -> None:
    """Very small subset of MongoDB positional operator support.
    Detects filter clauses like ``lots.id`` or ``lots.lot_number`` and,
    for each ``lots.$.<field>`` key in ``$set``, applies to the first
    matching lot."""
    array_field = None
    match_subfield = None
    match_value = None
    for k, v in filt.items():
        if "." in k and k.startswith("lots."):
            array_field = "lots"
            match_subfield = k.split(".", 1)[1]
            match_value = v
            break

    plain_sets, positional_sets = {}, {}
    for k, v in set_dict.items():
        if k.startswith(f"{array_field}.$.") if array_field else False:
            positional_sets[k.split(".$.", 1)[1]] = v
        else:
            plain_sets[k] = v

    if plain_sets:
        doc.update(plain_sets)

    if array_field and positional_sets and array_field in doc:
        for lot in doc[array_field]:
            if not isinstance(lot, dict):
                continue
            if lot.get(match_subfield) == match_value:
                for k, v in positional_sets.items():
                    lot[k] = v
                break


async def _patched_update_one(self: FakeCollection, filt, updates):
    for d in self._docs:
        # doc must match all filter keys except positional ones
        top_filt = {k: v for k, v in filt.items() if "." not in k}
        if not self._match(d, top_filt):
            continue
        # positional subfilter check
        pos_ok = True
        for k, v in filt.items():
            if "." in k and k.startswith("lots."):
                sub = k.split(".", 1)[1]
                if not any(l.get(sub) == v for l in (d.get("lots") or [])
                           if isinstance(l, dict)):
                    pos_ok = False
        if not pos_ok:
            continue

        if "$set" in updates:
            _apply_positional_set(d, filt, updates["$set"])
        if "$push" in updates:
            for k, v in updates["$push"].items():
                d.setdefault(k, []).append(v)
        return type("R", (), {"matched_count": 1, "modified_count": 1})()
    return type("R", (), {"matched_count": 0, "modified_count": 0})()


# Monkeypatch once — restored by pytest process teardown.
FakeCollection.update_one = _patched_update_one  # type: ignore[assignment]


# ─── Fixtures ─────────────────────────────────────────────────────────

def _make_multi(db, **kwargs):
    doc = {
        "id":        kwargs.get("id", "mi-1"),
        "seller_id": kwargs.get("seller_id", "seller-1"),
        "title":     kwargs.get("title", "Multi Auction A"),
        "description": kwargs.get("description", "Desc"),
        "status":    kwargs.get("status", "active"),
        "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
        "end_time": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
        "images": ["https://cdn/hero.jpg"],
        "lots": kwargs.get("lots", [
            {"id": "lot-a", "lot_number": 1, "title": "Bike",
             "starting_price": 20.0, "current_price": 20.0,
             "images": [], "bid_count": 0, "status": "active"},
            {"id": "lot-b", "lot_number": 2, "title": "Chair",
             "starting_price": 30.0, "current_price": 30.0,
             "images": [], "bid_count": 0, "status": "active"},
        ]),
        "bid_count": kwargs.get("bid_count", 0),
    }
    db["multi_item_listings"]._docs.append(doc)
    return doc


# ═════════════════════════════════════════════════════════════════════
#  1) Per-lot image add / remove
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_lot_image_add_by_owner_appends_and_logs():
    db = FakeDb()
    _make_multi(db)
    r = await live_edit(db, "mi-1", SELLER, "lot_image_add",
                        {"lot_id": "lot-a",
                         "image_url": "https://cdn/new-lot-a.jpg"})
    assert r["success"] is True
    assert r["lot_number"] == 1
    assert "https://cdn/new-lot-a.jpg" in r["new_value"]

    # Verify DB state
    doc = await db["multi_item_listings"].find_one({"id": "mi-1"})
    lot_a = next(l for l in doc["lots"] if l["id"] == "lot-a")
    assert "https://cdn/new-lot-a.jpg" in lot_a["images"]

    # Verify history entry captured
    assert any(h["field"] == "lot_image_add" and
               h.get("lot_number") == 1
               for h in doc.get("edited_history") or [])


@pytest.mark.asyncio
async def test_lot_image_remove_by_owner():
    db = FakeDb()
    _make_multi(db, lots=[
        {"id": "lot-a", "lot_number": 1,
         "images": ["https://cdn/keep.jpg", "https://cdn/drop.jpg"],
         "bid_count": 0, "status": "active",
         "starting_price": 20.0, "current_price": 20.0},
    ])
    r = await live_edit(db, "mi-1", SELLER, "lot_image_remove",
                        {"lot_id": "lot-a",
                         "image_url": "https://cdn/drop.jpg"})
    assert r["success"] is True
    assert "https://cdn/drop.jpg" not in r["new_value"]
    assert "https://cdn/keep.jpg" in r["new_value"]


@pytest.mark.asyncio
async def test_lot_image_add_by_non_owner_denied():
    db = FakeDb()
    _make_multi(db)
    with pytest.raises(AccessDenied):
        await live_edit(db, "mi-1", OTHER, "lot_image_add",
                        {"lot_id": "lot-a",
                         "image_url": "https://cdn/x.jpg"})


@pytest.mark.asyncio
async def test_lot_image_add_missing_lot_id():
    db = FakeDb()
    _make_multi(db)
    with pytest.raises(InvalidField):
        await live_edit(db, "mi-1", SELLER, "lot_image_add",
                        {"image_url": "https://cdn/x.jpg"})


@pytest.mark.asyncio
async def test_lot_image_add_lot_not_found():
    db = FakeDb()
    _make_multi(db)
    with pytest.raises(Exception):
        await live_edit(db, "mi-1", SELLER, "lot_image_add",
                        {"lot_id": "lot-nonexistent",
                         "image_url": "https://cdn/x.jpg"})


@pytest.mark.asyncio
async def test_lot_image_by_lot_number_fallback():
    db = FakeDb()
    _make_multi(db, lots=[
        {"lot_number": 7, "title": "no-id-lot",
         "images": [], "bid_count": 0, "status": "active",
         "starting_price": 10.0, "current_price": 10.0},
    ])
    # Pass lot_number (not lot_id) — resolver must handle it.
    r = await live_edit(db, "mi-1", SELLER, "lot_image_add",
                        {"lot_id": 7,
                         "image_url": "https://cdn/by-num.jpg"})
    assert r["lot_number"] == 7


# ═════════════════════════════════════════════════════════════════════
#  2) Bid-locked lot protection
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_lot_image_add_rejected_when_lot_has_bids():
    db = FakeDb()
    _make_multi(db, lots=[
        {"id": "lot-a", "lot_number": 1,
         "images": [], "bid_count": 3, "status": "active",
         "starting_price": 20.0, "current_price": 25.0},
    ])
    with pytest.raises(AccessDenied) as exc:
        await live_edit(db, "mi-1", SELLER, "lot_image_add",
                        {"lot_id": "lot-a",
                         "image_url": "https://cdn/x.jpg"})
    assert "lot_has_bids" in exc.value.reason


@pytest.mark.asyncio
async def test_admin_can_edit_lot_image_when_lot_has_bids():
    db = FakeDb()
    _make_multi(db, lots=[
        {"id": "lot-a", "lot_number": 1,
         "images": [], "bid_count": 5, "status": "active",
         "starting_price": 20.0, "current_price": 30.0},
    ])
    r = await live_edit(db, "mi-1", ADMIN, "lot_image_add",
                        {"lot_id": "lot-a",
                         "image_url": "https://cdn/admin-bypass.jpg"})
    assert r["success"] is True


# ═════════════════════════════════════════════════════════════════════
#  3) Auction-level bid lock (title/description/schedule/pickup/shipping)
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.parametrize("field, value", [
    ("title",       "New title with bids"),
    ("description", "New desc with bids"),
    ("schedule",    {"preview_date": "2026-09-01"}),
    ("pickup",      {"location": "New location"}),
    ("shipping",    {"available": True}),
])
async def test_auction_bid_lock_rejects_direct_edits(field, value):
    db = FakeDb()
    _make_multi(db, bid_count=2)  # top-level > 0 triggers lock
    with pytest.raises(AccessDenied) as exc:
        await live_edit(db, "mi-1", SELLER, field, value)
    assert "auction_has_bids" in exc.value.reason


@pytest.mark.asyncio
async def test_auction_bid_lock_allows_auction_level_images():
    """Images at the AUCTION level remain editable even after bids."""
    db = FakeDb()
    _make_multi(db, bid_count=1)
    r = await live_edit(db, "mi-1", SELLER, "images",
                        {"add": ["https://cdn/hero2.jpg"]})
    assert "https://cdn/hero2.jpg" in r["new_value"]


@pytest.mark.asyncio
async def test_auction_bid_lock_admin_bypass():
    db = FakeDb()
    _make_multi(db, bid_count=3)
    r = await live_edit(db, "mi-1", ADMIN, "title", "Admin new title")
    assert r["new_value"] == "Admin new title"


# ═════════════════════════════════════════════════════════════════════
#  4) get_edit_state exposes bid-count + lot lock signals
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_edit_state_reports_lot_locks_and_auction_lock():
    db = FakeDb()
    _make_multi(db, bid_count=2, lots=[
        {"id": "lot-a", "lot_number": 1, "title": "Locked",
         "bid_count": 2, "images": ["https://cdn/a.jpg"],
         "starting_price": 20.0, "current_price": 22.0,
         "status": "active"},
        {"id": "lot-b", "lot_number": 2, "title": "Free",
         "bid_count": 0, "images": [],
         "starting_price": 30.0, "current_price": 30.0,
         "status": "active"},
    ])
    s = await get_edit_state(db, "mi-1", SELLER)
    assert s["auction_locked"] is True
    assert s["bid_count"] >= 2
    assert set(s["locked_fields"]) == AUCTION_BID_LOCKED_FIELDS
    locks = {l["lot_number"]: l["locked"] for l in s["lots"]}
    assert locks == {1: True, 2: False}


# ═════════════════════════════════════════════════════════════════════
#  5) Auction Requests Service — create / list / duplicate / decide
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_reserve_price_request_and_duplicate_conflicts():
    db = FakeDb()
    _make_multi(db)
    r = await ars.create_request(
        db, "mi-1", SELLER,
        request_type="reserve_price", target="auction",
        payload={"requested_reserve_price": 150.5},
        reason="Please set the reserve at 150.50",
    )
    assert r["status"] == "pending"
    assert r["payload"]["requested_reserve_price"] == 150.5

    with pytest.raises(Conflict):
        await ars.create_request(
            db, "mi-1", SELLER,
            request_type="reserve_price", target="auction",
            payload={"requested_reserve_price": 200.0},
            reason="Duplicate should conflict here",
        )


@pytest.mark.asyncio
async def test_create_edit_request_validates_field():
    db = FakeDb()
    _make_multi(db, bid_count=1)
    with pytest.raises(InvalidField):
        await ars.create_request(
            db, "mi-1", SELLER,
            request_type="edit", target="auction",
            payload={"field_name": "not_a_field",
                     "requested_new_value": "x"},
            reason="Edit request with bad field name should fail",
        )
    ok = await ars.create_request(
        db, "mi-1", SELLER,
        request_type="edit", target="auction",
        payload={"field_name": "title",
                 "requested_new_value": "Better title please"},
        reason="Edit request with valid field name should succeed",
    )
    assert ok["payload"]["field_name"] == "title"


@pytest.mark.asyncio
async def test_create_request_reason_min_length():
    db = FakeDb()
    _make_multi(db)
    with pytest.raises(InvalidField):
        await ars.create_request(
            db, "mi-1", SELLER,
            request_type="reserve_price", target="auction",
            payload={"requested_reserve_price": 10.0},
            reason="tooshort",
        )


@pytest.mark.asyncio
async def test_create_end_time_request_via_unified_api():
    db = FakeDb()
    _make_multi(db)
    fut = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    r = await ars.create_request(
        db, "mi-1", SELLER,
        request_type="end_time", target="auction",
        payload={"requested_end_time": fut},
        reason="End time change reason at least 20 characters",
    )
    assert r["payload"]["requested_end_time"]


@pytest.mark.asyncio
async def test_admin_approve_edit_request_applies_field():
    db = FakeDb()
    _make_multi(db, bid_count=1)
    req = await ars.create_request(
        db, "mi-1", SELLER,
        request_type="edit", target="auction",
        payload={"field_name": "description",
                 "requested_new_value": "Approved description here"},
        reason="Please apply this description update please",
    )
    resolved = await ars.approve_request(
        db, req["id"], ADMIN, admin_note="Approved by test admin")
    assert resolved["status"] == "approved"

    # Verify the auction description was actually mutated
    doc = await db["multi_item_listings"].find_one({"id": "mi-1"})
    assert doc["description"] == "Approved description here"


@pytest.mark.asyncio
async def test_admin_deny_request_leaves_target_untouched():
    db = FakeDb()
    _make_multi(db)
    req = await ars.create_request(
        db, "mi-1", SELLER,
        request_type="reserve_price", target="auction",
        payload={"requested_reserve_price": 999.0},
        reason="Testing denial keeps state untouched here",
    )
    resolved = await ars.deny_request(
        db, req["id"], ADMIN, admin_note="Not this time")
    assert resolved["status"] == "denied"
    doc = await db["multi_item_listings"].find_one({"id": "mi-1"})
    # No reserve applied on deny
    assert doc.get("reserve_price") in (None, 0, 0.0)


@pytest.mark.asyncio
async def test_admin_list_requires_admin():
    db = FakeDb()
    _make_multi(db)
    with pytest.raises(AccessDenied):
        await ars.list_requests_admin(db, SELLER)


@pytest.mark.asyncio
async def test_seller_list_returns_own_requests():
    db = FakeDb()
    _make_multi(db)
    await ars.create_request(
        db, "mi-1", SELLER,
        request_type="reserve_price", target="auction",
        payload={"requested_reserve_price": 100.0},
        reason="Seller list should return this request row",
    )
    rows = await ars.list_requests_for_seller(db, "mi-1", SELLER)
    assert len(rows) >= 1
    assert rows[0]["request_type"] == "reserve_price"


# ═════════════════════════════════════════════════════════════════════
#  6) Admin reserve-price setter
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_admin_sets_lot_reserve_price():
    db = FakeDb()
    _make_multi(db)
    r = await ars.admin_set_reserve_price(
        db, "mi-1", target="lot-a",
        reserve_price_cents=25000, current_user=ADMIN)
    assert r["reserve_price"] == 250.0
    doc = await db["multi_item_listings"].find_one({"id": "mi-1"})
    lot_a = next(l for l in doc["lots"] if l["id"] == "lot-a")
    assert lot_a["reserve_price"] == 250.0


@pytest.mark.asyncio
async def test_admin_sets_auction_level_reserve():
    db = FakeDb()
    _make_multi(db)
    r = await ars.admin_set_reserve_price(
        db, "mi-1", target="auction",
        reserve_price_cents=99900, current_user=ADMIN)
    assert r["reserve_price"] == 999.0
    doc = await db["multi_item_listings"].find_one({"id": "mi-1"})
    assert doc["reserve_price"] == 999.0


@pytest.mark.asyncio
async def test_admin_clears_reserve_when_none():
    db = FakeDb()
    _make_multi(db)
    await ars.admin_set_reserve_price(
        db, "mi-1", target="auction",
        reserve_price_cents=50000, current_user=ADMIN)
    r = await ars.admin_set_reserve_price(
        db, "mi-1", target="auction",
        reserve_price_cents=None, current_user=ADMIN)
    assert r["reserve_price"] is None


@pytest.mark.asyncio
async def test_reserve_price_requires_admin():
    db = FakeDb()
    _make_multi(db)
    with pytest.raises(AccessDenied):
        await ars.admin_set_reserve_price(
            db, "mi-1", target="auction",
            reserve_price_cents=10000, current_user=SELLER)


@pytest.mark.asyncio
async def test_reserve_price_negative_rejected():
    db = FakeDb()
    _make_multi(db)
    with pytest.raises(InvalidField):
        await ars.admin_set_reserve_price(
            db, "mi-1", target="auction",
            reserve_price_cents=-1, current_user=ADMIN)
