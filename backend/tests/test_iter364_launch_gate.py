"""
iter364 — Launch-gate tripwires for iter364 features.

Static (frontend source) tests + backend live-API tests. Run with:
    cd /app/backend && python -m pytest tests/test_iter364_launch_gate.py -q
"""
import os
import re


# ═══════════════════════════════════════════════════════════════════════
# P0 — Hero phone client-provided assets
# ═══════════════════════════════════════════════════════════════════════

def test_hero_client_assets_exist():
    for lang in ("en", "fr"):
        p = f"/app/frontend/public/assets/hero-phone-{lang}.png"
        assert os.path.isfile(p), f"Missing {p}"
        assert os.path.getsize(p) > 100_000, f"{p} < 100KB — expected ~700KB client asset"


def test_hero_component_wires_to_client_assets():
    text = open("/app/frontend/src/components/HeroPhone.js", "r", encoding="utf-8").read()
    assert "/assets/hero-phone-en.png" in text
    assert "/assets/hero-phone-fr.png" in text


# ═══════════════════════════════════════════════════════════════════════
# P1 — Compare Listings feature
# ═══════════════════════════════════════════════════════════════════════

def test_compare_context_exists():
    p = "/app/frontend/src/contexts/CompareContext.jsx"
    assert os.path.isfile(p)
    text = open(p, "r", encoding="utf-8").read()
    # 4-item cap enforced
    assert "MAX_ITEMS = 4" in text
    # Session-storage persistence
    assert "sessionStorage" in text


def test_compare_bar_and_checkbox_exports():
    p = "/app/frontend/src/components/CompareBar.jsx"
    assert os.path.isfile(p)
    text = open(p, "r", encoding="utf-8").read()
    # Both named CompareCheckbox and default CompareBar export
    assert "export function CompareCheckbox" in text
    assert "export default function CompareBar" in text
    # Bilingual labels
    assert "Compare Now" in text
    assert "Comparer maintenant" in text


def test_compare_checkbox_wired_on_all_card_types():
    """Marketplace / Lots / Storage / Vehicle cards import & render CompareCheckbox."""
    files = [
        "/app/frontend/src/components/FlattenedMarketplace.js",
        "/app/frontend/src/pages/LotsMarketplacePage.js",
        "/app/frontend/src/pages/storage/StorageAuctionCard.js",
        "/app/frontend/src/components/vehicles/VehicleListingCard.js",
    ]
    for p in files:
        text = open(p, "r", encoding="utf-8").read()
        assert "CompareCheckbox" in text, f"CompareCheckbox missing from {p}"


def test_compare_page_and_route_registered():
    p = "/app/frontend/src/pages/ComparePage.jsx"
    assert os.path.isfile(p)
    app = open("/app/frontend/src/App.js", "r", encoding="utf-8").read()
    # EN + FR routes present
    assert 'path="/compare"' in app
    assert 'path="/fr/comparer"' in app
    # Provider + bar wired
    assert "CompareProvider" in app
    assert "<CompareBar />" in app


# ═══════════════════════════════════════════════════════════════════════
# P1 — Google AdSense integration
# ═══════════════════════════════════════════════════════════════════════

def test_adunit_component_env_aware():
    p = "/app/frontend/src/components/AdUnit.jsx"
    assert os.path.isfile(p)
    text = open(p, "r", encoding="utf-8").read()
    # Prod host allowlist
    assert "www.bidvex.com" in text
    # Placeholder rendered on non-prod
    assert "ad-unit-container--placeholder" in text
    # Uses REACT_APP_ADSENSE_CLIENT env var
    assert "REACT_APP_ADSENSE_CLIENT" in text


def test_adunit_placed_on_all_4_index_pages():
    files_and_slots = [
        ("/app/frontend/src/pages/MarketplacePage.js",             ["marketplace-top", "marketplace-bottom"]),
        ("/app/frontend/src/pages/LotsMarketplacePage.js",         ["lots-top", "lots-bottom"]),
        ("/app/frontend/src/pages/vehicles/VehicleAuctionsPage.js",["vehicles-top", "vehicles-mid"]),
        ("/app/frontend/src/pages/storage/StorageAuctionsBrowse.js",["storage-top", "storage-bottom"]),
    ]
    for p, slots in files_and_slots:
        text = open(p, "r", encoding="utf-8").read()
        assert "AdUnit" in text, f"AdUnit not imported in {p}"
        for slot in slots:
            assert slot in text, f"Ad slot '{slot}' missing in {p}"


def test_adsense_script_conditionally_loaded():
    """index.html conditionally loads AdSense JS only on prod hosts."""
    text = open("/app/frontend/public/index.html", "r", encoding="utf-8").read()
    assert "pagead2.googlesyndication.com" in text
    assert "PROD_HOSTS" in text
    # Must NOT unconditionally load — must be gated on hostname
    assert "PUBLISHER.indexOf('X') === -1" in text


# ═══════════════════════════════════════════════════════════════════════
# P1 — Admin Notification Bell
# ═══════════════════════════════════════════════════════════════════════

def test_notification_bell_component_exists():
    p = "/app/frontend/src/components/admin/NotificationBell.jsx"
    assert os.path.isfile(p)
    text = open(p, "r", encoding="utf-8").read()
    assert "/admin/notifications/summary" in text
    # 60s polling
    assert "60_000" in text or "60000" in text


def test_notification_bell_mounted_in_admin():
    text = open("/app/frontend/src/pages/AdminDashboard.js", "r", encoding="utf-8").read()
    assert "NotificationBell" in text
    assert "<NotificationBell" in text


def test_notification_summary_router_registered():
    p = "/app/backend/routes/admin_notifications.py"
    assert os.path.isfile(p)
    text = open(p, "r", encoding="utf-8").read()
    assert 'prefix="/api/admin/notifications"' in text
    server = open("/app/backend/server.py", "r", encoding="utf-8").read()
    assert "admin_notifications_router" in server


# ═══════════════════════════════════════════════════════════════════════
# P2 — MultiLotImageCarousel extended to vehicle cards
# ═══════════════════════════════════════════════════════════════════════

def test_vehicle_card_uses_carousel_when_multi_image():
    text = open("/app/frontend/src/components/vehicles/VehicleListingCard.js", "r", encoding="utf-8").read()
    assert "MultiLotImageCarousel" in text
    assert "vehicleImages" in text
    assert "vehicleImages.length >= 2" in text


# ═══════════════════════════════════════════════════════════════════════
# Regression tripwires
# ═══════════════════════════════════════════════════════════════════════

def test_placeholder_png_is_publicly_accessible():
    p = "/app/frontend/public/static/placeholder.png"
    assert os.path.isfile(p)
    assert os.path.getsize(p) > 1000, "placeholder.png looks corrupt (<1KB)"


def test_listing_image_helper_present():
    p = "/app/frontend/src/utils/listingImage.js"
    assert os.path.isfile(p)
    text = open(p, "r", encoding="utf-8").read()
    assert "getListingImage" in text
    # Field priority chain: images[0] → image_url → photos[0] → …
    assert "images?.[0]" in text
    assert "image_url" in text
    assert "photos?.[0]" in text
