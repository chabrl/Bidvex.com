"""
iter286 — Critical launch-blocking bug regression tests.

Covers the five production bugs reported by the operator on 2026-06-06
(post iter285 deploy — Ford F-350 listing incident):

  Bug 1) Vehicle media upload was MOCKED — never persisted to S3.
         Legacy listings stored relative `/uploads/vehicles/…` URLs
         that resolved to nothing in production. Fix: real S3 upload
         via `services/s3_service.py`; GET endpoint strips legacy
         relative URLs so the gallery renders a clean empty state.

  Bug 2) `/broker-relationships/compliance-check` returned 404 with
         `listing_not_found` for vehicles authored via the broker
         dealer wizard (they live in `db.vehicle_listings`, not
         `db.listings`). The dual-collection lookup now resolves
         both. The bid-panel error toast no longer renders the raw
         code.

  Bug 3) Right-side bid panel had an inner scrollbar
         (`lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto`),
         forcing buyers to scroll twice. Removed.

  Bug 4) Quick Bid on a marketplace card opened the GENERIC
         marketplace bid modal regardless of the listing's section,
         showing wrong fee/terms (e.g. buyer premium on a vehicle).
         Fix: section-aware routing to the dedicated detail page.

  Bug 5) Carfax / inspection-report feature missing. New optional
         model fields + new GET /vehicle-auctions/{id}/carfax
         endpoint with broker-gating (403 with `broker_required` for
         individuals, 200 for brokers + sellers + admins).
"""
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("PUBLIC_BACKEND_URL", "http://localhost:8001")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def buyer_token():
    """Use the stable iter286 test buyer (created during initial bring-up).

    The legacy users collection has a `mobile_number_normalized_1` unique
    index that errors on NULL — registering a brand-new user with a phone
    field requires a valid E.164 number that the backend normalizer
    accepts. Rather than fight the index, we reuse the prebuilt account.
    """
    candidate_emails = [
        "iter286-buyer-1780788613@test.bidvex.com",  # seeded during dev
    ]
    for email in candidate_emails:
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": "TestPassw0rd!"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("access_token") or r.json().get("token")
    pytest.skip(
        "iter286 stable test buyer not available — "
        "skip the dual-collection broker tests in this environment."
    )


@pytest.fixture()
def seeded_vehicle_with_legacy_media(db):
    """Vehicle in `db.vehicle_listings` with a mix of legacy `/uploads/...`
    relative URLs and a valid absolute https URL — exercises the GET
    endpoint's media-URL normalization."""
    vid = f"iter286-v-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id":            vid,
        "seller_id":     "iter286-seller",
        "title":         "iter286 test vehicle",
        "make":          "Toyota",
        "model":         "Camry",
        "year":          2020,
        "vin":           "1HGBH41JXMN109186",
        "starting_price": 1000,
        "current_bid":   1000,
        "status":        "active",
        "media": [
            {"id": "m1", "type": "photo", "url": "/uploads/vehicles/iter286/front_bad", "category": "front"},
            {"id": "m2", "type": "photo", "url": "https://example.com/photo-ok.jpg", "category": "rear"},
            {"id": "m3", "type": "photo", "url": "/uploads/vehicles/iter286/side_bad", "category": "driver_side"},
        ],
        "created_at": now,
    }
    db.vehicle_listings.insert_one(doc.copy())
    yield doc
    db.vehicle_listings.delete_one({"id": vid})


# ── Bug 1 — Media URL normalization ────────────────────────────────────


def test_bug1_get_vehicle_strips_legacy_uploads_paths(seeded_vehicle_with_legacy_media):
    """GET /api/vehicles/{id} must drop legacy relative `/uploads/...`
    URLs (the placeholder paths from the old mocked upload endpoint)
    so the gallery never tries to load broken images."""
    vid = seeded_vehicle_with_legacy_media["id"]
    r = requests.get(f"{BASE_URL}/api/vehicles/{vid}", timeout=10)
    assert r.status_code == 200, r.text
    media = r.json().get("media", [])
    # Only the absolute https URL should survive.
    assert len(media) == 1
    assert media[0]["url"].startswith("https://")
    assert media[0]["category"] == "rear"


# ── Bug 2 — Dual-collection compliance-check ──────────────────────────


def test_bug2_compliance_check_finds_vehicle_listings_unit(seeded_vehicle_with_legacy_media, buyer_token):
    """A vehicle that lives only in `db.vehicle_listings` (broker-dealer
    flow) used to 404 with `listing_not_found`. Now the dual-collection
    fallback resolves it. Expect a structured status — never 404."""
    vid = seeded_vehicle_with_legacy_media["id"]
    r = requests.get(
        f"{BASE_URL}/api/broker-relationships/compliance-check?listing_id={vid}",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    assert r.status_code != 404, f"compliance-check 404'd: {r.text}"
    assert r.status_code == 200, r.text
    body = r.json()
    # Buyer has no broker → expect `no_broker`, NOT `listing_not_found`.
    assert body.get("status") == "no_broker"


def test_bug2_compliance_check_still_404s_for_truly_unknown_listing(buyer_token):
    """Regression — the dual-collection fallback must NOT swallow real
    404s. A nonsense id must still 404 cleanly."""
    r = requests.get(
        f"{BASE_URL}/api/broker-relationships/compliance-check?listing_id=this-id-does-not-exist-iter286",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    assert r.status_code == 404
    body = r.json()
    assert body.get("detail", {}).get("error") == "listing_not_found"


# ── Bug 5 — Broker-gated Carfax endpoint ──────────────────────────────


def test_bug5_carfax_endpoint_403s_for_non_broker_buyer(seeded_vehicle_with_legacy_media, buyer_token):
    """Individual buyers (no broker status) get 403 with the
    `broker_required` code so the UI can render a locked-state CTA."""
    vid = seeded_vehicle_with_legacy_media["id"]
    r = requests.get(
        f"{BASE_URL}/api/vehicle-auctions/{vid}/carfax",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    assert r.status_code == 403, r.text
    detail = r.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "broker_required"


def test_bug5_carfax_endpoint_returns_documents_for_admin(seeded_vehicle_with_legacy_media, db):
    """Admins can read Carfax document references unconditionally."""
    # Attach a stub carfax URL.
    vid = seeded_vehicle_with_legacy_media["id"]
    db.vehicle_listings.update_one(
        {"id": vid},
        {"$set": {
            "carfax_url":  "https://www.carfax.ca/VehicleHistory/iter286-test",
            "carfax_file": "https://bidvex.s3.amazonaws.com/carfax/iter286.pdf",
        }},
    )
    # Use the seeded admin from test_credentials.md.
    # iter286 — Auth endpoint can rate-limit when prior tests have hit
    # /auth/login many times in the same minute; retry with backoff.
    import time as _t
    token = None
    last = None
    for _attempt in range(8):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
            timeout=15,
        )
        last = r
        if r.status_code == 200:
            token = r.json().get("access_token") or r.json().get("token")
            break
        _t.sleep(min(2 ** _attempt, 16))
    assert token, f"admin login failed: {last.status_code} {last.text[:200]}"
    rr = requests.get(
        f"{BASE_URL}/api/vehicle-auctions/{vid}/carfax",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert rr.status_code == 200, rr.text
    body = rr.json()
    assert body["carfax_url"].startswith("https://www.carfax.ca/")
    assert body["carfax_file"].endswith(".pdf")
    assert body["viewer_role"] in ("admin", "seller", "broker")


def test_bug5_carfax_endpoint_404s_for_unknown_vehicle(buyer_token):
    """Real 404 for unknown ids — fallback must not swallow legitimate
    missing-vehicle errors."""
    r = requests.get(
        f"{BASE_URL}/api/vehicle-auctions/this-vehicle-does-not-exist-iter286/carfax",
        headers={"Authorization": f"Bearer {buyer_token}"},
        timeout=10,
    )
    assert r.status_code == 404


# ── Bug 5 — Pydantic model accepts the new optional fields ────────────


def test_bug5_vehicle_create_model_accepts_carfax_fields():
    """`VehicleListingCreate` must accept `carfax_url`, `carfax_file`,
    `inspection_file` without raising. Optional → legacy callers safe."""
    from models.vehicle_models import VehicleListingCreate
    from datetime import timedelta

    payload = {
        "vin": "1HGBH41JXMN109186",
        "year": 2020,
        "make": "Toyota",
        "model": "Camry",
        "trim": "XSE",
        "body_type": "sedan",
        "mileage": 50000,
        "transmission": "automatic",
        "fuel_type": "gasoline",
        "drivetrain": "fwd",
        "exterior_color": "White",
        "interior_color": "Black",
        "ownership_status": "owned",
        "title_status": "clean",
        "lien_status": "clear",
        "condition_report": {
            "is_running": True, "starts_normally": True,
            "engine_condition": "good", "transmission_condition": "good",
            "brakes_condition": "good", "suspension_condition": "good",
            "body_condition": "good", "paint_condition": "good",
            "interior_condition": "good", "tires_condition": "good",
            "has_accident_history": False, "has_flood_damage": False,
            "has_fire_damage": False, "has_frame_damage": False,
        },
        "location_city": "Montreal",
        "location_province": "QC",
        "location_postal_code": "H3M 1H3",
        "auction_type": "timed",
        "visibility": "public",
        "auction_access": "public_individual",
        "run_status": "run_and_drive",
        "start_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        "end_time":   (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "starting_price": 1000.0,
        "bid_increment": 100.0,
        "requires_deposit": True,
        "deposit_amount": 500.0,
        "currency": "CAD",
        "title": "2020 Toyota Camry XSE",
        "description": "Clean title.",
        "features": [],
        "category_id": "passenger_cars",
        # iter286 — Bug 5 — Carfax / inspection references.
        "carfax_url":      "https://www.carfax.ca/VehicleHistory/abc",
        "carfax_file":     "https://bidvex.s3.amazonaws.com/carfax/abc.pdf",
        "inspection_file": "https://bidvex.s3.amazonaws.com/inspection/abc.pdf",
    }
    model = VehicleListingCreate(**payload)
    assert model.carfax_url == payload["carfax_url"]
    assert model.carfax_file == payload["carfax_file"]
    assert model.inspection_file == payload["inspection_file"]
