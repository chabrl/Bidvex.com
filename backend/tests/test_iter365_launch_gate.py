"""
iter365 — Launch-gate tripwires for:
  Item 1: Broker annual fee added to pricing engine.
  Item 2: All launch-window days standardised to 180.
  Item 3: Compare button de-duplicated on listing cards.
  Item 4: Buyer dashboard bids in 3-4/row responsive grid.
"""
import os
import re
import asyncio
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════════════
# Item 1 — Broker annual fee
# ═══════════════════════════════════════════════════════════════════════

def test_pricing_engine_service_has_broker_definition():
    text = open("/app/backend/services/pricing_engine_service.py", "r", encoding="utf-8").read()
    assert '"broker_annual_fee"' in text
    assert '"default_base_price_cad": 500.0' in text
    # 50 % launch discount, 180-day window (see also Item 2 test below).
    assert '"default_launch_discount_percent": 50' in text
    # BRK short-key for coupon versioning
    assert '"BRK"' in text or "'BRK'" in text


def test_pricing_engine_routes_include_broker_key():
    text = open("/app/backend/routes/pricing_engine_routes.py", "r", encoding="utf-8").read()
    assert '"broker_annual_fee"' in text
    assert "vehicle_dealer_annual_fee" in text and "partner_annual_fee" in text


def test_fee_calculator_broker_constants():
    text = open("/app/backend/services/fee_calculator.py", "r", encoding="utf-8").read()
    assert "BROKER_ANNUAL_FEE_CAD" in text
    assert 'Decimal("500.00")' in text
    assert "BROKER_ANNUAL_FEE_DISCOUNTED" in text
    assert 'Decimal("250.00")' in text


def test_broker_annual_fee_effective_price_math():
    """Verify effective_price(base=500, pct=50) == 250 via pure function."""
    import sys
    sys.path.insert(0, "/app/backend")
    from services.pricing_engine_service import effective_price
    doc = {"base_price_cad": 500.0, "launch_discount_percent": 50}
    assert effective_price(doc) == 250.00


def test_admin_pricing_engine_ui_shows_broker_row():
    text = open("/app/frontend/src/pages/admin/PricingEnginePage.js", "r", encoding="utf-8").read()
    assert "broker_annual_fee" in text
    assert "Broker Annual Membership" in text
    assert "courtier" in text  # FR label


def test_broker_registration_page_shows_correct_pricing_and_window():
    text = open("/app/frontend/src/pages/BecomeABrokerPage.jsx", "r", encoding="utf-8").read()
    # $250 discounted / $500 base
    assert "$250.00 CAD" in text
    assert "$500.00 CAD" in text
    # 180-day launch window shown
    assert "Launch window: 180 days" in text
    assert "180 jours" in text
    # No stale $100/$200 pricing left
    assert "$100.00 CAD" not in text
    assert "$200.00 CAD" not in text


# ═══════════════════════════════════════════════════════════════════════
# Item 2 — All launch windows standardised to 180 days
# ═══════════════════════════════════════════════════════════════════════

def test_all_three_account_types_default_180_day_window():
    """PRODUCT_DEFINITIONS in the service must have all three at 180 days."""
    import sys
    sys.path.insert(0, "/app/backend")
    # Force reimport in case a prior test cached
    import importlib, services.pricing_engine_service as pes
    importlib.reload(pes)
    for key in ("vehicle_dealer_annual_fee", "partner_annual_fee", "broker_annual_fee"):
        assert key in pes.PRODUCT_DEFINITIONS, f"{key} missing"
        assert pes.PRODUCT_DEFINITIONS[key]["default_launch_window_days"] == 180, \
            f"{key} default_launch_window_days != 180"


def test_pricing_engine_service_has_no_stale_90_day_defaults():
    text = open("/app/backend/services/pricing_engine_service.py", "r", encoding="utf-8").read()
    # No product definition may hard-code a 90-day default.
    m = re.findall(r'"default_launch_window_days":\s*(\d+)', text)
    for v in m:
        assert int(v) == 180, f"stale non-180 default found: {v}"


def test_db_pricing_settings_all_180():
    """Live DB check — all three pricing_settings docs must be at 180 days."""
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient

    async def _check():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        try:
            for key in ("vehicle_dealer_annual_fee", "partner_annual_fee", "broker_annual_fee"):
                doc = await db.pricing_settings.find_one({"key": key}, {"_id": 0})
                assert doc, f"pricing_settings row missing for {key}"
                assert doc.get("launch_window_days") == 180, \
                    f"{key} launch_window_days={doc.get('launch_window_days')} (expected 180)"
        finally:
            client.close()

    asyncio.run(_check())


# ═══════════════════════════════════════════════════════════════════════
# Item 3 — Duplicate Compare button removed
# ═══════════════════════════════════════════════════════════════════════

def test_flattened_marketplace_has_no_legacy_scale_compare_button():
    """The legacy top-right Scale-icon compare button must be gone."""
    text = open("/app/frontend/src/components/FlattenedMarketplace.js", "r", encoding="utf-8").read()
    # The legacy render used <Scale className="h-3.5 w-3.5"/> inside a <button>.
    assert '<Scale className="h-3.5 w-3.5"' not in text
    # The legacy `compare-toggle-${item.id}` testid must not appear either.
    assert "compare-toggle-${item.id}" not in text


def test_flattened_marketplace_has_no_legacy_floating_compare_bar():
    """Legacy `compare-floating-bar` was replaced by iter364 global <CompareBar>."""
    text = open("/app/frontend/src/components/FlattenedMarketplace.js", "r", encoding="utf-8").read()
    assert "compare-floating-bar" not in text
    # And navigation to `/compare?ids=…` (old URL scheme) is gone.
    assert "/compare?ids=" not in text


def test_iter364_compare_checkbox_still_present_on_all_cards():
    """Guardrail: the iter364 CompareCheckbox (the ONLY compare UI now) is still on all 4 card types."""
    for p in (
        "/app/frontend/src/components/FlattenedMarketplace.js",
        "/app/frontend/src/pages/LotsMarketplacePage.js",
        "/app/frontend/src/pages/storage/StorageAuctionCard.js",
        "/app/frontend/src/components/vehicles/VehicleListingCard.js",
    ):
        text = open(p, "r", encoding="utf-8").read()
        assert "CompareCheckbox" in text, f"CompareCheckbox missing from {p}"


# ═══════════════════════════════════════════════════════════════════════
# Item 4 — Buyer dashboard grid layout
# ═══════════════════════════════════════════════════════════════════════

def test_buyer_dashboard_uses_responsive_grid_for_all_bid_lists():
    text = open("/app/frontend/src/pages/BuyerDashboard.js", "r", encoding="utf-8").read()
    # All 3 tabs (All Bids / Winning / Outbid) render 3-to-4 per row on lg+ / xl.
    assert 'data-testid="buyer-bids-grid-all"' in text
    assert 'data-testid="buyer-bids-grid-winning"' in text
    assert 'data-testid="buyer-bids-grid-outbid"' in text
    assert "lg:grid-cols-3 xl:grid-cols-4" in text
