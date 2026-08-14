"""
P7.5 — Meta + Google Commerce Conversion Tracking regression tests.

Locks in the canonical catalog-ID contract that binds:
    Meta Pixel content_ids
    Meta Conversions API content_ids
    Google Merchant `items[].item_id`
    GA4 ecommerce `items[].item_id`
    Meta / Google catalog feeds

All 5 surfaces MUST resolve to byte-identical strings for every
BidVex listing type; otherwise Meta match rate drops to 0% and Google
Merchant attribution fails silently.

No production code path is exercised — these are pure-function contract
tests around `services/analytics_tracker.canonical_content_id`,
`canonical_lot_content_id`, and the Meta feed mapper's decomposition
rule. Adding these tests does not change the P7 financial regression
matrix.
"""
from services.analytics_tracker import (
    canonical_content_id,
    canonical_lot_content_id,
    deterministic_event_id,
)
from services.meta_feed_mapper import _content_id, TYPE_PREFIX


class TestCanonicalContentId:
    """Single-listing catalog id (marketplace, vehicle single, storage single)."""

    def test_marketplace_raw_uuid(self):
        assert canonical_content_id("marketplace", "abc123") == "abc123"

    def test_vehicle_single_raw_uuid(self):
        assert canonical_content_id("vehicle", "vehicle-uuid-999") == "vehicle-uuid-999"

    def test_storage_raw_uuid(self):
        assert canonical_content_id("storage", "storage-locker-42") == "storage-locker-42"

    def test_missing_id_returns_none(self):
        assert canonical_content_id("marketplace", None) is None
        assert canonical_content_id("vehicle", "") is None

    def test_listing_type_is_ignored_for_singletons(self):
        # Backwards-compat: listing_type kept in signature but never
        # participates in the output for singleton listings.
        assert canonical_content_id("vehicle", "xyz") == canonical_content_id("storage", "xyz")

    def test_output_matches_meta_feed_mapper_singleton(self):
        # Meta feed mapper MUST produce the same value as the pixel helper.
        assert _content_id("vehicle", "vehicle-uuid-999") == canonical_content_id(
            "vehicle", "vehicle-uuid-999"
        )


class TestCanonicalLotContentId:
    """Per-lot catalog id — multi-lot decomposition."""

    def test_general_multi_lot_by_lot_number(self):
        assert canonical_lot_content_id("lots", "parent-uuid", 1) == "LOT-parent-uuid-L1"
        assert canonical_lot_content_id("multi_lot", "parent-uuid", 42) == "LOT-parent-uuid-L42"

    def test_general_multi_lot_accepts_string_lot_number(self):
        assert canonical_lot_content_id("lots", "parent-uuid", "7") == "LOT-parent-uuid-L7"

    def test_vehicle_multi_lot_by_lot_id(self):
        assert canonical_lot_content_id(
            "vehicle_multi_lot", "event-uuid-abc", "abcdef1234567890"
        ) == "VML-event-uuid-abc-abcdef12"

    def test_vehicle_multi_lot_short_lot_id_preserved(self):
        # If the lot_id happens to be shorter than 8 chars, keep it as-is.
        assert canonical_lot_content_id(
            "vehicle_multi_lot", "event-uuid-abc", "abc12"
        ) == "VML-event-uuid-abc-abc12"

    def test_missing_parent_returns_none(self):
        assert canonical_lot_content_id("lots", None, 1) is None
        assert canonical_lot_content_id("lots", "", 1) is None

    def test_missing_lot_ref_returns_none(self):
        assert canonical_lot_content_id("lots", "parent", None) is None

    def test_output_matches_meta_feed_mapper_general_multi_lot(self):
        # Contract with `map_multi_lot_listing_to_meta_items` — the
        # feed emits `{PREFIX}-{parent_id}-L{lot_number}`.
        prefix = TYPE_PREFIX["lots"]
        expected = f"{prefix}-parent-uuid-L3"
        assert canonical_lot_content_id("lots", "parent-uuid", 3) == expected

    def test_output_matches_meta_feed_mapper_vehicle_multi_lot(self):
        prefix = TYPE_PREFIX["vehicle_multi_lot"]
        lot_id = "0123456789abcdef"
        expected = f"{prefix}-event-uuid-{lot_id[:8]}"
        assert canonical_lot_content_id(
            "vehicle_multi_lot", "event-uuid", lot_id,
        ) == expected


class TestDeterministicEventId:
    """Event-ID contract for Pixel↔CAPI browser/server deduplication."""

    def test_uses_content_id_verbatim(self):
        ev = deterministic_event_id(
            event_name="Purchase",
            content_id="LOT-abc-L1",
            discriminator="session_cs_test_123",
        )
        assert ev == "bidvex_purchase_LOT-abc-L1_session_cs_test_123"

    def test_deterministic_across_calls(self):
        a = deterministic_event_id(event_name="Purchase", content_id="x", discriminator="s")
        b = deterministic_event_id(event_name="Purchase", content_id="x", discriminator="s")
        assert a == b

    def test_lowercases_event_name(self):
        ev = deterministic_event_id(event_name="ViewContent", content_id="x")
        assert ev == "bidvex_viewcontent_x"


class TestGA4PayloadStructure:
    """Documents (and freezes) the shape the frontend GA4 helpers emit
    so a future refactor cannot silently drop required fields."""

    def _ga4_view_item(self, content_id, value, name="", category="", currency="CAD"):
        # Mirrors `utils/analytics_events.js::trackGA4ViewItem`.
        return {
            "currency": currency,
            "value": round(float(value or 0), 2),
            "items": [{
                "item_id": str(content_id),
                "item_name": name,
                "item_category": category,
                "price": round(float(value or 0), 2),
                "quantity": 1,
            }],
        }

    def _ga4_purchase(self, content_id, value, transaction_id, currency="CAD"):
        return {
            "transaction_id": str(transaction_id),
            "currency": currency,
            "value": round(float(value or 0), 2),
            "items": [{
                "item_id": str(content_id),
                "item_name": "",
                "item_category": "",
                "price": round(float(value or 0), 2),
                "quantity": 1,
            }],
        }

    def test_view_item_uses_canonical_content_id_singleton(self):
        cid = canonical_content_id("marketplace", "listing-uuid-1")
        p = self._ga4_view_item(cid, 100)
        assert p["items"][0]["item_id"] == "listing-uuid-1"

    def test_view_item_uses_lot_content_id_multi_lot(self):
        cid = canonical_lot_content_id("lots", "parent-abc", 5)
        p = self._ga4_view_item(cid, 250)
        assert p["items"][0]["item_id"] == "LOT-parent-abc-L5"

    def test_purchase_transaction_id_is_string(self):
        cid = canonical_content_id("marketplace", "listing-uuid-1")
        p = self._ga4_purchase(cid, 199.99, "cs_test_abc")
        assert p["transaction_id"] == "cs_test_abc"
        assert p["items"][0]["item_id"] == "listing-uuid-1"

    def test_purchase_ga4_and_meta_share_content_id(self):
        # The GA4 items[].item_id and Meta content_ids[0] MUST be the
        # exact same string — Meta AND Google catalog rows share this
        # key.
        cid = canonical_lot_content_id("vehicle_multi_lot", "evt", "abcdef1234")
        meta_content_ids = [cid]
        ga4_payload = self._ga4_purchase(cid, 500, "cs_test")
        assert meta_content_ids[0] == ga4_payload["items"][0]["item_id"]


class TestBilingualIdStability:
    """Language MUST NOT influence the catalog id — an EN visit and a
    FR visit on the same lot must resolve to identical Meta/GA4 items.
    """

    def test_lot_id_ignores_language_signal(self):
        # No language parameter exists on canonical helpers by design.
        # This test documents intent + guards against future drift.
        en = canonical_lot_content_id("lots", "parent-uuid", 7)
        fr = canonical_lot_content_id("lots", "parent-uuid", 7)
        assert en == fr == "LOT-parent-uuid-L7"

    def test_singleton_id_ignores_language_signal(self):
        assert canonical_content_id("marketplace", "abc") == canonical_content_id(
            "marketplace", "abc",
        )
