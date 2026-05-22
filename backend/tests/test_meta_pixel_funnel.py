"""
iter218 — Meta Pixel + Catalog match-rate parity tests.

These tests lock down the content_id format across:
    - backend/services/meta_feed_mapper.py::_content_id()       (Catalog feed)
    - backend/services/analytics_tracker.py::canonical_content_id() (CAPI)
    - frontend/src/utils/metaContentId.js::getCanonicalContentId() (Pixel)

If any of these three diverge, Meta's catalog match rate drops to 0%.
"""
import pytest
import re

from services.meta_feed_mapper import _content_id, TYPE_PREFIX as FEED_TYPE_PREFIX
from services.analytics_tracker import (
    canonical_content_id,
    canonical_content_type,
    deterministic_event_id,
    build_purchase_event,
    build_user_data,
    _TYPE_PREFIX_MAP as TRACKER_PREFIX_MAP,
)


# ─────────────────────────────────────────────────────────────────────
# 1. Type-prefix parity — Pixel ↔ Feed ↔ CAPI
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ltype, expected",
    [
        ("marketplace", "MKT"),
        ("single",      "MKT"),
        ("lots",        "LOT"),
        ("multi_lot",   "LOT"),
        ("vehicle",     "VEH"),
        ("storage",     "STO"),
        ("storage_locker", "STO"),
    ],
)
def test_capi_type_prefix_matches_feed(ltype, expected):
    """analytics_tracker MUST share the exact prefix mapping with the feed."""
    capi_id = canonical_content_id(ltype, "test-uuid-1234")
    assert capi_id == f"BIDVEX-{expected}-test-uuid-1234"


def test_feed_and_capi_produce_identical_content_id_for_same_listing():
    """Catalog row and CAPI Purchase event MUST share the same content_id."""
    for ltype in ("marketplace", "lots", "vehicle", "storage"):
        listing_id = "abc-123-def-456"
        feed_id = _content_id(ltype, listing_id)
        capi_id = canonical_content_id(ltype, listing_id)
        assert feed_id == capi_id, (
            f"Catalog feed and CAPI diverged for type={ltype!r}: "
            f"feed={feed_id!r} capi={capi_id!r}"
        )


def test_canonical_content_id_handles_unknown_type():
    """Unknown listing_type defaults to marketplace ('MKT')."""
    cid = canonical_content_id("__unknown__", "uuid-x")
    assert cid == "BIDVEX-MKT-uuid-x"


def test_canonical_content_id_none_listing_id():
    assert canonical_content_id("vehicle", None) is None
    assert canonical_content_id("vehicle", "") is None


# ─────────────────────────────────────────────────────────────────────
# 2. content_type parity
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ltype, expected",
    [
        ("vehicle",  "vehicle"),
        ("vehicles", "vehicle"),
        ("vehicle_dealer", "vehicle"),
        ("marketplace", "product"),
        ("lots", "product"),
        ("storage", "product"),
        (None, "product"),
        ("", "product"),
    ],
)
def test_canonical_content_type(ltype, expected):
    assert canonical_content_type(ltype) == expected


# ─────────────────────────────────────────────────────────────────────
# 3. Deterministic event_id — FE ↔ BE deduplication
# ─────────────────────────────────────────────────────────────────────


def test_deterministic_event_id_format():
    """Event ID format MUST match frontend metaContentId.js::buildEventId."""
    eid = deterministic_event_id(
        event_name="Purchase",
        content_id="BIDVEX-VEH-abc-123",
        discriminator="session_cs_test_xyz",
    )
    assert eid == "bidvex_purchase_BIDVEX-VEH-abc-123_session_cs_test_xyz"


def test_deterministic_event_id_no_discriminator():
    eid = deterministic_event_id(event_name="ViewContent", content_id="BIDVEX-MKT-abc")
    assert eid == "bidvex_viewcontent_BIDVEX-MKT-abc"


def test_deterministic_event_id_strips_whitespace():
    """Whitespace in inputs would break Meta's dedup matching."""
    eid = deterministic_event_id(
        event_name=" Purchase ",
        content_id="BIDVEX-MKT-abc",
        discriminator="session 123",
    )
    # event_name lowercased + stripped of inner ws via final replace
    assert " " not in eid


# ─────────────────────────────────────────────────────────────────────
# 4. build_purchase_event — content_ids carried through
# ─────────────────────────────────────────────────────────────────────


def test_build_purchase_event_includes_content_ids():
    user_data = build_user_data(email="x@y.com", country="ca")
    ev = build_purchase_event(
        platform_fee=375,
        broker_fee=500,
        user_data=user_data,
        event_id="bidvex_purchase_BIDVEX-VEH-uuid-1_session_cs_test",
        content_ids=["BIDVEX-VEH-uuid-1"],
        content_type="vehicle",
        content_name="2018 Honda Civic",
        content_category="vehicle",
    )
    cd = ev["custom_data"]
    assert cd["content_ids"] == ["BIDVEX-VEH-uuid-1"]
    assert cd["content_type"] == "vehicle"
    assert cd["content_name"] == "2018 Honda Civic"
    assert cd["num_items"] == 1
    assert cd["value"] == 875.0  # 375 + 500
    assert cd["contents"] == [
        {"id": "BIDVEX-VEH-uuid-1", "quantity": 1, "item_price": 875.0}
    ]
    assert ev["event_id"] == "bidvex_purchase_BIDVEX-VEH-uuid-1_session_cs_test"


def test_build_purchase_event_legacy_fallback_when_no_content_ids():
    """Legacy callers without content_ids still get a valid event payload."""
    ev = build_purchase_event(
        platform_fee=100,
        broker_fee=50,
        user_data={},
    )
    cd = ev["custom_data"]
    assert "content_ids" not in cd  # backwards-compat: omitted when not supplied
    assert cd["content_type"] == "product"
    assert cd["content_name"] == "BidVex Broker Service Fees"
    assert cd["value"] == 150.0


# ─────────────────────────────────────────────────────────────────────
# 5. content_id format strict regex
# ─────────────────────────────────────────────────────────────────────


_CONTENT_ID_RE = re.compile(r"^BIDVEX-(MKT|LOT|VEH|STO)-[A-Za-z0-9_\-]+$")


@pytest.mark.parametrize(
    "ltype, lid",
    [
        ("marketplace", "385b5477-7510-4b5e-8225-6f0dadf9b2b9"),
        ("vehicle",     "veh-uuid-001"),
        ("storage",     "stor-uuid-002"),
        ("lots",        "lots-uuid-003"),
    ],
)
def test_content_id_passes_meta_strict_regex(ltype, lid):
    """Catalog match requires strict alphanumeric + dash format."""
    cid = canonical_content_id(ltype, lid)
    assert _CONTENT_ID_RE.match(cid), f"Bad content_id format: {cid!r}"


def test_content_id_never_contains_locked_prefix():
    """Regression guard for the legacy `locked-<uuid>` bug that broke
    catalog ingestion in the previous session."""
    cid = canonical_content_id("marketplace", "385b5477-7510-4b5e-8225-6f0dadf9b2b9")
    assert "locked-" not in cid
    assert "auction_" not in cid
    assert "listing_" not in cid


# ─────────────────────────────────────────────────────────────────────
# 6. Type-prefix maps internal consistency
# ─────────────────────────────────────────────────────────────────────


def test_tracker_prefix_map_superset_of_feed_map():
    """analytics_tracker must support every type the feed knows about."""
    for k, v in FEED_TYPE_PREFIX.items():
        assert TRACKER_PREFIX_MAP.get(k) == v, (
            f"Prefix divergence for {k!r}: feed={v!r} tracker={TRACKER_PREFIX_MAP.get(k)!r}"
        )
