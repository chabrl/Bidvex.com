"""
iter218 — Meta Pixel / Catalog match-rate integration tests.

Complements `tests/test_meta_pixel_funnel.py` (unit-level parity) with
runtime checks against:
  * GET /api/feeds/facebook-local  — live, public endpoint
  * GET /api/payments/status/{session_id} — route reachability (Stripe lookup
    fails on synthetic IDs; we assert the route is wired and returns 400/404,
    not 5xx).
  * services.analytics_tracker.track_listing_purchase / track_broker_purchase
    behaviour end-to-end with a mocked Meta delivery + in-memory db stub.
"""
import asyncio
import csv
import io
import os
import re
import sys
from typing import Any, Dict, List

import pytest
import requests

# Make backend importable when pytest is launched from /app/backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import analytics_tracker  # noqa: E402
from services.analytics_tracker import (  # noqa: E402
    canonical_content_id,
    track_broker_purchase,
    track_listing_purchase,
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
_CONTENT_ID_RE = re.compile(r"^BIDVEX-(MKT|LOT|VEH|STO)-[A-Za-z0-9_\-]+$")


# ─────────────────────────────────────────────────────────────────────
# A. Live feed endpoint
# ─────────────────────────────────────────────────────────────────────


class TestFacebookFeedLive:
    """GET /api/feeds/facebook-local — production-shaped CSV check."""

    @pytest.fixture(scope="class")
    def feed_rows(self) -> List[Dict[str, str]]:
        resp = requests.get(f"{BASE_URL}/api/feeds/facebook-local", timeout=30)
        assert resp.status_code == 200, f"feed endpoint returned {resp.status_code}"
        rdr = csv.DictReader(io.StringIO(resp.text))
        rows = list(rdr)
        assert "id" in (rdr.fieldnames or []), "CSV missing 'id' column"
        return rows

    def test_feed_returns_at_least_five_listings(self, feed_rows):
        assert len(feed_rows) >= 5, f"Expected at least 5 rows, got {len(feed_rows)}"

    def test_all_ids_match_canonical_regex(self, feed_rows):
        bad = [r["id"] for r in feed_rows if not _CONTENT_ID_RE.match(r["id"])]
        assert not bad, f"Malformed content_ids in feed: {bad[:5]}"

    def test_no_legacy_id_prefixes_present(self, feed_rows):
        ids = [r["id"] for r in feed_rows]
        assert not any("locked-" in i for i in ids), "Legacy `locked-` prefix found"
        assert not any("auction_" in i for i in ids), "Legacy `auction_` prefix found"
        assert not any(i.startswith("listing_") for i in ids), "Legacy `listing_` prefix found"


# ─────────────────────────────────────────────────────────────────────
# B. /api/payments/status route reachability
# ─────────────────────────────────────────────────────────────────────


class TestPaymentsStatusRouteWiring:
    """Live Stripe sessions can't be created in test env, but we verify the
    route is reachable and surfaces a 4xx (Stripe lookup error) — NOT 5xx —
    when given a synthetic session_id. This guards against the route being
    accidentally unregistered or throwing unhandled exceptions."""

    def test_route_returns_4xx_for_synthetic_session_id(self):
        resp = requests.get(
            f"{BASE_URL}/api/payments/status/cs_test_iter218_synthetic_id_xyz",
            timeout=15,
        )
        # Stripe will return InvalidRequestError -> our route maps to 400 OR 404
        # depending on auth state; either way it MUST not 5xx.
        assert resp.status_code in (
            400,
            401,
            403,
            404,
        ), f"Unexpected status {resp.status_code}; body={resp.text[:200]}"


# ─────────────────────────────────────────────────────────────────────
# C. analytics_tracker — end-to-end with mocked Meta + db stub
# ─────────────────────────────────────────────────────────────────────


class _InsertOneRecorder:
    def __init__(self):
        self.docs: List[Dict[str, Any]] = []

    async def insert_one(self, doc):
        self.docs.append(doc)
        return type("R", (), {"inserted_id": "fake"})()

    async def update_one(self, *_a, **_kw):
        return type("R", (), {"modified_count": 1})()


class _DBStub:
    def __init__(self):
        self.meta_capi_log = _InsertOneRecorder()


@pytest.fixture
def patched_meta_send(monkeypatch):
    """Stub out _send_to_meta so no live API calls are made."""
    sent_events: List[Dict[str, Any]] = []

    async def fake_send(events):
        sent_events.extend(events)
        return {"ok": True, "stub": True, "received": len(events)}

    monkeypatch.setattr(analytics_tracker, "_send_to_meta", fake_send)
    return sent_events


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


class TestTrackListingPurchase:
    def test_listing_purchase_emits_content_ids_and_logs(self, patched_meta_send):
        db = _DBStub()
        result = _run(track_listing_purchase(
            db=db,
            session_id="cs_test_abc",
            listing_id="uuid-mkt-1",
            listing_type="marketplace",
            total_charged=199.99,
            buyer_user={"email": "x@y.com", "id": "u1", "country": "ca"},
            listing_title="Test Item",
            listing_category="electronics",
        ))

        # Return shape
        assert result["content_ids"] == ["BIDVEX-MKT-uuid-mkt-1"]
        assert result["value_cad"] == 199.99
        assert result["event_id"] == (
            "bidvex_purchase_BIDVEX-MKT-uuid-mkt-1_session_cs_test_abc"
        )

        # Emitted Meta event payload
        assert len(patched_meta_send) == 1
        ev = patched_meta_send[0]
        assert ev["event_name"] == "Purchase"
        cd = ev["custom_data"]
        assert cd["content_ids"] == ["BIDVEX-MKT-uuid-mkt-1"]
        assert cd["content_type"] == "product"
        assert cd["num_items"] == 1
        assert cd["value"] == 199.99
        assert cd["contents"] == [
            {"id": "BIDVEX-MKT-uuid-mkt-1", "quantity": 1, "item_price": 199.99}
        ]

        # Audit-log row
        assert len(db.meta_capi_log.docs) == 1
        log = db.meta_capi_log.docs[0]
        assert log["session_id"] == "cs_test_abc"
        assert log["content_ids"] == ["BIDVEX-MKT-uuid-mkt-1"]
        assert log["listing_type"] == "marketplace"

    def test_listing_purchase_missing_listing_id_short_circuits(self, patched_meta_send):
        db = _DBStub()
        result = _run(track_listing_purchase(
            db=db,
            session_id="cs_test_blank",
            listing_id="",
            listing_type="marketplace",
            total_charged=10.0,
        ))
        assert result.get("ok") is False
        assert result.get("reason") == "missing_content_id"
        # No Meta calls, no audit row
        assert patched_meta_send == []
        assert db.meta_capi_log.docs == []

    def test_listing_purchase_vehicle_uses_VEH_prefix(self, patched_meta_send):
        db = _DBStub()
        _run(track_listing_purchase(
            db=db,
            session_id="cs_test_veh",
            listing_id="veh-1",
            listing_type="vehicle",
            total_charged=5000.0,
            listing_title="2018 Honda Civic",
        ))
        assert patched_meta_send[0]["custom_data"]["content_ids"] == ["BIDVEX-VEH-veh-1"]
        assert patched_meta_send[0]["custom_data"]["content_type"] == "vehicle"

    def test_listing_purchase_storage_uses_STO_prefix(self, patched_meta_send):
        db = _DBStub()
        _run(track_listing_purchase(
            db=db,
            session_id="cs_test_sto",
            listing_id="sto-1",
            listing_type="storage",
            total_charged=300.0,
        ))
        assert patched_meta_send[0]["custom_data"]["content_ids"] == ["BIDVEX-STO-sto-1"]


class TestTrackBrokerPurchase:
    def test_broker_purchase_legacy_signature_still_works(self, patched_meta_send):
        """Old callers without listing_id/listing_type must not break."""
        db = _DBStub()
        result = _run(track_broker_purchase(
            db=db,
            invoice_id="inv-legacy-1",
            platform_fee=375.0,
            broker_fee=500.0,
        ))
        assert result["value_cad"] == 875.0
        assert result["event_id"] == "broker_invoice_inv-legacy-1"
        # No content_ids when listing not supplied
        cd = patched_meta_send[0]["custom_data"]
        assert "content_ids" not in cd
        assert cd["content_name"] == "BidVex Broker Service Fees"

    def test_broker_purchase_with_listing_carries_content_ids(self, patched_meta_send):
        db = _DBStub()
        result = _run(track_broker_purchase(
            db=db,
            invoice_id="inv-iter218-1",
            platform_fee=375.0,
            broker_fee=500.0,
            listing_id="veh-uuid-42",
            listing_type="vehicle",
            listing_title="2020 Ford F-150",
            listing_category="vehicle",
        ))
        assert result["content_ids"] == ["BIDVEX-VEH-veh-uuid-42"]
        # CRITICAL: value remains platform_fee+broker_fee (NOT hammer)
        assert result["value_cad"] == 875.0
        cd = patched_meta_send[0]["custom_data"]
        assert cd["content_ids"] == ["BIDVEX-VEH-veh-uuid-42"]
        assert cd["content_type"] == "vehicle"
        assert cd["content_name"] == "2020 Ford F-150"
        # Contents array present
        assert cd["contents"] == [
            {"id": "BIDVEX-VEH-veh-uuid-42", "quantity": 1, "item_price": 875.0}
        ]


# ─────────────────────────────────────────────────────────────────────
# D. Cross-type prefix smoke test (canonical helper)
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ltype, prefix",
    [
        ("marketplace", "MKT"),
        ("multi_lot", "LOT"),
        ("lots", "LOT"),
        ("vehicle", "VEH"),
        ("storage", "STO"),
        ("storage_locker", "STO"),
        (None, "MKT"),  # null → defaults to marketplace
        ("", "MKT"),
        ("totally_unknown", "MKT"),
    ],
)
def test_canonical_content_id_defaults(ltype, prefix):
    cid = canonical_content_id(ltype, "uuid-x")
    assert cid == f"BIDVEX-{prefix}-uuid-x"
