"""
iter444 supplement — additional validation-rule coverage + 403 gate + batch publish.
Runs against the live preview server. All tests use the admin (partner_pro tier).
"""
import io
import csv
import time
import httpx
import pytest
from datetime import datetime, timezone, timedelta

API_URL = ""
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            API_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "iter444_buyer@test.com"
BUYER_PASSWORD = "Iter444Buy!"

COLUMNS = [
    "title", "title_fr", "category", "starting_price", "quantity",
    "condition", "auction_end_date", "city", "region", "country",
    "postal_code", "description", "buy_now_price",
    "buyers_premium_percent", "shipping_available", "visit_offered",
    "visit_dates",
]


def _make_csv(rows, columns=None):
    cols = columns or COLUMNS
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    for r in rows:
        w.writerow([r.get(c, "") for c in cols])
    return buf.getvalue().encode("utf-8-sig")


def _future(days=14):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _valid(idx=1, **over):
    base = {
        "title": f"iter444 sup {idx} {time.time()}",
        "title_fr": "",
        "category": "electronics",
        "starting_price": "250.00",
        "quantity": "1",
        "condition": "excellent",
        "auction_end_date": _future(14),
        "city": "Toronto",
        "region": "ON",
        "country": "CA",
        "postal_code": "M5V 2H1",
        "description": "Full-frame mirrorless camera in excellent condition.",
        "buy_now_price": "500.00",
        "buyers_premium_percent": "5",
        "shipping_available": "Y",
        "visit_offered": "N",
        "visit_dates": "",
    }
    base.update(over)
    return base


@pytest.fixture(scope="module")
def admin_headers():
    r = httpx.post(f"{API_URL}/api/auth/login",
                   json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    r.raise_for_status()
    tok = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def buyer_headers():
    # Ensure the free-tier buyer exists (idempotent).
    httpx.post(f"{API_URL}/api/auth/register", json={
        "email": BUYER_EMAIL, "password": BUYER_PASSWORD, "name": "iter444 Buyer",
        "terms_agreed": True, "ai_disclosure_consent": True,
    }, timeout=15)
    r = httpx.post(f"{API_URL}/api/auth/login",
                   json={"email": BUYER_EMAIL, "password": BUYER_PASSWORD}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"buyer login failed: {r.status_code}")
    tok = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {tok}"}


def _preview(headers, rows):
    time.sleep(1.2)  # respect 30/min rate limit
    files = {"file": ("t.csv", _make_csv(rows), "text/csv")}
    return httpx.post(f"{API_URL}/api/partner-pro/bulk-import",
                      headers=headers, files=files, timeout=25)


def _all_errors(preview_json):
    return [e for row in preview_json["preview"] for e in row["errors"]]


# --- validation rules not yet in main suite ---

def test_starting_price_not_numeric(admin_headers):
    r = _preview(admin_headers, [_valid(starting_price="abc")])
    codes = [e["code"] for e in _all_errors(r.json())]
    assert "starting_price_not_numeric" in codes


def test_starting_price_below_min(admin_headers):
    r = _preview(admin_headers, [_valid(starting_price="0.5")])
    codes = [e["code"] for e in _all_errors(r.json())]
    assert "starting_price_out_of_range" in codes


def test_quantity_zero(admin_headers):
    r = _preview(admin_headers, [_valid(quantity="0")])
    codes = [e["code"] for e in _all_errors(r.json())]
    assert "quantity_positive" in codes


def test_category_required(admin_headers):
    r = _preview(admin_headers, [_valid(category="")])
    codes = [e["code"] for e in _all_errors(r.json())]
    assert "category_required" in codes


def test_category_unknown(admin_headers):
    r = _preview(admin_headers, [_valid(category="fluffybunnies")])
    codes = [e["code"] for e in _all_errors(r.json())]
    assert "category_unknown" in codes


def test_auction_end_date_invalid(admin_headers):
    r = _preview(admin_headers, [_valid(auction_end_date="not-a-date")])
    codes = [e["code"] for e in _all_errors(r.json())]
    assert "auction_end_date_invalid" in codes


def test_description_too_short(admin_headers):
    r = _preview(admin_headers, [_valid(description="short")])
    codes = [e["code"] for e in _all_errors(r.json())]
    assert "description_length" in codes


def test_description_too_long(admin_headers):
    r = _preview(admin_headers, [_valid(description="x" * 600)])
    codes = [e["code"] for e in _all_errors(r.json())]
    assert "description_length" in codes


def test_bilingual_prefix_row_and_field(admin_headers):
    """Every error message must start with 'Row {n} — Field...' EN and 'Ligne {n} — Champ...' FR."""
    r = _preview(admin_headers, [_valid(starting_price="abc", quantity="0")])
    errs = _all_errors(r.json())
    assert len(errs) >= 2
    for e in errs:
        assert e["message_en"].startswith(f"Row {e['row']}"), e
        assert "Field" in e["message_en"] or "field" in e["message_en"], e
        assert e["message_fr"].startswith(f"Ligne {e['row']}"), e
        assert "Champ" in e["message_fr"] or "champ" in e["message_fr"], e


# --- batch publish endpoint ---

def test_publish_batch_returns_expected_shape(admin_headers):
    # Create a fresh draft with a photo so it is publishable, plus one without.
    body_ok = {"rows": [{
        "title": f"iter444 batch OK {time.time()}",
        "title_fr": "",
        "category": "electronics",
        "starting_price": 100.0, "quantity": 1, "condition": "good",
        "auction_end_date": _future(20),
        "city": "Toronto", "region": "ON", "country": "CA", "postal_code": "M5V 2H1",
        "description": "A perfectly acceptable listing description.",
        "buy_now_price": 200.0, "buyers_premium_percent": 5,
        "shipping_available": True, "visit_offered": False, "visit_dates": "",
    }]}
    r1 = httpx.post(f"{API_URL}/api/partner-pro/bulk-import/confirm",
                    headers=admin_headers, json=body_ok, timeout=25)
    assert r1.status_code == 200, r1.text
    id_ok = r1.json()["drafts"][0]["id"]
    httpx.post(f"{API_URL}/api/partner-pro/bulk-import/{id_ok}/photos",
               headers=admin_headers, json={"image_urls": ["https://example.com/x.jpg"]}, timeout=15)

    body_noimg = {"rows": [{
        "title": f"iter444 batch NOIMG {time.time()}",
        "title_fr": "",
        "category": "electronics",
        "starting_price": 100.0, "quantity": 1, "condition": "good",
        "auction_end_date": _future(20),
        "city": "Toronto", "region": "ON", "country": "CA", "postal_code": "M5V 2H1",
        "description": "A perfectly acceptable listing description.",
        "buy_now_price": 200.0, "buyers_premium_percent": 5,
        "shipping_available": True, "visit_offered": False, "visit_dates": "",
    }]}
    r2 = httpx.post(f"{API_URL}/api/partner-pro/bulk-import/confirm",
                    headers=admin_headers, json=body_noimg, timeout=25)
    assert r2.status_code == 200
    id_noimg = r2.json()["drafts"][0]["id"]

    # publish-batch
    rb = httpx.post(f"{API_URL}/api/partner-pro/bulk-import/publish-batch",
                    headers=admin_headers, timeout=25)
    assert rb.status_code == 200, rb.text
    d = rb.json()
    for k in ("published_count", "pending_photos_count", "published_ids", "pending_photos"):
        assert k in d, f"missing key {k} in {d}"
    assert id_ok in d["published_ids"]
    # noimg draft should NOT have been promoted
    ids_pending = [x.get("id") for x in d["pending_photos"]]
    assert id_noimg in ids_pending or d["pending_photos_count"] >= 1


# --- 403 gate on all endpoints for a free-tier buyer ---

def test_free_buyer_gets_403_on_all_endpoints(buyer_headers):
    time.sleep(1)
    endpoints = [
        ("GET", "/api/partner-pro/bulk-import/template", None, None),
        ("POST", "/api/partner-pro/bulk-import", {"file": ("t.csv", _make_csv([_valid()]), "text/csv")}, None),
        ("POST", "/api/partner-pro/bulk-import/confirm", None, {"rows": [{
            "title": "buyer test", "category": "electronics", "starting_price": 50,
            "quantity": 1, "condition": "good", "auction_end_date": _future(10),
            "city": "T", "region": "ON", "country": "CA", "postal_code": "M5V 2H1",
            "description": "x" * 30, "buy_now_price": 100.0,
        }]}),
        ("GET", "/api/partner-pro/bulk-import/pending", None, None),
        ("POST", "/api/partner-pro/bulk-import/publish-batch", None, None),
    ]
    violations = []
    for method, path, files, json_body in endpoints:
        if method == "GET":
            r = httpx.get(f"{API_URL}{path}", headers=buyer_headers, timeout=15)
        else:
            r = httpx.post(f"{API_URL}{path}", headers=buyer_headers,
                           files=files, json=json_body, timeout=15)
        if r.status_code != 403:
            violations.append(f"{method} {path} → {r.status_code}")
    assert not violations, f"Endpoints did NOT return 403 for free-tier buyer: {violations}"


# --- regression: individual listing POST unchanged ---

def test_individual_listing_creation_regression(admin_headers):
    """POST /api/listings without csv_bulk_import source still works."""
    body = {
        "title": f"iter444 regression individual {time.time()}",
        "category": "electronics",
        "condition": "good",
        "starting_price": 50.0,
        "quantity": 1,
        "description": "A regression check that individual listing creation still works.",
        "city": "Toronto",
        "region": "ON",
        "country": "CA",
        "location": "Toronto, ON, CA",
        "auction_end_date": _future(10),
    }
    r = httpx.post(f"{API_URL}/api/listings", headers=admin_headers, json=body, timeout=25)
    # Some implementations return 200 or 201.
    assert r.status_code in (200, 201), f"individual listing creation regressed: {r.status_code} {r.text[:300]}"
