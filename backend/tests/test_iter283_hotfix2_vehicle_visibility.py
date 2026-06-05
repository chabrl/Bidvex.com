"""
iter283-hotfix-2 — Vehicle visibility deep fix.

The previous iter283-hotfix Mission 2 relaxed the visibility column on
the public /vehicles browse, but vehicles in the production data
remained invisible because:

  1. Vehicle listings are created with `status=DRAFT` and require a
     strict approval workflow (DRAFT → PENDING_APPROVAL → APPROVED →
     ACTIVE) gated by minimum-photo counts AND a global
     `vehicle_auctions_enabled` toggle. Real sellers complete the
     form and see nothing.

  2. `vehicle_listings.seller_id` references `vehicle_sellers.id`,
     NOT `users.id`. Backfills that joined on `users` were no-ops.

  3. Admin-approved listings end up in `APPROVED` status, not
     `ACTIVE`, when the global toggle is False (default) — invisible
     to public browse.

This iteration:
  • Fast-tracks vehicles created by approved sellers to ACTIVE.
  • Defaults `vehicle_auctions_enabled` to True so future approvals
    flip cleanly.
  • Expands the public browse to include status APPROVED alongside
    ACTIVE.
"""
from __future__ import annotations

import os
import pytest


def _read(rel: str) -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    with open(os.path.join(base, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ── Create-time fast-track ────────────────────────────────────────────


def test_hotfix2_create_fast_tracks_trusted_sellers():
    """The vehicle create endpoint MUST detect trusted sellers (admin,
    partner-verified, vehicle dealer, storage facility) and write
    `status=ACTIVE` directly. Untrusted sellers still go through the
    DRAFT workflow."""
    src = _read("routes/vehicles.py")
    idx = src.find("# iter283-hotfix-2 — Trusted-seller fast-track")
    assert idx > 0, "hotfix-2 fast-track block missing"
    block = src[idx:idx + 1500]
    # Every trust signal is checked.
    for marker in (
        'role',
        'admin',
        'is_partner',
        'is_vehicle_dealer',
        'is_storage_facility',
        'verification_status',
    ):
        assert marker in block
    # The fast-track flips status to ACTIVE before insert.
    assert "_VLS.ACTIVE.value" in block
    assert "approved_at" in block
    assert "approved_by" in block


# ── Public browse status filter ───────────────────────────────────────


def test_hotfix2_public_browse_includes_approved_status():
    """The public /vehicles browse MUST surface BOTH ACTIVE and
    APPROVED listings. APPROVED = admin-vetted but waiting on the
    global launch toggle. Hiding them traps inventory in a state
    the frontend can't represent."""
    src = _read("routes/vehicles.py")
    idx = src.find("# iter283-hotfix Mission 2 / hotfix-2")
    assert idx > 0, "hotfix-2 public-browse block missing"
    block = src[idx:idx + 1500]
    assert "_VLS.ACTIVE.value" in block
    assert "_VLS.APPROVED.value" in block
    # Visibility column is still flexed.
    assert '"$exists": False' in block


# ── Startup backfill ──────────────────────────────────────────────────


def test_hotfix2_backfill_uses_vehicle_sellers_id():
    """The seller-ID gate MUST query `vehicle_sellers` (verified
    sellers) not `users` — the listing's `seller_id` is the
    vehicle_sellers id, not the user id. Earlier backfills did
    the wrong join and the production drafts stayed stuck."""
    src = _read("services/vehicle_fast_track.py")
    assert "db.vehicle_sellers.find" in src
    assert '"verification_status": "approved"' in src
    # No (wrong) users.find call.
    assert "db.users.find" not in src


def test_hotfix2_backfill_promotes_draft_pending_and_approved():
    """The promotion targets every non-public status that should be
    visible after vetting: DRAFT, PENDING_APPROVAL, APPROVED."""
    src = _read("services/vehicle_fast_track.py")
    for st in ("draft", "pending_approval", "approved"):
        assert f'"{st}"' in src, f"status {st!r} missing from promotion target"


def test_hotfix2_toggle_default_true():
    """`vehicle_auctions_enabled` MUST default to True when missing.
    The flag was designed for emergency pause, not for a permanent
    default-off state."""
    src = _read("services/vehicle_fast_track.py")
    idx = src.find("ensure_vehicle_auctions_toggle_default")
    assert idx > 0
    block = src[idx:idx + 1500]
    assert '"vehicle_auctions_enabled": True' in block
    # Both the insert (no doc) and update ($exists=False) paths set True.
    assert block.count('"vehicle_auctions_enabled": True') >= 2


def test_hotfix2_server_wires_backfill():
    """`server.py` startup MUST call both fast-track helpers — without
    this the production drafts never get promoted."""
    src = _read("server.py")
    assert "fast_track_trusted_drafts" in src
    assert "ensure_vehicle_auctions_toggle_default" in src
    assert "iter283-hotfix-2" in src
