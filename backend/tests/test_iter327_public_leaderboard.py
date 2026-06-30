"""iter327 — Public Top Contractor Leaderboard widget endpoint tests.

Locks the privacy contract: the endpoint MUST NOT return names, emails,
profile photos, real extension numbers, dollar earnings, or user IDs.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, "/app/backend")


# ─── Helpers ──────────────────────────────────────────────────────────


def _build_app(monkeypatch, contractors):
    """Build an isolated FastAPI app with a stub DB containing the given users."""

    class _FakeCursor:
        def __init__(self, docs):
            self._docs = docs

        def __aiter__(self):
            self._iter = iter(self._docs)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    class _FakeColl:
        def __init__(self, docs):
            self._docs = docs

        def find(self, *_a, **_k):
            return _FakeCursor(self._docs)

    class _FakeDB:
        users = _FakeColl(contractors)

    from routes.contractor_profile_ext import public_leaderboard_router
    import routes.contractor_profile_ext as ext_mod
    monkeypatch.setattr(ext_mod, "_get_db", lambda: _FakeDB())

    app = FastAPI()
    app.include_router(public_leaderboard_router, prefix="/api")
    return app


def _row(**kw):
    return {
        "role": "dialer_contractor",
        "is_active": True,
        "extension_number": "1220",
        "leaderboard_overlay_rate": 0.0,
        "leaderboard_history": [],
        "weekly_volume_score": 100,
        # Sensitive fields that MUST NEVER appear in the response:
        "name": "John Doe",
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "profile_photo_url": "https://s3.amazonaws.com/jdoe.jpg",
        "id": "user-id-secret-1234",
        **kw,
    }


# ─── 1. Smoke ─────────────────────────────────────────────────────────


class TestSmoke:
    def test_endpoint_returns_200_with_no_contractors(self, monkeypatch):
        app = _build_app(monkeypatch, contractors=[])
        client = TestClient(app)
        r = client.get("/api/contractor/leaderboard/public")
        assert r.status_code == 200
        d = r.json()
        assert d["rows"] == []
        assert d["total"] == 0
        assert d["baseline_pct"] == 5.0
        assert d["ceiling_pct"] == 20.0

    def test_endpoint_returns_top_10_by_volume(self, monkeypatch):
        contractors = [_row(extension_number=f"12{i:02d}", weekly_volume_score=100 - i) for i in range(15)]
        app = _build_app(monkeypatch, contractors=contractors)
        client = TestClient(app)
        r = client.get("/api/contractor/leaderboard/public")
        assert r.status_code == 200
        d = r.json()
        assert d["total"] == 10
        assert len(d["rows"]) == 10
        # Ranks are 1-based and contiguous.
        assert [row["rank"] for row in d["rows"]] == list(range(1, 11))


# ─── 2. Privacy Contract (the heart of the feature) ───────────────────


class TestPrivacyContract:
    """Anonymization is the entire point of this endpoint. These tests lock
    the contract so future refactors cannot accidentally leak PII."""

    @pytest.fixture
    def client(self, monkeypatch):
        contractors = [
            _row(extension_number="1220", weekly_volume_score=500, leaderboard_overlay_rate=0.10),
            _row(extension_number="1199", weekly_volume_score=300, leaderboard_overlay_rate=0.05,
                 name="Jane Smith", email="jane@example.com"),
            _row(extension_number="1234", weekly_volume_score=100, leaderboard_overlay_rate=0.00),
        ]
        return TestClient(_build_app(monkeypatch, contractors))

    def test_response_contains_no_sensitive_fields(self, client):
        r = client.get("/api/contractor/leaderboard/public")
        body = r.text
        # PII / private data — must NEVER appear in the response.
        forbidden = [
            "John Doe", "Jane Smith", "John", "Jane", "Smith",
            "john@example.com", "jane@example.com",
            "s3.amazonaws.com", "jdoe.jpg",
            "user-id-secret-1234",
            # Real extension numbers (only the 2-digit prefix should appear).
            '"extension_number": "1220"',
            '"extension_number": "1199"',
            '"extension_number": "1234"',
        ]
        for token in forbidden:
            assert token not in body, f"Privacy violation: {token!r} leaked into public response"

    def test_extension_is_masked(self, client):
        r = client.get("/api/contractor/leaderboard/public")
        rows = r.json()["rows"]
        # Every row's extension_prefix is exactly 4 chars: 2 digits + '**'
        for row in rows:
            ext = row["extension_prefix"]
            assert len(ext) == 4
            assert ext.endswith("**")
            assert ext[:2].isdigit() or ext[:2] == "XX"

    def test_masked_id_format(self, client):
        r = client.get("/api/contractor/leaderboard/public")
        for row in r.json()["rows"]:
            assert row["masked_id"].startswith("Partner #")
            assert row["masked_id"].endswith("**")

    def test_response_keys_are_strictly_whitelisted(self, client):
        r = client.get("/api/contractor/leaderboard/public")
        allowed_row_keys = {
            "rank", "masked_id", "extension_prefix", "overlay_rate_pct",
            "effective_rate_pct", "weeks_in_top_5", "badge_label", "trend",
        }
        for row in r.json()["rows"]:
            extra = set(row.keys()) - allowed_row_keys
            assert not extra, f"Unexpected field(s) in public row: {extra}"


# ─── 3. Math (matches Section 6 of Manual) ────────────────────────────


class TestSection6Math:
    def test_effective_rate_clamps_to_20_pct(self, monkeypatch):
        # Overlay of 18% → base 5 + 18 = 23 → clamped to 20.
        contractors = [_row(extension_number="1200", leaderboard_overlay_rate=0.18)]
        client = TestClient(_build_app(monkeypatch, contractors))
        r = client.get("/api/contractor/leaderboard/public")
        assert r.json()["rows"][0]["effective_rate_pct"] == 20.0

    def test_effective_rate_floors_at_5_pct(self, monkeypatch):
        # Overlay of 0% → effective 5%
        contractors = [_row(extension_number="1200", leaderboard_overlay_rate=0.0)]
        client = TestClient(_build_app(monkeypatch, contractors))
        r = client.get("/api/contractor/leaderboard/public")
        assert r.json()["rows"][0]["effective_rate_pct"] == 5.0

    def test_badge_labels_progress_with_overlay(self, monkeypatch):
        contractors = [
            _row(extension_number="1200", leaderboard_overlay_rate=0.00, weekly_volume_score=1000),  # Rookie
            _row(extension_number="1201", leaderboard_overlay_rate=0.02, weekly_volume_score=900),   # Rising
            _row(extension_number="1202", leaderboard_overlay_rate=0.05, weekly_volume_score=800),   # Pro
            _row(extension_number="1203", leaderboard_overlay_rate=0.09, weekly_volume_score=700),   # Elite
            _row(extension_number="1204", leaderboard_overlay_rate=0.13, weekly_volume_score=600),   # Legendary
        ]
        client = TestClient(_build_app(monkeypatch, contractors))
        r = client.get("/api/contractor/leaderboard/public")
        rows = r.json()["rows"]
        # Sorted by volume desc, so rookie is #1, legendary is #5
        assert rows[0]["badge_label"] == "Rookie"
        assert rows[1]["badge_label"] == "Rising"
        assert rows[2]["badge_label"] == "Pro"
        assert rows[3]["badge_label"] == "Elite"
        assert rows[4]["badge_label"] == "Legendary"

    def test_french_badge_labels(self, monkeypatch):
        contractors = [
            _row(extension_number="1200", leaderboard_overlay_rate=0.13, weekly_volume_score=1000),
        ]
        client = TestClient(_build_app(monkeypatch, contractors))
        r = client.get("/api/contractor/leaderboard/public?lang=fr")
        assert r.json()["rows"][0]["badge_label"] == "Légendaire"

    def test_weeks_in_top_5_counted_from_tail(self, monkeypatch):
        # rank history: 7, 6, 3, 2, 1, 1, 2  → 5 consecutive weeks in Top 5 (from tail)
        history = [{"rank": r, "week_starting": f"2026-W{i:02d}"}
                   for i, r in enumerate([7, 6, 3, 2, 1, 1, 2], start=1)]
        contractors = [_row(extension_number="1200", leaderboard_history=history)]
        client = TestClient(_build_app(monkeypatch, contractors))
        r = client.get("/api/contractor/leaderboard/public")
        assert r.json()["rows"][0]["weeks_in_top_5"] == 5


# ─── 4. Limit & lang query params ─────────────────────────────────────


class TestQueryParams:
    def test_limit_clamps_to_50(self, monkeypatch):
        # Request limit=99 → clamped to 50.
        contractors = [_row(extension_number=f"{1000+i:04d}", weekly_volume_score=1000-i) for i in range(60)]
        client = TestClient(_build_app(monkeypatch, contractors))
        r = client.get("/api/contractor/leaderboard/public?limit=99")
        assert r.json()["limit"] == 50
        assert r.json()["total"] == 50

    def test_limit_floors_at_1(self, monkeypatch):
        contractors = [_row(extension_number=f"12{i:02d}", weekly_volume_score=100-i) for i in range(5)]
        client = TestClient(_build_app(monkeypatch, contractors))
        r = client.get("/api/contractor/leaderboard/public?limit=-5")
        assert r.json()["limit"] == 1
        assert r.json()["total"] == 1

    def test_unknown_lang_falls_back_to_en(self, monkeypatch):
        contractors = [_row(extension_number="1200", leaderboard_overlay_rate=0.13)]
        client = TestClient(_build_app(monkeypatch, contractors))
        r = client.get("/api/contractor/leaderboard/public?lang=de")
        assert r.json()["lang"] == "en"
        assert r.json()["rows"][0]["badge_label"] == "Legendary"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
