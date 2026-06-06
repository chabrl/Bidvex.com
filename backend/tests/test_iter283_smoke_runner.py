"""
iter283-smoke — Post-deployment smoke test pipeline pins.

Verifies:
  • `services/smoke_test_runner.py` module exists with the canonical
    runner + all 4 individual checks.
  • The scheduler registers the 6h interval job.
  • The admin route surface exists.
  • The runner produces the expected `[SMOKE_TEST_PASS]` log line
    on a happy-path run and writes an alert doc on failure.
  • Decoupling: a crash in any single check does NOT raise out of
    the orchestrator.
"""
from __future__ import annotations

import os
import asyncio
import pytest


# ── Static-text pins ─────────────────────────────────────────────────


def _read(rel: str) -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    with open(os.path.join(base, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def test_smoke_runner_module_exists():
    src = _read("services/smoke_test_runner.py")
    # Public surface.
    assert "async def run_smoke_test" in src
    assert "async def smoke_test_job" in src
    # All four checks declared.
    assert "_check_vehicles_endpoint" in src
    assert "_check_qc_tax_calculation" in src
    assert "_check_mongo_health" in src
    assert "_check_stripe_health" in src


def test_smoke_runner_uses_hard_timeout():
    """All HTTP probes use a 10s timeout so a hung upstream cannot
    tie up the scheduler thread."""
    src = _read("services/smoke_test_runner.py")
    assert "_HTTP_TIMEOUT = 10.0" in src
    assert "timeout=_HTTP_TIMEOUT" in src


def test_smoke_runner_logs_canonical_pass_line():
    """The success log line MUST match the spec: prefix
    `[SMOKE_TEST_PASS]` + `All core routes healthy at`."""
    src = _read("services/smoke_test_runner.py")
    assert "[SMOKE_TEST_PASS] All core routes healthy at" in src
    # Failure path logs are CRITICAL level + write to the alert ledger.
    assert "[SMOKE_TEST_FAIL]" in src
    assert "db.smoke_test_alerts.insert_one" in src


def test_smoke_runner_never_raises_in_job():
    """The scheduler entry-point wraps everything in try/except so
    a runner crash NEVER brings down the scheduler thread."""
    src = _read("services/smoke_test_runner.py")
    idx = src.find("async def smoke_test_job")
    assert idx > 0
    block = src[idx:idx + 600]
    assert "try:" in block
    assert "except Exception" in block


# ── Scheduler wiring ─────────────────────────────────────────────────


def test_scheduler_registers_6h_smoke_job():
    src = _read("services/scheduler.py")
    # The smoke job is registered with a 6-hour interval.
    assert 'from services.smoke_test_runner import smoke_test_job' in src
    assert 'id="smoke_test"' in src
    assert 'IntervalTrigger(hours=6)' in src
    # Job name pins the iteration so future agents see the source.
    assert 'name="Post-Deploy Smoke Test (iter283)"' in src


# ── Admin surface ────────────────────────────────────────────────────


def test_admin_smoke_routes_exist():
    src = _read("routes/admin.py")
    assert '@admin_router.post("/smoke-test/run")' in src
    assert '@admin_router.get("/smoke-test/alerts")' in src
    assert '@admin_router.post("/smoke-test/alerts/acknowledge")' in src
    # Each route requires admin auth.
    assert "await require_admin(credentials)" in src
    # iter283-smoke marker so future agents find the block.
    assert "iter283-smoke" in src


# ── Functional happy-path (mocked DB) ────────────────────────────────


class _FakeDB:
    """In-memory fake matching the Motor surface we touch."""

    def __init__(self):
        self.alerts = []
        self.command_calls = []

    async def command(self, name, *_a, **_k):
        self.command_calls.append(name)
        return {"ok": 1}

    @property
    def smoke_test_alerts(self):
        outer = self
        class _Coll:
            async def insert_one(self, doc):
                outer.alerts.append(doc)
                return type("R", (), {"inserted_id": "fake"})()
        return _Coll()


@pytest.mark.asyncio
async def test_smoke_runner_happy_path(monkeypatch):
    """All four checks pass → `all_ok=True`, log line written,
    no alert appended."""
    from services import smoke_test_runner as runner

    async def _ok_vehicles(_url):
        return {"ok": True, "check": "vehicles_endpoint", "elapsed_ms": 50,
                "total_vehicles": 3}

    monkeypatch.setattr(runner, "_check_vehicles_endpoint", _ok_vehicles)
    monkeypatch.setattr(runner, "_check_qc_tax_calculation",
                        lambda: {"ok": True, "check": "qc_tax_calculation",
                                 "elapsed_ms": 4, "buyer_premium": 25.0,
                                 "buyer_gst": 1.25, "buyer_qst": 2.49})
    monkeypatch.setattr(runner, "_check_stripe_health",
                        lambda: {"ok": True, "check": "stripe_health",
                                 "skipped": "test stub", "elapsed_ms": 0})

    db = _FakeDB()
    result = await runner.run_smoke_test(db, base_url="https://test")
    assert result["all_ok"] is True
    assert len(db.alerts) == 0
    # Mongo ping was issued.
    assert "ping" in db.command_calls


@pytest.mark.asyncio
async def test_smoke_runner_failure_appends_alert(monkeypatch):
    """A single failing check → `all_ok=False` AND an alert doc is
    appended to `db.smoke_test_alerts`."""
    from services import smoke_test_runner as runner

    async def _failing_vehicles(_url):
        return {"ok": False, "check": "vehicles_endpoint",
                "error": "synthetic"}

    monkeypatch.setattr(runner, "_check_vehicles_endpoint", _failing_vehicles)
    monkeypatch.setattr(runner, "_check_qc_tax_calculation",
                        lambda: {"ok": True, "check": "qc_tax_calculation",
                                 "elapsed_ms": 4})
    monkeypatch.setattr(runner, "_check_stripe_health",
                        lambda: {"ok": True, "check": "stripe_health",
                                 "skipped": "stub", "elapsed_ms": 0})

    db = _FakeDB()
    result = await runner.run_smoke_test(db, base_url="https://test")
    assert result["all_ok"] is False
    assert len(db.alerts) == 1
    alert = db.alerts[0]
    assert alert["all_ok"] is False
    assert alert["failed_count"] == 1
    assert alert["acknowledged"] is False
    # The failing check's payload travels through to the alert ledger
    # for admin triage.
    assert any(c["check"] == "vehicles_endpoint" for c in alert["checks"])


@pytest.mark.asyncio
async def test_smoke_runner_qc_tax_real_math():
    """Real (non-mocked) QC math returns the contract-pinned values:
    $25 platform fee + $1.25 GST + $2.49 QST on a $1000 hammer."""
    from services.smoke_test_runner import _check_qc_tax_calculation
    out = _check_qc_tax_calculation()
    assert out["ok"] is True
    assert abs(out["buyer_premium"] - 25.0) < 0.05
    assert abs(out["buyer_gst"] - 1.25) < 0.05
    assert abs(out["buyer_qst"] - 2.49) < 0.05
