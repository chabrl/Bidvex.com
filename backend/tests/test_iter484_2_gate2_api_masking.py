"""iter484.2 Gate 2 — API-level reserve masking verification against public URL."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")

# Load frontend/.env to be safe if env not exported
if not BASE_URL or "preview" not in BASE_URL:
    try:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except FileNotFoundError:
        pass


VEHICLES = {
    "iter484-2-gate2-no-reserve": ("none", False, False),
    "iter484-2-gate2-reserve-not-met": ("not_met", True, False),
    "iter484-2-gate2-reserve-met": ("met", True, True),
}


@pytest.fixture(scope="module")
def s():
    return requests.Session()


@pytest.mark.parametrize("vid,expected", list(VEHICLES.items()))
def test_vehicle_detail_masks_reserve(s, vid, expected):
    state, has_reserve, reserve_met = expected
    r = s.get(f"{BASE_URL}/api/vehicles/{vid}", timeout=30)
    assert r.status_code == 200, f"{vid} -> {r.status_code}: {r.text[:200]}"
    body = r.json()
    # Root or nested under "vehicle"/"listing"
    obj = body.get("vehicle") or body.get("listing") or body
    assert "reserve_price" not in obj, f"reserve_price LEAKED on {vid}"
    # Also assert nowhere in raw JSON text
    assert "reserve_price" not in r.text, f"reserve_price string appears in {vid} response body"
    assert obj.get("has_reserve") is has_reserve, f"has_reserve mismatch on {vid}: {obj.get('has_reserve')}"
    assert obj.get("reserve_state") == state, f"reserve_state mismatch on {vid}: {obj.get('reserve_state')}"
    assert obj.get("reserve_met") is reserve_met, f"reserve_met mismatch on {vid}: {obj.get('reserve_met')}"


def test_vehicles_list_masks_reserve(s):
    r = s.get(f"{BASE_URL}/api/vehicles", timeout=30)
    assert r.status_code == 200
    body = r.json()
    vehicles = body.get("vehicles") or body if isinstance(body, list) else body.get("vehicles", [])
    assert isinstance(vehicles, list)
    assert len(vehicles) > 0
    for v in vehicles:
        assert "reserve_price" not in v, f"reserve_price leaked on list item {v.get('id')}"
        assert "has_reserve" in v, f"has_reserve missing on {v.get('id')}"
        assert "reserve_state" in v, f"reserve_state missing on {v.get('id')}"
    # Also ensure the raw text has no reserve_price token
    assert "reserve_price" not in r.text


def test_vml_event_masks_reserve(s):
    r = s.get(f"{BASE_URL}/api/vehicle-multi-lot-auctions/iter484-2-gate2-vml-event", timeout=30)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert "reserve_price" not in r.text, "reserve_price string leaked in VML response"
    event = body.get("event") or body.get("auction") or body
    lots = event.get("lots") or body.get("lots") or []
    assert len(lots) == 3, f"Expected 3 lots, got {len(lots)}"
    # Sort by lot_number if present
    lots_sorted = sorted(lots, key=lambda x: x.get("lot_number", 0) or 0)
    expected_states = ["none", "not_met", "met"]
    for i, lot in enumerate(lots_sorted):
        assert "reserve_price" not in lot, f"lot {i+1} leaked reserve_price"
        assert lot.get("reserve_state") == expected_states[i], (
            f"lot #{i+1} expected {expected_states[i]}, got {lot.get('reserve_state')}"
        )


def test_regression_storage_accepted_payment_methods(s):
    r = s.get(f"{BASE_URL}/api/storage-auctions/ui343-storage", timeout=30)
    assert r.status_code == 200, r.text[:200]
    body = r.json()
    obj = body.get("auction") or body
    apm = obj.get("accepted_payment_methods")
    assert apm and "stripe" in apm, f"accepted_payment_methods regression: {apm}"
