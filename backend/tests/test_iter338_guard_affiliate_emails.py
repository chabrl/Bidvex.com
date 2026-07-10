"""
iter338 — Tests for:
  1. Vehicle-guard word-boundary fix (the exact alexboul1993 false positive)
  2. Admin notification on every gate block
  3. Systemic substring-bug fixes (word_match, category_rules)
  4. Affiliate 3% profit-share commission engine
  5. Careers/Contractor email → contractor@bidvex.com
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path("/app/backend")))
load_dotenv("/app/backend/.env")

from services.vehicle_listing_guard import is_vehicle_listing, enforce_vehicle_dealer_gate
from services.word_match import has_word, has_any_word, first_word_match
from services.category_rules import category_requires_broker, is_vehicle_category
from routes.affiliate import award_affiliate_commission, AFFILIATE_PROFIT_SHARE_RATE


@pytest.fixture
def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


# ---------------------------------------------------------------------------
# 1. The EXACT reported false positive + word-boundary regressions
# ---------------------------------------------------------------------------

class TestReportedFalsePositive:

    def test_exact_blocked_multi_lot_listing_now_passes(self):
        """alexboul1993@gmail.com's exact blocked title — signal was model:rio
        (substring inside 'Ontario'/'interior')."""
        is_v, signals, strength = is_vehicle_listing(
            "",
            "Absolute Multi-Lot Clearance: Bicycles, Furniture & Extra Goods",
            "Multiple lots: bikes, restaurant equipment, interior furniture, "
            "patio set. Pickup in Ontario. Includes Ninja blender and Vulcan range.",
        )
        assert not is_v, f"still blocked: signals={signals} strength={strength}"
        assert strength == 0

    def test_fatbike_x1_dimension_case_now_passes(self):
        """Their earlier blocked Fatbike listing — signal was model:x1 from dimensions."""
        is_v, signals, strength = is_vehicle_listing(
            "Bikes & Cycling",
            'Fatbike seven peaks 17" New in box',
            "Fat tire bike, 26x17 wheels, brand new. Size 17x1.5",
        )
        assert not is_v, f"signals={signals} strength={strength}"

    @pytest.mark.parametrize("title,description", [
        ("Restaurant equipment lot", "Vulcan 6-burner range, Ninja blenders, prep tables. Located in Ontario."),
        ("Office chairs", "Ergonomic, leather interior padding, made in Ontario 2022"),
        ("Ninja blender bundle", "Kitchen appliances, barely used"),
        ("Canon Rebel T7 camera kit", "DSLR with two lenses, purchased 2021"),
        ("A4 paper bulk lot", "50 boxes of A4 and A5 office paper"),
        ("Gaming PC", "RTX GTX 3080, Intel i7, Corsair RAM 1500MHz, purchased 2022"),
        ("M3 and M4 screw assortment", "3500 pieces of stainless hardware"),
        ("Golf clubs full set", "Titleist irons, leaf-pattern bag, summit edition"),
        ("Yamaha keyboard", "Digital piano purchased 2020, barely used"),
        ("Honda generator EU2200i", "Portable generator 2019 model"),
    ])
    def test_common_word_model_names_do_not_flag(self, title, description):
        is_v, signals, strength = is_vehicle_listing("", title, description)
        assert not is_v, f"{title!r} flagged: signals={signals} strength={strength}"

    @pytest.mark.parametrize("cat,title,desc", [
        ("Cars", "2018 Honda Civic LX", "Clean title"),
        ("Other", "ford f150", ""),
        ("Other", "Kia Rio", "hatchback for sale"),
        ("Other", "kia rio 2015 low km", ""),
        ("Tools", "chevy silverado", ""),
        ("Other", "jeep wrangler", ""),
        ("Motorcycles", "2019 Kawasaki Ninja 400", ""),
        ("Estate", "Weekend sale", "Includes a VIN: 1HGCM82633A004352"),
        ("Other", "dodge charger", ""),
        ("Other", "tesla model 3", ""),
    ])
    def test_real_vehicles_still_flagged(self, cat, title, desc):
        is_v, signals, strength = is_vehicle_listing(cat, title, desc)
        assert is_v, f"{title!r} missed: signals={signals} strength={strength}"


# ---------------------------------------------------------------------------
# 2. Admin notification on gate block
# ---------------------------------------------------------------------------

class _FakeUser:
    def __init__(self, id_):
        self.id = id_


@pytest.mark.asyncio
async def test_gate_block_creates_admin_notification(db):
    user_id = f"iter338-gate-{uuid.uuid4().hex[:8]}"
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"id": user_id, "email": f"{user_id}@example.com",
                  "seller_type": "individual", "dealer_license_verified": False}},
        upsert=True,
    )
    try:
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await enforce_vehicle_dealer_gate(
                db, _FakeUser(user_id),
                category="Other", title="ford f150", description="",
                surface="single_listing",
            )
        assert exc_info.value.status_code == 403
        notif = await db.admin_notifications.find_one(
            {"subkind": "blocked_at_gate", "seller_id": user_id}, {"_id": 0},
        )
        assert notif is not None, "gate block must create an admin notification"
        assert notif["kind"] == "vehicle_compliance_violation"
        assert any("model:" in s for s in notif["detection_signals"])
    finally:
        await db.users.delete_one({"id": user_id})
        await db.audit_logs.delete_many({"user_id": user_id})
        await db.admin_notifications.delete_many({"seller_id": user_id})


# ---------------------------------------------------------------------------
# 3. Systemic substring fixes
# ---------------------------------------------------------------------------

class TestWordMatch:

    def test_no_substring_bleed(self):
        assert not has_word("made in ontario", "rio")
        assert not has_word("interior furniture", "rio")
        assert not has_word("my listing here", "sti")
        assert not has_word("business hours", "bus")
        assert not has_word("carpets and rugs", "car")
        assert not has_word("automation tools", "auto")

    def test_whole_words_match(self):
        assert has_word("kia rio 2015", "rio")
        assert has_word("ford f-150 xlt", "f-150")
        assert has_word("vin: 1hgcm82633a004352", "vin:")
        assert first_word_match("a silverado truck", ("silverado",)) == "silverado"
        assert has_any_word("wire transfer only please", ["wire transfer"])

    def test_category_rules_word_boundary(self):
        assert category_requires_broker("Vehicles") is True
        assert category_requires_broker("vehicles_cars") is True
        assert category_requires_broker("Trucks & SUVs") is True
        assert category_requires_broker("Carpets & Rugs") is False       # was True (substring "car")
        assert category_requires_broker("Automation Equipment") is False  # was True (substring "auto")
        assert is_vehicle_category("Cars") is True
        assert is_vehicle_category("Restaurant Equipment") is False


# ---------------------------------------------------------------------------
# 4. Affiliate 3% profit-share engine
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_affiliate_3pct_commission_awarded(db):
    suffix = uuid.uuid4().hex[:8]
    referrer_id = f"iter338-ref-{suffix}"
    payer_id = f"iter338-payer-{suffix}"
    code = f"T338{suffix[:4].upper()}"
    await db.users.insert_one({"id": referrer_id, "name": "Ref User",
                               "email": f"{referrer_id}@example.com", "affiliate_code": code})
    await db.users.insert_one({"id": payer_id, "name": "Payer User",
                               "email": f"{payer_id}@example.com", "referred_by_code": code})
    try:
        # $100 platform fee → $3.00 commission
        credit = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=100.0,
            source="auction_buyer_fee", reference_id=f"auction:test:{suffix}",
        )
        assert credit is not None
        assert credit["amount"] == 3.0
        assert credit["commission_rate"] == AFFILIATE_PROFIT_SHARE_RATE == 0.03
        assert credit["commission_base"] == 100.0
        assert credit["status"] == "pending"
        assert credit["user_id"] == referrer_id

        # Idempotent — same (source, reference) never double-awards
        dup = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=100.0,
            source="auction_buyer_fee", reference_id=f"auction:test:{suffix}",
        )
        assert dup is None

        # LIFETIME — a second, different transaction awards again
        credit2 = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=50.0,
            source="subscription", reference_id=f"in_test_{suffix}",
        )
        assert credit2 is not None
        assert credit2["amount"] == 1.5

        # payer converted stamp
        payer = await db.users.find_one({"id": payer_id}, {"_id": 0, "first_paid_at": 1})
        assert payer.get("first_paid_at")

        total = 0.0
        async for c in db.platform_credits.find({"user_id": referrer_id, "source": "referral"}):
            total += c["amount"]
        assert round(total, 2) == 4.5
    finally:
        await db.users.delete_many({"id": {"$in": [referrer_id, payer_id]}})
        await db.platform_credits.delete_many({"user_id": referrer_id})


@pytest.mark.asyncio
async def test_affiliate_no_referrer_no_credit(db):
    payer_id = f"iter338-noref-{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({"id": payer_id, "name": "Solo", "email": f"{payer_id}@example.com"})
    try:
        credit = await award_affiliate_commission(
            db, payer_id=payer_id, platform_revenue=100.0,
            source="auction_buyer_fee", reference_id=f"auction:test:{payer_id}",
        )
        assert credit is None
    finally:
        await db.users.delete_one({"id": payer_id})


@pytest.mark.asyncio
async def test_affiliate_zero_revenue_no_credit(db):
    credit = await award_affiliate_commission(
        db, payer_id="anything", platform_revenue=0,
        source="auction_buyer_fee", reference_id="x",
    )
    assert credit is None


def test_affiliate_rate_constants_aligned():
    from services.pricing_config import AFFILIATE_COMMISSION_RATE as pc_rate
    from services.fee_calculator import AFFILIATE_COMMISSION_RATE as fc_rate
    from shared import AFFILIATE_COMMISSION_RATE as sh_rate
    assert float(pc_rate) == 0.03
    assert float(fc_rate) == 0.03
    assert float(sh_rate) == 0.03


# ---------------------------------------------------------------------------
# 5. Careers/Contractor email → contractor@bidvex.com
# ---------------------------------------------------------------------------

def test_careers_and_contractor_emails_updated():
    careers_src = Path("/app/backend/services/careers_notifications.py").read_text()
    aid_src = Path("/app/backend/routes/contractor_aid.py").read_text()
    assert "contractor@bidvex.com" in careers_src
    assert "support@bidvex.com" not in careers_src
    assert "contractor@bidvex.com" in aid_src
    assert "support@bidvex.com" not in aid_src
