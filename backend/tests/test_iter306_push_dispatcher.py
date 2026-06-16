"""
iter306 — Push Dispatcher unit tests.

Verifies the 6 supported kinds produce correctly shaped payloads
(EN/FR), and unknown kinds short-circuit gracefully without raising.
"""
import asyncio
import pytest
from services.push_dispatcher import _payload_for, dispatch_push


class _FakeDB:
    """Minimal fake DB exposing the `.users.find_one` coroutine and
    `.push_subscriptions.find` so dispatch_push() can run without hitting Mongo.
    """
    class _Users:
        async def find_one(self, *_a, **_kw):
            return {"preferred_language": "en"}
    class _Subs:
        def find(self, *_a, **_kw):
            class _Cursor:
                async def to_list(self, _limit): return []
            return _Cursor()
    def __init__(self):
        self.users = self._Users()
        self.push_subscriptions = self._Subs()


@pytest.mark.parametrize("kind", [
    "outbid", "auction_won", "ending_soon_1h",
    "payment_due", "dispute_resolved", "new_message",
])
def test_payload_kinds_supported_en(kind):
    p = _payload_for(kind, "en", title_item="My Item", amount=100,
                     listing_id="abc", sender_name="Alice", outcome="released")
    assert p is not None
    assert "title" in p and "body" in p
    assert p["type"] == kind


@pytest.mark.parametrize("kind", [
    "outbid", "auction_won", "ending_soon_1h",
    "payment_due", "dispute_resolved", "new_message",
])
def test_payload_kinds_supported_fr(kind):
    p = _payload_for(kind, "fr", title_item="Mon article", amount=100,
                     listing_id="abc", sender_name="Alice", outcome="remboursé")
    assert p is not None
    assert "title" in p and "body" in p


def test_payload_unknown_kind_returns_none():
    assert _payload_for("not_a_real_kind", "en") is None


def test_dispatch_push_returns_zero_when_no_user():
    res = asyncio.run(dispatch_push(_FakeDB(), user_id=None, kind="outbid", title_item="x"))
    assert res == 0


def test_dispatch_push_returns_zero_for_unknown_kind():
    res = asyncio.run(dispatch_push(_FakeDB(), user_id="u1", kind="garbage", title_item="x"))
    assert res == 0
