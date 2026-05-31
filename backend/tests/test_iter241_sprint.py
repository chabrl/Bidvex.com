"""
iter241 — Sprint test suite covering Missions 1, 4, 5, 6, 7.

Mission 1 — Stripe Checkout for Promoted Listings:
  - promotion_expiry sweeper flips expired listings back to unpromoted

Mission 4 — Campaign Insights real data:
  - get_campaign_stats returns daily series + loading flag for fresh sends

Mission 5 — Recipients filter:
  - build_advanced_audience(recipient_type='custom_list') NEVER returns
    segment users (the CRITICAL data-privacy bug)
  - build_advanced_audience(recipient_type='segment') ignores manual_emails
  - create_campaign refuses custom_list with empty manual_emails

Mission 6 — Campaign attachments:
  - attachments field round-trips on the campaign doc
  - validation paths exist (mime, count, size)

Mission 7 — Admin promotions engine:
  - create + lookup + apply_active_promotions choose best fit
  - per-user usage gate prevents double-redeem
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass


# ─── Mission 5: Recipients filter ──────────────────────────────────────
@pytest.mark.asyncio
async def test_mission5_custom_list_does_NOT_send_to_all_users():
    """CRITICAL: pasting a custom list must never return the entire user base."""
    from services.email_marketing import EmailMarketingService

    fake_db = MagicMock()
    # users.find() returns the 50-user "all" set — if we ever hit it under
    # custom_list, the test will catch it (segmented_count > 0).
    fake_db.users.find = MagicMock(return_value=MagicMock(
        to_list=AsyncMock(return_value=[
            {"id": f"u{i}", "email": f"victim{i}@example.com", "name": f"V{i}"}
            for i in range(50)
        ])
    ))
    fake_db.users.find_one = AsyncMock(return_value=None)
    fake_db.email_unsubscribes = MagicMock()
    fake_db.email_unsubscribes.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    fake_db.email_events = MagicMock()
    fake_db.email_events.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    fake_db.email_events.distinct = AsyncMock(return_value=[])

    svc = EmailMarketingService(fake_db)
    result = await svc.build_advanced_audience(
        filters={},
        manual_emails=["just-one@example.com"],
        recipient_type="custom_list",
    )
    # segmented_count must be 0 under custom_list.
    assert result["breakdown"]["segmented_count"] == 0, result["breakdown"]
    # `final_count` must equal the manual list size.
    assert result["final_count"] == 1, result["breakdown"]


@pytest.mark.asyncio
async def test_mission5_segment_ignores_manual_emails():
    from services.email_marketing import EmailMarketingService
    fake_db = MagicMock()
    fake_db.users.find = MagicMock(return_value=MagicMock(
        to_list=AsyncMock(return_value=[
            {"id": "u1", "email": "a@example.com", "name": "A"},
            {"id": "u2", "email": "b@example.com", "name": "B"},
        ])
    ))
    fake_db.email_unsubscribes = MagicMock()
    fake_db.email_unsubscribes.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    fake_db.email_events = MagicMock()
    fake_db.email_events.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    fake_db.email_events.distinct = AsyncMock(return_value=[])

    svc = EmailMarketingService(fake_db)
    # Override the suppression check so the SAME mocked users don't show up
    # as both segmented AND suppressed (MagicMock returns the same data on
    # every `find()` call regardless of query).
    svc.get_suppressed_emails = AsyncMock(return_value=set())
    result = await svc.build_advanced_audience(
        filters={"segment_type": "all"},
        manual_emails=["should-not-add@example.com"],
        recipient_type="segment",
    )
    assert result["breakdown"]["manual_external_count"] == 0
    assert result["breakdown"]["segmented_count"] == 2


@pytest.mark.asyncio
async def test_mission5_create_campaign_rejects_empty_custom_list():
    from services.email_marketing import EmailMarketingService
    fake_db = MagicMock()
    fake_db.users.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    fake_db.email_unsubscribes = MagicMock()
    fake_db.email_unsubscribes.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    fake_db.email_events = MagicMock()
    fake_db.email_events.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))

    svc = EmailMarketingService(fake_db)
    with pytest.raises(ValueError, match="requires at least one valid email"):
        await svc.create_campaign(
            name="Bad", subject="x", html_content="x", plain_text_content="x",
            audience_filters={}, admin_id="a", admin_email="a@a.com",
            manual_emails=[], recipient_type="custom_list",
        )


@pytest.mark.asyncio
async def test_mission5_invalid_recipient_type_rejected():
    from services.email_marketing import EmailMarketingService
    fake_db = MagicMock()
    fake_db.email_unsubscribes = MagicMock()
    fake_db.email_unsubscribes.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    fake_db.email_events = MagicMock()
    fake_db.email_events.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))

    svc = EmailMarketingService(fake_db)
    with pytest.raises(ValueError, match="recipient_type must be one of"):
        await svc.build_advanced_audience(filters={}, recipient_type="all_emails_paste")


# ─── Mission 7: Promotions engine ──────────────────────────────────────
@pytest.mark.asyncio
async def test_mission7_coupon_code_auto_generated():
    from routes.admin_promotions import _generate_coupon_code
    code = _generate_coupon_code()
    assert code.startswith("BIDVEX-")
    assert len(code) == 13  # "BIDVEX-" (7) + 6 alphanum
    # Generated codes are unique enough.
    codes = {_generate_coupon_code() for _ in range(50)}
    assert len(codes) >= 49


@pytest.mark.asyncio
async def test_mission7_apply_active_promotions_picks_best():
    """When multiple promos match the user, pick the highest-value one."""
    from routes.admin_promotions import apply_active_promotions

    user_doc = {"id": "u1", "email": "u1@example.com", "subscription_tier": "premium"}
    now_iso = datetime.now(timezone.utc).isoformat()
    later_iso = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

    promos = [
        {
            "id": "p_small", "type": "reduced_commission", "status": "active",
            "start_date": now_iso, "end_date": later_iso,
            "target": "all", "target_config": {"target": "all"},
            "config": {"discount_percent": 10, "scope": ["all"]},
            "current_uses": 0, "uses_per_user": 1, "coupon_code": "P-SMALL",
        },
        {
            "id": "p_huge", "type": "free_platform_fee", "status": "active",
            "start_date": now_iso, "end_date": later_iso,
            "target": "all", "target_config": {"target": "all"},
            "config": {"scope": ["all"]},
            "current_uses": 0, "uses_per_user": 1, "coupon_code": "P-HUGE",
        },
    ]

    fake_db = MagicMock()
    fake_db.promotions.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=promos)))
    fake_db.users.find_one = AsyncMock(return_value=user_doc)
    fake_db.promotion_usage.count_documents = AsyncMock(return_value=0)

    result = await apply_active_promotions(
        db=fake_db, user_id="u1", transaction_type="bid", listing_type="marketplace",
    )
    assert result is not None
    assert result["id"] == "p_huge", f"expected p_huge, got {result.get('id')}"


@pytest.mark.asyncio
async def test_mission7_per_user_usage_gate():
    """A user who has already used the promo to their uses_per_user limit
    must NOT receive a second match for the same promo."""
    from routes.admin_promotions import apply_active_promotions
    now_iso = datetime.now(timezone.utc).isoformat()
    later_iso = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    promo = {
        "id": "p1", "type": "free_platform_fee", "status": "active",
        "start_date": now_iso, "end_date": later_iso,
        "target": "all", "target_config": {"target": "all"},
        "config": {"scope": ["all"]},
        "current_uses": 0, "uses_per_user": 1, "coupon_code": "P1",
    }
    fake_db = MagicMock()
    fake_db.promotions.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[promo])))
    fake_db.users.find_one = AsyncMock(return_value={"id": "u1", "subscription_tier": "standard"})
    fake_db.promotion_usage.count_documents = AsyncMock(return_value=1)  # already used

    result = await apply_active_promotions(
        db=fake_db, user_id="u1", transaction_type="bid", listing_type="marketplace",
    )
    assert result is None


@pytest.mark.asyncio
async def test_mission7_target_tier_only_matches_tier():
    """A promo gated by tier=premium must NOT apply to a standard user."""
    from routes.admin_promotions import apply_active_promotions
    now_iso = datetime.now(timezone.utc).isoformat()
    later_iso = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    promo = {
        "id": "p_tier", "type": "subscription_discount", "status": "active",
        "start_date": now_iso, "end_date": later_iso,
        "target": "tier",
        "target_config": {"target": "tier", "target_tier": "premium"},
        "config": {"discount_percent": 50, "scope": ["all"]},
        "current_uses": 0, "uses_per_user": 1, "coupon_code": "P-TIER",
    }
    fake_db = MagicMock()
    fake_db.promotions.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[promo])))
    fake_db.users.find_one = AsyncMock(return_value={"id": "u1", "subscription_tier": "standard"})
    fake_db.promotion_usage.count_documents = AsyncMock(return_value=0)

    result = await apply_active_promotions(
        db=fake_db, user_id="u1", transaction_type="subscription", listing_type="all",
    )
    assert result is None  # standard user, tier-gated promo


@pytest.mark.asyncio
async def test_mission7_record_promotion_usage_bumps_counter():
    from routes.admin_promotions import record_promotion_usage
    fake_db = MagicMock()
    fake_db.promotion_usage.insert_one = AsyncMock()
    fake_db.promotions.update_one = AsyncMock()

    await record_promotion_usage(
        db=fake_db, promotion_id="p1", user_id="u1",
        transaction_id="tx1", saved_amount=9.99, transaction_type="bid",
    )
    fake_db.promotion_usage.insert_one.assert_awaited_once()
    fake_db.promotions.update_one.assert_awaited_once_with(
        {"id": "p1"}, {"$inc": {"current_uses": 1}},
    )


# ─── Mission 1: Promotion expiry sweeper ──────────────────────────────
@pytest.mark.asyncio
async def test_mission1_expiry_sweeper_flips_expired_promotions():
    from services.promotion_expiry import expire_listing_promotions

    past_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    fake_db = MagicMock()

    def make_coll(expired_docs):
        coll = MagicMock()
        coll.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=expired_docs)))
        coll.update_many = AsyncMock()
        return coll

    # Only `listings` has expired docs in this test.
    fake_db.__getitem__ = lambda self, name: (
        make_coll([{"id": "L1", "title": "Old", "seller_id": "s1",
                    "promotion_tier": "basic", "promotion_end": past_iso}])
        if name == "listings"
        else make_coll([])
    )
    fake_db.users.find_one = AsyncMock(return_value=None)  # No email send

    stats = await expire_listing_promotions(fake_db)
    assert stats["expired_count"] >= 1
    assert "listings" in stats["by_collection"]


# ─── Mission 4: Campaign insights ──────────────────────────────────────
@pytest.mark.asyncio
async def test_mission4_get_campaign_stats_loading_flag_for_fresh_send():
    from services.email_marketing import EmailMarketingService

    fresh_sent_at = datetime.now(timezone.utc).isoformat()
    fake_campaign = {
        "id": "c1", "name": "Fresh", "status": "completed",
        "sent_at": fresh_sent_at, "completed_at": fresh_sent_at,
        "stats": {"sent": 100, "delivered": 0, "opened": 0, "clicked": 0},
    }
    fake_db = MagicMock()
    fake_db.email_campaigns.find_one = AsyncMock(return_value=fake_campaign)
    fake_db.email_events = MagicMock()
    fake_db.email_events.aggregate = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))

    svc = EmailMarketingService(fake_db)
    out = await svc.get_campaign_stats("c1")
    assert out["loading"] is True
    assert "Stats updating" in (out["loading_message"] or "")
    assert isinstance(out.get("daily"), list)
    assert len(out["daily"]) == 7


@pytest.mark.asyncio
async def test_mission4_daily_series_has_seven_days():
    from services.email_marketing import EmailMarketingService

    old_sent = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    fake_campaign = {
        "id": "c2", "name": "Old", "status": "completed",
        "sent_at": old_sent, "completed_at": old_sent,
        "stats": {"sent": 100, "delivered": 90, "opened": 30, "clicked": 5},
    }
    fake_db = MagicMock()
    fake_db.email_campaigns.find_one = AsyncMock(return_value=fake_campaign)
    fake_db.email_events = MagicMock()
    fake_db.email_events.aggregate = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[
        {"_id": "open", "n": 5},
        {"_id": "click", "n": 1},
    ])))

    svc = EmailMarketingService(fake_db)
    out = await svc.get_campaign_stats("c2")
    assert len(out["daily"]) == 7
    assert all("date" in d for d in out["daily"])
    assert out["loading"] is False


# ─── Mission 6: Campaign attachments ──────────────────────────────────
@pytest.mark.asyncio
async def test_mission6_attachments_field_persisted_on_campaign():
    from services.email_marketing import EmailMarketingService
    fake_db = MagicMock()
    fake_db.users.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[
        {"id": "u1", "email": "x@example.com", "name": "X"}
    ])))
    fake_db.users.find_one = AsyncMock(return_value=None)
    fake_db.email_unsubscribes = MagicMock()
    fake_db.email_unsubscribes.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    fake_db.email_events = MagicMock()
    fake_db.email_events.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    fake_db.email_events.distinct = AsyncMock(return_value=[])
    fake_db.email_campaigns.insert_one = AsyncMock()

    svc = EmailMarketingService(fake_db)
    svc.get_suppressed_emails = AsyncMock(return_value=set())
    svc._log_audit = AsyncMock()  # bypass audit insert
    attachments = [{"id": "a1", "filename": "agenda.pdf", "mime_type": "application/pdf",
                    "size_bytes": 1234, "storage_path": "/tmp/agenda.pdf"}]
    campaign = await svc.create_campaign(
        name="Test", subject="hi", html_content="<p>hi</p>", plain_text_content="hi",
        audience_filters={"segment_type": "all"}, admin_id="a", admin_email="a@a.com",
        attachments=attachments, recipient_type="segment",
    )
    assert campaign["attachments"] == attachments
    fake_db.email_campaigns.insert_one.assert_awaited_once()
