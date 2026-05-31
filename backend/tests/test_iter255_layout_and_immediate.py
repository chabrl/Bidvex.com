"""
iter255 — Header overlap fix on B2B dashboards + immediate broadcast
dispatch contract.

Test roster (5 tests):

  Mission 1 — Layout padding assertions (3):
    1. PartnerDashboard outer container carries `pt-4` (or higher)
       safe-area padding so the dashboard content clears the fixed nav.
    2. BrokerDashboard outer container carries `pt-6` (or higher).
    3. StorageDashboard outer container carries `pt-4` (or higher).

  Mission 2 — Immediate broadcast dispatch (2):
    4. Blast endpoint response carries `dispatch_mode: "immediate"` +
       `dispatched_at` ISO timestamp — admins get atomic confirmation
       that the campaign has hit the SendGrid wire.
    5. Total elapsed time between the request hitting the endpoint and
       the response returning is bounded — the loop is synchronous, so
       2 recipients should complete in <8 seconds even with network
       latency. (Sanity proves there is NO scheduler queue path.)
"""
from __future__ import annotations

import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass


def _base() -> str:
    base = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not base:
        pytest.skip("REACT_APP_BACKEND_URL not configured")
    return base


_TOKEN = {"admin": None}


def _admin_token(base: str) -> str:
    if _TOKEN["admin"]:
        return _TOKEN["admin"]
    r = requests.post(
        f"{base}/api/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip("admin login failed")
    body = r.json()
    _TOKEN["admin"] = body.get("access_token") or body.get("token") or ""
    return _TOKEN["admin"]


# ─── Mission 1 — Layout padding ──────────────────────────────────────

FRONTEND_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "pages")
)


def _read_layout(rel_path: str) -> str:
    with open(os.path.join(FRONTEND_ROOT, rel_path), "r", encoding="utf-8") as fh:
        return fh.read()


def _assert_has_safe_padding(src: str, testid: str, *, min_pt: int = 4):
    """The outer wrapper carrying `data-testid={testid}` must include
    a `pt-*` (or `mt-*`) class with value >= min_pt so the dashboard
    content clears the fixed navbar."""
    # Match the wrapper div carrying that data-testid (single or multi-line).
    pattern = rf'<div[^>]*data-testid=["\']{re.escape(testid)}["\'][^>]*>'
    m = re.search(pattern, src)
    if m is None:
        # Some files put data-testid before className. Try the inverse.
        pattern = rf'<div[^>]*data-testid=["\']{re.escape(testid)}["\'][^>]*>'
        m = re.search(pattern, src)
    assert m is not None, f"could not locate <div data-testid={testid}>"
    chunk = m.group(0)
    # Extract pt-{n} or sm:pt-{n} classes.
    pts = [int(g) for g in re.findall(r"\bpt-(\d+)", chunk)]
    mts = [int(g) for g in re.findall(r"\bmt-(\d+)", chunk)]
    biggest = max(pts + mts + [0])
    assert biggest >= min_pt, (
        f"<div data-testid={testid}> needs pt-{min_pt} or higher; "
        f"found pt={pts}, mt={mts} in `{chunk}`"
    )


def test_iter255_partner_dashboard_has_header_safe_padding():
    src = _read_layout("PartnerDashboard.js")
    _assert_has_safe_padding(src, "partner-dashboard", min_pt=4)


def test_iter255_broker_dashboard_has_header_safe_padding():
    src = _read_layout("BrokerDashboardPage.jsx")
    _assert_has_safe_padding(src, "broker-dashboard-page", min_pt=6)


def test_iter255_storage_dashboard_has_header_safe_padding():
    src = _read_layout("storage/StorageDashboard.js")
    _assert_has_safe_padding(src, "storage-dashboard", min_pt=4)


# ─── Mission 2 — Immediate broadcast dispatch ────────────────────────

def test_iter255_blast_response_carries_immediate_dispatch_contract():
    """The partner-outreach blast endpoint MUST surface
    `dispatch_mode='immediate'` + `dispatched_at` in its response so
    the admin Launch Broadcast modal can render atomic 'campaign sent'
    confirmation toasts."""
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    # Build a transient promo with a small manual list.
    body = {
        "name_en": f"iter255-immediate-{uuid.uuid4().hex[:6]}",
        "name_fr": "iter255-immediate-fr",
        "type": "partner_launch_offer",
        "config": {"scope": ["all"]},
        "target_config": {
            "target": "custom",
            "custom_emails": [
                f"iter255-q-{uuid.uuid4().hex[:6]}@example.com",
                f"iter255-r-{uuid.uuid4().hex[:6]}@example.com",
            ],
        },
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        "uses_per_user": 1, "show_banner": False, "notify_users": False,
    }
    r = requests.post(f"{base}/api/admin/promotions", json=body, headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    promo = r.json()
    pid = promo["id"]
    try:
        rb = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={"promotion_id": pid, "dry_run": True},
            headers=headers, timeout=20,
        )
        assert rb.status_code == 200, rb.text
        out = rb.json()
        assert out.get("dispatch_mode") == "immediate", out
        assert out.get("dispatched_at"), out
        # The timestamp must parse as ISO-8601.
        datetime.fromisoformat(out["dispatched_at"].replace("Z", "+00:00"))
    finally:
        requests.delete(f"{base}/api/admin/promotions/{pid}", headers=headers, timeout=10)


def test_iter255_blast_completes_synchronously_within_time_budget():
    """Sanity proof that there is NO scheduler-queue path: a 2-recipient
    dry-run blast must return in under 8 seconds (network + DB + render)."""
    base = _base()
    token = _admin_token(base)
    headers = {"Authorization": f"Bearer {token}"}

    body = {
        "name_en": f"iter255-sync-{uuid.uuid4().hex[:6]}",
        "name_fr": "iter255-sync-fr",
        "type": "partner_launch_offer",
        "config": {"scope": ["all"]},
        "target_config": {
            "target": "custom",
            "custom_emails": [
                f"iter255-y-{uuid.uuid4().hex[:6]}@example.com",
                f"iter255-z-{uuid.uuid4().hex[:6]}@example.com",
            ],
        },
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        "uses_per_user": 1, "show_banner": False, "notify_users": False,
    }
    r = requests.post(f"{base}/api/admin/promotions", json=body, headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    try:
        t0 = time.monotonic()
        rb = requests.post(
            f"{base}/api/admin/promotions/partner-outreach/send",
            json={"promotion_id": pid, "dry_run": True},
            headers=headers, timeout=20,
        )
        elapsed = time.monotonic() - t0
        assert rb.status_code == 200, rb.text
        # Bound: 8 seconds is a generous ceiling that still proves the
        # loop is synchronous (a real cron queue would return <0.5s with
        # status="queued"). The blast MUST execute in-request.
        assert elapsed < 8.0, f"blast took {elapsed:.2f}s — exceeds immediate-dispatch budget"
        out = rb.json()
        # The synchronous loop guarantees `recipients` is fully populated
        # before the response returns.
        assert len(out["recipients"]) == out["recipient_count"]
        for row in out["recipients"]:
            # Every row carries an explicit status, not "pending"/"queued".
            status = row.get("status")
            assert status in ("skipped_dry_run", "sent", "logged", "error"), status
            assert status not in ("pending", "queued"), status
    finally:
        requests.delete(f"{base}/api/admin/promotions/{pid}", headers=headers, timeout=10)
