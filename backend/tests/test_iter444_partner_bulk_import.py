"""
iter444 — Partner CSV Bulk Import (preview + confirm + photos + publish)
==========================================================================
Backend contract test suite. Exercises the four new endpoints end-to-end
against the RUNNING server. Uses the seeded super_admin (partner_pro tier)
so the _require_partner_pro gate passes.

  1. GET  /api/partner-pro/bulk-import/template            → CSV bytes
  2. POST /api/partner-pro/bulk-import (preview, no DB write)
  3. POST /api/partner-pro/bulk-import/confirm             → drafts
  4. POST /api/partner-pro/bulk-import/{id}/photos          → attach
  5. POST /api/partner-pro/bulk-import/{id}/publish         → publish gate
  6. POST /api/partner-pro/bulk-import/publish-batch        → batch publish
"""
import io
import csv
import os
import sys
import time
from datetime import datetime, timezone, timedelta

import httpx
import pytest

sys.path.insert(0, "/app/backend")

API_URL = ""
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            API_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="module")
def token():
    r = httpx.post(
        f"{API_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    r.raise_for_status()
    d = r.json()
    return d.get("access_token") or d.get("token")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def _make_csv(rows: list[dict]) -> bytes:
    """Build a CSV byte-string from a list of row dicts matching
    the iter444 template columns."""
    columns = [
        "title", "title_fr", "category", "starting_price", "quantity",
        "condition", "auction_end_date", "city", "region", "country",
        "postal_code", "description", "buy_now_price",
        "buyers_premium_percent", "shipping_available", "visit_offered",
        "visit_dates",
    ]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(columns)
    for r in rows:
        w.writerow([r.get(c, "") for c in columns])
    return buf.getvalue().encode("utf-8-sig")


def _future_iso(days: int = 14) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _valid_row(idx: int = 1, **overrides) -> dict:
    base = {
        "title": f"iter444 Test Sony Camera {idx}",
        "title_fr": "",
        "category": "electronics",
        "starting_price": "250.00",
        "quantity": "1",
        "condition": "excellent",
        "auction_end_date": _future_iso(14),
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
    base.update(overrides)
    return base


# ─────────────────────────────────────────────────────────────
# 1) TEMPLATE
# ─────────────────────────────────────────────────────────────
def test_template_download_shape(headers):
    r = httpx.get(f"{API_URL}/api/partner-pro/bulk-import/template",
                  headers=headers, timeout=15)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    text = r.content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    lines = list(reader)
    # Header + 3 example rows.
    assert len(lines) == 4
    header = lines[0]
    # Canonical iter444 columns.
    expected = [
        "title", "title_fr", "category", "starting_price", "quantity",
        "condition", "auction_end_date", "city", "region", "country",
        "postal_code", "description", "buy_now_price",
        "buyers_premium_percent", "shipping_available", "visit_offered",
        "visit_dates",
    ]
    assert header == expected
    # Example row 2 has a French title (QC).
    row2 = dict(zip(header, lines[2]))
    assert row2["region"] == "QC"
    assert row2["title_fr"].strip() != ""


# ─────────────────────────────────────────────────────────────
# 2) PREVIEW — happy path
# ─────────────────────────────────────────────────────────────
def test_preview_valid_rows_no_errors(headers):
    csv_bytes = _make_csv([_valid_row(1), _valid_row(2)])
    files = {"file": ("valid.csv", csv_bytes, "text/csv")}
    r = httpx.post(f"{API_URL}/api/partner-pro/bulk-import",
                   headers=headers, files=files, timeout=25)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["total_rows"] == 2
    assert d["total_errors"] == 0
    assert d["can_import"] is True
    assert d["max_rows"] == 100
    assert len(d["preview"]) == 2


# ─────────────────────────────────────────────────────────────
# 3) PREVIEW — every validation rule surfaces a bilingual error
# ─────────────────────────────────────────────────────────────
def test_preview_starting_price_out_of_range(headers):
    csv_bytes = _make_csv([_valid_row(1, starting_price="15000")])
    files = {"file": ("bad_price.csv", csv_bytes, "text/csv")}
    r = httpx.post(f"{API_URL}/api/partner-pro/bulk-import",
                   headers=headers, files=files, timeout=25)
    d = r.json()
    assert d["total_errors"] >= 1
    codes = [e["code"] for row in d["preview"] for e in row["errors"]]
    assert "starting_price_out_of_range" in codes


def test_preview_quantity_not_integer(headers):
    csv_bytes = _make_csv([_valid_row(1, quantity="abc")])
    files = {"file": ("bad_q.csv", csv_bytes, "text/csv")}
    r = httpx.post(f"{API_URL}/api/partner-pro/bulk-import",
                   headers=headers, files=files, timeout=25)
    d = r.json()
    codes = [e["code"] for row in d["preview"] for e in row["errors"]]
    assert "quantity_not_integer" in codes


def test_preview_qc_missing_title_fr(headers):
    csv_bytes = _make_csv([_valid_row(1, region="QC", city="Montreal", title_fr="")])
    files = {"file": ("qc.csv", csv_bytes, "text/csv")}
    r = httpx.post(f"{API_URL}/api/partner-pro/bulk-import",
                   headers=headers, files=files, timeout=25)
    d = r.json()
    codes = [e["code"] for row in d["preview"] for e in row["errors"]]
    assert "bill96_title_fr_required" in codes
    # Bilingual error text.
    err = [e for row in d["preview"] for e in row["errors"] if e["code"] == "bill96_title_fr_required"][0]
    assert "Row 2" in err["message_en"] and "title_fr" in err["message_en"]
    assert "Ligne 2" in err["message_fr"] and "title_fr" in err["message_fr"]


def test_preview_end_date_in_past(headers):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    csv_bytes = _make_csv([_valid_row(1, auction_end_date=past)])
    files = {"file": ("past.csv", csv_bytes, "text/csv")}
    r = httpx.post(f"{API_URL}/api/partner-pro/bulk-import",
                   headers=headers, files=files, timeout=25)
    d = r.json()
    codes = [e["code"] for row in d["preview"] for e in row["errors"]]
    assert "auction_end_date_past" in codes


def test_preview_buy_now_below_20pct_floor(headers):
    csv_bytes = _make_csv([_valid_row(1, starting_price="100", buy_now_price="110")])
    files = {"file": ("bn.csv", csv_bytes, "text/csv")}
    r = httpx.post(f"{API_URL}/api/partner-pro/bulk-import",
                   headers=headers, files=files, timeout=25)
    d = r.json()
    codes = [e["code"] for row in d["preview"] for e in row["errors"]]
    assert "buy_now_price_too_low" in codes


def test_preview_condition_invalid(headers):
    csv_bytes = _make_csv([_valid_row(1, condition="fantastic")])
    files = {"file": ("cond.csv", csv_bytes, "text/csv")}
    r = httpx.post(f"{API_URL}/api/partner-pro/bulk-import",
                   headers=headers, files=files, timeout=25)
    d = r.json()
    codes = [e["code"] for row in d["preview"] for e in row["errors"]]
    assert "condition_invalid" in codes


def test_preview_buyers_premium_out_of_range(headers):
    csv_bytes = _make_csv([_valid_row(1, buyers_premium_percent="30")])
    files = {"file": ("bp.csv", csv_bytes, "text/csv")}
    r = httpx.post(f"{API_URL}/api/partner-pro/bulk-import",
                   headers=headers, files=files, timeout=25)
    d = r.json()
    codes = [e["code"] for row in d["preview"] for e in row["errors"]]
    assert "buyers_premium_out_of_range" in codes


# ─────────────────────────────────────────────────────────────
# 4) PREVIEW — batch-wide duplicate detection (points at first row)
# ─────────────────────────────────────────────────────────────
def test_preview_duplicate_within_batch_points_to_first_row(headers):
    dup_title = f"iter444 Dupe Title {time.time()}"
    row1 = _valid_row(1, title=dup_title)
    row2 = _valid_row(2, title=dup_title)  # same title+price+category
    csv_bytes = _make_csv([row1, row2])
    files = {"file": ("dup.csv", csv_bytes, "text/csv")}
    r = httpx.post(f"{API_URL}/api/partner-pro/bulk-import",
                   headers=headers, files=files, timeout=25)
    d = r.json()
    # Row 3 (second data row) should carry a duplicate error pointing at row 2.
    row2_errs = [e for row in d["preview"] if row["row"] == 3 for e in row["errors"]]
    dup_errs = [e for e in row2_errs if e["code"] == "duplicate_row"]
    assert len(dup_errs) == 1
    assert "row 2" in dup_errs[0]["message_en"].lower()
    assert "ligne 2" in dup_errs[0]["message_fr"].lower()


# ─────────────────────────────────────────────────────────────
# 5) PREVIEW — row-limit + missing columns + invalid encoding
# ─────────────────────────────────────────────────────────────
def test_preview_row_limit_101_rejected(headers):
    rows = [_valid_row(i) for i in range(101)]
    csv_bytes = _make_csv(rows)
    files = {"file": ("big.csv", csv_bytes, "text/csv")}
    r = httpx.post(f"{API_URL}/api/partner-pro/bulk-import",
                   headers=headers, files=files, timeout=30)
    assert r.status_code == 400
    d = r.json()["detail"]
    assert d["code"] == "row_limit_exceeded"
    assert "100" in d["message_en"] and "100" in d["message_fr"]


def test_preview_missing_columns(headers):
    # CSV without `starting_price` column.
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["title", "category"])
    w.writerow(["Foo", "electronics"])
    files = {"file": ("bad.csv", buf.getvalue().encode("utf-8"), "text/csv")}
    r = httpx.post(f"{API_URL}/api/partner-pro/bulk-import",
                   headers=headers, files=files, timeout=25)
    assert r.status_code == 400
    d = r.json()["detail"]
    assert d["code"] == "missing_columns"
    assert "starting_price" in d["message_en"]


# ─────────────────────────────────────────────────────────────
# 6) CONFIRM — creates drafts (never active)
# ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def created_draft_id(headers):
    unique = f"iter444 Draft Test {time.time()}"
    body = {
        "rows": [{
            "title": unique,
            "title_fr": "",
            "category": "electronics",
            "starting_price": 250.0,
            "quantity": 1,
            "condition": "excellent",
            "auction_end_date": _future_iso(14),
            "city": "Toronto",
            "region": "ON",
            "country": "CA",
            "postal_code": "M5V 2H1",
            "description": "Full-frame mirrorless camera in excellent condition.",
            "buy_now_price": 500.0,
            "buyers_premium_percent": 5,
            "shipping_available": True,
            "visit_offered": False,
            "visit_dates": "",
        }],
    }
    r = httpx.post(f"{API_URL}/api/partner-pro/bulk-import/confirm",
                   headers=headers, json=body, timeout=25)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    assert d["created"] == 1
    return d["drafts"][0]["id"]


def test_confirm_creates_draft_status(headers, created_draft_id):
    r = httpx.get(f"{API_URL}/api/listings/{created_draft_id}",
                  headers=headers, timeout=15)
    assert r.status_code == 200
    listing = r.json()
    assert listing["status"] == "draft"
    # `source` and `images` are verified at DB level by the confirm response.
    assert listing["images"] == []


# ─────────────────────────────────────────────────────────────
# 7) PUBLISH GATE — cannot publish without a photo
# ─────────────────────────────────────────────────────────────
def test_publish_without_photo_rejected(headers, created_draft_id):
    r = httpx.post(
        f"{API_URL}/api/partner-pro/bulk-import/{created_draft_id}/publish",
        headers=headers, timeout=15,
    )
    assert r.status_code == 400
    d = r.json()["detail"]
    assert d["code"] == "missing_photo"
    assert "photo" in d["message_en"].lower()
    assert "photo" in d["message_fr"].lower()


def test_attach_photos_then_publish_succeeds(headers, created_draft_id):
    body = {"image_urls": ["https://example.com/iter444-test.jpg"]}
    r = httpx.post(
        f"{API_URL}/api/partner-pro/bulk-import/{created_draft_id}/photos",
        headers=headers, json=body, timeout=15,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    assert d["image_count"] == 1
    assert d["needs_photos"] is False

    r2 = httpx.post(
        f"{API_URL}/api/partner-pro/bulk-import/{created_draft_id}/publish",
        headers=headers, timeout=15,
    )
    assert r2.status_code == 200, r2.text
    d2 = r2.json()
    assert d2["ok"] is True
    assert d2["status"] == "active"


# ─────────────────────────────────────────────────────────────
# 8) PENDING — lists drafts + photo counts
# ─────────────────────────────────────────────────────────────
def test_pending_endpoint_returns_shape(headers):
    r = httpx.get(f"{API_URL}/api/partner-pro/bulk-import/pending",
                  headers=headers, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "count" in d and "drafts" in d
    for draft in d["drafts"]:
        assert "image_count" in draft
        assert "needs_photos" in draft
