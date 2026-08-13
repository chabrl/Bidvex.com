"""iter483 — Seller Live Auction Edit tests."""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone

import pytest

from services.live_edit_service import (
    AccessDenied, Conflict, InvalidField, NotFoundError,
    add_lot, approve_end_time_request, create_end_time_request,
    deny_end_time_request, get_edited_history, get_end_time_request,
    list_end_time_requests, live_edit, resolve_auction,
    MIN_REASON_LENGTH, PERMITTED_FIELDS, REQUEST_COLLECTION,
)


# ─── In-memory fake Motor DB ─────────────────────────────────────────

class FakeCollection:
    def __init__(self, docs=None):
        self._docs = list(docs or [])

    def _match(self, doc, filt):
        for k, v in filt.items():
            if doc.get(k) != v:
                return False
        return True

    async def find_one(self, filt, proj=None):
        for d in self._docs:
            if self._match(d, filt):
                out = dict(d)
                out.pop("_id", None)
                return out
        return None

    async def insert_one(self, doc):
        self._docs.append(dict(doc))
        return type("R", (), {"inserted_id": doc.get("id")})()

    async def insert_many(self, docs):
        for d in docs:
            self._docs.append(dict(d))

    async def update_one(self, filt, updates):
        for d in self._docs:
            if self._match(d, filt):
                if "$set" in updates:
                    d.update(updates["$set"])
                if "$push" in updates:
                    for k, v in updates["$push"].items():
                        d.setdefault(k, []).append(v)
                return type("R", (), {"matched_count": 1, "modified_count": 1})()
        return type("R", (), {"matched_count": 0, "modified_count": 0})()

    def find(self, filt=None, proj=None):
        rows = [dict(d) for d in self._docs
                if not filt or self._match(d, filt)]
        for r in rows:
            r.pop("_id", None)
        return _FakeCursor(rows)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def sort(self, key, direction=1):
        try:
            self._rows.sort(key=lambda r: r.get(key) or "",
                             reverse=(direction == -1))
        except Exception:
            pass
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    async def to_list(self, length=None):
        return list(self._rows[:length]) if length else list(self._rows)


class FakeDb(dict):
    def __getitem__(self, k):
        if k not in self:
            self[k] = FakeCollection()
        return super().__getitem__(k)

    def __getattr__(self, k):
        # Motor exposes collections as attributes.
        if k.startswith("_") or k in ("keys", "values", "items"):
            raise AttributeError(k)
        return self[k]


SELLER = {"id": "seller-1", "email": "s@x.com"}
OTHER  = {"id": "other-1",  "email": "o@x.com"}
ADMIN  = {"id": "admin-1",  "email": "a@x.com", "role": "super_admin"}


def _make_active_listing(db, coll="multi_item_listings", **kwargs):
    doc = {
        "id": kwargs.get("id", "auc-1"),
        "seller_id": kwargs.get("seller_id", "seller-1"),
        "title": kwargs.get("title", "Original Title"),
        "description": kwargs.get("description", "Original desc"),
        "status": kwargs.get("status", "active"),
        "auction_end_date": kwargs.get(
            "auction_end_date",
            (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()),
        "images": kwargs.get("images", ["https://cdn/x.jpg"]),
        "lots": kwargs.get("lots", [
            {"lot_number": 1, "title": "Lot A", "status": "active",
             "starting_price": 10.0, "current_price": 15.0},
        ]),
    }
    db[coll]._docs.append(doc)
    return doc


# ═════════════════════════════════════════════════════════════════════
#  Resolution + permission
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_resolve_across_collections():
    db = FakeDb()
    _make_active_listing(db, coll="vehicle_listings", id="veh-1")
    coll, doc = await resolve_auction(db, "veh-1")
    assert coll == "vehicle_listings"
    assert doc["id"] == "veh-1"


@pytest.mark.asyncio
async def test_resolve_not_found_raises():
    db = FakeDb()
    with pytest.raises(NotFoundError):
        await resolve_auction(db, "nope")


@pytest.mark.asyncio
async def test_seller_edit_denied_for_non_owner():
    db = FakeDb()
    _make_active_listing(db)
    with pytest.raises(AccessDenied):
        await live_edit(db, "auc-1", OTHER, "title", "hack")


@pytest.mark.asyncio
async def test_seller_edit_denied_when_status_not_active():
    db = FakeDb()
    _make_active_listing(db, status="closed")
    with pytest.raises(AccessDenied) as exc:
        await live_edit(db, "auc-1", SELLER, "title", "new")
    assert "active" in exc.value.reason.lower()


@pytest.mark.asyncio
async def test_admin_edit_allowed_on_any_status():
    db = FakeDb()
    _make_active_listing(db, status="closed")
    r = await live_edit(db, "auc-1", ADMIN, "title", "admin new")
    assert r["new_value"] == "admin new"


@pytest.mark.asyncio
async def test_unauthenticated_denied():
    db = FakeDb()
    _make_active_listing(db)
    with pytest.raises(AccessDenied):
        await live_edit(db, "auc-1", None, "title", "x")


# ═════════════════════════════════════════════════════════════════════
#  Title / description
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_title_edit_updates_and_logs():
    db = FakeDb()
    _make_active_listing(db)
    r = await live_edit(db, "auc-1", SELLER, "title", "Brand New Title")
    assert r["new_value"] == "Brand New Title"
    doc = await db["multi_item_listings"].find_one({"id": "auc-1"})
    assert doc["title"] == "Brand New Title"
    hist = doc["edited_history"]
    assert len(hist) == 1
    assert hist[0]["field"] == "title"
    assert hist[0]["old_value"] == "Original Title"
    assert hist[0]["new_value"] == "Brand New Title"
    assert hist[0]["edited_by"] == SELLER["id"]


@pytest.mark.asyncio
async def test_title_edit_rejects_empty():
    db = FakeDb()
    _make_active_listing(db)
    with pytest.raises(InvalidField):
        await live_edit(db, "auc-1", SELLER, "title", "   ")


@pytest.mark.asyncio
async def test_description_edit_and_log():
    db = FakeDb()
    _make_active_listing(db)
    await live_edit(db, "auc-1", SELLER, "description", "Longer new desc")
    doc = await db["multi_item_listings"].find_one({"id": "auc-1"})
    assert doc["description"] == "Longer new desc"
    fields = [h["field"] for h in doc["edited_history"]]
    assert "description" in fields


# ═════════════════════════════════════════════════════════════════════
#  Images
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_images_add_and_remove():
    db = FakeDb()
    _make_active_listing(db)
    await live_edit(db, "auc-1", SELLER, "images",
                    {"add": ["https://cdn/y.jpg"]})
    doc = await db["multi_item_listings"].find_one({"id": "auc-1"})
    assert "https://cdn/y.jpg" in doc["images"]
    await live_edit(db, "auc-1", SELLER, "images",
                    {"remove": ["https://cdn/x.jpg"]})
    doc = await db["multi_item_listings"].find_one({"id": "auc-1"})
    assert "https://cdn/x.jpg" not in doc["images"]


@pytest.mark.asyncio
async def test_images_reorder():
    db = FakeDb()
    _make_active_listing(db, images=["a.jpg", "b.jpg", "c.jpg"])
    await live_edit(db, "auc-1", SELLER, "images",
                    {"reorder": ["c.jpg", "a.jpg", "b.jpg"]})
    doc = await db["multi_item_listings"].find_one({"id": "auc-1"})
    assert doc["images"] == ["c.jpg", "a.jpg", "b.jpg"]


@pytest.mark.asyncio
async def test_images_reorder_rejects_injection():
    db = FakeDb()
    _make_active_listing(db, images=["a.jpg", "b.jpg"])
    await live_edit(db, "auc-1", SELLER, "images",
                    {"reorder": ["a.jpg", "evil.jpg"]})
    doc = await db["multi_item_listings"].find_one({"id": "auc-1"})
    assert "evil.jpg" not in doc["images"]


# ═════════════════════════════════════════════════════════════════════
#  Schedule / pickup / shipping
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_schedule_edit():
    db = FakeDb()
    _make_active_listing(db)
    r = await live_edit(db, "auc-1", SELLER, "schedule",
        {"preview_date": "2026-08-20", "preview_time": "10:00",
         "location": "123 Main", "unknown": "dropped"})
    assert "unknown" not in r["new_value"]
    assert r["new_value"]["location"] == "123 Main"


@pytest.mark.asyncio
async def test_pickup_edit():
    db = FakeDb()
    _make_active_listing(db)
    r = await live_edit(db, "auc-1", SELLER, "pickup",
        {"location": "Sherbrooke QC",
         "window_start": "2026-08-25T10:00",
         "window_end":   "2026-08-25T14:00",
         "instructions": "Buzz #4"})
    assert r["new_value"]["location"] == "Sherbrooke QC"


@pytest.mark.asyncio
async def test_shipping_edit_marks_estimate_only():
    db = FakeDb()
    _make_active_listing(db)
    r = await live_edit(db, "auc-1", SELLER, "shipping",
        {"available": True, "notes": "Ships FedEx Ground",
         "estimated_cost": 25.50, "carrier": "FedEx"})
    assert r["new_value"]["is_estimate_only"] is True
    assert r["new_value"]["estimated_cost"] == "25.5"


@pytest.mark.asyncio
async def test_invalid_field_rejected():
    db = FakeDb()
    _make_active_listing(db)
    with pytest.raises(InvalidField):
        await live_edit(db, "auc-1", SELLER, "hammer_price", 999)


# ═════════════════════════════════════════════════════════════════════
#  Add lot
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_add_lot_appends_as_draft_and_pending():
    db = FakeDb()
    _make_active_listing(db)
    r = await add_lot(db, "auc-1", SELLER, {
        "title": "New Chair", "description": "Wooden",
        "quantity": 2, "starting_price": 20.0,
        "category": "furniture", "condition": "good",
    })
    assert r["lot"]["status"] == "draft"
    assert r["lot"]["moderation_status"] == "pending_admin_review"
    assert r["lot"]["lot_number"] == 2
    doc = await db["multi_item_listings"].find_one({"id": "auc-1"})
    assert len(doc["lots"]) == 2
    # Existing lot untouched
    assert doc["lots"][0]["current_price"] == 15.0


@pytest.mark.asyncio
async def test_add_lot_strips_forbidden_fields():
    db = FakeDb()
    _make_active_listing(db)
    r = await add_lot(db, "auc-1", SELLER, {
        "title": "Sneaky", "hammer_price": 999,
        "winner_user_id": "hacker", "current_price": 500,
    })
    lot = r["lot"]
    # Sneaky attempt to inject financial state is stripped
    assert "hammer_price" not in lot
    assert "winner_user_id" not in lot
    # current_price defaults to starting_price (0 here) — service default
    assert lot["current_price"] in (0, "0")


@pytest.mark.asyncio
async def test_add_lot_denied_non_owner():
    db = FakeDb()
    _make_active_listing(db)
    with pytest.raises(AccessDenied):
        await add_lot(db, "auc-1", OTHER, {"title": "x"})


@pytest.mark.asyncio
async def test_add_lot_history_entry():
    db = FakeDb()
    _make_active_listing(db)
    await add_lot(db, "auc-1", SELLER, {"title": "Extra"})
    doc = await db["multi_item_listings"].find_one({"id": "auc-1"})
    hist = doc["edited_history"]
    assert any(h["field"] == "lot_added" for h in hist)


# ═════════════════════════════════════════════════════════════════════
#  End-time request flow
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_end_time_request_created_pending():
    db = FakeDb()
    _make_active_listing(db)
    future = datetime.now(timezone.utc) + timedelta(days=5)
    r = await create_end_time_request(
        db, "auc-1", SELLER, future,
        "We need more time for buyer inspections this week")
    assert r["status"] == "pending"
    assert r["auction_id"] == "auc-1"
    # Admin alert email queued
    ob = await db.email_outbox.find_one({"kind": "end_time_request_submitted_admin"})
    assert ob is not None
    assert ob["dedupe_key"] == f"etr_admin_{r['id']}"


@pytest.mark.asyncio
async def test_end_time_request_reason_min_length():
    db = FakeDb()
    _make_active_listing(db)
    future = datetime.now(timezone.utc) + timedelta(days=5)
    with pytest.raises(InvalidField):
        await create_end_time_request(db, "auc-1", SELLER, future, "short")


@pytest.mark.asyncio
async def test_end_time_request_must_be_future():
    db = FakeDb()
    _make_active_listing(db)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    with pytest.raises(InvalidField):
        await create_end_time_request(
            db, "auc-1", SELLER, past,
            "We need more time for buyer inspections this week")


@pytest.mark.asyncio
async def test_only_one_pending_end_time_request_per_auction():
    db = FakeDb()
    _make_active_listing(db)
    future = datetime.now(timezone.utc) + timedelta(days=5)
    reason = "A" * 30
    await create_end_time_request(db, "auc-1", SELLER, future, reason)
    with pytest.raises(Conflict):
        await create_end_time_request(db, "auc-1", SELLER, future, reason)


@pytest.mark.asyncio
async def test_end_time_request_approve_updates_auction():
    db = FakeDb()
    _make_active_listing(db)
    future = datetime.now(timezone.utc) + timedelta(days=5)
    reason = "A" * 30
    r = await create_end_time_request(db, "auc-1", SELLER, future, reason)
    approve = await approve_end_time_request(
        db, r["id"], ADMIN, "Approved — good reason")
    assert approve["status"] == "approved"

    # Auction end time updated
    doc = await db["multi_item_listings"].find_one({"id": "auc-1"})
    assert doc["auction_end_date"] == future.isoformat()
    assert doc["end_time"] == future.isoformat()
    assert doc["soft_close_reset_by_request_id"] == r["id"]
    # Seller email queued (idempotent)
    ob = await db.email_outbox.find_one(
        {"kind": "end_time_request_approved_seller"})
    assert ob is not None
    # Approving again → 409
    with pytest.raises(Conflict):
        await approve_end_time_request(db, r["id"], ADMIN, "again")


@pytest.mark.asyncio
async def test_end_time_request_deny_leaves_end_time_alone():
    db = FakeDb()
    _make_active_listing(db)
    original_end = (await db["multi_item_listings"].find_one(
        {"id": "auc-1"}))["auction_end_date"]
    future = datetime.now(timezone.utc) + timedelta(days=5)
    r = await create_end_time_request(db, "auc-1", SELLER, future, "A" * 30)
    deny = await deny_end_time_request(
        db, r["id"], ADMIN, "Denied — not enough notice")
    assert deny["status"] == "denied"
    doc = await db["multi_item_listings"].find_one({"id": "auc-1"})
    assert doc["auction_end_date"] == original_end
    # Seller email queued
    ob = await db.email_outbox.find_one(
        {"kind": "end_time_request_denied_seller"})
    assert ob is not None


@pytest.mark.asyncio
async def test_admin_approve_denied_for_non_admin():
    db = FakeDb()
    _make_active_listing(db)
    future = datetime.now(timezone.utc) + timedelta(days=5)
    r = await create_end_time_request(db, "auc-1", SELLER, future, "A" * 30)
    with pytest.raises(AccessDenied):
        await approve_end_time_request(db, r["id"], SELLER, None)


@pytest.mark.asyncio
async def test_list_end_time_requests_admin_only():
    db = FakeDb()
    _make_active_listing(db)
    future = datetime.now(timezone.utc) + timedelta(days=5)
    await create_end_time_request(db, "auc-1", SELLER, future, "A" * 30)
    with pytest.raises(AccessDenied):
        await list_end_time_requests(db, SELLER)
    rows = await list_end_time_requests(db, ADMIN, status="pending")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_get_end_time_request_denied_for_non_owner():
    db = FakeDb()
    _make_active_listing(db)
    future = datetime.now(timezone.utc) + timedelta(days=5)
    await create_end_time_request(db, "auc-1", SELLER, future, "A" * 30)
    with pytest.raises(AccessDenied):
        await get_end_time_request(db, "auc-1", OTHER)


# ═════════════════════════════════════════════════════════════════════
#  edited_history reader
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_edited_history_seller_reads_own():
    db = FakeDb()
    _make_active_listing(db)
    await live_edit(db, "auc-1", SELLER, "title", "T1")
    await live_edit(db, "auc-1", SELLER, "title", "T2")
    hist = await get_edited_history(db, "auc-1", SELLER)
    assert len(hist) == 2
    # Immutable ordering — old_value chain intact
    assert hist[0]["new_value"] == "T1"
    assert hist[1]["old_value"] == "T1"
    assert hist[1]["new_value"] == "T2"


@pytest.mark.asyncio
async def test_edited_history_admin_reads_any():
    db = FakeDb()
    _make_active_listing(db)
    await live_edit(db, "auc-1", SELLER, "title", "T")
    hist = await get_edited_history(db, "auc-1", ADMIN)
    assert len(hist) == 1


@pytest.mark.asyncio
async def test_edited_history_non_owner_denied():
    db = FakeDb()
    _make_active_listing(db)
    with pytest.raises(AccessDenied):
        await get_edited_history(db, "auc-1", OTHER)


# ═════════════════════════════════════════════════════════════════════
#  HTTP end-to-end
# ═════════════════════════════════════════════════════════════════════

import httpx

_API = os.environ.get("REACT_APP_BACKEND_URL")
if not _API:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    _API = line.split("=", 1)[1].strip()
                    break
    except FileNotFoundError:
        _API = None


async def _login(email: str, password: str):
    async with httpx.AsyncClient(base_url=_API, timeout=15.0) as c:
        r = await c.post("/api/auth/login",
                          json={"email": email, "password": password})
        if r.status_code == 429:
            pytest.skip("auth rate-limited")
        r.raise_for_status()
        return r.json()["access_token"]


async def _ensure_seed_listing() -> str:
    """Seed the same listing used by the CSV export tests."""
    import os as _os
    from dotenv import load_dotenv
    from motor.motor_asyncio import AsyncIOMotorClient
    load_dotenv()
    client = AsyncIOMotorClient(_os.environ["MONGO_URL"])
    db = client[_os.environ["DB_NAME"]]
    seller = await db.users.find_one({"email": "testseller@bidvex.com"},
                                     {"_id": 0, "id": 1})
    if not seller:
        pytest.skip("testseller not seeded — run iter308_reseed_test_fixtures")
    await db.multi_item_listings.update_one(
        {"id": "iter482csv-seller-owned-test"},
        {"$set": {"status": "active", "seller_id": seller["id"]}},
    )
    # Ensure the listing exists (it should — seeded during iter482+ CSV run)
    exists = await db.multi_item_listings.find_one(
        {"id": "iter482csv-seller-owned-test"}, {"_id": 0, "id": 1})
    if not exists:
        pytest.skip("iter482csv-seller-owned-test listing missing")
    return "iter482csv-seller-owned-test"


@pytest.mark.asyncio
@pytest.mark.skipif(not _API, reason="No backend URL")
async def test_http_live_edit_title_by_owner():
    listing_id = await _ensure_seed_listing()
    tok = await _login("testseller@bidvex.com", "TestSeller2026!")
    async with httpx.AsyncClient(base_url=_API, timeout=15.0) as c:
        r = await c.patch(f"/api/auctions/{listing_id}/live-edit",
            json={"field": "title", "value": "Live edit title check"},
            headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200, r.text
        assert r.json()["new_value"] == "Live edit title check"


@pytest.mark.asyncio
@pytest.mark.skipif(not _API, reason="No backend URL")
async def test_http_live_edit_denies_non_owner():
    listing_id = await _ensure_seed_listing()
    tok = await _login("testbuyer@bidvex.com", "TestBuyer2026!")
    async with httpx.AsyncClient(base_url=_API, timeout=15.0) as c:
        r = await c.patch(f"/api/auctions/{listing_id}/live-edit",
            json={"field": "title", "value": "hack"},
            headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 403


@pytest.mark.asyncio
@pytest.mark.skipif(not _API, reason="No backend URL")
async def test_http_live_edit_unauth_401():
    async with httpx.AsyncClient(base_url=_API, timeout=15.0) as c:
        r = await c.patch("/api/auctions/some-id/live-edit",
            json={"field": "title", "value": "x"})
        assert r.status_code == 401


@pytest.mark.asyncio
@pytest.mark.skipif(not _API, reason="No backend URL")
async def test_http_end_time_request_flow():
    listing_id = await _ensure_seed_listing()
    tok = await _login("testseller@bidvex.com", "TestSeller2026!")
    from datetime import timezone as _tz
    future = (datetime.now(_tz.utc) + timedelta(days=10)).isoformat()
    async with httpx.AsyncClient(base_url=_API, timeout=15.0) as c:
        # Clear any prior pending request (idempotent by seeding admin denies)
        # Fresh POST — expect 200 or 409 depending on prior test state
        r = await c.post(f"/api/auctions/{listing_id}/end-time-request",
            json={"requested_end_time": future,
                  "reason": "Buyers need more time for inspection this week"},
            headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code in (200, 409), r.text

        # GET is always 200 (or 200 with None)
        rr = await c.get(f"/api/auctions/{listing_id}/end-time-request",
            headers={"Authorization": f"Bearer {tok}"})
        assert rr.status_code == 200
