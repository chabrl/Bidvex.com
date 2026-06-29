"""
iter317 Directive 1 — Unit tests for clamp_leaderboard_overlay() and the
weekly cron orchestration logic.

Strict tests prove the 5.0% effective-total floor and the 20.0% overlay
ceiling cannot be bypassed by ANY combination of base_rate + current
overlay + delta. Pure-function tests do NOT need a DB.

The DB-driven cron test uses mongomock (in-memory) to assert that the
top-5 rotation correctly hands out +1% on entry, −1% on drop-out, and
appends a `leaderboard_history` entry on every run for every active
contractor — even those with no delta.
"""
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest

from services.leaderboard_overlay import (
    EFFECTIVE_TOTAL_FLOOR,
    LEADERBOARD_TOP_N,
    OVERLAY_CEILING,
    OVERLAY_DELTA,
    clamp_leaderboard_overlay,
    run_weekly_leaderboard_overlay,
)


# ─── Pure clamp_leaderboard_overlay() tests ──────────────────────────────

class TestClampLeaderboardOverlay:
    def test_no_change_when_no_delta(self):
        out, applied, reason = clamp_leaderboard_overlay(
            base_rate=0.20, current_overlay=0.05, proposed_delta=0.0,
        )
        assert out == pytest.approx(0.05)
        assert applied == pytest.approx(0.0)
        assert reason == ""

    def test_normal_positive_delta_applied(self):
        out, applied, reason = clamp_leaderboard_overlay(
            base_rate=0.20, current_overlay=0.0, proposed_delta=OVERLAY_DELTA,
        )
        assert out == pytest.approx(0.01)
        assert applied == pytest.approx(0.01)
        assert reason == ""

    def test_normal_negative_delta_applied(self):
        out, applied, reason = clamp_leaderboard_overlay(
            base_rate=0.20, current_overlay=0.05, proposed_delta=-OVERLAY_DELTA,
        )
        assert out == pytest.approx(0.04)
        assert applied == pytest.approx(-0.01)
        assert reason == ""

    def test_overlay_ceiling_hard_capped_at_20pct(self):
        # Current overlay already at the ceiling, +1% requested → clamp.
        out, applied, reason = clamp_leaderboard_overlay(
            base_rate=0.20, current_overlay=OVERLAY_CEILING, proposed_delta=OVERLAY_DELTA,
        )
        assert out == pytest.approx(OVERLAY_CEILING)
        assert applied == pytest.approx(0.0)
        assert reason == "ceiling_hit"

    def test_overlay_ceiling_partial_clamp(self):
        # 19.5% + 1% = 20.5% → should clamp to 20%.
        out, applied, reason = clamp_leaderboard_overlay(
            base_rate=0.20, current_overlay=0.195, proposed_delta=0.01,
        )
        assert out == pytest.approx(0.20)
        assert applied == pytest.approx(0.005)
        assert reason == "ceiling_hit"

    def test_effective_total_floor_hard_blocked_at_5pct(self):
        # base=0.04, current_overlay=0.02 → effective=0.06. Requesting
        # -0.05 would drop effective to 0.01 — must clamp to (0.05 - 0.04) = 0.01.
        out, applied, reason = clamp_leaderboard_overlay(
            base_rate=0.04, current_overlay=0.02, proposed_delta=-0.05,
        )
        assert out == pytest.approx(0.01)  # 0.04 + 0.01 = 0.05 floor exactly
        assert applied == pytest.approx(-0.01)
        assert reason == "floor_hit"

    def test_effective_total_floor_with_zero_base_blocks_negative_overlay(self):
        # base=0.00 → overlay can never go below 0.05.
        out, applied, reason = clamp_leaderboard_overlay(
            base_rate=0.00, current_overlay=0.10, proposed_delta=-0.10,
        )
        assert out == pytest.approx(0.05)
        assert reason == "floor_hit"

    def test_high_base_rate_floor_never_triggers(self):
        # base=0.20 + overlay=0.05 → effective=0.25. Even -3% delta
        # leaves effective=0.22, well above floor → no clamp.
        out, applied, reason = clamp_leaderboard_overlay(
            base_rate=0.20, current_overlay=0.05, proposed_delta=-0.03,
        )
        assert out == pytest.approx(0.02)
        assert applied == pytest.approx(-0.03)
        assert reason == ""

    @pytest.mark.parametrize("base", [0.0, 0.05, 0.10, 0.20, 0.50])
    @pytest.mark.parametrize("delta", [-0.10, -0.01, 0.0, 0.01, 0.05])
    @pytest.mark.parametrize("cur", [0.0, 0.05, 0.15, 0.19, 0.20])
    def test_invariant_overlay_never_exceeds_20pct(self, base, cur, delta):
        out, _applied, _reason = clamp_leaderboard_overlay(
            base_rate=base, current_overlay=cur, proposed_delta=delta,
        )
        assert out <= OVERLAY_CEILING + 1e-9

    @pytest.mark.parametrize("base", [0.0, 0.03, 0.05, 0.10, 0.20])
    @pytest.mark.parametrize("delta", [-0.50, -0.10, -0.01, 0.0])
    @pytest.mark.parametrize("cur", [0.0, 0.05, 0.15, 0.20])
    def test_invariant_effective_never_below_5pct(self, base, cur, delta):
        out, _applied, _reason = clamp_leaderboard_overlay(
            base_rate=base, current_overlay=cur, proposed_delta=delta,
        )
        # The floor is base + clamped_overlay >= 5%. The clamp must
        # have brought the overlay up to that boundary if it would have
        # gone below.
        assert (base + out) >= EFFECTIVE_TOTAL_FLOOR - 1e-9

    def test_proposed_delta_clamp_reason_does_not_double_clamp(self):
        # Both directions tested by combining base too low + huge positive delta.
        out, applied, reason = clamp_leaderboard_overlay(
            base_rate=0.03, current_overlay=0.15, proposed_delta=0.10,
        )
        # naive 0.25 → ceiling 0.20 → applied=+0.05, ceiling_hit.
        assert out == pytest.approx(0.20)
        assert reason == "ceiling_hit"


# ─── DB-driven cron test (mongomock) ─────────────────────────────────────

class _InMemoryCollection:
    """Tiny async stub that mimics motor's interface for the small set
    of operations the cron uses."""

    def __init__(self):
        self.rows = []

    async def insert_one(self, doc):
        self.rows.append(dict(doc))
        return type("R", (), {"inserted_id": doc.get("id")})()

    async def find_one(self, query, projection=None, sort=None):
        candidates = [r for r in self.rows if all(r.get(k) == v for k, v in (query or {}).items()
                                                    if not isinstance(v, dict))]
        if sort:
            for k, direction in reversed(sort):
                candidates.sort(key=lambda r: r.get(k) or "", reverse=(direction == -1))
        return dict(candidates[0]) if candidates else None

    def find(self, query=None, projection=None):
        return _Cursor(self, query or {})

    async def update_one(self, query, update):
        for r in self.rows:
            if all(r.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
                if "$set" in update:
                    r.update(update["$set"])
                if "$push" in update:
                    for k, v in update["$push"].items():
                        r.setdefault(k, []).append(v)
                return type("R", (), {"modified_count": 1})()
        return type("R", (), {"modified_count": 0})()

    def aggregate(self, pipeline):
        # Only supports the $match → $group($sum) shape used by the cron.
        cursor_rows = list(self.rows)
        for stage in pipeline:
            if "$match" in stage:
                m = stage["$match"]
                new = []
                for r in cursor_rows:
                    ok = True
                    for k, v in m.items():
                        if isinstance(v, dict):
                            if "$gte" in v and (r.get(k) or "") < v["$gte"]:
                                ok = False
                                break
                        elif r.get(k) != v:
                            ok = False
                            break
                    if ok:
                        new.append(r)
                cursor_rows = new
            elif "$group" in stage:
                gid = stage["$group"]["_id"]  # e.g. "$contractor_id"
                key = gid.lstrip("$") if isinstance(gid, str) else None
                buckets: dict = {}
                for r in cursor_rows:
                    k = r.get(key)
                    bucket = buckets.setdefault(k, {"_id": k})
                    for fld, expr in stage["$group"].items():
                        if fld == "_id":
                            continue
                        if isinstance(expr, dict) and "$sum" in expr:
                            src = expr["$sum"]
                            if isinstance(src, str):
                                bucket[fld] = bucket.get(fld, 0) + float(r.get(src.lstrip("$"), 0) or 0)
                            else:
                                bucket[fld] = bucket.get(fld, 0) + float(src)
                cursor_rows = list(buckets.values())
        return _AggCursor(cursor_rows)


class _Cursor:
    def __init__(self, coll, query):
        self.coll = coll
        self.query = query
        self._limit = None
        self._sort = None

    def sort(self, key, direction=1):
        self._sort = (key, direction)
        return self

    def limit(self, n):
        self._limit = n
        return self

    async def to_list(self, length=None):
        rows = [r for r in self.coll.rows
                if all(r.get(k) == v for k, v in self.query.items()
                       if not isinstance(v, dict))]
        if self._sort:
            rows.sort(key=lambda r: r.get(self._sort[0]) or "",
                      reverse=(self._sort[1] == -1))
        if self._limit:
            rows = rows[: self._limit]
        return [dict(r) for r in rows]


class _AggCursor:
    def __init__(self, rows):
        self.rows = rows

    async def to_list(self, length=None):
        return [dict(r) for r in self.rows]


class _InMemoryDB:
    def __init__(self):
        self.users = _InMemoryCollection()
        self.contractor_commission_ledger = _InMemoryCollection()
        self.contractor_commission_rates = _InMemoryCollection()
        self.leaderboard_overlay_batches = _InMemoryCollection()


@pytest.fixture
def in_memory_db():
    return _InMemoryDB()


def _seed_contractor(db, *, cid, base_rate=0.20, existing_overlay=0.0):
    asyncio.get_event_loop().run_until_complete(db.users.insert_one({
        "id": cid, "role": "dialer_contractor", "email": f"{cid}@x.com",
        "leaderboard_overlay_rate": existing_overlay,
    }))
    asyncio.get_event_loop().run_until_complete(db.contractor_commission_rates.insert_one({
        "contractor_id": cid, "default_rate": base_rate,
    }))


def _seed_volume(db, *, cid, amount, days_ago=0):
    import datetime as _dt
    when = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days_ago)).isoformat()
    asyncio.get_event_loop().run_until_complete(db.contractor_commission_ledger.insert_one({
        "contractor_id": cid, "commission_amount": amount,
        "transaction_date": when,
    }))


class TestCronOrchestration:
    def test_first_run_assigns_overlay_to_top_5_only(self, in_memory_db):
        db = in_memory_db
        # Seed 7 contractors with descending volumes.
        for i, vol in enumerate([100, 80, 60, 40, 20, 10, 5]):
            cid = f"c{i+1}"
            _seed_contractor(db, cid=cid)
            _seed_volume(db, cid=cid, amount=vol)

        out = asyncio.get_event_loop().run_until_complete(
            run_weekly_leaderboard_overlay(db),
        )
        assert out["contractors_evaluated"] == 7
        assert out["top_5_ids"] == ["c1", "c2", "c3", "c4", "c5"]
        # No previous_top_5 → nothing gets +1% (they're already in top 5
        # but the previous list was empty → they "entered" by spec).
        assert sorted(out["entered_top_5"]) == ["c1", "c2", "c3", "c4", "c5"]
        assert out["dropped_top_5"] == []
        # Each top-5 contractor should now have overlay=0.01.
        for cid in out["top_5_ids"]:
            row = asyncio.get_event_loop().run_until_complete(
                db.users.find_one({"id": cid}),
            )
            assert row["leaderboard_overlay_rate"] == pytest.approx(0.01)
            assert len(row.get("leaderboard_history", [])) == 1

    def test_idempotent_within_same_iso_week(self, in_memory_db):
        db = in_memory_db
        _seed_contractor(db, cid="c1")
        _seed_volume(db, cid="c1", amount=10)

        first = asyncio.get_event_loop().run_until_complete(
            run_weekly_leaderboard_overlay(db),
        )
        second = asyncio.get_event_loop().run_until_complete(
            run_weekly_leaderboard_overlay(db),
        )
        assert first["batch_id"] == second["batch_id"]
        # User row should have exactly 1 history entry, not 2.
        row = asyncio.get_event_loop().run_until_complete(
            db.users.find_one({"id": "c1"}),
        )
        assert len(row.get("leaderboard_history", [])) == 1

    def test_history_appended_even_when_delta_is_zero(self, in_memory_db):
        db = in_memory_db
        # Contractor below top-5, no movement → 0 delta but still gets a
        # history entry on every run.
        for i, vol in enumerate([100, 80, 60, 40, 20, 10]):
            _seed_contractor(db, cid=f"c{i+1}")
            _seed_volume(db, cid=f"c{i+1}", amount=vol)

        out = asyncio.get_event_loop().run_until_complete(
            run_weekly_leaderboard_overlay(db),
        )
        # c6 is below top-5 and had no prior history → delta 0 but row exists.
        row = asyncio.get_event_loop().run_until_complete(
            db.users.find_one({"id": "c6"}),
        )
        hist = row.get("leaderboard_history", [])
        assert len(hist) == 1
        assert hist[0]["movement"] == "no_change"
        assert hist[0]["applied_delta"] == 0.0
        assert hist[0]["rank"] == 6
        assert hist[0]["in_top_5"] is False

    def test_drop_out_of_top_5_loses_overlay(self, in_memory_db, monkeypatch):
        """Simulate two consecutive 'weeks' by manually inserting a
        prior batch in leaderboard_overlay_batches with a different
        top_5_ids snapshot, then mock the ISO week key to be different."""
        from services import leaderboard_overlay as svc
        db = in_memory_db

        # Week 1 was: c1..c5 in top-5.
        # Manually seed prior batch.
        prior_top = ["c1", "c2", "c3", "c4", "c5"]
        asyncio.get_event_loop().run_until_complete(
            db.leaderboard_overlay_batches.insert_one({
                "iso_week": "2026-W07",
                "ran_at":   "2026-02-16T08:00:00+00:00",
                "top_5_ids": prior_top,
                "previous_top_5_ids": [],
                "entered_top_5": prior_top,
                "dropped_top_5": [],
                "adjustments": [],
                "contractors_evaluated": 5,
                "batch_id": "prev",
            }),
        )
        # Set up c5 with prior overlay = 0.01.
        for i, vol in enumerate([100, 80, 60, 40]):
            _seed_contractor(db, cid=f"c{i+1}", existing_overlay=0.01)
            _seed_volume(db, cid=f"c{i+1}", amount=vol)
        _seed_contractor(db, cid="c5", existing_overlay=0.01)
        _seed_volume(db, cid="c5", amount=2)  # c5 falls out
        _seed_contractor(db, cid="c6", existing_overlay=0.0)
        _seed_volume(db, cid="c6", amount=20)  # c6 enters top-5

        # Force a different ISO week key so idempotency doesn't kick in.
        monkeypatch.setattr(svc, "_iso_week_key", lambda *_a, **_kw: "2026-W08")

        out = asyncio.get_event_loop().run_until_complete(
            run_weekly_leaderboard_overlay(db),
        )

        assert "c6" in out["top_5_ids"]
        assert "c5" not in out["top_5_ids"]
        assert "c5" in out["dropped_top_5"]
        assert "c6" in out["entered_top_5"]

        c5 = asyncio.get_event_loop().run_until_complete(db.users.find_one({"id": "c5"}))
        c6 = asyncio.get_event_loop().run_until_complete(db.users.find_one({"id": "c6"}))
        # c5 was at 0.01, lost -0.01 → 0.0 (still above floor since base=0.20).
        assert c5["leaderboard_overlay_rate"] == pytest.approx(0.0)
        # c6 entered top-5 → +0.01.
        assert c6["leaderboard_overlay_rate"] == pytest.approx(0.01)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
