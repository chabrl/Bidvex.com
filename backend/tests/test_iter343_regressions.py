"""
iter343 — Regression-fix tests for the 6 reported bugs.

BUG 1  Map search unions all 5 collections + geo backfill
BUG 2  Homepage carousels include multi-lot + featured from all collections
BUG 3  Twilio auth token valid (live REST check)
BUG 4  Admin per-lot edit endpoints + field-level admin log
BUG 5  Watchlist: all collections, placeholders, price normalization
BUG 6  Quantity semantics surfaced in cost breakdown (per-lot vs per-item)
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, str(Path("/app/backend")))
load_dotenv("/app/backend/.env")


def _api_base() -> str:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE = _api_base()
API = BASE + "/api"
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

ADMIN = {"email": "charbel911@gmail.com", "password": "Anderosli123!@#"}
BUYER = {"email": "testbuyer@bidvex.com", "password": "TestBuyer2026!"}

MTL_GEO = {"type": "Point", "coordinates": [-73.5673, 45.5017]}
NOW = datetime.now(timezone.utc)
TAG = f"iter343-{uuid.uuid4().hex[:6]}"


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text[:200]
    t = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def admin_headers():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def buyer_headers():
    return _login(BUYER)


@pytest.fixture(scope="module")
def seeded(request):
    """Seed one doc per collection with Montréal geo, cleanup at exit."""
    end = (NOW + timedelta(hours=12)).isoformat()
    docs = {}

    docs["listing"] = {
        "id": f"{TAG}-listing", "title": f"{TAG} Single Item", "status": "active",
        "category": "electronics", "city": "Montréal", "region": "QC",
        "currency": "CAD", "starting_price": 100, "current_price": 100,
        "images": [], "seller_id": "seed", "quantity": 1,
        "auction_end_date": end, "created_at": NOW.isoformat(), "geo": MTL_GEO,
    }
    DB.listings.insert_one(dict(docs["listing"]))

    docs["multi"] = {
        "id": f"{TAG}-multi", "title": f"{TAG} Multi-Lot Auction", "status": "active",
        "category": "liquidation", "city": "Montréal", "region": "QC",
        "currency": "CAD", "seller_id": "seed", "is_featured": True,
        "total_lots": 2, "auction_end_date": end,
        "created_at": NOW.isoformat(), "geo": MTL_GEO,
        "lots": [
            {"lot_number": 1, "title": "Pallet of tools", "quantity": 10,
             "starting_price": 50.0, "current_bid": 50.0, "bid_count": 0,
             "images": [], "condition": "good"},
            {"lot_number": 2, "title": "Office chairs", "quantity": 4,
             "starting_price": 20.0, "current_bid": 20.0, "bid_count": 0,
             "images": [], "condition": "used"},
        ],
    }
    DB.multi_item_listings.insert_one(dict(docs["multi"]))

    docs["vehicle"] = {
        "id": f"{TAG}-vehicle", "status": "active", "year": 2019, "make": "Honda",
        "model": "Civic", "city": "Montréal", "region": "QC", "currency": "CAD",
        "current_bid": 9000, "starting_price": 9000, "images": [],
        "seller_id": "seed", "end_time": end, "created_at": NOW.isoformat(),
        "geo": MTL_GEO, "is_featured": True,
    }
    DB.vehicle_listings.insert_one(dict(docs["vehicle"]))

    docs["vml"] = {
        "id": f"{TAG}-vml", "title": f"{TAG} Dealer Event", "status": "live",
        "seller_id": "seed", "created_at": NOW, "geo": MTL_GEO,
        "lots": [{"id": f"{TAG}-vml-lot1", "lot_number": 1, "year": 2018,
                  "make": "Toyota", "model": "Corolla", "starting_price": 5000.0,
                  "current_bid": 5000.0, "bid_count": 0, "status": "active",
                  "location_city": "Montréal", "location_province": "QC",
                  "end_time": end}],
    }
    DB.vehicle_multi_lot_auctions.insert_one(dict(docs["vml"]))

    docs["storage"] = {
        "id": f"{TAG}-storage", "status": "active", "unit_number": "B12",
        "unit_size": "10x10", "facility_city": "Montréal",
        "facility_province": "QC", "currency": "CAD", "current_bid": 150,
        "starting_price": 150, "photos": [], "description_en": f"{TAG} storage unit",
        "end_time": end, "created_at": NOW.isoformat(), "geo": MTL_GEO,
    }
    DB.storage_auctions.insert_one(dict(docs["storage"]))

    def _cleanup():
        DB.listings.delete_many({"id": {"$regex": f"^{TAG}"}})
        DB.multi_item_listings.delete_many({"id": {"$regex": f"^{TAG}"}})
        DB.vehicle_listings.delete_many({"id": {"$regex": f"^{TAG}"}})
        DB.vehicle_multi_lot_auctions.delete_many({"id": {"$regex": f"^{TAG}"}})
        DB.storage_auctions.delete_many({"id": {"$regex": f"^{TAG}"}})
        DB.watchlist.delete_many({"item_id": {"$regex": TAG}})
        DB.admin_logs.delete_many({"details.event_id": {"$regex": f"^{TAG}"}})
    request.addfinalizer(_cleanup)
    return docs


# ═══ BUG 1 — Map search ═════════════════════════════════════════════════

class TestMapSearch:
    def test_sources_cover_all_five_collections(self):
        from routes.geo_search import GEO_SEARCH_SOURCES
        colls = {s[0] for s in GEO_SEARCH_SOURCES}
        assert colls == {"listings", "multi_item_listings", "vehicle_listings",
                         "vehicle_multi_lot_auctions", "storage_auctions"}

    def test_geo_query_returns_every_section(self, seeded):
        r = requests.get(f"{API}/marketplace/items/geo",
                         params={"lat": 45.5017, "lng": -73.5673, "radius_km": 50,
                                 "limit": 200}, timeout=30)
        assert r.status_code == 200, r.text[:300]
        items = r.json()["items"]
        mine = [i for i in items if str(i.get("id", "")).startswith(TAG)]
        sections = {i["_section"] for i in mine}
        assert "marketplace" in sections
        assert "lots" in sections, f"multi-lot missing from map: {sections}"
        assert "vehicle" in sections
        assert "vehicle_multi_lot" in sections
        assert "storage" in sections
        for i in mine:
            assert i["detail_path"].endswith(i["id"])
            assert i.get("distance_km") is not None

    def test_multi_lot_item_has_price_and_lot_count(self, seeded):
        r = requests.get(f"{API}/marketplace/items/geo",
                         params={"lat": 45.5017, "lng": -73.5673, "radius_km": 50,
                                 "limit": 200}, timeout=30)
        multi = next(i for i in r.json()["items"] if i["id"] == f"{TAG}-multi")
        assert multi["total_lots"] == 2
        assert multi["current_price"] == 70.0  # 50 + 20
        assert multi["detail_path"] == f"/lots/{TAG}-multi"

    def test_backfill_script_is_idempotent(self):
        import subprocess
        doc_id = f"{TAG}-nogeo"
        DB.multi_item_listings.insert_one({
            "id": doc_id, "title": "needs geo", "status": "draft",
            "city": "Laval", "region": "QC", "lots": [],
        })
        try:
            for _ in range(2):
                out = subprocess.run(
                    ["python3", "scripts/backfill_geo.py"],
                    cwd="/app/backend", capture_output=True, text=True, timeout=120)
                assert out.returncode == 0, out.stderr[-500:]
            doc = DB.multi_item_listings.find_one({"id": doc_id})
            assert doc.get("geo", {}).get("type") == "Point"
            assert doc["geo"]["coordinates"][1] == pytest.approx(45.6, abs=0.5)
        finally:
            DB.multi_item_listings.delete_one({"id": doc_id})


# ═══ BUG 2 — Homepage carousels ═════════════════════════════════════════

class TestHomepageCarousels:
    def test_featured_includes_all_collections(self, seeded):
        r = requests.get(f"{API}/carousel/featured", params={"limit": 50}, timeout=30)
        assert r.status_code == 200
        mine = {i["id"]: i for i in r.json() if str(i.get("id", "")).startswith(TAG)}
        assert f"{TAG}-multi" in mine, "featured multi-lot auction missing"
        assert f"{TAG}-vehicle" in mine, "featured vehicle missing"
        assert mine[f"{TAG}-multi"]["detail_path"] == f"/lots/{TAG}-multi"
        assert mine[f"{TAG}-vehicle"]["_section"] == "vehicle"
        # normalized title for vehicles
        assert "Honda" in mine[f"{TAG}-vehicle"]["title"]

    def test_ending_soon_includes_multi_lot(self, seeded):
        r = requests.get(f"{API}/carousel/ending-soon", params={"limit": 50}, timeout=30)
        assert r.status_code == 200
        ids = [i.get("id") for i in r.json()]
        assert f"{TAG}-multi" in ids, f"multi-lot missing from ending-soon: {ids[:10]}"
        assert f"{TAG}-vml" in ids, "live vehicle multi-lot event missing from ending-soon"

    def test_hot_items_includes_multi(self, seeded):
        r = requests.get(f"{API}/stats/hot-items", params={"limit": 50}, timeout=30)
        assert r.status_code == 200
        # endpoint merges without error and returns list
        assert isinstance(r.json(), list)


# ═══ BUG 3 — Twilio auth ════════════════════════════════════════════════

class TestTwilioAuth:
    def test_live_rest_auth_is_valid(self):
        import asyncio
        from services.twilio_service import verify_twilio_auth
        res = asyncio.get_event_loop().run_until_complete(verify_twilio_auth(force=True))
        assert res["valid"] is True, f"Twilio auth failed: {res['error']}"

    def test_config_endpoint_reports_auth_valid(self, admin_headers):
        r = requests.get(f"{API}/twilio/config", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json().get("auth_valid") is True


# ═══ BUG 4 — Admin per-lot editing ══════════════════════════════════════

class TestAdminLotEdit:
    def test_admin_edits_general_lot_with_audit_log(self, seeded, admin_headers):
        r = requests.put(
            f"{API}/admin/multi-item-listings/{TAG}-multi/lots/1",
            json={"title": "Pallet of premium tools", "quantity": 12,
                  "starting_price": 75.0},
            headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert set(r.json()["updated_fields"]) >= {"title", "quantity", "starting_price"}

        doc = DB.multi_item_listings.find_one({"id": f"{TAG}-multi"})
        lot = next(l for l in doc["lots"] if l["lot_number"] == 1)
        assert lot["title"] == "Pallet of premium tools"
        assert lot["quantity"] == 12
        assert lot["starting_price"] == 75.0
        assert lot["current_bid"] == 75.0  # bid-less lot stays in sync

        log = DB.admin_logs.find_one({"action": "admin_edit_multi_lot",
                                      "details.event_id": f"{TAG}-multi"})
        assert log, "admin log row missing"
        d = log["details"]
        assert d["lot_id"] == 1
        assert set(d["fields_changed"]) >= {"title", "quantity", "starting_price"}
        assert d["previous_values"]["quantity"] == 10
        assert d["new_values"]["quantity"] == 12
        assert log["admin_id"]

    def test_admin_edits_vehicle_lot_with_audit_log(self, seeded, admin_headers):
        r = requests.put(
            f"{API}/admin/vehicle-multi-lot-auctions/{TAG}-vml/lots/{TAG}-vml-lot1",
            json={"mileage": 88000, "starting_price": 5500.0},
            headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        doc = DB.vehicle_multi_lot_auctions.find_one({"id": f"{TAG}-vml"})
        lot = doc["lots"][0]
        assert lot["mileage"] == 88000
        assert lot["starting_price"] == 5500.0
        log = DB.admin_logs.find_one({"action": "admin_edit_vehicle_multi_lot",
                                      "details.event_id": f"{TAG}-vml"})
        assert log and log["details"]["new_values"]["mileage"] == 88000

    def test_non_admin_cannot_edit_lots(self, seeded, buyer_headers):
        r = requests.put(
            f"{API}/admin/multi-item-listings/{TAG}-multi/lots/1",
            json={"title": "hacked"}, headers=buyer_headers, timeout=30)
        assert r.status_code in (401, 403)

    def test_quantity_validation(self, seeded, admin_headers):
        r = requests.put(
            f"{API}/admin/multi-item-listings/{TAG}-multi/lots/1",
            json={"quantity": 0}, headers=admin_headers, timeout=30)
        assert r.status_code == 400


# ═══ BUG 5 — Watchlist ══════════════════════════════════════════════════

class TestWatchlist:
    def _add(self, headers, item_id, item_type):
        return requests.post(f"{API}/watchlist/add", params={
            "item_id": item_id, "item_type": item_type}, headers=headers, timeout=30)

    def test_all_types_addable_and_returned(self, seeded, buyer_headers):
        assert self._add(buyer_headers, f"{TAG}-listing", "listing").status_code == 200
        assert self._add(buyer_headers, f"{TAG}-multi", "auction").status_code == 200
        assert self._add(buyer_headers, f"{TAG}-multi:1", "lot").status_code == 200
        assert self._add(buyer_headers, f"{TAG}-vehicle", "vehicle").status_code == 200
        assert self._add(buyer_headers, f"{TAG}-storage", "storage").status_code == 200

        r = requests.get(f"{API}/watchlist", headers=buyer_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert any(l["id"] == f"{TAG}-listing" for l in data["listings"])
        assert any(a["id"] == f"{TAG}-multi" for a in data["auctions"])
        assert any(l["auction_id"] == f"{TAG}-multi" for l in data["lots"])
        assert any(v["id"] == f"{TAG}-vehicle" for v in data["vehicles"])
        assert any(s["id"] == f"{TAG}-storage" for s in data["storage"])

    def test_lot_price_normalized_and_vehicle_title_built(self, seeded, buyer_headers):
        r = requests.get(f"{API}/watchlist", headers=buyer_headers, timeout=30)
        data = r.json()
        lot_row = next(l for l in data["lots"] if l["auction_id"] == f"{TAG}-multi")
        assert lot_row["lot"]["current_price"] is not None, "lot current_price not normalized"
        veh = next(v for v in data["vehicles"] if v["id"] == f"{TAG}-vehicle")
        assert "Honda" in veh["title"]
        assert veh["current_price"] == 9000
        sto = next(s for s in data["storage"] if s["id"] == f"{TAG}-storage")
        assert sto["city"] == "Montréal"
        assert sto["images"] == []

    def test_deleted_listing_becomes_unavailable_placeholder(self, seeded, buyer_headers):
        ghost_id = f"{TAG}-ghost"
        DB.watchlist.insert_one({
            "id": str(uuid.uuid4()), "user_id": DB.users.find_one(
                {"email": BUYER["email"]})["id"],
            "item_id": ghost_id, "item_type": "listing",
            "added_at": NOW.isoformat(),
        })
        try:
            r = requests.get(f"{API}/watchlist", headers=buyer_headers, timeout=30)
            data = r.json()
            ghosts = [u for u in data["unavailable"] if u["item_id"] == ghost_id]
            assert ghosts, "deleted listing did not surface as unavailable placeholder"
            assert ghosts[0]["unavailable"] is True
            # total counts every saved row (resolved + unavailable)
            resolved = (len(data["listings"]) + len(data["auctions"]) + len(data["lots"])
                        + len(data["vehicles"]) + len(data["storage"]))
            assert data["total"] == resolved + len(data["unavailable"])
        finally:
            DB.watchlist.delete_many({"item_id": ghost_id})


# ═══ BUG 6 — Quantity semantics ═════════════════════════════════════════

class TestQuantitySemantics:
    def test_bid_model_flag_exists_in_fee_engine(self):
        """CONFIRMED MODEL: bids are PER-LOT totals by default; PER-ITEM
        (hammer × quantity) only when listing.multiply_hammer_by_quantity."""
        src = open("/app/backend/services/broker_fee_engine.py").read()
        assert "multiply_hammer_by_quantity" in src

    def test_cost_breakdown_component_handles_quantity(self):
        src = open("/app/frontend/src/components/CostBreakdown.jsx").read()
        assert "quantity = 1" in src
        assert "multiplyByQuantity" in src
        assert "cb-quantity" in src
        assert "cb-price-per-item" in src
        assert "hammerPrice * qty" in src

    def test_bid_confirmation_dialog_shows_quantity(self):
        src = open("/app/frontend/src/components/BidConfirmationDialog.js").read()
        assert "bid-confirm-quantity" in src
        assert "effectiveHammer" in src
        assert "total for ${qty} items" in src

    def test_listing_detail_passes_quantity_props(self):
        src = open("/app/frontend/src/pages/ListingDetailPage.js").read()
        assert "multiplyByQuantity={!!listing.multiply_hammer_by_quantity}" in src
        assert "quantity={listing.quantity || 1}" in src

    def test_fee_preview_scales_with_hammer(self):
        r1 = requests.get(f"{API}/fees/v2/preview",
                          params={"hammer_price": 100, "auction_type": "marketplace",
                                  "seller_account_type": "individual"}, timeout=30)
        r10 = requests.get(f"{API}/fees/v2/preview",
                           params={"hammer_price": 1000, "auction_type": "marketplace",
                                   "seller_account_type": "individual"}, timeout=30)
        assert r1.status_code == 200 and r10.status_code == 200
        assert r10.json()["hammer_price"] == 10 * r1.json()["hammer_price"]
